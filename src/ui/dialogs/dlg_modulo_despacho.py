"""Módulo exclusivo Despacho: control operativo QR/manual (despachador) y consulta solo lectura (administrador)."""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ...orders import Pedido
from ..theme import ROJO
from .despacho_componentes import (
    abrir_modal_confirmar_despacho_manual,
    construir_kpi_despacho,
    construir_tarjeta_pedido_despachado,
    construir_tarjeta_pedido_pendiente,
    es_fecha_hoy,
)


def construir_vista_modulo_despacho(
    interfaz: Any,
    *,
    modo_dialogo: bool = False,
) -> tuple[ft.Control, Callable[[], None]]:
    """Construye la vista del módulo Despacho según el rol activo (`despachador` o `administrador`).

    - `despachador`: modo operativo completo (pistola lectora QR con control bulto por bulto + despacho manual).
    - `administrador`: modo estrictamente de solo lectura que muestra únicamente pedidos ya despachados.
    """
    rol = str(getattr(getattr(interfaz, "usuario_actual", None), "role", "")).strip().lower()
    solo_lectura = rol == "administrador"
    puede_despachar = rol == "despachador"

    estado_ui: dict[str, Any] = {
        "vista": "despachados" if solo_lectura else "pendientes",
        "solo_hoy": False,
        "pedido_destacado_id": None,
        "pedido_requiere_manual": None,
    }

    # KPIs en vivo
    kpi_val_1 = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=interfaz.texto)
    kpi_val_2 = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=interfaz.texto)
    kpi_val_3 = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=interfaz.texto)
    kpi_val_4 = ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=interfaz.texto)

    if solo_lectura:
        fila_kpis = ft.Row(
            [
                construir_kpi_despacho(interfaz, "Despachados hoy", kpi_val_1, ft.Icons.TODAY, ft.Colors.GREEN_500),
                construir_kpi_despacho(interfaz, "Bultos hoy", kpi_val_2, ft.Icons.INVENTORY_2, ft.Colors.BLUE_500),
                construir_kpi_despacho(interfaz, "Total despachados", kpi_val_3, ft.Icons.LOCAL_SHIPPING, ROJO),
                construir_kpi_despacho(interfaz, "Bultos totales", kpi_val_4, ft.Icons.ALL_INBOX, ft.Colors.TEAL_500),
            ],
            spacing=10,
        )
    else:
        fila_kpis = ft.Row(
            [
                construir_kpi_despacho(interfaz, "Pendientes (Armados)", kpi_val_1, ft.Icons.PENDING_ACTIONS, ft.Colors.BLUE_500),
                construir_kpi_despacho(interfaz, "En control parcial", kpi_val_2, ft.Icons.QR_CODE_SCANNER, ft.Colors.AMBER_500),
                construir_kpi_despacho(interfaz, "Despachados hoy", kpi_val_3, ft.Icons.CHECK_CIRCLE, ft.Colors.GREEN_500),
                construir_kpi_despacho(interfaz, "Bultos despachados hoy", kpi_val_4, ft.Icons.LOCAL_SHIPPING, ROJO),
            ],
            spacing=10,
        )

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    lista_pedidos = ft.ListView(
        expand=not (es_movil and not modo_dialogo),
        height=340 if (modo_dialogo or es_movil) else None,
        spacing=8,
    )

    campo_filtro = ft.TextField(
        label="Buscar por N° de remito, cliente, transporte o despachador",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
    )

    chk_solo_hoy = ft.Checkbox(
        label="Solo despachados hoy",
        value=False,
        visible=solo_lectura,
    )

    # Controles exclusivos del modo operativo (despachador)
    campo_qr = ft.TextField(
        label="Pistola lectora QR / Código de remito",
        hint_text="Escanee el rótulo QR de cada bulto (ej: REMITO:0001-00012345|...|BULTO:1/3) y presione Enter",
        prefix_icon=ft.Icons.QR_CODE_SCANNER,
        autofocus=puede_despachar,
        expand=True,
    )
    txt_feedback = ft.Text(
        "Listo para escanear. Apunte la pistola lectora al código QR de cada bulto para verificar y pasar a DESPACHADO.",
        size=12,
        color=interfaz.secundario,
    )
    icono_feedback = ft.Icon(ft.Icons.QR_CODE_SCANNER, size=18, color=ROJO)
    btn_manual_desde_scan = ft.Button(
        content="Confirmar bultos manual",
        icon=ft.Icons.EDIT_NOTE,
        bgcolor=ft.Colors.AMBER_700,
        color=ft.Colors.WHITE,
        visible=False,
    )
    banner_feedback = ft.Container(
        bgcolor=ft.Colors.with_opacity(0.06, interfaz.texto),
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        content=ft.Row(
            [
                icono_feedback,
                ft.Container(content=txt_feedback, expand=True),
                btn_manual_desde_scan,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        visible=puede_despachar,
    )

    btn_tab_pendientes = ft.Button(
        content="Pendientes de Despacho",
        icon=ft.Icons.PENDING_ACTIONS,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
    )
    btn_tab_despachados = ft.Button(
        content="Despachados",
        icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
        bgcolor=ft.Colors.TRANSPARENT,
        color=interfaz.texto,
    )

    def _fijar_feedback(texto: str, tipo: str = "info", pedido_manual: Pedido | None = None) -> None:
        colores = {
            "ok": (ft.Colors.GREEN_500, ft.Icons.CHECK_CIRCLE),
            "parcial": (ft.Colors.AMBER_500, ft.Icons.QR_CODE_SCANNER),
            "alerta": (ft.Colors.ORANGE_500, ft.Icons.WARNING_AMBER_ROUNDED),
            "error": (ft.Colors.RED_400, ft.Icons.ERROR_OUTLINE),
            "info": (ROJO, ft.Icons.INFO_OUTLINE),
        }
        col, ico = colores.get(tipo, colores["info"])
        txt_feedback.value = texto
        txt_feedback.color = col if tipo != "info" else interfaz.secundario
        icono_feedback.icon = ico
        icono_feedback.color = col
        banner_feedback.bgcolor = ft.Colors.with_opacity(0.12 if tipo != "info" else 0.06, col)
        banner_feedback.border = ft.Border.all(1, ft.Colors.with_opacity(0.5 if tipo != "info" else 0.2, col))
        estado_ui["pedido_requiere_manual"] = pedido_manual
        btn_manual_desde_scan.visible = bool(puede_despachar and pedido_manual is not None)

    def _actualizar_estilos_tabs() -> None:
        es_pend = estado_ui["vista"] == "pendientes"
        btn_tab_pendientes.bgcolor = ROJO if es_pend else ft.Colors.TRANSPARENT
        btn_tab_pendientes.color = ft.Colors.WHITE if es_pend else interfaz.texto
        btn_tab_despachados.bgcolor = ROJO if not es_pend else ft.Colors.TRANSPARENT
        btn_tab_despachados.color = ft.Colors.WHITE if not es_pend else interfaz.texto

    def _abrir_manual(pedido: Pedido) -> None:
        if not puede_despachar or not interfaz.exigir_roles("despachador"):
            return

        def _al_confirmar(exito: bool, msg: str) -> None:
            _fijar_feedback(msg, tipo="ok" if exito else "error")
            estado_ui["pedido_destacado_id"] = None
            refrescar()
            if hasattr(interfaz, "sincronizar_sesiones"):
                try:
                    interfaz.sincronizar_sesiones()
                except Exception:
                    pass
            try:
                campo_qr.focus()
            except Exception:
                pass

        abrir_modal_confirmar_despacho_manual(interfaz, pedido, _al_confirmar)

    btn_manual_desde_scan.on_click = lambda _e: (
        _abrir_manual(estado_ui["pedido_requiere_manual"])
        if estado_ui["pedido_requiere_manual"] is not None
        else None
    )

    def refrescar(_e: Any = None) -> None:
        order_store = getattr(interfaz, "order_store", None)
        if order_store is None:
            return

        filtro = (campo_filtro.value or "").strip().lower()
        despachados = order_store.listar_pedidos_por_estado_despacho(
            estados=("despachado", "entregado"),
            limit=300,
        )
        despachados_hoy = [p for p in despachados if es_fecha_hoy(p.despachado_at or p.created_at)]
        bultos_hoy = sum(max(1, int(p.bultos or 1)) for p in despachados_hoy)

        if solo_lectura:
            kpi_val_1.value = str(len(despachados_hoy))
            kpi_val_2.value = str(bultos_hoy)
            kpi_val_3.value = str(len(despachados))
            kpi_val_4.value = str(sum(max(1, int(p.bultos or 1)) for p in despachados))
            origen = despachados_hoy if chk_solo_hoy.value else despachados
        else:
            pendientes = order_store.listar_pedidos_por_estado_despacho(
                estados=("armado",),
                limit=300,
            )
            mapa_bultos = order_store.obtener_mapa_bultos_escaneados([p.id for p in pendientes])
            en_control = sum(1 for p in pendientes if len(mapa_bultos.get(p.id, [])) > 0)
            kpi_val_1.value = str(len(pendientes))
            kpi_val_2.value = str(en_control)
            kpi_val_3.value = str(len(despachados_hoy))
            kpi_val_4.value = str(bultos_hoy)
            btn_tab_pendientes.content = f"Pendientes ({len(pendientes)})"
            btn_tab_despachados.content = f"Despachados ({len(despachados)})"
            origen = pendientes if estado_ui["vista"] == "pendientes" else despachados

        def _coincide(p: Pedido) -> bool:
            if not filtro:
                return True
            haystack = " ".join(
                [
                    p.nota_pedido or "",
                    p.numero_pedido or "",
                    p.cliente or "",
                    p.logistica or "",
                    p.armador or "",
                    p.despachado_por or "",
                    getattr(p, "numero_guia", "") or "",
                ]
            ).lower()
            return filtro in haystack

        filtrados = [p for p in origen if _coincide(p)]
        lista_pedidos.controls.clear()

        if not filtrados:
            vacio_txt = (
                "No hay pedidos despachados que coincidan con el filtro."
                if (solo_lectura or estado_ui["vista"] == "despachados")
                else "No hay pedidos pendientes (armados) para despachar."
            )
            lista_pedidos.controls.append(
                ft.Container(
                    padding=28,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.LOCAL_SHIPPING_OUTLINED, size=36, color=interfaz.secundario),
                            ft.Text(vacio_txt, size=13, color=interfaz.secundario),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                )
            )
        elif solo_lectura or estado_ui["vista"] == "despachados":
            for p in filtrados:
                lista_pedidos.controls.append(construir_tarjeta_pedido_despachado(interfaz, p))
        else:
            destacado_id = estado_ui["pedido_destacado_id"]
            # Mostrar primero el pedido actualmente escaneado si existe
            filtrados.sort(key=lambda p: (0 if p.id == destacado_id else 1, -p.id))
            for p in filtrados:
                lista_pedidos.controls.append(
                    construir_tarjeta_pedido_pendiente(
                        interfaz,
                        p,
                        bultos_escaneados=mapa_bultos.get(p.id, []),
                        on_despachar_manual=_abrir_manual,
                        destacado=(p.id == destacado_id),
                    )
                )

        if not solo_lectura:
            _actualizar_estilos_tabs()
        if getattr(interfaz, "page", None):
            try:
                interfaz.page.update()
            except Exception:
                pass

    def _procesar_qr(_e: ft.Event | None = None) -> None:
        if not puede_despachar or not interfaz.exigir_roles("despachador"):
            return
        raw = (campo_qr.value or "").strip()
        if not raw:
            return
        usuario_nom = (
            interfaz.usuario_actual.nombre_identificador
            if interfaz.usuario_actual
            else "Despachador"
        )
        res = interfaz.order_store.registrar_escaneo_bulto_despacho(
            codigo_qr_o_remito=raw,
            usuario=usuario_nom,
        )
        campo_qr.value = ""
        pedido_res: Pedido | None = res.get("pedido")

        if res.get("completado"):
            estado_ui["pedido_destacado_id"] = None
            _fijar_feedback(str(res["mensaje"]), tipo="ok")
            if hasattr(interfaz, "sincronizar_sesiones"):
                try:
                    interfaz.sincronizar_sesiones()
                except Exception:
                    pass
        elif res.get("requiere_confirmacion_bultos") and pedido_res is not None:
            estado_ui["vista"] = "pendientes"
            estado_ui["pedido_destacado_id"] = pedido_res.id
            _fijar_feedback(str(res["mensaje"]), tipo="alerta", pedido_manual=pedido_res)
        elif res.get("ok") and pedido_res is not None:
            estado_ui["vista"] = "pendientes"
            estado_ui["pedido_destacado_id"] = pedido_res.id
            _fijar_feedback(str(res["mensaje"]), tipo="parcial", pedido_manual=pedido_res)
        elif res.get("duplicado"):
            _fijar_feedback(str(res["mensaje"]), tipo="alerta")
        else:
            _fijar_feedback(str(res["mensaje"]), tipo="error")

        refrescar()
        try:
            campo_qr.focus()
        except Exception:
            pass

    campo_qr.on_submit = _procesar_qr
    campo_filtro.on_change = refrescar
    chk_solo_hoy.on_change = refrescar

    def _cambiar_tab(nueva_vista: str) -> None:
        estado_ui["vista"] = nueva_vista
        refrescar()

    btn_tab_pendientes.on_click = lambda _e: _cambiar_tab("pendientes")
    btn_tab_despachados.on_click = lambda _e: _cambiar_tab("despachados")

    bloques: list[ft.Control] = []

    # Cabecera del módulo
    if solo_lectura:
        bloques.append(
            ft.Container(
                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.BLUE_500),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500)),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.VISIBILITY, color=ft.Colors.BLUE_400, size=18),
                        ft.Text(
                            "Vista de solo lectura (Administrador): consulta únicamente de pedidos ya despachados.",
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=interfaz.texto,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
            )
        )
    else:
        bloques.append(
            ft.Row(
                [
                    campo_qr,
                    ft.Button(
                        content="Registrar QR",
                        icon=ft.Icons.QR_CODE_SCANNER,
                        bgcolor=ROJO,
                        color=ft.Colors.WHITE,
                        height=46,
                        on_click=_procesar_qr,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        bloques.append(banner_feedback)

    bloques.append(fila_kpis)

    # Barra de filtros y pestañas
    controles_barra: list[ft.Control] = []
    if not solo_lectura:
        controles_barra.extend([btn_tab_pendientes, btn_tab_despachados])
    controles_barra.append(campo_filtro)
    if solo_lectura:
        controles_barra.append(chk_solo_hoy)
    controles_barra.append(
        ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Actualizar listado",
            on_click=refrescar,
        )
    )
    bloques.append(
        ft.Row(
            controles_barra,
            spacing=8,
            wrap=es_movil,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )
    bloques.append(lista_pedidos)

    refrescar()

    contenedor = ft.Container(
        expand=not (es_movil and not modo_dialogo),
        bgcolor=interfaz.superficie if not modo_dialogo else None,
        border=ft.Border.all(1, interfaz.borde) if not modo_dialogo else None,
        border_radius=14 if not modo_dialogo else 0,
        padding=16 if not modo_dialogo else 0,
        content=ft.Column(
            bloques,
            expand=not (es_movil and not modo_dialogo),
            spacing=10,
            tight=modo_dialogo or es_movil,
        ),
    )
    return contenedor, refrescar


def mostrar_modulo_despacho(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Abre el módulo exclusivo Despacho: operativo para `despachador`, solo lectura para `administrador`."""
    if not interfaz.exigir_roles("despachador", "administrador"):
        return

    rol = str(getattr(getattr(interfaz, "usuario_actual", None), "role", "")).strip().lower()
    es_solo_lectura = rol == "administrador"
    titulo = (
        "Despacho · Pedidos Despachados (Solo Lectura)"
        if es_solo_lectura
        else "Módulo Despacho · Control QR y Bultos"
    )
    vista, _refrescar = construir_vista_modulo_despacho(interfaz, modo_dialogo=True)

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.LOCAL_SHIPPING, color=ROJO),
                ft.Text(titulo, weight=ft.FontWeight.BOLD, size=16),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=820,
            height=560,
            content=vista,
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dlg)
