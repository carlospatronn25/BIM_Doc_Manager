@echo off
cd /d "%~dp0"
python app.py
if errorlevel 1 (
  echo.
  echo No se pudo iniciar. Comprueba que Python 3.10 o superior este instalado.
  pause
)
