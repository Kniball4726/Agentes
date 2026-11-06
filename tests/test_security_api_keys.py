"""Tests para la capa de seguridad, sesiones persistidas, API Keys y rate limiting."""

import gc
import tempfile
import unittest
from pathlib import Path
from starlette.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import MagicMock

from src.api.v1.router import api_v1_router
from src.api.deps import (
    get_user_store,
    get_product_store,
    get_order_store,
    get_stock_manager,
    crear_sesion,
    _sesiones_activas,
)
from src.api.v1.auth import _ip_attempts, _verificar_rate_limit_ip
from src.user_store import UserStore
from src.product_store import ProductStore
from src.orders_store import OrderStore


class TestSecurityApiKeys(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        self.user_store = UserStore(self.base_path / "usuarios.sqlite3")
        self.product_store = ProductStore(self.base_path / "productos.sqlite3")
        self.order_store = OrderStore(self.base_path / "pedidos.sqlite3")

        # Admin user
        self.admin = self.user_store.create_user(
            username="admin_sec",
            password="AdminPass123!",
            role="administrador",
            nombre="Admin Seguridad",
            email="admin@sec.com",
        )
        # Operador user
        self.operador = self.user_store.create_user(
            username="oper_sec",
            password="OperPass123!",
            role="operador",
            nombre="Operador Seguridad",
            email="oper@sec.com",
        )

        with self.product_store._connect() as conn:
            conn.execute(
                "INSERT INTO products (code, name, stock, active, ubicacion) VALUES (?, ?, ?, 1, ?)",
                ("ART-001", "Martillo Acero 500g", 25, "B-02-1"),
            )

        # Configurar FastAPI de prueba
        self.app = FastAPI()
        self.app.include_router(api_v1_router)
        self.app.dependency_overrides[get_user_store] = lambda: self.user_store
        self.app.dependency_overrides[get_product_store] = lambda: self.product_store
        self.app.dependency_overrides[get_order_store] = lambda: self.order_store
        self.mock_sm = MagicMock()
        self.app.dependency_overrides[get_stock_manager] = lambda: self.mock_sm

        self.client = TestClient(self.app)
        _sesiones_activas.clear()
        _ip_attempts.clear()

    def tearDown(self):
        self.app.dependency_overrides.clear()
        _sesiones_activas.clear()
        _ip_attempts.clear()
        del self.user_store
        del self.product_store
        del self.order_store
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_persistencia_sesiones_sqlite(self):
        """Verifica que las sesiones creadas se persistan en SQLite y sobrevivan a reinicios de caché."""
        token = crear_sesion(self.admin, store=self.user_store)
        self.assertIsNotNone(token)

        # Borramos la caché en memoria para simular reinicio del servicio
        _sesiones_activas.clear()

        # Al llamar un endpoint con el token en Bearer header, debe resolverse desde SQLite
        response = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "admin_sec")

    def test_creacion_y_validacion_api_key(self):
        """Verifica el ciclo de vida de una API Key de integración (crear, validar, listar, revocar)."""
        raw_key, key_hash = self.user_store.create_api_key(
            client_name="ERP Central",
            role="operador",
        )
        self.assertTrue(raw_key.startswith("sk_live_"))
        self.assertEqual(len(key_hash), 64)

        # Validar key
        info = self.user_store.validate_api_key(raw_key)
        self.assertIsNotNone(info)
        self.assertEqual(info["client_name"], "ERP Central")
        self.assertEqual(info["role"], "operador")

        # Listar keys
        keys = self.user_store.list_api_keys()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0]["client_name"], "ERP Central")

        # Acceder a un endpoint con X-API-Key
        response = self.client.get(
            "/api/v1/productos/ART-001/stock",
            headers={"X-API-Key": raw_key},
        )
        self.assertEqual(response.status_code, 200)
        datos = response.json()
        self.assertEqual(datos["codigo"], "ART-001")
        self.assertEqual(datos["stock"], 25)
        self.assertEqual(datos["nombre"], "Martillo Acero 500g")

        # Revocar key
        revocado = self.user_store.revoke_api_key(key_hash)
        self.assertTrue(revocado)

        # Acceso posterior debe ser 401
        response2 = self.client.get(
            "/api/v1/productos/ART-001/stock",
            headers={"X-API-Key": raw_key},
        )
        self.assertEqual(response2.status_code, 401)

    def test_endpoints_gestion_api_keys(self):
        """Verifica la API REST para administradores de gestión de API Keys."""
        # Login como admin
        login_res = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin_sec", "password": "AdminPass123!"},
        )
        token_admin = login_res.json()["token"]
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        # Crear API Key
        res_create = self.client.post(
            "/api/v1/auth/api-keys?client_name=Sistema+WMS&role=operador",
            headers=headers_admin,
        )
        self.assertEqual(res_create.status_code, 200)
        data = res_create.json()
        api_key = data["api_key"]
        self.assertIn("sk_live_", api_key)

        # Listar API Keys
        res_list = self.client.get("/api/v1/auth/api-keys", headers=headers_admin)
        self.assertEqual(res_list.status_code, 200)
        keys = res_list.json()["api_keys"]
        self.assertEqual(len(keys), 1)
        key_hash = keys[0]["key_hash"]

        # Intentar crear con usuario operador (debe dar 403)
        login_oper = self.client.post(
            "/api/v1/auth/login",
            json={"username": "oper_sec", "password": "OperPass123!"},
        )
        token_oper = login_oper.json()["token"]
        res_forbidden = self.client.post(
            "/api/v1/auth/api-keys?client_name=Hacker&role=operador",
            headers={"Authorization": f"Bearer {token_oper}"},
        )
        self.assertEqual(res_forbidden.status_code, 403)

        # Revocar API Key por endpoint
        res_del = self.client.delete(f"/api/v1/auth/api-keys/{key_hash}", headers=headers_admin)
        self.assertEqual(res_del.status_code, 200)

        # Listar nuevamente: debe estar inactiva (active=0)
        res_list_after = self.client.get("/api/v1/auth/api-keys", headers=headers_admin)
        self.assertEqual(res_list_after.json()["api_keys"][0]["active"], 0)

    def test_rate_limit_ip_login(self):
        """Verifica la protección de fuerza bruta en /login (máximo 10 intentos por minuto por IP)."""
        client_ip = "192.168.1.100"
        for _ in range(10):
            _verificar_rate_limit_ip(client_ip)

        # El intento 11 debe disparar HTTPException 429
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as cm:
            _verificar_rate_limit_ip(client_ip)
        self.assertEqual(cm.exception.status_code, 429)

    def test_pragma_foreign_keys_activado(self):
        """Verifica que PRAGMA foreign_keys = ON se mantenga habilitado en OrderStore."""
        with self.order_store._connect() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys")
            row = cur.fetchone()
            self.assertEqual(row[0], 1)


if __name__ == "__main__":
    unittest.main()
