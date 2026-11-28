"""Gestión centralizada de perfiles y ambientes de ejecución (Producción, QA, Testing)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from ..paths import application_root

logger = logging.getLogger("stockagent.env")


def _get_env_file() -> Path:
    return application_root() / ".env_active"


def get_environment() -> str:
    """Devuelve el entorno actual configurado ('production', 'qa', 'testing')."""
    if "STOCKAGENT_ENV" in os.environ:
        return os.environ["STOCKAGENT_ENV"].strip().lower()

    env_file = _get_env_file()
    if env_file.exists():
        try:
            val = env_file.read_text(encoding="utf-8").strip().lower()
            if val in ("qa", "test", "testing", "sandbox"):
                return "qa"
        except OSError as exc:
            logger.warning("No se pudo leer el archivo de entorno %s: %s", env_file, exc)

    return "production"


def set_environment(env: str, persistir: bool = True) -> None:
    """Establece explícitamente el entorno de ejecución en memoria y opcionalmente en disco."""
    clean = "qa" if env.strip().lower() in ("qa", "test", "testing", "sandbox") else "production"
    os.environ["STOCKAGENT_ENV"] = clean
    if persistir:
        try:
            _get_env_file().write_text(clean, encoding="utf-8")
        except OSError as exc:
            logger.warning("No se pudo persistir el entorno '%s' en disco: %s", clean, exc)


def is_qa_environment() -> bool:
    """Indica si la aplicación se está ejecutando en ambiente de pruebas o QA manual."""
    return get_environment() in ("qa", "test", "testing", "sandbox")


def resolver_data_dir_para_raiz(raiz: Path) -> Path:
    """Resuelve `data/` o `data_qa/` relativo a `raiz` respetando STOCKAGENT_ENV y `raiz/.env_active`."""
    env_explicito = os.environ.get("STOCKAGENT_ENV", "").strip().lower()
    if env_explicito:
        es_qa = env_explicito in ("qa", "test", "testing", "sandbox")
    else:
        env_file = Path(raiz) / ".env_active"
        if env_file.exists():
            try:
                es_qa = env_file.read_text(encoding="utf-8").strip().lower() in ("qa", "test", "testing", "sandbox")
            except Exception:
                es_qa = False
        else:
            es_qa = False
    return Path(raiz) / ("data_qa" if es_qa else "data")


def get_data_dir() -> Path:
    """Devuelve la ruta absoluta del directorio de datos según el ambiente activo."""
    if is_qa_environment():
        data_dir = application_root() / "data_qa"
    else:
        data_dir = application_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_descuentos_dir() -> Path:
    """Devuelve la ruta absoluta del directorio de planillas y comprobantes según el ambiente activo."""
    if is_qa_environment():
        desc_dir = application_root() / "Descuentos_QA"
    else:
        desc_dir = application_root() / "Descuentos"
    desc_dir.mkdir(parents=True, exist_ok=True)
    return desc_dir


def get_db_path(database_name: str) -> Path:
    """Devuelve la ruta de una base de datos SQLite específica dentro del directorio de datos activo."""
    return get_data_dir() / database_name
