"""Operaciones de búsqueda y transacción atómica para Movimientos Rápidos de Stock."""

from __future__ import annotations

import sys
from typing import Any, Callable

import flet as ft

from ...products.barcode_utils import generar_variantes_codigo_lector, normalizar_codigo_lector
from ...webhook_manager import despachar_evento_webhook as _default_despachar_webhook


def obtener_stock_manager_movimiento(interfaz: Any, cache_sm: list[Any]) -> Any:
    """Obtiene o instancia el StockManager disponible desde la interfaz o el Excel base."""
    sm_attr = getattr(interfaz, "stock_manager", None)
    if sm_attr is not None:
        return sm_attr
    if cache_sm[0] is not None:
        return cache_sm[0]
    ruta_excel = getattr(getattr(interfaz, "menu", None), "ruta_excel_base", None)
    if ruta_excel:
        try:
            from src.inventory import StockManager

            cache_sm[0] = StockManager(ruta_excel)
            return cache_sm[0]
        except Exception:
            return None
    return None


def buscar_producto_movimiento(sm: Any, store: Any, raw_val: str) -> tuple[str, Any]:
    """Busca un producto por variantes de código o código de barras; devuelve (query_normalizada, fila)."""
    query = normalizar_codigo_lector(raw_val)
    if not query:
        return "", None

    variantes = generar_variantes_codigo_lector(raw_val) or [query]
    for cand in variantes:
        row = None
        if sm is not None and hasattr(sm, "buscar_producto_por_codigo_o_barras"):
            row = sm.buscar_producto_por_codigo_o_barras(cand)
        if row is None and store is not None:
            row = store.find_product_by_code_or_barcode(cand)
        if row is not None:
            return query, row
    return query, None


def extraer_datos_fila_producto(sm: Any, row: Any) -> dict[str, Any]:
    """Normaliza código, nombre, código de barras y stock actual desde una fila de producto."""
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    codigo = row["code"] if "code" in keys else row[0]
    nombre = row["name"] if "name" in keys else row[1]
    barcode = (
        row["cod_barras"]
        if "cod_barras" in keys and row["cod_barras"]
        else (row["barcode"] if "barcode" in keys else "")
    )

    stock_actual = 0
    if hasattr(sm, "catalogo") and codigo in sm.catalogo:
        stock_actual = int(sm.catalogo[codigo][2])
    elif "stock" in keys:
        stock_actual = int(row["stock"])

    return {
        "codigo": codigo,
        "nombre": nombre,
        "barcode": barcode,
        "stock_actual": stock_actual,
    }


def _resolver_despachar_webhook():
    mod = sys.modules.get("src.ui.dialogs.dlg_movimientos_rapidos")
    if mod is not None and hasattr(mod, "despachar_evento_webhook"):
        return getattr(mod, "despachar_evento_webhook")
    return _default_despachar_webhook


def ejecutar_transaccion_movimiento_rapido(
    interfaz: Any,
    sm: Any,
    *,
    es_ingreso: bool,
    color_tema: str,
    codigo: str,
    nombre: str,
    qty: int,
    stock_previo: int,
    motivo: str,
    obs: str,
    on_error: Callable[[str], None],
    on_cerrar: Callable[[], None],
    cerrar_al_final: bool = True,
) -> bool:
    """Aplica la transacción de stock, historial de movimientos, auditoría, webhook y acción Deshacer."""
    usuario_nom = (
        getattr(interfaz.usuario_actual, "nombre_identificador", None)
        or getattr(interfaz.usuario_actual, "username", "Operador")
    )
    if not sm:
        on_error("Error crítico: Gestor de stock no encontrado.")
        return False

    cantidad_ajuste = qty if es_ingreso else -qty

    try:
        sm.registrar_ingreso_fabrica({codigo: cantidad_ajuste}, sobrescribir=False)

        mtype = "ingreso_rapido" if es_ingreso else "salida_rapida"
        detalle_mov = f"[{motivo}] {obs}".strip()
        if hasattr(sm, "product_store") and sm.product_store:
            sm.product_store.register_movements(
                [(codigo, nombre, cantidad_ajuste, mtype)],
                usuario=usuario_nom,
                detalle=detalle_mov,
            )

        if hasattr(interfaz, "order_store") and interfaz.order_store:
            accion_audit = "INGRESO_RAPIDO" if es_ingreso else "SALIDA_RAPIDA"
            detalle_audit = f"[{motivo}] {codigo} ({nombre}) x{qty} u. - {obs}".strip()
            interfaz.order_store.registrar_auditoria(
                usuario=usuario_nom,
                accion=accion_audit,
                detalle=detalle_audit,
            )

        try:
            _resolver_despachar_webhook()(
                "MOVIMIENTO_RAPIDO",
                {
                    "tipo": "ingreso" if es_ingreso else "salida",
                    "codigo": codigo,
                    "nombre": nombre,
                    "cantidad": qty,
                    "motivo": motivo,
                    "usuario": usuario_nom,
                },
            )
        except Exception:
            pass

        msg_tipo = "Entrada registrada" if es_ingreso else "Salida registrada"
        revertido = [False]

        def _deshacer_movimiento(_ev: Any = None) -> None:
            if revertido[0]:
                return
            revertido[0] = True
            try:
                reversion = -cantidad_ajuste
                sm.registrar_ingreso_fabrica({codigo: reversion}, sobrescribir=False)
                if hasattr(sm, "product_store") and sm.product_store:
                    sm.product_store.register_movements(
                        [(codigo, nombre, reversion, "reversion_movimiento_rapido")],
                        usuario=usuario_nom,
                        detalle=f"Reversión de {msg_tipo.lower()} ({motivo})",
                    )
                if hasattr(interfaz, "order_store") and interfaz.order_store:
                    interfaz.order_store.registrar_auditoria(
                        usuario=usuario_nom,
                        accion="DESHACER_MOVIMIENTO_RAPIDO",
                        detalle=f"Reversión de {msg_tipo.lower()} para {codigo} ({qty} u.). Stock restaurado aprox. a {stock_previo}.",
                    )
                if hasattr(interfaz, "reproducir_sonido"):
                    interfaz.reproducir_sonido("exito")
                interfaz.notificar(f"↩️ Se revirtió el movimiento de {codigo} ({qty} u.).", ft.Colors.BLUE_700)
                if hasattr(interfaz, "actualizar_estado"):
                    interfaz.actualizar_estado()
            except Exception as exc_undo:
                revertido[0] = False
                interfaz.notificar(f"Error al revertir movimiento: {exc_undo}", ft.Colors.RED_700)

        if cerrar_al_final:
            on_cerrar()

        try:
            snack_undo = ft.SnackBar(
                content=ft.Text(f"✅ {msg_tipo}: {codigo} ({qty} u.)", color=ft.Colors.WHITE, size=13),
                action=ft.SnackBarAction(
                    label="Deshacer",
                    text_color=ft.Colors.AMBER_300,
                    on_click=_deshacer_movimiento,
                ),
                duration=6000,
                bgcolor=color_tema,
            )
            if getattr(interfaz, "page", None):
                interfaz.page.show_dialog(snack_undo)
        except Exception:
            interfaz.notificar(f"✅ {msg_tipo}: {codigo} ({qty} u.) por '{motivo}'", color_tema)

        if hasattr(interfaz, "actualizar_estado"):
            try:
                interfaz.actualizar_estado()
            except Exception:
                pass

        return True
    except Exception as ex:
        on_error(f"Error al registrar movimiento: {ex}")
        return False
