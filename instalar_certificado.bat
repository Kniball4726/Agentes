@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo ==================================================================
echo   INSTALADOR DE CERTIFICADO SSL - STOCK AGENT
echo ==================================================================
echo.

if not exist "data\certs\stockagent.crt" (
    echo [ERROR] No se encontr? el archivo "data\certs\stockagent.crt".
    echo Inicia primero la aplicaci?n para que se genere autom?ticamente.
    echo.
    pause
    goto :FIN
)

echo Instalando certificado en "Entidades de certificaci?n ra?z de confianza"...
echo.

certutil -addstore -f "ROOT" "data\certs\stockagent.crt"

if errorlevel 1 (
    echo.
    echo [AVISO] Se requieren permisos de Administrador.
    echo Haz clic derecho sobre este archivo ^("instalar_certificado.bat"^)
    echo y selecciona "Ejecutar como administrador".
) else (
    echo.
    echo ==================================================================
    echo [OK] ?Certificado instalado con ?xito!
    echo.
    echo IMPORTANTE: Cierra completamente tu navegador (Chrome, Edge, Brave)
    echo y vuelve a abrirlo para ver el candado seguro sin advertencias.
    echo ==================================================================
)

:FIN
echo.
pause
