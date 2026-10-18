@echo off
chcp 65001 > nul
title Agente de Control de Stock y Remitos
cd /d "%~dp0"
python main.py
pause
