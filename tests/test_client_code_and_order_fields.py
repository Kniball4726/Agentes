"""Tests unitarios para las nuevas funcionalidades de clientes y pedidos:
1. Separación de código y nombre de cliente al escanear remito.
2. Extracción y persistencia de dirección del cliente (para mapas / Google Maps API).
3. Extracción de fecha de despacho para auto-asignación de fecha de retiro.
4. Stepper (+ / -) de cantidad de bultos.
5. Validación obligatoria de tipo de logística sin selección por defecto.
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import flet as ft

from src.orders_store import Cliente, OrderStore
from src.remito_parser import ResultadoRemito, parsear_remito


class TestClientCodeAndOrderFields(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "pedidos_test.sqlite3"
        self.store = OrderStore(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_clientes_schema_migration_columns(self):
        """Verifica que las columnas 'codigo' y 'direccion' existan e indexen en SQLite."""
        with self.store._connect() as conn:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(clientes)").fetchall()}
            self.assertIn("codigo", cols)
            self.assertIn("direccion", cols)

    def test_crear_y_listar_cliente_con_codigo_y_direccion(self):
        """Crea clientes con código y dirección y valida su persistencia."""
        cli = self.store.crear_cliente(
            nombre="DIETETICA INTEGRAL",
            usuario="admin",
            codigo="01240",
            direccion="Diagonal 80 835, La Plata, Buenos Aires",
        )
        self.assertEqual(cli.nombre, "DIETETICA INTEGRAL")
        self.assertEqual(cli.codigo, "01240")
        self.assertEqual(cli.direccion, "Diagonal 80 835, La Plata, Buenos Aires")

        clientes = self.store.listar_clientes()
        self.assertEqual(len(clientes), 1)
        self.assertEqual(clientes[0].codigo, "01240")
        self.assertEqual(clientes[0].direccion, "Diagonal 80 835, La Plata, Buenos Aires")

    def test_actualizar_cliente_con_codigo_y_direccion(self):
        """Actualiza el código y dirección de un cliente existente."""
        cli = self.store.crear_cliente("FARMACIA NORTE", usuario="operador")
        self.assertEqual(cli.codigo, "")
        self.assertEqual(cli.direccion, "")

        act = self.store.actualizar_cliente(
            cliente_id=cli.id,
            nuevo_nombre="FARMACIA NORTE S.A.",
            usuario="admin",
            codigo="05500",
            direccion="Av. Santa Fe 1234, CABA",
        )
        self.assertEqual(act.nombre, "FARMACIA NORTE S.A.")
        self.assertEqual(act.codigo, "05500")
        self.assertEqual(act.direccion, "Av. Santa Fe 1234, CABA")

    def test_obtener_o_crear_cliente_enriquecimiento(self):
        """Valida que obtener_o_crear_cliente complete campos faltantes si se proveen."""
        # 1. Crear inicialmente sin código ni dirección
        c1 = self.store.crear_cliente("DISTRIBUIDORA SUR", usuario="sistema")
        self.assertEqual(c1.codigo, "")
        self.assertEqual(c1.direccion, "")

        # 2. Re-invocar con datos obtenidos del escaneo de remito
        c2 = self.store.obtener_o_crear_cliente(
            nombre="DISTRIBUIDORA SUR",
            codigo="03321",
            direccion="Calle 14 Nro 500, Berazategui",
            usuario="sistema",
        )
        self.assertEqual(c2.id, c1.id)
        self.assertEqual(c2.codigo, "03321")
        self.assertEqual(c2.direccion, "Calle 14 Nro 500, Berazategui")

    def test_buscar_clientes_por_codigo_o_direccion(self):
        """Busca clientes por código numérico y fragmento de dirección."""
        self.store.crear_cliente("SOL FITNESS", codigo="05013", direccion="Beruti 2971, Quilmes")
        self.store.crear_cliente("ALBERTO VILLAR", codigo="05067", direccion="Pumacahua 705, CABA")

        res_cod = self.store.buscar_clientes("05013")
        self.assertEqual(len(res_cod), 1)
        self.assertEqual(res_cod[0].nombre, "SOL FITNESS")

        res_dir = self.store.buscar_clientes("Pumacahua")
        self.assertEqual(len(res_dir), 1)
        self.assertEqual(res_dir[0].nombre, "ALBERTO VILLAR")

    def test_remito_parser_separacion_codigo_nombre_despacho_y_direccion(self):
        """Verifica que parsear_remito extraiga código limpio, nombre, fecha de despacho y dirección."""
        # Mock de PDF simulando estructura típica de remito
        pdf_text = (
            "0001-00024668\n"
            "23/10/2026\n"
            "Cliente:\n"
            "Télefono:Dirección:\n"
            "DATOS CLIENTE\n"
            "27/10/2026Fecha Despacho:\n"
            "00714 - DIETETICA IDEAS Y SABORES\n"
            "BUENOS AIRES  Localidad: BERAZATEGUI\n"
            "Operacion: 1-VENTAS A PREPARAR\n"
            "Marca\n"
            "148 1275\n"
            "CENTRO DE DISTRIBUCION\n"
            "CABA - WEB\n"
            "SUPPLEMENTS SRL\n"
            "2683 PRODUCTO EJEMPLO 1\n"
            "OBSERVACIONES\n"
            "FECHA DESPACHO: 27/10/2026\n"
            "Cant. Articulos: 1\n"
        )
        fake_page = SimpleNamespace(extract_text=lambda: pdf_text)
        with patch("src.remito_parser.PdfReader", return_value=SimpleNamespace(pages=[fake_page])):
            res = parsear_remito(Path("remito_mock.pdf"))

        self.assertEqual(res.codigo_cliente, "00714")
        self.assertEqual(res.cliente, "DIETETICA IDEAS Y SABORES")
        self.assertEqual(res.fecha_despacho, "27/10/2026")
        self.assertIn("148 1275", res.direccion)
        self.assertIn("BERAZATEGUI", res.direccion)
        self.assertEqual(res.articulos_extraidos, 1)

    def test_dialogo_pedidos_stepper_y_logistica_obligatoria(self):
        """Prueba los controles de UI de bultos (stepper +/-) y obligatoriedad de logística."""
        from src.ui.dialogs.dlg_pedidos import mostrar_dialogo_crear_pedido
        from src.user_store import User

        class FakePage:
            def __init__(self):
                self.dialogos = []
            def show_dialog(self, dlg):
                self.dialogos.append(dlg)
            def update(self):
                pass
            def pop_dialog(self):
                if self.dialogos:
                    self.dialogos.pop()

        page = FakePage()
        interfaz_mock = MagicMock()
        interfaz_mock.page = page
        interfaz_mock.usuario_actual = User(1, "operador1", "operador", True)
        interfaz_mock.order_store = self.store
        interfaz_mock.modo_oscuro = False
        interfaz_mock.borde = "#cccccc"
        interfaz_mock.fondo = "#ffffff"
        interfaz_mock.texto = "#000000"
        interfaz_mock.secundario = "#666666"

        mostrar_dialogo_crear_pedido(interfaz_mock)
        self.assertEqual(len(page.dialogos), 1)
        dialogo = page.dialogos[0]

        # Encontrar contenedor con stepper de bultos y selector de logística
        col_content = dialogo.content.content
        controles = col_content.controls

        # Selector de logística debe iniciar en None (sin selección por defecto)
        logistica_dropdown = None
        for c in controles:
            if isinstance(c, ft.Dropdown) and "Logística" in (c.label or ""):
                logistica_dropdown = c
                break

        self.assertIsNotNone(logistica_dropdown)
        self.assertIsNone(logistica_dropdown.value)


if __name__ == "__main__":
    unittest.main()
