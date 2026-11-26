@echo off
chcp 65001 >nul
title Crear BIM_Doc_Manager.exe
cd /d "%~dp0"
echo Este archivo crea el .exe portable. Solo lo necesita quien COMPILA; quien lo usa no necesita Python.
python -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error
python -m PyInstaller --noconfirm --clean --onefile --windowed --name BIM_Doc_Manager --add-data "catalogos.json;." app.py
if errorlevel 1 goto :error
echo.
echo Listo: dist\BIM_Doc_Manager.exe
pause
exit /b 0
:error
echo Hubo un error. Revisa los mensajes de arriba.
pause
exit /b 1
