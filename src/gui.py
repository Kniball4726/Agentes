"""Módulo de compatibilidad para la interfaz gráfica heredada de Tkinter (Obsoleta).

La interfaz gráfica principal es ahora Flet Web/Desktop (src/flet_gui.py)
y la Terminal Móvil nativa en Flutter (stockagent_mobile).
"""

from typing import Any


class InterfazGrafica:
    """Clase stub de compatibilidad para código y pruebas heredadas."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def iniciar(self) -> None:
        print("\n" + "=" * 65)
        print(" [AVISO] La interfaz Tkinter ha sido retirada del sistema.")
        print(" Por favor inicia la aplicación con Flet (Web/Desktop) ejecutando:")
        print("   main.py   (o iniciar_servidor_web.bat / iniciar_servidor_movil.bat)")
        print("=" * 65 + "\n")

    def _mostrar_datos_producto(self) -> tuple:
        return (("nombre", "Nombre del producto"),)
