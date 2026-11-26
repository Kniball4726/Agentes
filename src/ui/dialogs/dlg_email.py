"""Diálogo de composición de correo electrónico y fachada de compartición."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import flet as ft

from ...auth import USER_ROLES
from ...integrations.email_sender import despachar_correo, guardar_config_email, obtener_config_email
from ...paths import application_root
from ..app_config import guardar_correo_cierre, obtener_correo_cierre_guardado
from ..theme import ROJO
from .email_cierre import enviar_correo_cierre, mostrar_dialogo_compartir_cierre
from .whatsapp_share import compartir_whatsapp, compartir_whatsapp_pedido


def compartir_correo(
    interfaz: Any,
    _evento: ft.Event | None = None,
    ruta_especifica: Path | None = None,
) -> None:
    """Abre el diálogo de envío de correo para un archivo específico o el seleccionado."""
    if not interfaz.exigir_roles(*USER_ROLES):
        return
    archivos_init = [ruta_especifica] if ruta_especifica and ruta_especifica.exists() else None
    mostrar_dialogo_enviar_correo(interfaz, archivos_iniciales=archivos_init)


def _recopilar_adjuntos_iniciales(interfaz: Any, archivos_iniciales: list[Path] | None) -> list[Path]:
    adjuntos: list[Path] = []
    if archivos_iniciales:
        for p in archivos_iniciales:
            if p and p.exists() and p not in adjuntos:
                adjuntos.append(p)
    elif interfaz.informe_seleccionado and interfaz.informe_seleccionado.exists():
        adjuntos.append(interfaz.informe_seleccionado)
    elif interfaz.informes:
        adjuntos.append(interfaz.informes[0])
    return adjuntos


def _asunto_por_defecto(adjuntos: list[Path]) -> str:
    if adjuntos:
        primero = adjuntos[0].name
        return (
            f"Pedido a Fábrica: {primero}"
            if primero.startswith("Pedido_Fabrica")
            else f"Informe de Depósito: {primero}"
        )
    return f"Informe de Depósito - {datetime.now().strftime('%d/%m/%Y')}"


def _cuerpo_por_defecto(interfaz: Any) -> str:
    usuario_str = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
    return "\n".join(
        [
            "Estimados,",
            "",
            "Adjunto los documentos e informes solicitados del sistema de depósito.",
            "",
            f"Saludos cordiales,\n{usuario_str}",
        ]
    )


def _construir_tarjeta_adjunto(
    interfaz: Any,
    archivo: Path,
    on_quitar: Callable[[Path], None],
) -> ft.Container:
    ext = archivo.suffix.lower()
    icono = (
        ft.Icons.PICTURE_AS_PDF
        if ext == ".pdf"
        else (ft.Icons.TABLE_CHART if ext in (".xlsx", ".xls") else ft.Icons.ATTACH_FILE)
    )
    color_ico = (
        ft.Colors.RED_600
        if ext == ".pdf"
        else (ft.Colors.GREEN_700 if ext in (".xlsx", ".xls") else ft.Colors.BLUE_GREY_600)
    )
    try:
        tamano_txt = f"{round(archivo.stat().st_size / 1024, 1)} KB"
    except Exception:
        tamano_txt = ""

    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icono, color=color_ico, size=18),
                ft.Text(
                    archivo.name,
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=interfaz.texto,
                    expand=True,
                    no_wrap=True,
                ),
                ft.Text(tamano_txt, size=11, color=interfaz.secundario),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=16,
                    icon_color=ft.Colors.RED_400,
                    tooltip="Quitar archivo adjunto",
                    on_click=lambda _e, arch=archivo: on_quitar(arch),
                ),
            ],
            spacing=6,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.WHITE) if interfaz.modo_oscuro else ft.Colors.GREY_100,
        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
        border_radius=6,
    )


def _construir_placeholder_sin_adjuntos(interfaz: Any) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.ATTACH_FILE, color=ft.Colors.AMBER_700, size=18),
                ft.Text(
                    "No hay archivos adjuntos. Selecciona uno abajo o examina tu PC.",
                    size=12,
                    color=ft.Colors.AMBER_300 if interfaz.modo_oscuro else ft.Colors.AMBER_900,
                ),
            ],
            spacing=6,
        ),
        bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.AMBER_500) if interfaz.modo_oscuro else ft.Colors.AMBER_50,
        padding=ft.Padding.symmetric(vertical=6, horizontal=8),
        border_radius=6,
    )


def mostrar_dialogo_enviar_correo(
    interfaz: Any,
    archivos_iniciales: list[Path] | None = None,
    asunto_inicial: str = "",
    cuerpo_inicial: str = "",
    destinatarios_iniciales: str = "",
    titulo_dialogo: str = "Enviar por Correo",
) -> None:
    """Ventana modal completa para enviar correos con adjuntos múltiples y selección de informes."""
    if not interfaz.exigir_roles(*USER_ROLES):
        return

    adjuntos_lista = _recopilar_adjuntos_iniciales(interfaz, archivos_iniciales)
    cfg_email = obtener_config_email()
    correo_guardado = (
        destinatarios_iniciales
        or obtener_correo_cierre_guardado()
        or cfg_email.get("destinatarios_guardados", "")
    )

    destinatarios_input = ft.TextField(
        label="Destinatarios (separar con comas)",
        value=correo_guardado,
        hint_text="ej: gerencia@empresa.com, compras@empresa.com",
        prefix_icon=ft.Icons.EMAIL,
        expand=True,
        dense=True,
    )
    asunto_input = ft.TextField(
        label="Asunto",
        value=asunto_inicial or _asunto_por_defecto(adjuntos_lista),
        prefix_icon=ft.Icons.SUBJECT,
        expand=True,
        dense=True,
    )
    cuerpo_input = ft.TextField(
        label="Mensaje",
        value=cuerpo_inicial or _cuerpo_por_defecto(interfaz),
        multiline=True,
        min_lines=3,
        max_lines=6,
        dense=True,
    )
    msg_error = ft.Text("", size=11, color=ft.Colors.RED_400)
    contenedor_adjuntos = ft.Column(spacing=4)

    try:
        interfaz.actualizar_listas()
    except Exception:
        pass
    opciones_inf = [
        ft.dropdown.Option(key=str(inf), text=inf.name)
        for inf in interfaz.informes[:25]
        if inf.exists()
    ]
    dropdown_informes = ft.Dropdown(
        label="Informes recientes del sistema",
        options=opciones_inf,
        value=opciones_inf[0].key if opciones_inf else None,
        expand=True,
        dense=True,
    )

    def _quitar_adjunto(arch_quitar: Path) -> None:
        if arch_quitar in adjuntos_lista:
            adjuntos_lista.remove(arch_quitar)
            render_adjuntos()
            interfaz.page.update()

    def render_adjuntos() -> None:
        contenedor_adjuntos.controls.clear()
        if not adjuntos_lista:
            contenedor_adjuntos.controls.append(_construir_placeholder_sin_adjuntos(interfaz))
            return
        for arch in adjuntos_lista:
            contenedor_adjuntos.controls.append(_construir_tarjeta_adjunto(interfaz, arch, _quitar_adjunto))

    render_adjuntos()

    def agregar_desde_dropdown(_e: ft.Event) -> None:
        if not dropdown_informes.value:
            return
        ruta_elegida = Path(dropdown_informes.value)
        if ruta_elegida.exists() and ruta_elegida not in adjuntos_lista:
            adjuntos_lista.append(ruta_elegida)
            render_adjuntos()
            interfaz.page.update()

    async def examinar_pc(_e: ft.Event) -> None:
        try:
            carpeta_adjuntos = application_root() / "data" / "adjuntos_correo"
            subidos = await interfaz.subir_archivos_desde_pc(
                carpeta_destino=carpeta_adjuntos,
                extensiones=["pdf", "xlsx", "xls", "docx", "doc", "zip", "txt", "png", "jpg"],
                titulo="Seleccionar archivo(s) para adjuntar al correo",
            )
            if subidos:
                for subido in subidos:
                    if subido not in adjuntos_lista:
                        adjuntos_lista.append(subido)
                render_adjuntos()
                interfaz.page.update()
        except Exception as err:
            msg_error.value = f"Error al seleccionar archivo: {err}"
            interfaz.page.update()

    def enviar(_e: ft.Event) -> None:
        dest_raw = (destinatarios_input.value or "").strip()
        if not dest_raw:
            msg_error.value = "Por favor ingresa al menos una dirección de correo."
            interfaz.page.update()
            return

        dest_limpios = [d.strip() for d in dest_raw.replace(";", ",").split(",") if d.strip()]
        asunto_final = (asunto_input.value or "").strip() or "Informe de Depósito"
        cuerpo_final = cuerpo_input.value or ""

        rol_actual = getattr(getattr(interfaz, "usuario_actual", None), "role", "")
        if rol_actual in ("operador", "administrador", "master"):
            guardar_correo_cierre(dest_raw)
            cfg = obtener_config_email()
            cfg["destinatarios_guardados"] = dest_raw
            guardar_config_email(cfg)

        interfaz.page.pop_dialog()
        ok, mensaje = despachar_correo(
            destinatarios=dest_limpios,
            asunto=asunto_final,
            cuerpo=cuerpo_final,
            adjuntos=adjuntos_lista,
        )
        interfaz.notificar(f"✅ {mensaje}" if ok else f"⚠️ {mensaje}")

    acciones_correo: list[ft.Control] = []
    if getattr(getattr(interfaz, "usuario_actual", None), "role", "") == "master":
        acciones_correo.append(
            ft.IconButton(
                icon=ft.Icons.SETTINGS,
                tooltip="Configurar servidor SMTP (Gmail / Outlook / Servidor propio)",
                on_click=lambda _e: interfaz.mostrar_configuracion_smtp(),
            )
        )
    acciones_correo.extend(
        [
            ft.Button("Enviar Correo", icon=ft.Icons.SEND, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=enviar),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ]
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.EMAIL, color=ft.Colors.BLUE_400, size=22),
                ft.Text(titulo_dialogo, weight=ft.FontWeight.BOLD, size=16),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=interfaz.ancho_adaptable(550) if hasattr(interfaz, "ancho_adaptable") else 550,
            content=ft.Column(
                [
                    ft.Text("Archivos Adjuntos:", size=12, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                    contenedor_adjuntos,
                    ft.Divider(height=10),
                    ft.Text("Agregar más archivos:", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                    ft.Row(
                        [dropdown_informes, ft.Button("Adjuntar", icon=ft.Icons.ADD, on_click=agregar_desde_dropdown)],
                        spacing=6,
                    ),
                    ft.Row(
                        [ft.Button("Examinar en mi PC...", icon=ft.Icons.FOLDER_OPEN, on_click=examinar_pc)],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                    ft.Divider(height=10),
                    destinatarios_input,
                    asunto_input,
                    cuerpo_input,
                    msg_error,
                ],
                tight=True,
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
        ),
        actions=acciones_correo,
    )
    interfaz.page.show_dialog(dialogo)


__all__ = [
    "compartir_correo",
    "compartir_whatsapp",
    "compartir_whatsapp_pedido",
    "enviar_correo_cierre",
    "mostrar_dialogo_compartir_cierre",
    "mostrar_dialogo_enviar_correo",
]
