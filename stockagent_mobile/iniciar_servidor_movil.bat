@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
title StockAgent - Servidor para App Movil (HTTP Red Local)
cd /d "%~dp0.."

rem ------------------------------------------------------------------
rem Analizar parametros recibidos
rem ------------------------------------------------------------------
set "MODO_SILENCIOSO=0"
set "FORZAR_CONSOLA=0"

for %%A in (%*) do (
    if /i "%%~A"=="--consola" set "FORZAR_CONSOLA=1"
    if /i "%%~A"=="--console" set "FORZAR_CONSOLA=1"
    if /i "%%~A"=="--debug" set "FORZAR_CONSOLA=1"
    if /i "%%~A"=="--no-browser" set "MODO_SILENCIOSO=1"
    if /i "%%~A"=="--sin-navegador" set "MODO_SILENCIOSO=1"
    if /i "%%~A"=="--silent" set "MODO_SILENCIOSO=1"
    if /i "%%~A"=="--ocultar-consola" set "MODO_SILENCIOSO=1"
    if /i "%%~A"=="--hide-console" set "MODO_SILENCIOSO=1"
)

rem Si se ejecuta directamente sin argumentos y no se forzo consola,
rem lanzar de forma 100% invisible a traves del script VBS en segundo plano.
if "%~1"=="" if "!FORZAR_CONSOLA!"=="0" (
    if exist "%~dp0iniciar_servidor_movil_en_segundo_plano.vbs" (
        start "" wscript.exe //nologo "%~dp0iniciar_servidor_movil_en_segundo_plano.vbs"
        exit /b 0
    )
)

if "!MODO_SILENCIOSO!"=="0" (
    echo ==================================================================
    echo   STOCK AGENT - SERVIDOR MOVIL (MODO HTTP LIMPIO - PUERTO 8550)
    echo ==================================================================
    echo   * Modo: App Movil (HTTP Red Local LAN sin errores SSL)
    echo   * Escucha: 0.0.0.0:8550 (Todas las placas de red activas)
    echo ==================================================================
    echo.
    echo [1/2] Liberando puerto 8550 de instancias previas...
)

rem 1. Liberar puerto 8550 de instancias previas (StockAgent.exe o Python)
taskkill /F /IM StockAgent.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r ":8550 .*LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

if "!MODO_SILENCIOSO!"=="0" (
    echo [2/2] Iniciando servidor para conexion movil...
    echo.
)

rem 2. Iniciar servidor con entorno disponible
set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "ttech\Scripts\python.exe" set "PYTHON_EXE=ttech\Scripts\python.exe"

if defined PYTHON_EXE (
    if "!MODO_SILENCIOSO!"=="1" (
        "%PYTHON_EXE%" main.py --http --force --ocultar-consola --no-browser %*
    ) else (
        "%PYTHON_EXE%" main.py --http --force %*
    )
    goto :FIN
)

if exist "StockAgent.exe" (
    if "!MODO_SILENCIOSO!"=="1" (
        "StockAgent.exe" --http --force --ocultar-consola --no-browser %*
    ) else (
        "StockAgent.exe" --http --force %*
    )
    goto :FIN
)

where python >nul 2>&1
if not errorlevel 1 (
    if "!MODO_SILENCIOSO!"=="1" (
        python main.py --http --force --ocultar-consola --no-browser %*
    ) else (
        python main.py --http --force %*
    )
    goto :FIN
)

if exist "dist\StockAgent.exe" (
    if "!MODO_SILENCIOSO!"=="1" (
        "dist\StockAgent.exe" --http --force --ocultar-consola --no-browser %*
    ) else (
        "dist\StockAgent.exe" --http --force %*
    )
    goto :FIN
)

if "!MODO_SILENCIOSO!"=="0" (
    echo [ERROR] No se encontro Python ni el ejecutable StockAgent.exe.
    echo Por favor instala Python 3.10+ o activa el entorno virtual .venv.
    pause
)
exit /b 1

:FIN
if errorlevel 1 (
    if "!MODO_SILENCIOSO!"=="0" (
        echo.
        echo ==================================================================
        echo [ERROR] El servidor movil se cerro con error.
        echo Revisa el archivo de log en data\logs\stockagent.log
        echo ==================================================================
        echo.
        pause
    )
) else (
    if "!MODO_SILENCIOSO!"=="0" (
        echo.
        echo ==================================================================
        echo   El servidor movil se ha detenido correctamente.
        echo ==================================================================
        echo.
        pause
    )
)
