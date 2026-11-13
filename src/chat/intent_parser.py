"""Normalización de texto y detección local de intenciones operativas."""

from __future__ import annotations

import re
import unicodedata

_PALABRAS_AYUDA = ("ayuda", "comando", "que puedes hacer", "opciones", "/ayuda", "help")
_SALUDOS = {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hey", "saludos"}

_REGLAS_FRASES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "criticos",
        ("criticos", "critico", "agotados", "bajo stock"),
        ("stock critico", "stock bajo", "sin stock", "quiebre de stock", "poco stock", "agotado", "agotados", "productos criticos", "productos bajo stock", "por agotarse"),
    ),
    (
        "diagnostico",
        ("diagnostico", "revisar", "analizar"),
        ("diagnostico de archivos", "revisar archivos", "analizar pendientes", "verificar archivos", "diagnosticar"),
    ),
    (
        "ultimo_informe",
        ("ultimo", "ultimoreporte", "ultimoinforme"),
        ("ultimo informe", "ultimo reporte", "ultimo descuento", "ultimo archivo generado", "que se genero hoy"),
    ),
)

_REGLAS_FRASES_SECUNDARIAS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "reposicion",
        ("reposicion", "reponer", "compras", "pedir a fabrica", "fabricacion"),
        ("sugerido pedir", "cuanto pedir", "pedir fabrica", "comprar a fabrica"),
    ),
    (
        "pedidos",
        ("pedidos", "pedido", "historial", "mis pedidos"),
        ("pedidos de hoy", "ver pedidos", "armar pedido", "pedidos armados", "pedidos pendientes"),
    ),
    (
        "cierre",
        ("cierre", "cierres", "descuento", "descuentos", "cierre de jornada"),
        ("imprimir descuento", "hacer cierre", "cierre diario", "descuentos del dia"),
    ),
    (
        "mercadolibre",
        ("mercadolibre", "mercado libre", "ml"),
        ("remito mercadolibre", "remito ml", "descontar ml", "archivo docx", "descontar mercado libre"),
    ),
    (
        "metricas",
        ("metricas", "kpi", "dashboard", "estadisticas"),
        ("metricas del deposito", "rendimiento", "estadistica"),
    ),
    (
        "auditoria",
        ("auditoria", "logs", "trazabilidad", "eventos"),
        ("registro de auditoria", "log de cambios", "quien anulo"),
    ),
    (
        "backup",
        ("backup", "respaldo", "copia de seguridad"),
        ("hacer backup", "crear respaldo", "guardar copia"),
    ),
)


def normalizar_texto(texto: str) -> str:
    """Normaliza quitando acentos y convirtiendo a minúsculas limpias."""
    t = unicodedata.normalize("NFD", texto.casefold())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", t))


def detectar_intencion(mensaje: str) -> str:
    """Detecta la intención operativa del usuario a partir de su mensaje."""
    normalizado = normalizar_texto(mensaje)
    palabras = normalizado.split()
    if not normalizado:
        return "desconocido"

    if any(palabra.startswith("simul") for palabra in palabras):
        return "simular"

    if normalizado in ("limpiar", "clear", "limpiar chat", "borrar chat", "limpiar conversacion"):
        return "limpiar"

    if (
        mensaje.strip().lower().startswith(("/msg", "/mensaje", "/avisar", "msg ", "mensaje ", "@"))
        or normalizado in ("mensajes", "chat equipo", "mensajes equipo", "mensajeria", "equipo", "/equipo")
        or any(frase in normalizado for frase in ("mensaje a", "aviso a", "escribir a", "chat de equipo"))
    ):
        return "chat_equipo"

    if any(frase in normalizado for frase in _PALABRAS_AYUDA):
        return "ayuda"

    if normalizado in _SALUDOS:
        return "saludo"

    for intencion, exactos, frases in _REGLAS_FRASES:
        if normalizado in exactos or any(f in normalizado for f in frases):
            return intencion

    if (
        mensaje.strip().lower().startswith(("/stock", "/buscar", "stock ", "buscar "))
        or any(f in normalizado for f in ("cuanto stock", "stock de", "stock del", "hay stock", "buscar producto", "consultar stock"))
        or (len(palabras) >= 2 and palabras[0] in ("stock", "buscar"))
    ):
        return "buscar_stock"

    if normalizado == "estado" or any(p in palabras for p in ("estado", "pendiente", "pendientes", "archivado", "archivados")):
        return "estado"

    if any(p in palabras for p in ("informe", "informes", "reporte", "reportes")):
        return "informes"

    for intencion, exactos, frases in _REGLAS_FRASES_SECUNDARIAS:
        if normalizado in exactos or any(f in normalizado for f in frases):
            return intencion

    return "desconocido"


def extraer_termino_busqueda(mensaje: str) -> str:
    """Extrae el código o descripción a buscar del mensaje del usuario."""
    limpio = mensaje.strip()
    match_cmd = re.match(r"^/(?:stock|buscar)\s+(.*)$", limpio, re.IGNORECASE)
    if match_cmd:
        return match_cmd.group(1).strip()

    patrones = (
        r"(?:cuanto\s+stock\s+(?:queda\s+)?(?:de|del|hay\s+de)?\s*)(.+)",
        r"(?:hay\s+stock\s+de(?:l)?\s*)(.+)",
        r"(?:buscar\s+(?:el\s+)?producto\s*)(.+)",
        r"(?:stock\s+(?:de|del)?\s*)(.+)",
        r"(?:buscar\s+)(.+)",
    )
    norm = normalizar_texto(limpio)
    for pat in patrones:
        m = re.search(pat, norm)
        if m:
            termino = re.sub(r"[?¿!¡.,;:]", "", m.group(1).strip()).strip()
            if termino:
                return termino

    palabras_a_quitar = {"stock", "buscar", "producto", "codigo", "cuanto", "queda", "hay", "de", "del", "el", "la"}
    return " ".join(t for t in norm.split() if t not in palabras_a_quitar)
