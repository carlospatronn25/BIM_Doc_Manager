@echo off
chcp 65001 >nul
title BIM DOC MANAGER 7.0 - ENLACE FIJO
cd /d "%~dp0"
python iniciar_enlace_fijo.py
if errorlevel 1 (
    echo.
    echo Hubo un error. Revisa los mensajes de arriba.
    pause
)
