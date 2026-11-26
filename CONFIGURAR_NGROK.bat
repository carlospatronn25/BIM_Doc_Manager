@echo off
chcp 65001 >nul
title BIM DOC MANAGER 7.0 - CONFIGURAR NGROK
cd /d "%~dp0"
echo.
echo ================================================
echo  CONFIGURAR NGROK (solo la primera vez)
echo ================================================
echo.
where ngrok >nul 2>&1
if errorlevel 1 (
  echo Ngrok no esta disponible en el sistema.
  echo Se abrira su pagina de descarga oficial.
  echo Instala ngrok para Windows y luego ejecuta este archivo otra vez.
  start "" "https://ngrok.com/download/windows"
  pause
  exit /b 1
)
echo 1. Crea una cuenta gratuita de ngrok.
echo 2. Abre tu panel en https://dashboard.ngrok.com/get-started/your-authtoken
echo 3. Copia tu authtoken. NO LO COMPARTAS NI LO ENVIES POR CHAT.
echo.
start "" "https://dashboard.ngrok.com/get-started/your-authtoken"
set "BIM_AUTHTOKEN="
set /p "BIM_AUTHTOKEN=Escribe o pega TU authtoken aqui y pulsa Enter: "
if not defined BIM_AUTHTOKEN (
    echo No ingresaste el token.
    pause
    exit /b 1
)
ngrok config add-authtoken "%BIM_AUTHTOKEN%"
if errorlevel 1 (
    set "BIM_AUTHTOKEN="
    echo No se pudo guardar la configuracion de ngrok.
    pause
    exit /b 1
)
set "BIM_AUTHTOKEN="
echo.
echo Ngrok configurado. Ya puedes ejecutar INICIAR_ENLACE_FIJO.bat
pause
