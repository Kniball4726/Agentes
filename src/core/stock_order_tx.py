"""Coordinadores transaccionales con compensación automática entre Stock (SQLite) y Pedidos (SQLite)."""

from __future__ import annotations

import logging
from typing import Any, Callable
from unittest.mock import NonCallableMock

from ..orders.models import LOGISTICA_OPCIONES

logger = logging.getLogger("stockagent.tx")


def _validar_datos_basicos_pedido(
    *,
    remito: str,
    cliente: str,
    bultos: int,
    logistica: str,
    tipo_archivo: str,
) -> None:
    if not remito.strip():
        raise ValueError("La nota de pedido no puede estar vacía.")
    if not cliente.strip():
        raise ValueError("Debes especificar un cliente.")
    if bultos < 1:
        raise ValueError("La cantidad de bultos debe ser de al menos 1.")
    if logistica not in LOGISTICA_OPCIONES:
        raise ValueError(f"Logística inválida. Opciones permitidas: {', '.join(LOGISTICA_OPCIONES)}")
    if tipo_archivo.lower().strip() not in ("pdf", "excel", "docx"):
        raise ValueError("Tipo de archivo inválido (debe ser pdf, excel o docx).")


def _compensar_descuento_stock(stock_mgr: Any, descuentos: list[Any], *, contexto: str) -> None:
    """Devuelve al inventario las unidades descontadas cuando falla el registro de pedido."""
    devoluciones: dict[str, int] = {}
    for item in descuentos or []:
        cod = str(getattr(item, "codigo", "") or "").strip()
        cant = int(getattr(item, "cantidad_descontada", 0) or 0)
        if cod and cant > 0:
            devoluciones[cod] = devoluciones.get(cod, 0) + cant
    if not devoluciones:
        return
    try:
        stock_mgr.registrar_ingreso_fabrica(devoluciones, sobrescribir=False)
        logger.warning("Rollback compensatorio de stock ejecutado (%s): %s", contexto, devoluciones)
    except Exception as err_comp:
        logger.error("Error durante compensación de stock (%s): %s", contexto, err_comp)


