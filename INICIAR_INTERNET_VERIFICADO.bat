@echo off
setlocal EnableExtensions
chcp 65001 >nul
title BIM DOC MANAGER 7.0 - ACCESO POR ENLACE SIN CORREO
cd /d "%~dp0"
echo.
echo ================================================================
echo  BIM DOC MANAGER 7.0 - ACCESO SIN CORREO
echo ================================================================
echo Carpeta del programa:
echo %~dp0
echo.
if not exist "%~dp0iniciar_internet.py" (
    echo ERROR: Falta iniciar_internet.py en esta carpeta.
    echo Descomprime el ZIP actualizado en una carpeta NUEVA.
    goto :error
)
findstr /C:"ACCESO REMOTO POR ENLACE" "%~dp0iniciar_internet.py" >nul 2>nul
if errorlevel 1 (
    echo ERROR: Este iniciar_internet.py pertenece a otra version.
    echo Descomprime el ZIP completo en una carpeta NUEVA.
    goto :error
)
echo Preparando enlace temporal HTTPS. No se necesita correo.
echo.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0iniciar_internet.py"
) else (
    python "%~dp0iniciar_internet.py"
)
set "exit_code=%errorlevel%"
echo.
echo El acceso se ha detenido o no pudo iniciar.
pause
exit /b %exit_code%
:error
echo.
pause
exit /b 1
