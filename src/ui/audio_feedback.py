"""Módulo de soporte para lectores de códigos de barra (Barcode Wedge) y feedback acústico."""

import re


def normalizar_codigo_lector(raw: str) -> str:
    """Limpia y normaliza la lectura de pistolas lectoras y colectores industriales.
    
    Elimina caracteres de control (CR, LF, TAB), espacios residuales y prefijos
    estándar AIM Symbology Identifier (ej. ']C1', ']e0', ']E0') que envían algunos
    lectores industriales configurados en modo teclado.
    """
    if not raw:
        return ""
    
    texto = str(raw).strip()
    # Eliminar prefijos estándar AIM (']' seguido de letra y dígito)
    texto = re.sub(r"^\][A-Za-z][0-9]", "", texto)
    # Eliminar caracteres ASCII de control no imprimibles (0x00 a 0x1F y 0x7F)
    texto = "".join(ch for ch in texto if 32 <= ord(ch) <= 126 or ord(ch) > 127)
    return texto.strip()


def emitir_tono_exito() -> None:
    """Emite un tono acústico agudo de confirmación (1046 Hz / C6)."""
    try:
        import winsound
        winsound.Beep(1046, 85)
    except Exception:
        pass


def emitir_tono_error() -> None:
    """Emite un tono acústico grave de advertencia (260 Hz / C4 bajo)."""
    try:
        import winsound
        winsound.Beep(260, 200)
    except Exception:
        pass