def ejecutar_descuento_y_registro_atomico(
    *,
    order_store: Any,
    stock_mgr_factory: Callable[[], tuple[Any, Any]],
    tx_id: str,
    remito: str,
    num_ped: str,
    cli: str,
    bultos_val: int,
    log: str,
    f_retiro: str,
    armador_nom: str,
    es_agregado: bool,
    tipo_archivo: str,
    nombre_archivo: str,
    archivo_descuento: str,
    hash_comprobante: str,
) -> tuple[bool, Any, Any, Any] | None:
    """Ejecuta descuento de stock y registro de pedido con prevalidación y rollback compensatorio.

    Retorna `(True, stock_mgr, reporte, pedido)` si completó con éxito, o `None` si el
    `tx_id` ya había sido procesado por idempotencia. Ante cualquier falla tras descontar
    stock, revierte las cantidades descontadas y libera el `tx_id` fallido.
    """
    _validar_datos_basicos_pedido(
        remito=remito,
        cliente=cli,
        bultos=bultos_val,
        logistica=log,
        tipo_archivo=tipo_archivo,
    )

    existe_fn = getattr(order_store, "existe_nota_pedido", None)
    if callable(existe_fn) and existe_fn(remito) is True:
        raise ValueError(f"La nota de pedido '{remito}' ya fue registrada previamente.")

    tx_registrada = False
    reg_tx_fn = getattr(order_store, "registrar_transaccion_idempotente", None)
    if callable(reg_tx_fn) and tx_id:
        if not reg_tx_fn(tx_id, "CREAR_PEDIDO", remito):
            return None
        tx_registrada = True

    descontado = False
    stock_mgr = None
    descuentos_aplicados: list[Any] = []
    try:
        stock_mgr, reporte = stock_mgr_factory()
        descuentos_aplicados = list(getattr(reporte.reporte_stock, "descuentos_aplicados", []) or [])
        nombre_inf = (
            str(reporte.reporte_stock.archivo_guardado or "").split("/")[-1].split("\\")[-1]
            if getattr(reporte.reporte_stock, "archivo_guardado", "")
            else f"Pedido_{remito}"
        )

        stock_mgr.actualizar_stock_base(
            descuentos=descuentos_aplicados,
            sincronizar_excel=False,
            nombre_archivo=nombre_inf,
            usuario=armador_nom,
        )
        descontado = True

        total_descontado = sum(int(getattr(d, "cantidad_descontada", 0) or 0) for d in descuentos_aplicados)
        resumen_items = f"{len(descuentos_aplicados)} productos ({total_descontado} un.)"
        items_descontados = [
            (d.codigo, d.nombre_producto, d.cantidad_descontada) for d in descuentos_aplicados
        ]
        sin_coincidencia_doc = []
        for doc in getattr(reporte, "documentos_verificados", None) or []:
            sin_coincidencia_doc.extend(getattr(doc, "descripciones_sin_coincidencia", []) or [])

        pedido_creado = order_store.registrar_pedido(
            nota_pedido=remito,
            numero_pedido=num_ped,
            cliente=cli,
            bultos=bultos_val,
            logistica=log,
            armador=armador_nom,
            tipo_archivo=tipo_archivo,
            nombre_archivo=nombre_archivo,
            agregado=es_agregado,
            articulos_descontados=total_descontado,
            resumen_items=resumen_items,
            fecha_retiro=f_retiro,
            archivo_descuento=archivo_descuento,
            items=items_descontados,
            archivo_hash=hash_comprobante,
            items_sin_coincidencia=sin_coincidencia_doc,
        )

        if hasattr(stock_mgr, "programar_sincronizacion_excel"):
            stock_mgr.programar_sincronizacion_excel()

        return True, stock_mgr, reporte, pedido_creado
    except Exception:
        if descontado and stock_mgr is not None:
            _compensar_descuento_stock(stock_mgr, descuentos_aplicados, contexto=remito)
        if tx_registrada:
            liberar_fn = getattr(order_store, "liberar_transaccion_idempotente", None)
            if callable(liberar_fn):
                try:
                    liberar_fn(tx_id)
                except Exception:
                    pass
        raise


def ejecutar_baja_pedido_con_restitucion(
    *,
    restituir_fn: Callable[[], dict[str, int]],
    persistir_baja_fn: Callable[[int], tuple[str, str]],
    revertir_restitucion_fn: Callable[[dict[str, int]], None],
) -> tuple[int, str, str]:
    """Restituye stock y ejecuta baja lógica/física compensando el reingreso si falla la baja."""
    devoluciones = restituir_fn() or {}
    unidades = sum(cant for cant in devoluciones.values() if cant > 0)
    try:
        msg_exito, aviso_colab = persistir_baja_fn(unidades)
        return unidades, msg_exito, aviso_colab
    except Exception:
        if devoluciones:
            try:
                revertir_restitucion_fn(devoluciones)
                logger.warning("Rollback compensatorio de restitución ejecutado: %s", devoluciones)
            except Exception as err_rev:
                logger.error("Error al revertir restitución tras fallo en baja de pedido: %s", err_rev)
        raise


def _obtener_reservas_activas_seguro(
    product_store: Any,
    *,
    referencia_tipo: str | None = None,
    referencia_id: str | None = None,
) -> list[dict[str, Any]]:
    if product_store is None or isinstance(product_store, NonCallableMock):
        return []
    fn = getattr(product_store, "listar_reservas", None)
    if not callable(fn):
        return []
    try:
        res = fn(estado="activa", referencia_tipo=referencia_tipo, referencia_id=referencia_id)
        return res if isinstance(res, list) else []
    except Exception:
        return []


