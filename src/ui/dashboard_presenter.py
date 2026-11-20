"""Presentador y despachador del estado y datos del Dashboard principal."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft

from ..auth import USER_ROLES
from ..inventory import StockManager
from .dashboard import (
    _obtener_resumen_fechas_operador,
    renderizar_auditoria_master,
    renderizar_informes_generados,
    renderizar_pedidos_armados_por_fecha,
    renderizar_pedidos_preparados_turno,
)

__all__ = [
    "actualizar_estado_dashboard",
    "renderizar_auditoria_master",
    "renderizar_informes_generados",
    "renderizar_pedidos_armados_por_fecha",
    "renderizar_pedidos_preparados_turno",
]


def actualizar_estado_dashboard(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Actualiza y sincroniza en tiempo real todos los indicadores y listas del Dashboard."""
    if not interfaz.exigir_roles(*USER_ROLES):
        return

    mayoristas, canjes, mercado_libre = interfaz.menu._obtener_pendientes()
    archivados = interfaz.menu._obtener_archivados()
    mtimes_informes: dict[Path, float] = {}

    def _clave_informe(ruta: Path) -> tuple[int, str]:
        try:
            st = ruta.stat()
            mtimes_informes[ruta] = st.st_mtime
            return (st.st_mtime_ns, ruta.name.casefold())
        except OSError:
            return (0, ruta.name.casefold())

    informes = sorted(
        interfaz.menu._obtener_generados(),
        key=_clave_informe,
        reverse=True,
    )
    interfaz.informes = informes

    conteo_jornada = {"pdf": 0, "excel": 0, "docx": 0, "total": 0}
    if hasattr(interfaz, "order_store") and interfaz.order_store:
        try:
            conteo_jornada = interfaz.order_store.contar_pedidos_pendientes_cierre_por_tipo()
        except Exception:
            pass

    if "pdf" in interfaz.contadores:
        interfaz.contadores["pdf"].value = str(conteo_jornada.get("pdf", 0))
    if "canjes" in interfaz.contadores:
        interfaz.contadores["canjes"].value = str(conteo_jornada.get("excel", 0))
    if "ml" in interfaz.contadores:
        interfaz.contadores["ml"].value = str(conteo_jornada.get("docx", 0))
    if "total" in interfaz.contadores:
        interfaz.contadores["total"].value = str(conteo_jornada.get("total", 0))
    if "informes" in interfaz.contadores:
        interfaz.contadores["informes"].value = str(len(informes))

    interfaz._actualizar_estado_boton_cierre(int(conteo_jornada.get("total", 0)))

    rol = interfaz.usuario_actual.role if interfaz.usuario_actual else "consulta"

    if rol == "administrador":
        try:
            sm = StockManager(interfaz.menu.ruta_excel_base)
            criticos = sm.obtener_analisis_reposicion(solo_criticos=True)
        except Exception:
            criticos = []
        if "quiebres" in interfaz.contadores:
            interfaz.contadores["quiebres"].value = str(len(criticos))
            interfaz.contadores["quiebres"].color = (
                ft.Colors.RED_400 if len(criticos) > 0 else interfaz.texto
            )
        interfaz.actualizar_alerta_quiebre(criticos)
        interfaz._actualizar_icono_notificaciones()
        from .components.admin_operations_bar import actualizar_seguimiento_operativo_admin
        actualizar_seguimiento_operativo_admin(interfaz)
    else:
        interfaz.banner_alerta_quiebre.visible = False

    if rol == "master":
        try:
            todos_usr = interfaz.user_store.list_users()
            activos_usr = sum(1 for u in todos_usr if u.active)
        except Exception:
            todos_usr = []
            activos_usr = 0

        if "usuarios_total" in interfaz.contadores:
            interfaz.contadores["usuarios_total"].value = str(len(todos_usr))
        if "usuarios_activos" in interfaz.contadores:
            interfaz.contadores["usuarios_activos"].value = str(activos_usr)

        eventos_auditoria = []
        if hasattr(interfaz, "order_store") and interfaz.order_store:
            try:
                eventos_auditoria = interfaz.order_store.listar_auditoria(limit=100)
            except Exception:
                pass
        if "auditoria_eventos" in interfaz.contadores:
            interfaz.contadores["auditoria_eventos"].value = str(len(eventos_auditoria))

        try:
            from ..backup_manager import listar_backups
            bks = listar_backups()
        except Exception:
            bks = []
        if "backups_total" in interfaz.contadores:
            interfaz.contadores["backups_total"].value = str(len(bks))
        if "servidor_seguro" in interfaz.contadores:
            interfaz.contadores["servidor_seguro"].value = "HTTPS" if getattr(interfaz, "https", True) else "HTTP"

        try:
            from ..system_telemetry import obtener_telemetria_sistema
            telem = obtener_telemetria_sistema()
        except Exception:
            telem = None

        if telem:
            if "telemetria_disco" in interfaz.contadores:
                interfaz.contadores["telemetria_disco"].value = f"{telem.disco_libre_gb} GB"
                interfaz.contadores["telemetria_disco"].color = (
                    ft.Colors.RED_400 if telem.disco_alerta else interfaz.texto
                )
            if "telemetria_salud" in interfaz.contadores:
                interfaz.contadores["telemetria_salud"].value = telem.estado_salud
                if telem.estado_salud == "Óptimo":
                    interfaz.contadores["telemetria_salud"].color = ft.Colors.GREEN_400
                elif telem.estado_salud == "Atención":
                    interfaz.contadores["telemetria_salud"].color = ft.Colors.AMBER_400
                else:
                    interfaz.contadores["telemetria_salud"].color = ft.Colors.RED_400

        interfaz.banner_alerta_quiebre.visible = False
        interfaz.pendientes_texto.value = (
            f"Consola de Auditoría y Control de Accesos · Usuarios: {len(todos_usr)} · Cuentas activas: {activos_usr} · Backups: {len(bks)}"
        )
        renderizar_auditoria_master(interfaz, eventos_auditoria)
    elif rol == "despachador":
        interfaz.banner_alerta_quiebre.visible = False
        pend_armados = 0
        despachados_cnt = 0
        if hasattr(interfaz, "order_store") and interfaz.order_store:
            try:
                pend_armados = len(
                    interfaz.order_store.listar_pedidos_por_estado_despacho(estados=("armado",), limit=300)
                )
                despachados_cnt = len(
                    interfaz.order_store.listar_pedidos_por_estado_despacho(estados=("despachado", "entregado"), limit=300)
                )
            except Exception:
                pass
        interfaz.pendientes_texto.value = (
            f"Módulo Despacho · Pendientes (armados): {pend_armados} · Despachados: {despachados_cnt}"
        )
        refrescar_fn = getattr(interfaz, "_refrescar_modulo_despacho", None)
        if callable(refrescar_fn):
            try:
                refrescar_fn()
            except Exception:
                pass
    elif rol == "picker":
        interfaz.banner_alerta_quiebre.visible = False
        interfaz.pendientes_texto.value = (
            f"Módulo de Picking y Despacho · Informes: {len(informes)}"
        )
        renderizar_informes_generados(interfaz, informes, mtimes_informes)
    elif rol == "administrador":
        total_descontados = conteo_jornada.get("total", 0)
        total_archivados = sum(map(len, archivados))
        interfaz.pendientes_texto.value = (
            f"Panel de Control y Analítica · Pedidos descontados: {total_descontados} · Informes: {len(informes)}"
        )
        from .components.admin_flow_analytics import actualizar_panel_analitica_flujo_admin
        actualizar_panel_analitica_flujo_admin(interfaz)
    elif rol == "operador":
        total_descontados = conteo_jornada.get("total", 0)
        total_archivados = sum(map(len, archivados))
        interfaz.pendientes_texto.value = (
            f"Jornada en curso: {total_descontados} pedido(s) descontado(s) · Archivados: {total_archivados} · Informes: {len(informes)}"
        )

        pedidos_pendientes_turno = interfaz.order_store.listar_pedidos_pendientes_cierre()
        pedidos_pendientes_turno.sort(key=lambda p: p.id, reverse=True)
        renderizar_pedidos_preparados_turno(interfaz, pedidos_pendientes_turno)
        resumen_fechas = _obtener_resumen_fechas_operador(interfaz)
        renderizar_pedidos_armados_por_fecha(interfaz, resumen_fechas)
    else:
        total_descontados = conteo_jornada.get("total", 0)
        total_archivados = sum(map(len, archivados))
        interfaz.pendientes_texto.value = (
            f"Jornada en curso: {total_descontados} pedido(s) descontado(s) · Archivados: {total_archivados} · Informes: {len(informes)}"
        )

        pedidos_pendientes_turno = interfaz.order_store.listar_pedidos_pendientes_cierre()
        pedidos_pendientes_turno.sort(key=lambda p: p.id, reverse=True)
        renderizar_pedidos_preparados_turno(interfaz, pedidos_pendientes_turno)
        renderizar_informes_generados(interfaz, informes, mtimes_informes)

    if hasattr(interfaz, "actualizar_badge_chat"):
        try:
            interfaz.actualizar_badge_chat()
        except Exception:
            pass

    if interfaz.page and getattr(interfaz.page, "controls", None):
        try:
            interfaz.page.update()
        except Exception:
            pass
