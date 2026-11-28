@echo off
chcp 65001 > nul
setlocal
for %%I in ("%~dp0..\..") do set "ROOT_DIR=%%~fI"
cd /d "%ROOT_DIR%"

powershell -NoProfile -Command "Get-Process -Name StockAgent -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

if not exist "Descuentos\Productos.xlsx" call :crear_plantilla

if not exist "Descuentos\Productos.xlsx" (
    echo No se encontro Descuentos\Productos.xlsx.
    echo Coloque el catalogo obligatorio en esa ubicacion antes de compilar.
    exit /b 1
)

set "PYINSTALLER_EXE="
if exist "ttech\Scripts\pyinstaller.exe" (
    set "PYINSTALLER_EXE=%ROOT_DIR%\ttech\Scripts\pyinstaller.exe"
) else if exist ".venv\Scripts\pyinstaller.exe" (
    set "PYINSTALLER_EXE=%ROOT_DIR%\.venv\Scripts\pyinstaller.exe"
) else (
    for /f "delims=" %%P in ('where pyinstaller 2^>nul') do if not defined PYINSTALLER_EXE set "PYINSTALLER_EXE=%%P"
)

set "FLET_EXE="
if exist "ttech\Scripts\flet.exe" (
    set "FLET_EXE=%ROOT_DIR%\ttech\Scripts\flet.exe"
) else if exist ".venv\Scripts\flet.exe" (
    set "FLET_EXE=%ROOT_DIR%\.venv\Scripts\flet.exe"
) else (
    for /f "delims=" %%P in ('where flet 2^>nul') do if not defined FLET_EXE set "FLET_EXE=%%P"
)

if not defined PYINSTALLER_EXE if not defined FLET_EXE (
    echo No se encontro PyInstaller ni Flet. Instale las dependencias de compilacion en .venv.
    exit /b 1
)

set "APP_VERSION=2.0.3"
set "PY_BIN=python"
if exist ".venv\Scripts\python.exe" set "PY_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
for /f "usebackq delims=" %%V in (`"%PY_BIN%" -m src.version 2^>nul`) do set "APP_VERSION=%%V"

if defined PYINSTALLER_EXE if exist "StockAgent.spec" goto :build_spec
goto :build_flet

:build_spec
echo Compilando con PyInstaller - StockAgent.spec...
"%PYINSTALLER_EXE%" StockAgent.spec --distpath dist -y
goto :after_build

:build_flet
echo Compilando con Flet pack - StockAgent v%APP_VERSION%...
"%FLET_EXE%" pack main.py ^
    --name StockAgent ^
    --icon src/img/ultratech.ico ^
    --product-name "Stock Agent" ^
    --product-version "%APP_VERSION%" ^
    --file-description "Agente de control de stock" ^
    --add-data "src/img:src/img" ^
    --add-data "assets:assets" ^
    --distpath dist ^
    --debug-console True ^
    --yes ^
    -- --console --collect-all flet_web --collect-all uvicorn --collect-all fastapi --collect-all starlette --collect-all websockets --collect-all reportlab
goto :after_build

:after_build
if errorlevel 1 (
    echo Error al crear el ejecutable.
    exit /b 1
)

if not exist "dist\Descuentos" mkdir "dist\Descuentos"
copy /Y "Descuentos\Productos.xlsx" "dist\Descuentos\Productos.xlsx" > nul
if errorlevel 1 (
    echo No se pudo copiar el catalogo a la carpeta de distribucion.
    exit /b 1
)
if exist "assets" (
    if not exist "dist\assets" mkdir "dist\assets"
    xcopy /E /I /Y "assets" "dist\assets" > nul
)
if exist "iniciar_servidor_web.bat" copy /Y "iniciar_servidor_web.bat" "dist\iniciar_servidor_web.bat" > nul
if exist "detener_servidor.bat" copy /Y "detener_servidor.bat" "dist\detener_servidor.bat" > nul
if exist "iniciar_en_segundo_plano.vbs" copy /Y "iniciar_en_segundo_plano.vbs" "dist\iniciar_en_segundo_plano.vbs" > nul
if exist "scripts\operacion\instalar_certificado.bat" copy /Y "scripts\operacion\instalar_certificado.bat" "dist\instalar_certificado.bat" > nul
if exist "scripts\operacion\configurar_firewall_red.bat" copy /Y "scripts\operacion\configurar_firewall_red.bat" "dist\configurar_firewall_red.bat" > nul
if exist "scripts\operacion\crear_acceso_directo_cliente.bat" copy /Y "scripts\operacion\crear_acceso_directo_cliente.bat" "dist\crear_acceso_directo_cliente.bat" > nul
if exist "scripts\operacion\configurar_inicio_automatico.bat" copy /Y "scripts\operacion\configurar_inicio_automatico.bat" "dist\configurar_inicio_automatico.bat" > nul
if exist "scripts\operacion\desactivar_inicio_automatico.bat" copy /Y "scripts\operacion\desactivar_inicio_automatico.bat" "dist\desactivar_inicio_automatico.bat" > nul
if exist "Documentacion\*.pdf" (
    if not exist "dist\Documentacion" mkdir "dist\Documentacion"
    copy /Y "Documentacion\*.pdf" "dist\Documentacion\" > nul
)

echo.
echo Ejecutable creado: dist\StockAgent.exe
echo Mantenga Descuentos\Productos.xlsx junto al ejecutable.
exit /b 0

:crear_plantilla
if not exist "Descuentos" mkdir "Descuentos"
echo Creando plantilla base Descuentos\Productos.xlsx...
set "PY_PLANTILLA=python"
if exist ".venv\Scripts\python.exe" set "PY_PLANTILLA=%ROOT_DIR%\.venv\Scripts\python.exe"
"%PY_PLANTILLA%" -c "import openpyxl; wb=openpyxl.Workbook(); ws=wb.active; ws.title='Stock'; ws.append(['CÓDIGO', 'PRODUCTOS', 'STOCK']); wb.save('Descuentos/Productos.xlsx')"
exit /b %errorlevel%
