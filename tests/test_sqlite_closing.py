"""Pruebas de cierre determinista de conexiones SQLite y helpers centrales."""

from __future__ import annotations

import ast
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.auth.store import UserStore
from src.core.sqlite_utils import open_sqlite_connection, sqlite_connection
from src.orders.store import OrderStore
from src.products.store import ProductStore


class SqliteClosingTests(unittest.TestCase):
    """Verifica el cierre determinista de conexiones SQLite en utilidades y stores."""

    def test_sqlite_connection_closes_on_exit_and_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.sqlite3"
            with sqlite_connection(db_path) as conn:
                conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")

            with self.assertRaises(RuntimeError):
                with sqlite_connection(db_path) as conn_err:
                    conn_err.execute("SELECT 1").fetchone()
                    raise RuntimeError("boom")
            with self.assertRaises(sqlite3.ProgrammingError):
                conn_err.execute("SELECT 1")

    def test_open_sqlite_connection_closes_when_pragma_fails(self) -> None:
        fake_conn = MagicMock(spec=sqlite3.Connection)
        fake_conn.execute.side_effect = sqlite3.OperationalError("locked")
        with patch("src.core.sqlite_utils.sqlite3.connect", return_value=fake_conn):
            with self.assertRaises(sqlite3.OperationalError):
                open_sqlite_connection("dummy.sqlite3")
        fake_conn.close.assert_called_once()

    def test_stores_close_connections_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            u_store = UserStore(root / "usuarios.sqlite3")
            with u_store._connect() as u_conn:
                u_conn.execute("SELECT 1").fetchone()
            with self.assertRaises(sqlite3.ProgrammingError):
                u_conn.execute("SELECT 1")

            o_store = OrderStore(root / "pedidos.sqlite3")
            with o_store._connect() as o_conn:
                o_conn.execute("SELECT 1").fetchone()
            with self.assertRaises(sqlite3.ProgrammingError):
                o_conn.execute("SELECT 1")

            p_store = ProductStore(root / "productos.sqlite3")
            with closing(p_store._connect()) as p_conn:
                p_conn.execute("SELECT 1").fetchone()
            with self.assertRaises(sqlite3.ProgrammingError):
                p_conn.execute("SELECT 1")

    def test_no_unclosed_sqlite_connect_with_blocks_in_src_or_scripts(self) -> None:
        raiz = Path(__file__).resolve().parent.parent
        offenders: list[str] = []
        for carpeta in ("src", "scripts"):
            for ruta in sorted((raiz / carpeta).rglob("*.py")):
                tree = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
                for node in ast.walk(tree):
                    if isinstance(node, ast.With):
                        for item in node.items:
                            expr = ast.unparse(item.context_expr)
                            if "sqlite3.connect" in expr and "closing(" not in expr:
                                offenders.append(f"{ruta.relative_to(raiz)}:{node.lineno}: {expr}")
                            if "product_store._connect(" in expr and "closing(" not in expr:
                                offenders.append(f"{ruta.relative_to(raiz)}:{node.lineno}: {expr}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
