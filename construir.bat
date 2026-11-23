@echo off
REM ============================================================
REM  CEP - Construir el programa de escritorio y su instalador
REM  Resultado: instalador\salida\CEP-Setup-<version>.exe
REM  Requisitos: .venv (run.bat la crea) e Inno Setup 6.
REM  La construccion intermedia va a %USERPROFILE%\.cep-construccion: fuera de OneDrive y fuera
REM  de AppData (el Python de la Microsoft Store redirige en silencio lo que se escribe en AppData).
REM ============================================================
setlocal
cd /d "%~dp0"
set "CONSTR=%USERPROFILE%\.cep-construccion"
set "PY=.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo  Falta el entorno virtual. Ejecute primero run.bat.
    exit /b 1
)

set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo  No se encontro Inno Setup 6. Instalelo con: winget install --id JRSoftware.InnoSetup -e
    exit /b 1
)

echo [1/4] Dependencias de construccion ...
"%PY%" -m pip install --disable-pip-version-check -q -r requirements-build.txt || exit /b 1

echo [2/4] Pruebas ...
"%PY%" -m pytest -q -x || (echo  Hay pruebas que fallan: no se construye. & exit /b 1)

echo [3/4] Empaquetando con PyInstaller (puede tardar unos minutos) ...
"%PY%" instalador\crear_icono.py >nul || exit /b 1
"%PY%" -m PyInstaller instalador\cep.spec --noconfirm --clean --log-level WARN --distpath "%CONSTR%\dist" --workpath "%CONSTR%\build" || exit /b 1

echo [4/4] Armando el instalador con Inno Setup ...
"%ISCC%" /Q "/DFuente=%CONSTR%\dist\CEP" instalador\cep.iss || exit /b 1

echo.
echo  Listo: instalador\salida\
dir /b instalador\salida\*.exe
endlocal
