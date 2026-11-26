"""Pruebas de Fase 2: montaje ASGI explícito sin monkey-patch, migraciones PRAGMA user_version y atomicidad."""

from __future__ import annotations

import asyncio
from contextlib import closing
import socket
import sqlite3
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import flet_web.fastapi as flet_web_fastapi
import httpx
import openpyxl
import pytest
import uvicorn

from src.auth.schema import AUTH_SCHEMA_VERSION
from src.auth.store import UserStore
from src.core.sqlite_migrations import MigrationStep, aplicar_migraciones_sqlite, get_user_version
from src.core.stock_order_tx import (
    ejecutar_baja_pedido_con_restitucion,
    ejecutar_descuento_y_registro_atomico,
)
from src.inventory import StockManager
from src.orders import OrderStore
from src.orders.schema import ORDERS_SCHEMA_VERSION
from src.products import ProductStore
from src.products.schema import PRODUCTS_SCHEMA_VERSION
from src.server_app import crear_aplicacion_asgi
from src.ssl_manager import asegurar_certificado_ssl
from src.stock.models import RegistroDescuento, ReporteStock


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _crear_excel_stock(ruta_excel: Path, codigo: str = "SKU-1", stock: int = 20) -> None:
    ruta_excel.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stock"
    ws.append(["CÓDIGO", "PRODUCTOS", "STOCK"])
    ws.append([])
    ws.append([codigo, "Producto Test", stock])
    wb.save(ruta_excel)
    wb.close()


def test_montaje_asgi_explicito_sin_monkeypatch_y_uvicorn_https_real(tmp_path: Path) -> None:
    async def _dummy_main(_page) -> None:
        return None

    app = crear_aplicacion_asgi(_dummy_main, habilitar_docs_api=False)
    assert not hasattr(flet_web_fastapi.FastAPI, "_orig_init")
    assert not hasattr(uvicorn.Config, "_orig_init")
    assert app.docs_url is None
    assert app.openapi_url is None

    with patch("src.ssl_manager.application_root", return_value=tmp_path):
        cert_path, key_path = asegurar_certificado_ssl()

    puerto = _puerto_libre()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=puerto,
        log_level="error",
        ws="websockets-sansio",
        ssl_certfile=str(cert_path),
        ssl_keyfile=str(key_path),
    )
    server = uvicorn.Server(config)

    async def _probar_servidor_vivo() -> None:
        task = asyncio.create_task(server.serve())
        try:
            for _ in range(100):
                if getattr(server, "started", False) or task.done():
                    break
                await asyncio.sleep(0.05)
            assert getattr(server, "started", False) is True

            async with httpx.AsyncClient(
                base_url=f"https://127.0.0.1:{puerto}",
                verify=False,
                timeout=5.0,
            ) as client:
                r_ping = await client.get("/api/v1/sistema/ping")
                assert r_ping.status_code == 200
                assert r_ping.json().get("status") == "pong"

                r_sw = await client.get("/sw.js")
                assert r_sw.status_code == 200
                assert r_sw.headers.get("Service-Worker-Allowed") == "/"

                r_doc = await client.get("/documentos/ver?p=test.pdf")
                assert r_doc.status_code == 401
        finally:
            server.should_exit = True
            await task

    asyncio.run(_probar_servidor_vivo())


