"""Pruebas unitarias para las nuevas modificaciones:
1. Opción 'Canje' en logística y persistencia en OrderStore.
2. Descuentos sin generación de documento individual (se consolida en cierre).
3. Rótulos/etiquetas compactas en formato A4 (4 por hoja).
4. Búsqueda y alta automática de clientes.
"""

from pathlib import Path
import pytest
from reportlab.lib.pagesizes import A4
import pypdf

from src.orders_store import OrderStore, LOGISTICA_OPCIONES, Pedido
from src.agent import AgenteRemitosStock
from src.stock_manager import StockManager
from src.label_generator import generar_etiquetas_bultos_pdf
from src.menu import MenuAgente


def test_logistica_canje_disponible_y_persistente(tmp_path: Path):
    """Verifica que 'Canje' figure en LOGISTICA_OPCIONES y se guarde en SQLite."""
    assert "Canje" in LOGISTICA_OPCIONES

    db_path = tmp_path / "test_pedidos.sqlite3"
    store = OrderStore(db_path)

    store.crear_cliente("Cliente Canje Test")
    ped = store.registrar_pedido(
        nota_pedido="CANJE-0001",
        numero_pedido="P-100",
        cliente="Cliente Canje Test",
        bultos=2,
        logistica="Canje",
        armador="Operador",
        tipo_archivo="pdf",
        nombre_archivo="canje.pdf",
    )
    assert ped.logistica == "Canje"

    pedidos = store.listar_pedidos()
    assert len(pedidos) == 1
    assert pedidos[0].logistica == "Canje"


def test_descuento_sin_generar_documento(tmp_path: Path):
    """Verifica que ejecutar descuento con guardar_archivo=False no cree archivos en disco."""
    carpeta_descuentos = tmp_path / "descuentos"
    carpeta_descuentos.mkdir(parents=True, exist_ok=True)

    menu = MenuAgente()
    sm = StockManager(ruta_excel_base=menu.ruta_excel_base)
    agente = AgenteRemitosStock(stock_manager=sm)

    reporte = agente.ejecutar(
        rutas_pdf=[],
        rutas_canjes=[],
        carpeta_descuentos=carpeta_descuentos,
        simulacion=False,
        guardar_archivo=False,
    )
    # Ningún archivo individual debe haberse creado en la carpeta
    archivos_generados = list(carpeta_descuentos.glob("*"))
    assert len(archivos_generados) == 0
    assert reporte.reporte_stock.archivo_pdf is None
    assert reporte.reporte_stock.archivo_guardado == ""


def test_etiquetas_6_por_hoja_a4(tmp_path: Path):
    """Verifica que las etiquetas se generen en A4 a razón de 6 por página."""
    destino = tmp_path / "etiquetas"
    destino.mkdir()

    # Pedido con 6 bultos -> exactamente 1 página A4
    p6 = Pedido(
        id=1,
        nota_pedido="REM-001",
        numero_pedido="PED-01",
        cliente="Comercial ABC",
        bultos=6,
        logistica="Canje",
        armador="Juan",
        tipo_archivo="pdf",
        nombre_archivo="doc.pdf",
        agregado=False,
        articulos_descontados=10,
        resumen_items="10 un.",
        created_at="2026-10-26 12:00:00",
        estado="descontado",
    )
    pdf6 = generar_etiquetas_bultos_pdf(p6, destino)
    reader6 = pypdf.PdfReader(str(pdf6))
    assert len(reader6.pages) == 1
    # Dimensiones A4 (595.27 x 841.89)
    assert abs(float(reader6.pages[0].mediabox.width) - A4[0]) < 1.0
    assert abs(float(reader6.pages[0].mediabox.height) - A4[1]) < 1.0

    # Pedido con 7 bultos -> 2 páginas A4 (6 en la primera, 1 en la segunda)
    p7 = Pedido(
        id=2,
        nota_pedido="REM-002",
        numero_pedido="PED-02",
        cliente="Comercial ABC",
        bultos=7,
        logistica="Canje",
        armador="Juan",
        tipo_archivo="pdf",
        nombre_archivo="doc.pdf",
        agregado=False,
        articulos_descontados=12,
        resumen_items="12 un.",
        created_at="2026-10-26 12:00:00",
        estado="descontado",
    )
    pdf7 = generar_etiquetas_bultos_pdf(p7, destino)
    reader7 = pypdf.PdfReader(str(pdf7))
    assert len(reader7.pages) == 2


