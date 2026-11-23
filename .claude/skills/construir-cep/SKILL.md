---
name: construir-cep
description: Construir y verificar el programa de escritorio de CEP (CEP.exe con PyInstaller) y su instalador CEP-Setup-<versión>.exe (Inno Setup). Usar cuando se pida generar, actualizar o probar el instalador, cambiar la versión, o cuando se agreguen archivos que la app lee de disco.
---

# Construir el programa de escritorio y el instalador de CEP

## Comando
```powershell
$b = (Resolve-Path construir.bat).Path; cmd /c "`"$b`""
```
Hace: `requirements-build.txt` (PyInstaller + pywebview) → `pytest -x` → PyInstaller
(`instalador/cep.spec`) → Inno Setup (`instalador/cep.iss`). Salida:
`instalador/salida/CEP-Setup-<versión>.exe` (~70 MB). Tarda ~6 min (PyInstaller ~3–4 min).

## Trampas conocidas (no repetirlas)
- **Nunca construir en AppData.** El Python del proyecto es de la Microsoft Store: todo lo que
  escribe en `%LOCALAPPDATA%` va en silencio a `AppData\Local\Packages\PythonSoftwareFoundation…\LocalCache`.
  La construcción intermedia va a `%USERPROFILE%\.cep-construccion`.
- `cep.iss` debe guardarse en **UTF-8 con BOM** (si no, Inno Setup rompe las tildes).
- `construir.bat` debe tener saltos de línea **CRLF**; llamarlo con ruta completa desde PowerShell.
- Archivos que la app lee de disco (plantillas, estáticos, `app/core/plantillas`, CSV de la
  demostración) deben estar en `datas` de `cep.spec` con la **misma ruta relativa**.
- sqlite3 en Windows: cerrar conexiones con `contextlib.closing` (el `with` no cierra).

## Cambiar la versión
Actualizar en los tres lugares: `#define Version` en `instalador/cep.iss`, `VERSION` en
`app/api/sistema.py` y el nombre del instalador en `docs/INSTALACION.md` / `README.md`.

## Verificación (después de construir)
1. **Programa empaquetado, sin ventana** (datos en carpeta temporal):
   ```powershell
   $env:CEP_DATOS = "<carpeta temporal>"
   $p = Start-Process "$env:USERPROFILE\.cep-construccion\dist\CEP\CEP.exe" -ArgumentList "--sin-ventana","--puerto","8791" -PassThru
   # esperar /api/salud (primera vez hasta ~50 s; luego ~10 s) y probar:
   #   /operario, /ingenieria/plantilla, /static/js/comun.js            → 200
   #   POST /api/sistema/demo                                           → 201
   #   POST /api/reportes/generar {variable_id:3, formato:"pdf"}        → motor "latex" (si hay MiKTeX)
   #   POST /api/plantillas/generar {proceso_id:1, variables:[{id:1,fase_ii:5}]} → .xlsx
   Stop-Process -Id $p.Id -Force; $env:CEP_DATOS = $null
   ```
2. **Instalador** (silencioso, por usuario) y desinstalación:
   `CEP-Setup-<v>.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /TASKS=""` → queda en
   `%LOCALAPPDATA%\Programs\CEP`; desinstalar con el `UninstallString` de
   `HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall` + `/VERYSILENT`. Comprobar que la
   carpeta de datos **no** se borra.
3. **Ventana real** (opcional): `python -m app.escritorio`. Para inspeccionarla sin capturar la
   pantalla del usuario, usar `PrintWindow` sobre la ventana del proceso. Para manejarla por CDP:
   `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=<puerto>`. Una descarga debe abrir
   el diálogo «Guardar como» con el nombre del archivo.

Al terminar: correr `pytest`, actualizar `HANDOFF.md` y hacer commit (los binarios no se versionan:
`instalador/salida/`, `build/`, `dist/` están en `.gitignore`).
