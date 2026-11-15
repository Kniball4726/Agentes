"""Controlador independiente para ejecución de tareas por lotes y progreso."""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import sys
import traceback
from typing import Any, Callable

import flet as ft

logger = logging.getLogger(__name__)
_PROCESAMIENTO_LOCAL_ACTIVO: bool = False


def es_procesamiento_global_activo() -> bool:
    mod = sys.modules.get("src.flet_gui")
    if mod is not None and hasattr(mod, "PROCESAMIENTO_GLOBAL_ACTIVO"):
        return bool(mod.PROCESAMIENTO_GLOBAL_ACTIVO)
    return _PROCESAMIENTO_LOCAL_ACTIVO


def set_procesamiento_global_activo(valor: bool) -> None:
    global _PROCESAMIENTO_LOCAL_ACTIVO
    _PROCESAMIENTO_LOCAL_ACTIVO = bool(valor)
    mod = sys.modules.get("src.flet_gui")
    if mod is not None:
        mod.PROCESAMIENTO_GLOBAL_ACTIVO = bool(valor)


class BatchTaskController:
    """Orquesta simulación, procesamiento real en segundo plano y badges de cierre."""

    def __init__(
        self,
        host: Any,
        get_global_lock_fn: Callable[[], bool] | None = None,
        set_global_lock_fn: Callable[[bool], None] | None = None,
        check_roles_fn: Callable[..., bool] | None = None,
        notify_fn: Callable[[str], None] | None = None,
        refresh_dashboard_fn: Callable[[], None] | None = None,
        sync_sessions_fn: Callable[[], None] | None = None,
    ) -> None:
        self._host = host
        self._get_lock_fn = get_global_lock_fn or es_procesamiento_global_activo
        self._set_lock_fn = set_global_lock_fn or set_procesamiento_global_activo
        self._check_roles_fn = check_roles_fn
        self._notify_fn = notify_fn
        self._refresh_dashboard_fn = refresh_dashboard_fn
        self._sync_sessions_fn = sync_sessions_fn

    def _exigir_roles(self, *roles: Any) -> bool:
        fn = self._check_roles_fn or getattr(self._host, "exigir_roles", None)
        return bool(fn(*roles)) if callable(fn) else True

    def _notificar(self, mensaje: str) -> None:
        fn = self._notify_fn or getattr(self._host, "notificar", None)
        if callable(fn):
            fn(mensaje)

    def _actualizar_estado(self) -> None:
        fn = self._refresh_dashboard_fn or getattr(self._host, "actualizar_estado", None)
        if callable(fn):
            fn()

    def _sincronizar_sesiones(self) -> None:
        fn = self._sync_sessions_fn or getattr(self._host, "sincronizar_sesiones", None)
        if callable(fn):
            fn()

    def _set_status_text(self, texto: str, estado: str = "en_curso") -> None:
        setter = getattr(self._host, "fijar_estado_tarea", None)
        if callable(setter):
            setter(texto, estado=estado)
        else:
            self._host.estado_tarea.value = texto

    def resumen_estado(self) -> str:
        menu = self._host.menu
        mayoristas, canjes, mercado_libre = menu._obtener_pendientes()
        fab = menu._obtener_pendientes_fabrica()
        full = getattr(menu, "_obtener_pendientes_mercado_full", lambda: [])()
        archivados = menu._obtener_archivados()
        return (
            f"Pendientes: {len(mayoristas)} PDF mayoristas, {len(canjes)} Excel "
            f"de canjes, {len(mercado_libre)} DOCX de Mercado Libre, {len(fab)} fábrica "
            f"y {len(full)} Mercado Full. "
            f"Archivados: {sum(map(len, archivados))}. "
            f"Informes disponibles: {len(menu._obtener_generados())}."
        )

    def resumen_informes(self) -> str:
        informes = self._host.menu._obtener_generados()
        if not informes:
            return "Todavía no hay informes generados."
        nombres = [ruta.name for ruta in informes[-10:]]
        return "Informes recientes:\n" + "\n".join(nombres)

    def fuentes_seleccionadas(self) -> tuple[bool, bool, bool]:
        return (
            bool(self._host.mayoristas.value),
            bool(self._host.canjes.value),
            bool(self._host.mercado_libre.value),
        )

    async def simular(self, _evento: ft.Event | None) -> None:
        if not self._exigir_roles("operador"):
            return
        await self.procesar(simulacion=True)

    def procesar_real(self, _evento: ft.Event) -> None:
        if not self._exigir_roles("operador"):
            return
        confirm_btn_factory = getattr(self._host, "boton_dialogo", None)
        if callable(confirm_btn_factory):
            btn_cancel = confirm_btn_factory("Cancelar", lambda _e: self._host.page.pop_dialog())
            btn_confirm = confirm_btn_factory("Confirmar", self.confirmar_procesar_real)
        else:
            btn_cancel = ft.TextButton("Cancelar", on_click=lambda _e: self._host.page.pop_dialog())
            btn_confirm = ft.TextButton("Confirmar", on_click=self.confirmar_procesar_real)

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar procesamiento real"),
            content=ft.Text(
                "Esta operación generará el informe y moverá los documentos "
                "procesados a 'descontados'. No modificará Productos.xlsx. ¿Quieres continuar?"
            ),
            actions=[btn_cancel, btn_confirm],
        )
        self._host.page.show_dialog(dialogo)

    async def confirmar_procesar_real(self, _evento: ft.Event) -> None:
        if not self._exigir_roles("operador"):
            return
        self._host.page.pop_dialog()
        await self.procesar(simulacion=False)

    async def procesar(self, simulacion: bool) -> None:
        if not self._exigir_roles("operador"):
            return
        if self._get_lock_fn() or self._host.ocupado:
            self._notificar(
                "Hay una operación de procesamiento de stock en curso desde otra sesión o pestaña. "
                "Por seguridad en los archivos, espera a que finalice."
            )
            return
        fuentes = self.fuentes_seleccionadas()
        if not any(fuentes):
            self._notificar("Selecciona al menos una fuente.")
            return

        usuario_actual = getattr(self._host, "usuario_actual", None)
        usuario_actual_nom = usuario_actual.username if usuario_actual else "operador"
        await self.ejecutar_tarea(
            "Simulación" if simulacion else "Procesamiento real",
            lambda: self._host.menu.procesar(
                incluir_mayoristas=fuentes[0],
                incluir_canjes=fuentes[1],
                incluir_mercado_libre=fuentes[2],
                simulacion=simulacion,
                usuario=usuario_actual_nom,
            ),
        )

    async def ejecutar_tarea(self, nombre: str, accion: Callable[[], object]) -> bool:
        if self._get_lock_fn() or self._host.ocupado:
            self._notificar(
                "Hay una operación de procesamiento de stock en curso desde otra sesión o pestaña. "
                "Por seguridad en los archivos, espera a que finalice."
            )
            return False

        self._host.ocupado = True
        self._set_lock_fn(True)
        self._host.progreso_barra.visible = True
        self._host.progreso_barra.value = None
        self._set_status_text(f"En curso: {nombre}", estado="en_curso")
        self.actualizar_estado_botones()
        self._sincronizar_sesiones()
        self._host.page.update()

        salida = io.StringIO()
        exito = False

        def ejecutar() -> None:
            with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
                accion()

        try:
            await asyncio.to_thread(ejecutar)
        except Exception as exc:
            detalle = traceback.format_exc()
            logger.error("Error ejecutando tarea '%s': %s\n%s", nombre, exc, detalle)
            self._host.actividad.controls.append(
                ft.Text(
                    f"[ERROR]\n{detalle}",
                    color=ft.Colors.RED_400 if self._host.modo_oscuro else ft.Colors.RED_700,
                    size=14,
                )
            )
            self._set_status_text(f"{nombre} terminó con un error.", estado="error")
            self._notificar("La operación falló. Revisa el panel Actividad.")
        else:
            texto = salida.getvalue().strip()
            if texto:
                self._host.actividad.controls.append(
                    ft.Text(texto, color=self._host.texto, size=14)
                )
            self._set_status_text(f"{nombre} finalizada.", estado="listo")
            exito = True
        finally:
            self._host.ocupado = False
            self._set_lock_fn(False)
            self._host.progreso_barra.visible = False
            self._host.progreso_barra.value = None
            self.actualizar_estado_botones()
            self._actualizar_estado()
            self._sincronizar_sesiones()
        return exito

    def actualizar_progreso(self, actual: int, total: int, mensaje: str = "") -> None:
        """Actualiza el porcentaje y etiqueta de la barra de progreso de operaciones masivas."""
        if total > 0:
            val = min(1.0, max(0.0, float(actual) / float(total)))
            self._host.progreso_barra.value = val
            pct = int(val * 100)
            msg = f"{mensaje} ({pct}%)" if mensaje else f"Progreso: {pct}%"
            self._set_status_text(msg, estado="en_curso")
        else:
            self._host.progreso_barra.value = None
            if mensaje:
                self._set_status_text(mensaje, estado="en_curso")
        self._host.progreso_barra.visible = True
        page = getattr(self._host, "page", None)
        if page and hasattr(page, "update"):
            try:
                page.update()
            except Exception:
                pass

    def actualizar_estado_boton_cierre(self, conteo_total: int | None = None) -> None:
        """Habilita o deshabilita dinámicamente el botón de Cierre de Jornada según pendientes."""
        if conteo_total is None:
            conteo_total = 0
            order_store = getattr(self._host, "order_store", None)
            if order_store:
                try:
                    conteo = order_store.contar_pedidos_pendientes_cierre_por_tipo()
                    conteo_total = int(conteo.get("total", 0))
                except Exception:
                    conteo_total = 0

        esta_deshabilitado = bool(self._host.ocupado or self._get_lock_fn() or conteo_total == 0)
        tooltip_txt = (
            "No hay pedidos pendientes de cierre"
            if conteo_total == 0
            else f"{conteo_total} pedido(s) pendiente(s) de cierre"
        )

        botones = getattr(self._host, "botones_cierre_jornada", []) or []
        btn_single = getattr(self._host, "btn_cierre_jornada", None)
        todos_botones = list(botones)
        if btn_single and btn_single not in todos_botones:
            todos_botones.append(btn_single)

        for btn in todos_botones:
            btn.disabled = esta_deshabilitado
            btn.tooltip = tooltip_txt
            btn.content = f"Cierre de Jornada ({conteo_total})" if conteo_total > 0 else "Cierre de Jornada"

        try:
            from ..components.sidebar import actualizar_puntos_pendientes_sidebar
            actualizar_puntos_pendientes_sidebar(self._host)
        except Exception:
            pass

        for sec_attr, txt_attr in (
            ("badge_seccion_cierre", "badge_texto_cierre"),
            ("badge_h_seccion_cierre", "badge_h_texto_cierre"),
        ):
            badge_sec = getattr(self._host, sec_attr, None)
            badge_txt = getattr(self._host, txt_attr, None)
            if badge_sec is not None:
                badge_sec.visible = conteo_total > 0
            if badge_txt is not None:
                badge_txt.value = str(conteo_total)

    def actualizar_estado_botones(self) -> None:
        deshabilitado = self._host.ocupado or self._get_lock_fn()
        for control in self._host.controles_tarea:
            control.disabled = deshabilitado
        if not deshabilitado:
            self.actualizar_estado_boton_cierre()
        self._host.page.update()
