import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.product_store import ProductStore


class ProductStoreTests(unittest.TestCase):
    def test_updates_product_code_name_stock_and_active_state(self):
        with tempfile.TemporaryDirectory() as directorio:
            store = ProductStore(Path(directorio) / "productos.sqlite3")
            store.import_template_once(
                [
                    (4, "100", "Producto inicial", 8),
                    (5, "100", "Producto inicial", 8),
                    (6, "200", "Otro producto", 3),
                ]
            )

            store.update_product(
                old_code="100",
                new_code="101",
                name="Producto editado",
                stock=12,
                synchronize_template=lambda: [4, 5, 6],
                restore_template=lambda: None,
            )

            catalogo = store.list_catalog_rows(include_inactive=True)
            self.assertEqual([fila["code"] for fila in catalogo], ["101", "101", "200"])
            self.assertEqual(
                [fila["display_name"] for fila in catalogo],
                ["Producto editado", "Producto editado", "Otro producto"],
            )
            self.assertEqual(catalogo[0]["stock"], 12)

            store.set_product_active("101", False)
            self.assertEqual(
                [fila["code"] for fila in store.list_catalog_rows()],
                ["200"],
            )
            self.assertEqual(
                [producto["code"] for producto in store.list_products()],
                ["101", "200"],
            )
            store.set_product_active("101", True)
            self.assertEqual(
                [fila["code"] for fila in store.list_catalog_rows()],
                ["101", "101", "200"],
            )

    def test_rejects_product_code_collision_without_syncing_template(self):
        with tempfile.TemporaryDirectory() as directorio:
            store = ProductStore(Path(directorio) / "productos.sqlite3")
            store.import_template_once(
                [(4, "100", "Producto inicial", 8), (5, "200", "Otro", 3)]
            )
            sincronizaciones = []

            with self.assertRaisesRegex(ValueError, "ya está asignado"):
                store.update_product(
                    old_code="100",
                    new_code="200",
                    name="Producto editado",
                    stock=12,
                    synchronize_template=lambda: sincronizaciones.append(True) or [],
                    restore_template=lambda: None,
                )

            self.assertEqual(sincronizaciones, [])
            self.assertEqual(
                [fila["code"] for fila in store.list_catalog_rows()],
                ["100", "200"],
            )

    def test_rolls_back_product_edit_and_template_when_sync_fails(self):
        with tempfile.TemporaryDirectory() as directorio:
            root = Path(directorio)
            store = ProductStore(root / "productos.sqlite3")
            store.import_template_once([(4, "100", "Producto original", 8)])
            plantilla = root / "Productos.xlsx"
            plantilla.write_bytes(b"plantilla original")

            def sincronizar() -> list[int]:
                plantilla.write_bytes(b"plantilla modificada")
                return []

            def restaurar() -> None:
                plantilla.write_bytes(b"plantilla original")

            with self.assertRaises(RuntimeError):
                store.update_product(
                    old_code="100",
                    new_code="101",
                    name="Producto editado",
                    stock=12,
                    synchronize_template=sincronizar,
                    restore_template=restaurar,
                )

            self.assertEqual(plantilla.read_bytes(), b"plantilla original")
            self.assertEqual(
                [fila["code"] for fila in store.list_catalog_rows()],
                ["100"],
            )
            self.assertEqual(store.list_catalog_rows()[0]["stock"], 8)

    def test_migrates_existing_database_with_products_active_by_default(self):
        with tempfile.TemporaryDirectory() as directorio:
            database = Path(directorio) / "productos.sqlite3"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute(
                    """
                    CREATE TABLE products (
                        code TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        stock INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE product_catalog_rows (
                        id INTEGER PRIMARY KEY,
                        product_code TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        display_order INTEGER NOT NULL,
                        template_row INTEGER
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO products (code, name, stock) VALUES ('100', 'Producto', 4)"
                )
                connection.execute(
                    """
                    INSERT INTO product_catalog_rows (
                        product_code, display_name, display_order, template_row
                    ) VALUES ('100', 'Producto', 0, 4)
                    """
                )

            store = ProductStore(database)

            self.assertEqual(store.list_products()[0]["active"], 1)

    def test_rolls_back_database_and_restores_template_if_sync_fails(self):
        with tempfile.TemporaryDirectory() as directorio:
            root = Path(directorio)
            store = ProductStore(root / "productos.sqlite3")
            store.import_template_once([(4, "100", "Producto base", 8)])
            plantilla = root / "Productos.xlsx"
            plantilla.write_bytes(b"plantilla original")

            def sincronizar(_orden: int) -> list[int]:
                plantilla.write_bytes(b"plantilla actualizada")
                return []

            def restaurar() -> None:
                plantilla.write_bytes(b"plantilla original")

            with self.assertRaises(RuntimeError):
                store.add_product_after(
                    code="101",
                    name="Producto nuevo",
                    reference_code="100",
                    stock=3,
                    synchronize_template=sincronizar,
                    restore_template=restaurar,
                )

            self.assertEqual(plantilla.read_bytes(), b"plantilla original")
            self.assertEqual(
                [fila["code"] for fila in store.list_catalog_rows()],
                ["100"],
            )


    def test_registers_and_queries_stock_movements(self):
        with tempfile.TemporaryDirectory() as directorio:
            store = ProductStore(Path(directorio) / "productos.sqlite3")
            store.import_template_once([(4, "100", "Producto base", 8)])

            store.register_movements([
                ("100", "Producto base", -5, "descuento"),
                ("100", "Producto base", -3, "descuento"),
                ("200", "Otro producto", 15, "ingreso_fabrica"),
            ])

            # Consultar solo descuentos
            movs_descuento = store.query_movements(
                "2000-01-01T00:00:00",
                "2099-12-31T23:59:59",
                movement_type="descuento",
            )
            self.assertEqual(len(movs_descuento), 1)
            self.assertEqual(movs_descuento[0]["product_code"], "100")
            self.assertEqual(movs_descuento[0]["total_quantity"], 8)

            # Consultar todos
            todos = store.query_movements(
                "2000-01-01T00:00:00",
                "2099-12-31T23:59:59",
            )
            self.assertEqual(len(todos), 2)
            # Primero el de mayor cantidad total (15 > 8)
            self.assertEqual(todos[0]["product_code"], "200")
            self.assertEqual(todos[0]["total_quantity"], 15)
            self.assertEqual(todos[1]["product_code"], "100")
            self.assertEqual(todos[1]["total_quantity"], 8)

    def test_negative_stock_allowed_and_categorized_as_agotado(self):
        with tempfile.TemporaryDirectory() as directorio:
            store = ProductStore(Path(directorio) / "productos.sqlite3")
            store.import_template_once([(4, "100", "Producto base", 10)])

            # Permitir stock negativo para registrar sobredemanda
            store.update_stocks({"100": -5})
            catalogo = store.list_catalog_rows()
            self.assertEqual(catalogo[0]["stock"], -5)

            # En la vista debe figurar como AGOTADO y sugerir reordenar 105 (100 - (-5))
            analisis = store.get_replenishment_analysis(only_critical=True)
            self.assertEqual(len(analisis), 1)
            self.assertEqual(analisis[0]["estado_inventario"], "AGOTADO")
            self.assertEqual(analisis[0]["cantidad_sugerida_pedir"], 105)

    def test_database_trigger_automatically_audits_stock_updates(self):
        with tempfile.TemporaryDirectory() as directorio:
            store = ProductStore(Path(directorio) / "productos.sqlite3")
            store.import_template_once([(4, "100", "Producto base", 10)])

            # Actualizar stock a 7 (descuento de 3)
            store.update_stocks({"100": 7})

            # Consultar stock_movements generado automáticamente por el trigger
            movs = store.query_movements(
                "2000-01-01T00:00:00", "2099-12-31T23:59:59"
            )
            self.assertEqual(len(movs), 1)
            self.assertEqual(movs[0]["product_code"], "100")
            self.assertEqual(movs[0]["total_quantity"], 3)

    def test_replenishment_view_and_thresholds(self):
        with tempfile.TemporaryDirectory() as directorio:
            store = ProductStore(Path(directorio) / "productos.sqlite3")
            store.import_template_once([
                (4, "100", "Producto A", 2),
                (5, "200", "Producto B", 50),
            ])

            # Por defecto min es 5 y max es 100. Prod A tiene 2 <= 5 -> QUIEBRE_INMINENTE
            criticos = store.get_replenishment_analysis(only_critical=True)
            self.assertEqual(len(criticos), 1)
            self.assertEqual(criticos[0]["code"], "100")
            self.assertEqual(criticos[0]["estado_inventario"], "QUIEBRE_INMINENTE")
            self.assertEqual(criticos[0]["cantidad_sugerida_pedir"], 98)

            # Actualizar umbrales para Prod B: min=60, max=120 -> pasa a ser crítico
            store.update_product_thresholds("200", stock_minimo=60, stock_maximo=120)
            criticos_actualizados = store.get_replenishment_analysis(only_critical=True)
            self.assertEqual(len(criticos_actualizados), 2)

    def test_record_dispatch_and_details(self):
        with tempfile.TemporaryDirectory() as directorio:
            store = ProductStore(Path(directorio) / "productos.sqlite3")
            store.import_template_once([(4, "100", "Producto base", 10)])

            despacho_id = store.record_dispatch(
                tipo_origen="Mayorista",
                nombre_archivo="remito_001.pdf",
                total_articulos=4,
                detalles=[("100", 4, 10, 6)],
                reporte_archivo="informe_001.xlsx",
            )
            self.assertGreater(despacho_id, 0)

            with closing(store._connect()) as conn:
                despacho = conn.execute(
                    "SELECT * FROM despachos WHERE id = ?", (despacho_id,)
                ).fetchone()
                self.assertEqual(despacho["tipo_origen"], "Mayorista")
                self.assertEqual(despacho["total_articulos"], 4)

                detalles = conn.execute(
                    "SELECT * FROM despacho_detalles WHERE despacho_id = ?",
                    (despacho_id,),
                ).fetchall()
                self.assertEqual(len(detalles), 1)
                self.assertEqual(detalles[0]["product_code"], "100")
                self.assertEqual(detalles[0]["cantidad_descontada"], 4)

    def test_admin_notifications_flow(self):
        with tempfile.TemporaryDirectory() as directorio:
            store = ProductStore(Path(directorio) / "productos.sqlite3")
            self.assertEqual(store.get_unread_notifications_count(), 0)

            n1 = store.create_admin_notification(
                title="Descuento",
                message="Operario juan descontó 10 un.",
                operator_username="juan",
            )
            n2 = store.create_admin_notification(
                title="Descuento",
                message="Operario maria descontó 5 un.",
                operator_username="maria",
            )
            self.assertEqual(store.get_unread_notifications_count(), 2)

            unread = store.list_admin_notifications(unread_only=True)
            self.assertEqual(len(unread), 2)
            self.assertEqual(unread[0]["operator_username"], "maria")

            store.mark_notification_as_read(n2)
            self.assertEqual(store.get_unread_notifications_count(), 1)

            store.mark_all_notifications_as_read()
            self.assertEqual(store.get_unread_notifications_count(), 0)


if __name__ == "__main__":
    unittest.main()
