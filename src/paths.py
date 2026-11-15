"""Application paths shared by source runs and packaged executables."""

import sys
from pathlib import Path


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_data_dir() -> Path:
    from .core.environment import get_data_dir as _gdd
    return _gdd()


def get_descuentos_dir() -> Path:
    from .core.environment import get_descuentos_dir as _gddir
    return _gddir()


def get_db_path(database_name: str) -> Path:
    from .core.environment import get_db_path as _gdbp
    return _gdbp(database_name)


def is_qa_environment() -> bool:
    from .core.environment import is_qa_environment as _iqa
    return _iqa()


def get_environment() -> str:
    from .core.environment import get_environment as _genv
    return _genv()


def set_environment(env: str) -> None:
    from .core.environment import set_environment as _senv
    _senv(env)
