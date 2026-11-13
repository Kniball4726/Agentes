"""Mixin para autenticación, perfil, cierre de sesión y control de roles/inactividad."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import Any

import flet as ft

from ...user_store import UserRole
from ..app_config import INACTIVIDAD_MAX_MINUTOS
from ..dialogs import (
    mostrar_cambiar_mi_clave,
    mostrar_cambio_clave_obligatorio,
    mostrar_configuracion_inicial,
    mostrar_inicio_sesion,
    mostrar_mi_perfil,
)

logger = logging.getLogger(__name__)


def _obtener_inactividad_actual() -> int:
    mod = sys.modules.get("src.flet_gui")
    if mod is not None and hasattr(mod, "INACTIVIDAD_MAX_MINUTOS"):
        return int(mod.INACTIVIDAD_MAX_MINUTOS)
    return INACTIVIDAD_MAX_MINUTOS


class AuthSessionMixin:
    """Gestiona las vistas de login/perfil y la validación de roles e inactividad."""

    usuario_actual: Any
    user_store: Any
    order_store: Any
    ultima_actividad: datetime
    controles_tarea: list[ft.Button]
    conversacion: ft.ListView
    ventana_chat_flotante: ft.Container | None
    btn_cierre_jornada: ft.Button | None

    def mostrar_inicio_sesion(self, error: str = "") -> None:
        mostrar_inicio_sesion(self, error=error)

    def mostrar_cambio_clave_obligatorio(self) -> None:
        mostrar_cambio_clave_obligatorio(self)

    def mostrar_cambiar_mi_clave(self, _evento: ft.Event | None = None) -> None:
        mostrar_cambiar_mi_clave(self, _evento)

    def mostrar_mi_perfil(self, _evento: ft.Event | None = None) -> None:
        mostrar_mi_perfil(self, _evento)

    def mostrar_configuracion_inicial(self, error: str = "") -> None:
        mostrar_configuracion_inicial(self, error=error)

    def cerrar_sesion(self, _evento: ft.Event | None = None) -> None:
        self._heartbeat_activo = False
        self._heartbeat_iniciado = False
        if self.usuario_actual is not None:
            try:
                self.order_store.registrar_auditoria(
                    usuario=self.usuario_actual.username,
                    accion="LOGOUT",
                    detalle="Cierre de sesión manual",
                )
            except Exception:
                pass
            logger.info("Sesión cerrada manualmente por %s", self.usuario_actual.username)
        self.usuario_actual = None
        self._prefs_cargadas_usuario = False
        self.controles_tarea.clear()
        if hasattr(self, "botones_cierre_jornada") and self.botones_cierre_jornada is not None:
            self.botones_cierre_jornada.clear()
        self.btn_cierre_jornada = None
        self.conversacion.controls.clear()
        self.ventana_chat_flotante = None
        self._asegurar_file_picker(forzar_recrear=True)
        self.mostrar_inicio_sesion()

    def exigir_roles(self, *roles: UserRole) -> bool:
        """Verifica sesión activa, timeout por inactividad, vigencia de usuario y permisos de rol."""
        if self.usuario_actual is None:
            self.mostrar_inicio_sesion()
            return False
        ahora = datetime.now()
        inact_max = _obtener_inactividad_actual()
        if inact_max > 0 and (ahora - self.ultima_actividad).total_seconds() > inact_max * 60:
            nom_exp = self.usuario_actual.username
            self.usuario_actual = None
            tiempo_inactividad = (
                f"{inact_max // 60} h" if inact_max % 60 == 0 else f"{inact_max} min"
            )
            try:
                self.order_store.registrar_auditoria(
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
        self.ultima_actividad = ahora

        usuario = None
        if self.user_store:
            try:
                usuario_db = self.user_store.get_user(self.usuario_actual.id)
                if usuario_db and usuario_db.username.lower() == self.usuario_actual.username.lower():
                    usuario = usuario_db
            except Exception:
                pass
        if usuario is None:
            usuario = self.usuario_actual
        if usuario is None or not usuario.active:
            self.usuario_actual = None
            self.mostrar_inicio_sesion("La cuenta ya no está activa. Inicia sesión nuevamente.")
            return False
        self.usuario_actual = usuario
        if usuario.role not in roles:
            self.notificar("Tu rol no tiene permiso para realizar esta acción.")
            return False
        return True
