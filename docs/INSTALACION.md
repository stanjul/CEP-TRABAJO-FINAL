# Instalación y puesta en marcha

Aplicación de Control Estadístico de Procesos (CEP) — trabajo final. Corre en una sola
computadora: servidor local (FastAPI) + base SQLite + interfaz propia. No requiere internet.

Hay dos formas de usarla:

| Forma | Para quién | Qué se necesita |
|---|---|---|
| **Programa de escritorio** (`CEP-Setup-1.0.1.exe`) | Quien solo va a usar la aplicación | Windows 10/11 de 64 bits. Nada más. |
| **Desde el código** (`run.bat` / `run.sh`) | Quien la desarrolla o la revisa por dentro | Python 3.11+ (ver §1 en adelante) |

## 0. Programa de escritorio (recomendado)

1. Doble clic en **`CEP-Setup-1.0.1.exe`** (unos 70 MB). No pide permisos de administrador: se
   instala para el usuario actual. Si Windows muestra «Windows protegió su PC» (el programa no
   está firmado digitalmente), elegir **Más información → Ejecutar de todas formas**.
2. Abrir **CEP** desde el menú Inicio o el acceso directo del escritorio. Se abre en su propia
   ventana (sin navegador). La primera vez puede tardar hasta un minuto mientras Windows revisa
   el programa; las siguientes, unos segundos.
3. La base arranca **vacía**: crear el primer proceso con el asistente, o cargar los datos de
   demostración desde **Ingeniería → Base de datos y respaldos**.

**Dónde quedan los datos:** `C:\Users\<tu usuario>\CEP\` (no en Documentos, que suele estar
dentro de OneDrive: sincronizar una base de datos abierta puede crear copias en conflicto). Si una
versión anterior guardó datos en `Documentos\CEP`, el programa los copia solo a la carpeta nueva la
primera vez que se abre y deja la vieja como copia de seguridad, con un archivo «LEEME».

| Archivo / carpeta | Contenido |
|---|---|
| `cep.db` | La base de datos con todos los procesos |
| `reportes\` | Informes PDF y Excel generados |
| `respaldos\` | Copia automática de la base cada vez que se abre el programa (las últimas 20) |
| `registro.log` | Registro de errores (para diagnosticar problemas) |

Desinstalar (Configuración → Aplicaciones) **no borra** esta carpeta. Para pasar los datos a otro
equipo: en **Base de datos y respaldos**, «Descargar una copia» y, en el otro equipo,
«Restaurar desde un archivo».

Para los informes PDF con LaTeX instalar además MiKTeX (opcional, ver §1); sin él, el PDF se genera
con el formato de respaldo.

### Construir el instalador (desarrolladores)

Con el entorno de desarrollo listo (§2) e Inno Setup 6 (`winget install --id JRSoftware.InnoSetup -e`):

```bat
construir.bat
```

Instala PyInstaller y pywebview (`requirements-build.txt`), corre las pruebas, empaqueta con
PyInstaller (`instalador\cep.spec`, unos 4 minutos) y arma el instalador con Inno Setup
(`instalador\cep.iss`). Resultado: `instalador\salida\CEP-Setup-1.0.1.exe`. La construcción
intermedia va a `%USERPROFILE%\.cep-construccion` (fuera de OneDrive y de AppData: el Python de la
Microsoft Store redirige en silencio lo que se escribe en AppData).

Para probar el programa de escritorio sin empaquetar: `.venv\Scripts\python.exe -m app.escritorio`
(requiere `pip install pywebview`).

## 1. Requisitos

| Requisito | Versión | Notas |
|---|---|---|
| Sistema operativo | Windows 10/11, Linux o macOS | Probado en Windows 11 |
| Python | 3.11 o superior | En Windows marcar **"Add python.exe to PATH"** al instalar |
| Navegador | Edge, Chrome o Firefox actualizados | |
| Internet | Solo la **primera vez** | Para descargar las librerías de Python (~250 MB) |
| Espacio en disco | ~400 MB | Entorno virtual + base de datos + reportes |
| LaTeX (recomendado) | MiKTeX (Windows) o TeX Live (Linux / macOS) | Para el **informe PDF con LaTeX**. Sin LaTeX la app funciona igual y genera el PDF con el formato de respaldo |

### LaTeX para el informe PDF

El informe se compila con `pdflatex` y la fuente predeterminada de LaTeX. Paquetes que usa (vienen
en la instalación básica de MiKTeX y en TeX Live): `lmodern`, `babel` (español), `geometry`,
`booktabs`, `tabularx`, `longtable`, `xcolor`, `fancyhdr`, `lastpage`, `enumitem`, `titlesec`,
`needspace`, `microtype`, `hyperref`.

- **Windows:** instalar [MiKTeX](https://miktex.org/download) y comprobar en una terminal
  `pdflatex --version`. La app llama a MiKTeX con `--disable-installer`: si faltara un paquete, no
  aparece ninguna ventana; el PDF se genera con el formato de respaldo y la pantalla Reportes lo
  avisa. Para instalar los paquetes que falten, abrir la **MiKTeX Console → Packages**.
- **Linux:** `sudo apt install texlive-latex-recommended texlive-latex-extra texlive-lang-spanish`.
- **macOS:** instalar MacTeX o BasicTeX.

La pantalla **Reportes** indica si LaTeX está disponible en el equipo.

Verificar Python desde una terminal:

```bash
python --version      # Windows
python3 --version     # Linux / macOS
```

## 2. Arranque con un solo comando

### Windows
Doble clic en **`run.bat`** (o ejecutar `run.bat` en una terminal dentro de la carpeta del proyecto).

### Linux / macOS
```bash
chmod +x run.sh     # solo la primera vez
./run.sh
```

El script:

1. Crea el entorno virtual `.venv` si no existe.
2. Instala las dependencias de `requirements.txt` (solo la primera vez o si el archivo cambió).
3. Crea la base `data/cep.db` y carga los **datos de demostración** si está vacía.
4. Levanta el servidor en `http://127.0.0.1:8000` y **abre el navegador** cuando está listo.

