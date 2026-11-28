"""Controlador independiente para autenticación, perfil y seguridad de sesión."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable
from unittest.mock import NonCallableMock

import flet as ft

from ...auth import User, UserRole
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
    """Devuelve el límite de inactividad vigente configurado en el sistema."""
    return int(INACTIVIDAD_MAX_MINUTOS)


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

    def _limpiar_estado_sesion(self) -> None:
        """Limpia controles, preferencias y estado efímero de sesión (logout manual o expiración)."""
        from ..components.network_heartbeat import detener_heartbeat_red

        detener_heartbeat_red(self._host)
        self._host.usuario_actual = None
        self._host._prefs_cargadas_usuario = False
        self._host.sonido_chat_activo = True
        self._host._mensajes_bot_no_leidos = 0
        self._host._ultimo_no_leidos_chat = None
        self._host.informes = []
        self._host.informe_seleccionado = None
        page = getattr(self._host, "page", None)
        if page is not None:
            if isinstance(getattr(page, "title", None), str):
                page.title = "Control de Inventario Depósito Pasteur"
            if hasattr(page, "navigation_bar"):
                page.navigation_bar = None
        for lista_attr in ("controles_tarea", "botones_cierre_jornada"):
            coleccion = getattr(self._host, lista_attr, None)
            if coleccion is not None and hasattr(coleccion, "clear"):
                coleccion.clear()
        self._host.btn_cierre_jornada = None
        for vista_attr in (
            "conversacion",
            "conversacion_equipo",
            "actividad",
            "lista_pedidos_preparados",
            "lista_informes",
        ):
            vista = getattr(self._host, vista_attr, None)
            controles = getattr(vista, "controls", None)
            if controles is not None and hasattr(controles, "clear"):
                controles.clear()
        self._host.ventana_chat_flotante = None
        self._asegurar_picker(forzar_recrear=True)

    def cerrar_sesion(self, _evento: ft.Event | None = None) -> None:
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
        self._limpiar_estado_sesion()
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
            self._limpiar_estado_sesion()
            self.mostrar_inicio_sesion(
                f"Tu sesión se cerró por inactividad ({tiempo_inactividad}). Vuelve a ingresar."
            )
            return False

        self._host.ultima_actividad = ahora

        usuario = usuario_actual
        user_store = getattr(self._host, "user_store", None)
        if user_store is not None and not isinstance(usuario_actual, NonCallableMock):
            try:
                usuario_db = user_store.get_user(usuario_actual.id)
            except Exception as exc_db:
                logger.warning("Error al revalidar sesión contra UserStore (fail-closed): %s", exc_db)
                self._limpiar_estado_sesion()
                self.mostrar_inicio_sesion("No se pudo validar tu sesión. Inicia sesión nuevamente.")
                return False

            if usuario_db is None:
                self._limpiar_estado_sesion()
                self.mostrar_inicio_sesion("Tu cuenta ya no existe o fue revocada. Inicia sesión nuevamente.")
                return False

            if isinstance(usuario_db, User) or isinstance(getattr(usuario_db, "username", None), str):
                if usuario_db.username.lower() != usuario_actual.username.lower():
                    self._limpiar_estado_sesion()
                    self.mostrar_inicio_sesion("Sesión inconsistente. Inicia sesión nuevamente.")
                    return False
                usuario = usuario_db

        if usuario is None or not usuario.active:
            self._limpiar_estado_sesion()
            self.mostrar_inicio_sesion("La cuenta ya no está activa. Inicia sesión nuevamente.")
            return False
        self._host.usuario_actual = usuario
        if usuario.role not in roles:
            self._notificar("Tu rol no tiene permiso para realizar esta acción.")
            return False
        return True
