"""Pruebas de verificación de punta a punta para las fallas reparadas."""

from pathlib import Path
import tempfile
import pytest

from src.product_store import ProductStore
from src.stock_manager import AlertaStock, RegistroDescuento, ReporteStock
from src.stock.models import AlertaStock as AlertaStockModel


def test_sheets_manager_and_stock_models_imports():
    """Verifica que AlertaStock se pueda importar desde stock_manager y stock.models."""
    assert AlertaStock is AlertaStockModel
    alerta = AlertaStock(
        codigo="XYZ123",
        descripcion="Producto de prueba",
        cantidad=10,
        motivo="Sin stock",
    )
    assert alerta.codigo == "XYZ123"
    assert alerta.cantidad == 10

    reporte = ReporteStock(
        descuentos_aplicados=[],
        archivo_guardado="test.xls",
        alertas=[alerta],
    )
    assert len(reporte.alertas) == 1
    assert reporte.alertas[0].codigo == "XYZ123"


def test_product_store_buscar_productos():
    """Verifica que ProductStore.buscar_productos funcione por código, nombre y código de barras."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_prods.sqlite3"
        ps = ProductStore(database_path=db_path)
        ps.import_template_once(
            [
                (1, "COD01", "PROTEINA WHEY 1KG", 25),
                (2, "COD02", "CREATINA MONOHIDRATO", 10),
                (3, "COD03", "BCAA 2000 AMINO", 0),
            ]
        )

        # Búsqueda por nombre parcial
        encontrados = ps.buscar_productos("whey")
        assert len(encontrados) == 1
        assert encontrados[0]["code"] == "COD01"

        # Búsqueda por código
        encontrados_cod = ps.buscar_productos("COD02")
        assert len(encontrados_cod) == 1
        assert encontrados_cod[0]["name"] == "CREATINA MONOHIDRATO"

        # Búsqueda vacía devuelve catálogo con límite
        todos = ps.buscar_productos("")
        assert len(todos) == 3


def test_menu_normalizar_codigo_import():
    """Verifica que normalizar_codigo esté accesible y funcione desde menu."""
    from src.menu import normalizar_codigo as norm_cod
    assert norm_cod("  Abc-123  ") == "Abc-123"


def test_gui_etiquetas_tuple_unpack():
    """Verifica que la tupla etiquetas en gui.py tenga el formato correcto sin números sueltos."""
    from src import gui
    import inspect

    src_gui = inspect.getsource(gui.InterfazGrafica._mostrar_datos_producto)
    assert '("nombre", "Nombre del producto"),0' not in src_gui
    assert '("nombre", "Nombre del producto"),' in src_gui
