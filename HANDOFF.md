# HANDOFF — estado del proyecto CEP (actualizado 2026-11-22, Fase A del rediseño)

Documento de traspaso para retomar el trabajo en otra sesión (otra conversación de Claude u otra
persona). Leer junto con `CLAUDE.md` (convenciones) y `README.md` (visión general).

## 1. Qué es
Trabajo final de Control Estadístico de Procesos: app local que implementa el diseño de Google
Stitch (`Stitch/stitch_industrial_spc_suite/`). Stack: FastAPI + SQLite/SQLAlchemy + Jinja2 +
JS vanilla + Plotly.js; core estadístico en numpy/scipy/statsmodels; reportes con reportlab,
openpyxl y matplotlib. Arranque: `run.bat` (o `run.sh`).

`Programa/` es un proyecto anterior del usuario (Vite/Preact): **no tocarlo**.

## 2. Estado: las 4 fases pedidas están TERMINADAS
| Fase | Contenido | Verificación |
|---|---|---|
| 1. Core + tests | `app/core/*` (constantes, reglas, variables, atributos, supuestos, capacidad, diseño ARL, muestreo, datos, reportes, figuras) | Tests con valores de Montgomery |
| 2. API + BD | `app/api/*` (un router por módulo + `servicios.py`), `app/db/*` (modelos, sesión, semilla) | Tests de API con BD temporal |
| 3. Pantallas | `app/web/templates/*.html` + `app/web/static/js/*.js`, 12 pantallas | Capturas Edge headless en `docs/capturas/` |
| 4. Reportes + docs | PDF/Excel con SHA-256, pantalla Reportes, `docs/INSTALACION.md`, `docs/MANUAL_USUARIO.md`, `README.md` | Tests + PDF revisado página a página |

Última corrida: **269 tests pasan** (rediseño A–E + plantilla de carga) (`.venv\Scripts\python.exe -m pytest`, ~20–80 s).
`node --check` sin errores en todos los JS.

## 2b. Rediseño pedido el 2026-11-22 (en curso, por fases A–E)
Pedido del usuario (con el PDF de requisitos de la materia): app **usable por personas no expertas**.
Respaldo previo al rediseño: `respaldos/antes_fase_A_2026-11-22.zip` (no hay git instalado).

| Fase | Contenido | Estado |
|---|---|---|
| A | Asistente "Nueva variable" (`/ingenieria/mis-variables`), plan de muestreo editable con ARL/ATS + carga muestral (`/ingenieria/diseno`), σ de monitoreo fijada por el ingeniero, k editable, cambio de n en Fase II | **Hecha** (223 tests) |
| B | Quitar Pp/Ppk de todo (core, API, pantallas, reportes, tests); dejar Cp, Cpk, Cpl, Cpu y fracción no conforme | **Hecha** (227 tests) |
| C | Vista Operario simple: estado en palabras, una sola gráfica, alarmas en palabras (sin N1…N8), captura central, aviso de valor sospechoso, deshacer último registro, simulación solo en modo demo, % dentro de especificación en vez de Cp/Cpk | **Hecha** (235 tests) |
| D | Tipografía de la interfaz: **League Spartan** (títulos) + **Montserrat** (cuerpo y números, tnum) descargadas a `static/vendor/`; revisar mayúsculas; rehacer capturas | **Hecha** (235 tests) |
| E | Reportes PDF con **LaTeX** (`pdflatex`, fuente por defecto de LaTeX), sencillos, para no ingenieros, **solo mostrar** (sin recomendaciones); respaldo con reportlab si no hay MiKTeX | **Hecha** (252 tests) |

Decisiones de la Fase A (tomadas por defecto, el usuario puede corregirlas):
- "σ de monitoreo" = ambas cosas: k (qué tan estrictos son los límites) y valor de σ fijado.
- Cambio de n en Fase II permitido para X̄ (y np): límites con `gv.limites_con_sigma` (centro y σ
  congelados); las muestras de Fase II con el n anterior pasan a `archivo`.
