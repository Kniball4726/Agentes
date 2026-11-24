@echo off
chcp 65001 > nul
setlocal

echo ==================================================================
echo   DESACTIVAR INICIO AUTOMATICO - STOCK AGENT
echo ==================================================================
echo.

set "ACCESO_DIRECTO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\StockAgent.lnk"

if exist "%ACCESO_DIRECTO%" (
    del "%ACCESO_DIRECTO%"
    echo [EXITO] Se ha quitado StockAgent del inicio automatico de Windows.
) else (
    echo [INFO] No habia ningun inicio automatico configurado para StockAgent.
)

echo.
pause
