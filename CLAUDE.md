# CEP — Control Estadístico de Procesos (trabajo final)

App local (FastAPI + SQLite + Jinja2/JS vanilla + Plotly.js) que implementa el diseño exportado
de Google Stitch (`Stitch/stitch_industrial_spc_suite/`). `Programa/` es un proyecto anterior
(Vite/Preact): **no modificarlo**.

## Comandos
- Entorno: `.venv\Scripts\python.exe` (Python 3.11). Dependencias en `requirements.txt`.
- Tests: `.venv\Scripts\python.exe -m pytest`
- Demo del core en consola: `.venv\Scripts\python.exe datos_prueba\demo_core.py`
- Regenerar datos de prueba: `.venv\Scripts\python.exe datos_prueba\generar_datos.py`
- App: `run.bat` (Windows) / `run.sh`. Opciones: `--puerto 8001`, `--sin-navegador`, `--reiniciar`
  (borra `data/cep.db` y vuelve a sembrar los datos de demostración).
- API interactiva: http://127.0.0.1:8000/docs
- Git: repositorio en la raíz (rama `main`). Si `git` no está en el PATH de la terminal, usar
  `"C:\Program Files\Git\cmd\git.exe"`. Commit al cerrar cada fase. `Programa/` está en `.gitignore`.
- Desarrollo con recarga: `.venv\Scripts\python.exe -m uvicorn app.main:app --reload`

## Arquitectura y reglas de dependencia
- `app/core/` — estadística pura. **Prohibido** importar FastAPI, SQLAlchemy o cualquier cosa de
  `app/api`, `app/db`, `app/web`. Entradas: listas/arrays; salidas: `dict` serializables a JSON.
- `app/api/` — un router FastAPI por módulo (prefijo `/api`); `servicios.py` combina BD + core.
  Los routers no contienen fórmulas. Respuestas con `JSONSeguro` (NaN → null, numpy → Python).
- `app/db/` — modelos SQLAlchemy 2.0, sesión (SQLite en `data/cep.db`, o `CEP_DB_URL`) y
  `semilla.py` (datos de demostración si la base está vacía).
- `app/ejemplos_montgomery.py` — datasets del libro (semilla y tests).
- Trazabilidad: todo cambio de configuración, exclusión, congelamiento o importación pasa por
  `servicios.registrar_cambio` (versión + SHA-256 de la configuración). No hay login: el nombre
  del usuario llega en el campo `usuario` del cuerpo.
- Fases: los subgrupos guardan su fase (`I`, `II`, `archivo`). Cambios estructurales (tipo de
  carta, n, k, estimador σ) solo en Fase I.
- `app/web/` — plantillas Jinja2 derivadas de Stitch + JS vanilla por pantalla + `static/vendor/`
  (Tailwind, Plotly, fuentes: todo local, la app debe funcionar sin internet).

## Convenciones de código
- Idioma: identificadores, docstrings, comentarios y mensajes **en español** (sin ñ ni tildes en
  identificadores: `tamano`, `diseno`).
- Toda función pública lleva docstring que explica **la fórmula** que implementa.
- Índices de subgrupo en el core: base 0. En la interfaz y en los textos: base 1 (o las
  `etiquetas` reales del subgrupo).
- Reglas de control: ids `N1`–`N8` (Nelson) y `WE4`; presets en `app/core/reglas.py`.
  Las cartas de dispersión (R, S, MR) solo evalúan `N1`.
- Resultados de cartas: forma común `{tipo, fase, cartas{clave:{valores, lc, lcs, lci, sigma,
  violaciones}}, excluidos, puntos_con_senal, limites}`. `limites` es lo que se congela para la
  Fase II y se vuelve a pasar como `limites=`.
- Límites variables (p, u, X̄-S con n variable) se devuelven como listas; constantes como escalar.

