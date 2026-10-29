@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion
title StockAgent - Detener Servidor
cd /d "%~dp0"

echo ==================================================================
echo   DETENER SERVIDOR STOCK AGENT
echo ==================================================================
echo.

echo Deteniendo servidor y procesos en ejecucion...

rem 1. Detener ejecutable compilado si esta en ejecucion
taskkill /F /IM StockAgent.exe >nul 2>&1

rem 2. Detener proceso que este escuchando en el puerto 8550
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8550 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -gt 4 } | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }" >nul 2>&1

rem 3. Detener cualquier instancia residual de Python corriendo main.py de StockAgent
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*main.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo.
echo ==================================================================
echo [OK] El servidor ha sido detenido correctamente.
echo ==================================================================
echo.
timeout /t 2 >nul 2>&1
