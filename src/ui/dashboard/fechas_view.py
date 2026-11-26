"""Vista y renderizado de pedidos agrupados por fecha para el operador."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import flet as ft
from ..design import par_accion_tarjeta
from ..theme import ROJO


def _obtener_resumen_fechas_operador(interfaz: Any) -> list[dict[str, Any]]:
    """Obtiene el resumen agrupado de pedidos armados por fecha en orden descendente."""
    store = getattr(interfaz, "order_store", None)
    if store is None:
        return []
    if hasattr(store, "obtener_resumen_pedidos_por_fecha"):
        try:
            res = store.obtener_resumen_pedidos_por_fecha(limit=30)
            if isinstance(res, list):
                return res
        except Exception:
            pass
    if hasattr(store, "listar_pedidos"):
        try:
            pedidos = store.listar_pedidos(limit=200)
            if isinstance(pedidos, list):
                agrupado: dict[str, dict[str, Any]] = {}
                for p in pedidos:
                    if getattr(p, "estado", "descontado") == "anulado":
                        continue
                    creado = str(getattr(p, "created_at", "") or "")
                    fecha = creado[:10] if len(creado) >= 10 else "Sin fecha"
                    if fecha not in agrupado:
                        agrupado[fecha] = {
                            "fecha": fecha,
                            "cantidad_pedidos": 0,
                            "total_bultos": 0,
                            "total_articulos": 0,
                        }
                    agrupado[fecha]["cantidad_pedidos"] += 1
                    agrupado[fecha]["total_bultos"] += int(getattr(p, "bultos", 0) or 0)
                    agrupado[fecha]["total_articulos"] += int(getattr(p, "articulos_descontados", 0) or 0)
                return sorted(
                    agrupado.values(),
                    key=lambda d: (str(d["fecha"]), int(d["cantidad_pedidos"])),
                    reverse=True,
                )
        except Exception:
            pass
    return []


def renderizar_pedidos_armados_por_fecha(interfaz: Any, resumen_fechas: list[dict[str, Any]]) -> None:
    """Renderiza en la tarjeta derecha del operador la lista de pedidos armados agrupados por fecha y cantidad descendente."""
    interfaz.lista_informes.controls.clear()
    if not resumen_fechas:
        interfaz.lista_informes.controls.append(
            ft.Container(
                padding=20,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.CALENDAR_TODAY_OUTLINED, size=32, color=interfaz.secundario),
                        ft.Text("Todavía no hay pedidos armados registrados.", size=12, color=interfaz.secundario),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
            )
        )
        return

    hoy_iso = datetime.now().strftime("%Y-%m-%d")
    resumen_ordenado = sorted(
        resumen_fechas,
        key=lambda d: (str(d.get("fecha", "")), int(d.get("cantidad_pedidos", 0))),
        reverse=True,
    )

    for item in resumen_ordenado:
        fecha_raw = str(item.get("fecha", "") or "")
        cant_pedidos = int(item.get("cantidad_pedidos", 0) or 0)
        total_bultos = int(item.get("total_bultos", 0) or 0)
        total_articulos = int(item.get("total_articulos", 0) or 0)

        try:
            dt_obj = datetime.strptime(fecha_raw[:10], "%Y-%m-%d")
            fecha_fmt = dt_obj.strftime("%d/%m/%Y")
        except Exception:
            fecha_fmt = fecha_raw or "Sin fecha"

        es_hoy = fecha_raw[:10] == hoy_iso
        etiqueta_fecha = f"{fecha_fmt} · Hoy" if es_hoy else fecha_fmt
        txt_pedidos = f"{cant_pedidos} pedido" if cant_pedidos == 1 else f"{cant_pedidos} pedidos"

        info_fecha = ft.Row(
            [
                ft.Container(
                    content=ft.Icon(ft.Icons.CALENDAR_MONTH, size=18, color=ROJO),
                    bgcolor=ft.Colors.RED_50,
                    padding=6,
                    border_radius=6,
                ),
                ft.Column(
                    [
                        ft.Text(
                            etiqueta_fecha,
                            weight=ft.FontWeight.BOLD,
                            size=12,
                            color=interfaz.texto,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            f"📦 {total_bultos} bulto(s) · {total_articulos} art. descontados",
                            size=11,
                            color=interfaz.secundario,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=8,
            expand=True,
        )
        badge_pedidos = ft.Container(
            content=ft.Text(
                txt_pedidos,
                size=11,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE,
            ),
            bgcolor=ROJO if es_hoy else ft.Colors.BLUE_GREY_700,
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=12,
        )
        card_fecha = ft.Container(
            bgcolor=interfaz.superficie,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            ink=True,
            tooltip="Clic para abrir el Historial de Pedidos",
            on_click=lambda _e: interfaz.mostrar_historial_pedidos() if hasattr(interfaz, "mostrar_historial_pedidos") else None,
            content=par_accion_tarjeta(interfaz, info_fecha, badge_pedidos, umbral=480.0, spacing=8),
        )
        interfaz.lista_informes.controls.append(card_fecha)
