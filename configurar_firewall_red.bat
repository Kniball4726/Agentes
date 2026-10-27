@echo off
chcp 65001 > nul
setlocal

echo ==================================================================
echo   CONFIGURACI?N DE FIREWALL PARA STOCK AGENT WEB (PUERTO 8550)
echo ==================================================================
echo.
echo Habilitando regla de entrada TCP en el puerto 8550 para permitir
echo que la segunda m?quina se conecte desde el navegador...
echo.

netsh advfirewall firewall delete rule name="StockAgent Web (Puerto 8550)" >nul 2>&1
netsh advfirewall firewall add rule name="StockAgent Web (Puerto 8550)" dir=in action=allow protocol=TCP localport=8550 profile=private,domain,public

if errorlevel 1 (
    echo.
    echo [AVISO] No se pudo crear la regla autom?ticamente.
    echo Haz clic derecho sobre este archivo ^("configurar_firewall_red.bat"^)
    echo y selecciona "Ejecutar como administrador".
) else (
    echo.
    echo [OK] Puerto 8550 habilitado exitosamente en el Firewall de Windows.
    echo Ahora la segunda PC puede entrar desde su navegador a:
    echo http://TU-IP-LOCAL:8550
)
echo.
pause
