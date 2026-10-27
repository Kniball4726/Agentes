@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo ==================================================================
echo   CONFIGURAR INICIO AUTOMATICO - STOCK AGENT
echo ==================================================================
echo.

set "SCRIPT_VBS=%~dp0iniciar_en_segundo_plano.vbs"
set "CARPETA_TRABAJO=%~dp0"
set "ACCESO_DIRECTO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\StockAgent.lnk"

echo Creando acceso directo en la carpeta de Inicio de Windows...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%ACCESO_DIRECTO%'); $s.TargetPath = '%SCRIPT_VBS%'; $s.WorkingDirectory = '%CARPETA_TRABAJO%'; $s.WindowStyle = 7; $s.Description = 'StockAgent Servidor Web (Segundo Plano)'; $s.Save()"

if exist "%ACCESO_DIRECTO%" (
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
