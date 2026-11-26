"""Gestión de almacenes con contexto por instancia/servidor sensibles al ambiente activo."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
import threading
from typing import Any, Callable, Iterator, Optional
import weakref

from ..auth import UserStore
from ..core.environment import get_db_path, get_descuentos_dir, get_environment
from ..inventory import StockManager
from ..orders import OrderStore
from ..products import ProductStore

_GLOBAL_TOKEN_RESET_LISTENERS: list[Callable[[], None]] = []
_LISTENERS_LOCK = threading.RLock()


class ApiStoreContext:
    """Contenedor aislado de almacenes de dominio para una instancia de servidor FastAPI."""

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._lock = threading.RLock()
        self._user_store: Optional[UserStore] = None
        self._product_store: Optional[ProductStore] = None
        self._order_store: Optional[OrderStore] = None
        self._stock_manager: Optional[StockManager] = None
        self._active_env_name: Optional[str] = None
        self.sesiones_activas: dict[str, dict[str, Any]] = {}
        self.doc_tokens: dict[str, dict[str, Any]] = {}
        with _LISTENERS_LOCK:
            self._token_reset_listeners: list[Callable[[], None]] = list(_GLOBAL_TOKEN_RESET_LISTENERS)

    def register_token_reset_listener(self, callback: Callable[[], None]) -> None:
        """Registra un callback de limpieza de cachés de tokens al reiniciar almacenes."""
        with self._lock:
            if callback not in self._token_reset_listeners:
                self._token_reset_listeners.append(callback)

    def reset(self, revocar_sesiones_memoria: bool = True) -> None:
        """Reinicia los almacenes de este contexto al cambiar de ambiente (Producción/QA)."""
        with self._lock:
            self._user_store = None
            self._product_store = None
            self._order_store = None
            self._stock_manager = None
            self._active_env_name = get_environment()
            listeners = list(self._token_reset_listeners)
        if revocar_sesiones_memoria:
            self.sesiones_activas.clear()
            self.doc_tokens.clear()
            for cb in listeners:
                cb()

    def _sincronizar_ambiente(self) -> None:
        with self._lock:
            env_actual = get_environment()
            if self._active_env_name is None:
                self._active_env_name = env_actual
            elif self._active_env_name != env_actual:
                self.reset(revocar_sesiones_memoria=True)

    def get_user_store(self) -> UserStore:
        """Devuelve el almacén de usuarios activo dentro de este contexto de servidor."""
        with self._lock:
            self._sincronizar_ambiente()
            if self._user_store is None:
                self._user_store = UserStore(get_db_path("usuarios.sqlite3"))
            return self._user_store

    def get_product_store(self) -> ProductStore:
        """Devuelve el almacén de productos activo dentro de este contexto de servidor."""
        with self._lock:
            self._sincronizar_ambiente()
            if self._product_store is None:
                self._product_store = ProductStore(get_db_path("productos.sqlite3"))
            return self._product_store

    def get_order_store(self) -> OrderStore:
        """Devuelve el almacén de pedidos activo dentro de este contexto de servidor."""
        with self._lock:
            self._sincronizar_ambiente()
            if self._order_store is None:
                self._order_store = OrderStore(get_db_path("pedidos.sqlite3"))
            return self._order_store

    def get_stock_manager(self) -> StockManager:
        """Devuelve el gestor de inventario activo dentro de este contexto de servidor."""
        with self._lock:
            self._sincronizar_ambiente()
            if self._stock_manager is None:
                excel_path = get_descuentos_dir() / "Productos.xlsx"
                self._stock_manager = StockManager(excel_path)
            return self._stock_manager


_DEFAULT_CONTEXT = ApiStoreContext("default")
_REGISTERED_CONTEXTS: weakref.WeakSet[ApiStoreContext] = weakref.WeakSet([_DEFAULT_CONTEXT])
_ACTIVE_API_CONTEXT: ContextVar[Optional[ApiStoreContext]] = ContextVar(
    "_ACTIVE_API_CONTEXT", default=None
)


def crear_contexto_api(name: str = "server") -> ApiStoreContext:
    """Crea y registra un contexto independiente de almacenes para una instancia ASGI."""
    ctx = ApiStoreContext(name=name)
    _REGISTERED_CONTEXTS.add(ctx)
    return ctx


def obtener_contexto_api_por_defecto() -> ApiStoreContext:
    """Devuelve el contexto raíz predeterminado del proceso."""
    return _DEFAULT_CONTEXT


def obtener_contextos_api_registrados() -> list[ApiStoreContext]:
    """Retorna una instantánea de los contextos de servidor registrados."""
    return list(_REGISTERED_CONTEXTS)


def obtener_contexto_api_actual() -> ApiStoreContext:
    """Retorna el contexto de almacenes vinculado a la petición actual o el contexto base."""
    return _ACTIVE_API_CONTEXT.get() or _DEFAULT_CONTEXT


def establecer_contexto_api(context: ApiStoreContext) -> Token[Optional[ApiStoreContext]]:
    """Vincula un `ApiStoreContext` al hilo/tarea asíncrona actual y retorna su token."""
    return _ACTIVE_API_CONTEXT.set(context)


def restaurar_contexto_api(token: Token[Optional[ApiStoreContext]]) -> None:
    """Restaura el contexto API previo tras completar el ciclo de una petición."""
    _ACTIVE_API_CONTEXT.reset(token)


@contextmanager
def usar_contexto_api(context: ApiStoreContext) -> Iterator[ApiStoreContext]:
    """Context manager explícito para operar temporalmente bajo un `ApiStoreContext`."""
    token = establecer_contexto_api(context)
    try:
        yield context
    finally:
        restaurar_contexto_api(token)


def register_token_reset_listener(callback: Callable[[], None]) -> None:
    """Registra un callback global para limpiar cachés de tokens al reiniciar almacenes."""
    with _LISTENERS_LOCK:
        if callback not in _GLOBAL_TOKEN_RESET_LISTENERS:
            _GLOBAL_TOKEN_RESET_LISTENERS.append(callback)
    for ctx in list(_REGISTERED_CONTEXTS):
        ctx.register_token_reset_listener(callback)


def reset_api_stores(revocar_sesiones_memoria: bool = True) -> None:
    """Reinicia los almacenes del contexto activo y de las instancias registradas."""
    actual = _ACTIVE_API_CONTEXT.get()
    if actual is not None:
        actual.reset(revocar_sesiones_memoria=revocar_sesiones_memoria)
        return
    for ctx in list(_REGISTERED_CONTEXTS):
        ctx.reset(revocar_sesiones_memoria=revocar_sesiones_memoria)


def get_user_store() -> UserStore:
    """Devuelve el almacén de usuarios activo según el contexto y ambiente configurado."""
    return obtener_contexto_api_actual().get_user_store()


def get_product_store() -> ProductStore:
    """Devuelve el almacén de productos activo según el contexto y ambiente configurado."""
    return obtener_contexto_api_actual().get_product_store()


def get_order_store() -> OrderStore:
    """Devuelve el almacén de pedidos activo según el contexto y ambiente configurado."""
    return obtener_contexto_api_actual().get_order_store()


def get_stock_manager() -> StockManager:
    """Devuelve el gestor de inventario activo según el contexto y ambiente configurado."""
    return obtener_contexto_api_actual().get_stock_manager()
