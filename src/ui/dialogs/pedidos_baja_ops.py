"""Operaciones transaccionales, helpers de restitución y persistencia para baja de pedidos."""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import NonCallableMock

from ...core.stock_order_tx import (
    ejecutar_baja_pedido_con_restitucion,
    liberar_reserva_pedido_si_existe,
    tiene_reserva_activa_pedido,
)
from ...orders import Pedido
from ._shared import resolve_stock_manager


def _resolver_sm_cls(interfaz: Any = None):
    """Resuelve la clase StockManager vigente mediante inyección en ``interfaz``."""
    return resolve_stock_manager(interfaz)


def _instanciar_stock_manager_baja(interfaz: Any):
    """Instancia ``StockManager`` con la ruta de base de datos y Excel del entorno activo."""
    sm_cls = _resolver_sm_cls(interfaz)
    ruta_base_datos = getattr(interfaz, "ruta_base_datos", None) or getattr(
        interfaz.menu, "ruta_base_datos", None
    )
    kwargs: dict[str, Any] = {"ruta_excel_base": interfaz.menu.ruta_excel_base}
    if ruta_base_datos:
        kwargs["ruta_base_datos"] = ruta_base_datos
    return sm_cls(**kwargs)


def _resolver_product_store_baja(interfaz: Any) -> Any | None:
    """Obtiene ``ProductStore`` real desde ``interfaz`` o ``StockManager``, ignorando mocks vacíos."""
    ps_directo = getattr(interfaz, "product_store", None)
    if (
        ps_directo is not None
        and not isinstance(ps_directo, NonCallableMock)
        and hasattr(ps_directo, "listar_reservas")
    ):
        return ps_directo
    try:
        sm = _instanciar_stock_manager_baja(interfaz)
        ps_sm = getattr(sm, "product_store", None)
        if (
            ps_sm is not None
            and not isinstance(ps_sm, NonCallableMock)
            and hasattr(ps_sm, "listar_reservas")
        ):
            return ps_sm
    except Exception:
        pass
    return None


def _calcular_devoluciones_pedido(interfaz: Any, pedido: Pedido) -> dict[str, int]:
    """Agrupa las cantidades positivas de los ítems de un pedido para reincorporar stock."""
    items = interfaz.order_store.obtener_items_pedido(pedido.id)
    devoluciones: dict[str, int] = {}
    for cod, _desc, cant in items or []:
        if cant > 0:
            devoluciones[cod] = devoluciones.get(cod, 0) + cant
    return devoluciones


def _restituir_stock_pedido(interfaz: Any, pedido: Pedido) -> int:
    """Reincorpora los productos y cantidades de un pedido al stock de SQLite y Productos.xlsx en tiempo real."""
    devoluciones = _calcular_devoluciones_pedido(interfaz, pedido)
    if devoluciones:
        sm = _instanciar_stock_manager_baja(interfaz)
        sm.registrar_ingreso_fabrica(devoluciones, sobrescribir=False)
        try:
            sm.registrar_movimientos_historial(devoluciones, tipo="ingreso_fabrica")
        except Exception:
            pass
    return sum(devoluciones.values())


def _revertir_restitucion_baja(
    interfaz: Any,
    devoluciones: dict[str, int],
    nota_pedido: str,
) -> None:
    """Revierte una restitución previa cuando falla la persistencia en ``OrderStore``."""
    if not devoluciones:
        return
    sm = _instanciar_stock_manager_baja(interfaz)
    descuentos_pos = {cod: int(cant) for cod, cant in devoluciones.items() if cant > 0}
    if not descuentos_pos:
        return
    if hasattr(sm, "descontar_mercado_full"):
        sm.descontar_mercado_full(
            descuentos=descuentos_pos,
            nombre_archivo=f"RollbackBaja_{nota_pedido}",
            sincronizar_excel=True,
        )
    else:
        sm.registrar_ingreso_fabrica(
            {cod: -cant for cod, cant in descuentos_pos.items()},
            sobrescribir=False,
        )


def _resolver_pedido_actual(interfaz: Any, pedido: Pedido) -> Pedido | None:
    """Obtiene el estado vigente del pedido desde el store; tolera mocks sin configurar."""
    store = getattr(interfaz, "order_store", None)
    if store is None:
        return pedido
    for metodo, arg in (
        ("obtener_pedido_por_id", pedido.id),
        ("buscar_pedido_por_nota", pedido.nota_pedido),
    ):
        fn = getattr(store, metodo, None)
        if callable(fn):
            res = fn(arg)
            if res is None:
                return None
            if isinstance(getattr(res, "estado", None), str):
                return res
    return pedido


def _refrescar_vistas_pedido(interfaz: Any, al_final: Callable[[], None] | None) -> None:
    """Ejecuta el callback local y refresca las listas globales del dashboard sin duplicar."""
    act_listas = getattr(interfaz, "actualizar_listas", None)
    if callable(al_final):
        al_final()
    if callable(act_listas) and act_listas is not al_final:
        act_listas()


