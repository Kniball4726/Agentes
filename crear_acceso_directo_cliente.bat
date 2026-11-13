@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title StockAgent - Asistente de Acceso Directo para Estaciones Cliente

set "ESQUEMA=https"
for %%A in (%*) do (
    if /i "%%~A"=="--http" set "ESQUEMA=http"
)

echo =====================================================================
echo           STOCKAGENT - CONFIGURADOR DE ACCESO DIRECTO CLIENTE
echo =====================================================================
echo.
echo Este script creara un acceso directo en tu Escritorio para conectarte
echo directamente al servidor central de StockAgent en modo ventana dedicada.
if /i "!ESQUEMA!"=="http" (
    echo [AVISO] Modo HTTP legado activo por parametro --http.
) else (
    echo * Modo seguro: HTTPS por defecto [usa --http solo si el servidor corre sin SSL].
)
echo.

set "DEFAULT_IP=192.168.1.100"
set "DEFAULT_PORT=8550"

set /p SERVER_IP="Ingrese la IP de la PC Servidor [%DEFAULT_IP%]: "
if "!SERVER_IP!"=="" set "SERVER_IP=%DEFAULT_IP%"
set "SERVER_IP=!SERVER_IP:https://=!"
set "SERVER_IP=!SERVER_IP:http://=!"
set "SERVER_IP=!SERVER_IP:/=!"
set "SERVER_IP=!SERVER_IP: =!"

set /p SERVER_PORT="Ingrese el puerto [%DEFAULT_PORT%]: "
if "!SERVER_PORT!"=="" set "SERVER_PORT=%DEFAULT_PORT%"
set "SERVER_PORT=!SERVER_PORT: =!"

set "URL=!ESQUEMA!://!SERVER_IP!:!SERVER_PORT!"

echo.
echo Conectando con: !URL!
echo.

:: Detectar navegador disponible (Edge o Chrome)
set "BROWSER_EXE="
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    set "BROWSER_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    set "BROWSER_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
) else if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "BROWSER_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "BROWSER_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set "BROWSER_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"
)

set "STOCKAGENT_TARGET_URL=!URL!"
set "STOCKAGENT_BROWSER_EXE=!BROWSER_EXE!"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desk = [Environment]::GetFolderPath('Desktop'); if (-not $desk) { $desk = Join-Path $env:USERPROFILE 'Desktop' };" ^
  "$urlPath = Join-Path $desk 'StockAgent.url';" ^
  "@('[InternetShortcut]', ('URL=' + $env:STOCKAGENT_TARGET_URL), 'IconIndex=0') | Set-Content -Path $urlPath -Encoding ASCII;" ^
  "if ($env:STOCKAGENT_BROWSER_EXE) { $ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut((Join-Path $desk 'StockAgent - Deposito.lnk')); $s.TargetPath = $env:STOCKAGENT_BROWSER_EXE; $s.Arguments = '--app=' + $env:STOCKAGENT_TARGET_URL; $s.Description = 'Sistema StockAgent - Control de Deposito'; $s.Save() }"

echo.
echo [OK] Acceso directo creado exitosamente en tu Escritorio:
echo      - "StockAgent.url" [compatible para compartir en cualquier PC de la red]
if defined BROWSER_EXE (
    echo      - "StockAgent - Deposito.lnk" [ventana dedicada usando: !BROWSER_EXE!]
) else (
    echo      [Nota] No se encontro Edge/Chrome para crear el .lnk dedicado; usa StockAgent.url.
)
if /i "!ESQUEMA!"=="https" (
    echo.
    echo [HTTPS] Si en esta PC cliente aparece aviso de certificado autofirmado,
    echo         podes instalar data\certs\stockagent.crt con instalar_certificado.bat
    echo         [ejecutado como Administrador].
)
echo.
echo Ya puedes hacer doble clic sobre el acceso directo para iniciar.
echo =====================================================================
pause
