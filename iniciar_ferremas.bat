@echo off
setlocal
title FERREMAS - Servidor local

cd /d "%~dp0"

set "FERREMAS_PYTHON=%USERPROFILE%\.virtualenvs\ferremas\Scripts\python.exe"
set "FERREMAS_URL=http://127.0.0.1:8000/"

if not exist "%FERREMAS_PYTHON%" (
    echo No se encontro el entorno virtual de FERREMAS:
    echo %FERREMAS_PYTHON%
    echo.
    pause
    exit /b 1
)

sc.exe query MYSQL80 | findstr /C:"RUNNING" >nul
if errorlevel 1 (
    echo Iniciando MySQL...
    net start MYSQL80 >nul 2>&1
    if errorlevel 1 (
        echo.
        echo No se pudo iniciar MySQL.
        echo Ejecuta este archivo una vez como administrador.
        echo.
        pause
        exit /b 1
    )
)

echo Iniciando FERREMAS en %FERREMAS_URL%
echo Para detener el servidor, cierra esta ventana o presiona Ctrl+C.
echo.

echo Limpiando cuentas de clientes no verificadas y vencidas...
"%FERREMAS_PYTHON%" manage.py limpiar_cuentas_no_verificadas
if errorlevel 1 (
    echo.
    echo No se pudo comprobar la expiracion de cuentas pendientes.
    pause
    exit /b 1
)

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process '%FERREMAS_URL%'"
"%FERREMAS_PYTHON%" manage.py runserver 127.0.0.1:8000

if errorlevel 1 (
    echo.
    echo FERREMAS no pudo iniciarse. Revisa el mensaje anterior.
    pause
)
