"""Reconocimiento local de intenciones para el chat del agente."""

import re
import unicodedata


_PALABRAS_AYUDA = ("ayuda", "comando", "que puedes hacer", "opciones")
_SALUDOS = {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches"}


def detectar_intencion(mensaje: str) -> str:
    texto = unicodedata.normalize("NFD", mensaje.casefold())
    texto = "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")
    palabras = re.findall(r"[a-z0-9]+", texto)
    normalizado = " ".join(palabras)

    if not normalizado:
        return "desconocido"
    if any(palabra.startswith("simul") for palabra in palabras):
        return "simular"
    if normalizado == "estado" or any(
        palabra in palabras for palabra in ("estado", "pendiente", "pendientes", "archivado", "archivados")
    ):
        return "estado"
    if any(palabra in palabras for palabra in ("informe", "informes", "reporte", "reportes")):
        return "informes"
    if normalizado in _SALUDOS:
        return "saludo"
    if any(frase in normalizado for frase in _PALABRAS_AYUDA):
        return "ayuda"
    return "desconocido"
