@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo ==================================================================
echo   STOCK AGENT - SERVIDOR WEB HTTPS - PUERTO 8550
echo ==================================================================
echo.

if exist "StockAgent.exe" (
    echo Iniciando desde StockAgent.exe
    "StockAgent.exe" --web --https --port 8550
    goto :FIN
)

if exist "ttech\Scripts\python.exe" (
    echo Iniciando con Python ttech
    "ttech\Scripts\python.exe" main.py --web --https --port 8550
    goto :FIN
)

if exist ".venv\Scripts\python.exe" (
    echo Iniciando con Python venv
    ".venv\Scripts\python.exe" main.py --web --https --port 8550
    goto :FIN
)

if exist "dist\StockAgent.exe" (
    echo Iniciando desde dist StockAgent.exe
    "dist\StockAgent.exe" --web --https --port 8550
    goto :FIN
)

echo Iniciando con Python del sistema
python main.py --web --https --port 8550

:FIN
if errorlevel 1 (
    echo.
    echo ==================================================================
    echo [ERROR] La aplicacion se cerro con error.
    echo Revisa el archivo de log en data\logs\stockagent.log
    echo ==================================================================
    echo.
    pause
)
