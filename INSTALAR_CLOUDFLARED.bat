@echo off
chcp 65001 >nul
title Instalar Cloudflare Tunnel - BIM DOC MANAGER
cd /d "%~dp0"
echo.
echo Se instalara cloudflared desde los repositorios oficiales de winget.
echo Verifica que tienes Internet y Windows 10/11 con winget disponible.
echo.
where winget >nul 2>nul
if errorlevel 1 (
    echo winget no esta disponible en este computador.
    echo Instala cloudflared desde: https://developers.cloudflare.com/tunnel/downloads/
    pause
    exit /b 1
)
winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
echo.
echo Si se completo la instalacion, cierra y vuelve a abrir la consola.
echo Ejecuta INICIAR_INTERNET.bat para iniciar el acceso remoto.
pause
