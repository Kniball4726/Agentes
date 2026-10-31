@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
title StockAgent - Servidor para App Móvil (HTTP Red Local)
cd /d "%~dp0"

echo ==================================================================
echo   STOCK AGENT - SERVIDOR MÓVIL (MODO HTTP LIMPIO - PUERTO 8550)
echo ==================================================================
echo.

rem 1. Detener instancias previas que puedan estar bloqueando el puerto o en HTTPS
echo [1/3] Liberando puerto 8550...
taskkill /F /IM StockAgent.exe >nul 2>&1
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8550 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -gt 4 } | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo.
echo ==================================================================
echo   >>> DATOS PARA COLOCAR EN TU CELULAR <<<
echo   * Host / IP:   192.168.100.19
echo   * Puerto:      8550
echo   * Protocolo:   HTTP
echo   * (El celular y la PC deben estar en la misma red Wi-Fi)
echo ==================================================================
echo.

echo [2/3] Verificando regla de Firewall de Windows...
netsh advfirewall firewall show rule name="StockAgent Web (Puerto 8550)" >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Si el celular no conecta, ejecuta 'configurar_firewall_red.bat' como Administrador.
    netsh advfirewall firewall add rule name="StockAgent Web (Puerto 8550)" dir=in action=allow protocol=TCP localport=8550 profile=private,domain,public >nul 2>&1
)

echo.
echo [3/3] Iniciando servidor HTTP en 0.0.0.0:8550...
echo   (Mantén esta ventana abierta mientras uses la app móvil)
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py --http %*
    goto :FIN
)

if exist "StockAgent.exe" (
    "StockAgent.exe" --http %*
    goto :FIN
)

python main.py --http %*

:FIN
echo.
pause