def test_cliente_auto_creacion(tmp_path: Path):
    """Verifica la creación y listado de clientes en el store."""
    db_path = tmp_path / "test_clientes.sqlite3"
    store = OrderStore(db_path)

    assert "Nuevo Cliente Directo" not in store.listar_nombres_clientes()
    store.crear_cliente("Nuevo Cliente Directo")
    assert "Nuevo Cliente Directo" in store.listar_nombres_clientes()


def test_etiqueta_cliente_con_numero_pedido(tmp_path: Path):
    """Verifica que el nombre del cliente se concatene con el número de pedido en la etiqueta."""
    destino = tmp_path / "etiquetas_gregory"
    destino.mkdir()

    p = Pedido(
        id=10,
        nota_pedido="REM-9999",
        numero_pedido="3",
        cliente="Gregory Rodriguez",
        bultos=1,
        logistica="Domicilio",
        armador="Operario",
        tipo_archivo="pdf",
        nombre_archivo="doc.pdf",
        agregado=False,
        articulos_descontados=5,
        resumen_items="5 un.",
        created_at="2026-10-26 14:00:00",
        estado="descontado",
    )
    pdf = generar_etiquetas_bultos_pdf(p, destino)
    reader = pypdf.PdfReader(str(pdf))
    texto_pagina = reader.pages[0].extract_text()
    assert "Gregory Rodriguez Nro 3" in texto_pagina


def test_actualizar_datos_pedido(tmp_path: Path):
    """Verifica la modificación de datos de un pedido existente y sus validaciones."""
    db_path = tmp_path / "test_modificar_pedidos.sqlite3"
    store = OrderStore(db_path)

    ped = store.registrar_pedido(
        nota_pedido="REM-MOD-1",
        numero_pedido="1",
        cliente="Cliente Original",
        bultos=2,
        logistica="Domicilio",
        armador="Operador 1",
        tipo_archivo="pdf",
        nombre_archivo="remito.pdf",
    )
    assert ped.cliente == "Cliente Original"
    assert ped.bultos == 2
    assert ped.logistica == "Domicilio"

    # Modificar datos válidos
    actualizado = store.actualizar_datos_pedido(
        pedido_id=ped.id,
        cliente="Cliente Modificado",
        numero_pedido="5",
        bultos=4,
        logistica="Canje",
        fecha_retiro="28/10/2026",
        usuario="AdminTest",
    )
    assert actualizado.cliente == "Cliente Modificado"
    assert actualizado.numero_pedido == "5"
    assert actualizado.bultos == 4
    assert actualizado.logistica == "Canje"
    assert actualizado.fecha_retiro == "28/10/2026"

    # Verificar auditoría registrada
    logs = store.listar_auditoria(limit=10, filtro_accion="MODIFICAR_PEDIDO")
    assert len(logs) >= 1
    assert "Cliente Modificado" in logs[0].detalle
    assert "AdminTest" in logs[0].usuario

    # Validar que bultos < 1 falle
    with pytest.raises(Exception):
        store.actualizar_datos_pedido(pedido_id=ped.id, bultos=0)

    # Validar que logística inexistente falle
    with pytest.raises(Exception):
        store.actualizar_datos_pedido(pedido_id=ped.id, logistica="InexistenteLogistica")


