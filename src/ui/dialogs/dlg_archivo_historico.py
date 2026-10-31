"""Diálogo de Gestión y Archivado Histórico de Comprobantes para Administrador y Master."""

import os
from pathlib import Path
import sys
from typing import Any

import flet as ft

from ...archive_manager import archivar_comprobantes_antiguos, obtener_estadisticas_almacenamiento
from ...paths import application_root
from ..theme import ROJO


def mostrar_dialogo_archivo_historico(interfaz: Any, _e: ft.Event | None = None) -> None:
    """Ventana para archivar comprobantes antiguos y optimizar el almacenamiento."""
    if not interfaz.exigir_roles("master"):
        return

    texto_pedidos = ft.Text("...", size=13, color=interfaz.texto)
    texto_descontados = ft.Text("...", size=13, color=interfaz.texto)
    texto_historicos = ft.Text("...", size=13, color=interfaz.texto)
    texto_total = ft.Text("...", size=13, weight=ft.FontWeight.BOLD, color=interfaz.texto)
    texto_resultado = ft.Text("", size=12, color=ft.Colors.GREEN_400)

    dd_antiguedad = ft.Dropdown(
        label="Archivar comprobantes con antigüedad mayor a",
        value="30",
        options=[
            ft.dropdown.Option("15", "15 días"),
            ft.dropdown.Option("30", "30 días (Recomendado)"),
            ft.dropdown.Option("60", "60 días"),
            ft.dropdown.Option("90", "90 días (3 meses)"),
            ft.dropdown.Option("180", "180 días (6 meses)"),
            ft.dropdown.Option("365", "365 días (1 año)"),
        ],
        dense=True,
        expand=True,
    )

    def refrescar_estadisticas() -> None:
        stats = obtener_estadisticas_almacenamiento()
        texto_pedidos.value = f"{stats['pedidos_archivos_cant']} archivos ({stats['pedidos_archivos_mb']} MB)"
        texto_descontados.value = f"{stats['descontados_cant']} archivos ({stats['descontados_mb']} MB)"
        texto_historicos.value = f"{stats['historico_cant']} archivos ({stats['historico_mb']} MB)"
        texto_total.value = f"{stats['total_archivos']} archivos ({stats['total_mb']} MB)"
        interfaz.page.update()

    refrescar_estadisticas()

    def ejecutar_archivado(_e: ft.Event | None = None) -> None:
        try:
            dias = int(dd_antiguedad.value or "30")
        except ValueError:
            dias = 30

        res = archivar_comprobantes_antiguos(dias_antiguedad=dias)
        movidos = res["archivos_movidos"]
        mb = res["mb_organizados"]
        carpetas = res["carpetas_organizadas"]

        refrescar_estadisticas()
        if movidos > 0:
            c_str = ", ".join(carpetas[:4])
            texto_resultado.value = (
                f"✅ Se archivaron {movidos} comprobante(s) ({mb} MB) en subcarpetas: {c_str}"
            )
            texto_resultado.color = ft.Colors.GREEN_400
            try:
                if hasattr(interfaz, "order_store") and interfaz.order_store:
                    usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema"
                    interfaz.order_store.registrar_auditoria(
                        usuario=usr,
                        accion="ARCHIVAR_COMPROBANTES",
                        detalle=f"Archivado de {movidos} archivos ({mb} MB) de más de {dias} días hacia historico/",
                    )
            except Exception:
                pass
        else:
            texto_resultado.value = f"ℹ️ No se encontraron comprobantes con más de {dias} días para archivar."
            texto_resultado.color = interfaz.secundario
        interfaz.page.update()

    def abrir_carpeta_historico(_e: ft.Event | None = None) -> None:
        dir_h = application_root() / "data" / "historico"
        dir_h.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(dir_h)
            else:
                import subprocess
                subprocess.run(["xdg-open", str(dir_h)], check=False)
        except Exception as exc:
            interfaz.notificar(f"No se pudo abrir la carpeta: {exc}")

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.AUTO_DELETE, color=ROJO, size=24),
                ft.Text("Archivado y Optimización de Comprobantes", size=17, weight=ft.FontWeight.BOLD),
            ],
            spacing=10,
        ),
        content=ft.Container(
            width=520,
            content=ft.Column(
                [
                    ft.Text(
                        "Organiza comprobantes de remitos y pedidos antiguos en subcarpetas anuales/mensuales "
                        "('data/historico/YYYY/MM/'). Esto aligera las carpetas operativas y agiliza las búsquedas "
                        "manteniendo la capacidad de consulta y reimpresión en todo momento.",
                        size=12,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=14, color=interfaz.borde),
                    ft.Text("ESTADO DE ALMACENAMIENTO DE ARCHIVOS", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                    ft.Row([ft.Text("• Comprobantes de Pedidos:", size=12, color=interfaz.secundario), texto_pedidos], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("• Remitos Descontados:", size=12, color=interfaz.secundario), texto_descontados], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("• Comprobantes Históricos:", size=12, color=interfaz.secundario), texto_historicos], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=10, color=interfaz.borde),
                    ft.Row([ft.Text("Volumen Total:", size=13, weight=ft.FontWeight.BOLD, color=interfaz.texto), texto_total], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=14, color=interfaz.borde),
                    ft.Row([dd_antiguedad]),
                    texto_resultado,
                ],
                spacing=8,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton(
                "📂 Abrir Carpeta Histórica",
                icon=ft.Icons.FOLDER_OPEN,
                on_click=abrir_carpeta_historico,
            ),
            ft.FilledButton(
                "Organizar Ahora",
                icon=ft.Icons.ARCHIVE,
                style=ft.ButtonStyle(bgcolor=ROJO, color=ft.Colors.WHITE),
                on_click=ejecutar_archivado,
            ),
            ft.TextButton("Cerrar", on_click=lambda _e: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    interfaz.page.show_dialog(dialogo)
