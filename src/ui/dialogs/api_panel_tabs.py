"""Pestañas auxiliares de Documentación/Estado y Sesiones Activas para el panel API Master."""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
import webbrowser
from datetime import datetime
from typing import Any, Callable

import flet as ft

from ...server_app import PUERTO_WEB_DEFAULT as _DEFAULT_PUERTO
from ...server_app import obtener_ip_local as _default_ip_local
from ...server_app import obtener_ip_tailscale as _default_ip_tailscale
from ..design import colores_de, confirmar_accion_destructiva, es_viewport_estrecho, par_accion_tarjeta, tono_legible
from ..theme import ROJO, SECUNDARIO


def formatear_timestamp_api(ts: float | str | None) -> str:
    """Convierte timestamp numérico o string ISO a formato legible dd/mm/aaaa hh:mm."""
    if not ts:
        return "Nunca"
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts)
        else:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(ts)[:16]


def construir_estado_vacio_api(
    icono: str,
    titulo: str,
    subtitulo: str = "",
    color_sec: Any | None = None,
) -> ft.Container:
    """Construye un estado vacío estándar para listas de claves o sesiones API."""
    c_sec = color_sec or SECUNDARIO
    controles = [ft.Icon(icono, size=36, color=c_sec), ft.Text(titulo, size=13, color=c_sec)]
    if subtitulo:
        controles.append(ft.Text(subtitulo, size=11, color=c_sec))
    return ft.Container(
        content=ft.Column(controles, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        alignment=ft.Alignment.CENTER,
        padding=20,
    )


def _resolver_red_api():
    """Devuelve utilidades y constantes de red por defecto del servidor."""
    return _default_ip_local, _default_ip_tailscale, _DEFAULT_PUERTO


def construir_tab_docs_estado(interfaz: Any, texto_color: str) -> ft.Column:
    """Construye la pestaña de Documentación, enlaces de red y ping de salud API."""
    ip_lan_fn, ip_ts_fn, puerto_def = _resolver_red_api()
    puerto = getattr(interfaz, "puerto_web", puerto_def) or puerto_def
    ip_lan = ip_lan_fn()
    ip_tailscale = ip_ts_fn()
    esquema_actual = (os.environ.get("STOCKAGENT_SCHEME") or "https").strip().lower()
    if esquema_actual not in ("http", "https"):
        esquema_actual = "https"
    url_local = f"{esquema_actual}://localhost:{puerto}"
    url_lan = f"{esquema_actual}://{ip_lan}:{puerto}"
    docs_habilitados = os.environ.get("STOCKAGENT_ENABLE_API_DOCS", "0").strip().lower() in (
        "1", "true", "si", "yes"
    )
    url_docs = f"{url_local}/docs"
    url_redoc = f"{url_local}/redoc"

    def abrir_url_docs(target_url: str) -> None:
        if not docs_habilitados:
            interfaz.notificar(
                "🔒 Swagger/ReDoc están deshabilitados por seguridad en red. "
                "Define STOCKAGENT_ENABLE_API_DOCS=1 en .env solo para depuración local."
            )
            return
        try:
            interfaz.page.launch_url(target_url)
        except Exception:
            try:
                webbrowser.open(target_url)
            except Exception as exc:
                interfaz.notificar(f"No se pudo abrir el navegador: {exc}")

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    colores = colores_de(interfaz)
    res_salud_txt = ft.Text("", size=11)

    def probar_salud(_e: ft.Event) -> None:
        res_salud_txt.value = "Consultando endpoint /api/v1/sistema/ping..."
        res_salud_txt.color = colores.info
        interfaz.page.update()
        try:
            req = urllib.request.Request(f"{url_local}/api/v1/sistema/ping", headers={"User-Agent": "StockAgent-UI"})
            ctx = ssl._create_unverified_context() if url_local.startswith("https://") else None
            with urllib.request.urlopen(req, timeout=2.0, context=ctx) as resp:
                status_code = resp.getcode()
                body = json.loads(resp.read().decode("utf-8"))
            res_salud_txt.value = f"✅ HTTP {status_code} OK: {body}"
            res_salud_txt.color = colores.exito
        except Exception as exc:
            res_salud_txt.value = f"⚠️ Falló consulta directa ({exc}). Verifique que el servidor web esté en ejecución."
            res_salud_txt.color = colores.advertencia
        interfaz.page.update()

    tarjeta_red = ft.Container(
        content=ft.Column(
            [
                ft.Row([ft.Icon(ft.Icons.ROUTER, color=colores.info, size=20), ft.Text("Direcciones del Servidor REST", weight=ft.FontWeight.BOLD, color=texto_color)], spacing=6),
                ft.Text(f"• Localhost: {url_local}", size=12, font_family="monospace", color=texto_color),
                ft.Text(f"• Red Local (LAN): {url_lan}", size=12, font_family="monospace", color=texto_color),
                *([ft.Text(f"• Tailscale VPN: {esquema_actual}://{ip_tailscale}:{puerto}", size=12, font_family="monospace", color=texto_color)] if ip_tailscale else []),
                ft.Text(
                    "• Documentación Swagger/ReDoc: " + ("Habilitada (STOCKAGENT_ENABLE_API_DOCS=1)" if docs_habilitados else "Deshabilitada por seguridad en red"),
                    size=11,
                    color=colores.exito if docs_habilitados else colores.advertencia,
                ),
                ft.Row(
                    [
                        ft.Button("Abrir Swagger UI (/docs)", icon=ft.Icons.OPEN_IN_BROWSER, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=lambda _e: abrir_url_docs(url_docs)),
                        ft.Button("Abrir ReDoc (/redoc)", icon=ft.Icons.MENU_BOOK, on_click=lambda _e: abrir_url_docs(url_redoc)),
                        ft.Button("Ping Salud", icon=ft.Icons.HEALTH_AND_SAFETY, on_click=probar_salud),
                    ],
                    spacing=8,
                    wrap=True,
                    run_spacing=6,
                ),
                res_salud_txt,
            ],
            spacing=8,
        ),
        padding=12,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, texto_color)),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.04, texto_color),
    )

    tarjeta_endpoints = ft.Container(
        content=ft.Column(
            [
                ft.Row([ft.Icon(ft.Icons.DATA_OBJECT, color=colores.advertencia, size=20), ft.Text("Endpoints Principales Disponibles (v1)", weight=ft.FontWeight.BOLD, color=texto_color)], spacing=6),
                ft.Text("• GET  /api/v1/sistema/ping y /api/v1/sistema/estado — Conectividad y estado del servidor.", size=12, color=texto_color),
                ft.Text("• POST /api/v1/auth/login y /api/v1/auth/logout — Autenticación y cierre de sesión Bearer.", size=12, color=texto_color),
                ft.Text("• GET  /api/v1/auth/me — Perfil y permisos del usuario o API Key autenticada.", size=12, color=texto_color),
                ft.Text("• GET  /api/v1/productos/buscar y /api/v1/productos/{codigo_o_barcode} — Búsqueda y ficha por SKU o código de barras.", size=12, color=texto_color),
                ft.Text("• GET  /api/v1/productos/{codigo}/stock — Consulta rápida de existencia de inventario (B2B / ERP).", size=12, color=texto_color),
                ft.Text("• POST /api/v1/inventario/comparar-preliminar y /api/v1/inventario/finalizar — Relevamiento de inventario físico.", size=12, color=texto_color),
                ft.Text("• GET  /api/v1/despacho/pedidos y POST /api/v1/despacho/escanear — Listado de pedidos y escaneo QR/remito.", size=12, color=texto_color),
                ft.Divider(),
                ft.Text("Ejemplo de encabezados HTTP requeridos:", weight=ft.FontWeight.BOLD, size=11, color=texto_color),
                ft.Text("X-API-Key: sk_live_...\no\nAuthorization: Bearer <token_de_sesion>", font_family="monospace", size=11, color=tono_legible("LIGHT_BLUE", es_oscuro)),
            ],
            spacing=6,
        ),
        padding=12,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, texto_color)),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.04, texto_color),
    )

    return ft.Column([tarjeta_red, tarjeta_endpoints], spacing=10, scroll=ft.ScrollMode.AUTO, height=320)


