"""Funciones de hashing y validación segura de contraseñas con PBKDF2-HMAC-SHA256."""

import hashlib
import hmac
import secrets

from .models import PASSWORD_ITERATIONS, PASSWORD_MIN_LENGTH


def hash_clave(clave: str) -> str:
    """Genera un hash seguro PBKDF2-HMAC-SHA256 con salt criptográfica."""
    salt = secrets.token_hex(16)
    derivada = hashlib.pbkdf2_hmac(
        "sha256",
        clave.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"pbkdf2:sha256:{PASSWORD_ITERATIONS}${salt}${derivada}"


def verificar_clave(clave: str, hash_almacenado: str) -> bool:
    """Verifica una contraseña contra un hash almacenado de forma segura en tiempo constante."""
    try:
        prefijo, salt, derivada = hash_almacenado.split("$")
        iteraciones = int(prefijo.split(":")[-1])
        candidata = hashlib.pbkdf2_hmac(
            "sha256",
            clave.encode("utf-8"),
            salt.encode("utf-8"),
            iteraciones,
        ).hex()
        return hmac.compare_digest(candidata, derivada)
    except (ValueError, TypeError, AttributeError):
        return False


def validar_clave(clave: str) -> None:
    """Valida los requisitos de longitud para contraseñas."""
    if len(clave) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres.")