def test_obtener_items_y_desarmar_pedido(tmp_path: Path):
    """Verifica la recuperación de items y el flujo de desarmado de pedido."""
    db_path = tmp_path / "test_desarmar.sqlite3"
    store = OrderStore(db_path)

    items_orig = [
        ("ART01", "Producto Uno", 3),
        ("ART02", "Producto Dos", 5),
    ]
    ped = store.registrar_pedido(
        nota_pedido="REM-DESARM-1",
        numero_pedido="99",
        cliente="Cliente Desarme",
        bultos=1,
        logistica="Transporte",
        armador="Operador",
        tipo_archivo="docx",
        nombre_archivo="orden.docx",
        items=items_orig,
    )

    # Verificar que obtener_items_pedido devuelva los items cargados
    items_obtenidos = store.obtener_items_pedido(ped.id)
    assert len(items_obtenidos) == 2
    assert items_obtenidos[0] == ("ART01", "Producto Uno", 3)
    assert items_obtenidos[1] == ("ART02", "Producto Dos", 5)

    # Simular desarmar pedido: anulación y devolución de stock
    devoluciones = {cod: cant for cod, _desc, cant in items_obtenidos}
    assert devoluciones == {"ART01": 3, "ART02": 5}

    store.anular_pedido(
        pedido_id=ped.id,
        motivo="Desarmado y reincorporación de stock por cancelación",
        usuario="OperadorTest",
    )

    ped_anulado = store.buscar_pedido_por_nota("REM-DESARM-1")
    assert ped_anulado is not None
    assert ped_anulado.estado == "anulado"


def test_resultado_remito_compatibilidad_discrepancia():
    """Verifica que ResultadoRemito no falle por 'discrepancia' u otros argumentos en __init__."""
    from src.remito_parser import ResultadoRemito, ItemRemito

    # Con discrepancia explícita (para compatibilidad hacia atrás)
    r1 = ResultadoRemito(
        archivo="remito.pdf",
        numero_remito="1234",
        fecha="2026-10-27",
        cliente="Cliente Test",
        articulos_declarados=10,
        articulos_extraidos=10,
        verificacion_ok=True,
        discrepancia=False,
    )
    assert r1.verificacion_ok is True
    assert r1.discrepancia is False

    # Con items
    it = ItemRemito(codigo="ART01", descripcion="Desc", cantidad=5, origen_remito="1234")
    r2 = ResultadoRemito(
        archivo="remito2.pdf",
        numero_remito="1235",
        fecha="2026-10-27",
        cliente="Cliente Test 2",
        articulos_declarados=5,
        articulos_extraidos=5,
        items=[it],
        verificacion_ok=True,
    )
    assert len(r2.items) == 1
    assert r2.items[0].codigo == "ART01"


def test_cierre_jornada_y_actualizar_hoja_ruta(tmp_path: Path):
    """Verifica que el flujo de cierre de jornada y la actualización de hoja de ruta en OrderStore funcionen correctamente."""
    from src.dispatch_manifest import generar_hoja_ruta_pdf

    db_path = tmp_path / "test_cierre.sqlite3"
    store = OrderStore(db_path)
    store.crear_cliente("Cliente Cierre")
    ped = store.registrar_pedido(
        nota_pedido="CIERRE-01",
        numero_pedido="P-CIERRE",
        cliente="Cliente Cierre",
        bultos=3,
        logistica="Domicilio",
        armador="OperadorTest",
        tipo_archivo="pdf",
        nombre_archivo="test_cierre.pdf",
        articulos_descontados=10,
    )

    pendientes = store.listar_pedidos_pendientes_cierre()
    assert len(pendientes) == 1

    cierre_id = store.registrar_cierre(
        usuario="OperadorTest",
        pedidos_ids=[ped.id],
        articulos_totales=10,
        resumen_pedidos="1 pedido (10 un.)",
        archivo_pdf="Cierre_Test.pdf",
        archivo_excel="Cierre_Test.xls",
    )
    assert cierre_id > 0

    dest_folder = tmp_path / "descuentos"
    dest_folder.mkdir(parents=True, exist_ok=True)
    hoja_ruta = generar_hoja_ruta_pdf(
        cierre_id=cierre_id,
        pedidos=[ped],
        usuario="OperadorTest",
        carpeta_destino=dest_folder,
    )
    assert hoja_ruta.exists()

    store.actualizar_hoja_ruta_cierre(cierre_id, hoja_ruta.name)

    cierres = store.listar_cierres(limit=1)
    assert len(cierres) == 1
    assert cierres[0].archivo_hoja_ruta == hoja_ruta.name
    assert len(store.listar_pedidos_pendientes_cierre()) == 0



