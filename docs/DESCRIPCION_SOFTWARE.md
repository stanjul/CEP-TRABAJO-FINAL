# Descripción técnica del software CEP

**CEP — Control Estadístico de Procesos**, versión 1.0.0
Programa de escritorio para Windows (y aplicación web local) que implementa el control estadístico
de procesos de punta a punta: captura de datos, cartas de control en Fase I y Fase II, validación
de supuestos, capacidad, diseño de cartas por ARL/ATS, muestreo de aceptación y reportes con
trazabilidad.

Este documento describe **qué hace el software y cómo está construido**. El uso paso a paso está en
el [manual de usuario](MANUAL_USUARIO.md) y la instalación en [INSTALACION.md](INSTALACION.md).

---

## 1. Propósito y alcance

CEP convierte las mediciones o conteos de un proceso productivo en información para decidir:
si el proceso es estable (está bajo control estadístico), si es capaz de cumplir la especificación,
qué fracción del producto se espera fuera de ella y con qué plan de muestreo conviene vigilarlo.

| Aspecto | Alcance |
|---|---|
| Datos | Variables continuas (mediciones) y atributos (unidades defectuosas o defectos por unidad) |
| Fases | Fase I (estimación de límites con depuración de causas asignables) y Fase II (monitoreo con límites congelados) |
| Usuarios | Dos perfiles: **Operario** (registro y lectura del proceso en palabras simples) e **Ingeniería** (análisis completo) |
| Despliegue | Un solo equipo: servidor local en `127.0.0.1`, base SQLite, sin internet ni servicios externos |
| Base teórica | Montgomery, *Introduction to Statistical Quality Control*; los resultados del núcleo estadístico se validan con sus ejemplos resueltos |

---

## 2. Arquitectura

### 2.1 Capas

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Ventana propia (WebView2 vía pywebview)  ·  o navegador en modo servidor │
│   16 pantallas Jinja2 + JavaScript por pantalla + Plotly.js (todo local) │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ HTTP/JSON (127.0.0.1)
┌───────────────────────────────┴──────────────────────────────────────────┐
│ app/api — FastAPI: 67 operaciones REST en 16 grupos (routers por módulo) │
│   servicios.py: orquesta base de datos + núcleo (sin fórmulas propias)   │
└──────────────┬───────────────────────────────────────┬───────────────────┘
               │                                       │
┌──────────────┴──────────────┐        ┌───────────────┴───────────────────┐
│ app/db — SQLAlchemy 2       │        │ app/core — núcleo estadístico      │
│ SQLite (un archivo cep.db)  │        │ puro: listas/arrays → dict JSON    │
│ migraciones, respaldos      │        │ sin dependencias de web ni de BD   │
└─────────────────────────────┘        └────────────────────────────────────┘
```

**Regla de dependencias:** `app/core` no importa FastAPI, SQLAlchemy ni nada de las otras capas.
Cada función recibe datos y devuelve diccionarios serializables, y documenta en su docstring la
fórmula que implementa. Esto permite probar la estadística de forma aislada y reutilizarla en la
API, los reportes y la consola (`datos_prueba/demo_core.py`).

### 2.2 Tecnologías

| Capa | Tecnología (versión instalada) |
|---|---|
| Lenguaje | Python 3.11 |
| Cálculo | NumPy 2.4, SciPy 1.17, pandas 3.1, statsmodels 0.15 |
| API y servidor | FastAPI 0.165, Uvicorn 0.54, Pydantic (validación de entradas) |
| Persistencia | SQLAlchemy 2.1 sobre SQLite |
| Interfaz | Jinja2 3.1, JavaScript sin framework, Tailwind CSS (local), Plotly.js 2.35 (local) |
| Reportes | LaTeX (`pdflatex`, MiKTeX/TeX Live) + Jinja2; respaldo con ReportLab 5.1; Excel con openpyxl 3.1; figuras con Matplotlib 3.11 |
| Escritorio | pywebview 6.2 (Microsoft Edge WebView2), PyInstaller 6.22, Inno Setup 6 |
| Pruebas | pytest (278 pruebas automáticas) |

Todos los recursos de la interfaz (Tailwind, Plotly, tipografías League Spartan y Montserrat, íconos
Material Symbols) se sirven desde la propia aplicación: no hay solicitudes a internet en ejecución.

### 2.3 Tamaño del código propio

| Capa | Archivos | Líneas |
|---|---|---|
| `app/core` (estadística, reportes, plantilla) | 15 | ≈ 4 000 |
| `app/api` (endpoints y servicios) | 19 | ≈ 2 200 |
| `app/db` (modelos, sesión, semilla, respaldos) | 5 | ≈ 400 |
| `app/web` (plantillas HTML y JavaScript) | 39 | ≈ 5 800 |
| `tests` | 23 | ≈ 1 900 |

---

## 3. Modos de uso

### 3.1 Programa de escritorio (distribución a usuarios)

- **Instalador:** `CEP-Setup-1.0.0.exe` (≈ 69 MB). Instala por usuario, sin permisos de
  administrador (≈ 205 MB instalados), crea accesos directos y un desinstalador.
- **Ejecución:** `CEP.exe` levanta el servidor en `127.0.0.1` en un puerto libre (8000–8099) y
  abre una ventana propia con WebView2. Al cerrar la ventana se detiene el servidor. Se impide una
  segunda instancia (mutex de Windows).
- **Datos:** `C:\Users\<usuario>\CEP\` (fuera de OneDrive): `cep.db`, `reportes\`, `respaldos\`
  y `registro.log`. Desinstalar o actualizar no borra esta carpeta.
- **Primer arranque:** base vacía; los datos de demostración se cargan a pedido.
- **Respaldo automático** de la base en cada apertura (se conservan los últimos 20).

### 3.2 Modo servidor (desarrollo y revisión)

`run.bat` (Windows) o `run.sh` (Linux/macOS) crean el entorno virtual, instalan dependencias,
siembran los datos de demostración y abren el navegador en `http://127.0.0.1:8000`. La base queda
en `data/cep.db`.

