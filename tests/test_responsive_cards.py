"""Pruebas unitarias para la responsividad integral de tarjetas en dashboard y diálogos."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import flet as ft

from src.auth import User
from src.orders import OrderStore, Pedido
from src.ui.components.admin_flow_analytics import construir_panel_analitica_flujo_admin
from src.ui.components.panels import (
    construir_panel_acceso_rapido,
    construir_panel_informes_actividad,
    construir_panel_metricas,
)
from src.ui.controllers.responsive_controller import ResponsiveController
from src.ui.dashboard.fechas_view import renderizar_pedidos_armados_por_fecha
from src.ui.dashboard.pedidos_turno_view import renderizar_pedidos_preparados_turno
from src.ui.design import (
    es_viewport_estrecho,
    grilla_tarjetas_responsiva,
    par_accion_tarjeta,
    resolver_columnas_grilla,
)
from src.ui.dialogs.analytics_metricas import _construir_filas_metricas_dashboard
from src.ui.dialogs.despacho_componentes import construir_tarjeta_pedido_pendiente
from src.ui.dialogs.dlg_anomalias import mostrar_dialogo_anomalias
from src.ui.dialogs.dlg_heatmap import mostrar_dialogo_heatmap
from src.ui.dialogs.dlg_modulo_despacho import construir_vista_modulo_despacho
from src.ui.dialogs.cierre.dlg_cierres_admin import mostrar_dialogo_cierres_operarios
from src.ui.dialogs.historial_cards import (
    _construir_fila_pedido,
    construir_cabecera_columnas_historial,
)
from src.ui.dialogs.mercadolibre_api_cards import construir_tarjeta_orden_ml


def _fake_interfaz(
    role: str = "operador",
    *,
    width: float | None = 1280,
    height: float | None = 800,
    es_movil: bool = False,
    order_store: OrderStore | None = None,
) -> SimpleNamespace:
    dialogos: list[ft.AlertDialog] = []

    def _show_dialog(dlg: ft.AlertDialog) -> None:
        dialogos.append(dlg)

    def _pop_dialog() -> None:
        if dialogos:
            dialogos.pop()

    page = SimpleNamespace(
        width=width,
        height=height,
        client_user_agent="",
        platform="windows",
        web=False,
        show_dialog=_show_dialog,
        pop_dialog=_pop_dialog,
        update=lambda: None,
        dialogos=dialogos,
    )
    menu = SimpleNamespace(
        ruta_excel_base="Productos.xlsx",
        carpeta_descuentos=Path("."),
        _obtener_pendientes=lambda: ([], [], []),
        _obtener_archivados=lambda: ([], [], []),
        _obtener_generados=lambda: [],
    )
    noop = lambda *_a, **_kw: None
    itf = SimpleNamespace(
        page=page,
        menu=menu,
        order_store=order_store,
        product_store=None,
        usuario_actual=User(id=1, username=f"u_{role}", role=role, active=True),  # type: ignore[arg-type]
        modo_oscuro=True,
        fondo=ft.Colors.BLACK,
        superficie="#1e1e1e",
        fondo_acento="#262626",
        texto=ft.Colors.WHITE,
        secundario=ft.Colors.GREY_400,
        borde=ft.Colors.GREY_700,
        posicion_sidebar="izquierda",
        es_pantalla_movil=es_movil,
        contadores={},
        lista_informes=ft.ListView(),
        lista_pedidos_preparados=ft.ListView(),
        header_pedidos_fecha=ft.Text("Hoy"),
        header_pedidos_subtitulo=ft.Text("0 pedidos"),
        header_pedidos_bultos=ft.Text("0 bultos"),
        banner_alerta_quiebre=ft.Container(visible=False),
        pendientes_texto=ft.Text(""),
        contenedor_notificaciones=ft.Container(),
        tarjeta=lambda c, expand=False: ft.Container(content=c, expand=expand),
        boton_dialogo=lambda txt, fn: ft.TextButton(txt, on_click=fn),
        boton=lambda txt, ico, fn: ft.Button(content=txt, icon=ico, on_click=fn),
        exigir_roles=lambda *roles: role in roles,
        notificar=noop,
        actualizar_listas=noop,
        actualizar_estado=noop,
        ancho_adaptable=lambda d, margen=24: min(d, max(260, int(width - margen))) if width else d,
        alto_adaptable=lambda d, margen=60: min(d, max(300, int(height - margen))) if height else d,
        mostrar_gestion_usuarios=noop,
        mostrar_registro_auditoria=noop,
        mostrar_descuento_mercado_libre=noop,
        mostrar_dialogo_ingreso_rapido=noop,
        mostrar_dialogo_salida_rapida=noop,
        mostrar_crear_pedido=noop,
        mostrar_ver_stock=noop,
        mostrar_historial_pedidos=noop,
        mostrar_planificar_full=noop,
        mostrar_planificar_ingreso_fabrica=noop,
        mostrar_dialogo_editar_pedido=noop,
        mostrar_detalle_pedido_modal=noop,
        mostrar_dialogo_ajuste_bultos_express=noop,
        confirmar_desarmar_pedido=noop,
        confirmar_eliminacion_pedido=noop,
        abrir_informe=noop,
    )
    return itf


def _pedido_demo(pid: int = 1) -> Pedido:
    return Pedido(
        id=pid,
        nota_pedido=f"REM-{pid:04d}",
        numero_pedido=f"P-{pid}",
        cliente="Cliente Mayorista Norte S.A.",
        bultos=3,
        logistica="Transporte Expreso",
        armador="Carlos",
        tipo_archivo="pdf",
        nombre_archivo=f"REM-{pid:04d}.pdf",
        agregado=False,
        articulos_descontados=12,
        resumen_items="12 un.",
        created_at="2026-11-25 10:30:00",
        estado="descontado",
        estado_despacho="armado",
    )


class TestResponsiveCards(unittest.TestCase):
    def test_helpers_grilla_y_breakpoints_sin_huecos(self) -> None:
        cols5, span5 = resolver_columnas_grilla(5, compacto=True)
        self.assertEqual(cols5, 60)
        self.assertEqual(span5["lg"] * 5, 60)
        self.assertEqual(span5["xs"] * 2, 60)

        cols6, span6 = resolver_columnas_grilla(6, compacto=True)
        self.assertEqual(cols6, 12)
        self.assertEqual(span6["lg"] * 6, 12)

        # WebView móvil con ancho amplio fuerza máximo 2 columnas compactas o 1 ancha
        _, span_wv = resolver_columnas_grilla(5, compacto=True, forzar_movil=True)
        self.assertEqual(span_wv, {"xs": 6})
        _, span_wv_wide = resolver_columnas_grilla(3, compacto=False, forzar_movil=True)
        self.assertEqual(span_wv_wide, {"xs": 12})

        tarjetas = [ft.Container(expand=True) for _ in range(4)]
        grilla = grilla_tarjetas_responsiva(tarjetas, compacto=True)
        self.assertIsInstance(grilla, ft.ResponsiveRow)
        self.assertNotEqual(grilla.vertical_alignment, ft.CrossAxisAlignment.STRETCH)
        for t in tarjetas:
            self.assertFalse(t.expand)
            self.assertIsInstance(t.col, dict)

        # Incluso si un llamador pasa STRETCH, grilla_tarjetas_responsiva lo degrada a START
        # para no disparar `BoxConstraints forces an infinite height` en Column(scroll=AUTO).
        grilla_segura = grilla_tarjetas_responsiva(
            [ft.Container(), ft.Container(), ft.Container()],
            compacto=False,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.assertEqual(grilla_segura.vertical_alignment, ft.CrossAxisAlignment.START)
        self.assertEqual(grilla_segura.controls[0].col["md"], 4)

        itf_narrow = _fake_interfaz(width=400)
        itf_wide = _fake_interfaz(width=1280)
        itf_mock = MagicMock()
        self.assertTrue(es_viewport_estrecho(itf_narrow, 768))
        self.assertFalse(es_viewport_estrecho(itf_wide, 768))
        self.assertFalse(es_viewport_estrecho(itf_mock, 768))
        self.assertIsInstance(par_accion_tarjeta(itf_narrow, ft.Text("A"), ft.Button("B")), ft.Column)
        self.assertIsInstance(par_accion_tarjeta(itf_wide, ft.Text("A"), ft.Button("B")), ft.Row)

    def test_dashboard_metricas_acceso_rapido_y_flujo_usan_responsive_row_en_todos_los_tamanos(self) -> None:
        for es_movil, width in ((False, 1280), (False, 820), (True, 375), (True, 980)):
            itf_op = _fake_interfaz("operador", width=width, es_movil=es_movil)
            panel_m = construir_panel_metricas(itf_op)
            self.assertIsInstance(panel_m, ft.ResponsiveRow)
            self.assertEqual(len(panel_m.controls), 5)
            self.assertNotEqual(panel_m.vertical_alignment, ft.CrossAxisAlignment.STRETCH)

            panel_acc = construir_panel_acceso_rapido(itf_op)
            inner = panel_acc.content.controls[1]
            self.assertIsInstance(inner, ft.ResponsiveRow)
            self.assertEqual(len(inner.controls), 3)
            self.assertNotEqual(inner.vertical_alignment, ft.CrossAxisAlignment.STRETCH)

            with tempfile.TemporaryDirectory() as tmp:
                store = OrderStore(Path(tmp) / "pedidos.sqlite3")
                itf_adm = _fake_interfaz("administrador", width=width, es_movil=es_movil, order_store=store)
                panel_flujo = construir_panel_analitica_flujo_admin(itf_adm)
                self.assertIsInstance(panel_flujo, ft.Column)
                self.assertIsInstance(panel_flujo.controls[1], ft.ResponsiveRow)
                self.assertNotEqual(panel_flujo.controls[1].vertical_alignment, ft.CrossAxisAlignment.STRETCH)
                self.assertIsInstance(panel_flujo.controls[2], ft.ResponsiveRow)

    def test_panel_informes_apila_bajo_900px_y_redimensiona_en_tablet(self) -> None:
        itf = _fake_interfaz("operador", width=820, height=800, es_movil=False)
        panel_tablet = construir_panel_informes_actividad(itf)
        self.assertIsInstance(panel_tablet, ft.Column)

        rebuilds: list[bool] = []
        itf._modo_movil_previo = False
        itf._ancho_previo = 1280.0
        ctrl = ResponsiveController(itf, on_rebuild=lambda: rebuilds.append(True))
        ctrl.al_redimensionar()
        self.assertEqual(len(rebuilds), 1)

    def test_tarjetas_turno_fechas_y_despacho_adaptan_en_movil(self) -> None:
        ped = _pedido_demo(1)
        itf_narrow = _fake_interfaz("operador", width=390, es_movil=True)
        renderizar_pedidos_preparados_turno(itf_narrow, [ped])
        card_turno = itf_narrow.lista_pedidos_preparados.controls[0]
        self.assertIsInstance(card_turno.content, ft.Column)

        renderizar_pedidos_armados_por_fecha(
            itf_narrow,
            [{"fecha": "2026-11-25", "cantidad_pedidos": 4, "total_bultos": 8, "total_articulos": 20}],
        )
        card_fecha = itf_narrow.lista_informes.controls[0]
        self.assertIsInstance(card_fecha.content, ft.Column)

        with tempfile.TemporaryDirectory() as tmp:
            store = OrderStore(Path(tmp) / "desp.sqlite3")
            itf_desp = _fake_interfaz("despachador", width=400, es_movil=True, order_store=store)
            vista, _ = construir_vista_modulo_despacho(itf_desp, modo_dialogo=False)
            bloques = vista.content.controls
            self.assertTrue(any(isinstance(b, ft.ResponsiveRow) for b in bloques))

            card_pend = construir_tarjeta_pedido_pendiente(itf_desp, ped, [1], lambda _p: None)
            self.assertIsInstance(card_pend.content.controls[0], ft.Column)

    def test_dialogos_metricas_anomalias_heatmap_cierres_ml_e_historial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OrderStore(Path(tmp) / "all.sqlite3")
            itf_adm = _fake_interfaz("administrador", width=400, es_movil=True, order_store=store)

            # 1. Analytics métricas
            m = {
                "total_pedidos": 1,
                "total_bultos": 3,
                "estados_despacho": {"armado": 1, "despachado": 0, "entregado": 0},
                "distribucion_logistica": [("Transporte", 1, 3)],
                "rendimiento_armadores": [("Carlos", 1, 3)],
                "top_articulos": [("SKU-1", "Prod 1", 10)],
                "pedidos_por_dia": [("2026-11-25", 1, 3)],
            }
            kpis, tablas, _ = _construir_filas_metricas_dashboard(itf_adm, m)
            self.assertIsInstance(kpis, ft.ResponsiveRow)
            self.assertIsInstance(tablas, ft.ResponsiveRow)

            # 2. Heatmap & Anomalías & Cierres Admin
            mostrar_dialogo_heatmap(itf_adm)
            dlg_hm = itf_adm.page.dialogos[-1]
            self.assertIsInstance(dlg_hm.content.content.controls[0], ft.ResponsiveRow)
            itf_adm.page.pop_dialog()

            mostrar_dialogo_anomalias(itf_adm)
            dlg_anom = itf_adm.page.dialogos[-1]
            self.assertIsInstance(dlg_anom.content.content.controls[0], ft.ResponsiveRow)
            itf_adm.page.pop_dialog()

            mostrar_dialogo_cierres_operarios(itf_adm)
            dlg_cie = itf_adm.page.dialogos[-1]
            self.assertIsInstance(dlg_cie.content.content.controls[0], ft.ResponsiveRow)
            itf_adm.page.pop_dialog()

            # 3. Historial estrecho (tarjeta) vs desktop (fila tabular)
            ped = _pedido_demo(5)
            itf_op_narrow = _fake_interfaz("operador", width=400, es_movil=True, order_store=store)
            cab_movil = construir_cabecera_columnas_historial(itf_op_narrow)
            self.assertFalse(cab_movil.visible)
            card_hist = _construir_fila_pedido(
                itf_op_narrow,
                ped,
                set(),
                lambda _e, _id: None,
                lambda _e: None,
                lambda _p, _s: None,
            )
            self.assertIsInstance(card_hist.content, ft.Column)

            # 4. Mercado Libre API card en móvil
            ord_ml = {
                "ref_pedido": "ML-900",
                "cliente": "Comprador ML",
                "fecha": "2026-11-25",
                "total_unidades": 2,
                "total_importe": 15000.0,
                "stock_suficiente": True,
                "items_coincidentes": [
                    {"codigo": "101", "nombre": "Producto largo de prueba", "cantidad": 2, "stock_actual": 10}
                ],
                "items_no_coincidentes": [],
            }
            card_ml = construir_tarjeta_orden_ml(itf_op_narrow, ord_ml, False, True, lambda _e: None)
            self.assertIsInstance(card_ml.content.controls[0], ft.Column)
            lista_items_ml = card_ml.content.controls[1].content
            self.assertIsInstance(lista_items_ml.controls[0], ft.Column)


if __name__ == "__main__":
    unittest.main()
