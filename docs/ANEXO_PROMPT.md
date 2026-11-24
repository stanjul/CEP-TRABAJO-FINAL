# Anexo — Prompt de desarrollo del software CEP

> Prompt consolidado: resume en un solo texto las instrucciones que se dieron al asistente de
> inteligencia artificial (Claude, de Anthropic, en Claude Code) a lo largo del desarrollo.
> El trabajo real se hizo en varias sesiones y por fases; este texto reúne esos pedidos en orden
> lógico.

---

**Rol y contexto**

Actúa como desarrollador de software y especialista en control estadístico de procesos. Estoy
haciendo el trabajo final de la asignatura Control Estadístico de Procesos. Te adjunto el enunciado
del docente y un diseño de interfaz exportado de Google Stitch. Necesito construir, a partir de
ese diseño, un software funcional que una empresa pueda usar para estabilizar y controlar sus
procesos. Trabajaremos con datos de una empresa real.

**Objetivo**

Desarrolla una aplicación de control estadístico de procesos que cubra los ocho módulos del
enunciado:

1. **Gestión de datos.** Carga de archivos CSV y Excel, limpieza de faltantes y atípicos, formación
   de subgrupos racionales y tablas resumen. Diseña además una **plantilla Excel paramétrica**, con
   la estética de la aplicación, en la que yo elija:
   - cuántas muestras son para establecer los límites (estabilización) y cuántas para el control;
   - cuántas variables se monitorean, con su nombre y su tipo;
   - el tamaño de muestra.

   La plantilla debe validar los datos y cargarse sin tener que asignar columnas a mano.
2. **Cartas de control por variables:** X̄-R, X̄-S e I-MR. Deben cubrir la Fase I (estimar los
   límites y excluir las causas asignables con su justificación) y la Fase II (monitorear con los
   límites congelados).
3. **Cartas de control por atributos:** p, np, c y u, con un asistente que explique cuál conviene.
4. **Validación de supuestos:** normalidad, independencia y aleatoriedad, con un veredicto claro.
5. **Capacidad del proceso:** solo Cp, Cpk, Cpu, Cpl y la fracción no conforme, que es lo que vimos
   en clase. No incluyas Pp ni Ppk.
6. **Diseño de cartas por ARL/ATS.** Debo poder cambiar el tamaño de muestra y la frecuencia de
   muestreo, y que se recalculen el ARL y el ATS. También debo poder ajustar el σ de monitoreo
   según el criterio del ingeniero.
7. **Muestreo de aceptación:** curvas OC, AOQ y ATI, diseño de planes y dictamen de lotes.
8. **Reportes en PDF y Excel.** Los PDF se hacen con LaTeX, con la fuente por defecto. Deben ser
   sencillos, fáciles de leer para personas que no son ingenieras, y **solo describir** la
   información importante, sin sugerir cambios.

**Requisitos de uso**

- Debe ser un software usable por **personas no expertas**: intuitivo, con textos en palabras
  simples y mensajes de error que digan cómo arreglar el problema. La jerga técnica queda solo
  para la parte de ingeniería.
- Debe tener **dos vistas**:
  - **Operario**, poco técnica: permite registrar las unidades muestreadas y leer cómo va el
    proceso. No debe llevar a pantallas de ingeniería.
  - **Ingeniería**, con el análisis completo.
- Incluye un **asistente** para escoger y nombrar la variable a monitorear y su tipo.
- Cada cambio de configuración, exclusión o carga de datos debe quedar registrado (trazabilidad).
- Tipografía: **League Spartan** en los títulos y **Montserrat** en el cuerpo. Conserva los colores
  y la estructura del diseño de Stitch. Usa coma decimal.

**Requisitos técnicos**

- Debe funcionar **en un solo computador y sin internet**, con su propia base de datos (un backend
  local, sin alojarlo en la web): FastAPI, SQLite, plantillas HTML y gráficos con Plotly.
- Separa la estadística en un núcleo independiente y valídala con los ejemplos del libro de
  Montgomery mediante pruebas automáticas.
- Empaquétalo como **programa de escritorio** con instalador para Windows. Los datos deben quedar
  fuera de OneDrive, con respaldos automáticos. Debe poder compartirse con otras personas para que
  lo prueben en su computador.
- Mantén el proyecto en un **repositorio Git** publicado en GitHub.

**Forma de trabajo**

Antes de programar, propón un plan y sugerencias de usabilidad y de módulos. Luego avanza por
fases. Al cerrar cada fase:
- verifica con pruebas;
- muéstrame el resultado;
- espera mi aprobación antes de seguir.

Escribe todo en español.

**Entregables**

- El software, con su código fuente y su instalador.
- El manual de usuario y la guía de instalación.
- Una **descripción técnica del software** en PDF: qué hace, sus módulos, su arquitectura y sus modos
  de uso, escrita de forma técnica pero clara.