### 3.3 API REST

Toda la funcionalidad está disponible como API JSON con documentación interactiva (OpenAPI) en
`/docs`. La interfaz no tiene lógica estadística propia: consume esta API.

### 3.4 Perfiles de la interfaz

| Perfil | Pantallas | Enfoque |
|---|---|---|
| **Operario** | Registrar muestra · Cómo va el proceso · Alertas · Historial de muestras | Lenguaje simple: estado del proceso en palabras («El proceso va bien», «Revisar», «Detener y avisar»), qué hacer, una sola gráfica, alertas explicadas sin códigos de reglas |
| **Ingeniería** | 12 pantallas (ver §5) | Análisis completo, configuración, diseño, reportes y administración de la base |

No hay inicio de sesión: el nombre del usuario se indica en el encabezado y viaja con cada acción
registrada (trazabilidad).

---

## 4. Modelo de datos

Una sola base SQLite con todos los procesos de la planta.

| Tabla | Contenido |
|---|---|
| `procesos` | Proceso o línea productiva (nombre, planta, línea, descripción) |
| `variables` | Característica de calidad y su configuración: tipo de carta, tamaño de muestra *n*, frecuencia, especificaciones (LEI, objetivo, LES), ancho de límites *k*, estimador de σ, σ fijada por el ingeniero, reglas activas, fase, decimales, versión |
| `subgrupos` | Cada muestra: número, fecha y hora, fase (`I`, `II`, `archivo`, `anulado`), conteo y tamaño (atributos), operario, lote, origen (manual, importado, plantilla, semilla), exclusión con causa y acción |
| `mediciones` | Valores individuales de cada subgrupo (variables) |
| `limites_carta` | Límites congelados para la Fase II, con historial (uno activo) |
| `alarmas` | Violaciones de reglas y eventos manuales (parada, retención, anomalía), con explicación en palabras, severidad, estado, causa y acción |
| `cambios_configuracion` | Historial de auditoría: parámetro, valor anterior y nuevo, usuario, justificación, versión y SHA-256 de la configuración |
| `lotes_inspeccion` | Lotes evaluados por muestreo de aceptación y su dictamen |
| `reportes` | Reportes generados con su huella SHA-256 |
| `ajustes` | Ajustes globales (turnos, modo demostración, identificadores de plantillas) |

Las columnas agregadas en versiones posteriores se crean automáticamente al abrir una base
anterior (migración incorporada).

---

## 5. Módulos funcionales

Los módulos 1 a 8 corresponden al alcance técnico pedido para el trabajo. Para cada uno se indican
los métodos implementados.

### Módulo 1 — Gestión de datos