def test_migraciones_versionadas_pragma_y_backup_en_bd_heredadas(tmp_path: Path) -> None:
    # 1. Bases nuevas arrancan en su versión objetivo sin backups innecesarios
    db_users = tmp_path / "usuarios.sqlite3"
    db_prods = tmp_path / "productos.sqlite3"
    db_orders = tmp_path / "pedidos.sqlite3"

    UserStore(db_users)
    ProductStore(db_prods)
    OrderStore(db_orders)

    for ruta, esperado in (
        (db_users, AUTH_SCHEMA_VERSION),
        (db_prods, PRODUCTS_SCHEMA_VERSION),
        (db_orders, ORDERS_SCHEMA_VERSION),
    ):
        with closing(sqlite3.connect(ruta)) as conn:
            assert get_user_version(conn) == esperado
    assert not (tmp_path / "backups_migraciones").exists()

    # 2. Base heredada v0 con datos previos genera backup y preserva registros al migrar
    legacy_db = tmp_path / "legacy_orders.sqlite3"
    with closing(sqlite3.connect(legacy_db)) as conn, conn:
        conn.execute(
            """
            CREATE TABLE pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nota_pedido TEXT NOT NULL UNIQUE,
                numero_pedido TEXT NOT NULL DEFAULT '',
                cliente TEXT NOT NULL,
                bultos INTEGER NOT NULL DEFAULT 1,
                logistica TEXT NOT NULL,
                armador TEXT NOT NULL,
                tipo_archivo TEXT NOT NULL CHECK (tipo_archivo IN ('pdf', 'excel')),
                nombre_archivo TEXT NOT NULL,
                agregado INTEGER NOT NULL DEFAULT 0,
                articulos_descontados INTEGER NOT NULL DEFAULT 0,
                resumen_items TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                estado TEXT NOT NULL DEFAULT 'descontado'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO pedidos (nota_pedido, numero_pedido, cliente, bultos, logistica, armador, tipo_archivo, nombre_archivo)
            VALUES ('REM-LEG-1', '1', 'Cliente Historico', 2, 'Domicilio', 'ana', 'pdf', 'rem.pdf')
            """
        )
        assert get_user_version(conn) == 0

    OrderStore._initialized_dbs.clear()
    migrated_store = OrderStore(legacy_db)
    backups = list((tmp_path / "backups_migraciones").glob("legacy_orders_v0_a_v*.sqlite3"))
    assert len(backups) == 1
    with closing(sqlite3.connect(legacy_db)) as conn:
        assert get_user_version(conn) == ORDERS_SCHEMA_VERSION
    ped = migrated_store.buscar_pedido_por_nota("REM-LEG-1")
    assert ped is not None
    assert ped.cliente == "Cliente Historico"

    # Reapertura no crea backups duplicados ni vuelve a migrar
    OrderStore._initialized_dbs.clear()
    OrderStore(legacy_db)
    assert len(list((tmp_path / "backups_migraciones").glob("legacy_orders_*.sqlite3"))) == 1

    # 3. Múltiples dominios compartiendo una misma BD SQLite no colisionan entre sí
    shared_db = tmp_path / "shared_multi_domain.sqlite3"
    OrderStore(shared_db)
    user_shared = UserStore(shared_db)
    prod_shared = ProductStore(shared_db)
    assert any(u.role == "master" for u in user_shared.list_users())
    assert prod_shared.list_products() == []
    with closing(sqlite3.connect(shared_db)) as conn:
        rows = dict(conn.execute("SELECT domain, version FROM schema_migrations").fetchall())
    assert rows == {
        "orders": ORDERS_SCHEMA_VERSION,
        "auth": AUTH_SCHEMA_VERSION,
        "products": PRODUCTS_SCHEMA_VERSION,
    }