- Cambio de n en Fase I con datos (X̄-R, np): pide confirmación (`reiniciar_fase_i`) y archiva.
- σ fijada en Fase I: el centro sale de los datos y σ es la del ingeniero; al congelar se hereda.
- Atributos: ARL exacto con Binomial/Poisson (`diseno_arl.diseno_atributos`); σ no se fija a mano.
- Nueva columna `variables.sigma_monitoreo` + migración automática (`sesion.migrar_columnas`).
- Prueba de interacciones en navegador: script CDP (Edge headless + `websockets`), ver §6.

Fase B (hecha):
- `capacidad.analizar_capacidad` devuelve `indices` {cp, cpk, cpu, cpl} (antes `corto_plazo`),
  `ppm_esperado` (antes `ppm_esperado_dentro`), `desviacion_estandar` (s, solo descriptivo) y
  `observado` con `bajo_lei` / `sobre_les`. Ya no existen `largo_plazo`, `sigma_global` ni Pp/Ppk.
- Acepta `sigma=` (σ fijada por el ingeniero → `metodo_sigma = "fijada"`); los servicios la usan
  vía `_capacidad_core` (capacidad, operario, simulación de exclusiones).
- Cpm y k siguen calculándose en el core pero **no se muestran** (fuera del alcance del curso).
- Pantalla Capacidad: sin selector corto/largo plazo; tabla "Producto fuera de especificación"
  por lado (esperado vs observado). Menú de Operario sin enlaces a Ingeniería.

Fase C (hecha):
- Operario = 4 pantallas: `/operario` (Registrar muestra), `/operario/proceso` (Cómo va el
  proceso, nueva), `/operario/alertas`, `/operario/historial`. Piezas comunes en
  `static/js/operario_comun.js` (objeto `OPER`).
- `reglas.CATALOGO[...].simple` + `reglas.explicar(regla, lado)`: textos para el operario; cada
  violación trae `explicacion`. Nueva columna `alarmas.explicacion` (migración); las alarmas viejas
  la deducen de la descripción (`servicios._explicacion_de`).
- `resumen_operario` agrega `semaforo.titulo/que_hacer`, `ventana` (% dentro de especificación,
  promedio, defectos), `rango_habitual` (centro, σ → aviso de valor sospechoso a > 5σ),
  `segundos_para_deshacer`, `modo_demo`.
- Deshacer: `POST /variables/{id}/deshacer-ultimo` (10 min, solo registros manuales). El subgrupo
  pasa a fase `"anulado"` (no cuenta en cartas ni análisis; el número no se reutiliza), sus alarmas
  se cierran y queda una entrada en el historial de cambios.
- Modo demostración: `Ajuste "modo_demo"` (`GET/PUT /ajustes/modo-demo`, interruptor en
  Configuración); la semilla lo activa.
- `GRAF.cartaControl(..., {simple: true})`: rótulos en palabras, franja normal sombreada, "!".
- `main.py`: middleware `Cache-Control: no-cache` para `/static/js` y `/static/css` (antes el
  navegador podía quedarse con JS viejos tras una actualización).

Fase D (hecha):
- Fuentes locales League Spartan + Montserrat (`descargar_vendor.py` actualizado; se borraron los
  woff2 de Inter y JetBrains Mono). `tailwind-config.js`: nueva escala tipográfica.
- Se quitaron las 112 clases `uppercase` / `tracking-wide*` de plantillas y JS.
- Encabezado en palabras: pestañas «Operario» / «Ingeniería», estado «Va bien / Revisar / Detener y
  avisar / Conociendo el proceso» (igual que la vista Operario), «Conectado».
- Gráficos: Montserrat y coma decimal (`separators`). Capturas `docs/capturas/01–11` rehechas y
  nuevas `13_mis_variables`, `14_operario_proceso`. `12_reporte_pdf_pagina1` se rehará en la Fase E.
