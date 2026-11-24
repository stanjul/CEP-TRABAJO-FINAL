# CEP — Control Estadístico de Procesos

Aplicación local para el trabajo final de Control Estadístico de Procesos: cartas de control por
variables (X̄-R, X̄-S, I-MR) y atributos (p, np, c, u) en Fase I y Fase II, reglas de Nelson /
Western Electric con alarmas trazables, validación de supuestos, capacidad, diseño ARL/ATS,
muestreo de aceptación y reportes PDF / Excel. Interfaz basada en el diseño exportado de Google Stitch.

## Inicio rápido
- **Usuarios (Windows):** instalar `CEP-Setup-1.0.0.exe`. Programa de escritorio con ventana propia;
  los datos quedan en `C:\Users\<usuario>\CEP` (fuera de OneDrive). Se genera con `construir.bat` (ver
  [INSTALACION.md](docs/INSTALACION.md) §0).
- **Desde el código, Windows:** doble clic en `run.bat` · **Linux / macOS:** `./run.sh`
  (se abre el navegador en `http://127.0.0.1:8000` con datos de demostración cargados).

## Documentación
- [Descripción técnica del software](docs/DESCRIPCION_SOFTWARE.pdf) (PDF; fuente LaTeX en
  `docs/descripcion/`, versión en texto en [DESCRIPCION_SOFTWARE.md](docs/DESCRIPCION_SOFTWARE.md))
- [Instalación y solución de problemas](docs/INSTALACION.md)
- [Manual de usuario](docs/MANUAL_USUARIO.pdf) (PDF detallado con capturas; fuente LaTeX en `docs/manual/`)
- API interactiva: `http://127.0.0.1:8000/docs`
- Convenciones del código: [CLAUDE.md](CLAUDE.md)

## Estructura
```
app/core/      lógica estadística pura (validada con Montgomery)
app/api/       endpoints FastAPI por módulo
app/db/        modelos SQLAlchemy, sesión SQLite y datos de demostración
app/web/       plantillas Jinja2 (derivadas de Stitch), JS por pantalla y recursos locales
app/escritorio.py  programa de escritorio (ventana propia + servidor local)
instalador/    receta de PyInstaller (cep.spec), Inno Setup (cep.iss) e ícono
tests/         pytest
datos_prueba/  CSV/XLSX de ejemplo y script generador
docs/          instalación, manual y capturas
```

## Pruebas
```bash
.venv\Scripts\python.exe -m pytest
```
