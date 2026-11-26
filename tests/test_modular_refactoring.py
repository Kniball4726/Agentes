"""Pruebas unitarias para los módulos desacoplados y helpers puros tras la refactorización modular."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.api import deps as api_deps
from src.api import stores as api_stores
from src.api import tokens as api_tokens
from src.auth import User
from src.orders import OrderStore, Pedido
from src.orders.dispatch_qr import (
    construir_respuesta_escaneo,
    extraer_datos_qr_despacho,
    extraer_remito_de_codigo,
)
from src.ui.dialogs.dlg_email import mostrar_dialogo_compartir_cierre
from src.ui.dialogs.dlg_mercado_full import _archivar_y_registrar_full
from src.ui.dialogs.dlg_planificar_ingreso_fabrica import mostrar_planificar_ingreso_fabrica
from src.ui.dialogs.email_cierre import _construir_resumen_cierre_email
from src.ui.dialogs.historial_filtros import (
    agrupar_pedidos_por_fecha,
    filtrar_y_ordenar_pedidos,
    paginar_pedidos,
)
from src.ui.dialogs.reportes_config import (
    ejecutar_generacion_reporte,
    resolver_rango_fechas,
)
from src.ui.dialogs.stock_view_logic import (
    calcular_resumen_stock,
    clasificar_estado_stock,
    filtrar_productos_stock,
)
from src.ui.dialogs.whatsapp_share import construir_mensaje_whatsapp_pedido


def test_stock_view_logic_resumen_y_filtros():
    productos = [
        {"code": "00123", "name": "Taladro Percutor", "stock": 0, "stock_minimo": 5, "cod_barras": "779111", "ubicacion": "A-01"},
        {"code": "00456", "name": "Amoladora", "stock": 4, "stock_minimo": 5, "cod_barras": "779222", "ubicacion": "B-02"},
        {"code": "00789", "name": "Llave Inglesa", "stock": 20, "stock_minimo": 5, "cod_barras": "779333", "ubicacion": "C-03"},
    ]
    resumen = calcular_resumen_stock(productos)
    assert resumen == {"total": 3, "unidades": 24, "quiebres": 1, "bajos": 1, "normales": 1}

    assert len(filtrar_productos_stock(productos, estado="quiebre")) == 1
    assert len(filtrar_productos_stock(productos, estado="bajo")) == 1
    assert len(filtrar_productos_stock(productos, estado="normal")) == 1
    assert [p["code"] for p in filtrar_productos_stock(productos, termino="123")] == ["00123"]
    assert [p["code"] for p in filtrar_productos_stock(productos, termino="B-02")] == ["00456"]

    estado_q, _, _ = clasificar_estado_stock(0, 5)
    estado_b, _, _ = clasificar_estado_stock(5, 5)
    estado_n, _, _ = clasificar_estado_stock(6, 5)
    assert (estado_q, estado_b, estado_n) == ("QUIEBRE", "STOCK BAJO", "NORMAL")


def test_historial_filtros_paginacion_y_agrupacion():
    pedidos = [
        Pedido(
            id=1, nota_pedido="R-1", numero_pedido="1", cliente="Alfa", bultos=1,
            logistica="Domicilio", armador="op1", tipo_archivo="pdf", nombre_archivo="1.pdf",
            agregado=False, articulos_descontados=2, resumen_items="2 un.",
            created_at="2026-11-25 10:00:00", estado="cerrado", cierre_id=10, estado_despacho="despachado",
        ),
        Pedido(
            id=2, nota_pedido="R-2", numero_pedido="2", cliente="Beta", bultos=2,
            logistica="Transporte", armador="op2", tipo_archivo="pdf", nombre_archivo="2.pdf",
            agregado=False, articulos_descontados=4, resumen_items="4 un.",
            created_at="2026-11-26 09:00:00", estado="activo", cierre_id=None, estado_despacho="armado",
        ),
        Pedido(
            id=3, nota_pedido="R-3", numero_pedido="3", cliente="Gamma", bultos=1,
            logistica="Domicilio", armador="op1", tipo_archivo="pdf", nombre_archivo="3.pdf",
            agregado=False, articulos_descontados=1, resumen_items="1 un.",
            created_at="2026-11-26 11:00:00", estado="anulado", cierre_id=None, estado_despacho="armado",
        ),
    ]
    hoy = filtrar_y_ordenar_pedidos(pedidos, filtro_rapido="hoy", hoy_str="2026-11-26")
    assert [p.id for p in hoy] == [3, 2]

    pendientes = filtrar_y_ordenar_pedidos(pedidos, filtro_rapido="pendientes")
    assert [p.id for p in pendientes] == [2]

    despachados = filtrar_y_ordenar_pedidos(pedidos, filtro_rapido="despachados")
    assert [p.id for p in despachados] == [1]

    pagina, pag_seg, tot_pags, ini, fin = paginar_pedidos(pedidos, pagina_actual=99, tamano_pagina=2)
    assert (pag_seg, tot_pags, ini, fin) == (2, 2, 2, 3)
    assert len(pagina) == 1

    grupos = agrupar_pedidos_por_fecha(pedidos)
    assert [fecha for fecha, _ in grupos] == ["2026-11-26", "2026-11-25"]
    assert [p.id for p in grupos[0][1]] == [3, 2]


def test_reportes_config_fechas_y_despacho():
    ref = datetime(2026, 11, 26, 10, 0, 0)
    assert resolver_rango_fechas("hoy", "", "", ahora=ref) == ("2026-11-26", "2026-11-26")
    assert resolver_rango_fechas("ayer", "", "", ahora=ref) == ("2026-11-25", "2026-11-25")
    assert resolver_rango_fechas("7d", "", "", ahora=ref) == ("2026-11-20", "2026-11-26")
    assert resolver_rango_fechas("personalizado", "2026-11-01", "", ahora=ref) == ("2026-11-01", "2026-11-01")
    assert ejecutar_generacion_reporte(
        "inexistente",
        interfaz=MagicMock(),
        carpeta=Path("."),
        formato="pdf",
        usuario="op",
        params={},
    ) is None


def test_whatsapp_y_email_cierre_helpers(tmp_path: Path):
    ped = SimpleNamespace(cliente="Ferretería Norte", nota_pedido="R-77", bultos=3, logistica="Expreso", numero_guia="G-999")
    msg_wa = construir_mensaje_whatsapp_pedido(ped)
    assert "Ferretería Norte" in msg_wa and "R-77" in msg_wa and "G-999" in msg_wa

    asunto, lineas = _construir_resumen_cierre_email(42, "3 pedidos (10 un.)", "juan", fecha_str="26/11/2026 18:00")
    assert "Cierre de Jornada #42" in asunto
    assert any("juan" in l for l in lineas)

    pdf_file = tmp_path / "cierre.pdf"
    pdf_file.write_bytes(b"%PDF")
    composer = MagicMock()
    mostrar_dialogo_compartir_cierre(
        MagicMock(),
        cierre_id=42,
        archivo_pdf=pdf_file,
        archivo_excel=None,
        resumen_pedidos="3 pedidos",
        usuario="juan",
        abrir_composer_fn=composer,
    )
    composer.assert_called_once()
    assert composer.call_args.kwargs["archivos_iniciales"] == [pdf_file]


def test_dispatch_qr_y_api_modularizacion():
    assert extraer_remito_de_codigo("REMITO: 0001-0001 | BULTO: 1/2") == "0001-0001"
    assert extraer_datos_qr_despacho("REMITO:REM-9|BULTO:2/4") == {
        "remito": "REM-9",
        "bulto_num": 2,
        "total_bultos": 4,
    }
    resp = construir_respuesta_escaneo(ok=True, mensaje="OK", bultos_esperados=2)
    assert resp["ok"] is True and resp["bultos_escaneados"] == []

    # Verificar que deps re-exporta las mismas referencias de stores y tokens
    assert api_deps._sesiones_activas is api_tokens._sesiones_activas
    assert api_deps._doc_tokens is api_tokens._doc_tokens
    assert api_deps.get_user_store is api_stores.get_user_store
    api_deps._sesiones_activas["dummy"] = {"user_id": 1}
    api_deps.reset_api_stores(revocar_sesiones_memoria=True)
    assert api_deps._sesiones_activas == {}


def test_planificar_fabrica_dialogo_unificado_y_mercado_full_archiva(tmp_path: Path):
    store = OrderStore(tmp_path / "pedidos.sqlite3")
    mock_interfaz = MagicMock()
    mock_interfaz.order_store = store
    mock_interfaz.usuario_actual.nombre_identificador = "Admin"
    mock_interfaz.exigir_roles.return_value = True
    mock_interfaz.modo_oscuro = True
    mock_interfaz.secundario = "#888888"
    mock_interfaz.texto = "#ffffff"
    mock_interfaz.ancho_adaptable.return_value = 650
    mock_interfaz.menu.carpeta_fabrica = tmp_path / "Fabrica"
    mock_interfaz.menu.ruta_excel_base = tmp_path / "Productos.xlsx"

    mostrar_planificar_ingreso_fabrica(mock_interfaz)
    mock_interfaz.page.show_dialog.assert_called_once()

    # Verificar que _archivar_y_registrar_full ejecute shutil.move y datetime sin NameError
    origen = tmp_path / "full_envio.xlsx"
    origen.write_bytes(b"dummy")
    carpeta_desc = tmp_path / "Descontados"
    interfaz_full = SimpleNamespace(
        order_store=store,
        usuario_actual=User(id=1, username="picker1", role="picker", active=True, nombre="Picker 1"),
        menu=SimpleNamespace(ruta_excel_base=tmp_path / "Productos.xlsx", carpeta_descontados=carpeta_desc),
    )
    fake_sm = MagicMock()
    fake_sm.catalogo = {"SKU-1": (3, "Producto 1", 10)}
    fake_sm.descontar_mercado_full.return_value = [SimpleNamespace(codigo="SKU-1")]

    _archivar_y_registrar_full(interfaz_full, origen, {"SKU-1": 2}, stock_manager_factory=lambda: (lambda _p: fake_sm))
    assert not origen.exists()
    assert (carpeta_desc / "MercadoFull" / "full_envio.xlsx").exists()
    assert store.buscar_pedido_por_nota("FULL-full_envio") is not None


def test_fase4_y_pedidos_baja_modularizacion(tmp_path: Path):
    from src.products import ProductStore
    from src.products.locations_lots_repo import LocationsLotsRepository
    from src.products.locations_repo import WarehouseLocationsRepository
    from src.products.lots_fefo_repo import FefoLotsRepository
    from src.ui.dialogs import pedidos_baja, pedidos_baja_ops

    p_store = ProductStore(tmp_path / "productos.sqlite3")
    assert isinstance(p_store.locations_lots_repo, LocationsLotsRepository)
    assert isinstance(p_store.locations_lots_repo.locations, WarehouseLocationsRepository)
    assert isinstance(p_store.locations_lots_repo.lots, FefoLotsRepository)

    p_store.import_template_once([(1, "SKU-MOD", "Modulado", 20)])
    ubic = p_store.asignar_ubicacion_producto(
        "SKU-MOD", "A-01-1", tipo_zona="picking", stock=10, es_principal=True
    )
    assert ubic["ubicacion"] == "A-01-1" and ubic["es_principal"] is True

    lote = p_store.registrar_lote(
        "SKU-MOD", "LOT-MOD-1", 10, fecha_vencimiento="2027-01-15", ubicacion="A-01-1"
    )
    assert lote["lote"] == "LOT-MOD-1"
    assert len(p_store.listar_lotes_fefo("SKU-MOD")) == 1

    # Compatibilidad de re-exportación en pedidos_baja
    assert pedidos_baja._restituir_stock_pedido is pedidos_baja_ops._restituir_stock_pedido
    assert pedidos_baja._resolver_sm_cls is pedidos_baja_ops._resolver_sm_cls
    assert pedidos_baja._persistir_baja_pedido is pedidos_baja_ops._persistir_baja_pedido
    assert callable(pedidos_baja.mostrar_dialogo_confirmar_desarmar_pedido)
    assert callable(pedidos_baja.mostrar_dialogo_confirmar_eliminacion_pedido)