- Pendiente menor: algunos rótulos de Ingeniería siguen en Title Case heredado de Stitch
  («Veredicto Formal de Aptitud») y la tabla de constantes usa punto decimal.

Fase E (hecha):
- `app/core/reporte_latex.py` + `app/core/plantillas/reporte.tex`: informe en palabras (estado
  general, «En pocas palabras», indicadores con su significado, carta simple con guía de lectura,
  muestras fuera de lo normal, cumplimiento de la especificación, verificación de datos, plan de
  muestreo, alertas, lotes, historial en palabras, anexo técnico, glosario). Solo describe.
- Compila en 3–5 s con MiKTeX (todos los paquetes ya estaban instalados). Figuras flotantes y
  `needspace` para no dejar huecos ni títulos huérfanos.
- API: `/reportes/generar` intenta LaTeX y cae a reportlab (`motor`, `aviso` en la respuesta);
  `/reportes/plantillas` informa `latex`; `/reportes/vista-previa` trae `informe` (mismos textos).
- Pantalla Reportes: vista previa = primera página del informe nuevo; aviso si no hay LaTeX.
- PDF de respaldo y Excel: conclusiones descriptivas (sin «Investigue…», «Registre…»).
- `docs/INSTALACION.md` (MiKTeX/TeX Live), manual y capturas `11_reportes`, `12_reporte_pdf_pagina1`.
- Caso borde resuelto: Fase II sin muestras → «Todavía no hay muestras en esta etapa» (antes
  afirmaba «se mantuvo estable» con 0 muestras).

## 2c. Plantilla de carga (2026-11-23, hecha)
Pedido del usuario: plantilla paramétrica desde la app para cargar datos sin errores. Decisiones
confirmadas: «control» = muestras para establecer límites (Fase I), «monitoreo» = Fase II; la
plantilla puede traer variables/proceso nuevos que se crean al cargar (con confirmación); fuente
Montserrat en Excel (si no está instalada, Excel usa otra). Ver CLAUDE.md «Plantilla de carga».
- Verificado con Excel 16 (COM): abre sin reparar, fórmulas correctas, ámbar solo en valores fuera
  de lo aceptado. No se pudo verificar la paginación de impresión en este equipo (Excel exporta
  páginas de 842×204 pt también sin la configuración nueva: problema del entorno, sin impresora).
- **Programa de escritorio e instalador (hecho, 2026-11-23):** decisiones del usuario: una base para
  todo, solo este equipo, instalador. `CEP-Setup-1.0.0.exe` (68,8 MB, instala 205 MB por usuario sin
  admin). Verificado: build, programa empaquetado (pantallas, demo, PDF LaTeX, plantilla Excel),
  ventana WebView2 real (pantalla de carga, base vacía, instancia única, diálogo «Guardar como» en
  descargas) e instalación/desinstalación silenciosa (conserva los datos). Datos en
  `C:\Users\<usuario>\CEP` desde la v1.0.0 reconstruida (antes `Documentos\CEP`, que en este equipo
  está en OneDrive; se migran solos al abrir). Arranque: ~50 s la
  primera vez (Defender + caché de fuentes de matplotlib), ~10 s después; la ventana aparece al
  instante con pantalla de carga. Ver CLAUDE.md «Programa de escritorio» y la skill `construir-cep`.
  No probado: Windows 10 sin WebView2 y un equipo limpio distinto de este.
- **v1.0.1 (2026-11-24):** marcas de señal ("!" y códigos de regla) en su punto en las cartas
  (anotaciones en eje de categorías usan la posición), plural «1 resuelta», manual de usuario HTML
  interactivo + PDF (`docs/manual/`), descripción técnica en PDF, logos en `docs/marca/`.
  `CEP-Setup-1.0.1.exe` verificado empaquetado (versión, correcciones, demo, PDF LaTeX). Se instala
  encima de la 1.0.0 conservando los datos.
