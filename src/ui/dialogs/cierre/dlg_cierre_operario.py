"""Diálogo para el Cierre de Jornada de pedidos por parte del operario."""

from __future__ import annotations

import sys
from typing import Any

import flet as ft

from ....backup_manager import crear_backup_sistema
from ....parsers.canjes_parser import parsear_canje_excel
from ....parsers.mercado_libre_parser import parsear_pedido_mercado_libre
from ....parsers.remito_parser import parsear_remito
from ....paths import application_root
from ....stock.manifest_pdf import generar_hoja_ruta_pdf
from ...theme import ROJO
from .cierre_operario_exec import (
    ejecutar_tarea_cierre_operario,
    poblar_historial_cierres,
    poblar_items_pendientes,
)
from .hoja_ruta import (
    _get_stock_manager_cls,
    gestionar_hoja_ruta_cierre,
    resolver_archivos_cierre,
)


def mostrar_dialogo_cierre_jornada(interfaz: Any) -> None:
    """Abre el panel para cerrar la jornada operativa, descontar stock en bloque y generar la Hoja de Ruta."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "operador":
        interfaz.notificar("El cierre de jornada es una función exclusiva del rol operador.")
        return

    mod_gui = sys.modules.get("src.flet_gui")
    obtener_correo_fn = getattr(mod_gui, "obtener_correo_cierre_guardado", lambda: "")
    guardar_correo_fn = getattr(mod_gui, "guardar_correo_cierre", lambda _c: None)

    pedidos_pendientes = interfaz.order_store.listar_pedidos_pendientes_cierre()
    cierres_anteriores = interfaz.order_store.listar_cierres(limit=25)
    total_articulos_pendientes = sum(p.articulos_descontados for p in pedidos_pendientes)

    items_pendientes = ft.ListView(expand=True, spacing=6)
    poblar_items_pendientes(interfaz, items_pendientes, pedidos_pendientes)

    lista_cierres = ft.ListView(expand=True, spacing=6)
    poblar_historial_cierres(interfaz, lista_cierres, cierres_anteriores)

    correo_cierre_input = ft.TextField(
        label="Enviar copia de cierre por correo a (opcional)",
        value=obtener_correo_fn(),
        hint_text="ej: gerencia@empresa.com, administracion@empresa.com",
        prefix_icon=ft.Icons.EMAIL,
        dense=True,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
    )

    async def ejecutar_cierre(_e: ft.Event) -> None:
        if getattr(ejecutar_cierre, "_en_curso", False):
            return
        if not pedidos_pendientes:
            interfaz.notificar("No hay pedidos pendientes para cerrar.")
            return
        ejecutar_cierre._en_curso = True

        correo_destino = (correo_cierre_input.value or "").strip()
        if correo_destino:
            guardar_correo_fn(correo_destino)

        interfaz.page.pop_dialog()
        resultado_cierre: dict[str, Any] = {}

        def tarea_cierre() -> None:
            resultado_cierre.update(ejecutar_tarea_cierre_operario(interfaz, pedidos_pendientes))

        try:
            exito = await interfaz.ejecutar_tarea("Cierre de Jornada", tarea_cierre)
        finally:
            ejecutar_cierre._en_curso = False
        if not exito:
            return

        interfaz.actualizar_listas()

        pdf_path = resultado_cierre.get("pdf_path")
        hoja_ruta_pdf = resultado_cierre.get("hoja_ruta_pdf")
        cierre_id = resultado_cierre.get("cierre_id", 0)
        resumen_p = resultado_cierre.get("resumen_p", "")
        alerta_resumen_notif = resultado_cierre.get("alerta_resumen_notif", "")
        alerta_texto_correo = resultado_cierre.get("alerta_texto_correo", "")

        if pdf_path and pdf_path.exists():
            interfaz.abrir_informe(ruta_especifica=pdf_path)
        if hoja_ruta_pdf and hoja_ruta_pdf.exists():
            interfaz.abrir_informe(ruta_especifica=hoja_ruta_pdf)

        if correo_destino:
            interfaz.enviar_correo_cierre(
                destinatarios=correo_destino,
                cierre_id=cierre_id,
                archivo_pdf=pdf_path,
                archivo_excel=resultado_cierre.get("xls_path"),
                resumen_pedidos=resumen_p,
                usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Operario",
                archivo_hoja_ruta=hoja_ruta_pdf,
                alerta_stock=alerta_texto_correo,
            )

        mensaje_exito = (
            f"Cierre de jornada #{cierre_id} realizado con éxito ({resumen_p}). "
            "Se generó el informe, la Hoja de Ruta y el Respaldo de seguridad."
        )
        if alerta_resumen_notif:
            mensaje_exito += f"\n⚠️ {alerta_resumen_notif}"
        usr_nom = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operario"
        interfaz.reproducir_sonido("cierre")
        interfaz.sincronizar_sesiones(aviso_colaborativo=f"✅ {usr_nom} realizó el Cierre de Jornada #{cierre_id} ({resumen_p})")
        interfaz.notificar(mensaje_exito)

    vista_pendientes = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    bgcolor=ROJO if pedidos_pendientes else (ft.Colors.BLUE_GREY_900 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100),
                    border_radius=8,
                    padding=10,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(
                                        f"{len(pedidos_pendientes)} Pedidos Acumulados" if pedidos_pendientes else "Sin pedidos acumulados",
                                        weight=ft.FontWeight.BOLD,
                                        size=13,
                                        color=ft.Colors.WHITE,
                                    ),
                                    ft.Text(
                                        f"Total de {total_articulos_pendientes} unidades descontadas listas para cerrar jornada."
                                        if pedidos_pendientes
                                        else "Todos los pedidos anteriores están cerrados.",
                                        size=11,
                                        color=ft.Colors.WHITE_70,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Button(
                                "Cerrar Jornada e Imprimir",
                                icon=ft.Icons.LOCK,
                                bgcolor=ft.Colors.WHITE,
                                color=ROJO,
                                disabled=not bool(pedidos_pendientes),
                                on_click=ejecutar_cierre,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                correo_cierre_input,
                ft.Text("Pedidos incluidos en este cierre:", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ft.Container(content=items_pendientes, expand=True),
            ],
            spacing=10,
            expand=True,
        ),
        expand=True,
        visible=True,
    )

    vista_historial = ft.Container(
        content=ft.Column(
            [
                ft.Text("Cierres de jornada anteriores (puedes reimprimir cualquier cierre):", size=12, color=interfaz.secundario),
                ft.Container(content=lista_cierres, expand=True),
            ],
            spacing=8,
            expand=True,
        ),
        expand=True,
        visible=False,
    )

    boton_tab_pendientes = ft.Button(f"Pendientes ({len(pedidos_pendientes)})", icon=ft.Icons.PENDING_ACTIONS, bgcolor=ROJO, color=ft.Colors.WHITE)
    boton_tab_historial = ft.Button(
        f"Historial de Cierres ({len(cierres_anteriores)})",
        icon=ft.Icons.HISTORY,
        bgcolor=ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100,
        color=interfaz.texto,
    )

    def switch_tab(tab_idx: int) -> None:
        es_pend = tab_idx == 0
        vista_pendientes.visible = es_pend
        vista_historial.visible = not es_pend
        bg_inact = ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100
        boton_tab_pendientes.bgcolor = ROJO if es_pend else bg_inact
        boton_tab_pendientes.color = ft.Colors.WHITE if es_pend else interfaz.texto
        boton_tab_historial.bgcolor = bg_inact if es_pend else ROJO
        boton_tab_historial.color = interfaz.texto if es_pend else ft.Colors.WHITE
        interfaz.page.update()

    boton_tab_pendientes.on_click = lambda _e: switch_tab(0)
    boton_tab_historial.on_click = lambda _e: switch_tab(1)

    cuerpo_cierre = ft.Column([ft.Row([boton_tab_pendientes, boton_tab_historial], spacing=10), vista_pendientes, vista_historial], spacing=12, expand=True)
    dialogo = ft.AlertDialog(
        title=ft.Row([ft.Icon(ft.Icons.TASK_ALT, color=ROJO), ft.Text("Cierre de Jornada de Pedidos", weight=ft.FontWeight.BOLD)], spacing=8),
        content=ft.Container(width=720, height=520, content=cuerpo_cierre),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)


__all__ = [
    "_get_stock_manager_cls",
    "application_root",
    "crear_backup_sistema",
    "generar_hoja_ruta_pdf",
    "gestionar_hoja_ruta_cierre",
    "mostrar_dialogo_cierre_jornada",
    "parsear_canje_excel",
    "parsear_pedido_mercado_libre",
    "parsear_remito",
    "resolver_archivos_cierre",
]