def construir_tab_sesiones(
    interfaz: Any,
    user_store: Any,
    texto_color: str,
) -> tuple[ft.Column, Callable[[], None]]:
    """Construye la pestaña de Sesiones Activas de API/Web y devuelve (vista, refrescar_fn)."""
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    colores = colores_de(interfaz)
    sec_color = getattr(interfaz, "secundario", colores.secundario)
    lista_sesiones = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=260)
    total_sesiones_txt = ft.Text("0 sesiones activas", size=12, color=sec_color)

    def ejecutar_revocar_sesion(th: str, u_nom: str = "") -> None:
        try:
            ok = user_store.revoke_api_session(th)
            if ok:
                order_store = getattr(interfaz, "order_store", None)
                if order_store and hasattr(order_store, "registrar_auditoria"):
                    usr_act = getattr(getattr(interfaz, "usuario_actual", None), "username", "Master")
                    order_store.registrar_auditoria(usr_act, "REVOCAR_SESION_API", f"Usuario: {u_nom or th[:12]}")
                interfaz.notificar("🔒 Sesión revocada con éxito.")
                refrescar_lista_sesiones()
            else:
                interfaz.notificar("❌ No se pudo revocar la sesión.")
        except Exception as exc:
            interfaz.notificar(f"❌ Error al revocar sesión: {exc}")

    def refrescar_lista_sesiones() -> None:
        try:
            sesiones = user_store.list_api_sessions(max_records=100)
        except Exception as exc:
            lista_sesiones.controls = [ft.Text(f"Error al cargar sesiones: {exc}", color=colores.error)]
            interfaz.page.update()
            return

        total_sesiones_txt.value = f"{len(sesiones)} sesión(es) persistida(s)"
        if not sesiones:
            lista_sesiones.controls = [
                construir_estado_vacio_api(ft.Icons.DEVICES_OTHER, "No hay sesiones de API activas registradas.", color_sec=sec_color)
            ]
            interfaz.page.update()
            return

        items = []
        for s in sesiones:
            th = s.get("token_hash", "")
            u_nom = s.get("username", "desconocido")
            nom = s.get("nombre", "") or u_nom
            rol_s = s.get("role", "operador")
            c_at = formatear_timestamp_api(s.get("created_at"))
            l_act = formatear_timestamp_api(s.get("last_active"))

            info_sesion = ft.Row(
                [
                    ft.Icon(ft.Icons.LAPTOP_CHROMEBOOK, color=tono_legible("CYAN", es_oscuro), size=22),
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"{nom} (@{u_nom})", weight=ft.FontWeight.BOLD, size=13, color=texto_color),
                                    ft.Text(f"[{rol_s.upper()}]", size=11, color=colores.info),
                                ],
                                spacing=6,
                                wrap=True,
                                run_spacing=2,
                            ),
                            ft.Text(
                                f"Token: {th[:12]}... | Creada: {c_at} | Última actividad: {l_act}",
                                size=11,
                                color=sec_color,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        expand=True,
                        spacing=2,
                    ),
                ],
                spacing=8,
                expand=not es_viewport_estrecho(interfaz, umbral=560.0),
            )
            btn_rev_ses = ft.Button(
                "Cerrar sesión",
                icon=ft.Icons.LOGOUT,
                style=ft.ButtonStyle(color=colores.error),
                on_click=lambda _e, h=th, u=u_nom: ejecutar_revocar_sesion(h, u),
            )
            items.append(
                ft.Container(
                    content=par_accion_tarjeta(interfaz, info_sesion, btn_rev_ses, umbral=560.0, spacing=8),
                    padding=ft.Padding.all(8),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.12, texto_color)),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.03, texto_color),
                )
            )
        lista_sesiones.controls = items
        interfaz.page.update()

    def ejecutar_limpiar_expiradas(_e: ft.Event) -> None:
        try:
            cant = user_store.cleanup_expired_api_sessions(24 * 3600)
            interfaz.notificar(f"🧹 Se eliminaron {cant} sesiones inactivas expiradas.")
            refrescar_lista_sesiones()
        except Exception as exc:
            interfaz.notificar(f"❌ Error al limpiar sesiones: {exc}")

    def ejecutar_cerrar_todas(_e: ft.Event) -> None:
        def _do_cerrar_todas() -> None:
            cant = user_store.revoke_all_sessions()
            refrescar_lista_sesiones()
            interfaz.notificar(f"⚠️ Se cerraron todas las {cant} sesiones activas.")

        confirmar_accion_destructiva(
            interfaz,
            "Cerrar Todas las Sesiones API",
            "¿Confirmas revocar todas las sesiones activas de dispositivos móviles y clientes API? Todos los usuarios deberán volver a iniciar sesión.",
            _do_cerrar_todas,
            texto_confirmar="Sí, Cerrar Todas",
            roles_permitidos=("master",),
            auditoria=("REVOCAR_TODAS_SESIONES_API", "Revocación masiva de sesiones API/Móvil"),
        )

    acciones_sesiones = ft.Row(
        [
            ft.Button("Limpiar Expiradas", icon=ft.Icons.CLEANING_SERVICES, on_click=ejecutar_limpiar_expiradas),
            ft.Button("Cerrar Todas", icon=ft.Icons.LOGOUT, style=ft.ButtonStyle(color=colores.error), on_click=ejecutar_cerrar_todas),
        ],
        spacing=6,
        wrap=True,
        run_spacing=4,
    )
    vista_sesiones = ft.Column(
        [
            par_accion_tarjeta(
                interfaz,
                ft.Text("Sesiones de usuarios y terminales autenticados mediante API / Web móvil.", size=12, color=sec_color, expand=True),
                acciones_sesiones,
                umbral=600.0,
                spacing=8,
            ),
            ft.Divider(),
            ft.Row([ft.Text("Sesiones Activas", weight=ft.FontWeight.BOLD, size=13, color=texto_color), total_sesiones_txt], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            lista_sesiones,
        ],
        spacing=8,
    )
    return vista_sesiones, refrescar_lista_sesiones