- **Plantilla de carga paramétrica (recomendada).** La aplicación genera un libro Excel a la medida
  del proceso: una hoja por variable, muestras prenumeradas en dos bloques («para establecer los
  límites» = Fase I, «monitoreo» = Fase II), fecha y hora sugeridas según la frecuencia, columnas
  según el tipo de dato, columnas calculadas (promedio, rango, % defectuosas), validación de datos
  en Excel (solo números, conteos enteros, defectuosas ≤ revisadas), formato condicional para
  valores fuera de especificación, protección de la estructura y una descripción oculta que permite
  leerla sin mapeos. Al subirla se muestra un informe de revisión (errores y avisos por hoja y
  muestra) antes de guardar; cargas repetidas no duplican muestras y cada muestra entra en su fase.
- **Importación de CSV/Excel genéricos:** detección de delimitador y codificación, formato largo
  (una fila por medición) o ancho (una fila por subgrupo), perfilado de columnas, mapeo sugerido
  automáticamente, conversión numérica con coma o punto decimal.
- **Limpieza:** valores faltantes (descartar, imputar con la media del subgrupo o bloquear la
  importación) y atípicos (criterio de Tukey con rango intercuartílico, criterio de ±k·σ o ninguno),
  con informe de lo modificado.
- **Subgrupos racionales:** formación por columna de subgrupo o por tamaño *n* consecutivo.
- **Tablas resumen:** media, mediana, desviación estándar, mínimo, máximo, cuartiles y estadísticos
  por subgrupo; exportación del conjunto depurado.
- **Variables a controlar:** alta de procesos y variables con un asistente de cuatro pasos que
  recomienda la carta según cómo se registra el dato y el tamaño de muestra, explicando el porqué.

### Módulo 2 — Cartas de control por variables

- **X̄-R** (2 ≤ *n* ≤ 10): X̿ ± A₂R̄; R: [D₃R̄, D₄R̄]; σ̂ = R̄/d₂.
- **X̄-S** (*n* > 10 o *n* variable): X̿ ± A₃s̄; S: [B₃s̄, B₄s̄]; σ̂ = s̄/c₄; con *n* variable, límites por
  subgrupo y s̄ combinada.
- **I-MR** (*n* = 1): x̄ ± k·MR̄/1,128; MR: LCS = D₄(2)·MR̄.
- Ancho de límites *k* configurable (fórmulas generales cuando *k* ≠ 3) y **σ fijada por el
  ingeniero** (límites con estándar dado: X̄ ± kσ/√n, R: (d₂ ± k·d₃)σ, S: (c₄ ± k√(1−c₄²))σ).
- **Fase I:** cálculo con los subgrupos incluidos, exclusión de subgrupos con causa asignable
  obligatoria, simulación del efecto de excluir antes de confirmar, recálculo iterativo y
  congelamiento de límites (advierte si quedan señales o hay menos de 20 subgrupos).
- **Fase II:** cada subgrupo nuevo se evalúa contra los límites congelados y genera alarmas.
- Constantes A₂, A₃, B₃, B₄, D₃, D₄, d₂, d₃ y c₄ para *n* = 2 a 25.

### Módulo 3 — Cartas de control por atributos

- **p** (fracción defectuosa, *n* constante o variable con límites por muestra), **np** (número de
  defectuosos, *n* constante), **c** (defectos por muestra), **u** (defectos por unidad, tamaño
  variable).
- Límites p̄ ± k√(p̄(1−p̄)/nᵢ), c̄ ± k√c̄, ū ± k√(ū/nᵢ), recortados a [0, 1] o a 0.
- **Selección justificada:** asistente que elige la carta según el tipo de dato (unidad buena/mala
  frente a conteo de fallas) y si el tamaño de muestra es constante, con la explicación en palabras.
- Mismo flujo de Fase I y Fase II que en variables.

### Reglas de detección (comunes a ambos tipos de carta)

Nelson N1–N8 y la variante Western Electric WE4, evaluadas sobre el valor estandarizado
*z* = (x − LC)/σ del estadístico graficado, con presets «Nelson» y «Western Electric»:

