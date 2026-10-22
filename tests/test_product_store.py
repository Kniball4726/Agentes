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


if __name__ == "__main__":
    unittest.main()
