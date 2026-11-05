@echo off
chcp 65001 >nul
title StockAgent - Desacoplador de Proyecto Móvil Flutter

echo =====================================================================
echo         STOCKAGENT - DESACOPLAMIENTO DE LA APP MOVIL FLUTTER
echo =====================================================================
echo.
echo Este script copia el codigo fuente del cliente movil Flutter hacia
echo una carpeta independiente separada del backend Python (por ejemplo
echo "../StockAgent_Mobile").
echo.

set DESTINO=..\StockAgent_Mobile

set /p DEST_INPUT="Ingrese la ruta de destino [%DESTINO%]: "
if not "%DEST_INPUT%"=="" set DESTINO=%DEST_INPUT%

echo.
echo Copiando archivos hacia "%DESTINO%" (omitiendo temporales y builds)...
echo.

robocopy stockagent_mobile "%DESTINO%" /E /XD .dart_tool build .idea android\.gradle /XF *.apk *.lock

echo.
echo =====================================================================
echo [OK] Desacoplamiento finalizado con exito en: %DESTINO%
echo.
echo Proximos pasos para compilar la aplicacion movil:
echo   1. Abrir terminal en "%DESTINO%"
echo   2. Ejecutar: flutter pub get
echo   3. Ejecutar: flutter build apk --release
echo =====================================================================
pause
