"""Tests unitarios para la segregación de funciones (SoD) en Mercado Libre API:
- Rol Master: acceso completo a la configuración de credenciales (App ID, Client Secret, Tokens).
- Roles Administrador y Operador: acceso a sincronización y descuento de ventas sin exponer credenciales.
"""
from unittest.mock import MagicMock
import flet as ft
from src.ui.dialogs.dlg_mercadolibre import mostrar_dialogo_mercadolibre
from src.user_store import User


def test_dialogo_ml_solo_master_ve_credenciales():
    """Verifica que solo el usuario con rol Master tenga visible la pestaña de credenciales API."""
    
    # 1. Caso Administrador: no debe tener la pestaña de credenciales
    dialogo_admin = None
    def capturar_dialogo_admin(d):
        nonlocal dialogo_admin
        dialogo_admin = d

    interfaz_admin = MagicMock()
    interfaz_admin.usuario_actual = User(
        id=2, username="admin1", role="administrador",
        active=True, must_change_password=False, nombre="Admin", email="admin@empresa.com"
    )
    interfaz_admin.exigir_roles.return_value = True
    interfaz_admin.page.show_dialog = capturar_dialogo_admin

    mostrar_dialogo_mercadolibre(interfaz_admin)
    assert dialogo_admin is not None
    # El contenido debe ser un Container directo con vista_ordenes, no un ft.Tabs con credenciales
    assert not isinstance(dialogo_admin.content.content, ft.Tabs)

    # 2. Caso Operador: tampoco debe tener la pestaña de credenciales
    dialogo_operador = None
    def capturar_dialogo_op(d):
        nonlocal dialogo_operador
        dialogo_operador = d

    interfaz_operador = MagicMock()
    interfaz_operador.usuario_actual = User(
        id=3, username="operador1", role="operador",
        active=True, must_change_password=False, nombre="Operario", email="op@empresa.com"
    )
    interfaz_operador.exigir_roles.return_value = True
    interfaz_operador.page.show_dialog = capturar_dialogo_op

    mostrar_dialogo_mercadolibre(interfaz_operador)
    assert dialogo_operador is not None
    assert not isinstance(dialogo_operador.content.content, ft.Tabs)

    # 3. Caso Master: SÍ debe tener ft.Tabs con la pestaña de Credenciales
    dialogo_master = None
    def capturar_dialogo_master(d):
        nonlocal dialogo_master
        dialogo_master = d

    interfaz_master = MagicMock()
    interfaz_master.usuario_actual = User(
        id=1, username="Desarrollo", role="master",
        active=True, must_change_password=False, nombre="Master", email="master@empresa.com"
    )
    interfaz_master.exigir_roles.return_value = True
    interfaz_master.page.show_dialog = capturar_dialogo_master

    mostrar_dialogo_mercadolibre(interfaz_master)
    assert dialogo_master is not None
    assert isinstance(dialogo_master.content.content, ft.Tabs)