| Regla | Patrón |
|---|---|
| N1 | 1 punto fuera de los límites de control |
| N2 | 9 puntos seguidos del mismo lado de la línea central |
| N3 | 6 puntos seguidos crecientes o decrecientes |
| N4 | 14 puntos seguidos alternando arriba y abajo |
| N5 | 2 de 3 puntos más allá de 2σ del mismo lado |
| N6 | 4 de 5 puntos más allá de 1σ del mismo lado |
| N7 | 15 puntos seguidos dentro de ±1σ (estratificación) |
| N8 | 8 puntos seguidos fuera de ±1σ a ambos lados (mezcla) |
| WE4 | 8 puntos seguidos del mismo lado de la línea central |

Las cartas de dispersión (R, S, MR) evalúan solo N1. Cada violación genera una alarma con
severidad (crítica, advertencia, alerta) y una explicación en palabras simples para el operario;
una racha no genera alarmas repetidas.

### Módulo 4 — Validación de supuestos

| Supuesto | Métodos |
|---|---|
| Normalidad | Shapiro-Wilk, Anderson-Darling, Lilliefors; gráfico Q-Q con bandas de confianza al 95 %; asimetría y curtosis |
| Independencia | Función de autocorrelación (ACF) con bandas ±1,96/√N, prueba de Ljung-Box, estadístico de Durbin-Watson |
| Aleatoriedad y estabilidad | Prueba de rachas sobre la mediana, tendencia por τ de Kendall |
| Transformación | Box-Cox con λ estimado e intervalo de confianza |

Se emite un veredicto global de aptitud para cartas de Shewhart. Las causas especiales se
identifican con las reglas del Módulo 2 y se justifican al excluir subgrupos (causa y acción
obligatorias, registradas en el historial).

### Módulo 5 — Capacidad del proceso

- **Índices:** Cp = (LES − LEI)/6σ̂; Cpu = (LES − μ̂)/3σ̂; Cpl = (μ̂ − LEI)/3σ̂; Cpk = mín(Cpu, Cpl).
  Con especificación unilateral se informa el índice del lado especificado.
- σ̂ dentro de subgrupos (R̄/d₂, s̄/c₄ o MR̄/1,128) o σ fijada por el ingeniero.
- **Fracción no conforme esperada** bajo normalidad, por lado (debajo del mínimo y encima del
  máximo), en porcentaje y en piezas por millón; **fracción observada** en los datos, por lado.
- Comparación con la especificación mediante histograma con curva normal y líneas de mínimo,
  máximo, ideal y promedio.
- **Veredicto:** capaz (Cpk ≥ 1,33), marginal (1,00 ≤ Cpk < 1,33) o no capaz (Cpk < 1,00), con
  advertencia si el proceso no está bajo control.
- Para atributos, la capacidad se expresa como el nivel medio de defectos (p̄, c̄ o ū).

### Módulo 6 — Diseño de cartas y plan de muestreo

- **Carta X̄ / I:** α = 2Φ(−k); β = Φ(k − δ√n) − Φ(−k − δ√n); ARL₀ = 1/α; ARL₁ = 1/(1 − β);
  ATS = ARL·h; desviación estándar de la longitud de corrida y potencia.
- **Cartas de atributos:** ARL exacto con la distribución discreta (binomial para p y np, Poisson
  para c y u), con el nivel habitual de defectos y el nivel que se quiere detectar.
- **Curva ARL₁ (o ATS₁) frente al corrimiento δ** para comparar varios tamaños de muestra, tabla de
  desempeño para δ = 0 a 3 y muestras necesarias para detectar con 90 % de probabilidad.
- **Simulación de Monte Carlo** del ARL, con intervalo de confianza y error relativo frente al
  valor teórico.
- **Plan de muestreo aplicado a la variable:** se ajustan *n*, frecuencia, *k* y σ, y se compara el
  plan vigente con el propuesto en tiempo para detectar un cambio, frecuencia de falsas alarmas y
  **carga muestral** (unidades por hora y por turno), con explicación en palabras. Al guardar el
  plan en Fase II, los límites se recalculan con el centro y la σ congelados; un cambio de *n*
  archiva las muestras de monitoreo tomadas con el tamaño anterior.

### Módulo 7 — Muestreo de aceptación

- **Planes simples (n, c):** probabilidad de aceptación con modelos binomial, hipergeométrico
  (lote finito N) y Poisson.
- **Curva característica de operación (OC), calidad media de salida (AOQ) y su máximo (AOQL),
  inspección total media (ATI).**
