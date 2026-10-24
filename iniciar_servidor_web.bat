@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo ==================================================================
echo   STOCK AGENT - MODO SERVIDOR WEB EN NAVEGADOR (OPCIÓN 2)
echo ==================================================================
echo.

if exist "StockAgent.exe" (
    echo Iniciando servidor desde StockAgent.exe en el puerto 8550...
    echo Se abrirá automáticamente tu navegador web.
    echo Para conectar la 2da máquina, mira la dirección "Red local: http://..."
    echo en el encabezado del Panel de Control.
    echo.
    start "" "StockAgent.exe" --web --port 8550
) else if exist "dist\StockAgent.exe" (
    echo Iniciando servidor desde dist\StockAgent.exe en el puerto 8550...
    echo Se abrirá automáticamente tu navegador web.
    echo.
    start "" "dist\StockAgent.exe" --web --port 8550
) else if exist "ttech\Scripts\python.exe" (
    "ttech\Scripts\python.exe" main.py --web --port 8550
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py --web --port 8550
) else (
    python main.py --web --port 8550
)
