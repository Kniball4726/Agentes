"""Diálogos y utilidades para envío y compartición de informes por correo electrónico y WhatsApp."""

from datetime import datetime
from pathlib import Path
from typing import Any
import webbrowser

import flet as ft

from ..theme import ROJO
from ...email_sender import despachar_correo, guardar_config_email, obtener_config_email
from ...paths import application_root
from ...user_store import USER_ROLES


def compartir_correo(interfaz: Any, _evento: ft.Event | None = None, ruta_especifica: Path | None = None) -> None:
    """Abre el diálogo de envío de correo para un archivo específico o el seleccionado."""
    if not interfaz.exigir_roles(*USER_ROLES):
        return
    archivos_init = [ruta_especifica] if ruta_especifica and ruta_especifica.exists() else None
    mostrar_dialogo_enviar_correo(interfaz, archivos_iniciales=archivos_init)


def compartir_whatsapp(interfaz: Any, _evento: ft.Event | None = None, ruta_especifica: Path | None = None) -> None:
    """Abre la carpeta del informe y redirige a WhatsApp Web."""
    if not interfaz.exigir_roles(*USER_ROLES):
        return
    ruta = ruta_especifica or interfaz.ruta_informe()
    if ruta is None:
        return
    try:
        interfaz.abrir_carpeta_informe(ruta)
        if not webbrowser.open("https://web.whatsapp.com/"):
            raise RuntimeError("No se pudo abrir WhatsApp Web.")
    except (OSError, RuntimeError) as error:
        interfaz.notificar(f"No se pudo abrir WhatsApp o el archivo:\n{error}")


def enviar_correo_cierre(
    interfaz: Any,
    destinatarios: str,
    cierre_id: int,
    archivo_pdf: Path | None,
    archivo_excel: Path | None,
    resumen_pedidos: str,
    usuario: str,
    archivo_hoja_ruta: Path | None = None,
    alerta_stock: str = "",
) -> None:
    """Envía automáticamente el informe y hoja de ruta tras registrar un cierre de jornada."""
    dest_limpio = destinatarios.strip()
    if not dest_limpio:
        return
    from ...flet_gui import guardar_correo_cierre
    guardar_correo_cierre(dest_limpio)
    fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    asunto_txt = f"Cierre de Jornada #{cierre_id} - {fecha_str} ({resumen_pedidos})"
    lineas_cuerpo = [
        "Estimados,",
        "",
        f"Se ha completado el Cierre de Jornada #{cierre_id} en el sistema de depósito.",
        f"• Fecha y Hora: {fecha_str}",
        f"• Responsable: {usuario}",
        f"• Resumen consolidado: {resumen_pedidos}",
        "",
        "Archivos oficiales adjuntos generados:",
    ]
    adjuntos_validos: list[Path] = []
    for arch, desc in [
        (archivo_pdf, "PDF Cierre de Descuentos"),
        (archivo_excel, "Excel Descuentos"),
        (archivo_hoja_ruta, "Manifiesto / Hoja de Ruta de Despacho"),
    ]:
        if arch and arch.exists():
            lineas_cuerpo.append(f"• {desc}: {arch.name}")
            adjuntos_validos.append(arch)

    if alerta_stock:
        lineas_cuerpo.append("\n⚠️ ALERTAS DE INVENTARIO POST-CIERRE:")
        lineas_cuerpo.append(alerta_stock)
    lineas_cuerpo.append("\nLos archivos se encuentran guardados y respaldados en el servidor.")

    cuerpo_txt = "\n".join(lineas_cuerpo)
    dest_lista = [d.strip() for d in dest_limpio.replace(";", ",").split(",") if d.strip()]

    ok, msg = despachar_correo(
        destinatarios=dest_lista,
        asunto=asunto_txt,
        cuerpo=cuerpo_txt,
        adjuntos=adjuntos_validos,
    )
    if ok:
        interfaz.notificar(f"✅ {msg}")
    else:
        interfaz.notificar(f"⚠️ {msg}")