- **Carga muestral objetivo (2026-11-24, después de la 1.0.1):** pedido del usuario según lo que enseñó
  el profesor (carga = n/t). `diseno_arl.evaluar_carga`, `caminos_carga`, `comparar_carga`,
  `textos_carga`; servicio `carga_objetivo`; GET `/variables/{id}/carga` (carga, cambio en unidades,
  m, horizonte_h, k, sigma). Pantalla Plan de muestreo: sección «Carga muestral y potencia» (camino A
  aumentar n, camino B reducir t; potencia 1−β, 1−βᵐ, 1−β^⌊T/h⌋, ATS₁, ATS₀; curvas; «Usar este plan»).
  Solo cartas X̄/I (atributos: pendiente). `GRAF.curvas` admite `rangoY` y `leyendaAbajo`. 285 tests.
  Instalador 1.0.1 reconstruido con esta sección (misma versión, para no desalinear el manual) e
  instalado en el PC del usuario; verificado empaquetado (pantalla y GET /carga).
- **Git (2026-11-23):** instalado con winget (2.56.1). Repositorio local en la carpeta del proyecto,
  rama `main`, primer commit `a689e30`. `Programa/` queda **fuera** (pedido del usuario), igual que
  `.venv/`, `data/*.db`, `data/reportes/` y `respaldos/`. Autor: identidad global ya configurada
  en el equipo (stanjul), elegida por el usuario. `.gitattributes`: `run.sh` LF, `run.bat` CRLF.
  Remoto: **https://github.com/stanjul/CEP-TRABAJO-FINAL** (`origin`, privado, subido el 2026-11-23).
  Hacer commit y `git push` al cerrar cada fase. La sesión de GitHub quedó guardada en el
  Administrador de credenciales; desde una terminal no interactiva, el push necesita
  `GCM_INTERACTIVE=always` la primera vez.
- Respaldo previo: `respaldos/antes_plantilla_2026-11-23.zip`.

## 3. Decisiones tomadas con el usuario (no volver a discutir)
- Sin login: el nombre del usuario se ingresa en el header (localStorage) y viaja como `usuario`.
- Reglas: numeración Nelson N1–N8 + `WE4`; presets "nelson" y "western_electric" (N1, N5, N6, WE4).
- Fuera de alcance (deshabilitado en la UI): letra código ISO 2859, inspección normal/severa/
  reducida, plan doble/ASN, Johnson/Weibull/no paramétricas, firmas digitales/QR, balanza USB, SCADA.
- Ryan-Joiner reemplazado por Ljung-Box; Durbin-Watson con regla práctica 1.5–2.5.
- `.venv` dentro del proyecto (en OneDrive).
- Todo local: Tailwind, Plotly y fuentes en `app/web/static/vendor/` (regenerar con
  `python -m app.web.descargar_vendor` si se borran; requiere internet).

## 4. Hallazgos técnicos que conviene recordar
- Montgomery redondea valores intermedios (X̿=74.001, c̄=19.85): los tests verifican el valor
  exacto con tolerancia y reproducen el redondeo del libro.
- El plan n=89, c=2 del nomograma da α real 6 %; la búsqueda exacta da **n=110, c=3**.
- Fase I con los 25 subgrupos simulados está contaminada (señal espuria en el subgrupo 9): por eso
  la semilla congela solo la base 1–19.
- SQLite no distingue mayúsculas en columnas: `LoteInspeccion.N/n` se guardan como
  `tamano_lote` / `tamano_muestra`.
- Plotly en ejes de categorías: las x deben ser texto (si no, las anotaciones se corren).
- Box-Cox con datos lejos de 0 y poca dispersión: verosimilitud plana → λ acotado a [−5, 5] y la
  UI muestra "λ no identificable".
- "Capacidad instantánea" del operario = ventana móvil de los últimos 25 subgrupos (Fase I + II).
- Supuestos/capacidad sin fase explícita usan la Fase II solo si tiene ≥ 20 subgrupos.
- Reportes se guardan en `<carpeta de la BD>/reportes/` (los tests usan carpeta temporal).
- PDF usa fuente DejaVu de matplotlib (Helvetica no tiene σ, ≥, Δ).
- En PowerShell 5.1, `Set-Content -Encoding utf8` agrega BOM; para editar archivos por script
  usar `[IO.File]::WriteAllText(..., UTF8Encoding($false))`.

