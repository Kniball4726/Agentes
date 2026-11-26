"""Gestión de almacenes singleton sensibles al ambiente activo para la API REST."""

from __future__ import annotations

from typing import Callable, Optional

from ..auth import UserStore
from ..core.environment import get_db_path, get_descuentos_dir, get_environment
from ..inventory import StockManager
from ..orders import OrderStore
from ..products import ProductStore

_user_store: Optional[UserStore] = None
_product_store: Optional[ProductStore] = None
_order_store: Optional[OrderStore] = None
_stock_manager: Optional[StockManager] = None
_active_env_name: Optional[str] = None
_token_reset_listeners: list[Callable[[], None]] = []


def register_token_reset_listener(callback: Callable[[], None]) -> None:
    """Registra un callback para limpiar cachés de tokens al reiniciar almacenes de ambiente."""
    if callback not in _token_reset_listeners:
        _token_reset_listeners.append(callback)


def reset_api_stores(revocar_sesiones_memoria: bool = True) -> None:
    """Reinicia los almacenes singleton de la API al cambiar de ambiente (Producción/QA)."""
    global _user_store, _product_store, _order_store, _stock_manager, _active_env_name
    _user_store = None
    _product_store = None
    _order_store = None
    _stock_manager = None
    _active_env_name = get_environment()
    if revocar_sesiones_memoria:
        for cb in list(_token_reset_listeners):
            cb()


def _sincronizar_ambiente_api() -> None:
    """Detecta cambios de ambiente (Producción <-> QA) y recarga almacenes automáticamente."""
    global _active_env_name
    env_actual = get_environment()
    if _active_env_name is None:
        _active_env_name = env_actual
    elif _active_env_name != env_actual:
        reset_api_stores(revocar_sesiones_memoria=True)


def get_user_store() -> UserStore:
    """Devuelve el almacén de usuarios activo según el ambiente configurado."""
    global _user_store
    _sincronizar_ambiente_api()
    if _user_store is None:
        _user_store = UserStore(get_db_path("usuarios.sqlite3"))
    return _user_store


def get_product_store() -> ProductStore:
    """Devuelve el almacén de productos activo según el ambiente configurado."""
    global _product_store
    _sincronizar_ambiente_api()
    if _product_store is None:
        _product_store = ProductStore(get_db_path("productos.sqlite3"))
    return _product_store


def get_order_store() -> OrderStore:
    """Devuelve el almacén de pedidos activo según el ambiente configurado."""
    global _order_store
    _sincronizar_ambiente_api()
    if _order_store is None:
        _order_store = OrderStore(get_db_path("pedidos.sqlite3"))
    return _order_store


def get_stock_manager() -> StockManager:
    """Devuelve el gestor de inventario activo según el ambiente configurado."""
    global _stock_manager
    _sincronizar_ambiente_api()
    if _stock_manager is None:
        excel_path = get_descuentos_dir() / "Productos.xlsx"
        _stock_manager = StockManager(excel_path)
    return _stock_manager
