"""Tests para la API REST v1 de StockAgent."""

import tempfile
import unittest
from pathlib import Path
from starlette.testclient import TestClient
from fastapi import FastAPI

from src.api.v1.router import api_v1_router
from src.api.deps import (
    get_user_store,
    get_product_store,
    get_order_store,
    get_stock_manager,
    crear_sesion,
    _sesiones_activas,
)
from src.user_store import UserStore
from src.product_store import ProductStore
from src.orders_store import OrderStore


class TestApiV1(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        # Crear stores temporales aislados
        self.user_store = UserStore(self.base_path / "usuarios.sqlite3")
        self.product_store = ProductStore(self.base_path / "productos.sqlite3")
        self.order_store = OrderStore(self.base_path / "pedidos.sqlite3")

        # Crear usuario operador de prueba
        self.test_password = "OperadorSeguro123!"
        self.operador = self.user_store.create_user(
            username="operador_test",
            password=self.test_password,
            role="operador",
            nombre="Juan Operario",
            email="operador@test.com",
        )

        # Cargar un producto de prueba
        with self.product_store._connect() as conn:
            conn.execute(
                "INSERT INTO products (code, name, stock, active, ubicacion) VALUES (?, ?, ?, 1, ?)",
                ("PROD001", "Caja de Tornillos 1/2", 100, "A-01-1"),
            )
        self.product_store.set_product_barcode("PROD001", "7791234567890")

        # Cargar un pedido de prueba
        self.pedido = self.order_store.registrar_pedido(
            nota_pedido="0001-00012345",
            numero_pedido="NP-12345",
            cliente="Ferretería Central",
            bultos=2,
            logistica="Transporte",
            armador="Juan Operario",
            tipo_archivo="pdf",
            nombre_archivo="Remito_12345.pdf",
            articulos_descontados=5,
            items=[("PROD001", "Caja de Tornillos 1/2", 5)],
        )

        # Montar app de FastAPI con overrides de dependencias
        self.app = FastAPI()
        self.app.include_router(api_v1_router)

        self.app.dependency_overrides[get_user_store] = lambda: self.user_store
        self.app.dependency_overrides[get_product_store] = lambda: self.product_store
        self.app.dependency_overrides[get_order_store] = lambda: self.order_store

        from unittest.mock import MagicMock
        self.mock_stock_manager = MagicMock()
        self.mock_stock_manager.comparar_stock_fisico.return_value = [
            {
                "codigo": "PROD001",
                "nombre": "Caja de Tornillos 1/2",
                "stock_sistema": 100,
                "stock_fisico": 95,
                "diferencia": -5,
                "en_catalogo": True,
            }
        ]
        self.app.dependency_overrides[get_stock_manager] = lambda: self.mock_stock_manager

        self.client = TestClient(self.app)

        # Crear sesión token para el operador
        self.token = crear_sesion(self.operador)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        import gc
        _sesiones_activas.clear()
        del self.user_store
        del self.product_store
        del self.order_store
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_01_sistema_ping_y_estado(self):
        res_ping = self.client.get("/api/v1/sistema/ping")
        self.assertEqual(res_ping.status_code, 200)
        self.assertEqual(res_ping.json()["status"], "pong")

        res_estado = self.client.get("/api/v1/sistema/estado")
        self.assertEqual(res_estado.status_code, 200)
        data = res_estado.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["version"], "1.0.0")

    def test_02_auth_login_me_logout(self):
        # 1. Login exitoso
        res_login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "operador_test", "password": self.test_password},
        )
        self.assertEqual(res_login.status_code, 200)
        data_login = res_login.json()
        self.assertTrue(data_login["ok"])
        token_nuevo = data_login["token"]
        self.assertIsNotNone(token_nuevo)
        self.assertEqual(data_login["user"]["username"], "operador_test")

        # 2. Endpoint /me
        res_me = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_nuevo}"},
        )
        self.assertEqual(res_me.status_code, 200)
        self.assertEqual(res_me.json()["nombre"], "Juan Operario")

        # 3. Credenciales incorrectas
        res_fallo = self.client.post(
            "/api/v1/auth/login",
            json={"username": "operador_test", "password": "password_invalido"},
        )
        self.assertEqual(res_fallo.status_code, 401)

    def test_03_productos_buscar_y_detalle(self):
        # 1. Buscar por texto
        res_busq = self.client.get(
            "/api/v1/productos/buscar?q=Tornillos",
            headers=self.auth_headers,
        )
        self.assertEqual(res_busq.status_code, 200)
        data = res_busq.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["productos"][0]["code"], "PROD001")

        # 2. Obtener por SKU directo
        res_prod = self.client.get(
            "/api/v1/productos/PROD001",
            headers=self.auth_headers,
        )
        self.assertEqual(res_prod.status_code, 200)
        self.assertEqual(res_prod.json()["name"], "Caja de Tornillos 1/2")

        # 3. Obtener por código de barras escaneado
        res_barcode = self.client.get(
            "/api/v1/productos/7791234567890",
            headers=self.auth_headers,
        )
        self.assertEqual(res_barcode.status_code, 200)
        self.assertEqual(res_barcode.json()["code"], "PROD001")

        # 4. Actualizar ubicación física
        res_ubic = self.client.put(
            "/api/v1/productos/PROD001/ubicacion",
            json={"ubicacion": "B-05-4"},
            headers=self.auth_headers,
        )
        self.assertEqual(res_ubic.status_code, 200)
        self.assertEqual(res_ubic.json()["ubicacion"], "B-05-4")

    def test_04_despacho_listar_y_escanear_qr(self):
        # 1. Listar pedidos
        res_list = self.client.get(
            "/api/v1/despacho/pedidos",
            headers=self.auth_headers,
        )
        self.assertEqual(res_list.status_code, 200)
        data = res_list.json()
        self.assertGreaterEqual(data["total"], 1)
        self.assertEqual(data["pedidos"][0]["nota_pedido"], "0001-00012345")
        self.assertEqual(data["pedidos"][0]["estado_despacho"], "armado")

        # 2. Escaneo de QR para avanzar a DESPACHADO
        qr_string = "REMITO:0001-00012345|CLIENTE:Ferretería Central|BULTOS:2"
        res_scan = self.client.post(
            "/api/v1/despacho/escanear",
            json={"codigo": qr_string},
            headers=self.auth_headers,
        )
        self.assertEqual(res_scan.status_code, 200)
        scan_data = res_scan.json()
        self.assertTrue(scan_data["ok"])
        self.assertEqual(scan_data["pedido"]["estado_despacho"], "despachado")

        # 3. Escaneo siguiente para avanzar a ENTREGADO
        res_scan_2 = self.client.post(
            "/api/v1/despacho/escanear",
            json={"codigo": "0001-00012345"},
            headers=self.auth_headers,
        )
        self.assertEqual(res_scan_2.status_code, 200)
        self.assertEqual(res_scan_2.json()["pedido"]["estado_despacho"], "entregado")

    def test_05_inventario_comparativa(self):
        res_inv = self.client.post(
            "/api/v1/inventario/comparar-preliminar",
            json={"conteo": {"PROD001": 95}},
            headers=self.auth_headers,
        )
        self.assertEqual(res_inv.status_code, 200)
        data = res_inv.json()
        self.assertEqual(data["total_items"], 1)
        self.assertEqual(data["faltantes"], 1)
        self.assertEqual(data["items"][0]["estado"], "FALTANTE")
        self.assertEqual(data["items"][0]["diferencia"], -5)


if __name__ == "__main__":
    unittest.main()
