"""Utilidades compartidas para diálogos Flet (foco seguro, dependencias inyectadas y diseño)."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable
from unittest.mock import NonCallableMock

from ...paths import application_root as _default_app_root
from ..design import (  # noqa: F401 - reexportados para todos los diálogos
    boton_cancelar,
    boton_dialogo_semantico,
    boton_peligro,
    boton_primario,
    campo_numerico,
    campo_secreto_seguro,
    colores_de,
    colores_semanticos,
    confirmar_accion_destructiva,
    crear_dialogo_estandar,
    fijar_ocupado,
    limpiar_errores,
    marcar_error,
    resolver_secreto,
    validar_entero_no_negativo,
    validar_fecha_ddmmaaaa,
)


def _obtener_atributo_explicito(obj: Any, nombre: str) -> Any:
    """Obtiene un atributo explícito sin disparar autogeneración en mocks de pruebas."""
    if obj is None:
        return None
    if isinstance(obj, NonCallableMock):
        return obj.__dict__.get(nombre)
    return getattr(obj, nombre, None)


def resolve_stock_manager(
    interfaz: Any = None,
    *,
    stock_manager_factory: Callable[..., Any] | None = None,
) -> Any:
    """Resuelve la clase/fábrica StockManager mediante inyección desde `interfaz`/`AppDependencies`."""
    if callable(stock_manager_factory):
        return stock_manager_factory

    deps = _obtener_atributo_explicito(interfaz, "_deps")
    deps_factory = _obtener_atributo_explicito(deps, "stock_manager_factory")
    if callable(deps_factory):
        return deps_factory

    resolver = _obtener_atributo_explicito(interfaz, "resolver_stock_manager")
    if callable(resolver):
        factory = resolver()
        if callable(factory):
            return factory

    for attr in ("stock_manager_factory", "_stock_manager_factory"):
        cand = _obtener_atributo_explicito(interfaz, attr)
        if callable(cand):
            return cand

    from ...inventory import StockManager

    return StockManager


def resolve_app_root(
    interfaz: Any = None,
    *,
    app_root_fn: Callable[[], Path] | None = None,
) -> Path:
    """Resuelve la raíz de la aplicación mediante inyección en `interfaz`/`AppDependencies`."""
    if callable(app_root_fn):
        return Path(app_root_fn())

    deps = _obtener_atributo_explicito(interfaz, "_deps")
    deps_root_fn = _obtener_atributo_explicito(deps, "app_root_fn")
    if callable(deps_root_fn):
        return Path(deps_root_fn())

    resolver = _obtener_atributo_explicito(interfaz, "resolver_app_root")
    if callable(resolver):
        return Path(resolver())

    for attr in ("app_root_fn", "_app_root_fn"):
        cand = _obtener_atributo_explicito(interfaz, attr)
        if callable(cand):
            return Path(cand())

    return Path(_default_app_root())


def safe_focus(interfaz: Any, ctrl: Any) -> None:
    """Ejecuta el foco sobre un control sin fallar ante corrutinas en entornos sync/async."""
    try:
        res = ctrl.focus()
        if inspect.iscoroutine(res):
            if (
                hasattr(interfaz, "page")
                and hasattr(interfaz.page, "run_task")
                and callable(interfaz.page.run_task)
                and not getattr(interfaz.page, "_is_mock", False)
                and not hasattr(interfaz.page, "mock_calls")
            ):
                async def _f():
                    await res

                interfaz.page.run_task(_f)
            else:
                res.close()
    except Exception:
        pass
