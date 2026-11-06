"""Presentador y despachador del estado y datos del Dashboard principal."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import flet as ft

from .theme import ROJO
from ..user_store import USER_ROLES
from ..stock_manager import StockManager


def renderizar_auditoria_master(interfaz: Any, eventos_auditoria: list[Any]) -> None:
    """Genera las tarjetas de eventos de auditoría para la consola del rol Master."""
    interfaz.lista_informes.controls.clear()
    if not eventos_auditoria:
        interfaz.lista_informes.controls.append(
            ft.Text("Todavía no hay eventos de auditoría registrados.", size=12, color=interfaz.secundario)
        )
        return

    for ev in eventos_auditoria[:15]:
        accion_ev = getattr(ev, "accion", "")
        usuario_ev = getattr(ev, "usuario", "")
        fecha_ev = getattr(ev, "fecha", "")
        detalle_ev = getattr(ev, "detalle", "")

        if "LOGIN" in accion_ev or "AUTH" in accion_ev:
            icono_ev = ft.Icons.LOGIN
            color_ev = ft.Colors.GREEN_400
        elif "LOCK" in accion_ev or "BLOQUEO" in accion_ev or "ANULAR" in accion_ev:
            icono_ev = ft.Icons.LOCK
            color_ev = ft.Colors.RED_400
        elif "RESET" in accion_ev or "USER" in accion_ev:
            icono_ev = ft.Icons.MANAGE_ACCOUNTS
            color_ev = ft.Colors.BLUE_400
        elif "BACKUP" in accion_ev:
            icono_ev = ft.Icons.BACKUP
            color_ev = ft.Colors.PURPLE_400
        elif "INGRESO_RAPIDO" in accion_ev:
            icono_ev = ft.Icons.ADD_CIRCLE_OUTLINE
            color_ev = ft.Colors.GREEN_400
        elif "SALIDA_RAPIDA" in accion_ev:
            icono_ev = ft.Icons.REMOVE_CIRCLE_OUTLINE
            color_ev = ft.Colors.AMBER_400
        else:
            icono_ev = ft.Icons.SECURITY
            color_ev = ROJO

        interfaz.lista_informes.controls.append(
            ft.ListTile(
                leading=ft.Icon(icono_ev, color=color_ev, size=19),
                title=ft.Text(f"[{accion_ev}] @{usuario_ev}", size=12, color=interfaz.texto, weight=ft.FontWeight.W_500),
                subtitle=ft.Text(f"{detalle_ev} · {fecha_ev}", size=10, color=interfaz.secundario),
            )
        )


def renderizar_pedidos_preparados_turno(interfaz: Any, pedidos_pendientes_turno: list[Any]) -> None:
    """Renderiza la lista descendente de pedidos preparados en el turno activo."""
    total_bultos_turno = sum(p.bultos for p in pedidos_pendientes_turno)
    fecha_hoy_str = datetime.now().strftime("%A %d/%m/%Y").capitalize()

    interfaz.header_pedidos_fecha.value = fecha_hoy_str
    interfaz.header_pedidos_subtitulo.value = (
        f"{len(pedidos_pendientes_turno)} pedido(s) preparados en el turno actual"
        if pedidos_pendientes_turno
        else "Turno activo · Sin pedidos pendientes"
    )
    interfaz.header_pedidos_bultos.value = f"📦 {total_bultos_turno} bultos preparados"

    interfaz.lista_pedidos_preparados.controls.clear()
    if not pedidos_pendientes_turno:
        interfaz.lista_pedidos_preparados.controls.append(
            ft.Container(
                padding=20,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=32, color=ft.Colors.GREEN_400),
                        ft.Text("No hay pedidos pendientes de cierre.", size=12, color=interfaz.secundario),
                        ft.Text("Los pedidos que cargues aparecerán aquí en tiempo real.", size=11, color=interfaz.secundario),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
            )
        )
        return

    for ped in pedidos_pendientes_turno:
        hora_c = ped.created_at[11:16] if ped.created_at and len(ped.created_at) >= 16 else ""
        num_p = f"Pedido #{ped.numero_pedido} · " if getattr(ped, "numero_pedido", "") else ""
        titulo_card = f"{num_p}Remito: {ped.nota_pedido}"

        def abrir_modificar_o_ver(p_obj=ped):
            if interfaz.usuario_actual and interfaz.usuario_actual.role == "operador":
                interfaz.mostrar_dialogo_editar_pedido(p_obj, al_final=interfaz.actualizar_listas)
            elif interfaz.usuario_actual and interfaz.usuario_actual.role == "administrador":
                interfaz.mostrar_detalle_pedido_modal(p_obj)

        card_pedido = ft.Container(
            bgcolor=interfaz.superficie,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            ink=True,
            tooltip="Clic para abrir y modificar este pedido" if (interfaz.usuario_actual and interfaz.usuario_actual.role == "operador") else "Clic para ver detalle del pedido",
            on_click=lambda _e, p_obj=ped: abrir_modificar_o_ver(p_obj),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(ft.Icons.INVENTORY_2, size=18, color=ROJO),
                                bgcolor=ft.Colors.RED_50,
                                padding=6,
                                border_radius=6,
                            ),
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(titulo_card, weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                            ft.Container(
                                                content=ft.Text(f"{ped.bultos} bulto(s)", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                                bgcolor=ft.Colors.BLUE_GREY_700,
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                border_radius=10,
                                            ),
                                        ],
                                        spacing=6,
                                    ),
                                    ft.Text(f"Cliente: {ped.cliente} · {ped.logistica}", size=11, color=interfaz.secundario),
                                    ft.Text(f"Artículos: {ped.resumen_items or f'{ped.articulos_descontados} un.'}", size=10, color=ft.Colors.GREEN_400),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                        expand=True,
                    ),
                    ft.Column(
                        [
                            ft.Text(hora_c, size=10, color=interfaz.secundario, weight=ft.FontWeight.W_500),
                            *(
                                [
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_OUTLINED,
                                        icon_size=16,
                                        tooltip="Modificar pedido",
                                        icon_color=ft.Colors.BLUE_400,
                                        on_click=lambda _e, p_obj=ped: interfaz.mostrar_dialogo_editar_pedido(p_obj, al_final=interfaz.actualizar_listas),
                                    )
                                ]
                                if (interfaz.usuario_actual and interfaz.usuario_actual.role == "operador")
                                else []
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                        spacing=2,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        interfaz.lista_pedidos_preparados.controls.append(card_pedido)


def renderizar_informes_generados(interfaz: Any, informes: list[Path], mtimes_informes: dict[Path, float]) -> None:
    """Renderiza el listado de comprobantes, hojas de ruta y balances emitidos."""
    interfaz.lista_informes.controls.clear()
    if not informes:
        interfaz.lista_informes.controls.append(
            ft.Text("Todavía no hay informes.", size=12, color=interfaz.secundario)
        )
        return

    for ruta in informes[:30]:
        es_fabrica = ruta.name.startswith("Pedido_Fabrica")
        es_comparativa = ruta.name.startswith("Comparativa_Stock_Fisico")
        if es_comparativa:
            icono = ft.Icons.COMPARE_ARROWS
            color_icono = ft.Colors.BLUE_400
            tipo_txt = "Comparativa stock físico"
        elif es_fabrica:
            icono = ft.Icons.INVENTORY_2
            color_icono = ft.Colors.AMBER_400
            tipo_txt = "Pedido a fábrica"
        else:
            icono = ft.Icons.DESCRIPTION
            color_icono = ROJO
            tipo_txt = "Informe de descuentos"
        try:
            ts = mtimes_informes.get(ruta)
            if ts is None:
                ts = ruta.stat().st_mtime
            mtime = datetime.fromtimestamp(ts)
            fecha_fmt = mtime.strftime("%d/%m/%Y %H:%M")
        except Exception:
            fecha_fmt = ""

        subtitulo_txt = f"{tipo_txt} · {fecha_fmt}" if fecha_fmt else tipo_txt

        subtitulo = ft.Text(
            subtitulo_txt,
            size=10,
            color=ft.Colors.BLUE_300
            if (es_comparativa and interfaz.modo_oscuro)
            else (
                ft.Colors.BLUE_700
                if es_comparativa
                else (
                    ft.Colors.AMBER_300
                    if (es_fabrica and interfaz.modo_oscuro)
                    else (ft.Colors.AMBER_700 if es_fabrica else interfaz.secundario)
                )
            ),
        )
        interfaz.lista_informes.controls.append(
            ft.ListTile(
                leading=ft.Icon(icono, color=color_icono, size=19),
                title=ft.Text(ruta.name, size=12, color=interfaz.texto, weight=ft.FontWeight.W_500),
                subtitle=subtitulo,
                on_click=lambda _e, archivo=ruta: interfaz.seleccionar_informe(archivo),
                trailing=ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.VISIBILITY_OUTLINED,
                            tooltip="Ver informe",
                            icon_color=ft.Colors.BLUE_400,
                            icon_size=18,
                            on_click=lambda _e, r=ruta: interfaz.abrir_informe(ruta_especifica=r),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.FOLDER_OPEN,
                            tooltip="Abrir carpeta contenedora",
                            icon_color=interfaz.secundario,
                            icon_size=18,
                            on_click=lambda _e, r=ruta: interfaz.abrir_carpeta_informe(ruta_especifica=r),
                        ),
                    ],
                    spacing=2,
                    alignment=ft.MainAxisAlignment.END,
                ),
            )
        )


def actualizar_estado_dashboard(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Actualiza y sincroniza en tiempo real todos los indicadores y listas del Dashboard."""
    if not interfaz.exigir_roles(*USER_ROLES):
        return

    mayoristas, canjes, mercado_libre = interfaz.menu._obtener_pendientes()
    archivados = interfaz.menu._obtener_archivados()
    mtimes_informes: dict[Path, float] = {}

    def _clave_informe(ruta: Path) -> tuple[int, str]:
        try:
            st = ruta.stat()
            mtimes_informes[ruta] = st.st_mtime
            return (st.st_mtime_ns, ruta.name.casefold())
        except OSError:
            return (0, ruta.name.casefold())

    informes = sorted(
        interfaz.menu._obtener_generados(),
        key=_clave_informe,
        reverse=True,
    )
    interfaz.informes = informes

    conteo_jornada = {"pdf": 0, "excel": 0, "docx": 0, "total": 0}
    if hasattr(interfaz, "order_store") and interfaz.order_store:
        try:
            conteo_jornada = interfaz.order_store.contar_pedidos_pendientes_cierre_por_tipo()
        except Exception:
            pass

    if "pdf" in interfaz.contadores:
        interfaz.contadores["pdf"].value = str(conteo_jornada.get("pdf", 0))
    if "canjes" in interfaz.contadores:
        interfaz.contadores["canjes"].value = str(conteo_jornada.get("excel", 0))
    if "ml" in interfaz.contadores:
        interfaz.contadores["ml"].value = str(conteo_jornada.get("docx", 0))
    if "total" in interfaz.contadores:
        interfaz.contadores["total"].value = str(conteo_jornada.get("total", 0))
    if "informes" in interfaz.contadores:
        interfaz.contadores["informes"].value = str(len(informes))

    interfaz._actualizar_estado_boton_cierre(int(conteo_jornada.get("total", 0)))

    rol = interfaz.usuario_actual.role if interfaz.usuario_actual else "consulta"

    if rol == "administrador":
        try:
            sm = StockManager(interfaz.menu.ruta_excel_base)
            criticos = sm.obtener_analisis_reposicion(solo_criticos=True)
        except Exception:
            criticos = []
        if "quiebres" in interfaz.contadores:
            interfaz.contadores["quiebres"].value = str(len(criticos))
            interfaz.contadores["quiebres"].color = (
                ft.Colors.RED_400 if len(criticos) > 0 else interfaz.texto
            )
        interfaz.actualizar_alerta_quiebre(criticos)
        interfaz._actualizar_icono_notificaciones()
    else:
        interfaz.banner_alerta_quiebre.visible = False

    if rol == "master":
        try:
            todos_usr = interfaz.user_store.list_users()
            activos_usr = sum(1 for u in todos_usr if u.active)
        except Exception:
            todos_usr = []
            activos_usr = 0

        if "usuarios_total" in interfaz.contadores:
            interfaz.contadores["usuarios_total"].value = str(len(todos_usr))
        if "usuarios_activos" in interfaz.contadores:
            interfaz.contadores["usuarios_activos"].value = str(activos_usr)

        eventos_auditoria = []
        if hasattr(interfaz, "order_store") and interfaz.order_store:
            try:
                eventos_auditoria = interfaz.order_store.listar_auditoria(limit=100)
            except Exception:
                pass
        if "auditoria_eventos" in interfaz.contadores:
            interfaz.contadores["auditoria_eventos"].value = str(len(eventos_auditoria))

        try:
            from ..backup_manager import listar_backups
            bks = listar_backups()
        except Exception:
            bks = []
        if "backups_total" in interfaz.contadores:
            interfaz.contadores["backups_total"].value = str(len(bks))
        if "servidor_seguro" in interfaz.contadores:
            interfaz.contadores["servidor_seguro"].value = "HTTPS" if getattr(interfaz, "https", True) else "HTTP"

        try:
            from ..system_telemetry import obtener_telemetria_sistema
            telem = obtener_telemetria_sistema()
        except Exception:
            telem = None

        if telem:
            if "telemetria_disco" in interfaz.contadores:
                interfaz.contadores["telemetria_disco"].value = f"{telem.disco_libre_gb} GB"
                interfaz.contadores["telemetria_disco"].color = (
                    ft.Colors.RED_400 if telem.disco_alerta else interfaz.texto
                )
            if "telemetria_salud" in interfaz.contadores:
                interfaz.contadores["telemetria_salud"].value = telem.estado_salud
                if telem.estado_salud == "Óptimo":
                    interfaz.contadores["telemetria_salud"].color = ft.Colors.GREEN_400
                elif telem.estado_salud == "Atención":
                    interfaz.contadores["telemetria_salud"].color = ft.Colors.AMBER_400
                else:
                    interfaz.contadores["telemetria_salud"].color = ft.Colors.RED_400

        interfaz.banner_alerta_quiebre.visible = False
        interfaz.pendientes_texto.value = (
            f"Consola de Auditoría y Control de Accesos · Usuarios: {len(todos_usr)} · Cuentas activas: {activos_usr} · Backups: {len(bks)}"
        )
        renderizar_auditoria_master(interfaz, eventos_auditoria)
    else:
        total_descontados = conteo_jornada.get("total", 0)
        total_archivados = sum(map(len, archivados))
        interfaz.pendientes_texto.value = (
            f"Jornada en curso: {total_descontados} pedido(s) descontado(s) · Archivados: {total_archivados} · Informes: {len(informes)}"
        )

        pedidos_pendientes_turno = interfaz.order_store.listar_pedidos_pendientes_cierre()
        pedidos_pendientes_turno.sort(key=lambda p: p.id, reverse=True)
        renderizar_pedidos_preparados_turno(interfaz, pedidos_pendientes_turno)
        renderizar_informes_generados(interfaz, informes, mtimes_informes)

    if hasattr(interfaz, "actualizar_badge_chat"):
        try:
            interfaz.actualizar_badge_chat()
        except Exception:
            pass

    if interfaz.page and getattr(interfaz.page, "controls", None):
        try:
            interfaz.page.update()
        except Exception:
            pass
