"""Diálogo modal para el Centro Unificado de Reportes de StockAgent."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Any

import flet as ft

from ...paths import application_root
from ..theme import ROJO
from .reportes_config import (
    DESCRIPCIONES_REPORTE as _DESCRIPCIONES_REPORTE,
    OPCIONES_REPORTE,
    REPORTES_CON_PERIODO,
    VISIBILIDAD_CAMPOS_REPORTE,
    ejecutar_generacion_reporte,
    opciones_dropdown,
    resolver_rango_fechas as _resolver_rango_fechas,
)

logger = logging.getLogger(__name__)


def _cargar_opciones_transporte() -> list[ft.DropdownOption]:
    opciones = [ft.DropdownOption("TODOS", "Todos los transportes")]
    try:
        from ...orders import LOGISTICA_OPCIONES

        for log in LOGISTICA_OPCIONES:
            opciones.append(ft.DropdownOption(log, log))
    except Exception:
        pass
    return opciones


def _crear_controles_parametros(interfaz: Any, hoy_str: str) -> dict[str, Any]:
    """Construye los controles de entrada parametrizables para los distintos tipos de reporte."""
    tipo_reporte = ft.Dropdown(
        label="Seleccionar Tipo de Reporte",
        value="stock_critico",
        options=opciones_dropdown(OPCIONES_REPORTE),
        dense=True,
        expand=True,
    )
    descripcion_reporte = ft.Text(
        _DESCRIPCIONES_REPORTE["stock_critico"],
        size=12,
        color=interfaz.secundario,
    )
    transporte_filtro = ft.Dropdown(
        label="Filtrar por Transporte / Logística (Opcional)",
        value="TODOS",
        options=_cargar_opciones_transporte(),
        dense=True,
        visible=False,
    )
    modo_movimiento = ft.Dropdown(
        label="Vista / Contenido del Reporte",
        value="ambos",
        options=opciones_dropdown(
            (
                ("ambos", "Consolidado (Salidas + Ingresos)"),
                ("cierre_admin", "Consolidado Administrador (Suma Total)"),
                ("salidas", "Sólo Salidas de Stock"),
                ("ingresos", "Sólo Ingresos de Stock"),
            )
        ),
        dense=True,
        visible=False,
    )
    orden_movimientos = ft.Dropdown(
        label="Ordenamiento",
        value="catalog",
        options=opciones_dropdown(
            (
                ("catalog", "Orden de Catálogo"),
                ("ubicacion", "Por Ubicación"),
                ("volume", "Por Mayor Volumen"),
                ("alpha", "Alfabético"),
            )
        ),
        dense=True,
        visible=False,
    )
    preset_periodo = ft.Dropdown(
        label="Período",
        value="hoy",
        options=opciones_dropdown(
            (
                ("hoy", "Jornada de Hoy"),
                ("ayer", "Ayer"),
                ("7d", "Últimos 7 días"),
                ("30d", "Últimos 30 días"),
                ("personalizado", "Rango personalizado (AAAA-MM-DD)"),
            )
        ),
        dense=True,
        visible=False,
    )
    fecha_desde_input = ft.TextField(label="Desde (AAAA-MM-DD)", value=hoy_str, dense=True, expand=True)
    fecha_hasta_input = ft.TextField(label="Hasta (AAAA-MM-DD)", value=hoy_str, dense=True, expand=True)
    fila_fechas_custom = ft.Row([fecha_desde_input, fecha_hasta_input], spacing=8, visible=False)
    sku_kardex_input = ft.TextField(
        label="Código SKU o nombre del producto",
        hint_text="ej: UT-2156 o Taladro",
        dense=True,
        visible=False,
    )
    chk_conteo_ciego = ft.Checkbox(
        label="Conteo ciego (ocultar stock actual del sistema para control real)",
        value=True,
        visible=False,
    )
    filtro_ubicacion_input = ft.TextField(
        label="Filtrar por pasillo / ubicación (opcional)",
        hint_text="ej: A-01",
        dense=True,
        visible=False,
    )
    ventana_rotacion = ft.Dropdown(
        label="Ventana de análisis",
        value="30",
        options=opciones_dropdown(
            (
                ("7", "Últimos 7 días"),
                ("15", "Últimos 15 días"),
                ("30", "Últimos 30 días"),
                ("60", "Últimos 60 días"),
                ("90", "Últimos 90 días"),
            )
        ),
        dense=True,
        visible=False,
    )
    return {
        "tipo_reporte": tipo_reporte,
        "descripcion_reporte": descripcion_reporte,
        "transporte_filtro": transporte_filtro,
        "modo_movimiento": modo_movimiento,
        "orden_movimientos": orden_movimientos,
        "preset_periodo": preset_periodo,
        "fecha_desde_input": fecha_desde_input,
        "fecha_hasta_input": fecha_hasta_input,
        "fila_fechas_custom": fila_fechas_custom,
        "sku_kardex_input": sku_kardex_input,
        "chk_conteo_ciego": chk_conteo_ciego,
        "filtro_ubicacion_input": filtro_ubicacion_input,
        "ventana_rotacion": ventana_rotacion,
    }


def _construir_encabezado_reportes(interfaz: Any) -> ft.Row:
    return ft.Row(
        [
            ft.Icon(ft.Icons.ASSESSMENT, size=28, color=ROJO),
            ft.Column(
                [
                    ft.Text("Centro Unificado de Reportes", size=18, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ft.Text(
                        "Genera informes operativos, de stock, movimientos y auditoría para imprimir o exportar.",
                        size=11,
                        color=interfaz.secundario,
                    ),
                ],
                spacing=2,
                expand=True,
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def mostrar_centro_reportes(interfaz: Any) -> None:
    """Abre la ventana modal del Centro Unificado de Reportes."""
    if not interfaz.usuario_actual:
        interfaz.notificar("Debes iniciar sesión para acceder a los reportes.")
        return

    usuario_nombre = (
        getattr(interfaz.usuario_actual, "display_name", None)
        or getattr(interfaz.usuario_actual, "username", "Operador")
    )
    carpeta_informes = Path(application_root()) / "data" / "informes"
    carpeta_informes.mkdir(parents=True, exist_ok=True)
    hoy_str = datetime.now().strftime("%Y-%m-%d")

    ctrls = _crear_controles_parametros(interfaz, hoy_str)
    tipo_reporte = ctrls["tipo_reporte"]
    preset_periodo = ctrls["preset_periodo"]
    fila_fechas_custom = ctrls["fila_fechas_custom"]

    def _actualizar_visibilidad_fechas(_e: ft.Event | None = None) -> None:
        usa_fechas = tipo_reporte.value in REPORTES_CON_PERIODO
        preset_periodo.visible = usa_fechas
        fila_fechas_custom.visible = usa_fechas and preset_periodo.value == "personalizado"
        if interfaz.page:
            interfaz.page.update()

    def al_cambiar_tipo(_e: ft.Event | None = None) -> None:
        sel = str(tipo_reporte.value or "stock_critico")
        ctrls["descripcion_reporte"].value = _DESCRIPCIONES_REPORTE.get(sel, "")
        visibles = set(VISIBILIDAD_CAMPOS_REPORTE.get(sel, ()))
        for clave in (
            "transporte_filtro",
            "modo_movimiento",
            "orden_movimientos",
            "sku_kardex_input",
            "chk_conteo_ciego",
            "filtro_ubicacion_input",
            "ventana_rotacion",
        ):
            ctrls[clave].visible = clave in visibles
        _actualizar_visibilidad_fechas()

    tipo_reporte.on_select = al_cambiar_tipo
    preset_periodo.on_select = _actualizar_visibilidad_fechas

    estado_indicador = ft.Text("", size=12, color=ft.Colors.GREEN_400, visible=False)
    progreso = ft.ProgressBar(visible=False, height=4)

    def ejecutar_generacion(formato: str) -> None:
        progreso.visible = True
        estado_indicador.visible = True
        estado_indicador.value = f"Generando reporte en formato {formato.upper()}..."
        estado_indicador.color = interfaz.secundario
        if interfaz.page:
            interfaz.page.update()

        try:
            preset_val = str(preset_periodo.value or "hoy")
            f_desde, f_hasta = _resolver_rango_fechas(
                preset_val,
                str(ctrls["fecha_desde_input"].value or ""),
                str(ctrls["fecha_hasta_input"].value or ""),
            )
            params = {
                "f_desde": f_desde,
                "f_hasta": f_hasta,
                "preset": preset_val,
                "orden": str(ctrls["orden_movimientos"].value or "catalog"),
                "modo": str(ctrls["modo_movimiento"].value or "ambos"),
                "conteo_ciego": bool(ctrls["chk_conteo_ciego"].value),
                "filtro_ubicacion": str(ctrls["filtro_ubicacion_input"].value or ""),
                "sku_kardex": str(ctrls["sku_kardex_input"].value or ""),
                "dias_rotacion": int(ctrls["ventana_rotacion"].value or 30),
                "transporte": ctrls["transporte_filtro"].value,
            }
            ruta_generada = ejecutar_generacion_reporte(
                str(tipo_reporte.value or ""),
                interfaz=interfaz,
                carpeta=carpeta_informes,
                formato=formato,
                usuario=usuario_nombre,
                params=params,
            )

            progreso.visible = False
            if ruta_generada and ruta_generada.exists():
                estado_indicador.value = f"Reporte generado con éxito: {ruta_generada.name}"
                estado_indicador.color = ft.Colors.GREEN_400
                if interfaz.page:
                    interfaz.page.update()
                interfaz.abrir_informe(ruta_especifica=ruta_generada)
            else:
                estado_indicador.value = "No se pudo generar el reporte solicitado."
                estado_indicador.color = ft.Colors.RED_400
                if interfaz.page:
                    interfaz.page.update()
        except Exception as exc:
            logger.error("Error al generar reporte: %s", exc, exc_info=True)
            progreso.visible = False
            estado_indicador.value = f"Error al generar reporte: {exc}"
            estado_indicador.color = ft.Colors.RED_400
            if interfaz.page:
                interfaz.page.update()

    btn_pdf = ft.Button(
        "Generar PDF (Ver / Imprimir)",
        icon=ft.Icons.PICTURE_AS_PDF,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        height=42,
        on_click=lambda _: ejecutar_generacion("pdf"),
        tooltip="Abre el informe en el visor web para visualizar o imprimir directamente",
    )
    btn_excel = ft.Button(
        "Exportar Excel (.xlsx)",
        icon=ft.Icons.TABLE_CHART,
        bgcolor=ft.Colors.GREEN_700,
        color=ft.Colors.WHITE,
        height=42,
        on_click=lambda _: ejecutar_generacion("xlsx"),
        tooltip="Exporta los datos tabulados a una planilla de cálculo Excel",
    )

    contenido = ft.Container(
        width=600,
        padding=16,
        content=ft.Column(
            [
                _construir_encabezado_reportes(interfaz),
                ft.Divider(color=interfaz.borde),
                ft.Text("Parámetros del Reporte", weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                tipo_reporte,
                ft.Container(content=ctrls["descripcion_reporte"], padding=ft.Padding.only(left=4, bottom=6)),
                ctrls["transporte_filtro"],
                ctrls["modo_movimiento"],
                ctrls["orden_movimientos"],
                preset_periodo,
                fila_fechas_custom,
                ctrls["sku_kardex_input"],
                ctrls["chk_conteo_ciego"],
                ctrls["filtro_ubicacion_input"],
                ctrls["ventana_rotacion"],
                ft.Container(height=6),
                progreso,
                estado_indicador,
                ft.Container(height=10),
                ft.Text("Selecciona el formato de salida:", size=12, weight=ft.FontWeight.W_500, color=interfaz.texto),
                ft.Row([btn_pdf, btn_excel], spacing=12, alignment=ft.MainAxisAlignment.START),
            ],
            spacing=10,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        ),
    )

    dialogo = ft.AlertDialog(
        content=contenido,
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    interfaz.page.show_dialog(dialogo)
