@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

if "%1"=="--elevated" goto :EJECUTAR

net session >nul 2>&1
if not errorlevel 1 goto :EJECUTAR

echo [INFO] Solicitando permisos de administrador...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '--elevated' -Verb RunAs" >nul 2>&1
exit /b

:EJECUTAR
echo ==================================================================
echo   CONFIGURACIÓN DE FIREWALL PARA STOCK AGENT (PUERTO 8550)
echo ==================================================================
echo.

echo [1/2] Abriendo puerto TCP 8550 para la App Móvil...
netsh advfirewall firewall delete rule name="StockAgent Web (Puerto 8550)" >nul 2>&1
netsh advfirewall firewall add rule name="StockAgent Web (Puerto 8550)" dir=in action=allow protocol=TCP localport=8550 profile=any >nul 2>&1

echo [2/2] Habilitando permisos para Python...
if exist ".venv\Scripts\python.exe" (
    netsh advfirewall firewall delete rule name="StockAgent Python" >nul 2>&1
    netsh advfirewall firewall add rule name="StockAgent Python" dir=in action=allow program="%~dp0.venv\Scripts\python.exe" profile=any >nul 2>&1
)

echo.
echo ==================================================================
echo   [OK] Firewall de Windows configurado exitosamente!
echo   El puerto 8550 esta abierto para tu celular.
echo ==================================================================
echo.
pause