## 5. Pendientes / mejoras sugeridas (en orden de prioridad)
0. ~~Fases A–E del rediseño~~ → completas (ver §2b). Quedan pendientes menores anotados en cada fase.
1. ~~Pantalla para crear procesos y variables~~ → hecha en la Fase A (asistente).
2. **Prueba manual en navegador** de interacciones no automatizadas: subir archivo en Datos,
   modales (causas de exclusión, justificaciones), descarga de PDF/Excel. Solo los endpoints están
   cubiertos por tests.
3. **Manual:** completar las marcas "✍ Completar" de `docs/MANUAL_USUARIO.md` (las debe escribir el
   equipo del usuario; no inventarlas).
4. Confirmar la edición de Montgomery del curso (los valores esperados se tomaron de memoria y
   son consistentes con los datos, pero la numeración de ejemplos varía por edición).
5. ~~Git~~ → instalado y con repositorio (ver §2c). Opcional: subirlo a GitHub (privado) y, con
   eso como respaldo, mover el proyecto fuera de OneDrive.
6. Opcionales: fidelidad fina al Stitch en pantallas armadas desde el outline (Datos, Supuestos,
   Capacidad, Muestreo, Configuración); botón eliminar subgrupo/variable; edición de procesos.

## 6. Cómo retomar
```powershell
cd C:\Users\sjuli\OneDrive\Escritorio\Control
.\.venv\Scripts\python.exe -m pytest                       # debe dar 269 passed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload # desarrollo
run.bat --reiniciar                                        # app con datos de demostración frescos
```
Verificación visual (como se hizo en las fases 3 y 4): Edge headless
`msedge --headless=new --window-size=1600,1500 --virtual-time-budget=8000 --screenshot=salida.png http://127.0.0.1:8765/<ruta>?v=<id>`
con un uvicorn en el puerto 8765.

Interacciones (clics, formularios, modales) sin dependencias nuevas: Edge headless con
`--remote-debugging-port` y el protocolo CDP vía `websockets` (ya instalado con uvicorn). El script
de la Fase A estaba en el scratchpad de la sesión (puede haberse borrado): abre la página, ejecuta
pasos `{"js": ...}`, `{"esperar": s}`, `{"captura": png}` con `Runtime.evaluate` y
`Page.captureScreenshot`. Ejecutar Python con `-I` y `sys.stdout.reconfigure(encoding="utf-8")`.

Variables sembradas: 1 Peso neto (X̄-R, Fase II), 2 Envases defectuosos (p, Fase I),
3 Anillos (X̄-R), 4 Préstamos (I-MR), 5 Circuitos (c), 6 Computadoras (u).

## 7. Mapa rápido de archivos clave
| Necesito… | Archivo |
|---|---|
| Fórmulas / lógica | `app/core/<modulo>.py` |
| Lógica que une BD + core | `app/api/servicios.py` |
| Endpoints | `app/api/<modulo>.py` (`app/api/__init__.py` los registra) |
| Modelos | `app/db/modelos.py` |
| Datos de demostración | `app/db/semilla.py`, `app/ejemplos_montgomery.py`, `datos_prueba/` |
| Rutas de pantallas | `app/web/rutas.py` (tabla `PANTALLAS`) |
| Layout común (header/sidebar) | `app/web/templates/base.html` |
| Utilidades JS / gráficos | `app/web/static/js/comun.js`, `graficos.js` |
| Reportes PDF/Excel | `app/core/reportes.py`, `app/core/figuras.py`, `app/api/reportes.py` |

## 8. Preferencias del usuario
- Habla español; quiere todo (código, comentarios, docs) en español.
- Pidió trabajar por fases y, al terminar cada una, correr los tests y explicar cómo probarla.
- Pide aprobación antes de cambios grandes de alcance.