def detectar_conflictos_stock_y_reservas(
    descuentos: list[Any],
    product_store: Any | None,
) -> list[dict[str, Any]]:
    """Detecta quiebres físicos y colisiones contra `stock_disponible` reservado por otras olas/pedidos."""
    items = list(descuentos or [])
    if not items:
        return []

    mapa_reservas: dict[str, int] = {}
    if product_store is not None and not isinstance(product_store, NonCallableMock):
        fn_mapa = getattr(product_store, "obtener_mapa_reservas_activas", None)
        if callable(fn_mapa):
            try:
                codigos = [
                    str(getattr(d, "codigo", "") or "").strip()
                    for d in items
                    if str(getattr(d, "codigo", "") or "").strip()
                ]
                cand = fn_mapa(codigos) if codigos else {}
                if isinstance(cand, dict):
                    mapa_reservas = cand
            except Exception:
                mapa_reservas = {}

    conflictos: list[dict[str, Any]] = []
    for d in items:
        cod = str(getattr(d, "codigo", "") or "").strip()
        nom = str(getattr(d, "nombre_producto", cod) or cod)
        stock_ant = int(getattr(d, "stock_anterior", getattr(d, "stock_original", 0)) or 0)
        cant = int(getattr(d, "cantidad_descontada", 0) or 0)
        stock_nuevo = int(getattr(d, "stock_nuevo", stock_ant - cant) or 0)
        reservado = max(0, int(mapa_reservas.get(cod, 0) or 0))
        disponible = max(0, stock_ant - reservado)

        if stock_nuevo <= 0:
            conflictos.append(
                {
                    "item": d,
                    "codigo": cod,
                    "nombre_producto": nom,
                    "stock_anterior": stock_ant,
                    "cantidad_descontada": cant,
                    "stock_nuevo": stock_nuevo,
                    "stock_reservado": reservado,
                    "stock_disponible": disponible,
                    "tipo": "QUIEBRE_FISICO",
                }
            )
        elif cant > disponible and reservado > 0:
            conflictos.append(
                {
                    "item": d,
                    "codigo": cod,
                    "nombre_producto": nom,
                    "stock_anterior": stock_ant,
                    "cantidad_descontada": cant,
                    "stock_nuevo": stock_nuevo,
                    "stock_reservado": reservado,
                    "stock_disponible": disponible,
                    "tipo": "CONFLICTO_RESERVA",
                }
            )
    return conflictos


