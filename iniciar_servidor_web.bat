@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
title StockAgent - Servidor Web HTTPS (Multi-Equipo)
cd /d "%~dp0"

echo ==================================================================
echo   STOCK AGENT - SERVIDOR WEB HTTPS (PUERTO 8550)
echo ==================================================================
echo   * Modo: Multi-Equipo (Red Local LAN y Acceso Remoto Seguro)
echo   * Escucha: 0.0.0.0:8550 (Todas las placas de red activas)
echo   * Seguridad: Cifrado TLS / HTTPS con proteccion anti-ataques
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

rem Iniciar la aplicacion utilizando el entorno disponible
rem main.py detecta si ya hay una instancia activa en el puerto 8550
rem y abre el navegador hacia ella sin duplicar procesos

if exist ".venv\Scripts\python.exe" (
    echo [INFO] Iniciando con entorno virtual Python .venv...
    ".venv\Scripts\python.exe" main.py %*
    goto :FIN
)

if exist "StockAgent.exe" (
    echo [INFO] Iniciando ejecutable principal StockAgent.exe...
    "StockAgent.exe" %*
    goto :FIN
)

if exist "ttech\Scripts\python.exe" (
    echo [INFO] Iniciando con entorno Python ttech...
    "ttech\Scripts\python.exe" main.py %*
    goto :FIN
)

where python >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Iniciando con Python del sistema...
    python main.py %*
    goto :FIN
)

if exist "dist\StockAgent.exe" (
    echo [INFO] Iniciando desde dist\StockAgent.exe...
    "dist\StockAgent.exe" %*
    goto :FIN
)

echo [ERROR] No se encontro Python ni el ejecutable StockAgent.exe.
echo Por favor instala Python 3.10+ o activa el entorno virtual .venv.
pause
exit /b 1

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
        echo   El servidor web se ha detenido correctamente.
        echo ==================================================================
        echo.
    )
)
