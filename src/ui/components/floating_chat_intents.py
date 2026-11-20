"""Manejadores de intención y control de permisos por rol para el chat flotante."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any

from ...chat import (
    detectar_intencion,
    extraer_termino_busqueda,
    formatear_diagnostico_archivos,
    formatear_respuesta_criticos,
    formatear_respuesta_stock,
    formatear_ultimo_informe,
    obtener_comandos_ayuda,
    obtener_mensaje_bienvenida,
    obtener_pie_ayuda,
)
from ...inventory import StockManager as _DefaultStockManager
from ...paths import application_root as _default_app_root

_INTENCIONES_BLOQUEADAS_MASTER = frozenset({
    "simular",
    "reposicion",
    "diagnostico",
    "buscar_stock",
    "criticos",
    "pedidos",
    "cierre",
    "mercadolibre",
    "ultimo_informe",
    "informes",
    "metricas",
})
_INTENCIONES_BLOQUEADAS_OPERADOR = frozenset({"simular", "reposicion", "diagnostico"})
_INTENCIONES_BLOQUEADAS_CONSULTA = frozenset({"simular", "cierre", "mercadolibre", "pedidos"})
_INTENCIONES_BLOQUEADAS_PICKER = frozenset({
    "simular",
    "reposicion",
    "diagnostico",
    "cierre",
    "auditoria",
    "informes",
    "ultimo_informe",
    "backup",
    "metricas",
})
_INTENCIONES_BLOQUEADAS_DESPACHADOR = frozenset({
    "simular",
    "reposicion",
    "diagnostico",
    "buscar_stock",
    "criticos",
    "cierre",
    "mercadolibre",
    "auditoria",
    "informes",
    "ultimo_informe",
    "backup",
    "metricas",
})


def _resolver_stock_manager():
    """Resuelve StockManager respetando patches sobre src.flet_gui o floating_chat."""
    mod_fc = sys.modules.get("src.ui.components.floating_chat")
    if mod_fc is not None:
        fc_sm = getattr(mod_fc, "StockManager", _DefaultStockManager)
        if fc_sm is not _DefaultStockManager:
            return fc_sm
    mod_gui = sys.modules.get("src.flet_gui")
    if mod_gui is not None and hasattr(mod_gui, "StockManager"):
        return getattr(mod_gui, "StockManager")
    return _DefaultStockManager


def _resolver_app_root():
    mod_fc = sys.modules.get("src.ui.components.floating_chat")
    if mod_fc is not None:
        fc_root = getattr(mod_fc, "application_root", _default_app_root)
        if fc_root is not _default_app_root:
            return fc_root
    return _default_app_root


def _validar_permiso_intencion(rol: str, intencion: str) -> str | None:
    """Devuelve mensaje de restricción si el rol no tiene permiso para la intención."""
    if rol != "master" and intencion == "auditoria":
        return "⚠️ El registro de auditoría forense y eventos de seguridad está reservado exclusivamente para el rol Master (Seguridad & IAM)."
    if rol == "master" and intencion in _INTENCIONES_BLOQUEADAS_MASTER:
        return (
            "⚠️ El rol Master está dedicado exclusivamente a Seguridad, IAM y Auditoría.\n"
            "Las operaciones de stock, reposición y pedidos están reservadas para Administrador y Operador.\n"
            "Puedes consultar /auditoria, /backup, /estado o comunicarte por /equipo."
        )
    if rol == "operador" and intencion in _INTENCIONES_BLOQUEADAS_OPERADOR:
        return (
            "⚠️ Esta función está reservada para roles de gestión (Administrador).\n"
            "Como Operador puedes consultar /stock, /pedidos, /cierre o /mercadolibre."
        )
    if rol == "consulta" and intencion in _INTENCIONES_BLOQUEADAS_CONSULTA:
        return "⚠️ El rol Consulta es de solo lectura. Puedes consultar /stock, /criticos o /informes."
    if rol == "picker" and intencion in _INTENCIONES_BLOQUEADAS_PICKER:
        return (
            "⚠️ Esta función no está disponible para el perfil Picker.\n"
            "Como Picker puedes consultar /stock, /mercadolibre, /pedidos o comunicarte por /equipo."
        )
    if rol == "despachador" and intencion in _INTENCIONES_BLOQUEADAS_DESPACHADOR:
        return (
            "⚠️ El rol Despachador está dedicado exclusivamente al módulo Despacho.\n"
            "Puedes consultar /pedidos o comunicarte con el depósito por /equipo."
        )
    return None


def _responder_pedidos(interfaz: Any) -> str:
    pendientes = interfaz.order_store.listar_pedidos_pendientes_cierre()
    recientes = interfaz.order_store.listar_pedidos(limit=5)
    lineas = [
        "📦 Resumen de Pedidos del Sistema:\n",
        f"• Pendientes de cierre de jornada: {len(pendientes)} pedido(s) acumulados.",
    ]
    if pendientes:
        total_items = sum(p.articulos_descontados for p in pendientes)
        lineas.append(f"• Total unidades en pedidos pendientes: {total_items} ítem(s).")
    if recientes:
        lineas.append("\nÚltimos pedidos registrados:")
        for p in recientes[:4]:
            cli = p.cliente or "Consumidor Final"
            nota = f" [NP: {p.nota_pedido}]" if p.nota_pedido else ""
            est = "🟡 Pendiente" if p.cierre_id is None else "🟢 Cerrado"
            lineas.append(f"• {est} {p.created_at[:16]} - {cli}{nota} ({p.articulos_descontados} un., {p.estado_despacho})")
    lineas.append("\nPuedes cargar nuevos pedidos desde el menú 'Cargar / Armar Pedido'.")
    return "\n".join(lineas)


def _responder_cierre(interfaz: Any) -> str:
    pendientes = interfaz.order_store.listar_pedidos_pendientes_cierre()
    ultimos_cierres = interfaz.order_store.listar_cierres(limit=1)
    lineas = [
        "🖨️ Estado de Cierre de Jornada y Descuentos:\n",
        f"• Pedidos acumulados para el próximo cierre: {len(pendientes)}",
    ]
    if pendientes:
        lineas.append("  (Al realizar el cierre, estos pedidos se consolidarán e imprimirán en el informe diario).")
    else:
        lineas.append("  (No hay pedidos pendientes de cierre en este momento).")
    if ultimos_cierres:
        uc = ultimos_cierres[0]
        lineas.extend([
            "\nÚltimo cierre realizado:",
            f"• Fecha: {uc.created_at[:16]}",
            f"• Responsable: {uc.usuario}",
            f"• Pedidos consolidados: {uc.cantidad_pedidos} ({uc.articulos_totales} artículos)",
        ])
    lineas.append("\nPara generar un cierre formal, presiona 'Cierre de Jornada' en el menú lateral.")
    return "\n".join(lineas)


def _responder_reposicion(interfaz: Any) -> str:
    stock_mgr = _resolver_stock_manager()(interfaz.menu.ruta_excel_base)
    analisis = stock_mgr.obtener_analisis_reposicion(solo_criticos=True)
    if not analisis:
        return "¡Excelente! No hay productos en quiebre de stock ni bajo su umbral mínimo."
    lineas = [f"📋 Análisis de reposición ({len(analisis)} productos a pedir a fábrica):\n"]
    for r in analisis[:12]:
        cod = str(r["code"])
        nom = str(r["name"])[:30]
        stk = int(r["stock"])
        s_min = int(r["stock_minimo"])
        s_max = int(r["stock_maximo"])
        pedir = int(r["cantidad_sugerida_pedir"])
        est = str(r["estado_inventario"])
        lineas.append(f"• [{est}] [{cod}] {nom} -> Stock: {stk} (Mín: {s_min}, Máx: {s_max}) | Sugerido pedir: +{pedir} un.")
    if len(analisis) > 12:
        lineas.append(f"\n... y {len(analisis) - 12} productos más.")
    return "\n".join(lineas)


def _responder_chat_equipo(interfaz: Any, mensaje: str) -> str:
    cuerpo_msg = ""
    destinatario = "Todos"
    texto_limpio = mensaje.strip()

    if texto_limpio.lower().startswith(("/msg", "/mensaje", "/avisar", "msg ", "mensaje ")):
        partes = texto_limpio.split(maxsplit=2)
        if len(partes) > 1:
            if partes[1].startswith("@") and len(partes) > 2:
                destinatario = partes[1].lstrip("@")
                cuerpo_msg = partes[2]
            elif not partes[1].startswith("@"):
                cuerpo_msg = texto_limpio.split(maxsplit=1)[1]
    elif texto_limpio.startswith("@"):
        partes = texto_limpio.split(maxsplit=1)
        destinatario = partes[0].lstrip("@")
        if len(partes) > 1:
            cuerpo_msg = partes[1]

    if not cuerpo_msg:
        interfaz.cambiar_pestaña_chat("equipo")
        return (
            "👥 Cambiado al canal de **Chat de Equipo**.\n"
            "Aquí puedes escribir directamente a tus compañeros o al canal general."
        )

    emisor_nom = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
    cuerpo_enriq = interfaz._enriquecer_mensaje_con_pedidos(cuerpo_msg)
    interfaz.order_store.enviar_mensaje_chat(emisor=emisor_nom, mensaje=cuerpo_enriq, destinatario=destinatario)
    interfaz.sincronizar_sesiones(notificar_chat=(emisor_nom, destinatario, cuerpo_msg))
    interfaz.cargar_mensajes_equipo()
    tag_dest_txt = f"@{destinatario}" if destinatario != "Todos" else "📢 Todos los usuarios"
    return (
        f"💬 **Mensaje enviado al equipo:**\n"
        f"• Para: {tag_dest_txt}\n"
        f"• Mensaje: \"{cuerpo_msg}\"\n\n"
        f"💡 Puedes cambiar a la pestaña 'Chat Equipo' para ver la conversación completa."
    )


def _notificar_respuesta_chatbot(interfaz: Any, marcar_no_leido: bool = True) -> None:
    """Emite campana breve al responder el chatbot y activa el punto si no está visible."""
    try:
        if bool(getattr(interfaz, "sonido_chat_activo", True)):
            sonido_fn = getattr(interfaz, "reproducir_sonido", None)
            if callable(sonido_fn):
                sonido_fn("campana")
    except Exception:
        pass

    if not marcar_no_leido:
        return

    chat_abierto_en_bot = (
        bool(getattr(interfaz, "chat_visible", False))
        and getattr(interfaz, "modo_chat_activo", "bot") == "bot"
    )
    if not chat_abierto_en_bot:
        actual = getattr(interfaz, "_mensajes_bot_no_leidos", 0)
        interfaz._mensajes_bot_no_leidos = (actual if isinstance(actual, int) else 0) + 1
        badge_fn = getattr(interfaz, "actualizar_badge_chat", None)
        if callable(badge_fn):
            badge_fn()


async def procesar_mensaje_chat_agente(interfaz: Any, mensaje: str) -> None:
    """Procesa una consulta del usuario dirigida al asistente bot y redacta la respuesta contextual."""
    intencion = detectar_intencion(mensaje)
    rol = interfaz.usuario_actual.role if interfaz.usuario_actual else "operador"
    nom = interfaz.usuario_actual.username if interfaz.usuario_actual else ""

    aviso_permiso = _validar_permiso_intencion(rol, intencion)
    if aviso_permiso:
        interfaz.escribir_chat("Agente", aviso_permiso)
        _notificar_respuesta_chatbot(interfaz, marcar_no_leido=True)
        interfaz.page.update()
        return

    if intencion == "limpiar":
        interfaz.limpiar_chat()
        return

    if intencion == "estado":
        if rol == "master":
            try:
                from ...backup_manager import ejecutar_diagnostico_salud_sistema
                diag = ejecutar_diagnostico_salud_sistema()
                sql_status = "🟢 Íntegras (PRAGMA OK)" if diag["sqlite_ok"] else "🔴 Advertencia en BD"
                disco_txt = f"{diag['disco_libre_gb']} GB disponibles"
                espejo_txt = "Configurado" if diag["espejo_red"] else "Solo local"
                resumen_base = interfaz.resumen_estado()
                respuesta = (
                    f"🛡️ **Telemetría & Salud del Sistema (Master):**\n"
                    f"• Bases SQLite: {sql_status}\n"
                    f"• Espacio en disco: {disco_txt}\n"
                    f"• Copias de seguridad: {diag['total_backups']} respaldos (Último: {diag['ultimo_backup']})\n"
                    f"• Resguardo espejo/red: {espejo_txt}\n\n"
                    f"{resumen_base}"
                )
            except Exception:
                respuesta = interfaz.resumen_estado()
        else:
            respuesta = interfaz.resumen_estado()
    elif intencion == "informes":
        respuesta = interfaz.resumen_informes()
    elif intencion == "saludo":
        respuesta = obtener_mensaje_bienvenida(rol, nom)
    elif intencion == "ayuda":
        respuesta = obtener_comandos_ayuda(rol)
    elif intencion == "pedidos":
        respuesta = _responder_pedidos(interfaz)
    elif intencion == "cierre":
        respuesta = _responder_cierre(interfaz)
    elif intencion == "mercadolibre":
        respuesta = (
            "🟡 Descuento Mercado Libre (DOCX):\n"
            "• Permite descontar stock cargando las etiquetas o remitos en formato .docx.\n"
            "• Los productos se emparejan automáticamente por descripción contra el catálogo oficial.\n"
            "• Se actualiza el stock en la base SQLite y en el Excel, registrando además el pedido y generando un informe PDF.\n\n"
            "👉 Para utilizarlo, presiona el botón 'Descontar Mercado Libre' en el menú lateral."
        )
    elif intencion == "metricas":
        m = interfaz.order_store.obtener_metricas_dashboard()
        prom = (m["total_bultos"] / m["total_pedidos"]) if m["total_pedidos"] > 0 else 0
        respuesta = (
            f"📊 **Métricas del Depósito:**\n"
            f"• Total Pedidos: {m['total_pedidos']}\n"
            f"• Total Bultos: {m['total_bultos']} (promedio: {prom:.1f} bultos/pedido)\n"
            f"• Pedidos cerrados: {m['pedidos_cerrados']} | Pendientes: {m['pedidos_pendientes']}\n"
            f"• Cierres de jornada: {m['total_cierres']}\n\n"
            f"💡 Presiona 'Métricas y Rendimiento' en el menú de Administración para ver el panel interactivo completo."
        )
    elif intencion == "auditoria":
        logs = interfaz.order_store.listar_auditoria(limit=5)
        lineas = ["🛡️ **Últimos 5 Eventos de Auditoría:**\n"]
        for l in logs:
            lineas.append(f"• [{l.created_at[11:16]}] {l.usuario} ({l.accion}): {l.detalle}")
        lineas.append("\n💡 Accede a 'Registro de Auditoría' en el menú lateral para buscar y filtrar todos los eventos.")
        respuesta = "\n".join(lineas)
    elif intencion == "backup":
        carpeta_bks = _resolver_app_root()() / "data" / "backups"
        bks = sorted(carpeta_bks.glob("Backup_Deposito_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if carpeta_bks.exists() else []
        if bks:
            ultimo = bks[0]
            t_str = datetime.fromtimestamp(ultimo.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
            respuesta = (
                f"💾 **Copia de Seguridad:**\n"
                f"• Último respaldo: {ultimo.name}\n"
                f"• Fecha: {t_str}\n"
                f"• Respaldos en disco: {len(bks)} archivos en data/backups/\n\n"
                f"💡 Puedes generar un respaldo manual en cualquier momento desde 'Copia de Seguridad' en el menú lateral."
            )
        else:
            respuesta = "💾 Aún no se han generado copias de seguridad. Se generará una automáticamente en el próximo Cierre de Jornada o puedes presionar 'Copia de Seguridad' en el menú lateral."
    elif intencion == "criticos":
        productos = _resolver_stock_manager()(interfaz.menu.ruta_excel_base).listar_productos()
        respuesta = formatear_respuesta_criticos(productos)
    elif intencion == "reposicion" or mensaje.strip().casefold().startswith("/reposicion"):
        respuesta = _responder_reposicion(interfaz)
    elif intencion == "diagnostico":
        mayoristas, canjes, ml = interfaz.menu._obtener_pendientes()
        fab = interfaz.menu._obtener_pendientes_fabrica()
        full = getattr(interfaz.menu, "_obtener_pendientes_mercado_full", lambda: [])()
        respuesta = formatear_diagnostico_archivos(mayoristas, canjes, ml, fab, full)
    elif intencion == "ultimo_informe":
        respuesta = formatear_ultimo_informe(interfaz.informes)
    elif intencion == "buscar_stock":
        termino = extraer_termino_busqueda(mensaje)
        productos = _resolver_stock_manager()(interfaz.menu.ruta_excel_base).listar_productos()
        respuesta = formatear_respuesta_stock(termino, productos)
    elif intencion == "simular":
        if interfaz.ocupado:
            respuesta = "Ya hay una operación en curso. Inténtalo de nuevo al finalizar."
        elif not any(interfaz.fuentes_seleccionadas()):
            respuesta = "Selecciona al menos una fuente antes de iniciar la simulación."
        elif interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("operador", "administrador", "master"):
            respuesta = "No tienes permisos suficientes para iniciar simulaciones."
        else:
            respuesta = "Simulación de solo lectura iniciada."
            await interfaz.simular(None)
    elif intencion == "chat_equipo":
        respuesta = _responder_chat_equipo(interfaz, mensaje)
    else:
        respuesta = f"No reconocí la consulta.\n{obtener_pie_ayuda(rol)}"

    interfaz.escribir_chat("Agente", respuesta)
    solo_cambio_a_equipo = (
        intencion == "chat_equipo" and getattr(interfaz, "modo_chat_activo", "bot") == "equipo"
    )
    _notificar_respuesta_chatbot(interfaz, marcar_no_leido=not solo_cambio_a_equipo)
    interfaz.page.update()
