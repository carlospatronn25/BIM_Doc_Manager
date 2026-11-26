@echo off
chcp 65001 >nul
title BIM DOC MANAGER 7.0 - CAMBIAR CLAVE DE ENLACE
cd /d "%~dp0"
echo ADVERTENCIA: al reiniciar el programa, el enlace anterior dejara de funcionar.
echo Si estas usando actualmente el servidor, cierralo antes de continuar.
choice /c SN /m "Quieres cambiar la clave del enlace"
if errorlevel 2 exit /b 0
python iniciar_enlace_fijo.py --rotar-clave
pause
