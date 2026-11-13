"""Módulo de autenticación, control de accesos (IAM), sesiones y claves API."""

from .models import (
    UserRole,
    USER_ROLES,
    DEFAULT_MASTER_USERNAME,
    DEFAULT_MASTER_PASSWORD,
    PASSWORD_ITERATIONS,
    PASSWORD_MIN_LENGTH,
    MAX_FAILED_ATTEMPTS,
    FAILED_WINDOW_SECONDS,
    LOCKOUT_SECONDS,
    EMAIL_REGEX,
    User,
    AuthResult,
    _master_default_credentials,
)
from ..core.exceptions import UserStoreError
from .events import register_session_revocation_listener
from .store import UserStore

__all__ = [
    "UserRole",
    "USER_ROLES",
    "DEFAULT_MASTER_USERNAME",
    "DEFAULT_MASTER_PASSWORD",
    "PASSWORD_ITERATIONS",
    "PASSWORD_MIN_LENGTH",
    "MAX_FAILED_ATTEMPTS",
    "FAILED_WINDOW_SECONDS",
    "LOCKOUT_SECONDS",
    "EMAIL_REGEX",
    "User",
    "AuthResult",
    "UserStoreError",
    "UserStore",
    "_master_default_credentials",
    "register_session_revocation_listener",
]
