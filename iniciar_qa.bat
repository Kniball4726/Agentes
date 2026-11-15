@echo off
title StockAgent - Ambiente QA / Pruebas
chcp 65001 > nul
echo ========================================================
echo   Iniciando StockAgent en Ambiente de QA y Pruebas
echo   (Base de datos aislada data_qa, no altera produccion)
echo ========================================================
echo.

if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe main.py --qa %*
) else (
    python main.py --qa %*
)

pause
