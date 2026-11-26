"""Pruebas para eliminación física (Eliminar) y borrado lógico (Desarmar) de pedidos."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import flet as ft
import openpyxl

from src.auth import User
from src.inventory import StockManager
from src.orders import OrderStore, Pedido
from src.stock.models import RegistroDescuento
from src.ui.dashboard.pedidos_turno_view import renderizar_pedidos_preparados_turno
from src.ui.dialogs.dlg_pedidos import (
    mostrar_dialogo_confirmar_desarmar_pedido,
    mostrar_dialogo_confirmar_eliminacion_pedido,
)
from src.ui.dialogs.historial_cards import (
    _construir_fila_pedido,
    construir_cabecera_columnas_historial,
)
from src.ui.dialogs.historial_vista import mostrar_historial_pedidos


def _crear_entorno_stock_y_pedidos(tmp_path: Path):
    excel_path = tmp_path / "Productos.xlsx"
    db_prod_path = tmp_path / "productos.sqlite3"
    db_ped_path = tmp_path / "pedidos.sqlite3"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["CÓDIGO", "PRODUCTOS", "STOCK"])
    ws.append([])
    ws.append(["PROD-1", "Proteina 1kg", 50])
    ws.append(["PROD-2", "Creatina 300g", 20])
    wb.save(excel_path)
    wb.close()

    stock_mgr = StockManager(excel_path, ruta_base_datos=db_prod_path)
    order_store = OrderStore(db_ped_path)

    stock_mgr.actualizar_stock_base(
        descuentos=[
            RegistroDescuento(
                codigo="PROD-1",
                nombre_producto="Proteina 1kg",
                fila_excel=3,
                stock_anterior=50,
                cantidad_descontada=5,
                stock_nuevo=45,
            ),
            RegistroDescuento(
                codigo="PROD-2",
                nombre_producto="Creatina 300g",
                fila_excel=4,
                stock_anterior=20,
                cantidad_descontada=3,
                stock_nuevo=17,
            ),
        ],
        sincronizar_excel=True,
        nombre_archivo="Remito_101.pdf",
        usuario="operario1",
    )

    order_store.registrar_transaccion_idempotente("PED_REM-101_abcd1234", "CREAR_PEDIDO", "REM-101")
    pedido = order_store.registrar_pedido(
        nota_pedido="REM-101",
        numero_pedido="101",
        cliente="Cliente Prueba",
        bultos=2,
        logistica="Domicilio",
        armador="operario1",
        tipo_archivo="pdf",
        nombre_archivo="Remito_101.pdf",
        items=[("PROD-1", "Proteina 1kg", 5), ("PROD-2", "Creatina 300g", 3)],
        archivo_hash="abcd1234",
    )
    return excel_path, db_prod_path, order_store, pedido


def _crear_interfaz_falsa(order_store, excel_path: Path, db_prod_path: Path, role: str = "operador"):
    interfaz = MagicMock()
    interfaz.usuario_actual = User(id=1, username="operario1", role=role, active=True, nombre="Operario 1")
    interfaz.order_store = order_store
    interfaz.ruta_base_datos = db_prod_path
    interfaz.menu = SimpleNamespace(ruta_excel_base=excel_path, ruta_base_datos=db_prod_path)
    interfaz.modo_oscuro = True
    interfaz.es_pantalla_movil = False
    interfaz.texto = ft.Colors.WHITE
    interfaz.secundario = ft.Colors.GREY_400
    interfaz.superficie = ft.Colors.GREY_900
    interfaz.fondo = ft.Colors.BLACK
    interfaz.fondo_acento = ft.Colors.GREY_900
    interfaz.borde = ft.Colors.GREY_800
    interfaz.ancho_adaptable = lambda w: w
    interfaz.boton_dialogo = lambda txt, cb: ft.TextButton(txt, on_click=cb)
    interfaz.lista_pedidos_preparados = ft.Column()
    interfaz.header_pedidos_fecha = ft.Text("")
    interfaz.header_pedidos_subtitulo = ft.Text("")
    interfaz.header_pedidos_bultos = ft.Text("")
    return interfaz


def _extraer_icon_buttons(control) -> list[ft.IconButton]:
    botones: list[ft.IconButton] = []
    if isinstance(control, ft.IconButton):
        botones.append(control)
    content = getattr(control, "content", None)
    if content is not None:
        botones.extend(_extraer_icon_buttons(content))
    for hijo in getattr(control, "controls", None) or []:
        botones.extend(_extraer_icon_buttons(hijo))
    return botones


def test_order_store_eliminar_pedido_fisico_y_reutilizar_remito(tmp_path: Path):
    """Verifica que eliminar_pedido borre físicamente el pedido, cascada, bloqueos e idempotencia."""
    _, _, store, pedido = _crear_entorno_stock_y_pedidos(tmp_path)
    store.adquirir_bloqueo_pedido(pedido.id, "operario1")

    eliminado = store.eliminar_pedido(pedido.id, motivo="Carga errónea", usuario="operario1")
    assert eliminado.id == pedido.id
    assert store.obtener_pedido_por_id(pedido.id) is None
    assert store.buscar_pedido_por_nota("REM-101") is None
    assert store.existe_nota_pedido("REM-101") is False
    assert store.obtener_items_pedido(pedido.id) == []
    assert store.consultar_bloqueo_pedido(pedido.id) is None

    # Debe permitir volver a registrar exactamente la misma transacción y nota de pedido
    assert store.registrar_transaccion_idempotente("PED_REM-101_abcd1234", "CREAR_PEDIDO", "REM-101") is True
    nuevo = store.registrar_pedido(
        nota_pedido="REM-101",
        numero_pedido="101",
        cliente="Cliente Prueba",
        bultos=2,
        logistica="Domicilio",
        armador="operario1",
        tipo_archivo="pdf",
        nombre_archivo="Remito_101.pdf",
        items=[("PROD-1", "Proteina 1kg", 5)],
        archivo_hash="abcd1234",
    )
    assert nuevo.nota_pedido == "REM-101"

    logs = store.listar_auditoria(filtro_accion="ELIMINAR_PEDIDO")
    assert len(logs) == 1
    assert "REM-101" in logs[0].detalle


def test_dialogo_desarmar_borrado_logico_restituye_stock(tmp_path: Path):
    """Desarmar mantiene el registro como 'anulado' (borrado lógico) y devuelve stock."""
    excel_path, db_prod_path, store, pedido = _crear_entorno_stock_y_pedidos(tmp_path)
    interfaz = _crear_interfaz_falsa(store, excel_path, db_prod_path, role="operador")
    callback_final = MagicMock()

    mostrar_dialogo_confirmar_desarmar_pedido(interfaz, pedido, al_final=callback_final)
    interfaz.page.show_dialog.assert_called_once()
    dialogo = interfaz.page.show_dialog.call_args[0][0]
    btn_confirmar = dialogo.actions[0]
    btn_confirmar.on_click(MagicMock())

    ped_post = store.obtener_pedido_por_id(pedido.id)
    assert ped_post is not None
    assert ped_post.estado == "anulado"
    assert store.existe_nota_pedido("REM-101") is True

    sm_after = StockManager(excel_path, ruta_base_datos=db_prod_path)
    assert sm_after.product_store.get_product("PROD-1")["stock"] == 50
    assert sm_after.product_store.get_product("PROD-2")["stock"] == 20
    callback_final.assert_called_once()
    interfaz.actualizar_listas.assert_called_once()

    logs = store.listar_auditoria(filtro_accion="DESARMAR_PEDIDO")
    assert len(logs) == 1


def test_dialogo_eliminar_borrado_fisico_restituye_stock_sin_duplicar_si_ya_anulado(tmp_path: Path):
    """Eliminar borra físicamente y restituye stock si estaba activo, o sin duplicar si ya estaba anulado."""
    excel_path, db_prod_path, store, pedido = _crear_entorno_stock_y_pedidos(tmp_path)
    interfaz = _crear_interfaz_falsa(store, excel_path, db_prod_path, role="operador")
    callback_final = MagicMock()

    # 1. Eliminar pedido activo -> devuelve stock y borra registro físico
    mostrar_dialogo_confirmar_eliminacion_pedido(interfaz, pedido, al_final=callback_final)
    dialogo = interfaz.page.show_dialog.call_args[0][0]
    dialogo.actions[0].on_click(MagicMock())

    assert store.obtener_pedido_por_id(pedido.id) is None
    assert store.existe_nota_pedido("REM-101") is False

    sm_after = StockManager(excel_path, ruta_base_datos=db_prod_path)
    assert sm_after.product_store.get_product("PROD-1")["stock"] == 50
    assert sm_after.product_store.get_product("PROD-2")["stock"] == 20
    callback_final.assert_called_once()

    # 2. Registrar otro pedido, desarmarlo primero (stock vuelve a 50/20), luego eliminarlo físicamente
    sm_after.actualizar_stock_base(
        descuentos=[
            RegistroDescuento("PROD-1", "Proteina 1kg", 3, 50, 4, 46),
        ],
        sincronizar_excel=True,
        nombre_archivo="Remito_102.pdf",
        usuario="operario1",
    )
    ped2 = store.registrar_pedido(
        nota_pedido="REM-102",
        numero_pedido="102",
        cliente="Cliente 2",
        bultos=1,
        logistica="Domicilio",
        armador="operario1",
        tipo_archivo="pdf",
        nombre_archivo="Remito_102.pdf",
        items=[("PROD-1", "Proteina 1kg", 4)],
    )
    store.anular_pedido(ped2.id, motivo="Desarme previo", usuario="operario1")
    sm_after.registrar_ingreso_fabrica({"PROD-1": 4}, sobrescribir=False)  # stock ahora en 50

    ped2_anulado = store.obtener_pedido_por_id(ped2.id)
    assert ped2_anulado is not None and ped2_anulado.estado == "anulado"

    interfaz.page.show_dialog.reset_mock()
    mostrar_dialogo_confirmar_eliminacion_pedido(interfaz, ped2_anulado)
    dlg2 = interfaz.page.show_dialog.call_args[0][0]
    dlg2.actions[0].on_click(MagicMock())

    assert store.obtener_pedido_por_id(ped2.id) is None
    sm_final = StockManager(excel_path, ruta_base_datos=db_prod_path)
    # No debe haber devuelto +4 una segunda vez (debe permanecer en 50, no 54)
    assert sm_final.product_store.get_product("PROD-1")["stock"] == 50


def test_permisos_desarmar_y_eliminar_bloquean_roles_no_autorizados(tmp_path: Path):
    """Picker y consulta no pueden abrir los diálogos de desarmar ni eliminar."""
    excel_path, db_prod_path, store, pedido = _crear_entorno_stock_y_pedidos(tmp_path)
    for rol in ("picker", "consulta", "despachador"):
        interfaz = _crear_interfaz_falsa(store, excel_path, db_prod_path, role=rol)
        mostrar_dialogo_confirmar_desarmar_pedido(interfaz, pedido)
        mostrar_dialogo_confirmar_eliminacion_pedido(interfaz, pedido)
        assert not interfaz.page.show_dialog.called
        assert interfaz.notificar.call_count == 2


def test_tarjetas_panel_principal_y_filas_historial_muestran_desarmar_y_eliminar_para_operario(tmp_path: Path):
    """Verifica botones Desarmar y Eliminar en panel principal y filas del historial solo para operario."""
    excel_path, db_prod_path, store, pedido = _crear_entorno_stock_y_pedidos(tmp_path)
    interfaz_op = _crear_interfaz_falsa(store, excel_path, db_prod_path, role="operador")

    # 1. Panel principal (Dashboard)
    renderizar_pedidos_preparados_turno(interfaz_op, [pedido])
    card = interfaz_op.lista_pedidos_preparados.controls[0]
    iconos_card = [b.icon for b in _extraer_icon_buttons(card)]
    assert ft.Icons.EDIT_OUTLINED in iconos_card
    assert ft.Icons.REMOVE_SHOPPING_CART_OUTLINED in iconos_card
    assert ft.Icons.DELETE_OUTLINE in iconos_card

    # 2. Filas de historial (cabecera + fila activa + fila anulada)
    cab_op = construir_cabecera_columnas_historial(interfaz_op)
    assert any(
        isinstance(getattr(c, "content", None), ft.Text) and c.content.value == "Acciones"
        for c in cab_op.content.controls
    )

    fila_activa = _construir_fila_pedido(
        interfaz_op,
        pedido,
        set(),
        lambda _e, _id: None,
        lambda _e: None,
        lambda _p, _s: None,
        on_recargar=MagicMock(),
    )
    btns_fila = _extraer_icon_buttons(fila_activa)
    btn_desarmar = next(b for b in btns_fila if b.icon == ft.Icons.REMOVE_SHOPPING_CART_OUTLINED)
    btn_eliminar = next(b for b in btns_fila if b.icon == ft.Icons.DELETE_OUTLINE)
    assert btn_desarmar.disabled is False
    assert btn_eliminar.disabled is False

    # Clic en ambos botones delega al coordinador pasando callback de recarga
    btn_desarmar.on_click(MagicMock())
    interfaz_op.confirmar_desarmar_pedido.assert_called_once()
    btn_eliminar.on_click(MagicMock())
    interfaz_op.confirmar_eliminacion_pedido.assert_called_once()

    # En fila ya anulada: Desarmar deshabilitado, Eliminar habilitado
    ped_anulado = Pedido(**{**pedido.__dict__, "estado": "anulado"})
    fila_anulada = _construir_fila_pedido(
        interfaz_op,
        ped_anulado,
        set(),
        lambda _e, _id: None,
        lambda _e: None,
        lambda _p, _s: None,
    )
    btns_anulada = _extraer_icon_buttons(fila_anulada)
    btn_des_anulado = next(b for b in btns_anulada if b.icon == ft.Icons.REMOVE_SHOPPING_CART_OUTLINED)
    btn_elim_anulado = next(b for b in btns_anulada if b.icon == ft.Icons.DELETE_OUTLINE)
    assert btn_des_anulado.disabled is True
    assert btn_elim_anulado.disabled is False

    # 3. Administrador no ve botones de acción operativa en tarjetas ni columna Acciones en filas
    interfaz_adm = _crear_interfaz_falsa(store, excel_path, db_prod_path, role="administrador")
    renderizar_pedidos_preparados_turno(interfaz_adm, [pedido])
    card_adm = interfaz_adm.lista_pedidos_preparados.controls[0]
    iconos_adm = [b.icon for b in _extraer_icon_buttons(card_adm)]
    assert ft.Icons.REMOVE_SHOPPING_CART_OUTLINED not in iconos_adm
    assert ft.Icons.DELETE_OUTLINE not in iconos_adm

    cab_adm = construir_cabecera_columnas_historial(interfaz_adm)
    assert not any(
        isinstance(getattr(c, "content", None), ft.Text) and c.content.value == "Acciones"
        for c in cab_adm.content.controls
    )

    # 4. Flujo integrado en mostrar_historial_pedidos para operador
    mostrar_historial_pedidos(interfaz_op)
    assert interfaz_op.page.show_dialog.called
