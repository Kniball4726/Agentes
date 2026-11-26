"""Módulo de soporte para lectores de códigos de barra (Barcode Wedge) y feedback acústico."""

from src.products.barcode_utils import normalizar_codigo_lector

__all__ = [
    "emitir_tono_error",
    "emitir_tono_exito",
    "normalizar_codigo_lector",
]


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