def test_aplicar_migraciones_reutilizable_valida_versiones(tmp_path: Path) -> None:
    db_path = tmp_path / "custom.sqlite3"
    steps = [
        MigrationStep(1, "crear tabla", lambda c: c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")),
        MigrationStep(2, "agregar col", lambda c: c.execute("ALTER TABLE t ADD COLUMN nombre TEXT DEFAULT ''")),
    ]
    with closing(sqlite3.connect(db_path)) as conn:
        v = aplicar_migraciones_sqlite(conn, db_path, steps)
        assert v == 2
        assert get_user_version(conn) == 2

    with pytest.raises(ValueError):
        with closing(sqlite3.connect(db_path)) as conn:
            aplicar_migraciones_sqlite(conn, db_path, [MigrationStep(0, "invalida", lambda _c: None)])


def test_atomicidad_compensacion_al_fallar_registro_o_baja_de_pedido(tmp_path: Path) -> None:
    excel_path = tmp_path / "Descuentos" / "Productos.xlsx"
    db_prod = tmp_path / "data" / "productos.sqlite3"
    db_ped = tmp_path / "data" / "pedidos.sqlite3"
    _crear_excel_stock(excel_path, codigo="SKU-1", stock=20)

    sm = StockManager(excel_path, ruta_base_datos=db_prod)
    order_store = OrderStore(db_ped)

    descuento = RegistroDescuento(
        codigo="SKU-1",
        nombre_producto="Producto Test",
        fila_excel=3,
        stock_anterior=20,
        cantidad_descontada=5,
        stock_nuevo=15,
    )
    reporte_fake = SimpleNamespace(
        reporte_stock=ReporteStock(
            descuentos_aplicados=[descuento],
            archivo_guardado="",
            archivo_pdf=None,
        ),
        documentos_verificados=[],
    )

    # 1. Fallo en OrderStore tras descontar stock -> debe compensar stock a 20 y liberar tx_id
    with patch.object(order_store, "registrar_pedido", side_effect=RuntimeError("Fallo simulado en pedidos")):
        with pytest.raises(RuntimeError, match="Fallo simulado"):
            ejecutar_descuento_y_registro_atomico(
                order_store=order_store,
                stock_mgr_factory=lambda: (sm, reporte_fake),
                tx_id="TX-ROLLBACK-1",
                remito="REM-ERR-1",
                num_ped="100",
                cli="Cliente Test",
                bultos_val=1,
                log="Domicilio",
                f_retiro="2026-11-26",
                armador_nom="operario",
                es_agregado=False,
                tipo_archivo="pdf",
                nombre_archivo="rem.pdf",
                archivo_descuento="",
                hash_comprobante="abc123",
            )

    assert sm.product_store.get_product("SKU-1")["stock"] == 20
    assert order_store.buscar_pedido_por_nota("REM-ERR-1") is None

    # 2. Al reintentar con el mismo tx_id ya liberado, se registra correctamente y descuenta a 15
    res = ejecutar_descuento_y_registro_atomico(
        order_store=order_store,
        stock_mgr_factory=lambda: (sm, reporte_fake),
        tx_id="TX-ROLLBACK-1",
        remito="REM-ERR-1",
        num_ped="100",
        cli="Cliente Test",
        bultos_val=1,
        log="Domicilio",
        f_retiro="2026-11-26",
        armador_nom="operario",
        es_agregado=False,
        tipo_archivo="pdf",
        nombre_archivo="rem.pdf",
        archivo_descuento="",
        hash_comprobante="abc123",
    )
    assert res is not None and res[0] is True
    assert sm.product_store.get_product("SKU-1")["stock"] == 15
    assert order_store.buscar_pedido_por_nota("REM-ERR-1") is not None

    # 3. Prevalidación impide volver a descontar stock si el remito ya existe con otro tx_id
    with pytest.raises(ValueError, match="ya fue registrada"):
        ejecutar_descuento_y_registro_atomico(
            order_store=order_store,
            stock_mgr_factory=lambda: (sm, reporte_fake),
            tx_id="TX-OTRO-2",
            remito="REM-ERR-1",
            num_ped="100",
            cli="Cliente Test",
            bultos_val=1,
            log="Domicilio",
            f_retiro="2026-11-26",
            armador_nom="operario",
            es_agregado=False,
            tipo_archivo="pdf",
            nombre_archivo="rem.pdf",
            archivo_descuento="",
            hash_comprobante="abc123",
        )
    assert sm.product_store.get_product("SKU-1")["stock"] == 15

    # 4. Baja fallida tras restituir stock -> compensa regresando el stock a 15
    def _restituir() -> dict[str, int]:
        sm.registrar_ingreso_fabrica({"SKU-1": 5}, sobrescribir=False)
        return {"SKU-1": 5}

    def _revertir(devs: dict[str, int]) -> None:
        sm.descontar_mercado_full(descuentos=devs, nombre_archivo="RollbackTest", sincronizar_excel=False)

    with pytest.raises(RuntimeError, match="Fallo baja"):
        ejecutar_baja_pedido_con_restitucion(
            restituir_fn=_restituir,
            persistir_baja_fn=lambda _u: (_ for _ in ()).throw(RuntimeError("Fallo baja")),
            revertir_restitucion_fn=_revertir,
        )
    assert sm.product_store.get_product("SKU-1")["stock"] == 15


def test_reintentos_sincronizacion_excel_ante_archivo_bloqueado(tmp_path: Path) -> None:
    StockManager.cancelar_sincronizaciones_pendientes()
    excel_path = tmp_path / "Descuentos" / "Productos.xlsx"
    db_prod = tmp_path / "data" / "productos.sqlite3"
    _crear_excel_stock(excel_path, codigo="SKU-R1", stock=10)

    sm = StockManager(excel_path, ruta_base_datos=db_prod)
    sm.product_store.update_stocks({"SKU-R1": 7})

    llamadas = [0]
    done = threading.Event()
    orig_sync = StockManager.sincronizar_catalogo_completo_excel

    def _sync_con_bloqueo_inicial(self_sm):
        if Path(self_sm.ruta_excel_base).resolve() != excel_path.resolve():
            return orig_sync(self_sm)
        llamadas[0] += 1
        if llamadas[0] == 1:
            raise PermissionError("Archivo bloqueado por Excel")
        res = orig_sync(self_sm)
        done.set()
        return res

    try:
        with patch.object(StockManager, "sincronizar_catalogo_completo_excel", _sync_con_bloqueo_inicial):
            sm.programar_sincronizacion_excel(delay_s=0.02, max_reintentos=2)
            assert done.wait(timeout=3.0) is True
            for _ in range(30):
                if str(excel_path.resolve()) not in StockManager.obtener_pendientes_sincronizacion_excel():
                    break
                time.sleep(0.02)
    finally:
        StockManager.cancelar_sincronizaciones_pendientes()

    assert llamadas[0] == 2
    assert str(excel_path.resolve()) not in StockManager.obtener_pendientes_sincronizacion_excel()
    wb = openpyxl.load_workbook(excel_path)
    try:
        ws = wb["Stock"]
        stocks_por_cod = {
            str(ws.cell(r, 1).value): ws.cell(r, 3).value
            for r in range(1, ws.max_row + 1)
            if ws.cell(r, 1).value is not None
        }
        assert stocks_por_cod["SKU-R1"] == 7
    finally:
        wb.close()