def mostrar_dialogo_compartir_cierre(
    interfaz: Any,
    cierre_id: int,
    archivo_pdf: Path | None,
    archivo_excel: Path | None,
    resumen_pedidos: str,
    usuario: str,
    archivo_hoja_ruta: Path | None = None,
) -> None:
    """Prepara el diálogo de correo con los archivos del cierre de jornada precargados."""
    fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    asunto = f"Cierre de Jornada #{cierre_id} - {fecha_str} ({resumen_pedidos})"
    lineas_cuerpo = [
        "Estimados,",
        "",
        f"Se ha completado el Cierre de Jornada #{cierre_id} en el sistema de depósito.",
        f"• Fecha y Hora: {fecha_str}",
        f"• Responsable: {usuario}",
        f"• Resumen consolidado: {resumen_pedidos}",
        "",
        "Archivos adjuntos para control y archivo contable.",
    ]
    archivos = [p for p in [archivo_pdf, archivo_excel, archivo_hoja_ruta] if p and p.exists()]
    mostrar_dialogo_enviar_correo(
        interfaz,
        archivos_iniciales=archivos,
        asunto_inicial=asunto,
        cuerpo_inicial="\n".join(lineas_cuerpo),
        titulo_dialogo=f"Enviar Cierre #{cierre_id} por Correo",
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

    from ...flet_gui import guardar_correo_cierre, obtener_correo_cierre_guardado

    adjuntos_lista: list[Path] = []
    if archivos_iniciales:
        for p in archivos_iniciales:
            if p and p.exists() and p not in adjuntos_lista:
                adjuntos_lista.append(p)
    elif interfaz.informe_seleccionado and interfaz.informe_seleccionado.exists():
        adjuntos_lista.append(interfaz.informe_seleccionado)
    elif interfaz.informes:
        adjuntos_lista.append(interfaz.informes[0])

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

    if not asunto_inicial:
        if adjuntos_lista:
            primero = adjuntos_lista[0].name
            asunto_inicial = (
                f"Pedido a Fábrica: {primero}"
                if primero.startswith("Pedido_Fabrica")
                else f"Informe de Depósito: {primero}"
            )
        else:
            asunto_inicial = f"Informe de Depósito - {datetime.now().strftime('%d/%m/%Y')}"

    asunto_input = ft.TextField(
        label="Asunto",
        value=asunto_inicial,
        prefix_icon=ft.Icons.SUBJECT,
        expand=True,
        dense=True,
    )

    if not cuerpo_inicial:
        lineas = [
            "Estimados,",
            "",
            "Adjunto los documentos e informes solicitados del sistema de depósito.",
        ]
        usuario_str = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
        lineas.extend(["", f"Saludos cordiales,\n{usuario_str}"])
        cuerpo_inicial = "\n".join(lineas)

    cuerpo_input = ft.TextField(
        label="Mensaje",
        value=cuerpo_inicial,
        multiline=True,
        min_lines=3,
        max_lines=6,
        dense=True,
    )

    msg_error = ft.Text("", size=11, color=ft.Colors.RED_400)
    contenedor_adjuntos = ft.Column(spacing=4)
    dropdown_informes = ft.Dropdown(
        label="Informes recientes del sistema",
        options=[],
        expand=True,
        dense=True,
    )

    try:
        interfaz.actualizar_listas()
    except Exception:
        pass
    opciones_inf = []
    for inf in interfaz.informes[:25]:
        if inf.exists():
            opciones_inf.append(ft.dropdown.Option(key=str(inf), text=inf.name))
    dropdown_informes.options = opciones_inf
    if opciones_inf:
        dropdown_informes.value = opciones_inf[0].key

    def render_adjuntos() -> None:
        contenedor_adjuntos.controls.clear()
        if not adjuntos_lista:
            contenedor_adjuntos.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.ATTACH_FILE, color=ft.Colors.AMBER_700, size=18),
                            ft.Text(
                                "No hay archivos adjuntos. Selecciona uno abajo o examina tu PC.",
                                size=12,
                                color=ft.Colors.AMBER_900,
                            ),
                        ],
                        spacing=6,
                    ),
                    bgcolor=ft.Colors.AMBER_50,
                    padding=ft.Padding.symmetric(vertical=6, horizontal=8),
                    border_radius=6,
                )
            )
        else:
            for p in adjuntos_lista:
                ext = p.suffix.lower()
                icono = ft.Icons.PICTURE_AS_PDF if ext == ".pdf" else (
                    ft.Icons.TABLE_CHART if ext in (".xlsx", ".xls") else ft.Icons.ATTACH_FILE
                )
                color_ico = ft.Colors.RED_600 if ext == ".pdf" else (
                    ft.Colors.GREEN_700 if ext in (".xlsx", ".xls") else ft.Colors.BLUE_GREY_600
                )
                try:
                    tamano_kb = round(p.stat().st_size / 1024, 1)
                    tamano_txt = f"{tamano_kb} KB"
                except Exception:
                    tamano_txt = ""

                def quitar_archivo(_e: ft.Event, arch_quitar=p) -> None:
                    if arch_quitar in adjuntos_lista:
                        adjuntos_lista.remove(arch_quitar)
                        render_adjuntos()
                        interfaz.page.update()

                contenedor_adjuntos.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(icono, color=color_ico, size=18),
                                ft.Text(p.name, size=12, weight=ft.FontWeight.BOLD, expand=True, no_wrap=True),
                                ft.Text(tamano_txt, size=11, color=ft.Colors.GREY_600),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_size=16,
                                    icon_color=ft.Colors.RED_400,
                                    tooltip="Quitar archivo adjunto",
                                    on_click=quitar_archivo,
                                ),
                            ],
                            spacing=6,
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        bgcolor=ft.Colors.GREY_100,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                        border_radius=6,
                    )
                )

    render_adjuntos()

    def agregar_desde_dropdown(_e: ft.Event) -> None:
        if dropdown_informes.value:
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
                for s in subidos:
                    if s not in adjuntos_lista:
                        adjuntos_lista.append(s)
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

        from ...flet_gui import guardar_correo_cierre
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
        if ok:
            interfaz.notificar(f"✅ {mensaje}")
        else:
            interfaz.notificar(f"⚠️ {mensaje}")

    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.EMAIL, color=ft.Colors.BLUE_400, size=22),
                ft.Text(titulo_dialogo, weight=ft.FontWeight.BOLD, size=16),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=550,
            content=ft.Column(
                [
                    ft.Text("Archivos Adjuntos:", size=12, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                    contenedor_adjuntos,
                    ft.Divider(height=10),
                    ft.Text("Agregar más archivos:", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                    ft.Row(
                        [
                            dropdown_informes,
                            ft.Button("Adjuntar", icon=ft.Icons.ADD, on_click=agregar_desde_dropdown),
                        ],
                        spacing=6,
                    ),
                    ft.Row(
                        [
                            ft.Button(
                                "Examinar en mi PC...",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=examinar_pc,
                            ),
                        ],
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
        actions=[
            ft.IconButton(
                icon=ft.Icons.SETTINGS,
                tooltip="Configurar servidor SMTP (Gmail / Outlook / Servidor propio)",
                on_click=lambda _e: interfaz.mostrar_configuracion_smtp(),
            ),
            ft.Button("Enviar Correo", icon=ft.Icons.SEND, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=enviar),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)
