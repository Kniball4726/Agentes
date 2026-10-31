"""Diálogo modal para generación y restauración de copias de seguridad (.ZIP)."""
from pathlib import Path
from typing import Any
import flet as ft
from ...backup_manager import (
    crear_backup_sistema,
    guardar_config_backup,
    listar_backups_disponibles,
    obtener_config_backup,
    restaurar_backup_sistema,
)
from ...paths import application_root
from ..theme import ROJO


def mostrar_dialogo_backup(interfaz: Any) -> None:
    """Abre el diálogo modal para crear y restaurar copias de seguridad del sistema."""
    if not interfaz.exigir_roles("administrador", "master"):
        return

    es_master = bool(interfaz.usuario_actual and interfaz.usuario_actual.role == "master")
    cfg_bk = obtener_config_backup()
    input_carpeta_ext = ft.TextField(
        label="Carpeta secundaria / externa de backup (opcional, ej: D:\\Backups_Deposito)",
        value=str(cfg_bk.get("carpeta_externa", "") or ""),
        dense=True,
        expand=True,
        prefix_icon=ft.Icons.FOLDER_SPECIAL,
    )
    msg_bk = ft.Text("", size=11, color=interfaz.secundario)

    backups_disp = listar_backups_disponibles()
    selector_restore = ft.Dropdown(
        label="Seleccionar respaldo .ZIP para restaurar",
        options=[ft.DropdownOption(key=str(p), text=p.name) for p in backups_disp],
        value=str(backups_disp[0]) if backups_disp else None,
        expand=True,
        dense=True,
    )

    def probar_y_guardar_cfg_ext(_ev: ft.Event) -> None:
        if not es_master:
            interfaz.notificar("Solo el rol Master puede modificar la ruta de respaldo externo.")
            return
        val = (input_carpeta_ext.value or "").strip()
        if not val:
            guardar_config_backup("")
            msg_bk.value = "ℹ️ Carpeta secundaria desactivada (respaldos solo en data/backups)."
            msg_bk.color = interfaz.secundario
            if interfaz.page:
                interfaz.page.update()
            return
        try:
            p = Path(val)
            p.mkdir(parents=True, exist_ok=True)
            test_file = p / "_test_perm.tmp"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            guardar_config_backup(val)
            msg_bk.value = f"✅ Espejo verificado con éxito en: {val}"
            msg_bk.color = ft.Colors.GREEN_400
            interfaz.reproducir_sonido("exito")
        except Exception as ex_e:
            msg_bk.value = f"❌ Error de acceso a carpeta espejo: {ex_e}"
            msg_bk.color = ft.Colors.RED_400
            interfaz.reproducir_sonido("error")
        if interfaz.page:
            interfaz.page.update()

    def ejecutar_backup(_ev: ft.Event) -> None:
        if es_master:
            guardar_config_backup(input_carpeta_ext.value or "")
        interfaz.page.pop_dialog()
        try:
            ruta_zip = crear_backup_sistema(
                ruta_excel_base=interfaz.menu.ruta_excel_base,
                usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema",
            )
            interfaz.order_store.registrar_auditoria(
                usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema",
                accion="BACKUP_MANUAL",
                detalle=f"Respaldo manual completo generado: {ruta_zip.name}",
            )
            interfaz.reproducir_sonido("exito")
            interfaz.notificar(f"Copia de seguridad generada con éxito:\n{ruta_zip.name}")
            interfaz.abrir_carpeta_informe(ruta_zip)
        except Exception as err:
            interfaz.notificar(f"Error al generar copia de seguridad:\n{err}")

    async def subir_zip_restore(_ev: ft.Event) -> None:
        if not es_master:
            interfaz.notificar("Solo el rol Master tiene autorización para restaurar copias de seguridad.")
            return
        carpeta_bks = application_root() / "data" / "backups"
        subidos = await interfaz.subir_archivos_desde_pc(
            carpeta_destino=carpeta_bks,
            extensiones=["zip"],
            titulo="Seleccionar archivo .ZIP de Backup para restaurar",
        )
        if subidos:
            nuevos = listar_backups_disponibles()
            selector_restore.options = [ft.DropdownOption(key=str(p), text=p.name) for p in nuevos]
            selector_restore.value = str(subidos[0])
            msg_bk.value = f"Archivo cargado: {subidos[0].name}"
            interfaz.page.update()

    def confirmar_restaurar_zip(_ev: ft.Event) -> None:
        if not es_master:
            interfaz.notificar("Solo el rol Master tiene autorización para restaurar copias de seguridad.")
            return
        if not selector_restore.value:
            msg_bk.value = "Selecciona primero un archivo .ZIP de respaldo."
            msg_bk.color = ft.Colors.RED_400
            interfaz.page.update()
            return
        ruta_elegida = Path(selector_restore.value)
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Admin"
        interfaz.page.pop_dialog()
        ok, detalle_msg, _ = restaurar_backup_sistema(
            ruta_zip=ruta_elegida,
            ruta_excel_base=interfaz.menu.ruta_excel_base,
            usuario=usr,
        )
        if ok:
            try:
                interfaz.order_store.registrar_auditoria(
                    usuario=usr,
                    accion="BACKUP_RESTAURADO",
                    detalle=detalle_msg,
                )
            except Exception:
                pass
            interfaz.actualizar_estado()
            interfaz.notificar(f"✅ {detalle_msg}")
        else:
            interfaz.notificar(f"❌ {detalle_msg}")

    dialogo = ft.AlertDialog(
        title=ft.Row([ft.Icon(ft.Icons.BACKUP, color=ft.Colors.BLUE_600), ft.Text("Copia de Seguridad y Restauración (.ZIP)" if es_master else "Copia de Seguridad del Sistema")]),
        content=ft.Container(
            width=560,
            content=ft.Column(
                [
                    ft.Text("El respaldo completo incluye con verificación de integridad:"),
                    ft.Text("• 3 Bases SQLite: pedidos.sqlite3, productos.sqlite3 y usuarios.sqlite3", size=12),
                    ft.Text("• Configuraciones (SMTP cifrado, notificaciones) y Excel maestro (Productos.xlsx)", size=12),
                    *([
                        ft.Divider(height=8),
                        ft.Row(
                            [
                                input_carpeta_ext,
                                ft.Button(
                                    "Probar y Guardar Espejo",
                                    icon=ft.Icons.CLOUD_SYNC,
                                    tooltip="Verifica permisos y activa el respaldo en espejo hacia red/nube",
                                    on_click=probar_y_guardar_cfg_ext,
                                ),
                            ],
                            spacing=6,
                        ),
                        ft.Divider(height=10),
                        ft.Text("Restaurar el sistema desde un Backup (.ZIP):", weight=ft.FontWeight.BOLD, size=12),
                        ft.Text(
                            "Verifica automáticamente PRAGMA integrity_check en todas las bases SQLite antes de restaurar.",
                            size=11,
                            color=interfaz.secundario,
                        ),
                        ft.Row(
                            [
                                selector_restore,
                                ft.Button("Subir .ZIP", icon=ft.Icons.UPLOAD_FILE, on_click=subir_zip_restore),
                            ],
                            spacing=6,
                        ),
                        ft.Row(
                            [
                                ft.Button(
                                    "Verificar y Restaurar Backup Seleccionado",
                                    icon=ft.Icons.SETTINGS_BACKUP_RESTORE,
                                    on_click=confirmar_restaurar_zip,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                        msg_bk,
                    ] if es_master else [
                        ft.Divider(height=10),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.LOCK, size=15, color=interfaz.secundario),
                                    ft.Text(
                                        "Restauración de bases de datos (.ZIP) y rutas externas restringidas al usuario Master.",
                                        size=11,
                                        color=interfaz.secundario,
                                    ),
                                ],
                                spacing=6,
                            ),
                            padding=ft.Padding.all(8),
                            bgcolor=ft.Colors.with_opacity(0.04, interfaz.texto),
                            border_radius=6,
                        ),
                    ]),
                ],
                tight=True,
                spacing=6,
            ),
        ),
        actions=[
            ft.Button("Generar Nuevo Respaldo Ahora", icon=ft.Icons.SAVE, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=ejecutar_backup),
            interfaz.boton_dialogo("Cerrar", lambda _ev: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)