- **Diseño del plan** a partir de AQL, LTPD y riesgos α y β, por búsqueda exacta de *n* y *c*.
- **Dictamen de un lote:** aceptar si d ≤ c, con la fracción defectuosa estimada y su intervalo de
  confianza de Wilson; registro histórico de lotes inspeccionados.

### Módulo 8 — Reportes

- **Informe PDF compilado con LaTeX** (fuente predeterminada de LaTeX), escrito para lectores no
  especialistas y **solo descriptivo** (no incluye recomendaciones): estado general en una frase,
  hallazgos, indicadores con su significado, carta de control con guía de lectura, muestras fuera de
  lo normal, cumplimiento de la especificación, verificación de supuestos, plan de muestreo,
  alertas, lotes, historial de cambios, anexo técnico y glosario. Cuatro plantillas (integral,
  capacidad, control, trazabilidad) y selección de secciones.
- **Formato de respaldo:** si el equipo no tiene LaTeX, el PDF se genera con ReportLab y la
  pantalla lo informa.
- **Libro Excel** con una hoja por sección y los datos numéricos reales (subgrupos, límites,
  capacidad, supuestos, diseño, lotes, historial y gráficos).
- Cada archivo se guarda con su **huella SHA-256** y puede verificarse después (detecta cualquier
  modificación).

### Componentes transversales

- **Vista Operario:** captura con resultado en vivo (promedio y si está dentro de lo normal), aviso
  de valor probablemente mal escrito (a más de 5σ del centro habitual o muy lejos de la
  especificación), **deshacer** el último registro durante 10 minutos (queda como «anulado», con
  motivo), cuenta regresiva a la próxima muestra según la frecuencia, resumen del turno y
  reporte manual de problemas.
- **Alarmas:** seguimiento con estados (sin revisar, en revisión, resuelta); para resolver se
  exigen causa y acción.
- **Configuración y auditoría:** especificaciones, reglas, turnos y parámetros con versión, motivo
  obligatorio y SHA-256 de la configuración; historial filtrable y exportable.
- **Base de datos y respaldos:** respaldo manual y automático, restauración a un respaldo (con
  respaldo previo automático), copia descargable de la base, restauración desde archivo y carga de
  los datos de demostración en una base vacía.

---

## 6. Interfaz

| Vista | Pantalla | Función principal |
|---|---|---|
| Operario | Registrar muestra | Estado del proceso, captura, deshacer, gráfica de las últimas 25 muestras, alertas y turno |
| | Cómo va el proceso | Gráfica ampliada con guía de lectura y muestras para revisar |
| | Alertas | Seguimiento de alarmas y eventos |
| | Historial de muestras | Todas las muestras (incluidas archivadas y anuladas), exportable a CSV |
| Ingeniería | Variables a controlar | Procesos y variables; asistente de alta |
| | Plantilla de carga | Generación y carga de la plantilla Excel paramétrica |
| | Datos y carga CSV | Importación, limpieza y subgrupos |
| | Gráficos por variables / por atributos | Cartas en Fase I y II, depuración y congelamiento |
| | Validación de supuestos | Normalidad, independencia, rachas, Box-Cox |
| | Capacidad | Índices, fracción no conforme, histograma y veredicto |
| | Plan de muestreo (ARL) | Diseño de la carta y plan aplicado a la variable |
| | Muestreo de aceptación | Curvas OC, AOQ, ATI, diseño de planes y dictamen de lotes |
| | Límites y reglas | Configuración, reglas, turnos, historial de auditoría y modo demostración |
| | Reportes | Vista previa, PDF, Excel e historial con verificación SHA-256 |
| | Base de datos y respaldos | Ubicación, respaldos, restauración y demostración |

Convenciones de diseño: paleta del diseño original (Google Stitch), colores de semáforo reservados
para el estado del proceso, números con coma decimal también en los gráficos, y textos sin jerga en
la vista Operario.

---

## 7. API REST

67 operaciones bajo el prefijo `/api`, documentadas en `/docs`:

| Grupo | Operaciones | Grupo | Operaciones |
|---|---|---|---|
| Procesos y variables | 9 | Plantilla de carga | 4 |
| Configuración | 9 | Cartas de control | 4 |
| Sistema y respaldos | 9 | Diseño ARL/ATS | 3 |
| Reportes | 6 | Atributos | 2 |
| Subgrupos | 5 | Operario | 1 |
| Muestreo de aceptación | 5 | Supuestos | 1 |
| Alarmas | 4 | Capacidad | 1 |
| Datos | 4 | | |

