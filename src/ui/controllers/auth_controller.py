"""Controlador independiente para autenticación, perfil y seguridad de sesión."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import Any, Callable

import flet as ft

from ...auth import UserRole
from ..app_config import INACTIVIDAD_MAX_MINUTOS
from ..dialogs import (
    mostrar_cambiar_mi_clave,
    mostrar_cambio_clave_obligatorio,
    mostrar_configuracion_inicial,
    mostrar_inicio_sesion,
    mostrar_mi_perfil,
)

logger = logging.getLogger(__name__)


def obtener_inactividad_actual() -> int:
    mod = sys.modules.get("src.flet_gui")
    if mod is not None and hasattr(mod, "INACTIVIDAD_MAX_MINUTOS"):
        return int(mod.INACTIVIDAD_MAX_MINUTOS)
    return INACTIVIDAD_MAX_MINUTOS


class AuthSessionController:
    """Gestiona vistas de autenticación, expiración por inactividad y validación de roles."""

    def __init__(
        self,
        host: Any,
        inactivity_limit_fn: Callable[[], int] | None = None,
        notify_fn: Callable[[str], None] | None = None,
        ensure_file_picker_fn: Callable[..., None] | None = None,
    ) -> None:
        self._host = host
        self._inactivity_limit_fn = inactivity_limit_fn or obtener_inactividad_actual
        self._notify_fn = notify_fn
        self._ensure_file_picker_fn = ensure_file_picker_fn

    def _notificar(self, mensaje: str) -> None:
        fn = self._notify_fn or getattr(self._host, "notificar", None)
        if callable(fn):
            fn(mensaje)

    def _asegurar_picker(self, forzar_recrear: bool = False) -> None:
        fn = self._ensure_file_picker_fn or getattr(self._host, "_asegurar_file_picker", None)
        if callable(fn):
            fn(forzar_recrear=forzar_recrear)

    def mostrar_inicio_sesion(self, error: str = "") -> None:
        mostrar_inicio_sesion(self._host, error=error)

    def mostrar_cambio_clave_obligatorio(self) -> None:
        mostrar_cambio_clave_obligatorio(self._host)

    def mostrar_cambiar_mi_clave(self, _evento: ft.Event | None = None) -> None:
        mostrar_cambiar_mi_clave(self._host, _evento)

    def mostrar_mi_perfil(self, _evento: ft.Event | None = None) -> None:
        mostrar_mi_perfil(self._host, _evento)

    def mostrar_configuracion_inicial(self, error: str = "") -> None:
        mostrar_configuracion_inicial(self._host, error=error)

    def cerrar_sesion(self, _evento: ft.Event | None = None) -> None:
        self._host._heartbeat_activo = False
        self._host._heartbeat_iniciado = False
        usuario = getattr(self._host, "usuario_actual", None)
        if usuario is not None:
            try:
                self._host.order_store.registrar_auditoria(
                    usuario=usuario.username,
                    accion="LOGOUT",
                    detalle="Cierre de sesión manual",
                )
            except Exception:
                pass
            logger.info("Sesión cerrada manualmente por %s", usuario.username)
        self._host.usuario_actual = None
        self._host._prefs_cargadas_usuario = False
        self._host.controles_tarea.clear()
        botones_cierre = getattr(self._host, "botones_cierre_jornada", None)
        if botones_cierre is not None:
            botones_cierre.clear()
        self._host.btn_cierre_jornada = None
        self._host.conversacion.controls.clear()
        self._host.ventana_chat_flotante = None
        self._asegurar_picker(forzar_recrear=True)
        self.mostrar_inicio_sesion()

    def exigir_roles(self, *roles: UserRole) -> bool:
        """Verifica sesión activa, timeout por inactividad, vigencia de usuario y rol permitido."""
        usuario_actual = getattr(self._host, "usuario_actual", None)
        if usuario_actual is None:
            self.mostrar_inicio_sesion()
            return False

        ahora = datetime.now()
        inact_max = int(self._inactivity_limit_fn())
        ultima_act = getattr(self._host, "ultima_actividad", ahora)
        if inact_max > 0 and (ahora - ultima_act).total_seconds() > inact_max * 60:
            nom_exp = usuario_actual.username
            self._host.usuario_actual = None
            tiempo_inactividad = (
                f"{inact_max // 60} h" if inact_max % 60 == 0 else f"{inact_max} min"
            )
            try:
                self._host.order_store.registrar_auditoria(
                    usuario=nom_exp,
                    accion="LOGOUT_INACTIVIDAD",
                    detalle=f"Sesión cerrada automáticamente tras {tiempo_inactividad} de inactividad",
                )
            except Exception:
                pass
            logger.info("Sesión de '%s' expirada por inactividad (%s)", nom_exp, tiempo_inactividad)
            self.mostrar_inicio_sesion(
                f"Tu sesión se cerró por inactividad ({tiempo_inactividad}). vuelve a ingresar."
            )
            return False

        self._host.ultima_actividad = ahora

        usuario = None
        user_store = getattr(self._host, "user_store", None)
        if user_store:
            try:
                usuario_db = user_store.get_user(usuario_actual.id)
                if usuario_db and usuario_db.username.lower() == usuario_actual.username.lower():
                    usuario = usuario_db
            except Exception:
                pass
        if usuario is None:
            usuario = usuario_actual
        if usuario is None or not usuario.active:
            self._host.usuario_actual = None
            self.mostrar_inicio_sesion("La cuenta ya no está activa. Inicia sesión nuevamente.")
            return False
        self._host.usuario_actual = usuario
        if usuario.role not in roles:
            self._notificar("Tu rol no tiene permiso para realizar esta acción.")
            return False
        return True
