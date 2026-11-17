import asyncio
import unittest
from unittest.mock import MagicMock, patch
import flet as ft

from src.ui.dialogs.productos_modales import (
    mostrar_dialogo_formulario_producto,
    mostrar_dialogo_editar_producto,
)
from src.ui.controllers.batch_controller import BatchTaskController


class TestValidacionFormularios(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.interfaz = MagicMock()
        self.interfaz.exigir_roles.return_value = True
        self.interfaz.page = MagicMock()
        self.interfaz.menu = MagicMock()
        self.interfaz.menu.ruta_excel_base = "test_productos.xlsx"
        self.interfaz.notificar = MagicMock()
        self.interfaz.boton_dialogo = lambda text, on_click: ft.TextButton(text, on_click=on_click)

    async def test_alta_producto_codigo_duplicado(self):
        fake_stock_manager = MagicMock()
        fake_stock_manager.product_store.get_product.side_effect = lambda code: (
            {"name": "Electrolyte Arandano"} if str(code) == "2807" else None
        )
        fake_stock_manager.catalogo = {"2807": (327, "Electrolyte Arandano", 10)}

        with patch("src.ui.dialogs.productos_modales._resolver_stock_manager_cls", return_value=lambda _: fake_stock_manager):
            dialogo_capturado = None
            def capturar_dialogo(d):
                nonlocal dialogo_capturado
                dialogo_capturado = d
            self.interfaz.page.show_dialog = capturar_dialogo

            mostrar_dialogo_formulario_producto(self.interfaz)
            self.assertIsNotNone(dialogo_capturado)

            # Extraer campos
            columna = dialogo_capturado.content
            campo_cod = [c for c in columna.controls if "Código del nuevo producto" in c.label][0]
            campo_nom = [c for c in columna.controls if "Nombre del producto" in c.label][0]
            campo_ref = [c for c in columna.controls if "anterior" in c.label][0]

            campo_cod.value = "2807"
            campo_nom.value = "Nuevo Producto"
            campo_ref.value = "2806"

            # Ejecutar guardar
            guardar_btn_handler = dialogo_capturado.actions[1].on_click
            await guardar_btn_handler(None)

            # Debe haberse seteado error_text y NO haberse hecho pop_dialog
            self.assertIn("ya existe", campo_cod.error_text.lower())
            self.interfaz.page.pop_dialog.assert_not_called()
            self.interfaz.notificar.assert_called_with("El producto con código '2807' ya existe.")

    async def test_alta_producto_referencia_no_existe(self):
        fake_stock_manager = MagicMock()
        fake_stock_manager.product_store.get_product.return_value = None
        fake_stock_manager.catalogo = {}

        with patch("src.ui.dialogs.productos_modales._resolver_stock_manager_cls", return_value=lambda _: fake_stock_manager):
            dialogo_capturado = None
            self.interfaz.page.show_dialog = lambda d: setattr(self, "_dlg", d)

            mostrar_dialogo_formulario_producto(self.interfaz)
            dialogo = self._dlg

            columna = dialogo.content
            campo_cod = [c for c in columna.controls if "Código del nuevo producto" in c.label][0]
            campo_nom = [c for c in columna.controls if "Nombre del producto" in c.label][0]
            campo_ref = [c for c in columna.controls if "anterior" in c.label][0]

            campo_cod.value = "9999"
            campo_nom.value = "Nuevo Producto"
            campo_ref.value = "8888"

            guardar_btn_handler = dialogo.actions[1].on_click
            await guardar_btn_handler(None)

            self.assertIn("No existe", campo_ref.error_text)
            self.interfaz.page.pop_dialog.assert_not_called()

    async def test_editar_producto_codigo_duplicado(self):
        fake_stock_manager = MagicMock()
        fake_stock_manager.product_store.get_product.side_effect = lambda code: (
            {"name": "Otro Producto"} if str(code) == "2807" else None
        )
        fake_stock_manager.catalogo = {"2807": (327, "Otro Producto", 10)}

        self.interfaz.page.show_dialog = lambda d: setattr(self, "_dlg", d)

        producto = {
            "code": "2805",
            "name": "Producto Actual",
            "stock": 10,
            "stock_minimo": 5,
            "stock_maximo": 100,
            "cod_barras": "",
        }

        mostrar_dialogo_editar_producto(self.interfaz, fake_stock_manager, producto, MagicMock())
        dialogo = self._dlg

        campo_cod = [c for c in dialogo.content.controls if c.label == "Código"][0]
        campo_cod.value = "2807"  # Cambiar al código existente

        guardar_btn_handler = dialogo.actions[1].on_click
        await guardar_btn_handler(None)

        self.assertIn("ya existe", campo_cod.error_text.lower())
        self.interfaz.page.pop_dialog.assert_not_called()

    async def test_batch_controller_value_error_handling(self):
        host = MagicMock()
        host.actividad.controls = []
        host.modo_oscuro = False
        host.ocupado = False

        lock_state = [False]
        def get_lock():
            return lock_state[0]
        def set_lock(val):
            lock_state[0] = val

        ctrl = BatchTaskController(host, get_global_lock_fn=get_lock, set_global_lock_fn=set_lock)
        ctrl._notificar = MagicMock()
        ctrl._set_status_text = MagicMock()

        def accion_con_value_error():
            raise ValueError("El producto ya existe en el sistema.")

        exito = await ctrl.ejecutar_tarea("Prueba", accion_con_value_error)
        self.assertFalse(exito)
        ctrl._notificar.assert_called_with("El producto ya existe en el sistema.")
        self.assertTrue(any("[AVISO]" in getattr(c, "value", "") for c in host.actividad.controls))


if __name__ == "__main__":
    unittest.main()
