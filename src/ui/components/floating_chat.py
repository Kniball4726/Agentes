import sys
"""Componente de ventana de chat flotante (Asistente Bot y Chat de Equipo)."""
from datetime import datetime
from pathlib import Path
from typing import Any
import flet as ft
from ...internal_chat import (
    detectar_intencion,
    extraer_termino_busqueda,
    formatear_diagnostico_archivos,
    formatear_respuesta_criticos,
    formatear_respuesta_stock,
    formatear_ultimo_informe,
    obtener_chips_configuracion,
    obtener_comandos_ayuda,
    obtener_mensaje_bienvenida,
    obtener_pie_ayuda,
)
from ...paths import application_root
from ...stock_manager import StockManager
from ..theme import ROJO


def crear_ventana_chat_flotante(interfaz: Any) -> ft.Container:
    """Construye y devuelve el contenedor del chat flotante con pestañas de Asistente Bot y Chat de Equipo."""
    rol_actual = interfaz.usuario_actual.role if interfaz.usuario_actual else "operador"
    ico_encabezado = ft.Icon(
        ft.Icons.FORUM if interfaz.modo_chat_activo == "equipo" else ft.Icons.SMART_TOY,
        color=ft.Colors.WHITE if interfaz.modo_oscuro else ROJO,
        size=18,
    )
    encabezado_chat = ft.Row(
        [
            ft.Row(
                [
                    ft.Container(
                        width=34,
                        height=34,
                        border_radius=10,
                        bgcolor=ft.Colors.RED_900 if interfaz.modo_oscuro else ft.Colors.RED_50,
                        alignment=ft.Alignment.CENTER,
                        content=ico_encabezado,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                "StockAgent · Chat y Asistente",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                                color=interfaz.texto,
                            ),
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_400, size=8),
                                    ft.Text(f"Rol: {rol_actual.capitalize()} · En línea", size=10, color=interfaz.secundario),
                                ],
                                spacing=4,
                            ),
                        ],
                        spacing=1,
                    ),
                ],
                spacing=8,
            ),
            ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.DELETE_SWEEP_OUTLINED,
                        icon_color=interfaz.secundario,
                        icon_size=18,
                        tooltip="Limpiar conversación del bot",
                        on_click=interfaz.limpiar_chat,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                        icon_color=interfaz.secundario,
                        icon_size=20,
                        tooltip="Minimizar",
                        on_click=interfaz.alternar_chat_flotante,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_color=interfaz.secundario,
                        icon_size=18,
                        tooltip="Cerrar",
                        on_click=interfaz.cerrar_chat_flotante,
                    ),
                ],
                spacing=0,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    def mapear_icono(nombre: str) -> str:
        iconos = {
            "SEARCH": ft.Icons.SEARCH,
            "WARNING_AMBER_ROUNDED": ft.Icons.WARNING_AMBER_ROUNDED,
            "PRECISION_MANUFACTURING": ft.Icons.PRECISION_MANUFACTURING,
            "ANALYTICS": ft.Icons.ANALYTICS,
            "HISTORY": ft.Icons.HISTORY,
            "BACKUP": ft.Icons.BACKUP,
            "FACT_CHECK": ft.Icons.FACT_CHECK,
            "DASHBOARD": ft.Icons.DASHBOARD,
            "DESCRIPTION": ft.Icons.DESCRIPTION,
            "SCIENCE": ft.Icons.SCIENCE,
            "INVENTORY_2": ft.Icons.INVENTORY_2,
            "POINT_OF_SALE": ft.Icons.POINT_OF_SALE,
            "LOCAL_SHIPPING": ft.Icons.LOCAL_SHIPPING,
            "FOLDER_OPEN": ft.Icons.FOLDER_OPEN,
            "HELP_OUTLINE": ft.Icons.HELP_OUTLINE,
            "CHAT": ft.Icons.CHAT,
        }
        return iconos.get(nombre, ft.Icons.SMART_TOY)

    chips_def = obtener_chips_configuracion(rol_actual)
    chips_controles = []
    for item in chips_def:
        if len(item) == 3:
            etiqueta, comando, ico_nombre = item
        else:
            etiqueta, comando = item
            ico_nombre = "SMART_TOY"
        icono = mapear_icono(ico_nombre)
        boton_func = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icono, size=13, color=ft.Colors.WHITE if interfaz.modo_oscuro else ROJO),
                    ft.Text(etiqueta, size=11, weight=ft.FontWeight.W_600, color=interfaz.texto, no_wrap=True),
                ],
                spacing=5,
                tight=True,
            ),
            bgcolor=ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=14,
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            ink=True,
            tooltip=f"Comando {comando} - Clic para ejecutar",
            on_click=lambda _e, cmd=comando: interfaz.ejecutar_comando_rapido(cmd),
        )
        chips_controles.append(boton_func)

    chips_fila = ft.Row(
        chips_controles,
        scroll=ft.ScrollMode.AUTO,
        spacing=6,
    )

    input_fila = ft.Row(
        [
            interfaz.entrada_chat,
            ft.IconButton(
                icon=ft.Icons.SEND,
                icon_color=ft.Colors.WHITE,
                bgcolor=ROJO,
                tooltip="Enviar mensaje al bot",
                on_click=interfaz.enviar_chat,
            ),
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.END,
    )

    pie_texto = ft.Text(
        obtener_pie_ayuda(rol_actual),
        size=10,
        color=interfaz.secundario,
    )

    es_bot = interfaz.modo_chat_activo == "bot"
    cuerpo_bot = ft.Column(
        [
            chips_fila,
            ft.Divider(height=6, color=interfaz.borde),
            interfaz.conversacion,
            input_fila,
            pie_texto,
        ],
        expand=True,
        spacing=6,
        visible=es_bot,
    )

    barra_equipo = ft.Row(
        [
            interfaz.selector_destinatario_equipo,
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                icon_size=18,
                tooltip="Actualizar mensajes",
                on_click=lambda _e: (
                    interfaz.refrescar_usuarios_chat_equipo(),
                    interfaz.cargar_mensajes_equipo(),
                ),
            ),
        ],
        spacing=6,
    )

    input_fila_equipo = ft.Row(
        [
            interfaz.entrada_chat_equipo,
            ft.IconButton(
                icon=ft.Icons.SEND,
                icon_color=ft.Colors.WHITE,
                bgcolor=ROJO,
                tooltip="Enviar al equipo",
                on_click=interfaz.enviar_mensaje_equipo,
            ),
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    cuerpo_equipo = ft.Column(
        [
            barra_equipo,
            ft.Divider(height=6, color=interfaz.borde),
            interfaz.conversacion_equipo,
            input_fila_equipo,
        ],
        expand=True,
        spacing=6,
        visible=not es_bot,
    )

    def cambiar_tab(modo: str) -> None:
        interfaz.modo_chat_activo = modo
        es_bot_nuevo = (modo == "bot")
        cuerpo_bot.visible = es_bot_nuevo
        cuerpo_equipo.visible = not es_bot_nuevo

        btn_tab_bot.bgcolor = ROJO if es_bot_nuevo else (ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200)
        txt_tab_bot.color = ft.Colors.WHITE if es_bot_nuevo else interfaz.texto
        ico_tab_bot.color = ft.Colors.WHITE if es_bot_nuevo else interfaz.texto

        btn_tab_equipo.bgcolor = ROJO if not es_bot_nuevo else (ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200)
        txt_tab_equipo.color = ft.Colors.WHITE if not es_bot_nuevo else interfaz.texto
        ico_tab_equipo.color = ft.Colors.WHITE if not es_bot_nuevo else interfaz.texto

        ico_encabezado.icon = ft.Icons.SMART_TOY if es_bot_nuevo else ft.Icons.FORUM

        if modo == "equipo":
            interfaz.refrescar_usuarios_chat_equipo()
            interfaz.cargar_mensajes_equipo()
            if interfaz.usuario_actual:
                interfaz.order_store.marcar_mensajes_leidos(interfaz.usuario_actual.username)
                interfaz.actualizar_badge_chat()

        interfaz.page.update()

    interfaz._cambiar_tab_fn = cambiar_tab

    ico_tab_bot = ft.Icon(ft.Icons.SMART_TOY_OUTLINED, size=15, color=ft.Colors.WHITE if es_bot else interfaz.texto)
    txt_tab_bot = ft.Text("Asistente Bot", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE if es_bot else interfaz.texto)
    btn_tab_bot = ft.Container(
        content=ft.Row(
            [
                ico_tab_bot,
                txt_tab_bot,
            ],
            spacing=5,
            tight=True,
        ),
        bgcolor=ROJO if es_bot else (ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=12,
        ink=True,
        on_click=lambda _e: cambiar_tab("bot"),
    )

    ico_tab_equipo = ft.Icon(ft.Icons.FORUM_OUTLINED, size=15, color=interfaz.texto if es_bot else ft.Colors.WHITE)
    txt_tab_equipo = ft.Text("Chat Equipo", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto if es_bot else ft.Colors.WHITE)
    btn_tab_equipo = ft.Container(
        content=ft.Row(
            [
                ico_tab_equipo,
                txt_tab_equipo,
                interfaz.texto_badge_tab,
            ],
            spacing=5,
            tight=True,
        ),
        bgcolor=(ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200) if es_bot else ROJO,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=12,
        ink=True,
        on_click=lambda _e: cambiar_tab("equipo"),
    )

    barra_tabs = ft.Row(
        [
            btn_tab_bot,
            btn_tab_equipo,
        ],
        spacing=8,
    )

    es_movil = getattr(interfaz, "es_pantalla_movil", False)
    ventana = ft.Container(
        width=None if es_movil else 420,
        height=480 if es_movil else 550,
        left=8 if es_movil else None,
        right=8 if es_movil else 24,
        bottom=75 if es_movil else 90,
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=16,
        shadow=ft.BoxShadow(
            blur_radius=22,
            spread_radius=2,
            color=ft.Colors.BLACK_54 if interfaz.modo_oscuro else ft.Colors.BLACK_26,
            offset=ft.Offset(0, 8),
        ),
        padding=10 if es_movil else 14,
        visible=interfaz.chat_visible,
        content=ft.Column(
            [
                encabezado_chat,
                barra_tabs,
                cuerpo_bot,
                cuerpo_equipo,
            ],
            expand=True,
            spacing=8,
        ),
    )
    interfaz.ventana_chat_flotante = ventana
    return ventana


async def procesar_mensaje_chat_agente(interfaz: Any, mensaje: str) -> None:
    """Procesa una consulta del usuario dirigida al asistente bot y redacta la respuesta contextual."""
    intencion = detectar_intencion(mensaje)
    rol = interfaz.usuario_actual.role if interfaz.usuario_actual else "operador"
    nom = interfaz.usuario_actual.username if interfaz.usuario_actual else ""

    # Control de permisos según el rol activo
    if rol != "master" and intencion == "auditoria":
        interfaz.escribir_chat(
            "Agente",
            "⚠️ El registro de auditoría forense y eventos de seguridad está reservado exclusivamente para el rol Master (Seguridad & IAM).",
        )
        interfaz.page.update()
        return

    if rol == "master" and intencion in (
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
    ):
        interfaz.escribir_chat(
            "Agente",
            "⚠️ El rol Master está dedicado exclusivamente a Seguridad, IAM y Auditoría.\n"
            "Las operaciones de stock, reposición y pedidos están reservadas para Administrador y Operador.\n"
            "Puedes consultar /auditoria, /backup, /estado o comunicarte por /equipo.",
        )
        interfaz.page.update()
        return

    if rol == "operador" and intencion in ("simular", "reposicion", "diagnostico"):
        interfaz.escribir_chat(
            "Agente",
            "⚠️ Esta función está reservada para roles de gestión (Administrador).\n"
            "Como Operador puedes consultar /stock, /pedidos, /cierre o /mercadolibre.",
        )
        interfaz.page.update()
        return

    if rol == "consulta" and intencion in ("simular", "cierre", "mercadolibre", "pedidos"):
        interfaz.escribir_chat(
            "Agente",
            "⚠️ El rol Consulta es de solo lectura. Puedes consultar /stock, /criticos o /informes.",
        )
        interfaz.page.update()
        return

    if intencion == "estado":
        respuesta = interfaz.resumen_estado()
    elif intencion == "informes":
        respuesta = interfaz.resumen_informes()
    elif intencion == "saludo":
        respuesta = obtener_mensaje_bienvenida(rol, nom)
    elif intencion == "ayuda":
        respuesta = obtener_comandos_ayuda(rol)
    elif intencion == "pedidos":
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
        respuesta = "\n".join(lineas)
    elif intencion == "cierre":
        pendientes = interfaz.order_store.listar_pedidos_pendientes_cierre()
        ultimos_cierres = interfaz.order_store.listar_cierres(limit=1)
        lineas = ["🖨️ Estado de Cierre de Jornada y Descuentos:\n"]
        lineas.append(f"• Pedidos acumulados para el próximo cierre: {len(pendientes)}")
        if pendientes:
            lineas.append("  (Al realizar el cierre, estos pedidos se consolidarán e imprimirán en el informe diario).")
        else:
            lineas.append("  (No hay pedidos pendientes de cierre en este momento).")
        if ultimos_cierres:
            uc = ultimos_cierres[0]
            lineas.append("\nÚltimo cierre realizado:")
            lineas.append(f"• Fecha: {uc.created_at[:16]}")
            lineas.append(f"• Responsable: {uc.usuario}")
            lineas.append(f"• Pedidos consolidados: {uc.cantidad_pedidos} ({uc.articulos_totales} artículos)")
        lineas.append("\nPara generar un cierre formal, presiona 'Cierre de Jornada' en el menú lateral.")
        respuesta = "\n".join(lineas)
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
        carpeta_bks = application_root() / "data" / "backups"
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
                # Resolver StockManager dinámicamente para soportar mocks y evitar acoplamiento rígido
        _sm_cls = getattr(sys.modules.get("src.flet_gui"), "StockManager", StockManager)
        stock_mgr = _sm_cls(interfaz.menu.ruta_excel_base)
        productos = stock_mgr.listar_productos()
        respuesta = formatear_respuesta_criticos(productos)
    elif intencion == "reposicion" or mensaje.strip().casefold().startswith("/reposicion"):
                # Resolver StockManager dinámicamente para soportar mocks y evitar acoplamiento rígido
        _sm_cls = getattr(sys.modules.get("src.flet_gui"), "StockManager", StockManager)
        stock_mgr = _sm_cls(interfaz.menu.ruta_excel_base)
        analisis = stock_mgr.obtener_analisis_reposicion(solo_criticos=True)
        if not analisis:
            respuesta = "¡Excelente! No hay productos en quiebre de stock ni bajo su umbral mínimo."
        else:
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
            respuesta = "\n".join(lineas)
    elif intencion == "diagnostico":
        mayoristas, canjes, ml = interfaz.menu._obtener_pendientes()
        fab = interfaz.menu._obtener_pendientes_fabrica()
        full = getattr(interfaz.menu, "_obtener_pendientes_mercado_full", lambda: [])()
        respuesta = formatear_diagnostico_archivos(mayoristas, canjes, ml, fab, full)
    elif intencion == "ultimo_informe":
        respuesta = formatear_ultimo_informe(interfaz.informes)
    elif intencion == "buscar_stock":
        termino = extraer_termino_busqueda(mensaje)
                # Resolver StockManager dinámicamente para soportar mocks y evitar acoplamiento rígido
        _sm_cls = getattr(sys.modules.get("src.flet_gui"), "StockManager", StockManager)
        stock_mgr = _sm_cls(interfaz.menu.ruta_excel_base)
        productos = stock_mgr.listar_productos()
        respuesta = formatear_respuesta_stock(termino, productos)
    elif intencion == "limpiar":
        interfaz.limpiar_chat()
        return
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

        if cuerpo_msg:
            emisor_nom = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
            cuerpo_enriq = interfaz._enriquecer_mensaje_con_pedidos(cuerpo_msg)
            interfaz.order_store.enviar_mensaje_chat(
                emisor=emisor_nom,
                mensaje=cuerpo_enriq,
                destinatario=destinatario,
            )
            interfaz.sincronizar_sesiones(notificar_chat=(emisor_nom, destinatario, cuerpo_msg))
            interfaz.cargar_mensajes_equipo()
            tag_dest_txt = f"@{destinatario}" if destinatario != "Todos" else "📢 Todos los usuarios"
            respuesta = (
                f"💬 **Mensaje enviado al equipo:**\n"
                f"• Para: {tag_dest_txt}\n"
                f"• Mensaje: \"{cuerpo_msg}\"\n\n"
                f"💡 Puedes cambiar a la pestaña 'Chat Equipo' para ver la conversación completa."
            )
        else:
            interfaz.cambiar_pestaña_chat("equipo")
            respuesta = (
                "👥 Cambiado al canal de **Chat de Equipo**.\n"
                "Aquí puedes escribir directamente a tus compañeros o al canal general."
            )
    else:
        respuesta = (
            f"No reconocí la consulta.\n"
            f"{obtener_pie_ayuda(rol)}"
        )
    interfaz.escribir_chat("Agente", respuesta)
    interfaz.page.update()
