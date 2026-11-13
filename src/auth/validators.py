"""Validadores y normalizadores de campos para cuentas de usuario."""

from __future__ import annotations

import sqlite3

from .models import EMAIL_REGEX, USER_ROLES, UserRole


def normalizar_usuario(username: str) -> str:
    """Normaliza y valida longitud y ausencia de espacios en nombres de usuario."""
    username = username.strip()
    if not 3 <= len(username) <= 64:
        raise ValueError("El usuario debe tener entre 3 y 64 caracteres.")
    if any(character.isspace() for character in username):
        raise ValueError("El usuario no puede contener espacios.")
    return username


def validar_rol(role: str) -> UserRole:
    """Valida que el rol pertenezca al catálogo oficial del sistema."""
    if role in USER_ROLES:
        return role  # type: ignore[return-value]
    raise ValueError("El rol seleccionado no es válido.")


def validar_nombre(nombre: str) -> str:
    """Limpia espacios y valida longitud y caracteres de control del nombre legible."""
    if not nombre:
        return ""
    nombre_limpio = " ".join(str(nombre).strip().split())
    if len(nombre_limpio) > 120:
        raise ValueError("El nombre no puede superar los 120 caracteres.")
    if any(ord(c) < 32 for c in nombre_limpio):
        raise ValueError("El nombre contiene caracteres de control no permitidos.")
    return nombre_limpio


def validar_email(email: str) -> str:
    """Valida formato RFC simplificado y longitud máxima del correo electrónico."""
    if not email:
        return ""
    email_limpio = str(email).strip().lower()
    if len(email_limpio) > 254:
        raise ValueError("El correo electrónico no puede superar los 254 caracteres.")
    if not EMAIL_REGEX.match(email_limpio):
        raise ValueError("El formato del correo electrónico no es válido.")
    return email_limpio


def verificar_email_unico(
    connection: sqlite3.Connection, email: str, except_user_id: int | None = None
) -> None:
    """Verifica unicidad case-insensitive del correo electrónico en SQLite."""
    if not email:
        return
    query = "SELECT id, username FROM users WHERE email = ? COLLATE NOCASE"
    params: list[object] = [email]
    if except_user_id is not None:
        query += " AND id != ?"
        params.append(except_user_id)
    row = connection.execute(query, params).fetchone()
    if row is not None:
        raise ValueError(
            f"El correo electrónico '{email}' ya se encuentra registrado por el usuario '{row['username']}'."
        )
