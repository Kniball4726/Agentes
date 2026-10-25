@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo ==================================================================
echo   STOCK AGENT - MODO SERVIDOR WEB SEGURO HTTPS (OPCION 2)
echo ==================================================================
echo.

taskkill /F /IM StockAgent.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /R /C:":8550 " ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

if exist "StockAgent.exe" (
    echo Iniciando servidor HTTPS desde StockAgent.exe en el puerto 8550...
    echo Se abrira automaticamente tu navegador web en https://127.0.0.1:8550
    echo Para conectar la 2da maquina, mira la direccion "Red local: https://..."
    echo en el encabezado del Panel de Control.
    echo.
    start "" "StockAgent.exe" --web --https --port 8550
) else if exist "ttech\Scripts\python.exe" (
    echo Iniciando servidor HTTPS con Python (ttech) en el puerto 8550...
    "ttech\Scripts\python.exe" main.py --web --https --port 8550
) else if exist ".venv\Scripts\python.exe" (
    echo Iniciando servidor HTTPS con Python (.venv) en el puerto 8550...
    ".venv\Scripts\python.exe" main.py --web --https --port 8550
) else if exist "dist\StockAgent.exe" (
    echo Iniciando servidor HTTPS desde dist\StockAgent.exe en el puerto 8550...
    echo Se abrira automaticamente tu navegador web en https://127.0.0.1:8550
    echo.
    start "" "dist\StockAgent.exe" --web --https --port 8550
) else (
    python main.py --web --https --port 8550
)
