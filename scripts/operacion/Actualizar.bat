@echo off
title Actualizando StockAgent...
set "STOCKAGENT_ROOT=%~dp0"
if not exist "%STOCKAGENT_ROOT%iniciar_en_segundo_plano.vbs" (
    if exist "%~dp0..\..\iniciar_en_segundo_plano.vbs" (
        for %%I in ("%~dp0..\..") do set "STOCKAGENT_ROOT=%%~fI\"
    )
)
cd /d "%STOCKAGENT_ROOT%"
echo Cerrando servidor actual...
call "%STOCKAGENT_ROOT%detener_servidor.bat" >nul 2>&1
echo Descargando ultimas mejoras...
if exist "%STOCKAGENT_ROOT%.venv\Scripts\python.exe" (
    "%STOCKAGENT_ROOT%.venv\Scripts\python.exe" -m src.auto_updater --pre-start --reiniciar
) else (
    git pull --ff-only origin master
)
echo Iniciando servidor actualizado...
start "" "%STOCKAGENT_ROOT%iniciar_en_segundo_plano.vbs" --no-browser --no-auto-update
echo [OK] Sistema actualizado exitosamente.
pause
