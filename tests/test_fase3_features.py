"""Tests unitarios para las funcionalidades de la Fase 3:
1. Módulo conector oficial con la API REST de Mercado Libre.
2. Renovación OAuth y verificación de credenciales (/users/me).
3. Consulta de órdenes recientes pagadas (/orders/search).
4. Emparejamiento inteligente de ítems (SKU prioritario + fuzzy semántico de títulos).
5. Descuento atómico de stock, prevención de duplicados y generación de comprobante .docx.
"""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import openpyxl

from src.mercado_libre_api import (
    cargar_config_mercadolibre,
    consultar_ordenes_ml,
    descontar_orden_ml_api,
    guardar_config_mercadolibre,
    mapear_orden_ml_a_items,
    renovar_token_ml,
    verificar_credenciales_ml,
)
from src.orders_store import OrderStore
from src.stock_manager import StockManager


class TestFase3Features(unittest.TestCase):
    def test_config_mercadolibre_carga_y_guarda(self):
        """Verifica la persistencia y carga de la configuración de Mercado Libre API."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            # 1. Configuración por defecto
            cfg_def = cargar_config_mercadolibre(tmp_root)
            self.assertEqual(cfg_def["app_id"], "")
            self.assertEqual(cfg_def["access_token"], "")
            self.assertFalse(cfg_def["activo"])
            self.assertEqual(cfg_def["filtro_estado"], "paid")

            # 2. Guardar nueva configuración
            nueva = {
                "app_id": "123456789",
                "client_secret": "SEC_TEST_999",
                "seller_id": "987654321",
                "access_token": "APP_USR-TEST-TOKEN",
                "refresh_token": "TG-TEST-REFRESH",
                "activo": True,
                "filtro_estado": "paid",
                "horas_atras": 24,
                "auto_descontar": False,
                "ultima_sincronizacion": "2026-10-29T20:00:00",
            }
            guardar_config_mercadolibre(nueva, tmp_root)

            # 3. Recargar y verificar
            cfg_cargada = cargar_config_mercadolibre(tmp_root)
            self.assertEqual(cfg_cargada["app_id"], "123456789")
            self.assertEqual(cfg_cargada["access_token"], "APP_USR-TEST-TOKEN")
            self.assertEqual(cfg_cargada["seller_id"], "987654321")
            self.assertTrue(cfg_cargada["activo"])

    def test_verificar_credenciales_ml_sin_token(self):
        """Valida que intentar verificar sin token falle limpiamente."""
        ok, msg, data = verificar_credenciales_ml({"access_token": ""})
        self.assertFalse(ok)
        self.assertIn("Falta ingresar el Access Token", msg)
        self.assertEqual(data, {})

    def test_verificar_credenciales_ml_con_mock_exitoso(self):
        """Valida la verificación exitosa de credenciales mediante mock de /users/me."""
        mock_data = {
            "id": 987654321,
            "nickname": "TIENDA_OFICIAL_ML",
            "email": "ventas@tiendaoficial.com",
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            cfg = {"access_token": "VALID_TOKEN", "seller_id": ""}
            ok, msg, data = verificar_credenciales_ml(cfg)
            self.assertTrue(ok)
            self.assertIn("TIENDA_OFICIAL_ML", msg)
            self.assertEqual(data["id"], 987654321)
            # Verifica que asignó automáticamente el seller_id
            self.assertEqual(cfg["seller_id"], "987654321")

    def test_renovar_token_ml_con_mock(self):
        """Valida la renovación de token OAuth mediante POST mockeado a /oauth/token."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            mock_oauth_resp = {
                "access_token": "NUEVO_ACCESS_TOKEN_123",
                "refresh_token": "NUEVO_REFRESH_TOKEN_456",
                "user_id": 987654321,
                "expires_in": 21600,
            }
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_oauth_resp).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp

            cfg = {
                "app_id": "APP_123",
                "client_secret": "SEC_123",
                "refresh_token": "OLD_REFRESH",
                "access_token": "OLD_ACCESS",
            }
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ok, msg, nuevo_tok = renovar_token_ml(cfg, root_path=tmp_root)
                self.assertTrue(ok)
                self.assertEqual(nuevo_tok, "NUEVO_ACCESS_TOKEN_123")
                self.assertEqual(cfg["access_token"], "NUEVO_ACCESS_TOKEN_123")
                self.assertEqual(cfg["refresh_token"], "NUEVO_REFRESH_TOKEN_456")

    def test_consultar_ordenes_ml_con_mock(self):
        """Valida la consulta y recepción de órdenes pagadas desde /orders/search."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            mock_orders_resp = {
                "results": [
                    {
                        "id": 2000009999,
                        "date_created": "2026-10-29T18:00:00.000-03:00",
                        "status": "paid",
                        "buyer": {"id": 111, "nickname": "COMPRADOR_UNO", "first_name": "Carlos", "last_name": "Gomez"},
                        "shipping": {"id": 8888, "shipping_mode": "me2"},
                        "order_items": [
                            {
                                "item": {"id": "MLA1", "title": "Creatina 300g", "seller_sku": "101"},
                                "quantity": 2,
                                "unit_price": 20000.0,
                            }
                        ],
                    }
                ]
            }
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_orders_resp).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp

            cfg = {"access_token": "TOK", "seller_id": "123", "filtro_estado": "paid"}
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ok, msg, ordenes = consultar_ordenes_ml(cfg, horas=24, root_path=tmp_root)
                self.assertTrue(ok)
                self.assertEqual(len(ordenes), 1)
                self.assertEqual(ordenes[0]["id"], 2000009999)

    def test_mapear_orden_ml_a_items_prioridad_sku_y_fuzzy(self):
        """Verifica que el mapeo empareje por SKU prioritario y aplique fuzzy matching por título."""
        catalogo = {
            "101": (3, "Creatina Micronizada 300g", 25),
            "102": (4, "Proteina Whey 1kg", 15),
        }
        orden_mock = {
            "id": 2000001234,
            "date_created": "2026-10-29T19:30:00.000-03:00",
            "buyer": {"first_name": "Mariana", "last_name": "Lopez", "nickname": "MARI_LPZ"},
            "shipping": {"id": 444555, "shipping_mode": "me2"},
            "order_items": [
                # Caso 1: Tiene seller_sku explícito que coincide con "101"
                {
                    "item": {"id": "MLA101", "title": "Cualquier Título Publicación", "seller_sku": "101"},
                    "quantity": 3,
                    "unit_price": 18000.0,
                },
                # Caso 2: Sin SKU, pero título coincide con "Proteina Whey 1kg"
                {
                    "item": {"id": "MLA102", "title": "Proteina Whey 1kg", "seller_sku": ""},
                    "quantity": 1,
                    "unit_price": 32000.0,
                },
            ],
        }

        res = mapear_orden_ml_a_items(orden_mock, catalogo)
        self.assertEqual(res["orden_id"], "2000001234")
        self.assertEqual(res["ref_pedido"], "ML-2000001234")
        self.assertEqual(res["cliente"], "Mariana Lopez")
        self.assertEqual(res["total_unidades"], 4)
        self.assertEqual(res["total_importe"], 3 * 18000.0 + 1 * 32000.0)
        self.assertTrue(res["todos_coinciden"])
        self.assertTrue(res["stock_suficiente"])
        self.assertEqual(len(res["items_coincidentes"]), 2)
        self.assertEqual(res["items_coincidentes"][0]["metodo"], "SKU")
        self.assertEqual(res["items_coincidentes"][1]["metodo"], "Fuzzy Título")

    def test_descontar_orden_ml_api_y_registro_pedidos(self):
        """Verifica el descuento atómico de stock en SQLite, registro en OrderStore y creación del docx."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            ruta_excel = tmp_root / "Productos.xlsx"
            ruta_db_prod = tmp_root / "productos.sqlite3"
            ruta_db_orders = tmp_root / "pedidos.sqlite3"

            # 1. Crear Excel base (fila 1: encabezados, fila 2: vacía, fila 3: datos)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Productos"
            ws.append(["Codigo", "Nombre", "Stock", "Precio", "Stock Min", "Stock Max", "Cod Barras"])
            ws.append([])
            ws.append(["101", "Creatina Micronizada 300g", 20, 15000, 5, 50, "779101"])
            ws.append(["102", "Proteina Whey 1kg", 10, 25000, 2, 20, "779102"])
            wb.save(ruta_excel)
            wb.close()

            # 2. Inicializar StockManager y OrderStore
            sm = StockManager(ruta_excel, ruta_base_datos=ruta_db_prod)
            order_store = OrderStore(ruta_db_orders)

            # 3. Preparar orden ya mapeada
            orden_mapeada = {
                "orden_id": "2000005555",
                "ref_pedido": "ML-2000005555",
                "cliente": "Roberto Gomez",
                "fecha": "2026-10-29 20:15:00",
                "shipping_id": "999888777",
                "total_unidades": 4,
                "total_importe": 70000.0,
                "items_coincidentes": [
                    {
                        "codigo": "101",
                        "nombre": "Creatina Micronizada 300g",
                        "cantidad": 3,
                        "stock_actual": 20,
                        "precio": 15000.0,
                        "fila": 3,
                    },
                    {
                        "codigo": "102",
                        "nombre": "Proteina Whey 1kg",
                        "cantidad": 1,
                        "stock_actual": 10,
                        "precio": 25000.0,
                        "fila": 4,
                    },
                ],
                "items_no_coincidentes": [],
            }

            # 4. Ejecutar descuento por API
            exito, msg = descontar_orden_ml_api(
                orden_mapeada,
                stock_manager=sm,
                order_store=order_store,
                armador="OperadorTest",
                root_path=tmp_root,
            )
            self.assertTrue(exito)
            self.assertIn("descontada con éxito", msg)

            # 5. Verificar saldos descontados en SQLite
            prod_101 = sm.buscar_producto_por_codigo_o_barras("101")
            prod_102 = sm.buscar_producto_por_codigo_o_barras("102")
            self.assertIsNotNone(prod_101)
            self.assertIsNotNone(prod_102)
            self.assertEqual(int(prod_101["stock"]), 17)  # 20 - 3
            self.assertEqual(int(prod_102["stock"]), 9)   # 10 - 1

            # 6. Verificar registro en OrderStore
            self.assertTrue(order_store.existe_nota_pedido("ML-2000005555"))
            pedido_db = order_store.buscar_pedido_por_nota("ML-2000005555")
            self.assertIsNotNone(pedido_db)
            self.assertEqual(pedido_db.cliente, "Roberto Gomez")
            self.assertEqual(pedido_db.articulos_descontados, 4)
            self.assertEqual(pedido_db.armador, "OperadorTest")
            self.assertEqual(pedido_db.tipo_archivo, "docx")
            self.assertEqual(pedido_db.nombre_archivo, "ML_API_2000005555.docx")

            # 7. Verificar existencia física del archivo .docx generado
            docx_path = tmp_root / "data" / "pedidos_archivos" / "ML_API_2000005555.docx"
            self.assertTrue(docx_path.exists())
            self.assertGreater(docx_path.stat().st_size, 0)

            # 8. Prevención de duplicados: reintentar la misma orden debe fallar
            exito_dup, msg_dup = descontar_orden_ml_api(
                orden_mapeada,
                stock_manager=sm,
                order_store=order_store,
                armador="OperadorTest",
                root_path=tmp_root,
            )
            self.assertFalse(exito_dup)
            self.assertIn("ya fue descontada previamente", msg_dup)


if __name__ == "__main__":
    unittest.main()
