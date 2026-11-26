"""Pruebas integrales de Fase 4: reservas de stock, multi-ubicación y trazabilidad FEFO."""

from __future__ import annotations

from contextlib import closing
from datetime import date, timedelta
import gc
from pathlib import Path
import sqlite3
import tempfile
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
from src.api.v1.router import api_v1_router
from src.auth import UserStore
from src.core.exceptions import InsufficientStockError
from src.core.sqlite_migrations import aplicar_migraciones_sqlite
from src.orders import (
    OrderStore,
    consolidar_ola_picking,
    consolidar_y_despachar_ola_picking,
    crear_y_reservar_ola_picking,
    liberar_ola_picking,
)
from src.products import ProductStore
from src.products.schema import PRODUCTS_SCHEMA_VERSION, _PRODUCTS_MIGRATION_STEPS
from src.warehouse_slotting import generar_sugerencias_reposicion_picking


class TestFase4WarehouseEvolution(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.product_store = ProductStore(self.base_path / "productos.sqlite3")
        self.order_store = OrderStore(self.base_path / "pedidos.sqlite3")
        self.user_store = UserStore(self.base_path / "usuarios.sqlite3")

        with closing(self.product_store._connect()) as conn, conn:
            conn.executemany(
                """
                INSERT INTO products (code, name, stock, stock_minimo, stock_maximo, active, ubicacion)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                [
                    ("SKU1", "Tornillo Hexagonal M8", 10, 5, 25, "A-01-1"),
                    ("SKU2", "Tuerca Autofrenante M8", 6, 3, 15, "A-01-2"),
                    ("SKU3", "Sellador Siliconado 300ml", 100, 10, 80, "B-02-1"),
                ],
            )
        # Reflejar el alta en product_locations como ocurre tras migración/asignación
        self.product_store.asignar_ubicacion_producto(
            "SKU1", "A-01-1", tipo_zona="picking", stock=10, capacidad_max=25, es_principal=True
        )
        self.product_store.asignar_ubicacion_producto(
            "SKU2", "A-01-2", tipo_zona="picking", stock=6, capacidad_max=15, es_principal=True
        )
        self.product_store.asignar_ubicacion_producto(
            "SKU3", "B-02-1", tipo_zona="picking", stock=100, capacidad_max=80, es_principal=True
        )

    def tearDown(self) -> None:
        _sesiones_activas.clear()
        del self.user_store
        del self.order_store
        del self.product_store
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_01_migracion_v3_a_v4_crea_tablas_y_backfill_ubicaciones(self) -> None:
        db_v3 = self.base_path / "legacy_v3.sqlite3"
        with closing(sqlite3.connect(db_v3)) as conn:
            conn.row_factory = sqlite3.Row
            aplicar_migraciones_sqlite(
                conn,
                db_v3,
                _PRODUCTS_MIGRATION_STEPS[:3],
                domain="products",
            )
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], 3
            )
            conn.execute(
                "INSERT INTO products (code, name, stock, active, ubicacion) VALUES ('LEG1', 'Item Legacy', 30, 1, '  c-03-2  ')"
            )
            conn.execute(
                "INSERT INTO products (code, name, stock, active, ubicacion) VALUES ('LEG2', 'Item Sin Ubic', 15, 1, '')"
            )
            conn.commit()

        migrated_store = ProductStore(db_v3)
        with closing(migrated_store._connect()) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, PRODUCTS_SCHEMA_VERSION)
            self.assertEqual(version, 4)

        ubics_leg1 = migrated_store.listar_ubicaciones_producto("LEG1")
        self.assertEqual(len(ubics_leg1), 1)
        self.assertEqual(ubics_leg1[0]["ubicacion"], "C-03-2")
        self.assertEqual(ubics_leg1[0]["tipo_zona"], "picking")
        self.assertEqual(ubics_leg1[0]["stock"], 30)
        self.assertTrue(ubics_leg1[0]["es_principal"])
        self.assertEqual(migrated_store.listar_ubicaciones_producto("LEG2"), [])

        backups = list((self.base_path / "backups_migraciones").glob("legacy_v3_v3_a_v4_*.sqlite3"))
        self.assertTrue(backups, "La migración v3->v4 debe crear un respaldo automático.")
        del migrated_store

    def test_02_reservas_evitan_sobreasignacion_y_ciclo_consolidar_liberar(self) -> None:
        ped1 = self.order_store.registrar_pedido(
            nota_pedido="0001-0001",
            numero_pedido="NP-1",
            cliente="Cliente Uno",
            bultos=1,
            logistica="Transporte",
            armador="Operario A",
            tipo_archivo="pdf",
            nombre_archivo="R1.pdf",
            articulos_descontados=7,
            items=[("SKU1", "Tornillo Hexagonal M8", 7)],
        )
        ped2 = self.order_store.registrar_pedido(
            nota_pedido="0001-0002",
            numero_pedido="NP-2",
            cliente="Cliente Dos",
            bultos=1,
            logistica="Domicilio",
            armador="Operario B",
            tipo_archivo="pdf",
            nombre_archivo="R2.pdf",
            articulos_descontados=5,
            items=[("SKU1", "Tornillo Hexagonal M8", 5)],
        )

        # Operador 1 reserva Ola 1 (7 de 10 unidades)
        ola1 = crear_y_reservar_ola_picking(
            self.order_store,
            [ped1],
            self.product_store,
            referencia_id="OLA-001",
            usuario="operario_a",
        )
        self.assertEqual(ola1["reserva"]["total_unidades_reservadas"], 7)

        resumen = self.product_store.obtener_resumen_stock_disponible("SKU1")
        self.assertEqual(resumen["stock_fisico"], 10)
        self.assertEqual(resumen["stock_reservado"], 7)
        self.assertEqual(resumen["stock_disponible"], 3)

        # Re-reserva idempotente para la misma referencia no se bloquea a sí misma
        ola1_dup = crear_y_reservar_ola_picking(
            self.order_store,
            [ped1],
            self.product_store,
            referencia_id="OLA-001",
            usuario="operario_a",
        )
        self.assertEqual(ola1_dup["reserva"]["total_unidades_reservadas"], 7)

        # Operador 2 intenta preparar Ola 2 (pide 5 cuando quedan 3 disponibles) -> bloqueo atómico
        with self.assertRaises(InsufficientStockError):
            crear_y_reservar_ola_picking(
                self.order_store,
                [ped2],
                self.product_store,
                referencia_id="OLA-002",
                usuario="operario_b",
            )

        # consolidar_ola_picking refleja disponibilidad real restante (10 fís, 7 res, 3 disp)
        vista_ola2 = consolidar_ola_picking(self.order_store, [ped2], product_store=self.product_store)
        self.assertEqual(vista_ola2[0]["stock_fisico"], 10)
        self.assertEqual(vista_ola2[0]["stock_reservado"], 7)
        self.assertEqual(vista_ola2[0]["stock_disponible"], 3)

        # Liberar Ola 1 devuelve las 7 unidades al disponible
        lib = liberar_ola_picking(self.product_store, "OLA-001", motivo="Reprogramación")
        self.assertEqual(lib["unidades_liberadas"], 7)
        self.assertEqual(self.product_store.obtener_resumen_stock_disponible("SKU1")["stock_disponible"], 10)

        # Ahora Ola 2 sí puede reservar y consolidar descontando stock físico real
        crear_y_reservar_ola_picking(
            self.order_store,
            [ped2],
            self.product_store,
            referencia_id="OLA-002",
            usuario="operario_b",
        )
        cons = consolidar_y_despachar_ola_picking(
            self.product_store, "OLA-002", descontar_stock=True, usuario="operario_b"
        )
        self.assertEqual(cons["unidades_consolidadas"], 5)

        resumen_final = self.product_store.obtener_resumen_stock_disponible("SKU1")
        self.assertEqual(resumen_final["stock_fisico"], 5)
        self.assertEqual(resumen_final["stock_reservado"], 0)
        self.assertEqual(resumen_final["stock_disponible"], 5)

    def test_03_multiubicacion_transferencias_y_reposicion_slotting(self) -> None:
        # Configurar picking bajo en SKU1 y stock en pulmón/pallet
        self.product_store.asignar_ubicacion_producto(
            "SKU1", "A-01-1", tipo_zona="picking", stock=2, capacidad_max=20, es_principal=True
        )
        self.product_store.asignar_ubicacion_producto(
            "SKU1", "P-01-1", tipo_zona="pulmon", stock=40, capacidad_max=100, es_principal=False
        )
        self.product_store.asignar_ubicacion_producto(
            "SKU1", "PAL-02", tipo_zona="pallet", stock=80, capacidad_max=200, es_principal=False
        )

        # Actualizar ubicación principal en catálogo sincroniza product_locations sin perder stock
        self.assertTrue(self.product_store.actualizar_ubicacion("SKU1", "A-01-3"))
        ubics = self.product_store.listar_ubicaciones_producto("SKU1")
        principal = [u for u in ubics if u["es_principal"]][0]
        self.assertEqual(principal["ubicacion"], "A-01-3")
        self.assertEqual(principal["stock"], 2)

        # Lote FEFO próximo a vencer alojado en pulmón
        vto_proximo = (date.today() + timedelta(days=10)).isoformat()
        self.product_store.registrar_lote(
            "SKU1", "L-PULMON-1", 25, fecha_vencimiento=vto_proximo, ubicacion="P-01-1"
        )

        sugerencias = generar_sugerencias_reposicion_picking(
            self.product_store, dias_alerta_vencimiento=30
        )
        sug_sku1 = [s for s in sugerencias if s.product_code == "SKU1"]
        self.assertEqual(len(sug_sku1), 1)
        self.assertEqual(sug_sku1[0].ubicacion_origen, "P-01-1")
        self.assertEqual(sug_sku1[0].ubicacion_destino, "A-01-3")
        self.assertEqual(sug_sku1[0].prioridad, "URGENTE")
        self.assertEqual(sug_sku1[0].lote_fefo, "L-PULMON-1")

        # Transferencia interna pulmón -> picking traslada bins y lote FEFO
        traslado = self.product_store.transferir_entre_ubicaciones(
            "SKU1", "P-01-1", "A-01-3", 10
        )
        self.assertEqual(traslado["origen"]["stock"], 30)
        self.assertEqual(traslado["destino"]["stock"], 12)
        self.assertEqual(len(traslado["lotes_trasladados"]), 1)
        self.assertEqual(traslado["lotes_trasladados"][0]["lote"], "L-PULMON-1")
        self.assertEqual(traslado["lotes_trasladados"][0]["cantidad"], 10)

        # Transferencia mayor al disponible en origen falla sin corromper saldos
        with self.assertRaises(InsufficientStockError):
            self.product_store.transferir_entre_ubicaciones("SKU1", "P-01-1", "A-01-3", 999)

    def test_04_lotes_fefo_estricto_y_alertas_vencimiento(self) -> None:
        hoy = date.today()
        ayer = (hoy - timedelta(days=1)).isoformat()
        en_7_dias = (hoy + timedelta(days=7)).strftime("%d/%m/%Y")  # Verifica normalización DD/MM/YYYY
        en_5_dias = (hoy + timedelta(days=5)).isoformat()
        en_90_dias = (hoy + timedelta(days=90)).isoformat()

        self.product_store.registrar_lote("SKU3", "L-VENCIDO", 15, fecha_vencimiento=ayer, ubicacion="B-02-1")
        self.product_store.registrar_lote("SKU3", "L-LARGO", 30, fecha_vencimiento=en_90_dias, ubicacion="B-02-1")
        self.product_store.registrar_lote("SKU3", "L-SIN-VENC", 20, fecha_vencimiento="", ubicacion="B-02-1")
        self.product_store.registrar_lote("SKU3", "L-CORTO", 10, fecha_vencimiento=en_7_dias, ubicacion="B-02-1")

        ordenados = self.product_store.listar_lotes_fefo("SKU3", solo_disponibles=True)
        self.assertEqual(
            [l["lote"] for l in ordenados],
            ["L-VENCIDO", "L-CORTO", "L-LARGO", "L-SIN-VENC"],
        )
        self.assertTrue(ordenados[0]["vencido"])
        self.assertEqual(ordenados[1]["fecha_vencimiento"], (hoy + timedelta(days=7)).isoformat())

        # Reservar y consolidar 25 u. debe omitir L-VENCIDO, agotar L-CORTO (10) y descontar 15 de L-LARGO
        self.product_store.reservar_stock({"SKU3": 25}, referencia_id="OLA-FEFO-1", asignar_fefo=True)
        cons = self.product_store.consolidar_reserva("OLA-FEFO-1", descontar_stock=True)
        consumidos = cons["items"][0]["lotes_consumidos"]
        self.assertEqual(
            [(c["lote"], c["cantidad"]) for c in consumidos],
            [("L-CORTO", 10), ("L-LARGO", 15)],
        )

        # Verificar estados y saldos resultantes tras consumo FEFO
        lotes_despues = {l["lote"]: l for l in self.product_store.listar_lotes_fefo("SKU3")}
        self.assertEqual(lotes_despues["L-CORTO"]["stock"], 0)
        self.assertEqual(lotes_despues["L-CORTO"]["estado"], "agotado")
        self.assertEqual(lotes_despues["L-LARGO"]["stock"], 15)
        self.assertEqual(lotes_despues["L-VENCIDO"]["stock"], 15)
        self.assertEqual(self.product_store.obtener_resumen_stock_disponible("SKU3")["stock_fisico"], 75)

        # Registrar otro lote crítico (+5 días) y comprobar endpoint lógico de alertas
        self.product_store.registrar_lote("SKU3", "L-CRITICO", 8, fecha_vencimiento=en_5_dias, ubicacion="B-02-1")
        alertas = self.product_store.listar_lotes_proximos_vencer(dias=30, incluir_vencidos=True)
        niveles = {a["lote"]: a["nivel_alerta"] for a in alertas}
        self.assertEqual(niveles.get("L-VENCIDO"), "VENCIDO")
        self.assertEqual(niveles.get("L-CRITICO"), "CRITICO")
        self.assertNotIn("L-LARGO", niveles)

    def test_05_api_v1_endpoints_reservas_ubicaciones_y_fefo(self) -> None:
        op = self.user_store.create_user(
            username="op_f4", password="PasswordF4!", role="operador", nombre="Operador Fase4"
        )
        cons_user = self.user_store.create_user(
            username="lectura_f4", password="PasswordF4!", role="consulta", nombre="Solo Lectura"
        )
        headers_op = {"Authorization": f"Bearer {crear_sesion(op)}"}
        headers_consulta = {"Authorization": f"Bearer {crear_sesion(cons_user)}"}

        app = FastAPI()
        app.include_router(api_v1_router)
        app.dependency_overrides[get_user_store] = lambda: self.user_store
        app.dependency_overrides[get_product_store] = lambda: self.product_store
        app.dependency_overrides[get_order_store] = lambda: self.order_store
        client = TestClient(app)

        # 1. Rol consulta no puede mutar reservas/ubicaciones/lotes
        r_forb = client.post(
            "/api/v1/productos/reservas",
            json={"referencia_id": "OLA-DENEGADA", "items": [{"codigo": "SKU1", "cantidad": 2}]},
            headers=headers_consulta,
        )
        self.assertEqual(r_forb.status_code, 403)

        # 2. Crear reserva vía API y validar stock disponible vs reservado
        r_res = client.post(
            "/api/v1/productos/reservas",
            json={
                "referencia_id": "OLA-API-1",
                "items": [{"codigo": "SKU1", "cantidad": 6}],
                "nota": "Preparación prioritaria",
            },
            headers=headers_op,
        )
        self.assertEqual(r_res.status_code, 200)
        self.assertEqual(r_res.json()["total_unidades_reservadas"], 6)

        r_list_res = client.get("/api/v1/productos/reservas", headers=headers_op)
        self.assertEqual(r_list_res.status_code, 200)
        self.assertEqual(r_list_res.json()["total"], 1)

        r_prod = client.get("/api/v1/productos/SKU1", headers=headers_op)
        self.assertEqual(r_prod.status_code, 200)
        self.assertEqual(r_prod.json()["stock"], 10)
        self.assertEqual(r_prod.json()["stock_reservado"], 6)
        self.assertEqual(r_prod.json()["stock_disponible"], 4)

        r_stock = client.get("/api/v1/productos/SKU1/stock", headers=headers_op)
        self.assertEqual(r_stock.status_code, 200)
        self.assertEqual(r_stock.json()["stock_disponible"], 4)

        # 3. Conflicto 409 al intentar reservar más del disponible
        r_conflicto = client.post(
            "/api/v1/productos/reservas",
            json={"referencia_id": "OLA-API-2", "items": [{"codigo": "SKU1", "cantidad": 5}]},
            headers=headers_op,
        )
        self.assertEqual(r_conflicto.status_code, 409)

        # 4. Multi-ubicación + transferencia HTTP
        r_asig = client.post(
            "/api/v1/productos/SKU1/ubicaciones",
            json={"ubicacion": "P-09-1", "tipo_zona": "pulmon", "stock": 15, "capacidad_max": 50},
            headers=headers_op,
        )
        self.assertEqual(r_asig.status_code, 200)

        r_transf = client.post(
            "/api/v1/productos/SKU1/ubicaciones/transferir",
            json={"origen": "P-09-1", "destino": "A-01-1", "cantidad": 5},
            headers=headers_op,
        )
        self.assertEqual(r_transf.status_code, 200)
        self.assertEqual(r_transf.json()["origen"]["stock"], 10)
        self.assertEqual(r_transf.json()["destino"]["stock"], 15)

        # 5. Lotes FEFO y alertas HTTP
        fv_1 = (date.today() + timedelta(days=12)).isoformat()
        fv_2 = (date.today() + timedelta(days=40)).isoformat()
        self.assertEqual(
            client.post(
                "/api/v1/productos/SKU2/lotes",
                json={"lote": "L-API-A", "cantidad": 4, "fecha_vencimiento": fv_1},
                headers=headers_op,
            ).status_code,
            200,
        )
        self.assertEqual(
            client.post(
                "/api/v1/productos/SKU2/lotes",
                json={"lote": "L-API-B", "cantidad": 5, "fecha_vencimiento": fv_2},
                headers=headers_op,
            ).status_code,
            200,
        )

        r_alert = client.get("/api/v1/productos/lotes/proximos-vencer?dias=20", headers=headers_op)
        self.assertEqual(r_alert.status_code, 200)
        self.assertTrue(any(l["lote"] == "L-API-A" for l in r_alert.json()["lotes"]))

        r_cons_lote = client.post(
            "/api/v1/productos/SKU2/lotes/consumir-fefo",
            json={"cantidad": 5, "descontar_stock_producto": True},
            headers=headers_op,
        )
        self.assertEqual(r_cons_lote.status_code, 200)
        self.assertEqual(
            [(c["lote"], c["cantidad"]) for c in r_cons_lote.json()["consumos"]],
            [("L-API-A", 4), ("L-API-B", 1)],
        )

        # 6. Consolidar reserva API descontando stock
        r_consolidar = client.post(
            "/api/v1/productos/reservas/consolidar",
            json={"referencia_id": "OLA-API-1", "descontar_stock": True},
            headers=headers_op,
        )
        self.assertEqual(r_consolidar.status_code, 200)
        self.assertEqual(r_consolidar.json()["unidades_consolidadas"], 6)
        self.assertEqual(
            client.get("/api/v1/productos/SKU1/stock", headers=headers_op).json()["stock"],
            4,
        )


if __name__ == "__main__":
    unittest.main()
