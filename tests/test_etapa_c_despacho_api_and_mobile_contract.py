"""Pruebas de Etapa C: despacho móvil/API con consolidación automática y contratos JSON."""

from __future__ import annotations

from contextlib import closing
from datetime import date, timedelta
import gc
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from fastapi import FastAPI
from starlette.testclient import TestClient

from src.api.deps import (
    _sesiones_activas,
    crear_sesion,
    get_order_store,
    get_product_store,
    get_user_store,
)
from src.api.v1 import despacho as api_despacho
from src.api.v1.router import api_v1_router
from src.auth import UserStore
from src.core.stock_order_tx import ejecutar_reserva_y_registro_atomico
from src.orders import OrderStore
from src.products import ProductStore


class TestEtapaCDespachoYContratosMoviles(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.user_store = UserStore(self.base / "usuarios.sqlite3")
        self.product_store = ProductStore(self.base / "productos.sqlite3")
        self.order_store = OrderStore(self.base / "pedidos.sqlite3")

        with closing(self.product_store._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO products (code, name, stock, stock_minimo, stock_maximo, active, ubicacion)
                VALUES ('MOV1', 'Cable Canal 20x10', 20, 5, 50, 1, 'A-01-2')
                """
            )
        self.product_store.asignar_ubicacion_producto(
            "MOV1", "A-01-2", tipo_zona="picking", stock=12, capacidad_max=30, es_principal=True
        )
        self.product_store.asignar_ubicacion_producto(
            "MOV1", "P-02-1", tipo_zona="pulmon", stock=8, capacidad_max=50, es_principal=False
        )
        fv = (date.today() + timedelta(days=14)).isoformat()
        self.product_store.registrar_lote(
            "MOV1", "L-MOV-1", 10, fecha_vencimiento=fv, ubicacion="A-01-2"
        )

    def tearDown(self) -> None:
        _sesiones_activas.clear()
        del self.order_store
        del self.product_store
        del self.user_store
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _crear_pedido_reservado(self, remito: str, bultos: int, cantidad: int):
        desc = [
            SimpleNamespace(
                codigo="MOV1",
                nombre_producto="Cable Canal 20x10",
                stock_anterior=20,
                cantidad_descontada=cantidad,
                stock_nuevo=20 - cantidad,
            )
        ]
        sm_fake = SimpleNamespace(product_store=self.product_store)
        rep_fake = SimpleNamespace(
            reporte_stock=SimpleNamespace(descuentos_aplicados=desc),
            documentos_verificados=[],
        )
        _, _, _, pedido, _ = ejecutar_reserva_y_registro_atomico(
            order_store=self.order_store,
            stock_mgr_factory=lambda: (sm_fake, rep_fake),
            tx_id=f"TX_{remito}",
            remito=remito,
            num_ped=remito,
            cli="Cliente Móvil",
            bultos_val=bultos,
            log="Domicilio",
            f_retiro="Sin fecha",
            armador_nom="Operario Web",
            es_agregado=False,
            tipo_archivo="pdf",
            nombre_archivo=f"{remito}.pdf",
            hash_comprobante=f"h_{remito}",
        )
        return pedido

    def test_01_escanear_despacho_consolida_reserva_pedido_al_despachar(self) -> None:
        desp = self.user_store.create_user(
            username="desp_mov", password="Password123!", role="despachador", nombre="Desp Móvil"
        )
        headers = {"Authorization": f"Bearer {crear_sesion(desp)}"}
        app = FastAPI()
        app.include_router(api_v1_router)
        app.dependency_overrides[get_user_store] = lambda: self.user_store
        app.dependency_overrides[get_order_store] = lambda: self.order_store
        app.dependency_overrides[get_product_store] = lambda: self.product_store
        client = TestClient(app)

        self._crear_pedido_reservado("0001-00050001", bultos=2, cantidad=6)
        self.assertEqual(self.product_store.obtener_resumen_stock_disponible("MOV1")["stock_reservado"], 6)

        # Escaneo bulto 1/2: sigue armado, NO consolida todavía
        r1 = client.post(
            "/api/v1/despacho/escanear",
            json={"codigo": "REMITO:0001-00050001|BULTO:1/2"},
            headers=headers,
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["pedido"]["estado_despacho"], "armado")
        self.assertEqual(self.product_store.obtener_resumen_stock_disponible("MOV1")["stock_fisico"], 20)
        self.assertEqual(self.product_store.obtener_resumen_stock_disponible("MOV1")["stock_reservado"], 6)

        # Escaneo bulto 2/2: pasa a despachado y consolida la reserva descontando stock y lote FEFO
        r2 = client.post(
            "/api/v1/despacho/escanear",
            json={"codigo": "REMITO:0001-00050001|BULTO:2/2"},
            headers=headers,
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["pedido"]["estado_despacho"], "despachado")
        resumen = self.product_store.obtener_resumen_stock_disponible("MOV1")
        self.assertEqual(resumen["stock_fisico"], 14)
        self.assertEqual(resumen["stock_reservado"], 0)
        self.assertEqual(resumen["stock_disponible"], 14)
        lote = self.product_store.listar_lotes_fefo("MOV1")[0]
        self.assertEqual(lote["stock"], 4)

    def test_02_escanear_lote_offline_consolida_reservas_y_tolera_entorno_aislado(self) -> None:
        op = self.user_store.create_user(
            username="op_mov", password="Password123!", role="operador", nombre="Op Móvil"
        )
        headers = {"Authorization": f"Bearer {crear_sesion(op)}"}

        # 1) Sin get_product_store configurado no rompe escaneo
        app_sin_ps = FastAPI()
        app_sin_ps.include_router(api_despacho.router, prefix="/api/v1")
        app_sin_ps.dependency_overrides[get_user_store] = lambda: self.user_store
        app_sin_ps.dependency_overrides[get_order_store] = lambda: self.order_store
        client_sin = TestClient(app_sin_ps)

        self._crear_pedido_reservado("0001-00050002", bultos=1, cantidad=5)
        r_ok = client_sin.post(
            "/api/v1/despacho/escanear",
            json={"codigo": "0001-00050002", "nuevo_estado": "despachado"},
            headers=headers,
        )
        self.assertEqual(r_ok.status_code, 200)
        self.assertTrue(r_ok.json()["ok"])

        # 2) En lote offline con get_product_store activo consolida correctamente
        self._crear_pedido_reservado("0001-00050003", bultos=1, cantidad=4)
        app_full = FastAPI()
        app_full.include_router(api_v1_router)
        app_full.dependency_overrides[get_user_store] = lambda: self.user_store
        app_full.dependency_overrides[get_order_store] = lambda: self.order_store
        app_full.dependency_overrides[get_product_store] = lambda: self.product_store
        client_full = TestClient(app_full)

        r_batch = client_full.post(
            "/api/v1/despacho/escanear-lote",
            json={"items": [{"codigo": "0001-00050003", "nuevo_estado": "despachado"}]},
            headers=headers,
        )
        self.assertEqual(r_batch.status_code, 200)
        self.assertEqual(r_batch.json()["exitosos"], 1)
        self.assertEqual(self.product_store.obtener_resumen_stock_disponible("MOV1")["stock_fisico"], 16)

    def test_03_contrato_json_flutter_product_locations_lotes_reservas(self) -> None:
        op = self.user_store.create_user(
            username="picker_mov", password="Password123!", role="picker", nombre="Picker Móvil"
        )
        headers = {"Authorization": f"Bearer {crear_sesion(op)}"}
        app = FastAPI()
        app.include_router(api_v1_router)
        app.dependency_overrides[get_user_store] = lambda: self.user_store
        app.dependency_overrides[get_order_store] = lambda: self.order_store
        app.dependency_overrides[get_product_store] = lambda: self.product_store
        client = TestClient(app)

        self.product_store.reservar_stock({"MOV1": 3}, referencia_id="OLA-MOV-1", referencia_tipo="ola_picking")

        # ProductItem campos esperados por ProductItem.fromJson
        prod_json = client.get("/api/v1/productos/MOV1", headers=headers).json()
        for k in ("code", "name", "stock", "stock_fisico", "stock_reservado", "stock_disponible", "ubicacion"):
            self.assertIn(k, prod_json)
        self.assertEqual(prod_json["stock_reservado"], 3)
        self.assertEqual(prod_json["stock_disponible"], 17)

        # ProductLocationsSummary campos esperados por ProductLocationsSummary.fromJson
        loc_json = client.get("/api/v1/productos/MOV1/ubicaciones", headers=headers).json()
        for k in ("product_code", "product_name", "stock_fisico", "stock_reservado", "stock_disponible", "ubicaciones"):
            self.assertIn(k, loc_json)
        self.assertEqual(len(loc_json["ubicaciones"]), 2)
        for k in ("id", "product_code", "ubicacion", "tipo_zona", "stock", "capacidad_max", "es_principal"):
            self.assertIn(k, loc_json["ubicaciones"][0])

        # StockLot campos esperados por StockLot.fromJson
        alert_json = client.get("/api/v1/productos/lotes/proximos-vencer?dias=30", headers=headers).json()
        self.assertGreaterEqual(alert_json["total"], 1)
        for k in ("id", "product_code", "product_name", "lote", "ubicacion", "fecha_vencimiento", "stock", "estado", "dias_para_vencer", "vencido", "nivel_alerta"):
            self.assertIn(k, alert_json["lotes"][0])

        # StockReservation campos esperados por StockReservation.fromJson
        res_json = client.get("/api/v1/productos/reservas", headers=headers).json()
        self.assertEqual(res_json["total"], 1)
        for k in ("id", "referencia_tipo", "referencia_id", "product_code", "product_name", "cantidad", "estado", "ubicacion", "usuario", "nota"):
            self.assertIn(k, res_json["reservas"][0])


if __name__ == "__main__":
    unittest.main()
