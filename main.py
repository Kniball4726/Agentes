"""
Punto de Entrada Principal del Agente de Stock y Remitos.
Al ejecutarse sin argumentos abre la interfaz de Flet en modo Servidor Web (Opción 2)
para permitir conexión desde múltiples máquinas en la red local.
También soporta:
  --desktop          : abre la ventana nativa de escritorio (una sola máquina)
  --port N           : define el puerto del servidor web (por defecto 8550)
  --host IP          : define la interfaz de escucha (por defecto 0.0.0.0)
  --https            : habilita servidor web seguro HTTPS (genera certificado autofirmado si no existe)
  --ssl-cert RUTA    : ruta opcional a certificado X.509 (.crt / .pem)
  --ssl-key RUTA     : ruta opcional a clave privada (.key / .pem)
  --auto             : procesamiento completo automático
  --dry-run          : modo simulación por consola
"""

import os
import sys

# Asegurar que stdout/stderr existan cuando se ejecuta como .exe sin consola (--noconsole)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Importaciones explícitas para que PyInstaller empaquete el servidor web de Flet
try:
    import fastapi  # noqa: F401
    import flet_web  # noqa: F401
    import flet_web.fastapi.serve_fastapi_web_app  # noqa: F401
    import starlette  # noqa: F401
    import uvicorn  # noqa: F401
    import websockets  # noqa: F401
    import reportlab  # noqa: F401
    import reportlab.graphics.barcode.qr  # noqa: F401
except ImportError:
    pass


def _obtener_parametro(flag: str, valor_por_defecto: str) -> str:
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return valor_por_defecto


def main():
    from src.logger_config import configurar_logging

    logger = configurar_logging()

    if "--auto" in sys.argv or "--all" in sys.argv:
        from src.menu import MenuAgente

        menu = MenuAgente()
        logger.info("Iniciando modo automático (--auto)")
        print("[AUTO] Ejecutando procesamiento completo automático...")
        menu.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=False)
    elif "--dry-run" in sys.argv or "--simulacion" in sys.argv:
        from src.menu import MenuAgente

        menu = MenuAgente()
        logger.info("Iniciando modo simulación (--dry-run)")
        print("[SIMULACION] Ejecutando simulación...")
        menu.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=True)
    elif "--tkinter" in sys.argv:
        from src.gui import InterfazGrafica

        InterfazGrafica().iniciar()
    else:
        from src.flet_gui import PUERTO_WEB_DEFAULT, iniciar

        modo_web = "--desktop" not in sys.argv
        host = _obtener_parametro("--host", os.environ.get("STOCKAGENT_HOST", "0.0.0.0"))
        puerto_str = _obtener_parametro(
            "--port", os.environ.get("STOCKAGENT_PORT", str(PUERTO_WEB_DEFAULT))
        )
        try:
            puerto = int(puerto_str)
        except ValueError:
            puerto = PUERTO_WEB_DEFAULT

        usar_https = (
            "--http" not in sys.argv
            and os.environ.get("STOCKAGENT_HTTPS", "1").strip().lower() not in ("0", "false", "no")
        ) or ("--https" in sys.argv)
        ssl_cert = _obtener_parametro("--ssl-cert", os.environ.get("STOCKAGENT_SSL_CERT", ""))
        ssl_key = _obtener_parametro("--ssl-key", os.environ.get("STOCKAGENT_SSL_KEY", ""))

        iniciar(
            modo_web=modo_web,
            host=host,
            port=puerto,
            https=usar_https,
            ssl_certfile=ssl_cert or None,
            ssl_keyfile=ssl_key or None,
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INTERRUMPIDO] Ejecución cancelada por el usuario (Ctrl+C). ¡Hasta luego!\n")
    except Exception as e:
        import logging

        logging.getLogger("stockagent").exception("Error inesperado en ejecución principal: %s", e)
        print(f"\n[ERROR INESPERADO] {e}\n")
        raise
