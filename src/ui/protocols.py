"""Contratos explícitos (Protocols) y contenedor de dependencias inyectables para la UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, runtime_checkable

import flet as ft


@dataclass
class AppDependencies:
    """Dependencias de dominio y almacenamiento inyectables en `InterfazFlet`."""

    user_store: Any
    order_store: Any
    product_store: Any
    menu: Any
    stock_manager_factory: Callable[..., Any] | None = None
    app_root_fn: Callable[[], Path] | None = None


@runtime_checkable
class ThemeHostProtocol(Protocol):
    """Contrato mínimo para el control de paleta y tema visual."""

    modo_oscuro: bool
    fondo: Any
    superficie: Any
    texto: Any
    secundario: Any
    borde: Any
    fondo_acento: Any


@runtime_checkable
class ResponsiveHostProtocol(Protocol):
    """Contrato mínimo para utilidades de layout responsivo y drawer móvil."""

    page: ft.Page
    usuario_actual: Any
    superficie: Any
    user_store: Any
    ventana_chat_flotante: ft.Container | None

    def _sidebar_controls(self) -> list[ft.Control]: ...
    def construir(self) -> None: ...
    def mostrar_configuracion_inicial(self, error: str = "") -> None: ...
    def mostrar_inicio_sesion(self, error: str = "") -> None: ...


@runtime_checkable
class FileTransferHostProtocol(Protocol):
    """Contrato mínimo para selección, carga y descarga de archivos en Flet."""

    page: ft.Page
    file_picker: ft.FilePicker

    def notificar(self, mensaje: str, color: Any | None = None) -> None: ...
    def actualizar_estado(self, _evento: ft.Event | None = None) -> None: ...
    def sincronizar_sesiones(
        self,
        notificar_chat: tuple[str, str, str] | None = None,
        aviso_colaborativo: str | None = None,
    ) -> None: ...


@runtime_checkable
class DocumentViewerHostProtocol(Protocol):
    """Contrato mínimo para apertura y compartición de documentos e informes."""

    page: ft.Page
    usuario_actual: Any
    menu: Any
    informes: list[Path]
    informe_seleccionado: Path | None

    def exigir_roles(self, *roles: Any) -> bool: ...
    def notificar(self, mensaje: str, color: Any | None = None) -> None: ...


@runtime_checkable
class AuthHostProtocol(Protocol):
    """Contrato mínimo para autenticación, roles y timeout de inactividad."""

    usuario_actual: Any
    user_store: Any
    order_store: Any
    ultima_actividad: Any
    controles_tarea: list[ft.Button]
    conversacion: ft.ListView
    ventana_chat_flotante: ft.Container | None
    btn_cierre_jornada: ft.Button | None

    def notificar(self, mensaje: str, color: Any | None = None) -> None: ...
    def _asegurar_file_picker(self, forzar_recrear: bool = False) -> None: ...


@runtime_checkable
class BatchHostProtocol(Protocol):
    """Contrato mínimo para ejecución de tareas por lotes y progreso."""

    page: ft.Page
    menu: Any
    order_store: Any
    usuario_actual: Any
    ocupado: bool
    modo_oscuro: bool
    texto: Any
    mayoristas: ft.Checkbox
    canjes: ft.Checkbox
    mercado_libre: ft.Checkbox
    progreso_barra: ft.ProgressBar
    estado_tarea: ft.Text
    actividad: ft.ListView
    controles_tarea: list[ft.Button]

    def exigir_roles(self, *roles: Any) -> bool: ...
    def notificar(self, mensaje: str, color: Any | None = None) -> None: ...
    def boton_dialogo(self, texto: str, accion: Callable[..., Any], variante: str = "auto") -> ft.Button: ...
    def actualizar_estado(self, _evento: ft.Event | None = None) -> None: ...
    def sincronizar_sesiones(
        self,
        notificar_chat: tuple[str, str, str] | None = None,
        aviso_colaborativo: str | None = None,
    ) -> None: ...


@runtime_checkable
class ChatHostProtocol(Protocol):
    """Contrato mínimo para el panel de chat asistente flotante."""

    page: ft.Page
    usuario_actual: Any
    order_store: Any
    modo_oscuro: bool
    texto: Any
    chat_visible: bool
    modo_chat_activo: str
    ventana_chat_flotante: ft.Container | None
    conversacion: ft.ListView
    entrada_chat: ft.TextField

    def exigir_roles(self, *roles: Any) -> bool: ...


@runtime_checkable
class SessionSyncHostProtocol(Protocol):
    """Contrato mínimo para sincronización en tiempo real entre sesiones y chat de equipo."""

    page: ft.Page
    usuario_actual: Any
    order_store: Any
    user_store: Any
    modo_oscuro: bool
    modo_chat_activo: str
    secundario: Any
    borde: Any
    texto: Any
    badge_chat_container: Any
    texto_badge_chat: Any
    texto_badge_tab: Any
    selector_destinatario_equipo: Any
    conversacion_equipo: Any
    entrada_chat_equipo: Any

    def exigir_roles(self, *roles: Any) -> bool: ...
    def actualizar_estado(self, _evento: ft.Event | None = None) -> None: ...
    def _enriquecer_mensaje_con_pedidos(self, texto: str) -> str: ...


@runtime_checkable
class DialogHostProtocol(Protocol):
    """Contrato mínimo para coordinación y despacho de diálogos modales."""

    order_store: Any
    menu: Any
    usuario_actual: Any

    def cerrar_drawer_si_movil(self) -> None: ...
    def _asegurar_file_picker(self, forzar_recrear: bool = False) -> None: ...
    def exigir_roles(self, *roles: Any) -> bool: ...
    def notificar(self, mensaje: str, color: Any | None = None) -> None: ...


SessionsProvider = Callable[[], Iterable[Any]]