Para detener el servidor: cerrar la ventana o presionar `Ctrl + C`.

### Opciones

| Opción | Efecto |
|---|---|
| `run.bat --puerto 8001` | Usa otro puerto (si 8000 está ocupado se elige el siguiente libre automáticamente) |
| `run.bat --sin-navegador` | No abre el navegador |
| `run.bat --reiniciar` | Borra `data/cep.db` y vuelve a cargar los datos de demostración |

## 3. Datos de demostración

Al iniciar con la base vacía se cargan:

| Proceso | Variable | Carta | Estado inicial |
|---|---|---|---|
| Línea de Envasado L-04 | Peso neto (g) | X̄-R, n = 5 | **Fase II**: base con los subgrupos 1–19 de `datos_prueba/proceso_simulado.csv` congelada; listo para registrar los subgrupos 20–25 (corrimiento de +1.5σ) |
| Línea de Envasado L-04 | Envases defectuosos | p, n = 50 | Fase I con los datos de Montgomery (latas de jugo) sin depurar |
| Ejemplos Montgomery | Diámetro de anillos de pistón (mm) | X̄-R | Fase I |
| Ejemplos Montgomery | Costo de préstamos hipotecarios | I-MR | Fase I |
| Ejemplos Montgomery | No conformidades en circuitos | c | Fase I |
| Ejemplos Montgomery | Defectos en computadoras | u | Fase I |

Los archivos de `datos_prueba/` se pueden cargar desde **Ingeniería → Datos & Carga CSV**.
Para regenerarlos: `.venv\Scripts\python.exe datos_prueba\generar_datos.py`.

## 4. Ejecutar las pruebas

```bash
.venv\Scripts\python.exe -m pytest          # Windows
.venv/bin/python -m pytest                  # Linux / macOS
```

Hay pruebas de la lógica estadística (validada con los ejemplos resueltos de Montgomery), de la
API, de las pantallas y de la generación de reportes. Para ver la lógica en consola sin interfaz:

```bash
.venv\Scripts\python.exe datos_prueba\demo_core.py
```

## 5. Dónde queda cada cosa

| Elemento | Ubicación |
|---|---|
| Base de datos | `data/cep.db` (SQLite; se puede abrir con *DB Browser for SQLite*) |
| Reportes generados (PDF / Excel) | `data/reportes/` (también se descargan desde la pantalla Reportes) |
| Documentación de la API | `http://127.0.0.1:8000/docs` (Swagger, se puede probar cada endpoint) |
| Recursos web locales (Tailwind, Plotly, fuentes) | `app/web/static/vendor/` |

Para copiar el proyecto a otra computadora basta con copiar la carpeta **sin** `.venv` (se recrea
con `run.bat`). Para conservar los datos, copiar también `data/`.

## 6. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `No se encontró Python 3.11 o superior` | Python no instalado o fuera del PATH | Instalar Python 3.11+ marcando "Add python.exe to PATH" y volver a ejecutar |
| `Error instalando dependencias` / `getaddrinfo failed` / `incomplete-download` | Corte de red o DNS durante la descarga | Verificar la conexión y volver a ejecutar `run.bat` (reintenta con `--retries 10`). En redes con proxy: `.venv\Scripts\python.exe -m pip install -r requirements.txt --proxy http://usuario:clave@proxy:puerto` |
| El navegador no abre | Bloqueo del sistema | Abrir manualmente la dirección que muestra la consola (`http://127.0.0.1:8000/`) |
| `Sin conexión` en el encabezado de la app | El servidor se detuvo | Volver a ejecutar `run.bat` |
| La cuenta regresiva aparece "atrasada" | Los datos de demostración se cargaron hace tiempo | Registrar un subgrupo o reiniciar con `run.bat --reiniciar` |
| Lentitud en OneDrive | OneDrive sincroniza `.venv` | Pausar la sincronización o mover el proyecto fuera de OneDrive |
| Faltan los recursos web (página sin estilos) | Se borró `app/web/static/vendor/` | Con internet: `.venv\Scripts\python.exe -m app.web.descargar_vendor` |
| «PDF generado con el formato de respaldo» | No hay LaTeX instalado o falta un paquete | Instalar MiKTeX / TeX Live (ver §1); el aviso de la pantalla Reportes muestra el error de LaTeX |

## 7. Desarrollo

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload    # recarga automática al editar
```

Convenciones del código y arquitectura: ver [`CLAUDE.md`](../CLAUDE.md).
