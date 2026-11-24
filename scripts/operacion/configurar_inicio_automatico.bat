@echo off
chcp 65001 > nul
setlocal
set "STOCKAGENT_ROOT=%~dp0"
if not exist "%STOCKAGENT_ROOT%iniciar_en_segundo_plano.vbs" (
    if exist "%~dp0..\..\iniciar_en_segundo_plano.vbs" (
        for %%I in ("%~dp0..\..") do set "STOCKAGENT_ROOT=%%~fI\"
    )
)
cd /d "%STOCKAGENT_ROOT%"

echo ==================================================================
echo   CONFIGURAR INICIO AUTOMATICO - STOCK AGENT
echo ==================================================================
echo.

set "STOCKAGENT_SCRIPT_VBS=%STOCKAGENT_ROOT%iniciar_en_segundo_plano.vbs"
set "STOCKAGENT_CARPETA_TRABAJO=%STOCKAGENT_ROOT%"
set "STOCKAGENT_ACCESO_DIRECTO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\StockAgent.lnk"

echo Creando acceso directo en la carpeta de Inicio de Windows...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut($env:STOCKAGENT_ACCESO_DIRECTO); $s.TargetPath = $env:STOCKAGENT_SCRIPT_VBS; $s.Arguments = '--no-browser'; $s.WorkingDirectory = $env:STOCKAGENT_CARPETA_TRABAJO; $s.WindowStyle = 7; $s.Description = 'StockAgent Servidor Web (Segundo Plano)'; $s.Save()"

if exist "%STOCKAGENT_ACCESO_DIRECTO%" (
    echo.
    echo ==================================================================
    echo [EXITO] Inicio automatico activado correctamente.
    echo Cada vez que inicies sesion en Windows, el servidor web de
    echo StockAgent se iniciara de forma automatica y en segundo plano.
    echo ==================================================================
) else (
    echo.
    echo [ERROR] No se pudo crear el acceso directo en Inicio.
)

echo.
pause
