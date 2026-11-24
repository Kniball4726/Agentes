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
taskkill /f /im python.exe 2>nul
taskkill /f /im StockAgent.exe 2>nul
echo Descargando ultimas mejoras...
git pull origin master
echo Iniciando servidor actualizado...
start "" "%STOCKAGENT_ROOT%iniciar_en_segundo_plano.vbs" --no-browser
echo [OK] Sistema actualizado exitosamente.
pause