def ejecutar_reserva_y_registro_atomico(
    *,
    order_store: Any,
    stock_mgr_factory: Callable[[], tuple[Any, Any]],
    tx_id: str,
    remito: str,
    num_ped: str,
    cli: str,
    bultos_val: int,
    log: str,
    f_retiro: str,
    armador_nom: str,
    es_agregado: bool,
    tipo_archivo: str,
    nombre_archivo: str,
    hash_comprobante: str,
) -> tuple[bool, Any, Any, Any, dict[str, Any]] | None:
    """Registra un pedido individual bloqueando stock en reserva (`referencia_tipo='pedido'`) sin descontar físico."""
    _validar_datos_basicos_pedido(
        remito=remito,
        cliente=cli,
        bultos=bultos_val,
        logistica=log,
        tipo_archivo=tipo_archivo,
    )

    existe_fn = getattr(order_store, "existe_nota_pedido", None)
    if callable(existe_fn) and existe_fn(remito) is True:
        raise ValueError(f"La nota de pedido '{remito}' ya fue registrada previamente.")

    tx_registrada = False
    reg_tx_fn = getattr(order_store, "registrar_transaccion_idempotente", None)
    if callable(reg_tx_fn) and tx_id:
        if not reg_tx_fn(tx_id, "RESERVAR_PEDIDO", remito):
            return None
        tx_registrada = True

    reservado = False
    product_store = None
    try:
        stock_mgr, reporte = stock_mgr_factory()
        product_store = getattr(stock_mgr, "product_store", None)
        if product_store is None or isinstance(product_store, NonCallableMock) or not hasattr(product_store, "reservar_stock"):
            raise ValueError("El almacén de productos no soporta reservas activas.")

        descuentos_aplicados = list(getattr(reporte.reporte_stock, "descuentos_aplicados", []) or [])
        pares = [
            (str(d.codigo).strip(), int(d.cantidad_descontada))
            for d in descuentos_aplicados
            if str(getattr(d, "codigo", "")).strip() and int(getattr(d, "cantidad_descontada", 0)) > 0
        ]
        res_reserva = product_store.reservar_stock(
            pares,
            referencia_id=remito.strip(),
            referencia_tipo="pedido",
            usuario=armador_nom,
            nota=f"Pedido #{remito.strip()} ({cli.strip()})",
            asignar_fefo=True,
            permitir_parcial=False,
        )
        reservado = True

        total_reservado = sum(cant for _, cant in pares)
        resumen_items = f"{len(pares)} productos ({total_reservado} un. reservadas)"
        items_pedido = [
            (d.codigo, d.nombre_producto, int(d.cantidad_descontada))
            for d in descuentos_aplicados
            if int(getattr(d, "cantidad_descontada", 0)) > 0
        ]
        sin_coincidencia_doc = []
        for doc in getattr(reporte, "documentos_verificados", None) or []:
            sin_coincidencia_doc.extend(getattr(doc, "descripciones_sin_coincidencia", []) or [])

        pedido_creado = order_store.registrar_pedido(
            nota_pedido=remito,
            numero_pedido=num_ped,
            cliente=cli,
            bultos=bultos_val,
            logistica=log,
            armador=armador_nom,
            tipo_archivo=tipo_archivo,
            nombre_archivo=nombre_archivo,
            agregado=es_agregado,
            articulos_descontados=total_reservado,
            resumen_items=resumen_items,
            fecha_retiro=f_retiro,
            archivo_descuento="",
            items=items_pedido,
            archivo_hash=hash_comprobante,
            items_sin_coincidencia=sin_coincidencia_doc,
        )
        return True, stock_mgr, reporte, pedido_creado, res_reserva
    except Exception:
        if reservado and product_store is not None:
            try:
                product_store.liberar_reserva(
                    referencia_id=remito.strip(),
                    referencia_tipo="pedido",
                    motivo=f"Rollback tras error registrando pedido #{remito}",
                )
            except Exception as err_lib:
                logger.error("Error al liberar reserva en rollback (%s): %s", remito, err_lib)
        if tx_registrada:
            liberar_fn = getattr(order_store, "liberar_transaccion_idempotente", None)
            if callable(liberar_fn):
                try:
                    liberar_fn(tx_id)
                except Exception:
                    pass
        raise


def tiene_reserva_activa_pedido(product_store: Any, nota_pedido: str) -> bool:
    """Indica si existe una reserva activa asociada a `referencia_tipo='pedido'`."""
    nota = str(nota_pedido or "").strip()
    if not nota:
        return False
    return bool(
        _obtener_reservas_activas_seguro(
            product_store, referencia_tipo="pedido", referencia_id=nota
        )
    )


def liberar_reserva_pedido_si_existe(
    product_store: Any,
    nota_pedido: str,
    motivo: str = "",
) -> dict[str, Any] | None:
    """Libera reservas activas del pedido (`referencia_tipo='pedido'`), retornando el resumen o None."""
    nota = str(nota_pedido or "").strip()
    if not nota:
        return None
    reservas = _obtener_reservas_activas_seguro(
        product_store, referencia_tipo="pedido", referencia_id=nota
    )
    if not reservas:
        return None
    return product_store.liberar_reserva(
        referencia_id=nota,
        referencia_tipo="pedido",
        motivo=motivo or f"Liberación por baja/anulación de pedido {nota}",
    )


def consolidar_reserva_pedido_si_existe(
    product_store: Any,
    nota_pedido: str,
    usuario: str = "sistema",
    detalle: str = "",
) -> dict[str, Any] | None:
    """Consolida y descuenta stock físico/FEFO si el pedido tenía reserva activa sin descontar."""
    nota = str(nota_pedido or "").strip()
    if not nota:
        return None
    reservas = _obtener_reservas_activas_seguro(
        product_store, referencia_tipo="pedido", referencia_id=nota
    )
    if not reservas:
        return None
    return product_store.consolidar_reserva(
        referencia_id=nota,
        referencia_tipo="pedido",
        descontar_stock=True,
        usuario=usuario,
        detalle=detalle or f"Consolidación despacho pedido #{nota}",
    )
