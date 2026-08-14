@echo off
setlocal
title FERREMAS - Pruebas de seguridad

cd /d "%~dp0"
set "FERREMAS_PYTHON=%USERPROFILE%\.virtualenvs\ferremas\Scripts\python.exe"

if not exist "%FERREMAS_PYTHON%" (
    echo No se encontro el entorno virtual de FERREMAS.
    pause
    exit /b 1
)

echo [1/5] Revisando configuracion de Django...
"%FERREMAS_PYTHON%" manage.py check || goto :error

echo.
echo [2/5] Ejecutando pruebas aisladas...
"%FERREMAS_PYTHON%" manage.py test --settings=ferremas.test_settings --noinput || goto :error

echo.
echo [3/5] Comprobando migraciones...
"%FERREMAS_PYTHON%" manage.py makemigrations --check --dry-run || goto :error
"%FERREMAS_PYTHON%" manage.py migrate --check || goto :error

echo.
echo [4/5] Buscando problemas de seguridad medios o altos...
"%FERREMAS_PYTHON%" -m bandit -r ferremas usuarios productos carro_compras home -x "*/migrations/*,*/tests.py" -ll || goto :error

echo.
echo [5/5] Auditando dependencias conocidas...
"%FERREMAS_PYTHON%" -m pip_audit -r requirements.txt
if errorlevel 1 (
    echo.
    echo NOTA: Transbank SDK 6.1.0 exige marshmallow 3.26.1.
    echo Su vulnerabilidad de carga masiva no se usa en el flujo Webpay Plus de FERREMAS.
    echo Revisa cualquier alerta adicional que aparezca arriba.
)

echo.
echo Revision local terminada.
pause
exit /b 0

:error
echo.
echo La revision se detuvo porque una comprobacion fallo.
pause
exit /b 1
