"""Pruebas unitarias para los diálogos de Entrada Rápida y Salida Rápida de Stock."""

import unittest
from unittest.mock import MagicMock, patch
import sqlite3

import flet as ft
from src.ui.dialogs.dlg_movimientos_rapidos import (
    MotivoIngresoRapido,
    MotivoSalidaRapida,
    mostrar_dialogo_ingreso_rapido,
    mostrar_dialogo_salida_rapida,
)


class TestMovimientosRapidos(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock()
        self.page.dialog = None
        self.dialogo_mostrado = None

        def _mock_show_dialog(dlg):
            self.dialogo_mostrado = dlg
            self.page.dialog = dlg

        self.page.show_dialog = MagicMock(side_effect=_mock_show_dialog)
        self.page.pop_dialog = MagicMock()
        self.page.update = MagicMock()

        self.usuario_operador = MagicMock()
        self.usuario_operador.username = "operador1"
        self.usuario_operador.role = "operador"
        self.usuario_operador.nombre_identificador = "Juan Operario"

        self.usuario_consulta = MagicMock()
        self.usuario_consulta.username = "auditor1"
        self.usuario_consulta.role = "consulta"
        self.usuario_consulta.nombre_identificador = "Auditor Externo"

        self.stock_manager = MagicMock()
        self.stock_manager.catalogo = {
            "PROD-01": (1, "Taladro Percutor 500W", 25),
        }
        mock_row = {"code": "PROD-01", "name": "Taladro Percutor 500W", "barcode": "7791234567890", "stock": 25}
        self.stock_manager.buscar_producto_por_codigo_o_barras.return_value = mock_row

        self.order_store = MagicMock()
        self.order_store.registrar_auditoria = MagicMock()

        self.interfaz = MagicMock()
        self.interfaz.page = self.page
        self.interfaz.usuario_actual = self.usuario_operador
        self.interfaz.stock_manager = self.stock_manager
        self.interfaz.order_store = self.order_store
        self.interfaz.texto = ft.Colors.WHITE
        self.interfaz.secundario = ft.Colors.GREY_400
        self.interfaz.borde = ft.Colors.GREY_700
        self.interfaz.notificar = MagicMock()
        self.interfaz.actualizar_estado = MagicMock()
        self.interfaz.cerrar_drawer_si_movil = MagicMock()

    def test_enums_motivos(self):
        """Verifica que los enums contengan motivos operativos requeridos."""
        self.assertIn("Devolución de Cliente", [m.value for m in MotivoIngresoRapido])
        self.assertIn("Movimiento Interno", [m.value for m in MotivoIngresoRapido])
        self.assertIn("Sobrante de Inventario / Ajuste", [m.value for m in MotivoIngresoRapido])
        self.assertIn("Muestra / Ingreso Especial", [m.value for m in MotivoIngresoRapido])

        self.assertIn("Rotura / Merma / Dañado", [m.value for m in MotivoSalidaRapida])
        self.assertIn("Muestra Comercial / Exhibición", [m.value for m in MotivoSalidaRapida])
        self.assertIn("Consumo / Uso Interno", [m.value for m in MotivoSalidaRapida])
        self.assertIn("Devolución a Proveedor", [m.value for m in MotivoSalidaRapida])
        self.assertIn("Faltante / Ajuste de Inventario", [m.value for m in MotivoSalidaRapida])

    def test_permiso_rol_consulta_denegado(self):
        """Verifica que el rol 'consulta' no pueda abrir el diálogo de movimiento rápido."""
        self.interfaz.usuario_actual = self.usuario_consulta

        mostrar_dialogo_ingreso_rapido(self.interfaz)
        self.page.show_dialog.assert_not_called()
        self.interfaz.notificar.assert_called_once()
        self.assertIn("no tiene permisos", self.interfaz.notificar.call_args[0][0].lower())

        self.interfaz.notificar.reset_mock()
        mostrar_dialogo_salida_rapida(self.interfaz)
        self.page.show_dialog.assert_not_called()
        self.interfaz.notificar.assert_called_once()
        self.assertIn("no tiene permisos", self.interfaz.notificar.call_args[0][0].lower())

    def test_apertura_dialogo_ingreso_rapido(self):
        """Verifica que el diálogo de Entrada Rápida se configure correctamente para operador."""
        mostrar_dialogo_ingreso_rapido(self.interfaz)
        self.page.show_dialog.assert_called_once()
        dlg = self.dialogo_mostrado
        self.assertIsInstance(dlg, ft.AlertDialog)

        # Validar título de diálogo
        titulo_row = dlg.title
        self.assertTrue(any("Entrada Rápida" in getattr(c, "value", "") for c in titulo_row.controls if isinstance(c, ft.Text)))

    def test_apertura_dialogo_salida_rapida(self):
        """Verifica que el diálogo de Salida Rápida se configure correctamente para operador."""
        mostrar_dialogo_salida_rapida(self.interfaz)
        self.page.show_dialog.assert_called_once()
        dlg = self.dialogo_mostrado
        self.assertIsInstance(dlg, ft.AlertDialog)

        # Validar título de diálogo
        titulo_row = dlg.title
        self.assertTrue(any("Salida Rápida" in getattr(c, "value", "") for c in titulo_row.controls if isinstance(c, ft.Text)))

    def test_botonera_cuarteto_accesos_rapidos_sidebar(self):
        """Verifica que el menú lateral contenga los 4 accesos directos rápidos para el operador."""
        from src.ui.components.sidebar import construir_sidebar_controls
        controles = construir_sidebar_controls(self.interfaz)
        textos = []
        for c in controles:
            if isinstance(c, ft.Column):
                for sub in getattr(c, "controls", []):
                    if isinstance(sub, ft.Row):
                        for btn in getattr(sub, "controls", []):
                            content = getattr(btn, "content", None)
                            if isinstance(content, ft.Row):
                                for elem in getattr(content, "controls", []):
                                    if isinstance(elem, ft.Text):
                                        textos.append(elem.value)
        self.assertIn("Entrada", textos)
        self.assertIn("Salida", textos)
        self.assertIn("Cargar Pedido", textos)
        self.assertIn("Mercado Libre", textos)

    def test_flujo_ingreso_rapido_confirmado(self):
        """Prueba completa del flujo de búsqueda y confirmación de una Entrada Rápida."""
        mostrar_dialogo_ingreso_rapido(self.interfaz)
        dlg = self.dialogo_mostrado
        col = dlg.content

        # Controles internos
        fila_busqueda = next(c for c in col.controls if isinstance(c, ft.Row) and any(isinstance(x, ft.TextField) for x in c.controls))
        txt_busqueda = fila_busqueda.controls[0]
        btn_buscar = fila_busqueda.controls[1]
        dropdown_motivo = next(c for c in col.controls if isinstance(c, ft.Dropdown))
        btn_confirmar = dlg.actions[1]

        # Simular búsqueda de producto
        txt_busqueda.value = "PROD-01"
        btn_buscar.on_click(None)

        self.stock_manager.buscar_producto_por_codigo_o_barras.assert_called_with("PROD-01")

        # Seleccionar motivo obligatorio
        dropdown_motivo.value = MotivoIngresoRapido.DEVOLUCION_CLIENTE.value

        # Confirmar movimiento
        btn_confirmar.on_click(None)

        # Validar que se llamó al StockManager con +1
        self.stock_manager.registrar_ingreso_fabrica.assert_called_once_with({"PROD-01": 1}, sobrescribir=False)
        self.stock_manager.product_store.register_movements.assert_called_once()
        args_mov = self.stock_manager.product_store.register_movements.call_args
        self.assertEqual(args_mov[0][0][0][0], "PROD-01")
        self.assertEqual(args_mov[0][0][0][2], 1)
        self.assertEqual(args_mov[0][0][0][3], "ingreso_rapido")

        # Validar auditoría
        self.order_store.registrar_auditoria.assert_called_once()
        audit_args = self.order_store.registrar_auditoria.call_args[1] if self.order_store.registrar_auditoria.call_args[1] else self.order_store.registrar_auditoria.call_args[0]
        self.assertIn("INGRESO_RAPIDO", str(audit_args))

        # Validar cierre de diálogo y notificación
        self.page.pop_dialog.assert_called_once()
        self.interfaz.notificar.assert_called_once()

    def test_flujo_salida_rapida_confirmada(self):
        """Prueba completa del flujo de búsqueda y confirmación de una Salida Rápida."""
        mostrar_dialogo_salida_rapida(self.interfaz)
        dlg = self.dialogo_mostrado
        col = dlg.content

        fila_busqueda = next(c for c in col.controls if isinstance(c, ft.Row) and any(isinstance(x, ft.TextField) for x in c.controls))
        txt_busqueda = fila_busqueda.controls[0]
        btn_buscar = fila_busqueda.controls[1]
        dropdown_motivo = next(c for c in col.controls if isinstance(c, ft.Dropdown))
        btn_confirmar = dlg.actions[1]

        txt_busqueda.value = "PROD-01"
        btn_buscar.on_click(None)

        dropdown_motivo.value = MotivoSalidaRapida.ROTURA_MERMA.value
        btn_confirmar.on_click(None)

        # En salida rápida, la cantidad a registrar en registrar_ingreso_fabrica es negativa (-1)
        self.stock_manager.registrar_ingreso_fabrica.assert_called_once_with({"PROD-01": -1}, sobrescribir=False)
        args_mov = self.stock_manager.product_store.register_movements.call_args
        self.assertEqual(args_mov[0][0][0][2], -1)
        self.assertEqual(args_mov[0][0][0][3], "salida_rapida")

        self.order_store.registrar_auditoria.assert_called_once()
        self.assertIn("SALIDA_RAPIDA", str(self.order_store.registrar_auditoria.call_args))

    def test_validacion_sin_producto_o_motivo(self):
        """Verifica que el diálogo impida confirmar si no hay producto o motivo."""
        mostrar_dialogo_ingreso_rapido(self.interfaz)
        dlg = self.dialogo_mostrado
        col = dlg.content
        btn_confirmar = dlg.actions[1]
        lbl_estado = next(c for c in col.controls if isinstance(c, ft.Text) and hasattr(c, 'value'))

        # 1. Intentar sin seleccionar producto
        btn_confirmar.on_click(None)
        self.stock_manager.registrar_ingreso_fabrica.assert_not_called()
        self.assertIn("primero debes escanear", lbl_estado.value.lower())

        # 2. Seleccionar producto pero no motivo
        fila_busqueda = next(c for c in col.controls if isinstance(c, ft.Row) and any(isinstance(x, ft.TextField) for x in c.controls))
        txt_busqueda = fila_busqueda.controls[0]
        btn_buscar = fila_busqueda.controls[1]
        txt_busqueda.value = "PROD-01"
        btn_buscar.on_click(None)

        btn_confirmar.on_click(None)
        self.stock_manager.registrar_ingreso_fabrica.assert_not_called()
        self.assertIn("motivo justificado obligatorio", lbl_estado.value.lower())


if __name__ == "__main__":
    unittest.main()
