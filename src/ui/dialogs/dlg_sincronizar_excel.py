"""Diálogo modal para la sincronización bidireccional entre la base de datos y Productos.xlsx."""

from __future__ import annotations

import logging
from typing import Any
import flet as ft

from ..design import colores_de, confirmar_accion_destructiva, tono_legible

logger = logging.getLogger(__name__)


def mostrar_dialogo_sincronizar_excel(interfaz: Any) -> None:
    """Abre un diálogo interactivo para sincronizar el catálogo SQLite con Productos.xlsx."""
    if not interfaz.exigir_roles("administrador", "master"):
        return

    colores = colores_de(interfaz)
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    ruta_excel = interfaz.menu.ruta_excel_base
    es_qa = "qa" in str(ruta_excel).lower()
    env_label = "QA (Pruebas)" if es_qa else "PRODUCCIÓN"
    env_color = ft.Colors.AMBER_400 if es_qa else ft.Colors.GREEN_400

    lbl_estado = ft.Text("", size=12, weight=ft.FontWeight.W_500)
    prg_barra = ft.ProgressBar(visible=False, color=colores.info)

    def _do_volcado_a_excel() -> None:
        lbl_estado.value = "⏳ Volcando base de datos hacia Productos.xlsx..."
        lbl_estado.color = colores.info
        prg_barra.visible = True
        btn_volcar.disabled = True
        btn_importar.disabled = True
        interfaz.page.update()

        try:
            from ...inventory import StockManager

            sm = StockManager(ruta_excel)
            total = sm.sincronizar_catalogo_completo_excel()
            desactivados = getattr(sm, "_ultimos_desactivados", 0)
            msg = f"✅ Éxito: Se volcaron y sincronizaron {total} productos en '{ruta_excel.name}'."
            if desactivados > 0:
                msg += f" ({desactivados} productos ausentes en Excel quedaron inactivos)."
            lbl_estado.value = msg
            lbl_estado.color = colores.exito
            try:
                order_store = getattr(interfaz, "order_store", None)
                if order_store and hasattr(order_store, "registrar_auditoria"):
                    usr = getattr(getattr(interfaz, "usuario_actual", None), "username", "Admin")
                    order_store.registrar_auditoria(usr, "SINCRONIZAR_A_EXCEL", f"Volcados {total} productos a {ruta_excel.name}")
            except Exception:
                pass
            interfaz.notificar(msg)
        except PermissionError:
            lbl_estado.value = (
                "❌ Error de acceso: 'Productos.xlsx' está abierto en Microsoft Excel. "
                "Ciérralo e intenta nuevamente."
            )
            lbl_estado.color = colores.error
        except Exception as exc:
            lbl_estado.value = f"❌ Error al sincronizar: {exc}"
            lbl_estado.color = colores.error
            logger.error("Error en sincronización a Excel: %s", exc, exc_info=True)
        finally:
            prg_barra.visible = False
            btn_volcar.disabled = False
            btn_importar.disabled = False
            interfaz.page.update()

    def ejecutar_volcado_a_excel(_e: ft.ControlEvent) -> None:
        confirmar_accion_destructiva(
            interfaz,
            "Confirmar Volcado a Excel",
            f"¿Confirmas sobrescribir '{ruta_excel.name}' con el catálogo y stock actual de SQLite?",
            _do_volcado_a_excel,
            texto_confirmar="Sí, Volcar a Excel",
            roles_permitidos=("administrador", "master"),
        )

    def _do_importacion_desde_excel() -> None:
        lbl_estado.value = "⏳ Leyendo e importando catálogo desde Productos.xlsx..."
        lbl_estado.color = colores.advertencia
        prg_barra.visible = True
        btn_volcar.disabled = True
        btn_importar.disabled = True
        interfaz.page.update()

        try:
            from ...inventory import StockManager

            sm = StockManager(ruta_excel)
            res = sm.importar_catalogo_desde_excel()
            total = getattr(res, "importados", res.get("importados", int(res)) if isinstance(res, dict) else int(res))
            desactivados = getattr(res, "desactivados", res.get("desactivados", 0) if isinstance(res, dict) else 0)
            msg = f"✅ Éxito: Se importaron y sincronizaron {total} productos desde '{ruta_excel.name}' a SQLite."
            if desactivados > 0:
                msg += f" ({desactivados} productos no presentes en Excel se marcaron como inactivos)."
            lbl_estado.value = msg
            lbl_estado.color = colores.exito
            try:
                order_store = getattr(interfaz, "order_store", None)
                if order_store and hasattr(order_store, "registrar_auditoria"):
                    usr = getattr(getattr(interfaz, "usuario_actual", None), "username", "Admin")
                    order_store.registrar_auditoria(usr, "IMPORTAR_DESDE_EXCEL", f"Importados {total} productos desde {ruta_excel.name}")
            except Exception:
                pass
            interfaz.notificar(msg)
            if hasattr(interfaz, "sincronizar_sesiones"):
                interfaz.sincronizar_sesiones()
        except PermissionError:
            lbl_estado.value = (
                "❌ Error de acceso: 'Productos.xlsx' está abierto en Microsoft Excel. "
                "Ciérralo e intenta nuevamente."
            )
            lbl_estado.color = colores.error
        except Exception as exc:
            lbl_estado.value = f"❌ Error al importar desde Excel: {exc}"
            lbl_estado.color = colores.error
            logger.error("Error en importación desde Excel: %s", exc, exc_info=True)
        finally:
            prg_barra.visible = False
            btn_volcar.disabled = False
            btn_importar.disabled = False
            interfaz.page.update()

    def ejecutar_importacion_desde_excel(_e: ft.ControlEvent) -> None:
        confirmar_accion_destructiva(
            interfaz,
            "Confirmar Importación desde Excel",
            f"¿Confirmas importar y sobrescribir el stock en SQLite con los valores de '{ruta_excel.name}'?\n"
            "Los productos que no figuren en la planilla quedarán inactivos.",
            _do_importacion_desde_excel,
            texto_confirmar="Sí, Importar a SQLite",
            roles_permitidos=("administrador", "master"),
        )

    btn_volcar = ft.FilledButton(
        "Volcar Catálogo a Excel",
        icon=ft.Icons.UPLOAD_FILE,
        on_click=ejecutar_volcado_a_excel,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_700,
            color=ft.Colors.WHITE,
        ),
    )

    btn_importar = ft.OutlinedButton(
        "Importar Cambios de Excel a Sistema",
        icon=ft.Icons.FILE_DOWNLOAD,
        on_click=ejecutar_importacion_desde_excel,
        style=ft.ButtonStyle(
            color=tono_legible("AMBER", es_oscuro),
        ),
    )

    ancho_dlg = interfaz.ancho_adaptable(580) if hasattr(interfaz, "ancho_adaptable") else 580
    contenido = ft.Container(
        width=ancho_dlg,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.FOLDER_OPEN, size=18, color=colores.secundario),
                        ft.Text(f"Ruta activa: {ruta_excel}", size=11, color=colores.secundario, selectable=True),
                    ],
                    spacing=6,
                ),
                ft.Row(
                    [
                        ft.Text("Entorno activo:", size=12, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=ft.Text(env_label, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                            bgcolor=env_color,
                            border_radius=4,
                            padding=ft.Padding(8, 2, 8, 2),
                        ),
                    ],
                    spacing=8,
                ),
                ft.Container(
                    bgcolor=ft.Colors.AMBER_900 if interfaz.modo_oscuro else ft.Colors.AMBER_50,
                    border=ft.Border.all(1, ft.Colors.AMBER_600),
                    border_radius=8,
                    padding=10,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_400, size=24),
                            ft.Column(
                                [
                                    ft.Text(
                                        "Asegúrate de que 'Productos.xlsx' esté cerrado",
                                        weight=ft.FontWeight.BOLD,
                                        size=12,
                                        color=ft.Colors.AMBER_300 if interfaz.modo_oscuro else ft.Colors.AMBER_900,
                                    ),
                                    ft.Text(
                                        "Si el archivo está abierto en Microsoft Excel, Windows bloqueará la escritura con un error de permisos.",
                                        size=11,
                                        color=ft.Colors.AMBER_200 if interfaz.modo_oscuro else ft.Colors.AMBER_800,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                ft.Divider(height=1),
                ft.Text("Opciones de sincronización:", weight=ft.FontWeight.BOLD, size=13),
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.CLOUD_UPLOAD, color=ft.Colors.BLUE_400),
                                        ft.Text("1. Volcar a Excel (SQLite ➔ Excel)", weight=ft.FontWeight.BOLD, size=13),
                                    ],
                                    spacing=8,
                                ),
                                ft.Text(
                                    "Sobrescribe atómicamente la plantilla Productos.xlsx con el catálogo activo y stock actual. Los productos que no estén en la planilla quedarán inactivos en la base de datos.",
                                    size=11,
                                    color=colores.secundario,
                                ),
                                ft.Row([btn_volcar], alignment=ft.MainAxisAlignment.END),
                            ],
                            spacing=6,
                        ),
                    ),
                ),
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(ft.Icons.CLOUD_DOWNLOAD, color=colores.advertencia),
                                        ft.Text("2. Importar desde Excel (Excel ➔ SQLite)", weight=ft.FontWeight.BOLD, size=13),
                                    ],
                                    spacing=8,
                                ),
                                ft.Text(
                                    "Lee Productos.xlsx e incorpora o actualiza nombres y stock en SQLite. Cualquier producto en la base de datos que ya no figure en la planilla se marcará automáticamente como inactivo.",
                                    size=11,
                                    color=colores.secundario,
                                ),
                                ft.Row([btn_importar], alignment=ft.MainAxisAlignment.END),
                            ],
                            spacing=6,
                        ),
                    ),
                ),
                prg_barra,
                lbl_estado,
            ],
            spacing=10,
            tight=True,
        ),
    )

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.SYNC, color=ft.Colors.BLUE_400),
                ft.Text("Sincronización con Productos.xlsx", weight=ft.FontWeight.BOLD),
            ],
            spacing=10,
        ),
        content=contenido,
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dlg)
