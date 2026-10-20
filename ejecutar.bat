@echo off
chcp 65001 > nul
title Agente de Control de Stock y Remitos
cd /d "%~dp0"

set "ROOT=%~dp0"
set "PYTHON_EXE="

if exist "%ROOT%ttech\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%ttech\Scripts\python.exe"
) else if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
)

if defined PYTHON_EXE (
    "%PYTHON_EXE%" main.py --flet
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        py main.py --flet
    ) else (
        where python >nul 2>nul
        if not errorlevel 1 (
            python main.py --flet
        ) else (
            echo No se encontró Python 3.10+ en el sistema.
            echo Instale Python desde https://www.python.org/downloads/windows/ o ejecute:
            echo   py -m pip install -r requirements.txt
            pause
            exit /b 1
        )
    )
)

pause