## Tests
- Cada módulo de `app/core` tiene su `tests/test_<modulo>.py`.
- Los valores esperados de Montgomery (*Introduction to SQC*) están en `tests/datos_montgomery.py`
  con el tema del ejemplo. Cuando el libro redondea valores intermedios, el test lo documenta y
  verifica ambas cosas (valor exacto con tolerancia + reproducción del redondeo del libro).
- No relajar una tolerancia sin dejar el motivo en un comentario.

## Frontend (Fase 3)
- `app/web/rutas.py` registra las pantallas (tabla `PANTALLAS`). Cada pantalla = `templates/<id>.html`
  (extiende `base.html`) + `static/js/<id>.js`. Sin build: Tailwind Play CDN local + `tailwind-config.js`
  (colores, espaciado y bordes de Stitch; tipografía propia, ver «Diseño»).
- `static/js/comun.js` expone `CEP` (api, arrancar, fmt, modal, toast, usuario, contexto). Cada pantalla
  llama `CEP.arrancar(iniciar)`; la variable activa viaja en `?v=<id>` y en localStorage.
- `static/js/graficos.js` expone `GRAF` (cartaControl, histograma, qq, acf, curvas, barras) con la paleta
  del diseño. Ejes de categorías: las x se pasan como texto.
- `carta_ing.js` sirve a Variables y Atributos (detecta `body[data-pagina]`).
- Recursos externos prohibidos en runtime: si se agrega una librería, descargarla con
  `python -m app.web.descargar_vendor` (o similar) a `static/vendor/`.
- Inputs con `border-outline-variant` reciben borde desde `estilos.css` (no hay plugin de forms).
- Verificación visual: Edge headless `--screenshot` sobre el servidor local.

## Reportes (Fase 4, rehecha en la Fase E del rediseño)
- **PDF principal con LaTeX:** `app/core/reporte_latex.py` + plantilla `app/core/plantillas/reporte.tex`
  (Jinja2 con delimitadores `<% %>`, `<< >>`, `<# #>`; no escribirlos en comentarios de la plantilla).
  `pdflatex` dos pasadas, fuente predeterminada (Latin Modern), `--disable-installer` en MiKTeX.
  Todo texto pasa por `esc()`. El informe **solo describe** (sin recomendaciones) y está escrito
  para no expertos. Figuras simples: `figuras.carta_simple` / `histograma_simple`.
- Si no hay LaTeX o falla (`ErrorLatex`), la API usa `reportes.construir_pdf` (reportlab) como
  respaldo y devuelve `motor`/`aviso`. `CEP_SIN_LATEX=1` fuerza el respaldo (tests).
- PDF de respaldo y Excel usan `api.reportes.conclusiones_descriptivas` (mismos textos que LaTeX).
- `app/core/reportes.py`: `construir_pdf` (reportlab, fuente DejaVu de matplotlib para σ/≥/Δ) y
  `construir_excel` (openpyxl). Reciben un dict `contenido` (ver docstring).
- `app/core/figuras.py`: gráficos PNG con matplotlib (backend Agg), misma paleta que la interfaz.
- `app/api/reportes.py`: arma `contenido` desde la BD, guarda en `<carpeta de la BD>/reportes/` y
  registra `ReporteGenerado` con SHA-256 (`/verificar` recalcula el hash).
- Documentación de usuario: `docs/INSTALACION.md`, `docs/MANUAL_USUARIO.md`, capturas en `docs/capturas/`.

## Usabilidad (rediseño 2026-11, ver HANDOFF §2b)
- La app debe ser comprensible para **personas no expertas**: textos en palabras simples, la jerga
  técnica solo en Ingeniería y en secciones "Detalle técnico". Errores que digan cómo arreglarlo.
- Plan de muestreo: `servicios.plan_muestreo` / `aplicar_plan`; textos en `diseno_arl.textos_plan`
  (reutilizables en reportes). σ fijada: `variables.sigma_monitoreo` + `gv.limites_con_sigma`.
