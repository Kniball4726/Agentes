"""Fachada de compatibilidad hacia atrás para el subsistema de usuarios y autenticación.

Re-exporta los símbolos del módulo modularizado `src.auth` para garantizar que
todos los imports heredados sigan funcionando sin cambios.
"""

from .auth import (
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
    UserStoreError,
    User,
    AuthResult,
    UserStore,
    _master_default_credentials,
)

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
    "UserStoreError",
    "User",
    "AuthResult",
    "UserStore",
    "_master_default_credentials",
]
