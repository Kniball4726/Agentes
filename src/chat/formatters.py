"""Formateadores de respuestas operativas (stock, críticos, bandeja de entrada e informes)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

from .intent_parser import normalizar_texto


_STOPWORDS_SUSTITUTOS = {
    "de", "del", "la", "las", "el", "los", "en", "con", "y", "o", "a", "al", "para", "por",
    "un", "una", "unos", "unas", "sin", "sobre", "x", "mm", "cm", "mts",
}


def buscar_sustitutos_disponibles(
    codigo_original: str,
    nombre_original: str,
    productos: Iterable[Any],
    limite: int = 3,
) -> list[tuple[str, str, int]]:
    """Busca productos alternativos activos con stock positivo basados en palabras clave o prefijo de código."""
    cod_orig_norm = normalizar_texto(codigo_original)
    nom_orig_norm = normalizar_texto(nombre_original)
    palabras_clave = [p for p in nom_orig_norm.split() if len(p) >= 3 and p not in _STOPWORDS_SUSTITUTOS]
    prefijo_cod = cod_orig_norm[:4] if len(cod_orig_norm) >= 4 else cod_orig_norm

    candidatos = []
    for p in productos:
        has_sub = isinstance(p, dict) or hasattr(p, "__getitem__")
        cod = str(p["code"] if has_sub else getattr(p, "code", ""))
        nom = str(p["name"] if has_sub else getattr(p, "name", ""))
        stk = int(p["stock"] if has_sub else getattr(p, "stock", 0))
        act = bool(p["active"] if has_sub else getattr(p, "active", True))

        if not act or stk <= 0:
            continue

        cod_norm = normalizar_texto(cod)
        if cod_norm == cod_orig_norm:
            continue

        nom_norm = normalizar_texto(nom)
        puntos = 0

        # Coincidencia de palabras clave
        palabras_coincidentes = sum(1 for pal in palabras_clave if pal in nom_norm)
        if palabras_coincidentes > 0:
            puntos += palabras_coincidentes * 30

        # Mismo prefijo de código (familia)
        if len(prefijo_cod) >= 3 and cod_norm.startswith(prefijo_cod):
            puntos += 25

        if puntos > 0:
            candidatos.append((puntos, stk, cod, nom))

    candidatos.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [(c[2], c[3], c[1]) for c in candidatos[:limite]]


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
        has_sub = isinstance(p, dict) or hasattr(p, "__getitem__")
        codigo = str(p["code"] if has_sub else getattr(p, "code", ""))
        nombre = str(p["name"] if has_sub else getattr(p, "name", ""))
        stock = int(p["stock"] if has_sub else getattr(p, "stock", 0))
        activo = bool(p["active"] if has_sub else getattr(p, "active", True))

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
        extra_sustitutos = ""
        if stk <= 0:
            stk_txt = f"{stk} unidades (SIN STOCK)"
            sustitutos = buscar_sustitutos_disponibles(cod, nom, productos, limite=3)
            if sustitutos:
                items_sust = "\n".join(f"• [{s_cod}] {s_nom[:35]} ({s_stk} un.)" for s_cod, s_nom, s_stk in sustitutos)
                extra_sustitutos = f"\n\n💡 Alternativas sugeridas con stock:\n{items_sust}"
        elif stk <= 5:
            stk_txt = f"{stk} unidades (STOCK BAJO)"
        else:
            stk_txt = f"{stk} unidades"

        return (
            "📦 Producto Encontrado:\n"
            f"• Código: {cod}\n"
            f"• Descripción: {nom}\n"
            f"• Stock disponible: {stk_txt}\n"
            f"• Estado: {estado_txt}"
            f"{extra_sustitutos}"
        )

    lineas = [f"🔍 Encontré {len(coincidencias)} productos relacionados con '{termino}':\n"]
    for _, cod, nom, stk, _ in coincidencias[:5]:
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
        has_sub = isinstance(p, dict) or hasattr(p, "__getitem__")
        codigo = str(p["code"] if has_sub else getattr(p, "code", ""))
        nombre = str(p["name"] if has_sub else getattr(p, "name", ""))
        stock = int(p["stock"] if has_sub else getattr(p, "stock", 0))
        activo = bool(p["active"] if has_sub else getattr(p, "active", True))
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
    categorias = (
        ("Mayoristas (PDF)", "archivo(s)", mayoristas),
        ("Canjes (Excel)", "planilla(s)", canjes),
        ("Mercado Libre (DOCX)", "pedido(s)", mercado_libre),
        ("Pedidos de Fábrica (Ingreso)", "archivo(s)", fab_lista),
        ("Envíos Mercado Full (Excel)", "planilla(s)", full_lista),
    )
    for nombre_cat, unidad, archivos in categorias:
        if archivos:
            lineas.append(f"• {nombre_cat}: {len(archivos)} {unidad}")
            for arch in archivos[:3]:
                lineas.append(f"   - {arch.name}")
            if len(archivos) > 3:
                lineas.append(f"   - ...y {len(archivos) - 3} más")

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
        "📄 Último Informe Generado:\n"
        f"• Nombre: {ultimo.name}\n"
        f"• Formato: {tipo} ({tamano_kb} KB)\n"
        "• Selecciónalo en la lista para abrirlo o compartirlo."
    )