- Columnas nuevas en modelos: agregarlas también a `sesion.COLUMNAS_NUEVAS` (migración automática).
- Capacidad: solo Cp, Cpk, Cpl, Cpu y fracción no conforme (sin Pp/Ppk).

## Plantilla de carga (2026-11)
- `app/core/plantilla.py`: `construir_plantilla(spec)` (Excel con openpyxl: hoja por variable, bloques
  Fase I / Fase II, validación de datos, formato condicional con `FormulaRule` + `ISNUMBER`, protección
  sin contraseña, hoja oculta `_cep` con el JSON que describe filas y columnas) y `leer_plantilla`.
  Rellenos de formato condicional: fijar `bgColor` (Excel lo usa en DXF).
- `app/api/plantillas.py`: `/plantillas/sugerencia`, `/generar`, `/revisar` (no guarda), `/importar`.
  El número de muestra de la plantilla es el número real (`registrar_subgrupo(numero=...)`): no hay
  duplicados al resubir. Ids de variables/proceso creados desde una plantilla: ajuste `plantilla:<id>`.
- Pantalla `/ingenieria/plantilla` (`ing_plantilla.html/js`). Verificación del Excel: abrirlo con
  Excel por COM (`DisplayFormat.Interior.Color`, `ExportAsFixedFormat`) si está instalado.

## Programa de escritorio e instalador (2026-11)
- `app/escritorio.py` = entrada de `CEP.exe`: datos en `C:\Users\<usuario>\CEP` (o `CEP_DATOS`; **no**
  Documentos, que suele estar en OneDrive; `migrar_datos_anteriores` copia desde Documentos\CEP), mutex de
  instancia única, respaldo al iniciar, `registro.log`, uvicorn en un hilo (127.0.0.1) y ventana
  pywebview/WebView2 con pantalla de carga inmediata. `private_mode=False` + `storage_path` para
  conservar localStorage; `ALLOW_DOWNLOADS` para PDF/Excel. `--sin-ventana --puerto N` para pruebas.
- Variables de entorno: `CEP_MODO=escritorio`, `CEP_SIN_DEMO=1` (la base arranca vacía; demo con
  `POST /api/sistema/demo`). `app/db/respaldos.py` + `app/api/sistema.py` (respaldos, restaurar,
  copia descargable). sqlite3: cerrar conexiones con `contextlib.closing` (Windows bloquea archivos).
- Construir: `construir.bat` → `instalador/cep.spec` (PyInstaller onedir) + `instalador/cep.iss`
  (Inno Setup, por usuario, sin admin; el .iss debe guardarse en UTF-8 **con BOM**). Salida en
  `instalador/salida/`. Construcción intermedia en `%USERPROFILE%\.cep-construccion`: **nunca en
  AppData** (el Python de la Microsoft Store la redirige en silencio a su carpeta privada).
- Al agregar archivos que la app lee de disco, sumarlos a `datas` en `cep.spec`.
- Skill del proyecto `construir-cep` (`.claude/skills/`) con la receta y la verificación.

## Diseño (frontend)
- Conservar las clases Tailwind y la estructura de Stitch; la configuración de colores está en
  `Stitch/.../industrial_precision_control/DESIGN.md`.
- Tipografía (pedido del usuario, 2026-11): **League Spartan** en `headline-*` y **Montserrat** en
  `body-*`, `label-*` y `metric-*` (cifras tabulares). Archivos locales en `static/vendor/fuentes/`
  (regenerar con `python -m app.web.descargar_vendor`). Sin etiquetas en mayúsculas (`uppercase`).
- Números con coma decimal también en los gráficos (`separators: ",."` en Plotly).
- Colores de cartas: LC `#0f4c5c`, LCS/LCI `#ba1a1a`, LES/LEI `#70787c` punteado; semáforo verde
  `#15803D`, ámbar `#B45309`, rojo `#B91C1C` reservados para estado del proceso.
