"""Modal Flet para administración por SKU de ubicaciones multi-zona y lotes FEFO."""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ...warehouse_slotting import analizar_ubicaciones_sku
from ..theme import ROJO

_ZONAS_VALIDAS: tuple[str, ...] = ("picking", "pulmon", "pallet", "recepcion", "cuarentena")


def _resolver_product_store(interfaz: Any, stock_manager: Any) -> Any | None:
    p_store = getattr(stock_manager, "product_store", None) if stock_manager is not None else None
    if p_store is None:
        p_store = getattr(interfaz, "product_store", None)
    return p_store


def _safe_update(interfaz: Any) -> None:
    try:
        if hasattr(interfaz, "page") and interfaz.page:
            interfaz.page.update()
    except Exception:
        pass


def mostrar_dialogo_ubicaciones_lotes(
    interfaz: Any,
    stock_manager: Any,
    producto: Any,
    on_actualizado: Callable[[], None] | None = None,
) -> None:
    """Abre un diálogo modal para gestionar zonas, traslados internos y lotes FEFO de un SKU."""
    if not interfaz.exigir_roles("administrador", "operador"):
        return

    product_store = _resolver_product_store(interfaz, stock_manager)
    if product_store is None or not hasattr(product_store, "listar_ubicaciones_producto"):
        interfaz.notificar("El módulo de multi-ubicación y lotes requiere ProductStore inicializado.")
        return

    codigo = str(producto["code"]).strip()
    nombre = str(producto["name"]).strip()
    dark = bool(getattr(interfaz, "modo_oscuro", True))
    card_bg = ft.Colors.WHITE_10 if dark else ft.Colors.GREY_100
    card_border = ft.Border.all(1, ft.Colors.WHITE_24 if dark else ft.Colors.GREY_300)

    resumen_txt = ft.Text("", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_400)
    lista_ubicaciones = ft.ListView(height=150, spacing=6)
    lista_lotes = ft.ListView(height=150, spacing=6)

    campo_ubic = ft.TextField(label="Ubicación (ej: P-01-2)", width=150, dense=True)
    campo_zona = ft.Dropdown(
        label="Zona",
        value="picking",
        options=[ft.dropdown.Option(z, z.capitalize()) for z in _ZONAS_VALIDAS],
        width=130,
        dense=True,
    )
    campo_ubic_stock = ft.TextField(
        label="Stock", value="0", width=80, keyboard_type=ft.KeyboardType.NUMBER, dense=True
    )
    campo_ubic_cap = ft.TextField(
        label="Cap. máx", value="0", width=85, keyboard_type=ft.KeyboardType.NUMBER, dense=True
    )
    chk_principal = ft.Checkbox(label="Principal", value=False)

    campo_origen = ft.Dropdown(label="Origen", width=130, dense=True, options=[])
    campo_destino = ft.TextField(label="Destino", width=130, dense=True)
    campo_dest_zona = ft.Dropdown(
        label="Zona dest.",
        value="picking",
        options=[ft.dropdown.Option(z, z.capitalize()) for z in _ZONAS_VALIDAS],
        width=125,
        dense=True,
    )
    campo_transf_cant = ft.TextField(
        label="Cant. traslado", value="1", width=105, keyboard_type=ft.KeyboardType.NUMBER, dense=True
    )

    campo_lote = ft.TextField(label="Lote *", width=130, dense=True)
    campo_lote_cant = ft.TextField(
        label="Cant. lote", value="0", width=90, keyboard_type=ft.KeyboardType.NUMBER, dense=True
    )
    campo_lote_fv = ft.TextField(
        label="Vencimiento (YYYY-MM-DD)", width=165, hint_text="Opcional", dense=True
    )
    campo_lote_ubic = ft.TextField(label="Ubicación", width=120, dense=True)

    def _refrescar_vista() -> None:
        snap = analizar_ubicaciones_sku(product_store, codigo)
        resumen_txt.value = (
            f"Físico: {snap['stock_fisico']} u.  ·  "
            f"Reservado: {snap['stock_reservado']} u.  ·  "
            f"Disponible neto: {snap['stock_disponible']} u."
        )

        ubics = snap.get("ubicaciones", [])
        lista_ubicaciones.controls.clear()
        opciones_origen: list[ft.dropdown.Option] = []
        for u in ubics:
            opciones_origen.append(ft.dropdown.Option(u["ubicacion"], f"{u['ubicacion']} ({u['stock']} u.)"))
            princ_tag = " · ⭐ PRINCIPAL" if u.get("es_principal") else ""
            cap_tag = f" / máx {u['capacidad_max']}" if int(u.get("capacidad_max", 0)) > 0 else ""
            lista_ubicaciones.controls.append(
                ft.Container(
                    bgcolor=card_bg,
                    border=card_border,
                    border_radius=6,
                    padding=8,
                    content=ft.Row(
                        [
                            ft.Text(str(u["ubicacion"]), weight=ft.FontWeight.BOLD, size=12),
                            ft.Text(f"[{u['tipo_zona']}{princ_tag}]", size=11, color=ft.Colors.TEAL_300),
                            ft.Text(
                                f"Saldo: {u['stock']} u.{cap_tag}",
                                size=11,
                                color=interfaz.texto,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                )
            )
        if not lista_ubicaciones.controls:
            lista_ubicaciones.controls.append(
                ft.Text("Sin ubicaciones multi-zona registradas aún.", size=11, color=interfaz.secundario)
            )
        campo_origen.options = opciones_origen
        if opciones_origen and (campo_origen.value not in [o.key for o in opciones_origen]):
            campo_origen.value = opciones_origen[0].key

        lotes = snap.get("lotes_fefo", [])
        lista_lotes.controls.clear()
        for lt in lotes:
            fv = str(lt.get("fecha_vencimiento") or "") or "Sin vencimiento"
            vencido = bool(lt.get("vencido", False))
            color_v = ft.Colors.RED_400 if vencido else ft.Colors.GREEN_400
            lista_lotes.controls.append(
                ft.Container(
                    bgcolor=card_bg,
                    border=card_border,
                    border_radius=6,
                    padding=8,
                    content=ft.Row(
                        [
                            ft.Text(str(lt["lote"]), weight=ft.FontWeight.BOLD, size=12),
                            ft.Text(f"Ubic: {lt.get('ubicacion') or '-'}", size=11, color=interfaz.secundario),
                            ft.Text(f"Vto: {fv}", size=11, color=color_v),
                            ft.Text(f"{lt.get('stock', 0)} u. ({lt.get('estado', '')})", size=11),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                )
            )
        if not lista_lotes.controls:
            lista_lotes.controls.append(
                ft.Text("Sin lotes registrados para control FEFO.", size=11, color=interfaz.secundario)
            )
        _safe_update(interfaz)

    def _guardar_ubicacion(_e: Any) -> None:
        try:
            product_store.asignar_ubicacion_producto(
                codigo,
                campo_ubic.value or "",
                tipo_zona=campo_zona.value or "picking",
                stock=int((campo_ubic_stock.value or "0").strip()),
                capacidad_max=int((campo_ubic_cap.value or "0").strip()),
                es_principal=bool(chk_principal.value),
            )
            campo_ubic.value = ""
            interfaz.notificar(f"Ubicación guardada para {codigo}.", color=ft.Colors.GREEN_600)
            _refrescar_vista()
            if on_actualizado is not None:
                on_actualizado()
        except Exception as exc:
            interfaz.notificar(f"No se pudo guardar la ubicación: {exc}")

    def _ejecutar_transferencia(_e: Any) -> None:
        try:
            res = product_store.transferir_entre_ubicaciones(
                codigo,
                campo_origen.value or "",
                campo_destino.value or "",
                int((campo_transf_cant.value or "0").strip()),
                destino_zona=campo_dest_zona.value or "picking",
            )
            campo_destino.value = ""
            interfaz.notificar(
                f"Trasladadas {res['cantidad']} u. de {res['origen']['ubicacion']} a {res['destino']['ubicacion']}.",
                color=ft.Colors.GREEN_600,
            )
            _refrescar_vista()
            if on_actualizado is not None:
                on_actualizado()
        except Exception as exc:
            interfaz.notificar(f"No se pudo transferir stock: {exc}")

    def _guardar_lote(_e: Any) -> None:
        try:
            product_store.registrar_lote(
                codigo,
                campo_lote.value or "",
                int((campo_lote_cant.value or "0").strip()),
                fecha_vencimiento=campo_lote_fv.value or "",
                ubicacion=campo_lote_ubic.value or "",
            )
            campo_lote.value = ""
            campo_lote_fv.value = ""
            interfaz.notificar(f"Lote registrado para {codigo}.", color=ft.Colors.GREEN_600)
            _refrescar_vista()
            if on_actualizado is not None:
                on_actualizado()
        except Exception as exc:
            interfaz.notificar(f"No se pudo registrar el lote: {exc}")

    tabs_sku = ft.Tabs(
        length=2,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Ubicaciones y Traslados", icon=ft.Icons.WAREHOUSE_OUTLINED),
                        ft.Tab(label="Lotes FEFO", icon=ft.Icons.CALENDAR_MONTH_OUTLINED),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Column(
                            [
                                lista_ubicaciones,
                                ft.Divider(height=6, color=interfaz.borde),
                                ft.Text("Asignar / actualizar ubicación", size=11, weight=ft.FontWeight.BOLD),
                                ft.Row(
                                    [
                                        campo_ubic,
                                        campo_zona,
                                        campo_ubic_stock,
                                        campo_ubic_cap,
                                        chk_principal,
                                        ft.Button("Guardar Ubic.", on_click=_guardar_ubicacion, bgcolor=ROJO, color=ft.Colors.WHITE),
                                    ],
                                    spacing=6,
                                    wrap=True,
                                ),
                                ft.Text("Transferir existencias entre ubicaciones", size=11, weight=ft.FontWeight.BOLD),
                                ft.Row(
                                    [
                                        campo_origen,
                                        campo_destino,
                                        campo_dest_zona,
                                        campo_transf_cant,
                                        ft.Button("Transferir", on_click=_ejecutar_transferencia),
                                    ],
                                    spacing=6,
                                    wrap=True,
                                ),
                            ],
                            spacing=6,
                            scroll=ft.ScrollMode.ADAPTIVE,
                        ),
                        ft.Column(
                            [
                                lista_lotes,
                                ft.Divider(height=6, color=interfaz.borde),
                                ft.Text("Alta / actualización de lote FEFO", size=11, weight=ft.FontWeight.BOLD),
                                ft.Row(
                                    [
                                        campo_lote,
                                        campo_lote_cant,
                                        campo_lote_fv,
                                        campo_lote_ubic,
                                        ft.Button("Registrar Lote", on_click=_guardar_lote, bgcolor=ROJO, color=ft.Colors.WHITE),
                                    ],
                                    spacing=6,
                                    wrap=True,
                                ),
                            ],
                            spacing=6,
                            scroll=ft.ScrollMode.ADAPTIVE,
                        ),
                    ],
                ),
            ],
        ),
    )

    ancho_dlg = interfaz.ancho_adaptable(700) if hasattr(interfaz, "ancho_adaptable") else 700
    alto_dlg = interfaz.alto_adaptable(470) if hasattr(interfaz, "alto_adaptable") else 470
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Column(
            [
                ft.Text(f"Ubicaciones y Lotes FEFO — [{codigo}] {nombre}", size=15, weight=ft.FontWeight.BOLD),
                resumen_txt,
            ],
            spacing=3,
        ),
        content=ft.Container(width=ancho_dlg, height=alto_dlg, content=tabs_sku),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)
    _refrescar_vista()
