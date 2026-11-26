@echo off
chcp 65001 >nul
title BIM DOC MANAGER 7.0 - Acceso desde cualquier red
cd /d "%~dp0"
call "%~dp0INICIAR_INTERNET_VERIFICADO.bat"
