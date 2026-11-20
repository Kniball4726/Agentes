"""Diálogos auxiliares y helpers de parseo/confirmación para la creación de pedidos."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Callable

import flet as ft

from ...agent import AgenteRemitosStock
from ...inventory import StockManager as _DefaultStockManager
from ..theme import ROJO


def _resolver_sm_cls():
    mod_ped = sys.modules.get("src.ui.dialogs.dlg_pedidos")
    if mod_ped is not None and hasattr(mod_ped, "_get_stock_manager_cls"):
        return mod_ped._get_stock_manager_cls()
    mod_gui = sys.modules.get("src.flet_gui")
    if mod_gui is not None and hasattr(mod_gui, "StockManager"):
        return getattr(mod_gui, "StockManager")
    return _DefaultStockManager


def parsear_comprobante_pedido(arch_candidato: Path, ruta_excel_base: Path) -> Any | None:
    """Parsea un comprobante PDF, DOCX o Excel y retorna los datos extraídos o None."""
    ext_c = arch_candidato.suffix.lower()
    if ext_c == ".pdf":
        from ...parsers.remito_parser import parsear_remito
        return parsear_remito(arch_candidato)
    if ext_c == ".docx":
        from ...parsers.mercado_libre_parser import parsear_pedido_mercado_libre
        sm = _resolver_sm_cls()(ruta_excel_base)
        return parsear_pedido_mercado_libre(arch_candidato, [(cod, val[1]) for cod, val in sm.catalogo.items()])
    from ...parsers.canjes_parser import parsear_canje_excel
    return parsear_canje_excel(arch_candidato)


def _mostrar_dialogo_exito_pedido(
    interfaz: Any,
    remito: str,
    cli: str,
    bultos_val: int,
    log: str,
    resumen_items: str,
    reporte: Any,
) -> None:
    """Ofrece impresión inmediata de rótulos y muestra alertas de stock crítico tras registrar un pedido."""
    try:
        pedido_reciente = interfaz.order_store.buscar_pedido_por_nota(remito)
        if not (pedido_reciente and interfaz.page):
            return
        items_alerta = []
        for d in reporte.reporte_stock.descuentos_aplicados:
            if d.stock_nuevo <= 0:
                items_alerta.append(f"🔴 [{d.codigo}] {d.nombre_producto}: QUIEBRE (Quedan {d.stock_nuevo} un.)")
            elif d.stock_nuevo <= 5:
                items_alerta.append(f"🟠 [{d.codigo}] {d.nombre_producto}: CRÍTICO (Quedan {d.stock_nuevo} un.)")

        def cerrar_exito(_e):
            interfaz.page.pop_dialog()

        def imprimir_rotulos_directo(_e, ped=pedido_reciente):
            interfaz.page.pop_dialog()
            interfaz.imprimir_rotulos_pedido(ped)

        dialogo_exito = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400), ft.Text("Pedido Registrado y Descontado")]),
            content=ft.Container(
                width=450,
                content=ft.Column(
                    [
                        ft.Text(f"El pedido #{remito} de '{cli}' fue procesado con éxito.", size=13, weight=ft.FontWeight.W_500),
                        ft.Text(f"• Bultos: {bultos_val} · Logística: {log}", size=12, color=interfaz.secundario),
                        ft.Text(f"• Descuento: {resumen_items} en tiempo real.", size=12, color=ft.Colors.GREEN_400),
                        *(
                            [
                                ft.Divider(height=10),
                                ft.Text("⚠️ Advertencia de Inventario:", weight=ft.FontWeight.BOLD, size=11, color=ft.Colors.AMBER_400),
                                ft.Container(
                                    content=ft.ListView([ft.Text(it, size=11, color=interfaz.texto) for it in items_alerta], height=70, spacing=2),
                                    bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_100,
                                    padding=6,
                                    border_radius=4,
                                ),
                            ]
                            if items_alerta
                            else []
                        ),
                        ft.Divider(height=10),
                        ft.Text("¿Deseas imprimir los rótulos A4 para los bultos ahora?", size=12, color=interfaz.texto),
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                ft.Button(f"Rótulos A4 ({bultos_val} b)", icon=ft.Icons.PRINT, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=imprimir_rotulos_directo),
                ft.Button(
                    "Rótulo Térmico Rollo",
                    icon=ft.Icons.LABEL,
                    bgcolor=ft.Colors.PURPLE_700,
                    color=ft.Colors.WHITE,
                    on_click=lambda _e, ped=pedido_reciente: (interfaz.page.pop_dialog(), interfaz.imprimir_rotulos_termicos_pedido(ped)),
                ),
                interfaz.boton_dialogo("Listo / Continuar", cerrar_exito),
            ],
        )
        interfaz.page.show_dialog(dialogo_exito)
    except Exception as ex_post:
        print(f"[AVISO] Error al mostrar diálogo posterior: {ex_post}")


def _mostrar_alerta_preventiva_quiebre(
    interfaz: Any,
    remito: str,
    cli: str,
    quiebres: list[Any],
    ejecutar_descuento_pedido: Callable[[], None],
) -> None:
    """Despliega confirmación previa cuando el comprobante dejará productos en quiebre."""
    filas_q = [
        ft.Text(
            f"• [{d.codigo}] {getattr(d, 'nombre_producto', '')}: Stock actual {getattr(d, 'stock_anterior', getattr(d, 'stock_original', 0))} → Descuenta {d.cantidad_descontada} → Quedará en {d.stock_nuevo} un.",
            size=11,
            color=ft.Colors.RED_400,
            weight=ft.FontWeight.W_500,
        )
        for d in quiebres
    ]

    async def autorizar_y_seguir(_e):
        interfaz.page.pop_dialog()
        await interfaz.ejecutar_tarea(f"Remito #{remito} ({cli})", ejecutar_descuento_pedido)

    dlg_prev = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_400), ft.Text("Alerta Preventiva de Stock Insuficiente")]),
        content=ft.Container(
            width=480,
            content=ft.Column(
                [
                    ft.Text(
                        f"El comprobante '{remito}' contiene {len(quiebres)} artículo(s) que dejarán el inventario en quiebre o saldo negativo:",
                        size=12,
                        color=interfaz.texto,
                    ),
                    ft.Container(
                        content=ft.ListView(filas_q, height=85, spacing=3),
                        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.RED_50,
                        padding=8,
                        border_radius=6,
                    ),
                    ft.Text(
                        "¿Deseas autorizar el descuento de todos modos o apartar el comprobante para revisión?",
                        size=12,
                        color=interfaz.secundario,
                    ),
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            ft.Button("Autorizar y Descontar", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=autorizar_y_seguir),
            interfaz.boton_dialogo("Cancelar y Revisar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.reproducir_sonido("error")
    interfaz.page.show_dialog(dlg_prev)


def ejecutar_descuento_y_registro_pedido(
    *,
    interfaz: Any,
    remito: str,
    num_ped: str,
    cli: str,
    bultos_val: int,
    log: str,
    f_retiro: str,
    armador_nom: str,
    es_agregado: bool,
    tipo_archivo: str,
    archivo_path: Path,
    hash_comprobante: str,
    cache_simulacion: dict[str, Any],
) -> None:
    """Aplica descuento en StockManager SQLite-first, registra en OrderStore y notifica éxito."""
    tx_id = f"PED_{remito}_{hash_comprobante[:10] if hash_comprobante else ''}"
    if hasattr(interfaz.order_store, "registrar_transaccion_idempotente"):
        if not interfaz.order_store.registrar_transaccion_idempotente(tx_id, "CREAR_PEDIDO", remito):
            print(f"[IDEMPOTENCIA] Transacción duplicada ignorada antes de descontar stock: {tx_id}")
            return

    stock_mgr = cache_simulacion.get("stock_mgr")
    reporte = cache_simulacion.get("reporte")
    if stock_mgr is None or reporte is None:
        stock_mgr = _resolver_sm_cls()(ruta_excel_base=interfaz.menu.ruta_excel_base)
        agente = AgenteRemitosStock(stock_manager=stock_mgr)
        kw = {"rutas_pdf": [archivo_path]} if tipo_archivo == "pdf" else {"rutas_canjes": [archivo_path]}
        reporte = agente.ejecutar(**kw, carpeta_descuentos=interfaz.menu.carpeta_descuentos, simulacion=False, guardar_archivo=False)

    nombre_inf = Path(reporte.reporte_stock.archivo_guardado).name if reporte.reporte_stock.archivo_guardado else f"Pedido_{remito}"
    stock_mgr.actualizar_stock_base(
        descuentos=reporte.reporte_stock.descuentos_aplicados,
        sincronizar_excel=False,
        nombre_archivo=nombre_inf,
        usuario=armador_nom,
    )
    if hasattr(stock_mgr, "programar_sincronizacion_excel"):
        stock_mgr.programar_sincronizacion_excel()

    pdf_nom = Path(reporte.reporte_stock.archivo_pdf).name if reporte.reporte_stock.archivo_pdf else ""
    total_descontado = sum(d.cantidad_descontada for d in reporte.reporte_stock.descuentos_aplicados)
    resumen_items = f"{len(reporte.reporte_stock.descuentos_aplicados)} productos ({total_descontado} un.)"
    items_descontados = [(d.codigo, d.nombre_producto, d.cantidad_descontada) for d in reporte.reporte_stock.descuentos_aplicados]
    sin_coincidencia_doc = []
    if reporte and reporte.documentos_verificados:
        for doc in reporte.documentos_verificados:
            sin_coincidencia_doc.extend(doc.descripciones_sin_coincidencia)

    interfaz.order_store.registrar_pedido(
        nota_pedido=remito,
        numero_pedido=num_ped,
        cliente=cli,
        bultos=bultos_val,
        logistica=log,
        armador=armador_nom,
        tipo_archivo=tipo_archivo,
        nombre_archivo=archivo_path.name,
        agregado=es_agregado,
        articulos_descontados=total_descontado,
        resumen_items=resumen_items,
        fecha_retiro=f_retiro,
        archivo_descuento=pdf_nom,
        items=items_descontados,
        archivo_hash=hash_comprobante,
        items_sin_coincidencia=sin_coincidencia_doc,
    )
    interfaz.actualizar_listas()
    interfaz.sincronizar_sesiones(aviso_colaborativo=f"📦 {armador_nom} preparó el Pedido #{remito} ({cli})")
    interfaz.reproducir_sonido("exito")
    print(f"[PEDIDO REGISTRADO] Remito/Factura: {remito} | Pedido: {num_ped} | Cliente: {cli} | Descontados: {resumen_items} | Retiro: {f_retiro}")
    _mostrar_dialogo_exito_pedido(interfaz, remito, cli, bultos_val, log, resumen_items, reporte)
