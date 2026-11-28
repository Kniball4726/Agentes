"""Fuente única de verdad de versión para StockAgent (Backend, API, ejecutable Windows y cliente móvil)."""

from __future__ import annotations

APP_VERSION = "2.0.2"
APP_BUILD_NUMBER = 5


def obtener_version_completa() -> str:
    """Devuelve la versión en formato compatible con Flutter/pubspec (`X.Y.Z+BUILD`)."""
    return f"{APP_VERSION}+{APP_BUILD_NUMBER}"


if __name__ == "__main__":
    print(APP_VERSION)
