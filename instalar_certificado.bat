@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo ==================================================================
echo   INSTALADOR DE CERTIFICADO SSL - STOCK AGENT
echo ==================================================================
echo.

set "CERT_A_INSTALAR="
if exist "data\certs\stockagent_ca.crt" (
    set "CERT_A_INSTALAR=data\certs\stockagent_ca.crt"
) else if exist "data\certs\stockagent.crt" (
    set "CERT_A_INSTALAR=data\certs\stockagent.crt"
)

if "%CERT_A_INSTALAR%"=="" (
    echo [ERROR] No se encontro el archivo "data\certs\stockagent_ca.crt" ni "data\certs\stockagent.crt".
    echo Inicia primero la aplicacion para que se genere automaticamente.
    echo.
    pause
    goto :FIN
)

echo Instalando certificado CA local restringida ^("%CERT_A_INSTALAR%"^) en "Entidades de certificacion raiz de confianza"...
echo.

certutil -addstore -f "ROOT" "%CERT_A_INSTALAR%"

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
