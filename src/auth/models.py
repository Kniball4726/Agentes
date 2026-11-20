"""Modelos de datos y constantes para el subsistema de autenticación y roles."""

import os
import re
from dataclasses import dataclass
from typing import Literal

UserRole = Literal["master", "administrador", "operador", "consulta", "picker", "despachador"]
USER_ROLES: tuple[UserRole, ...] = ("master", "administrador", "operador", "consulta", "picker", "despachador")
DEFAULT_MASTER_USERNAME = "Auditoria"
DEFAULT_MASTER_PASSWORD = "master1713"


def _master_default_credentials() -> tuple[str, str]:
    return (
        os.getenv("STOCKAGENT_MASTER_USER") or DEFAULT_MASTER_USERNAME,
        os.getenv("STOCKAGENT_MASTER_PASSWORD") or DEFAULT_MASTER_PASSWORD,
    )


PASSWORD_ITERATIONS = 600_000
PASSWORD_MIN_LENGTH = 10
MAX_FAILED_ATTEMPTS = 5
FAILED_WINDOW_SECONDS = 15 * 60
LOCKOUT_SECONDS = 15 * 60

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
)


@dataclass(frozen=True)
class User:
    """Entidad inmutable que representa una cuenta de usuario."""

    id: int
    username: str
    role: UserRole
    active: bool
    must_change_password: bool = False
    nombre: str = ""
    email: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def nombre_identificador(self) -> str:
        """Nombre usado para identificar al usuario tanto en el sistema como en documentos."""
        if self.nombre and self.nombre.strip():
            return self.nombre.strip()
        return self.username

    @property
    def display_name(self) -> str:
        """Alias amigable de nombre_identificador."""
        return self.nombre_identificador


@dataclass(frozen=True)
class AuthResult:
    """Resultado detallado de un intento de inicio de sesión."""

    user: User | None
    status: str  # "ok" | "invalid" | "inactive" | "locked"
    retry_after: int = 0  # segundos restantes de bloqueo (solo si status == "locked")
    attempts_left: int | None = None

    @property
    def locked(self) -> bool:
        return self.status == "locked"

    @property
    def remaining_attempts(self) -> int | None:
        return self.attempts_left

    @property
    def error(self) -> str:
        if self.status == "ok":
            return ""
        if self.status == "locked":
            mins = max(1, (self.retry_after + 59) // 60)
            return f"Cuenta bloqueada temporalmente por seguridad. Intentá de nuevo en {mins} min."
        if self.status == "inactive":
            return "Esta cuenta se encuentra deshabilitada. Contactá a un administrador."
        if self.attempts_left is not None:
            return f"Usuario o contraseña incorrectos ({self.attempts_left} intento(s) restante(s))."
        return "Usuario o contraseña incorrectos."
