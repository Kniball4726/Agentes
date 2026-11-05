@echo off
chcp 65001 >nul
title StockAgent - Asistente de Acceso Directo para Estaciones Cliente

echo =====================================================================
echo           STOCKAGENT - CONFIGURADOR DE ACCESO DIRECTO CLIENTE
echo =====================================================================
echo.
echo Este script creara un acceso directo en tu Escritorio para conectarte
echo directamente al servidor central de StockAgent en modo ventana dedicada.
echo.

set DEFAULT_IP=192.168.1.100
set DEFAULT_PORT=8550

set /p SERVER_IP="Ingrese la IP de la PC Servidor [%DEFAULT_IP%]: "
if "%SERVER_IP%"=="" set SERVER_IP=%DEFAULT_IP%

set /p SERVER_PORT="Ingrese el puerto [%DEFAULT_PORT%]: "
if "%SERVER_PORT%"=="" set SERVER_PORT=%DEFAULT_PORT%

set URL=http://%SERVER_IP%:%SERVER_PORT%

echo.
echo Conectando con: %URL%
echo.

:: Detectar navegador disponible (Edge o Chrome)
set BROWSER_CMD=""
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    set BROWSER_CMD="%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app="%URL%"
) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    set BROWSER_CMD="%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app="%URL%"
) else if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set BROWSER_CMD="%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app="%URL%"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set BROWSER_CMD="%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --app="%URL%"
)

set DESKTOP_DIR=%USERPROFILE%\Desktop
set SHORTCUT_PATH=%DESKTOP_DIR%\StockAgent.url

echo [InternetShortcut] > "%SHORTCUT_PATH%"
echo URL=%URL% >> "%SHORTCUT_PATH%"
echo IconIndex=0 >> "%SHORTCUT_PATH%"

:: Si encontramos Edge o Chrome, crear acceso directo .lnk mediante PowerShell
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP_DIR%\StockAgent - Deposito.lnk'); $s.TargetPath = 'msedge.exe'; $s.Arguments = '--app=%URL%'; $s.Description = 'Sistema StockAgent - Control de Deposito'; $s.Save()" 2>nul

echo.
echo [OK] Acceso directo creado exitosamente en tu Escritorio:
echo      - "StockAgent - Deposito.lnk"
echo.
echo Ya puedes hacer doble clic sobre el acceso directo para iniciar.
echo =====================================================================
pause
