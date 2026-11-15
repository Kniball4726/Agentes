"""Mixin para ejecución de tareas por lotes, progreso y controles de procesamiento."""

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


def _es_procesamiento_global_activo() -> bool:
    mod = sys.modules.get("src.flet_gui")
    if mod is not None and hasattr(mod, "PROCESAMIENTO_GLOBAL_ACTIVO"):
        return bool(mod.PROCESAMIENTO_GLOBAL_ACTIVO)
    return _PROCESAMIENTO_LOCAL_ACTIVO


def _set_procesamiento_global_activo(valor: bool) -> None:
    global _PROCESAMIENTO_LOCAL_ACTIVO
    _PROCESAMIENTO_LOCAL_ACTIVO = bool(valor)
    mod = sys.modules.get("src.flet_gui")
    if mod is not None:
        mod.PROCESAMIENTO_GLOBAL_ACTIVO = bool(valor)


class BatchProcessingMixin:
    """Orquesta simulación, procesamiento real de documentos y actualización de progreso."""

    page: ft.Page
    menu: Any
    order_store: Any
    usuario_actual: Any
    ocupado: bool
    modo_oscuro: bool
    texto: str
    mayoristas: ft.Checkbox
    canjes: ft.Checkbox
    mercado_libre: ft.Checkbox
    progreso_barra: ft.ProgressBar
    estado_tarea: ft.Text
    actividad: ft.ListView
    controles_tarea: list[ft.Button]

    def resumen_estado(self) -> str:
        mayoristas, canjes, mercado_libre = self.menu._obtener_pendientes()
        fab = self.menu._obtener_pendientes_fabrica()
        full = getattr(self.menu, "_obtener_pendientes_mercado_full", lambda: [])()
        archivados = self.menu._obtener_archivados()
        return (
            f"Pendientes: {len(mayoristas)} PDF mayoristas, {len(canjes)} Excel "
            f"de canjes, {len(mercado_libre)} DOCX de Mercado Libre, {len(fab)} fábrica "
            f"y {len(full)} Mercado Full. "
            f"Archivados: {sum(map(len, archivados))}. "
            f"Informes disponibles: {len(self.menu._obtener_generados())}."
        )

    def resumen_informes(self) -> str:
        informes = self.menu._obtener_generados()
        if not informes:
            return "Todavía no hay informes generados."
        nombres = [ruta.name for ruta in informes[-10:]]
        return "Informes recientes:\n" + "\n".join(nombres)

    def fuentes_seleccionadas(self) -> tuple[bool, bool, bool]:
        return (
            bool(self.mayoristas.value),
            bool(self.canjes.value),
            bool(self.mercado_libre.value),
        )

    async def simular(self, _evento: ft.Event | None) -> None:
        if not self.exigir_roles("operador"):
            return
        await self.procesar(simulacion=True)

    def procesar_real(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("operador"):
            return
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar procesamiento real"),
            content=ft.Text(
                "Esta operación generará el informe y moverá los documentos "
                "procesados a 'descontados'. No modificará Productos.xlsx. ¿Quieres continuar?"
            ),
            actions=[
                self.boton_dialogo("Cancelar", lambda _e: self.page.pop_dialog()),
                self.boton_dialogo("Confirmar", self.confirmar_procesar_real),
            ],
        )
        self.page.show_dialog(dialogo)

    async def confirmar_procesar_real(self, _evento: ft.Event) -> None:
        if not self.exigir_roles("operador"):
            return
        self.page.pop_dialog()
        await self.procesar(simulacion=False)

    async def procesar(self, simulacion: bool) -> None:
        if not self.exigir_roles("operador"):
            return
        if _es_procesamiento_global_activo() or self.ocupado:
            self.notificar(
                "Hay una operación de procesamiento de stock en curso desde otra sesión o pestaña. "
                "Por seguridad en los archivos, espera a que finalice."
            )
            return
        fuentes = self.fuentes_seleccionadas()
        if not any(fuentes):
            self.notificar("Selecciona al menos una fuente.")
            return

        usuario_actual_nom = self.usuario_actual.username if self.usuario_actual else "operador"
        await self.ejecutar_tarea(
            "Simulación" if simulacion else "Procesamiento real",
            lambda: self.menu.procesar(
                incluir_mayoristas=fuentes[0],
                incluir_canjes=fuentes[1],
                incluir_mercado_libre=fuentes[2],
                simulacion=simulacion,
                usuario=usuario_actual_nom,
            ),
        )

    async def ejecutar_tarea(
        self, nombre: str, accion: Callable[[], object]
    ) -> bool:
        if _es_procesamiento_global_activo() or self.ocupado:
            self.notificar(
                "Hay una operación de procesamiento de stock en curso desde otra sesión o pestaña. "
                "Por seguridad en los archivos, espera a que finalice."
            )
            return False

        self.ocupado = True
        _set_procesamiento_global_activo(True)
        self.progreso_barra.visible = True
        self.progreso_barra.value = None
        if hasattr(self, "fijar_estado_tarea"):
            self.fijar_estado_tarea(f"En curso: {nombre}", estado="en_curso")
        else:
            self.estado_tarea.value = f"En curso: {nombre}"
        self.actualizar_estado_botones()
        self.sincronizar_sesiones()
        self.page.update()

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
            self.actividad.controls.append(
                ft.Text(
                    f"[ERROR]\n{detalle}",
                    color=ft.Colors.RED_400 if self.modo_oscuro else ft.Colors.RED_700,
                    size=14,
                )
            )
            if hasattr(self, "fijar_estado_tarea"):
                self.fijar_estado_tarea(f"{nombre} terminó con un error.", estado="error")
            else:
                self.estado_tarea.value = f"{nombre} terminó con un error."
            self.notificar("La operación falló. Revisa el panel Actividad.")
        else:
            texto = salida.getvalue().strip()
            if texto:
                self.actividad.controls.append(
                    ft.Text(texto, color=self.texto, size=14)
                )
            if hasattr(self, "fijar_estado_tarea"):
                self.fijar_estado_tarea(f"{nombre} finalizada.", estado="listo")
            else:
                self.estado_tarea.value = f"{nombre} finalizada."
            exito = True
        finally:
            self.ocupado = False
            _set_procesamiento_global_activo(False)
            self.progreso_barra.visible = False
            self.progreso_barra.value = None
            self.actualizar_estado_botones()
            self.actualizar_estado()
            self.sincronizar_sesiones()
        return exito

    def actualizar_progreso(self, actual: int, total: int, mensaje: str = "") -> None:
        """Actualiza el porcentaje y etiqueta de la barra de progreso de operaciones masivas."""
        if total > 0:
            val = min(1.0, max(0.0, float(actual) / float(total)))
            self.progreso_barra.value = val
            pct = int(val * 100)
            msg = f"{mensaje} ({pct}%)" if mensaje else f"Progreso: {pct}%"
            if hasattr(self, "fijar_estado_tarea"):
                self.fijar_estado_tarea(msg, estado="en_curso")
            else:
                self.estado_tarea.value = msg
        else:
            self.progreso_barra.value = None
            if mensaje:
                if hasattr(self, "fijar_estado_tarea"):
                    self.fijar_estado_tarea(mensaje, estado="en_curso")
                else:
                    self.estado_tarea.value = mensaje
        self.progreso_barra.visible = True
        if hasattr(self.page, "update"):
            try:
                self.page.update()
            except Exception:
                pass

    def _actualizar_estado_boton_cierre(self, conteo_total: int | None = None) -> None:
        """Habilita o deshabilita dinámicamente el botón de Cierre de Jornada según pedidos pendientes."""
        if conteo_total is None:
            conteo_total = 0
            if hasattr(self, "order_store") and self.order_store:
                try:
                    conteo = self.order_store.contar_pedidos_pendientes_cierre_por_tipo()
                    conteo_total = int(conteo.get("total", 0))
                except Exception:
                    conteo_total = 0

        esta_deshabilitado = bool(self.ocupado or _es_procesamiento_global_activo() or conteo_total == 0)

        if conteo_total == 0:
            tooltip_txt = "No hay pedidos pendientes de cierre"
        else:
            tooltip_txt = f"{conteo_total} pedido(s) pendiente(s) de cierre"

        botones = getattr(self, "botones_cierre_jornada", []) or []
        btn_single = getattr(self, "btn_cierre_jornada", None)
        todos_botones = list(botones)
        if btn_single and btn_single not in todos_botones:
            todos_botones.append(btn_single)

        for btn in todos_botones:
            btn.disabled = esta_deshabilitado
            btn.tooltip = tooltip_txt
            btn.content = f"Cierre de Jornada ({conteo_total})" if conteo_total > 0 else "Cierre de Jornada"

        try:
            from ..components.sidebar import actualizar_puntos_pendientes_sidebar
            actualizar_puntos_pendientes_sidebar(self)
        except Exception:
            pass
        badge_sec = getattr(self, "badge_seccion_cierre", None)
        badge_txt = getattr(self, "badge_texto_cierre", None)
        if badge_sec is not None:
            badge_sec.visible = conteo_total > 0
        if badge_txt is not None:
            badge_txt.value = str(conteo_total)

        badge_h_sec = getattr(self, "badge_h_seccion_cierre", None)
        badge_h_txt = getattr(self, "badge_h_texto_cierre", None)
        if badge_h_sec is not None:
            badge_h_sec.visible = conteo_total > 0
        if badge_h_txt is not None:
            badge_h_txt.value = str(conteo_total)

    def actualizar_estado_botones(self) -> None:
        deshabilitado = self.ocupado or _es_procesamiento_global_activo()
        for control in self.controles_tarea:
            control.disabled = deshabilitado
        if not deshabilitado:
            self._actualizar_estado_boton_cierre()
        self.page.update()
