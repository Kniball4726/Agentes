"""Reconocimiento local de intenciones y lógica para el chat del agente."""

import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Sequence


_PALABRAS_AYUDA = ("ayuda", "comando", "que puedes hacer", "opciones", "/ayuda", "help")
_SALUDOS = {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hey", "saludos"}


def normalizar_texto(texto: str) -> str:
    """Normaliza quitando acentos y convirtiendo a minúsculas limpias."""
    t = unicodedata.normalize("NFD", texto.casefold())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    palabras = re.findall(r"[a-z0-9]+", t)
    return " ".join(palabras)


def detectar_intencion(mensaje: str) -> str:
    """Detecta la intención operativa del usuario a partir de su mensaje."""
    normalizado = normalizar_texto(mensaje)
    palabras = normalizado.split()

    if not normalizado:
        return "desconocido"

    # 1. Simulación
    if any(palabra.startswith("simul") for palabra in palabras):
        return "simular"

    # 2. Limpiar chat
    if normalizado in ("limpiar", "clear", "limpiar chat", "borrar chat", "limpiar conversacion"):
        return "limpiar"

    # 3. Ayuda específica
    if any(frase in normalizado for frase in _PALABRAS_AYUDA):
        return "ayuda"

    # 4. Saludos
    if normalizado in _SALUDOS:
        return "saludo"

    # 5. Stock crítico / bajo / agotado
    if (
        normalizado in ("criticos", "critico", "agotados", "bajo stock")
        or any(
            frase in normalizado
            for frase in (
                "stock critico",
                "stock bajo",
                "sin stock",
                "quiebre de stock",
                "poco stock",
                "agotado",
                "agotados",
                "productos criticos",
                "productos bajo stock",
                "por agotarse",
            )
        )
    ):
        return "criticos"

    # 6. Diagnóstico de archivos pendientes
    if (
        normalizado in ("diagnostico", "revisar", "analizar")
        or any(
            frase in normalizado
            for frase in (
                "diagnostico de archivos",
                "revisar archivos",
                "analizar pendientes",
                "verificar archivos",
                "diagnosticar",
            )
        )
    ):
        return "diagnostico"

    # 7. Último informe generado
    if (
        normalizado in ("ultimo", "ultimoreporte", "ultimoinforme")
        or any(
            frase in normalizado
            for frase in (
                "ultimo informe",
                "ultimo reporte",
                "ultimo descuento",
                "ultimo archivo generado",
                "que se genero hoy",
            )
        )
    ):
        return "ultimo_informe"

    # 8. Consulta de stock o búsqueda de producto
    if (
        mensaje.strip().lower().startswith(("/stock", "/buscar", "stock ", "buscar "))
        or any(
            frase in normalizado
            for frase in (
                "cuanto stock",
                "stock de",
                "stock del",
                "hay stock",
                "buscar producto",
                "consultar stock",
            )
        )
        or (len(palabras) >= 2 and palabras[0] in ("stock", "buscar"))
    ):
        return "buscar_stock"

    # 9. Estado de pendientes o archivados
    if normalizado == "estado" or any(
        palabra in palabras for palabra in ("estado", "pendiente", "pendientes", "archivado", "archivados")
    ):
        return "estado"

    # 10. Informes generados
    if any(palabra in palabras for palabra in ("informe", "informes", "reporte", "reportes")):
        return "informes"

    # 11. Reposición para fábrica
    if (
        normalizado in ("reposicion", "reponer", "compras", "pedir a fabrica", "fabricacion")
        or any(frase in normalizado for frase in ("sugerido pedir", "cuanto pedir", "pedir fabrica", "comprar a fabrica"))
    ):
        return "reposicion"

    # 12. Pedidos y armado
    if (
        normalizado in ("pedidos", "pedido", "historial", "mis pedidos")
        or any(
            frase in normalizado
            for frase in ("pedidos de hoy", "ver pedidos", "armar pedido", "pedidos armados", "pedidos pendientes")
        )
    ):
        return "pedidos"

    # 13. Cierre de jornada y descuentos
    if (
        normalizado in ("cierre", "cierres", "descuento", "descuentos", "cierre de jornada")
        or any(
            frase in normalizado
            for frase in ("imprimir descuento", "hacer cierre", "cierre diario", "descuentos del dia")
        )
    ):
        return "cierre"

    # 14. Mercado Libre
    if (
        normalizado in ("mercadolibre", "mercado libre", "ml")
        or any(
            frase in normalizado
            for frase in ("remito mercadolibre", "remito ml", "descontar ml", "archivo docx", "descontar mercado libre")
        )
    ):
        return "mercadolibre"

    return "desconocido"


def extraer_termino_busqueda(mensaje: str) -> str:
    """Extrae el código o descripción a buscar del mensaje del usuario."""
    limpio = mensaje.strip()
    match_cmd = re.match(r"^/(?:stock|buscar)\s+(.*)$", limpio, re.IGNORECASE)
    if match_cmd:
        return match_cmd.group(1).strip()

    patrones = [
        r"(?:cuanto\s+stock\s+(?:queda\s+)?(?:de|del|hay\s+de)?\s*)(.+)",
        r"(?:hay\s+stock\s+de(?:l)?\s*)(.+)",
        r"(?:buscar\s+(?:el\s+)?producto\s*)(.+)",
        r"(?:stock\s+(?:de|del)?\s*)(.+)",
        r"(?:buscar\s+)(.+)",
    ]
    norm = normalizar_texto(limpio)
    for pat in patrones:
        m = re.search(pat, norm)
        if m:
            termino = m.group(1).strip()
            termino = re.sub(r"[?¿!¡.,;:]", "", termino).strip()
            if termino:
                return termino

    palabras_a_quitar = {"stock", "buscar", "producto", "codigo", "cuanto", "queda", "hay", "de", "del", "el", "la"}
    tokens = [t for t in norm.split() if t not in palabras_a_quitar]
    return " ".join(tokens)


def formatear_respuesta_stock(termino: str, productos: Iterable[Any]) -> str:
    """Busca en el catálogo y genera un mensaje con el stock disponible."""
    termino_norm = normalizar_texto(termino)
    if not termino_norm:
        return (
            "Indica el código o nombre del producto a consultar. "
            "Ejemplo: `/stock 1002` o `stock filtro`."
        )

    coincidencias = []
    for p in productos:
        codigo = str(p["code"] if isinstance(p, dict) or hasattr(p, "__getitem__") else getattr(p, "code", ""))
        nombre = str(p["name"] if isinstance(p, dict) or hasattr(p, "__getitem__") else getattr(p, "name", ""))
        stock = int(p["stock"] if isinstance(p, dict) or hasattr(p, "__getitem__") else getattr(p, "stock", 0))
        activo = bool(p["active"] if isinstance(p, dict) or hasattr(p, "__getitem__") else getattr(p, "active", True))

        cod_norm = normalizar_texto(codigo)
        nom_norm = normalizar_texto(nombre)

        puntos = 0
        if termino_norm == cod_norm:
            puntos += 100
        elif cod_norm.startswith(termino_norm) or termino_norm in cod_norm:
            puntos += 60

        if termino_norm in nom_norm:
            puntos += 40
        else:
            palabras_termino = termino_norm.split()
            if palabras_termino and all(palabra in nom_norm for palabra in palabras_termino):
                puntos += 25

        if puntos > 0:
            coincidencias.append((puntos, codigo, nombre, stock, activo))

    if not coincidencias:
        return (
            f"No encontré ningún producto que coincida con '{termino}'. "
            "Verifica el código o prueba con otra palabra clave."
        )

    coincidencias.sort(key=lambda x: (x[0], x[3]), reverse=True)

    if len(coincidencias) == 1:
        _, cod, nom, stk, act = coincidencias[0]
        estado_txt = "Activo" if act else "Inactivo"
        if stk <= 0:
            stk_txt = f"{stk} unidades (SIN STOCK)"
        elif stk <= 5:
            stk_txt = f"{stk} unidades (STOCK BAJO)"
        else:
            stk_txt = f"{stk} unidades"

        return (
            f"📦 Producto Encontrado:\n"
            f"• Código: {cod}\n"
            f"• Descripción: {nom}\n"
            f"• Stock disponible: {stk_txt}\n"
            f"• Estado: {estado_txt}"
        )

    lineas = [f"🔍 Encontré {len(coincidencias)} productos relacionados con '{termino}':\n"]
    for _, cod, nom, stk, act in coincidencias[:5]:
        alerta = " [SIN STOCK]" if stk <= 0 else (" [BAJO]" if stk <= 5 else "")
        lineas.append(f"• [{cod}] {nom[:38]} -> {stk} un.{alerta}")

    if len(coincidencias) > 5:
        lineas.append(f"\n... y {len(coincidencias) - 5} coincidencias más.")
    else:
        lineas.append("\nPuedes consultar un código específico con: /stock <código>")

    return "\n".join(lineas)


def formatear_respuesta_criticos(productos: Iterable[Any], umbral: int = 5) -> str:
    """Retorna productos activos con stock menor o igual a su stock mínimo."""
    criticos = []
    for p in productos:
        codigo = str(p["code"] if isinstance(p, dict) or hasattr(p, "__getitem__") else getattr(p, "code", ""))
        nombre = str(p["name"] if isinstance(p, dict) or hasattr(p, "__getitem__") else getattr(p, "name", ""))
        stock = int(p["stock"] if isinstance(p, dict) or hasattr(p, "__getitem__") else getattr(p, "stock", 0))
        activo = bool(p["active"] if isinstance(p, dict) or hasattr(p, "__getitem__") else getattr(p, "active", True))
        try:
            minimo = int(p["stock_minimo"])
        except Exception:
            minimo = getattr(p, "stock_minimo", umbral)

        if activo and stock <= minimo:
            criticos.append((stock, codigo, nombre, minimo))

    if not criticos:
        return "¡Excelente! No hay productos activos en nivel crítico ni quiebre de stock."

    criticos.sort(key=lambda x: (x[0], x[1]))

    lineas = [f"⚠️ {len(criticos)} producto(s) en nivel crítico o quiebre de stock:\n"]
    for stk, cod, nom, min_val in criticos[:8]:
        aviso = "[AGOTADO]" if stk <= 0 else f"[BAJO - Mín: {min_val}]"
        lineas.append(f"• {aviso} [{cod}] {nom[:32]} -> {stk} un.")

    if len(criticos) > 8:
        lineas.append(f"\n... y {len(criticos) - 8} productos más con bajo stock.")

    return "\n".join(lineas)


def formatear_diagnostico_archivos(
    mayoristas: Sequence[Path],
    canjes: Sequence[Path],
    mercado_libre: Sequence[Path],
    fabrica: Sequence[Path] | None = None,
    mercado_full: Sequence[Path] | None = None,
) -> str:
    """Genera un análisis rápido de la bandeja de entrada de archivos."""
    fab_lista = list(fabrica or [])
    full_lista = list(mercado_full or [])
    total = len(mayoristas) + len(canjes) + len(mercado_libre) + len(fab_lista) + len(full_lista)
    if total == 0:
        return (
            "📋 Diagnóstico de archivos:\n"
            "• No hay archivos pendientes en las carpetas de entrada.\n"
            "• Listo para recibir nuevos PDFs, Excels o DOCXs."
        )

    lineas = [f"📋 Diagnóstico de bandeja ({total} pendientes):\n"]
    if mayoristas:
        lineas.append(f"• Mayoristas (PDF): {len(mayoristas)} archivo(s)")
        for m in mayoristas[:3]:
            lineas.append(f"   - {m.name}")
        if len(mayoristas) > 3:
            lineas.append(f"   - ...y {len(mayoristas) - 3} más")

    if canjes:
        lineas.append(f"• Canjes (Excel): {len(canjes)} planilla(s)")
        for c in canjes[:3]:
            lineas.append(f"   - {c.name}")
        if len(canjes) > 3:
            lineas.append(f"   - ...y {len(canjes) - 3} más")

    if mercado_libre:
        lineas.append(f"• Mercado Libre (DOCX): {len(mercado_libre)} pedido(s)")
        for ml in mercado_libre[:3]:
            lineas.append(f"   - {ml.name}")
        if len(mercado_libre) > 3:
            lineas.append(f"   - ...y {len(mercado_libre) - 3} más")

    if fab_lista:
        lineas.append(f"• Pedidos de Fábrica (Ingreso): {len(fab_lista)} archivo(s)")
        for fb in fab_lista[:3]:
            lineas.append(f"   - {fb.name}")
        if len(fab_lista) > 3:
            lineas.append(f"   - ...y {len(fab_lista) - 3} más")

    if full_lista:
        lineas.append(f"• Envíos Mercado Full (Excel): {len(full_lista)} planilla(s)")
        for fl in full_lista[:3]:
            lineas.append(f"   - {fl.name}")
        if len(full_lista) > 3:
            lineas.append(f"   - ...y {len(full_lista) - 3} más")

    lineas.append("\nTip: Ejecuta /simular para chequear consistencia sin descontar stock.")
    return "\n".join(lineas)


def formatear_ultimo_informe(informes: Sequence[Path]) -> str:
    """Muestra los datos del último informe generado."""
    if not informes:
        return "No hay informes generados todavía. Realiza un procesamiento para crear el primero."

    ultimo = informes[0]
    tipo = "PDF" if ultimo.suffix.lower() == ".pdf" else "Excel"
    tamano_kb = round(ultimo.stat().st_size / 1024, 1) if ultimo.exists() else 0
    return (
        f"📄 Último Informe Generado:\n"
        f"• Nombre: {ultimo.name}\n"
        f"• Formato: {tipo} ({tamano_kb} KB)\n"
        f"• Selecciónalo en la lista para abrirlo o compartirlo."
    )


def obtener_mensaje_bienvenida(rol: str, nombre_usuario: str = "") -> str:
    """Genera un mensaje de bienvenida contextualizado al rol del usuario."""
    nombre = f" {nombre_usuario}" if nombre_usuario else ""
    if rol == "operador":
        return (
            f"¡Hola{nombre}! 👋 Soy tu asistente de depósito.\n"
            "Puedo ayudarte a consultar stock y existencias en tiempo real (/stock <código>), "
            "ver el estado de pedidos del día (/pedidos), guiarte con remitos DOCX (/mercadolibre) "
            "o consultar el cierre de jornada (/cierre).\n"
            "Escribe /ayuda para ver todos tus comandos."
        )
    elif rol in ("administrador", "master"):
        return (
            f"¡Hola{nombre}! 👋 Asistente de Gestión Activo.\n"
            "Puedes supervisar stock crítico (/criticos), calcular reposición para fábrica (/reposicion), "
            "verificar archivos pendientes (/diagnostico), simular remitos (/simular) y auditar inventario (/stock).\n"
            "Escribe /ayuda para ver el listado de comandos."
        )
    else:  # consulta o por defecto
        return (
            f"¡Hola{nombre}! 👋 Asistente de Consulta y Auditoría.\n"
            "Puedes consultar existencias en tiempo real (/stock <código>), verificar productos críticos (/criticos) "
            "o revisar informes (/informes).\n"
            "Escribe /ayuda para más información."
        )


def obtener_comandos_ayuda(rol: str) -> str:
    """Retorna la lista de comandos permitidos según el rol."""
    if rol == "operador":
        return (
            "📋 Comandos disponibles para Operador:\n"
            "• /stock <código o nombre>: Consulta existencias y ubicación en tiempo real.\n"
            "• /pedidos: Resumen de pedidos cargados y armados durante la jornada.\n"
            "• /cierre: Información sobre descuentos y estado del cierre de jornada.\n"
            "• /mercadolibre: Guía para descontar remitos de Mercado Libre (DOCX).\n"
            "• /limpiar: Limpia la pantalla del chat."
        )
    elif rol in ("administrador", "master"):
        return (
            "📋 Comandos disponibles para Administrador / Master:\n"
            "• /stock <código o nombre>: Consulta stock y estado en tiempo real.\n"
            "• /criticos: Lista productos con stock bajo o agotados.\n"
            "• /reposicion: Sugiere cantidades a pedir a fábrica para evitar quiebres.\n"
            "• /diagnostico: Analiza remitos, canjes, ML, fábrica y full pendientes.\n"
            "• /estado: Muestra resumen de pendientes y archivados.\n"
            "• /informes: Lista todos los informes generados.\n"
            "• /ultimo: Muestra información del informe más reciente.\n"
            "• /simular: Ejecuta una simulación de prueba sin alterar stock.\n"
            "• /pedidos: Resumen de pedidos del sistema.\n"
            "• /cierre: Resumen de cierres y descuentos acumulados.\n"
            "• /limpiar: Limpia la pantalla del chat."
        )
    else:  # consulta
        return (
            "📋 Comandos disponibles (Modo Consulta):\n"
            "• /stock <código o nombre>: Consulta stock y estado en tiempo real.\n"
            "• /criticos: Lista productos con stock bajo o agotados.\n"
            "• /informes: Lista los informes generados.\n"
            "• /ultimo: Muestra el informe más reciente.\n"
            "• /limpiar: Limpia la pantalla del chat."
        )


def obtener_chips_configuracion(rol: str) -> list[tuple[str, str]]:
    """Devuelve pares (etiqueta, comando) para los botones rápidos según el rol."""
    if rol == "operador":
        return [
            ("🔍 Stock", "/stock"),
            ("📦 Pedidos", "/pedidos"),
            ("🖨️ Cierre", "/cierre"),
            ("🟡 Mercado Libre", "/mercadolibre"),
            ("❓ Ayuda", "/ayuda"),
        ]
    elif rol in ("administrador", "master"):
        return [
            ("📦 Críticos", "/criticos"),
            ("🏭 Reposición", "/reposicion"),
            ("📋 Diagnóstico", "/diagnostico"),
            ("📄 Último", "/ultimo"),
            ("📊 Estado", "/estado"),
            ("🧪 Simular", "/simular"),
            ("🔍 Stock", "/stock"),
        ]
    else:  # consulta
        return [
            ("🔍 Stock", "/stock"),
            ("📦 Críticos", "/criticos"),
            ("📊 Informes", "/informes"),
            ("📄 Último", "/ultimo"),
            ("❓ Ayuda", "/ayuda"),
        ]


def obtener_pie_ayuda(rol: str) -> str:
    """Texto de ayuda en el pie de la ventana de chat según el rol."""
    if rol == "operador":
        return "Usa /stock <cód>, /pedidos, /cierre, /mercadolibre o /ayuda"
    elif rol in ("administrador", "master"):
        return "Usa /stock <cód>, /criticos, /reposicion, /diagnostico, /estado o /ayuda"
    else:
        return "Usa /stock <cód>, /criticos, /informes o /ayuda"