Las respuestas son JSON; los valores no numéricos (NaN, ±∞) se convierten en `null`. Las entradas
se validan con esquemas Pydantic y los errores se devuelven con mensajes en español que indican
cómo corregirlos.

---

## 8. Trazabilidad e integridad

- Toda modificación de configuración, exclusión de subgrupos, congelamiento o regreso a Fase I,
  cambio de plan, importación y anulación de registros queda en el historial con usuario, fecha,
  valor anterior y nuevo, motivo, versión y **SHA-256 de la configuración resultante**.
- Las muestras no se borran: se excluyen (con causa), se archivan (al reiniciar la Fase I o cambiar
  *n*) o se anulan (error de captura), y conservan su número.
- Los reportes y las plantillas importadas se identifican por su huella SHA-256.

---

## 9. Validación y calidad

- **278 pruebas automáticas** (pytest): cada módulo del núcleo tiene su archivo de pruebas, más
  pruebas de la API con base temporal, de las pantallas y de la generación de archivos.
- **Valores de referencia de Montgomery:** cartas X̄-R (anillos de pistón), I-MR (préstamos), p
  (jugo de naranja), c (circuitos), u (computadoras), capacidad, ARL y muestreo de aceptación.
  Cuando el libro redondea valores intermedios, la prueba verifica el valor exacto con tolerancia y
  reproduce el redondeo del libro.
- **Verificación visual** de las pantallas con Microsoft Edge en modo automático, de la plantilla
  Excel abriéndola en Excel y de los PDF página por página.
- **Programa empaquetado** probado de extremo a extremo: instalación, arranque, pantallas,
  descargas, informe con LaTeX y desinstalación.

---

## 10. Requisitos

| Uso | Requisitos |
|---|---|
| Programa de escritorio | Windows 10 u 11 de 64 bits; Microsoft Edge WebView2 (incluido en Windows 11); ≈ 205 MB de disco |
| Informe PDF con LaTeX (opcional) | MiKTeX (Windows) o TeX Live; sin él se usa el formato de respaldo |
| Modo servidor / desarrollo | Python 3.11 o superior; ≈ 400 MB para el entorno virtual |
| Construcción del instalador | `construir.bat` con PyInstaller e Inno Setup 6 |

---

## 11. Limitaciones y decisiones de alcance

- **Un solo equipo:** el servidor escucha solo en `127.0.0.1`; no hay acceso desde otros equipos de
  la red ni inicio de sesión (el usuario se identifica por nombre).
- **Capacidad:** solo índices Cp, Cpk, Cpu y Cpl (no se calculan Pp ni Ppk); la fracción no conforme
  esperada supone distribución normal (por eso se informa también la observada y se valida la
  normalidad).
- **Cartas:** Shewhart por variables y atributos; no se incluyen CUSUM ni EWMA.
- **Fuera de alcance:** letra código y niveles de inspección de ISO 2859, planes dobles y múltiples,
  ajustes de distribución no normal (Johnson, Weibull) e índices no paramétricos, firma digital,
  integración con balanzas o sistemas SCADA.
- **Distribución:** el instalador no está firmado digitalmente, por lo que Windows muestra una
  advertencia la primera vez.

---

## 12. Organización del código

```
app/
  core/            núcleo estadístico puro
    constantes.py        constantes de cartas (n = 2…25)
    graficos_variables.py, graficos_atributos.py, reglas.py
    supuestos.py, capacidad.py, diseno_arl.py, muestreo_aceptacion.py
    datos.py             lectura, limpieza y subgrupos
    plantilla.py         plantilla Excel paramétrica
    reportes.py, reporte_latex.py, figuras.py, plantillas/reporte.tex
  api/             FastAPI: un router por módulo + servicios.py
  db/              modelos, sesión y migraciones, datos de demostración, respaldos
  web/             rutas de pantallas, plantillas Jinja2, JavaScript y recursos locales
  escritorio.py    programa de escritorio (ventana + servidor local)
  iniciar.py       arranque en modo servidor
instalador/        receta de PyInstaller, script de Inno Setup e ícono
tests/             pruebas automáticas
datos_prueba/      conjuntos de datos de ejemplo y generador
docs/              instalación, manual de usuario, esta descripción y capturas
```
