@echo off
REM ============================================================
REM  CEP - Control Estadistico de Procesos
REM  Arranque con un solo comando (Windows): doble clic o "run.bat"
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creando entorno virtual .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo  No se encontro Python 3.11 o superior. Instalelo desde https://www.python.org/downloads/
        echo  y marque "Add python.exe to PATH".
        pause
        exit /b 1
    )
)

REM Se reinstalan dependencias solo si requirements.txt cambio desde la ultima instalacion.
fc /b requirements.txt ".venv\requirements.instalado" >nul 2>&1
if errorlevel 1 (
    echo [2/3] Instalando dependencias, puede tardar unos minutos la primera vez ...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt --retries 10 --timeout 60
    if errorlevel 1 (
        echo.
        echo  Error instalando dependencias. Revise la conexion a internet y vuelva a ejecutar run.bat
        pause
        exit /b 1
    )
    copy /y requirements.txt ".venv\requirements.instalado" >nul
)

echo [3/3] Iniciando servidor ...
".venv\Scripts\python.exe" -m app.iniciar %*
pause
