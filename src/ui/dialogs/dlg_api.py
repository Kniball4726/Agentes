"""Diálogo modal para la gestión de API REST, Claves de Integración y Sesiones (Master)."""

from datetime import datetime
import time
from typing import Any
import webbrowser
import flet as ft

from ..theme import ROJO, SUPERFICIE, TEXTO, SECUNDARIO, BORDE
from ...server import obtener_ip_local, obtener_ip_tailscale, PUERTO_WEB_DEFAULT


def _formatear_timestamp(ts: float | str | None) -> str:
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


def mostrar_dialogo_api_master(interfaz: Any, tab_inicial: int = 0) -> None:
    """Abre el panel maestro de API REST: claves API, documentación Swagger y sesiones activas."""
    if not interfaz.exigir_roles("master"):
        return

    user_store = getattr(interfaz, "user_store", None)
    if not user_store:
        interfaz.notificar("❌ No se pudo acceder al almacén de usuarios.")
        return

    es_oscuro = getattr(interfaz, "modo_oscuro", True)
    bg_activo = ROJO
    bg_inactivo = ft.Colors.BLUE_GREY_800 if es_oscuro else ft.Colors.BLUE_GREY_100
    texto_color = getattr(interfaz, "texto", ft.Colors.WHITE if es_oscuro else ft.Colors.BLACK)

    # Puertos y enlaces de red
    puerto = getattr(interfaz, "puerto_web", PUERTO_WEB_DEFAULT) or PUERTO_WEB_DEFAULT
    ip_lan = obtener_ip_local()
    ip_tailscale = obtener_ip_tailscale()
    url_local = f"http://localhost:{puerto}"
    url_lan = f"http://ip_lan:{puerto}".replace("ip_lan", ip_lan)
    url_docs = f"{url_local}/docs"
    url_redoc = f"{url_local}/redoc"

    # --- PESTAÑA 1: CLAVES API ---
    input_cliente = ft.TextField(
        label="Nombre del Cliente / Sistema Externo *",
        hint_text="Ej: ERP Logística, Facturación B2B, App Externa",
        expand=True,
        dense=True,
    )
    dd_rol = ft.Dropdown(
        label="Rol API",
        value="operador",
        options=[
            ft.DropdownOption("operador", "Operador (Despacho / Stock)"),
            ft.DropdownOption("consulta", "Consulta (Solo lectura)"),
            ft.DropdownOption("administrador", "Administrador (Completo catálogo)"),
            ft.DropdownOption("master", "Master (Acceso irrestricto)"),
        ],
        width=230,
        dense=True,
    )

    banner_nueva_clave = ft.Container(visible=False)
    lista_claves = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=260)
    total_keys_txt = ft.Text("0 claves registradas", size=12, color=SECUNDARIO)

    def refrescar_lista_claves() -> None:
        try:
            keys = user_store.list_api_keys()
        except Exception as exc:
            lista_claves.controls = [ft.Text(f"Error al cargar claves: {exc}", color=ft.Colors.RED_400)]
            interfaz.page.update()
            return

        total_keys_txt.value = f"{len(keys)} clave(s) registrada(s)"
        if not keys:
            lista_claves.controls = [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.VPN_KEY_OFF, size=36, color=SECUNDARIO),
                            ft.Text("No hay claves API generadas aún.", size=13, color=SECUNDARIO),
                            ft.Text("Genera una clave arriba para conectar sistemas externos.", size=11, color=SECUNDARIO),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=20,
                )
            ]
            interfaz.page.update()
            return

        items = []
        for k in keys:
            k_hash = k.get("key_hash", "")
            c_name = k.get("client_name", "Desconocido")
            rol_k = k.get("role", "operador")
            activo = bool(k.get("active", 1))
            creado = _formatear_timestamp(k.get("created_at"))
            ultimo = _formatear_timestamp(k.get("last_used"))

            badge_estado = ft.Container(
                content=ft.Text("ACTIVA" if activo else "REVOCADA", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.GREEN_700 if activo else ft.Colors.RED_800,
                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                border_radius=4,
            )

            badge_rol = ft.Container(
                content=ft.Text(rol_k.upper(), size=10, weight=ft.FontWeight.W_500, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.BLUE_GREY_700,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=4,
            )

            def hacer_revocar(h: str = k_hash):
                return lambda _e: ejecutar_revocar_clave(h)

            def hacer_eliminar(h: str = k_hash):
                return lambda _e: ejecutar_eliminar_clave(h)

            acciones = [
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="Eliminar clave permanentemente",
                    icon_color=ft.Colors.RED_400,
                    icon_size=18,
                    on_click=hacer_eliminar(),
                )
            ]
            if activo:
                acciones.insert(
                    0,
                    ft.Button(
                        "Revocar",
                        icon=ft.Icons.BLOCK,
                        style=ft.ButtonStyle(
                            color=ft.Colors.RED_400,
                            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                        ),
                        on_click=hacer_revocar(),
                    ),
                )

            tarjeta = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.KEY if activo else ft.Icons.KEY_OFF, color=ft.Colors.AMBER_400 if activo else SECUNDARIO, size=24),
                        ft.Column(
                            [
                                ft.Row([ft.Text(c_name, weight=ft.FontWeight.BOLD, size=13), badge_rol, badge_estado], spacing=8),
                                ft.Text(f"Hash: {k_hash[:14]}... | Creada: {creado} | Último uso: {ultimo}", size=11, color=SECUNDARIO),
                            ],
                            expand=True,
                            spacing=2,
                        ),
                        ft.Row(acciones, spacing=4),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.Padding.all(10),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, texto_color)),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.03, texto_color),
            )
            items.append(tarjeta)

        lista_claves.controls = items
        interfaz.page.update()

    def ejecutar_crear_clave(_e: ft.Event) -> None:
        cliente = (input_cliente.value or "").strip()
        if not cliente:
            interfaz.notificar("⚠️ Ingrese un nombre descriptivo para el cliente o sistema externo.")
            return

        rol_elegido = dd_rol.value or "operador"
        try:
            raw_key, key_hash = user_store.create_api_key(client_name=cliente, role=rol_elegido)
        except Exception as exc:
            interfaz.notificar(f"❌ Error al crear clave API: {exc}")
            return

        input_cliente.value = ""
        banner_nueva_clave.visible = True
        banner_nueva_clave.content = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400, size=20),
                            ft.Text("¡Clave API Generada Exitosamente!", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                        ],
                        spacing=6,
                    ),
                    ft.Text(
                        "⚠️ COPIA ESTA CLAVE AHORA. Por motivos de seguridad de cifrado, nunca volverá a mostrarse completa:",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.AMBER_300,
                    ),
                    ft.Row(
                        [
                            ft.TextField(
                                value=raw_key,
                                read_only=True,
                                expand=True,
                                dense=True,
                                text_style=ft.TextStyle(font_family="monospace", size=12),
                            ),
                            ft.Button(
                                "Copiar",
                                icon=ft.Icons.COPY,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                on_click=lambda _ev: copiar_al_portapapeles(raw_key),
                            ),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding.all(12),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN),
            border=ft.Border.all(1, ft.Colors.GREEN_700),
            border_radius=8,
        )
        refrescar_lista_claves()
        interfaz.notificar("✅ Clave API generada con éxito.")

    def copiar_al_portapapeles(texto: str) -> None:
        try:
            interfaz.page.set_clipboard(texto)
            interfaz.notificar("📋 Clave API copiada al portapapeles.")
        except Exception:
            interfaz.notificar("⚠️ Selecciona el texto manualmente para copiar.")

    def ejecutar_revocar_clave(k_hash: str) -> None:
        try:
            ok = user_store.revoke_api_key(k_hash)
            if ok:
                interfaz.notificar("🔒 Clave API revocada. No se aceptarán más peticiones con ella.")
                refrescar_lista_claves()
            else:
                interfaz.notificar("❌ No se pudo revocar la clave.")
        except Exception as exc:
            interfaz.notificar(f"❌ Error al revocar clave: {exc}")

    def ejecutar_eliminar_clave(k_hash: str) -> None:
        try:
            ok = user_store.delete_api_key(k_hash)
            if ok:
                interfaz.notificar("🗑️ Clave eliminada del registro.")
                refrescar_lista_claves()
            else:
                interfaz.notificar("❌ No se pudo eliminar la clave.")
        except Exception as exc:
            interfaz.notificar(f"❌ Error al eliminar clave: {exc}")

    btn_crear = ft.Button(
        "Generar Clave API",
        icon=ft.Icons.KEY,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        on_click=ejecutar_crear_clave,
    )

    vista_keys = ft.Column(
        [
            ft.Text(
                "Emite claves API estáticas (sk_live_...) para autenticar clientes B2B, ERPs o lectores externos mediante encabezado X-API-Key.",
                size=12,
                color=SECUNDARIO,
            ),
            ft.Row([input_cliente, dd_rol, btn_crear], spacing=8, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            banner_nueva_clave,
            ft.Divider(),
            ft.Row([ft.Text("Claves Registradas", weight=ft.FontWeight.BOLD, size=13), total_keys_txt], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            lista_claves,
        ],
        spacing=8,
    )

    # --- PESTAÑA 2: DOCUMENTACIÓN Y ESTADO ---
    def abrir_url(target_url: str) -> None:
        try:
            interfaz.page.launch_url(target_url)
        except Exception:
            try:
                webbrowser.open(target_url)
            except Exception as exc:
                interfaz.notificar(f"No se pudo abrir el navegador: {exc}")

    res_salud_txt = ft.Text("", size=11)

    def probar_salud(_e: ft.Event) -> None:
        res_salud_txt.value = "Consultando endpoint /api/v1/sistema/health..."
        res_salud_txt.color = ft.Colors.BLUE_400
        interfaz.page.update()
        try:
            import urllib.request
            import json

            req = urllib.request.Request(f"{url_local}/api/v1/sistema/health", headers={"User-Agent": "StockAgent-UI"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                status_code = resp.getcode()
                body = json.loads(resp.read().decode("utf-8"))
            res_salud_txt.value = f"✅ HTTP {status_code} OK: {body}"
            res_salud_txt.color = ft.Colors.GREEN_400
        except Exception as exc:
            res_salud_txt.value = f"⚠️ Falló consulta directa ({exc}). Verifique que el servidor web esté en ejecución."
            res_salud_txt.color = ft.Colors.AMBER_400
        interfaz.page.update()

    tarjeta_red = ft.Container(
        content=ft.Column(
            [
                ft.Row([ft.Icon(ft.Icons.ROUTER, color=ft.Colors.BLUE_400, size=20), ft.Text("Direcciones del Servidor REST", weight=ft.FontWeight.BOLD)], spacing=6),
                ft.Text(f"• Localhost: {url_local}", size=12, font_family="monospace"),
                ft.Text(f"• Red Local (LAN): {url_lan}", size=12, font_family="monospace"),
                *( [ft.Text(f"• Tailscale VPN: http://{ip_tailscale}:{puerto}", size=12, font_family="monospace")] if ip_tailscale else [] ),
                ft.Row(
                    [
                        ft.Button("Abrir Swagger UI (/docs)", icon=ft.Icons.OPEN_IN_BROWSER, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=lambda _e: abrir_url(url_docs)),
                        ft.Button("Abrir ReDoc (/redoc)", icon=ft.Icons.MENU_BOOK, on_click=lambda _e: abrir_url(url_redoc)),
                        ft.Button("Health Check", icon=ft.Icons.HEALTH_AND_SAFETY, on_click=probar_salud),
                    ],
                    spacing=8,
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
                ft.Row([ft.Icon(ft.Icons.DATA_OBJECT, color=ft.Colors.AMBER_400, size=20), ft.Text("Endpoints Principales Disponibles (v1)", weight=ft.FontWeight.BOLD)], spacing=6),
                ft.Text("• GET  /api/v1/sistema/health — Estado operativo y de base de datos.", size=12),
                ft.Text("• POST /api/v1/auth/login — Autenticación para obtener token Bearer.", size=12),
                ft.Text("• GET  /api/v1/auth/me — Perfil y permisos del usuario o API Key.", size=12),
                ft.Text("• GET  /api/v1/productos — Catálogo maestro con filtros y paginado.", size=12),
                ft.Text("• GET  /api/v1/productos/{codigo}/stock — Consulta de existencia específica.", size=12),
                ft.Text("• GET  /api/v1/inventario/stock — Balance global de inventario.", size=12),
                ft.Text("• POST /api/v1/despacho/pedidos — Carga y registro de remitos / bultos.", size=12),
                ft.Divider(),
                ft.Text("Ejemplo de encabezados HTTP requeridos:", weight=ft.FontWeight.BOLD, size=11),
                ft.Text("X-API-Key: sk_live_...\no\nAuthorization: Bearer <token_de_sesion>", font_family="monospace", size=11, color=ft.Colors.LIGHT_BLUE_300),
            ],
            spacing=6,
        ),
        padding=12,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, texto_color)),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.04, texto_color),
    )

    vista_docs = ft.Column(
        [
            tarjeta_red,
            tarjeta_endpoints,
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        height=320,
    )

    # --- PESTAÑA 3: SESIONES ACTIVAS ---
    lista_sesiones = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=260)
    total_sesiones_txt = ft.Text("0 sesiones activas", size=12, color=SECUNDARIO)

    def refrescar_lista_sesiones() -> None:
        try:
            sesiones = user_store.list_api_sessions(max_records=100)
        except Exception as exc:
            lista_sesiones.controls = [ft.Text(f"Error al cargar sesiones: {exc}", color=ft.Colors.RED_400)]
            interfaz.page.update()
            return

        total_sesiones_txt.value = f"{len(sesiones)} sesión(es) persistida(s)"
        if not sesiones:
            lista_sesiones.controls = [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.DEVICES_OTHER, size=36, color=SECUNDARIO),
                            ft.Text("No hay sesiones de API activas registradas.", size=13, color=SECUNDARIO),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=20,
                )
            ]
            interfaz.page.update()
            return

        items = []
        for s in sesiones:
            th = s.get("token_hash", "")
            u_nom = s.get("username", "desconocido")
            nom = s.get("nombre", "") or u_nom
            rol_s = s.get("role", "operador")
            c_at = _formatear_timestamp(s.get("created_at"))
            l_act = _formatear_timestamp(s.get("last_active"))

            def hacer_revocar_sesion(h: str = th):
                return lambda _e: ejecutar_revocar_sesion(h)

            tarjeta = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.LAPTOP_CHROMEBOOK, color=ft.Colors.CYAN_400, size=22),
                        ft.Column(
                            [
                                ft.Row([ft.Text(f"{nom} (@{u_nom})", weight=ft.FontWeight.BOLD, size=13), ft.Text(f"[{rol_s.upper()}]", size=11, color=ft.Colors.BLUE_200)], spacing=6),
                                ft.Text(f"Token: {th[:12]}... | Creada: {c_at} | Última actividad: {l_act}", size=11, color=SECUNDARIO),
                            ],
                            expand=True,
                            spacing=2,
                        ),
                        ft.Button(
                            "Cerrar sesión",
                            icon=ft.Icons.LOGOUT,
                            style=ft.ButtonStyle(color=ft.Colors.RED_400),
                            on_click=hacer_revocar_sesion(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.Padding.all(8),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, texto_color)),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.03, texto_color),
            )
            items.append(tarjeta)

        lista_sesiones.controls = items
        interfaz.page.update()

    def ejecutar_revocar_sesion(th: str) -> None:
        try:
            ok = user_store.revoke_api_session(th)
            if ok:
                interfaz.notificar("🔒 Sesión revocada con éxito.")
                refrescar_lista_sesiones()
            else:
                interfaz.notificar("❌ No se pudo revocar la sesión.")
        except Exception as exc:
            interfaz.notificar(f"❌ Error al revocar sesión: {exc}")

    def ejecutar_limpiar_expiradas(_e: ft.Event) -> None:
        try:
            cant = user_store.cleanup_expired_api_sessions(24 * 3600)
            interfaz.notificar(f"🧹 Se eliminaron {cant} sesiones inactivas expiradas.")
            refrescar_lista_sesiones()
        except Exception as exc:
            interfaz.notificar(f"❌ Error al limpiar sesiones: {exc}")

    def ejecutar_cerrar_todas(_e: ft.Event) -> None:
        try:
            cant = user_store.revoke_all_sessions()
            interfaz.notificar(f"⚠️ Se cerraron todas las {cant} sesiones activas.")
            refrescar_lista_sesiones()
        except Exception as exc:
            interfaz.notificar(f"❌ Error: {exc}")

    vista_sesiones = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Sesiones de usuarios y terminales autenticados mediante API / Web móvil.", size=12, color=SECUNDARIO, expand=True),
                    ft.Button("Limpiar Expiradas", icon=ft.Icons.CLEANING_SERVICES, on_click=ejecutar_limpiar_expiradas),
                    ft.Button("Cerrar Todas", icon=ft.Icons.LOGOUT, style=ft.ButtonStyle(color=ft.Colors.RED_400), on_click=ejecutar_cerrar_todas),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Divider(),
            ft.Row([ft.Text("Sesiones Activas", weight=ft.FontWeight.BOLD, size=13), total_sesiones_txt], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            lista_sesiones,
        ],
        spacing=8,
    )

    # --- NAVEGACIÓN POR BOTONES TABS ---
    btn_tab_keys = ft.Button("Claves de API (Keys)", icon=ft.Icons.VPN_KEY)
    btn_tab_docs = ft.Button("Documentación y Estado", icon=ft.Icons.CODE)
    btn_tab_sesiones = ft.Button("Sesiones Conectadas", icon=ft.Icons.DEVICES)

    def cambiar_tab(indice: int) -> None:
        vista_keys.visible = (indice == 0)
        vista_docs.visible = (indice == 1)
        vista_sesiones.visible = (indice == 2)

        btn_tab_keys.bgcolor = bg_activo if indice == 0 else bg_inactivo
        btn_tab_keys.color = ft.Colors.WHITE if indice == 0 else texto_color

        btn_tab_docs.bgcolor = bg_activo if indice == 1 else bg_inactivo
        btn_tab_docs.color = ft.Colors.WHITE if indice == 1 else texto_color

        btn_tab_sesiones.bgcolor = bg_activo if indice == 2 else bg_inactivo
        btn_tab_sesiones.color = ft.Colors.WHITE if indice == 2 else texto_color

        if indice == 0:
            refrescar_lista_claves()
        elif indice == 2:
            refrescar_lista_sesiones()
        interfaz.page.update()

    btn_tab_keys.on_click = lambda _e: cambiar_tab(0)
    btn_tab_docs.on_click = lambda _e: cambiar_tab(1)
    btn_tab_sesiones.on_click = lambda _e: cambiar_tab(2)

    # Modal Principal
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.API, color=ROJO, size=24),
                ft.Text("API REST y Servicios de Integración", weight=ft.FontWeight.BOLD, size=16),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=720,
            content=ft.Column(
                [
                    ft.Row([btn_tab_keys, btn_tab_docs, btn_tab_sesiones], spacing=8),
                    ft.Divider(),
                    vista_keys,
                    vista_docs,
                    vista_sesiones,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())
        ],
    )

    interfaz.page.show_dialog(dialogo)
    cambiar_tab(tab_inicial)


def mostrar_gestion_api_keys(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Acceso directo a la pestaña de Gestión de Claves API."""
    mostrar_dialogo_api_master(interfaz, tab_inicial=0)


def mostrar_estado_api(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Acceso directo a la pestaña de Estado y Documentación API."""
    mostrar_dialogo_api_master(interfaz, tab_inicial=1)


def mostrar_sesiones_api(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Acceso directo a la pestaña de Sesiones API Activas."""
    mostrar_dialogo_api_master(interfaz, tab_inicial=2)
