"""
Punto de Entrada Principal del Agente de Stock y Remitos.
Al ejecutarse sin argumentos abre el Menú Interactivo.
También soporta modo automático (--auto o --all) y modo simulación (--dry-run).
"""

import sys
from menu import MenuAgente


def main():
    menu = MenuAgente()

    if "--auto" in sys.argv or "--all" in sys.argv:
        print("[AUTO] Ejecutando procesamiento completo automático...")
        menu.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=False)
    elif "--dry-run" in sys.argv or "--simulacion" in sys.argv:
        print("[SIMULACION] Ejecutando simulación...")
        menu.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=True)
    else:
        # Por defecto abre el panel de control interactivo
        menu.iniciar()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INTERRUMPIDO] Ejecución cancelada por el usuario (Ctrl+C). ¡Hasta luego!\n")
    except Exception as e:
        print(f"\n[ERROR INESPERADO] {e}\n")
        raise