def _textos_confirmacion_baja(
    pedido: Pedido,
    *,
    es_eliminar: bool,
    ya_anulado: bool,
) -> tuple[str, str, str]:
    """Devuelve texto de confirmación, advertencia de cierre y texto del botón para baja de pedido."""
    if es_eliminar:
        texto = (
            f"¿Confirmas la eliminación física definitiva del pedido anulado de '{pedido.cliente}'? "
            "Se borrará permanentemente de la base de datos y podrás volver a cargar el remito."
            if ya_anulado
            else f"¿Confirmas la eliminación física definitiva del pedido de '{pedido.cliente}'? "
            "Se borrará permanentemente de la base de datos (permitiendo recargar el remito) y los productos se devolverán al stock."
        )
        aviso_cierre = (
            f"⚠️ Atención: Este pedido formó parte del Cierre #{pedido.cierre_id}. "
            "Al eliminarlo, desaparecerá del historial de ese cierre y se restituirá el stock activo."
        )
        return texto, aviso_cierre, "Eliminar Definitivamente"

    texto = (
        f"¿Confirmas el desarmado del pedido de '{pedido.cliente}'? "
        "Se aplicará borrado lógico (estado anulado) y los productos se sumarán de vuelta al stock disponible en el sistema y en el Excel."
    )
    aviso_cierre = (
        f"⚠️ Atención: Este pedido ya formó parte del Cierre #{pedido.cierre_id}. "
        "Al desarmarlo, las unidades se reincorporarán al stock actual."
    )
    return texto, aviso_cierre, "Desarmar y Devolver Stock"


def _persistir_baja_pedido(
    interfaz: Any,
    pedido: Pedido,
    *,
    es_eliminar: bool,
    usr: str,
    motivo_txt: str,
    unidades_restituidas: int,
    unidades_liberadas: int = 0,
) -> tuple[str, str]:
    """Ejecuta el borrado físico o lógico en ``OrderStore`` junto con su registro de auditoría."""
    if es_eliminar:
        interfaz.order_store.eliminar_pedido(
            pedido_id=pedido.id,
            motivo=motivo_txt,
            usuario=usr,
            registrar_auditoria=False,
        )
        accion_texto = (
            f"Reserva liberada: {unidades_liberadas} unidades."
            if unidades_liberadas > 0
            else f"Stock restituido: {unidades_restituidas} unidades."
        )
        interfaz.order_store.registrar_auditoria(
            usuario=usr,
            accion="ELIMINAR_PEDIDO",
            detalle=(
                f"Pedido #{pedido.nota_pedido} ({pedido.cliente}) eliminado definitivamente (borrado físico). "
                f"{accion_texto} Motivo: {motivo_txt or 'Sin especificar'}"
            ),
        )
        msg_exito = f"Pedido #{pedido.nota_pedido} eliminado definitivamente."
        if unidades_liberadas > 0:
            msg_exito += f" Se liberó la reserva de {unidades_liberadas} unidades al disponible."
        elif unidades_restituidas > 0:
            msg_exito += f" Se reincorporaron {unidades_restituidas} unidades al stock."
        return msg_exito, f"🗑️ {usr} eliminó el Pedido #{pedido.nota_pedido} ({pedido.cliente})"

    interfaz.order_store.anular_pedido(
        pedido_id=pedido.id,
        motivo=f"Desarmado de pedido y devolución de stock. {motivo_txt}".strip(),
        usuario=usr,
    )
    accion_texto = (
        f"Reserva liberada: {unidades_liberadas} unidades."
        if unidades_liberadas > 0
        else f"Stock restituido: {unidades_restituidas} unidades."
    )
    interfaz.order_store.registrar_auditoria(
        usuario=usr,
        accion="DESARMAR_PEDIDO",
        detalle=(
            f"Pedido #{pedido.nota_pedido} ({pedido.cliente}) desarmado (borrado lógico). "
            f"{accion_texto} Motivo: {motivo_txt or 'Sin especificar'}"
        ),
    )
    if unidades_liberadas > 0:
        return (
            f"Pedido #{pedido.nota_pedido} desarmado con éxito. Se liberaron {unidades_liberadas} unidades de reserva al disponible.",
            f"⚠️ {usr} desarmó el Pedido #{pedido.nota_pedido} ({pedido.cliente})",
        )
    return (
        f"Pedido #{pedido.nota_pedido} desarmado con éxito. Se reincorporaron {unidades_restituidas} unidades al stock.",
        f"⚠️ {usr} desarmó el Pedido #{pedido.nota_pedido} ({pedido.cliente})",
    )


