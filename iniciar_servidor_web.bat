@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ==================================================================
echo   STOCK AGENT - SERVIDOR WEB HTTPS - PUERTO 8550
echo ==================================================================
echo.

set "MODO_SILENCIOSO=0"
for %%A in (%*) do (
    if /i "%%~A"=="--no-browser" set "MODO_SILENCIOSO=1"
    if /i "%%~A"=="--sin-navegador" set "MODO_SILENCIOSO=1"
    if /i "%%~A"=="--silent" set "MODO_SILENCIOSO=1"
    if /i "%%~A"=="--ocultar-consola" set "MODO_SILENCIOSO=1"
    if /i "%%~A"=="--hide-console" set "MODO_SILENCIOSO=1"
)

rem 1. Verificar si el servidor ya est? activo en el puerto 8550
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8550 -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] El servidor ya se encuentra activo y funcionando en segundo plano.
    echo   -^> En esta PC:   https://127.0.0.1:8550
    echo.
    echo Si deseas reiniciar el servidor, primero ejecuta 'detener_servidor.bat'.
    echo ==================================================================
    echo.
    if "!MODO_SILENCIOSO!"=="0" (
        echo Abriendo navegador en la instancia activa...
        start "" "https://127.0.0.1:8550"
        echo.
        pause
    )
    goto :FIN_OK
)

rem 2. Si no est? activo, iniciar la aplicaci?n
if exist "StockAgent.exe" (
    echo Iniciando desde StockAgent.exe...
    "StockAgent.exe" --web --https --port 8550 %*
    goto :FIN
)

if exist "ttech\Scripts\python.exe" (
    echo Iniciando con Python ttech...
    "ttech\Scripts\python.exe" main.py --web --https --port 8550 %*
    goto :FIN
)

if exist ".venv\Scripts\python.exe" (
    echo Iniciando con Python venv...
    ".venv\Scripts\python.exe" main.py --web --https --port 8550 %*
    goto :FIN
)

if exist "dist\StockAgent.exe" (
    echo Iniciando desde dist\StockAgent.exe...
    "dist\StockAgent.exe" --web --https --port 8550 %*
    goto :FIN
)

echo Iniciando con Python del sistema...
python main.py --web --https --port 8550 %*

:FIN
if errorlevel 1 (
    echo.
    echo ==================================================================
    echo [ERROR] La aplicacion se cerro con error.
    echo Revisa el archivo de log en data\logs\stockagent.log
    echo ==================================================================
    echo.
    pause
) else (
    if "!MODO_SILENCIOSO!"=="0" (
        echo.
        echo ==================================================================
        echo   El servidor se ha detenido.
        echo ==================================================================
        echo.
        pause
    )
)

:FIN_OK
