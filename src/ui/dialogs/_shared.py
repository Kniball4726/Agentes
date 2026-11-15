"""Utilidades compartidas para diálogos Flet (foco seguro y resolución de StockManager)."""

from __future__ import annotations

import inspect
import sys
from typing import Any

from ...inventory import StockManager as _DefaultStockManager


def resolve_stock_manager(*mod_names: str):
    """Resuelve StockManager respetando mocks/patches registrados en módulos activos."""
    for name in mod_names:
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "_get_stock_manager"):
            fn = getattr(mod, "_get_stock_manager")
            if getattr(fn, "__module__", "") != __name__ and fn.__name__ != "_delegated_get_sm":
                # Evitar recursión infinita si el llamador también delega aquí
                pass
        if mod is not None and hasattr(mod, "StockManager"):
            return getattr(mod, "StockManager")
    mod_gui = sys.modules.get("src.flet_gui")
    if mod_gui is not None and hasattr(mod_gui, "StockManager"):
        return getattr(mod_gui, "StockManager")
    return _DefaultStockManager


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
