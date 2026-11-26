@echo off
chcp 65001 >nul
title BIM DOC MANAGER 7.0 - Acceso desde el telefono
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 mobile_web.py
) else (
    python mobile_web.py
)
echo.
echo El servidor se ha detenido. Presiona una tecla para cerrar.
pause >nul
