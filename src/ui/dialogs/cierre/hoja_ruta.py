"""Resolución de comprobantes y gestión de hojas de ruta de despacho."""
from pathlib import Path
import sys
from typing import Any
import flet as ft

from ....dispatch_manifest import generar_hoja_ruta_pdf
from ....paths import application_root
from ...theme import ROJO
from ....stock_manager import StockManager as _DefaultStockManager

def _get_stock_manager_cls():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager

def resolver_archivos_cierre(interfaz: Any, c: Any) -> tuple[Path | None, Path | None, Path | None]:
    """Resuelve las rutas absolutas físicas de los archivos generados en un cierre de jornada."""
    root = application_root()
    carpeta = getattr(getattr(interfaz, "menu", None), "carpeta_descuentos", root / "Descuentos")

    def _buscar(nombre: str | None) -> Path | None:
        if not nombre:
            return None
        candidatos = [
            carpeta / nombre,
            root / "Descuentos" / nombre,
            root / "data" / "informes" / nombre,
            root / "data" / "descontados" / nombre,
            root / "data" / "pedidos_archivos" / nombre,
        ]
        for cand in candidatos:
            if cand.exists():
                return cand
        return carpeta / nombre

    pdf_ruta = _buscar(getattr(c, "archivo_pdf", None))
    xls_ruta = _buscar(getattr(c, "archivo_excel", None))
    hoja_ruta = _buscar(getattr(c, "archivo_hoja_ruta", None))
    return pdf_ruta, xls_ruta, hoja_ruta


def gestionar_hoja_ruta_cierre(interfaz: Any, cierre_obj: Any, hr_path: Path | None) -> None:
    """Gestiona la apertura o generación bajo demanda de la Hoja de Ruta de despacho para un cierre."""
    peds = interfaz.order_store.obtener_pedidos_por_cierre(cierre_obj.id)
    if not peds:
        if hr_path and hr_path.exists():
            interfaz.abrir_informe(ruta_especifica=hr_path)
        else:
            interfaz.notificar("No se encontraron registros de pedidos para este cierre.")
        return

    transportes_presentes = sorted(list({p.logistica for p in peds if p.logistica}))

    if len(transportes_presentes) <= 1:
        if hr_path and hr_path.exists():
            interfaz.abrir_informe(ruta_especifica=hr_path)
        else:
            destino = getattr(getattr(interfaz, "menu", None), "carpeta_descuentos", application_root() / "Descuentos")
            nueva_hr = generar_hoja_ruta_pdf(
                cierre_id=cierre_obj.id,
                pedidos=peds,
                usuario=cierre_obj.usuario,
                carpeta_destino=destino,
            )
            interfaz.order_store.actualizar_hoja_ruta_cierre(cierre_obj.id, nueva_hr.name)
            interfaz.abrir_informe(ruta_especifica=nueva_hr)
        return

    def emitir_hr(transporte_sel=None):
        interfaz.page.pop_dialog()
        destino = getattr(getattr(interfaz, "menu", None), "carpeta_descuentos", application_root() / "Descuentos")
        doc = generar_hoja_ruta_pdf(
            cierre_id=cierre_obj.id,
            pedidos=peds,
            usuario=cierre_obj.usuario,
            carpeta_destino=destino,
            filtro_logistica=transporte_sel,
        )
        interfaz.abrir_informe(ruta_especifica=doc)

    botones_transportes = [
        ft.Button(
            "📄 Hoja de Ruta General (Todos los transportes)",
            icon=ft.Icons.ALL_INBOX,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
            on_click=lambda _e: emitir_hr(None),
        )
    ]
    for tr in transportes_presentes:
        c_bultos = sum(p.bultos for p in peds if p.logistica == tr)
        c_peds = sum(1 for p in peds if p.logistica == tr)
        botones_transportes.append(
            ft.OutlinedButton(
                f"🚚 Solo {tr} ({c_peds} pedidos · {c_bultos} bultos)",
                icon=ft.Icons.LOCAL_SHIPPING,
                on_click=lambda _e, t=tr: emitir_hr(t),
            )
        )

    dlg_sel_transporte = ft.AlertDialog(
        title=ft.Row([ft.Icon(ft.Icons.LOCAL_SHIPPING, color=ROJO), ft.Text(f"Hoja de Ruta · Cierre #{cierre_obj.id}")]),
        content=ft.Container(
            width=460,
            content=ft.Column(
                [
                    ft.Text("Selecciona cómo deseas imprimir la Hoja de Ruta de despacho:", size=12, color=interfaz.texto),
                    ft.Divider(height=6),
                    *botones_transportes,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dlg_sel_transporte)