def liberar_o_restituir_para_baja(
    interfaz: Any,
    pedido_actual: Pedido,
    *,
    motivo_reserva: str,
) -> tuple[dict[str, int], int, int]:
    """Libera reserva activa si existe o restituye stock físico evitando doble devolución.

    Retorna ``(devoluciones_fisicas, unidades_restituidas, unidades_liberadas)``.
    """
    p_store = _resolver_product_store_baja(interfaz)
    res_lib = liberar_reserva_pedido_si_existe(
        p_store,
        pedido_actual.nota_pedido,
        motivo=motivo_reserva,
    )
    if res_lib is not None:
        return {}, 0, int(res_lib.get("unidades_liberadas", 0))
    devoluciones = _calcular_devoluciones_pedido(interfaz, pedido_actual)
    unidades_restituidas = _restituir_stock_pedido(interfaz, pedido_actual) if devoluciones else 0
    return devoluciones, unidades_restituidas, 0


def ejecutar_anulacion_pedido_tx(
    interfaz: Any,
    pedido: Pedido,
    *,
    usr: str,
    motivo_txt: str,
) -> tuple[str, str]:
    """Ejecuta la anulación de un pedido reservado o descontado y retorna ``(msg, aviso_colab)``."""
    pedido_actual = interfaz.order_store.buscar_pedido_por_nota(pedido.nota_pedido) or pedido
    if getattr(pedido_actual, "estado", "") == "anulado":
        return f"El pedido {pedido.nota_pedido} ya se encontraba anulado.", ""

    _, unidades_restituidas, unidades_liberadas = liberar_o_restituir_para_baja(
        interfaz,
        pedido_actual,
        motivo_reserva=motivo_txt or "Anulación de pedido reservado",
    )
    if unidades_liberadas > 0:
        detalle_aud = (
            f"Pedido #{pedido.nota_pedido} ({pedido.cliente}) anulado. "
            f"Reserva liberada: {unidades_liberadas} un. Motivo: {motivo_txt or 'Sin motivo'}"
        )
    else:
        detalle_aud = (
            f"Pedido #{pedido.nota_pedido} ({pedido.cliente}) anulado. "
            f"Stock devuelto: {unidades_restituidas} un. Motivo: {motivo_txt or 'Sin motivo'}"
        )
    interfaz.order_store.anular_pedido(
        pedido_id=pedido.id,
        motivo=f"Anulación de pedido: {motivo_txt}".strip() if motivo_txt else "Anulación de pedido",
        usuario=usr,
    )
    interfaz.order_store.registrar_auditoria(
        usuario=usr,
        accion="ANULAR_PEDIDO",
        detalle=detalle_aud,
    )
    msg = f"Pedido {pedido.nota_pedido} anulado correctamente."
    if unidades_liberadas > 0:
        msg += f" Se liberó la reserva activa de {unidades_liberadas} unidades al disponible."
    elif unidades_restituidas > 0:
        msg += f" Se reincorporaron {unidades_restituidas} unidades al inventario y al Excel."
    return msg, f"⚠️ {usr} anuló el Pedido #{pedido.nota_pedido} ({pedido.cliente})"


def ejecutar_baja_transaccional(
    interfaz: Any,
    pedido: Pedido,
    pedido_actual: Pedido,
    *,
    es_eliminar: bool,
    usr: str,
    motivo_txt: str,
) -> tuple[str, str]:
    """Ejecuta desarmado o eliminación con rollback de restitución física ante fallos."""
    estaba_anulado = getattr(pedido_actual, "estado", "") == "anulado"
    unidades_liberadas = [0]

    def _restituir() -> dict[str, int]:
        if estaba_anulado:
            return {}
        devoluciones, _, liberadas = liberar_o_restituir_para_baja(
            interfaz,
            pedido_actual,
            motivo_reserva=motivo_txt or ("Eliminación de pedido" if es_eliminar else "Desarmado de pedido"),
        )
        unidades_liberadas[0] = liberadas
        return devoluciones

    _, msg_exito, aviso_colab = ejecutar_baja_pedido_con_restitucion(
        restituir_fn=_restituir,
        persistir_baja_fn=lambda unidades: _persistir_baja_pedido(
            interfaz,
            pedido,
            es_eliminar=es_eliminar,
            usr=usr,
            motivo_txt=motivo_txt,
            unidades_restituidas=unidades,
            unidades_liberadas=unidades_liberadas[0],
        ),
        revertir_restitucion_fn=lambda devs: _revertir_restitucion_baja(
            interfaz, devs, pedido_actual.nota_pedido
        ),
    )
    return msg_exito, aviso_colab


__all__ = [
    "_calcular_devoluciones_pedido",
    "_instanciar_stock_manager_baja",
    "_persistir_baja_pedido",
    "_refrescar_vistas_pedido",
    "_resolver_pedido_actual",
    "_resolver_product_store_baja",
    "_resolver_sm_cls",
    "_restituir_stock_pedido",
    "_revertir_restitucion_baja",
    "_textos_confirmacion_baja",
    "ejecutar_anulacion_pedido_tx",
    "ejecutar_baja_transaccional",
    "liberar_o_restituir_para_baja",
    "tiene_reserva_activa_pedido",
]
