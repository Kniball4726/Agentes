"""Configuración centralizada de logging en archivo rotativo para el sistema."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import application_root

_CONFIGURADO = False


def obtener_ruta_log() -> Path:
    """Devuelve la ruta del archivo principal de log en data/logs/stockagent.log."""
    log_dir = application_root() / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "stockagent.log"


def configurar_logging(nivel: int = logging.INFO) -> logging.Logger:
    """Inicializa el logger raíz y el logger 'stockagent' con rotación de archivos (2 MB x 5)."""
    global _CONFIGURADO
    logger = logging.getLogger("stockagent")
    if _CONFIGURADO:
        return logger

    ruta_log = obtener_ruta_log()
    formato = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        file_handler = RotatingFileHandler(
            ruta_log,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formato)
        file_handler.setLevel(nivel)

        root_logger = logging.getLogger()
        if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
            root_logger.addHandler(file_handler)
        if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
            logger.addHandler(file_handler)
        if root_logger.level == logging.NOTSET or root_logger.level > nivel:
            root_logger.setLevel(nivel)

        logger.setLevel(nivel)
        _CONFIGURADO = True
        logger.info("Sistema de logs inicializado en %s", ruta_log)
    except Exception:
        pass

    return logger
