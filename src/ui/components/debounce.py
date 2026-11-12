"""Utilidad de debounce para campos de búsqueda y filtros reactivos."""

from __future__ import annotations

import threading
from typing import Any, Callable


class Debouncer:
    """Ejecuta una función diferida cancelando ejecuciones intermedias dentro del periodo de espera."""

    def __init__(self, delay_seconds: float = 0.25) -> None:
        self.delay_seconds = delay_seconds
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def debounce(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.delay_seconds, fn, args=args, kwargs=kwargs)
            self._timer.daemon = True
            self._timer.start()

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
