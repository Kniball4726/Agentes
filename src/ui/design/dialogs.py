"""Diálogos estándar y confirmación uniforme de acciones destructivas."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Iterable, Sequence

import flet as ft

from .buttons import boton_cancelar, boton_peligro, boton_primario, fijar_ocupado
from .tokens import colores_de

logger = logging.getLogger(__name__)

MENSAJE_SIN_PERMISO = "Tu rol no tiene permiso para realizar esta acción."


def _ancho(interfaz: Any, deseado: int) -> int:
    fn = getattr(interfaz, "ancho_adaptable", None)
    if callable(fn):
        try:
            valor = fn(deseado)
            if isinstance(valor, (int, float)):
                return int(valor)
        except Exception:
            pass
    return deseado


def encabezado_dialogo(
    interfaz: Any,
    titulo: str,
    icono: ft.IconData | None = None,
    color_icono: Any | None = None,
) -> ft.Control:
    """Encabezado consistente: ícono en círculo tenue + título en negrita."""
    pal = colores_de(interfaz)
    texto = ft.Text(titulo, size=17, weight=ft.FontWeight.BOLD, color=pal.texto)
    if icono is None:
        return texto
    color = color_icono or pal.marca
    return ft.Row(
        [
            ft.Container(
                content=ft.Icon(icono, color=color, size=20),
                bgcolor=ft.Colors.with_opacity(0.14, color),
                border_radius=18,
                width=36,
                height=36,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Container(content=texto, expand=True),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def crear_dialogo_estandar(
    interfaz: Any,
    titulo: str,
    contenido: ft.Control,
    acciones: Sequence[ft.Control] | None = None,
    *,
    icono: ft.IconData | None = None,
    ancho: int = 560,
    modal: bool = True,
    texto_cerrar: str | None = "Cerrar",
) -> ft.AlertDialog:
    """AlertDialog con ``modal=True``, ancho adaptable, encabezado y acciones alineadas a la derecha.

    Si no se pasan acciones, agrega un botón neutro de cierre.
    """
    page = getattr(interfaz, "page", None)
    lista_acciones: list[ft.Control] = list(acciones or [])
    if not lista_acciones and texto_cerrar:
        lista_acciones = [boton_cancelar(texto_cerrar, lambda _e: page.pop_dialog() if page else None)]
    return ft.AlertDialog(
        modal=modal,
        title=encabezado_dialogo(interfaz, titulo, icono),
        content=ft.Container(content=contenido, width=_ancho(interfaz, ancho)),
        actions=lista_acciones,
        actions_alignment=ft.MainAxisAlignment.END,
        bgcolor=getattr(interfaz, "superficie", None),
    )


def _rol_actual(interfaz: Any) -> str:
    usuario = getattr(interfaz, "usuario_actual", None)
    return str(getattr(usuario, "role", "") or "").strip().lower()


def _notificar(interfaz: Any, mensaje: str, color: Any | None = None) -> None:
    fn = getattr(interfaz, "notificar", None)
    if callable(fn):
        try:
            if color is None:
                fn(mensaje)
            else:
                fn(mensaje, color)
        except Exception:
            pass


def _registrar_auditoria(interfaz: Any, auditoria: tuple[str, str] | None) -> None:
    if not auditoria:
        return
    store = getattr(interfaz, "order_store", None)
    fn = getattr(store, "registrar_auditoria", None)
    if not callable(fn):
        return
    usuario = getattr(getattr(interfaz, "usuario_actual", None), "username", None) or "desconocido"
    accion, detalle = auditoria
    try:
        fn(str(usuario), str(accion), str(detalle))
    except Exception:
        logger.debug("No se pudo registrar auditoría de acción destructiva", exc_info=True)


def confirmar_accion_destructiva(
    interfaz: Any,
    titulo: str,
    mensaje: str,
    on_confirmar: Callable[[], Any],
    *,
    texto_confirmar: str = "Eliminar",
    roles_permitidos: Iterable[str] | None = None,
    auditoria: tuple[str, str] | None = None,
    mensaje_exito: str | None = None,
    en_segundo_plano: bool = False,
) -> ft.AlertDialog | None:
    """Muestra un modal uniforme antes de ejecutar una acción irreversible.

    - Verifica el rol (``roles_permitidos``) antes de abrir el modal (fail-closed).
    - Bloquea los botones mientras se ejecuta (evita doble clic / doble envío).
    - Registra la acción en ``logs_auditoria`` si se indica ``auditoria=(accion, detalle)``.
    - ``on_confirmar`` puede devolver ``False`` o un ``str`` para informar un error.
    """
    if roles_permitidos is not None:
        permitidos = {str(r).strip().lower() for r in roles_permitidos}
        if _rol_actual(interfaz) not in permitidos:
            _notificar(interfaz, MENSAJE_SIN_PERMISO)
            return None

    page = getattr(interfaz, "page", None)
    pal = colores_de(interfaz)
    estado = {"ejecutando": False}
    indicador = ft.ProgressRing(width=18, height=18, stroke_width=2, visible=False)

    def _cerrar(_e: Any = None) -> None:
        if estado["ejecutando"]:
            return
        try:
            page.pop_dialog()
        except Exception:
            pass

    btn_cancelar = boton_cancelar("Cancelar", _cerrar)

    def _finalizar(resultado: Any) -> None:
        estado["ejecutando"] = False
        indicador.visible = False
        fijar_ocupado(btn_confirmar, False)
        btn_cancelar.disabled = False
        try:
            page.pop_dialog()
        except Exception:
            pass
        if resultado is False or isinstance(resultado, str):
            detalle = resultado if isinstance(resultado, str) and resultado else "No se pudo completar la acción."
            _notificar(interfaz, detalle, pal.error)
            return
        _registrar_auditoria(interfaz, auditoria)
        if mensaje_exito:
            _notificar(interfaz, mensaje_exito, ft.Colors.GREEN_700)

    def _ejecutar() -> None:
        try:
            resultado = on_confirmar()
        except Exception as exc:  # noqa: BLE001 - se informa sin exponer trazas
            logger.warning("Acción destructiva falló: %s", exc)
            resultado = "Ocurrió un error al ejecutar la acción."
        _finalizar(resultado)

    def _confirmar(_e: Any = None) -> None:
        if estado["ejecutando"]:
            return
        estado["ejecutando"] = True
        indicador.visible = True
        fijar_ocupado(btn_confirmar, True, "Procesando…")
        btn_cancelar.disabled = True
        try:
            page.update()
        except Exception:
            pass
        if en_segundo_plano:
            threading.Thread(target=_ejecutar, daemon=True).start()
        else:
            _ejecutar()

    btn_confirmar = boton_peligro(texto_confirmar, _confirmar)
    dialogo = ft.AlertDialog(
        modal=True,
        title=encabezado_dialogo(interfaz, titulo, ft.Icons.WARNING_AMBER_ROUNDED, pal.error),
        content=ft.Container(
            width=_ancho(interfaz, 440),
            content=ft.Column(
                [
                    ft.Text(mensaje, color=pal.texto, size=14),
                    ft.Text(
                        "Esta acción no se puede deshacer.",
                        color=pal.secundario,
                        size=12,
                        italic=True,
                    ),
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[btn_cancelar, ft.Row([indicador, btn_confirmar], tight=True, spacing=8)],
        actions_alignment=ft.MainAxisAlignment.END,
        bgcolor=getattr(interfaz, "superficie", None),
    )
    try:
        page.show_dialog(dialogo)
    except Exception:
        pass
    return dialogo


def boton_confirmacion(texto: str, accion: Callable[..., Any] | None) -> ft.Button:
    """Alias semántico del botón primario para formularios de confirmación."""
    return boton_primario(texto, accion)
