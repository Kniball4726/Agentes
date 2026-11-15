"""Módulo de inicialización y datos de prueba para el entorno QA / Sandbox."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any
import openpyxl

from ..core.environment import get_data_dir, get_descuentos_dir, set_environment
from ..auth.store import UserStore
from ..orders.store import OrderStore
from ..products.store import ProductStore


PRODUCTOS_SEMILLA_QA = [
    ("101", "Proteína Whey 1kg Vainilla", 150, "7791234567890", "ESTANTE-A1"),
    ("102", "Proteína Whey 1kg Chocolate", 120, "7791234567891", "ESTANTE-A2"),
    ("201", "Creatina Monohidrato 300g", 80, "7791234567892", "ESTANTE-B1"),
    ("202", "Creatina Micronizada 500g", 50, "7791234567893", "ESTANTE-B2"),
    ("301", "BCAA 2:1:1 250g Frutos Rojos", 95, "7791234567894", "ESTANTE-C1"),
    ("302", "Shaker Mezclador 700ml Negro", 200, "7791234567895", "ESTANTE-D1"),
    ("401", "Barra Proteica Choco-Caramelo", 300, "7791234567896", "ESTANTE-E1"),
]

USUARIOS_SEMILLA_QA = [
    ("admin_qa", "password123", "administrador", "Admin QA", "admin.qa@empresa.com"),
    ("picker_qa", "password123", "picker", "Picker QA", "picker.qa@empresa.com"),
    ("operador_qa", "password123", "operador", "Operador QA", "operador.qa@empresa.com"),
    ("consulta_qa", "password123", "consulta", "Consulta QA", "consulta.qa@empresa.com"),
]

CLIENTES_SEMILLA_QA = [
    ("Distribuidora Fitness SA", "CLI-001", "Av. San Martín 1234"),
    ("Gimnasio MegaSport SRL", "CLI-002", "Calle Belgrano 456"),
    ("Mercado Libre", "ML-001", "Centro Logístico Colecta"),
    ("Mercado Envíos Full", "FULL-001", "Depósito Central Full"),
]


def inicializar_ambiente_qa(forzar_reinicio: bool = False) -> dict[str, Any]:
    """
    Inicializa un ambiente de pruebas manuales (QA) completamente aislado.
    Crea bases de datos en data_qa/ y carpetas en Descuentos_QA/.
    """
    set_environment("qa")
    data_dir = get_data_dir()
    desc_dir = get_descuentos_dir()

    # Subcarpetas requeridas
    for sub in (
        "Mayoristas",
        "Canjes",
        "MercadoLibre",
        "MercadoFull",
        "Fabrica",
        "StockFisico",
        "descuentos",
        "descontados",
        "pedidos_archivos",
    ):
        (desc_dir / sub if sub != "pedidos_archivos" else data_dir / sub).mkdir(parents=True, exist_ok=True)

    if forzar_reinicio:
        for db_name in ("usuarios.sqlite3", "pedidos.sqlite3", "productos.sqlite3"):
            db_p = data_dir / db_name
            if db_p.exists():
                try:
                    db_p.unlink()
                except Exception:
                    pass

    # 1. Usuarios QA
    user_store = UserStore(data_dir / "usuarios.sqlite3")
    usuarios_creados = []
    for u_name, u_pass, u_role, u_nom, u_email in USUARIOS_SEMILLA_QA:
        try:
            if not user_store.get_user_by_username(u_name):
                user_store.create_user(
                    username=u_name,
                    password=u_pass,
                    role=u_role,
                    creator_role="master",
                    nombre=u_nom,
                    email=u_email,
                )
                usuarios_creados.append(u_name)
        except Exception:
            pass

    # 2. Catálogo de Productos QA
    product_store = ProductStore(data_dir / "productos.sqlite3")
    with closing(sqlite3.connect(data_dir / "productos.sqlite3")) as conn, conn:
        for idx, (cod, nom, stk, ean, ubic) in enumerate(PRODUCTOS_SEMILLA_QA, start=1):
            conn.execute(
                """
                INSERT OR REPLACE INTO products (code, name, stock, stock_minimo, stock_maximo, cod_barras, ubicacion, active)
                VALUES (?, ?, ?, 5, 150, ?, ?, 1)
                """,
                (cod, nom, stk, ean, ubic),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO product_catalog_rows (id, product_code, display_name, display_order, template_row)
                VALUES (?, ?, ?, ?, ?)
                """,
                (idx, cod, nom, idx, idx + 3),
            )

        # Movimientos de prueba iniciales para reportes y gráficos analíticos
        cant_movs = conn.execute("SELECT count(*) FROM stock_movements").fetchone()[0]
        if cant_movs == 0:
            from datetime import timedelta
            ahora = datetime.now()
            movs_qa = [
                ("101", "Proteína Whey 1kg Vainilla", -15, "descuento", "operador_qa", "Remito Mayorista 401", (ahora - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")),
                ("201", "Creatina Monohidrato 300g", -22, "descuento", "operador_qa", "Remito Mayorista 401", (ahora - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")),
                ("102", "Proteína Whey 1kg Chocolate", -18, "descuento", "operador_qa", "Despacho Canje 88", (ahora - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S")),
                ("202", "Creatina Micronizada 500g", -10, "descuento", "operador_qa", "Mercado Libre Envío", (ahora - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")),
                ("301", "BCAA 2:1:1 250g Frutos Rojos", -14, "descuento", "operador_qa", "Mercado Libre Envío", (ahora - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S")),
                ("302", "Shaker Mezclador 700ml Negro", -30, "descuento", "operador_qa", "Mercado Full Lote 1", (ahora - timedelta(days=12)).strftime("%Y-%m-%dT%H:%M:%S")),
                ("401", "Barra Proteica Choco-Caramelo", -45, "descuento", "operador_qa", "Venta Directa Mayorista", (ahora - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%S")),
                ("101", "Proteína Whey 1kg Vainilla", -8, "salida_rapida", "admin_qa", "Ajuste por merma", (ahora - timedelta(days=18)).strftime("%Y-%m-%dT%H:%M:%S")),
                ("101", "Proteína Whey 1kg Vainilla", 50, "ingreso_fabrica", "admin_qa", "Lote Fabrica F-102", (ahora - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%S")),
                ("201", "Creatina Monohidrato 300g", 40, "ingreso_fabrica", "admin_qa", "Lote Fabrica F-102", (ahora - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%S")),
            ]
            conn.executemany(
                """
                INSERT INTO stock_movements (product_code, product_name, quantity, movement_type, usuario, detalle, registered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                movs_qa,
            )
        conn.commit()

    # 3. Pedidos y Clientes QA
    order_store = OrderStore(data_dir / "pedidos.sqlite3")
    for c_nom, c_cod, c_dir in CLIENTES_SEMILLA_QA:
        try:
            order_store.crear_cliente(c_nom, codigo=c_cod, direccion=c_dir)
        except Exception:
            pass

    # Pedido de ejemplo si no hay pedidos
    if not order_store.listar_pedidos():
        order_store.registrar_pedido(
            nota_pedido="REM-QA-001",
            numero_pedido="PED-1001",
            cliente="Distribuidora Fitness SA",
            bultos=2,
            logistica="Transporte",
            armador="operador_qa",
            tipo_archivo="pdf",
            nombre_archivo="Remito_QA_001.pdf",
            agregado=False,
            articulos_descontados=8,
            resumen_items="2 productos (8 un.)",
            items=[("101", "Proteína Whey 1kg Vainilla", 5), ("201", "Creatina Monohidrato 300g", 3)],
        )

    # Plan Full de ejemplo si no hay planes
    if not order_store.listar_planes_mercado_full():
        order_store.crear_plan_mercado_full(
            nombre_envio="Envío Full QA - Lote 1",
            archivo_excel="Planilla_Full_QA.xlsx",
            creado_por="admin_qa",
            items=[
                ("101", "Proteína Whey 1kg Vainilla", 10),
                ("201", "Creatina Monohidrato 300g", 5),
                ("302", "Shaker Mezclador 700ml Negro", 15),
            ],
        )

    # 4. Archivos Excel de Plantilla en Descuentos_QA
    _generar_excel_productos_qa(desc_dir / "Productos.xlsx")
    _generar_excel_full_qa(desc_dir / "MercadoFull" / "Planilla_Full_QA.xlsx")

    return {
        "ambiente": "qa",
        "data_dir": str(data_dir),
        "descuentos_dir": str(desc_dir),
        "usuarios": [u[0] for u in USUARIOS_SEMILLA_QA],
        "clave_default": "password123",
        "productos_cargados": len(PRODUCTOS_SEMILLA_QA),
        "timestamp": datetime.now().isoformat(),
    }


def _generar_excel_productos_qa(ruta_archivo: Path) -> None:
    """Crea la plantilla Productos.xlsx con formato en Descuentos_QA."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Productos"

    # Encabezados
    encabezados = ["Código", "Descripción", "Stock", "Código de Barras", "Ubicación"]
    ws.append(encabezados)

    for cod, nom, stk, ean, ubic in PRODUCTOS_SEMILLA_QA:
        ws.append([cod, nom, stk, ean, ubic])

    ruta_archivo.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta_archivo)


def _generar_excel_full_qa(ruta_archivo: Path) -> None:
    """Crea una planilla de ejemplo de Mercado Full para pruebas de carga y escaneo."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MercadoFull"

    ws.append(["SKU / Código", "Descripción", "Cantidad a Enviar"])
    ws.append(["101", "Proteína Whey 1kg Vainilla", 10])
    ws.append(["201", "Creatina Monohidrato 300g", 5])
    ws.append(["302", "Shaker Mezclador 700ml Negro", 15])

    ruta_archivo.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta_archivo)
