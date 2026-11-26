"""Diálogos auxiliares y helpers de parseo/confirmación para la creación de pedidos."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import flet as ft

from ...agent import AgenteRemitosStock
from ..theme import ROJO
from ._shared import resolve_stock_manager


def _resolver_sm_cls(interfaz: Any = None):
    """Resuelve StockManager mediante inyección en `interfaz`."""
    return resolve_stock_manager(interfaz)


def parsear_comprobante_pedido(
    arch_candidato: Path,
    ruta_excel_base: Path,
    interfaz: Any = None,
) -> Any | None:
    """Parsea un comprobante PDF, DOCX o Excel y retorna los datos extraídos o None."""
    ext_c = arch_candidato.suffix.lower()
    if ext_c == ".pdf":
        from ...parsers.remito_parser import parsear_remito
        return parsear_remito(arch_candidato)
    if ext_c == ".docx":
        from ...parsers.mercado_libre_parser import parsear_pedido_mercado_libre
        sm = _resolver_sm_cls(interfaz)(ruta_excel_base)
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
    *,
    solo_reserva: bool = False,
) -> None:
    """Ofrece impresión inmediata de rótulos y muestra alertas de stock crítico tras registrar un pedido."""
    try:
        pedido_reciente = interfaz.order_store.buscar_pedido_por_nota(remito)
        if not (pedido_reciente and interfaz.page):
            return
        items_alerta = []
        if not solo_reserva:
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

        titulo_exito = "Pedido Registrado con Stock Reservado" if solo_reserva else "Pedido Registrado y Descontado"
        detalle_op = (
            f"• Reserva activa: {resumen_items} (stock físico se descontará al consolidar/despachar)."
            if solo_reserva
            else f"• Descuento: {resumen_items} en tiempo real."
        )

        dialogo_exito = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400), ft.Text(titulo_exito)]),
            content=ft.Container(
                width=450,
                content=ft.Column(
                    [
                        ft.Text(f"El pedido #{remito} de '{cli}' fue procesado con éxito.", size=13, weight=ft.FontWeight.W_500),
                        ft.Text(f"• Bultos: {bultos_val} · Logística: {log}", size=12, color=interfaz.secundario),
                        ft.Text(detalle_op, size=12, color=ft.Colors.TEAL_400 if solo_reserva else ft.Colors.GREEN_400),
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


def _formatear_fila_alerta_preventiva(entry: Any) -> ft.Text:
    """Formatea líneas de alerta para quiebres físicos o conflictos contra reservas activas."""
    if isinstance(entry, dict):
        cod = entry.get("codigo", "")
        nom = entry.get("nombre_producto", "")
        stock_ant = entry.get("stock_anterior", 0)
        cant = entry.get("cantidad_descontada", 0)
        stock_nuevo = entry.get("stock_nuevo", 0)
        tipo = entry.get("tipo", "QUIEBRE_FISICO")
        if tipo == "CONFLICTO_RESERVA":
            res = entry.get("stock_reservado", 0)
            disp = entry.get("stock_disponible", 0)
            return ft.Text(
                f"• [{cod}] {nom}: Reservado por olas ({res} u.) → Disponible neto {disp} u. (Solicita {cant} u. sobre físico {stock_ant})",
                size=11,
                color=ft.Colors.AMBER_400,
                weight=ft.FontWeight.W_500,
            )
        return ft.Text(
            f"• [{cod}] {nom}: Stock actual {stock_ant} → Descuenta {cant} → Quedará en {stock_nuevo} un.",
            size=11,
            color=ft.Colors.RED_400,
            weight=ft.FontWeight.W_500,
        )
    return ft.Text(
        f"• [{entry.codigo}] {getattr(entry, 'nombre_producto', '')}: Stock actual {getattr(entry, 'stock_anterior', getattr(entry, 'stock_original', 0))} → Descuenta {entry.cantidad_descontada} → Quedará en {entry.stock_nuevo} un.",
        size=11,
        color=ft.Colors.RED_400,
        weight=ft.FontWeight.W_500,
    )


def _mostrar_alerta_preventiva_quiebre(
    interfaz: Any,
    remito: str,
    cli: str,
    quiebres: list[Any],
    ejecutar_descuento_pedido: Callable[[], None],
    *,
    solo_reservar: bool = False,
) -> None:
    """Despliega confirmación previa ante quiebres físicos o conflictos con reservas activas."""
    filas_q = [_formatear_fila_alerta_preventiva(d) for d in quiebres]
    solo_reserva_conflicto = all(
        isinstance(q, dict) and q.get("tipo") == "CONFLICTO_RESERVA" for q in quiebres
    )

    async def autorizar_y_seguir(_e):
        interfaz.page.pop_dialog()
        await interfaz.ejecutar_tarea(f"Remito #{remito} ({cli})", ejecutar_descuento_pedido)

    titulo_alerta = (
        "Alerta Preventiva: Stock Comprometido en Reservas"
        if solo_reserva_conflicto
        else "Alerta Preventiva de Stock Insuficiente"
    )
    subtitulo_alerta = (
        f"El comprobante '{remito}' afecta {len(quiebres)} artículo(s) comprometidos en reservas activas de depósito:"
        if solo_reserva_conflicto
        else f"El comprobante '{remito}' contiene {len(quiebres)} artículo(s) que exceden el stock disponible neto o dejan quiebre:"
    )

    acciones = [interfaz.boton_dialogo("Cancelar y Revisar", lambda _e: interfaz.page.pop_dialog())]
    if not solo_reservar:
        acciones.insert(
            0,
            ft.Button("Autorizar y Descontar", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=autorizar_y_seguir),
        )

    dlg_prev = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_400), ft.Text(titulo_alerta)]),
        content=ft.Container(
            width=500,
            content=ft.Column(
                [
                    ft.Text(subtitulo_alerta, size=12, color=interfaz.texto),
                    ft.Container(
                        content=ft.ListView(filas_q, height=95, spacing=3),
                        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.RED_50,
                        padding=8,
                        border_radius=6,
                    ),
                    ft.Text(
                        "En modo 'Solo Reservar' no se permite sobre-asignar stock comprometido."
                        if solo_reservar
                        else "¿Deseas autorizar el descuento de todos modos o apartar el comprobante para revisión?",
                        size=12,
                        color=interfaz.secundario,
                    ),
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=acciones,
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
    from ...core.stock_order_tx import ejecutar_descuento_y_registro_atomico

    tx_id = f"PED_{remito}_{hash_comprobante[:10] if hash_comprobante else ''}"

    def _resolver_sm_y_reporte():
        sm_cached = cache_simulacion.get("stock_mgr")
        rep_cached = cache_simulacion.get("reporte")
        if sm_cached is not None and rep_cached is not None:
            return sm_cached, rep_cached
        sm_local = _resolver_sm_cls(interfaz)(ruta_excel_base=interfaz.menu.ruta_excel_base)
        agente = AgenteRemitosStock(stock_manager=sm_local)
        kw = {"rutas_pdf": [archivo_path]} if tipo_archivo == "pdf" else {"rutas_canjes": [archivo_path]}
        rep_local = agente.ejecutar(
            **kw,
            carpeta_descuentos=interfaz.menu.carpeta_descuentos,
            simulacion=False,
            guardar_archivo=False,
        )
        return sm_local, rep_local

    pdf_nom = ""
    if cache_simulacion.get("reporte") and getattr(cache_simulacion["reporte"].reporte_stock, "archivo_pdf", None):
        pdf_nom = Path(cache_simulacion["reporte"].reporte_stock.archivo_pdf).name

    resultado = ejecutar_descuento_y_registro_atomico(
        order_store=interfaz.order_store,
        stock_mgr_factory=_resolver_sm_y_reporte,
        tx_id=tx_id,
        remito=remito,
        num_ped=num_ped,
        cli=cli,
        bultos_val=bultos_val,
        log=log,
        f_retiro=f_retiro,
        armador_nom=armador_nom,
        es_agregado=es_agregado,
        tipo_archivo=tipo_archivo,
        nombre_archivo=archivo_path.name,
        archivo_descuento=pdf_nom,
        hash_comprobante=hash_comprobante,
    )
    if resultado is None:
        print(f"[IDEMPOTENCIA] Transacción duplicada ignorada antes de descontar stock: {tx_id}")
        return

    _, _, reporte, _ = resultado
    total_descontado = sum(d.cantidad_descontada for d in reporte.reporte_stock.descuentos_aplicados)
    resumen_items = f"{len(reporte.reporte_stock.descuentos_aplicados)} productos ({total_descontado} un.)"
    interfaz.actualizar_listas()
    interfaz.sincronizar_sesiones(aviso_colaborativo=f"📦 {armador_nom} preparó el Pedido #{remito} ({cli})")
    interfaz.reproducir_sonido("exito")
    print(f"[PEDIDO REGISTRADO] Remito/Factura: {remito} | Pedido: {num_ped} | Cliente: {cli} | Descontados: {resumen_items} | Retiro: {f_retiro}")
    _mostrar_dialogo_exito_pedido(interfaz, remito, cli, bultos_val, log, resumen_items, reporte)


def ejecutar_reserva_y_registro_pedido(
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
    """Registra el pedido en preparación reservando stock disponible sin descontar físico todavía."""
    from ...core.stock_order_tx import ejecutar_reserva_y_registro_atomico

    tx_id = f"PEDRES_{remito}_{hash_comprobante[:10] if hash_comprobante else ''}"

    def _resolver_sm_y_simulacion():
        sm_cached = cache_simulacion.get("stock_mgr")
        rep_cached = cache_simulacion.get("reporte")
        if sm_cached is not None and rep_cached is not None:
            return sm_cached, rep_cached
        sm_local = _resolver_sm_cls(interfaz)(ruta_excel_base=interfaz.menu.ruta_excel_base)
        agente = AgenteRemitosStock(stock_manager=sm_local)
        kw = {"rutas_pdf": [archivo_path]} if tipo_archivo == "pdf" else {"rutas_canjes": [archivo_path]}
        rep_local = agente.ejecutar(
            **kw,
            carpeta_descuentos=interfaz.menu.carpeta_descuentos,
            simulacion=True,
            guardar_archivo=False,
        )
        return sm_local, rep_local

    resultado = ejecutar_reserva_y_registro_atomico(
        order_store=interfaz.order_store,
        stock_mgr_factory=_resolver_sm_y_simulacion,
        tx_id=tx_id,
        remito=remito,
        num_ped=num_ped,
        cli=cli,
        bultos_val=bultos_val,
        log=log,
        f_retiro=f_retiro,
        armador_nom=armador_nom,
        es_agregado=es_agregado,
        tipo_archivo=tipo_archivo,
        nombre_archivo=archivo_path.name,
        hash_comprobante=hash_comprobante,
    )
    if resultado is None:
        return

    _, _, reporte, _, res_reserva = resultado
    total_res = int(res_reserva.get("total_unidades_reservadas", 0))
    cant_skus = len(res_reserva.get("reservas", []))
    resumen_items = f"{cant_skus} productos ({total_res} un.)"
    interfaz.actualizar_listas()
    interfaz.sincronizar_sesiones(
        aviso_colaborativo=f"🔖 {armador_nom} reservó stock para el Pedido #{remito} ({cli})"
    )
    interfaz.reproducir_sonido("exito")
    _mostrar_dialogo_exito_pedido(
        interfaz,
        remito,
        cli,
        bultos_val,
        log,
        resumen_items,
        reporte,
        solo_reserva=True,
    )
