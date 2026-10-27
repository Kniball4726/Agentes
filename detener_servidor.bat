@echo off
chcp 65001 > nul
setlocal

echo ==================================================================
echo   DETENER SERVIDOR STOCK AGENT
echo ==================================================================
echo.

echo Deteniendo servidor y procesos en ejecucion...

taskkill /F /IM StockAgent.exe >nul 2>&1

powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8550 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo.
echo ==================================================================
echo [OK] El servidor ha sido detenido correctamente.
echo ==================================================================
echo.
pause
