"""
Punto de Entrada Principal del Agente de Stock y Remitos.
Al ejecutarse sin argumentos abre el Menú Interactivo.
También soporta modo automático (--auto o --all) y modo simulación (--dry-run).
"""

import sys


def main():
    if "--auto" in sys.argv or "--all" in sys.argv:
        from src.menu import MenuAgente

        menu = MenuAgente()
        print("[AUTO] Ejecutando procesamiento completo automático...")
        menu.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=False)
    elif "--dry-run" in sys.argv or "--simulacion" in sys.argv:
        from src.menu import MenuAgente

        menu = MenuAgente()
        print("[SIMULACION] Ejecutando simulación...")
        menu.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=True)
    else:
        from src.gui import InterfazGrafica

        InterfazGrafica().iniciar()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INTERRUMPIDO] Ejecución cancelada por el usuario (Ctrl+C). ¡Hasta luego!\n")
    except Exception as e:
        print(f"\n[ERROR INESPERADO] {e}\n")
        raise
