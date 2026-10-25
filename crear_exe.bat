@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

taskkill /F /IM StockAgent.exe >nul 2>&1

if not exist "Descuentos\Productos.xlsx" (
    echo No se encontro Descuentos\Productos.xlsx.
    echo Coloque el catalogo obligatorio en esa ubicacion antes de compilar.
    exit /b 1
)

set "FLET_EXE="
if exist "ttech\Scripts\python.exe" (
    set "FLET_EXE=%~dp0ttech\Scripts\flet.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "FLET_EXE=%~dp0.venv\Scripts\flet.exe"
) else (
    for /f "delims=" %%P in ('where flet 2^>nul') do if not defined FLET_EXE set "FLET_EXE=%%P"
)

if not defined FLET_EXE (
    echo No se encontro Flet. Instale las dependencias de compilacion en .venv.
    exit /b 1
)

"%FLET_EXE%" pack main.py ^
    --name StockAgent ^
    --icon src/img/ultratech.ico ^
    --product-name "Stock Agent" ^
    --file-description "Agente de control de stock" ^
    --add-data "src/img:src/img" ^
    --add-data "assets:assets" ^
    --distpath dist ^
    --yes ^
    -- --collect-all flet_web --collect-all uvicorn --collect-all fastapi --collect-all starlette --collect-all websockets --collect-all reportlab
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
if exist "configurar_firewall_red.bat" copy /Y "configurar_firewall_red.bat" "dist\configurar_firewall_red.bat" > nul

echo.
echo Ejecutable creado: dist\StockAgent.exe
echo Mantenga Descuentos\Productos.xlsx junto al ejecutable.
