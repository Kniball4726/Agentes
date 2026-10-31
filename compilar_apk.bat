@echo off
chcp 65001 > nul
setlocal
title Compilar APK - StockAgent Movil
cd /d "%~dp0stockagent_mobile"

echo ==================================================================
echo   COMPILADOR DE APK PARA ANDROID - STOCK AGENT MOVIL (FLUTTER)
echo ==================================================================
echo.

rem Asegurar JAVA_HOME si esta instalado Eclipse Adoptium JDK 17
if exist "C:\Program Files\Eclipse Adoptium\jdk-17.0.14.7-hotspot" (
    set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-17.0.14.7-hotspot"
)

rem 1. Verificar si Flutter esta en el PATH
set "FLUTTER_CMD=flutter"
where flutter >nul 2>&1
if not errorlevel 1 goto :COMPILAR

rem 2. Buscar Flutter en rutas comunes de Windows
if exist "C:\flutter\bin\flutter.bat" (
    set "FLUTTER_CMD=C:\flutter\bin\flutter.bat"
    goto :COMPILAR
)
if exist "C:\src\flutter\bin\flutter.bat" (
    set "FLUTTER_CMD=C:\src\flutter\bin\flutter.bat"
    goto :COMPILAR
)
if exist "%LOCALAPPDATA%\flutter\bin\flutter.bat" (
    set "FLUTTER_CMD=%LOCALAPPDATA%\flutter\bin\flutter.bat"
    goto :COMPILAR
)
if exist "%USERPROFILE%\flutter\bin\flutter.bat" (
    set "FLUTTER_CMD=%USERPROFILE%\flutter\bin\flutter.bat"
    goto :COMPILAR
)

echo [AVISO] No se encontro Flutter instalado en el sistema.
echo.
echo Para generar el archivo APK necesitas tener instalado Flutter SDK en tu PC:
echo 1. Descargalo gratis desde: https://docs.flutter.dev/get-started/install/windows/mobile
echo 2. Descomprimelo en C:\flutter
echo 3. Vuelve a hacer doble clic en este archivo "compilar_apk.bat".
echo.
echo (Nota: El codigo fuente del proyecto movil ya esta 100%% listo en 'stockagent_mobile')
echo.
pause
goto :EOF

:COMPILAR
rem Detener daemons de Gradle previos para liberar memoria RAM
if exist "android\gradlew.bat" (
    call "android\gradlew.bat" --stop >nul 2>&1
)

echo [1/3] Verificando dependencias de Flutter...
call "%FLUTTER_CMD%" pub get
if errorlevel 1 (
    echo [ERROR] Fallo la descarga de paquetes de Flutter.
    pause
    goto :EOF
)

echo.
echo [2/3] Compilando APK Release para Android...
call "%FLUTTER_CMD%" build apk --release --android-skip-build-dependency-validation
if errorlevel 1 (
    echo [ERROR] Hubo un error durante la compilacion del APK.
    pause
    goto :EOF
)

echo.
echo [3/3] Organizando instalador final...
set "DESTINO=%~dp0dist_movil"
if not exist "%DESTINO%" mkdir "%DESTINO%"

copy /y "build\app\outputs\flutter-apk\app-release.apk" "%DESTINO%\StockAgent.apk" >nul

echo ==================================================================
echo   COMPILACION EXITOSA!
echo ==================================================================
echo   El archivo instalador esta listo en:
echo   %DESTINO%\StockAgent.apk
echo.
echo   Pasos para instalarlo en tu telefono Android:
echo   1. Pasa "StockAgent.apk" a tu celular (WhatsApp, cable USB o Google Drive).
echo   2. Tocalo en tu telefono e instalalo.
echo   3. En tu PC, inicia "iniciar_servidor_movil.bat".
echo   4. Abre la app en el telefono, coloca la IP de tu PC y listo!
echo ==================================================================
echo.

explorer "%DESTINO%"
pause
