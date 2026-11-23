"""Plantilla Excel paramétrica para cargar datos sin errores.

`construir_plantilla(spec)` arma un libro .xlsx con la estética de la app:
  - hoja «Instrucciones» en palabras simples;
  - una hoja por variable con las muestras ya numeradas, separadas en dos bloques
    («Para establecer los límites» = Fase I y «Monitoreo» = Fase II), fecha y hora sugeridas,
    columnas de datos según el tipo (Unidad 1…n | Revisadas/Defectuosas | Fallas),
    columnas calculadas de solo lectura y validación mientras se escribe;
  - hoja oculta «_cep» con la descripción exacta (JSON) para leerla de vuelta sin mapeos.

`leer_plantilla(datos)` lee un archivo llenado y devuelve, por variable, las muestras completas,
los errores (filas a medio llenar, números inválidos, defectuosas > revisadas…) y avisos
(valores fuera de lo aceptado, fechas desordenadas). Las filas vacías se ignoran: la plantilla
puede subirse varias veces a medida que se llena.

spec = {
  "id": str, "generada": iso, "proceso": {"id": int|None, "nombre": str, "linea": str|None},
  "opciones": {"lote": bool, "operario": bool, "observaciones": bool},
  "variables": [{"clave", "id"|None, "nombre", "unidad", "tipo_carta", "n", "decimales", "lei",
                 "objetivo", "les", "frecuencia_min", "inicio_numero", "fase_i", "fase_ii",
                 "fecha_inicio" (iso)}],
}
"""

from __future__ import annotations

import io
import json
import math
import re
from datetime import date, datetime, time, timedelta

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

VERSION = 1
HOJA_META = "_cep"
FILA_ENCABEZADO = 5

# Paleta de la app (DESIGN.md de Stitch)
PETROLEO, TINTA, GRIS = "0F4C5C", "0B1C30", "40484B"
FONDO_BANDA, FONDO_ALTERNO, AMBAR_FONDO, AMBAR = "DCE9FF", "EFF4FF", "FEF3C7", "B45309"
CALC_FONDO = "E5EEFF"
F_TITULO = "League Spartan"
F_TEXTO = "Montserrat"

TIPOS_MEDIDA = ("xbar_r", "xbar_s", "imr")
NOMBRE_TIPO = {"xbar_r": "Medición", "xbar_s": "Medición", "imr": "Medición (una unidad por vez)",
               "p": "Unidades defectuosas", "np": "Unidades defectuosas", "c": "Fallas por muestra",
               "u": "Fallas por unidad"}


class ErrorPlantilla(ValueError):
    """El archivo no es una plantilla de CEP o fue modificado en su estructura."""


# ---------------------------------------------------------------------------
# Columnas según el tipo de variable
# ---------------------------------------------------------------------------

def columnas_de(v: dict, opciones: dict) -> list[dict]:
    """Columnas de la hoja de una variable: [{clave, titulo, ancho, rol, editable}].

    rol: numero | fecha | hora | valor | revisadas | conteo | calculo | lote | operario | obs
    """
    t = v["tipo_carta"]
    cols = [{"clave": "numero", "titulo": "Muestra", "ancho": 10, "rol": "numero", "editable": False},
            {"clave": "fecha", "titulo": "Fecha", "ancho": 13, "rol": "fecha", "editable": True},
            {"clave": "hora", "titulo": "Hora", "ancho": 9, "rol": "hora", "editable": True}]
    if t in TIPOS_MEDIDA:
        n = 1 if t == "imr" else int(v["n"])
        unidad = f" ({v['unidad']})" if v.get("unidad") else ""
        for i in range(n):
            cols.append({"clave": f"v{i + 1}", "titulo": ("Valor" if n == 1 else f"Unidad {i + 1}") + unidad,
                         "ancho": 13, "rol": "valor", "editable": True})
        if n > 1:
            cols += [{"clave": "promedio", "titulo": "Promedio", "ancho": 12, "rol": "calculo", "editable": False},
                     {"clave": "rango", "titulo": "Rango", "ancho": 10, "rol": "calculo", "editable": False}]
    elif t in ("p", "np"):
        cols += [{"clave": "revisadas", "titulo": "Revisadas", "ancho": 12, "rol": "revisadas", "editable": t == "p"},
                 {"clave": "conteo", "titulo": "Defectuosas", "ancho": 13, "rol": "conteo", "editable": True},
                 {"clave": "pct", "titulo": "% defectuosas", "ancho": 14, "rol": "calculo", "editable": False}]
    elif t == "u":
        cols += [{"clave": "revisadas", "titulo": "Unidades revisadas", "ancho": 18, "rol": "revisadas", "editable": True},
                 {"clave": "conteo", "titulo": "Fallas", "ancho": 10, "rol": "conteo", "editable": True},
                 {"clave": "por_unidad", "titulo": "Fallas por unidad", "ancho": 17, "rol": "calculo", "editable": False}]
    else:  # c
        cols.append({"clave": "conteo", "titulo": "Fallas", "ancho": 10, "rol": "conteo", "editable": True})
    if opciones.get("lote", True):
        cols.append({"clave": "lote", "titulo": "Lote", "ancho": 14, "rol": "lote", "editable": True})
    if opciones.get("operario", True):
        cols.append({"clave": "operario", "titulo": "Operario", "ancho": 16, "rol": "operario", "editable": True})
    if opciones.get("observaciones", True):
        cols.append({"clave": "obs", "titulo": "Observaciones", "ancho": 34, "rol": "obs", "editable": True})
    for i, c in enumerate(cols, start=1):
        c["col"] = i
    return cols


def _nombre_hoja(nombre: str, usados: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", " ", nombre).strip()[:28] or "Variable"
    if base == HOJA_META or base.lower() == "instrucciones":
        base += " (datos)"
    hoja, k = base, 2
    while hoja.lower() in usados:
        hoja = f"{base[:26]} {k}"
        k += 1
    usados.add(hoja.lower())
    return hoja


def _num(x, d: int = 2) -> str:
    return "—" if x is None else f"{x:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")


# ---------------------------------------------------------------------------
# Construcción del libro
# ---------------------------------------------------------------------------

def construir_plantilla(spec: dict) -> bytes:
    """Arma el libro Excel de la plantilla y devuelve sus bytes (.xlsx)."""
    wb = Workbook()
    instr = wb.active
    instr.title = "Instrucciones"
    opciones = spec.get("opciones") or {}
    usados = {"instrucciones", HOJA_META}
    meta = {"version": VERSION, "id": spec["id"], "generada": spec.get("generada"), "proceso": spec["proceso"],
            "opciones": opciones, "variables": []}
    for v in spec["variables"]:
        hoja = _nombre_hoja(v["nombre"], usados)
        ws = wb.create_sheet(hoja)
        meta["variables"].append(_hoja_variable(ws, v, spec, opciones))
    _hoja_instrucciones(instr, spec, meta)
    oculta = wb.create_sheet(HOJA_META)
    oculta["A1"] = json.dumps(meta, ensure_ascii=False)
    oculta.sheet_state = "veryHidden"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _estilos():
    borde = Side(style="thin", color="C0C8CB")
    return {
        "titulo": Font(name=F_TITULO, size=18, bold=True, color=PETROLEO),
        "sub": Font(name=F_TEXTO, size=10, color=GRIS),
        "enc": Font(name=F_TEXTO, size=10, bold=True, color="FFFFFF"),
        "enc_fondo": PatternFill("solid", fgColor=PETROLEO),
        "banda": Font(name=F_TEXTO, size=10, bold=True, color=TINTA),
        "banda_fondo": PatternFill("solid", fgColor=FONDO_BANDA),
        "texto": Font(name=F_TEXTO, size=10, color=TINTA),
        "calc": Font(name=F_TEXTO, size=10, color=GRIS, italic=True),
        "calc_fondo": PatternFill("solid", fgColor=CALC_FONDO),
        "alterno": PatternFill("solid", fgColor=FONDO_ALTERNO),
        "borde": Border(bottom=borde),
        # En el formato condicional Excel toma el color de bgColor: se fijan ambos.
        "ambar": PatternFill("solid", fgColor=AMBAR_FONDO, bgColor=AMBAR_FONDO),
    }


def _hoja_variable(ws, v: dict, spec: dict, opciones: dict) -> dict:
    """Dibuja la hoja de una variable y devuelve su descripción para la hoja oculta."""
    E = _estilos()
    cols = columnas_de(v, opciones)
    ultima = get_column_letter(len(cols))
    t = v["tipo_carta"]
    d = int(v.get("decimales", 2))
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = PETROLEO

    # Encabezado de la hoja
    ws["A1"] = v["nombre"]
    ws["A1"].font = E["titulo"]
    proc = spec["proceso"]
    partes = [f"Proceso: {proc['nombre']}" + (f" ({proc['linea']})" if proc.get("linea") else ""),
              f"Qué se registra: {NOMBRE_TIPO[t]}"]
    if t in TIPOS_MEDIDA:
        partes.append(f"{1 if t == 'imr' else v['n']} {'unidad' if t == 'imr' else 'unidades'} por muestra")
    elif t in ("p", "np", "u"):
        partes.append(f"{v['n']} unidades revisadas por muestra")
    ws["A2"] = " · ".join(partes)
    ws["A2"].font = E["sub"]
    if t in TIPOS_MEDIDA and (v.get("lei") is not None or v.get("les") is not None):
        acept = []
        if v.get("lei") is not None:
            acept.append(f"mínimo {_num(v['lei'], d)}")
        if v.get("objetivo") is not None:
            acept.append(f"ideal {_num(v['objetivo'], d)}")
        if v.get("les") is not None:
            acept.append(f"máximo {_num(v['les'], d)}")
        ws["A3"] = f"Valores aceptados: {' · '.join(acept)} {v.get('unidad') or ''}. Las celdas fuera de lo aceptado se pintan de ámbar."
    else:
        ws["A3"] = "Escribe solo en las celdas blancas. Las filas vacías se ignoran al subir el archivo."
    ws["A3"].font = E["sub"]
    for f in (1, 2, 3):
        ws.merge_cells(f"A{f}:{ultima}{f}")
    ws.row_dimensions[1].height = 28

    # Encabezado de columnas
    for c in cols:
        celda = ws.cell(FILA_ENCABEZADO, c["col"], c["titulo"])
        celda.font, celda.fill = E["enc"], E["enc_fondo"]
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(c["col"])].width = c["ancho"]
    ws.row_dimensions[FILA_ENCABEZADO].height = 30

    # Filas de datos en dos bloques
    filas, fila = [], FILA_ENCABEZADO + 1
    inicio = datetime.fromisoformat(v["fecha_inicio"]) if v.get("fecha_inicio") else datetime.now().replace(
        minute=0, second=0, microsecond=0)
    numero = int(v.get("inicio_numero", 1))
    paso = timedelta(minutes=int(v.get("frecuencia_min") or 60))
    rangos: list[tuple[int, int]] = []
    k = 0
    for fase, titulo, cantidad in (("I", "Para establecer los límites normales (Fase I)", int(v.get("fase_i", 0))),
                                   ("II", "Monitoreo: se comparan con los límites fijados (Fase II)", int(v.get("fase_ii", 0)))):
        if cantidad <= 0:
            continue
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=len(cols))
        b = ws.cell(fila, 1, f"{titulo} · {cantidad} muestras")
        b.font, b.fill = E["banda"], E["banda_fondo"]
        fila += 1
        desde = fila
        for _ in range(cantidad):
            momento = inicio + k * paso
            for c in cols:
                celda = ws.cell(fila, c["col"])
                celda.font = E["texto"]
                celda.border = E["borde"]
                if k % 2:
                    celda.fill = E["alterno"]
                if c["editable"]:
                    celda.protection = Protection(locked=False)
                if c["rol"] == "numero":
                    celda.value = numero
                    celda.alignment = Alignment(horizontal="center")
                elif c["rol"] == "fecha":
                    celda.value = momento.date()
                    celda.number_format = "dd/mm/yyyy"
                elif c["rol"] == "hora":
                    celda.value = momento.time()
                    celda.number_format = "hh:mm"
                elif c["rol"] == "valor":
                    celda.number_format = "0" + ("." + "0" * d if d else "")
                elif c["rol"] == "revisadas":
                    celda.value = int(v["n"])
                    celda.number_format = "0"
                elif c["rol"] == "conteo":
                    celda.number_format = "0"
                elif c["rol"] == "calculo":
                    celda.font, celda.fill = E["calc"], E["calc_fondo"]
                    celda.value, celda.number_format = _formula(c["clave"], cols, fila, d)
            filas.append({"fila": fila, "numero": numero, "fase": fase})
            numero += 1
            fila += 1
            k += 1
        rangos.append((desde, fila - 1))

    _validaciones(ws, v, cols, rangos, E)
    ws.freeze_panes = f"D{FILA_ENCABEZADO + 1}"  # fijas: encabezado y columnas Muestra/Fecha/Hora
    # Impresión (para llenarla a mano en planta): horizontal, al ancho de la hoja, encabezado en cada página.
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.print_title_rows = f"{FILA_ENCABEZADO}:{FILA_ENCABEZADO}"
    ws.page_margins.left = ws.page_margins.right = 0.4
    # Solo se escriben las celdas de datos; se permite ajustar anchos y altos. Sin contraseña.
    ws.protection.sheet = True
    ws.protection.formatColumns = False
    ws.protection.formatRows = False
    ws.protection.formatCells = False
    return {"clave": v["clave"], "id": v.get("id"), "hoja": ws.title, "nombre": v["nombre"], "unidad": v.get("unidad"),
            "tipo_carta": t, "n": int(v["n"]), "decimales": d, "lei": v.get("lei"), "objetivo": v.get("objetivo"),
            "les": v.get("les"), "frecuencia_min": v.get("frecuencia_min"), "nueva": v.get("id") is None,
            "columnas": [{k2: c[k2] for k2 in ("clave", "titulo", "rol", "col")} for c in cols], "filas": filas}


def _formula(clave: str, cols: list[dict], fila: int, d: int) -> tuple[str, str]:
    letra = {c["clave"]: get_column_letter(c["col"]) for c in cols}
    fmt = "0" + ("." + "0" * (d + 1))
    if clave in ("promedio", "rango"):
        valores = [c for c in cols if c["rol"] == "valor"]
        rango = f"{get_column_letter(valores[0]['col'])}{fila}:{get_column_letter(valores[-1]['col'])}{fila}"
        n = len(valores)
        if clave == "promedio":
            return f'=IF(COUNT({rango})={n},AVERAGE({rango}),"")', fmt
        return f'=IF(COUNT({rango})={n},MAX({rango})-MIN({rango}),"")', "0" + ("." + "0" * d if d else "")
    r, x = f"{letra['revisadas']}{fila}", f"{letra['conteo']}{fila}"
    if clave == "pct":
        return f'=IF(AND(ISNUMBER({r}),{r}>0,ISNUMBER({x})),{x}/{r},"")', "0.0%"
    return f'=IF(AND(ISNUMBER({r}),{r}>0,ISNUMBER({x})),{x}/{r},"")', "0.00"


def _validaciones(ws, v: dict, cols: list[dict], rangos: list[tuple[int, int]], E: dict) -> None:
    """Validación de datos de Excel (mientras se escribe) y formato condicional de especificación."""
    if not rangos:
        return
    por_rol = {}
    for c in cols:
        por_rol.setdefault(c["rol"], []).append(get_column_letter(c["col"]))

    def sqref(letras):
        return " ".join(f"{l}{a}:{l}{b}" for l in letras for a, b in rangos)

    def agregar(dv, letras):
        dv.error_title, dv.prompt_title = "Valor no válido", "CEP"
        ws.add_data_validation(dv)
        for rango in sqref(letras).split():  # DataValidation.add acepta un rango por llamada
            dv.add(rango)

    if "valor" in por_rol:
        dv = DataValidation(type="decimal", operator="between", formula1="-1E+15", formula2="1E+15", allow_blank=True,
                            error="Escribe solo un número (puedes usar coma decimal).", showErrorMessage=True)
        agregar(dv, por_rol["valor"])
        lei, les = v.get("lei"), v.get("les")
        rango_valores = sqref(por_rol["valor"])
        # Regla con fórmula y ISNUMBER: con «menor que» simple Excel pinta también las celdas vacías (vacía = 0).
        celda = f"{por_rol['valor'][0]}{rangos[0][0]}"
        condiciones = ([f"{celda}<{lei}"] if lei is not None else []) + ([f"{celda}>{les}"] if les is not None else [])
        if condiciones:
            formula = f"AND(ISNUMBER({celda}),OR({','.join(condiciones)}))"
            ws.conditional_formatting.add(rango_valores, FormulaRule(formula=[formula], fill=E["ambar"]))
    if "revisadas" in por_rol:
        dv = DataValidation(type="whole", operator="greaterThan", formula1="0", allow_blank=True,
                            error="Las unidades revisadas deben ser un número entero mayor que cero.", showErrorMessage=True)
        agregar(dv, por_rol["revisadas"])
    if "conteo" in por_rol:
        x = f"{por_rol['conteo'][0]}{rangos[0][0]}"
        if "revisadas" in por_rol and v["tipo_carta"] in ("p", "np"):
            r = f"{por_rol['revisadas'][0]}{rangos[0][0]}"
            dv = DataValidation(type="custom", formula1=f"AND(ISNUMBER({x}),{x}>=0,{x}=INT({x}),{x}<={r})", allow_blank=True,
                                error="Escribe un número entero entre 0 y la cantidad de unidades revisadas.",
                                showErrorMessage=True)
        else:
            dv = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="0", allow_blank=True,
                                error="Escribe un número entero (0 o más).", showErrorMessage=True)
        agregar(dv, por_rol["conteo"])
    if "fecha" in por_rol:
        dv = DataValidation(type="date", operator="greaterThan", formula1="36526", allow_blank=True,  # > 01/01/2000
                            error="Escribe una fecha (dd/mm/aaaa).", showErrorMessage=True)
        agregar(dv, por_rol["fecha"])
    if "hora" in por_rol:
        dv = DataValidation(type="time", operator="between", formula1="0", formula2="0.999988", allow_blank=True,
                            error="Escribe una hora (hh:mm).", showErrorMessage=True)
        agregar(dv, por_rol["hora"])


def _hoja_instrucciones(ws, spec: dict, meta: dict) -> None:
    E = _estilos()
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 100
    ws["B2"] = "Plantilla de carga de datos"
    ws["B2"].font = E["titulo"]
    proc = spec["proceso"]
    ws["B3"] = f"Proceso: {proc['nombre']}" + (f" ({proc['linea']})" if proc.get("linea") else "") + \
               f" · Generada el {datetime.fromisoformat(spec['generada']).strftime('%d/%m/%Y %H:%M') if spec.get('generada') else ''}"
    ws["B3"].font = E["sub"]
    lineas = [
        ("Cómo llenarla", True),
        ("1. Cada hoja corresponde a una variable. Las muestras ya están numeradas.", False),
        ("2. Escribe solo en las celdas blancas. Las grises (promedio, rango, porcentaje) se calculan solas.", False),
        ("3. La fecha y la hora vienen sugeridas según la frecuencia; corrígelas si la muestra se tomó en otro momento.", False),
        ("4. Puedes usar coma decimal. Si un valor queda en ámbar, está fuera de lo que acepta el cliente: revisa que esté bien escrito.", False),
        ("5. No cambies los nombres de las hojas ni de las columnas: la aplicación los usa para leer el archivo.", False),
        ("6. Puedes subir el archivo varias veces a medida que lo llenas: las filas vacías se ignoran y las muestras ya cargadas no se duplican.", False),
        ("", False),
        ("Los dos bloques de cada hoja", True),
        ("«Para establecer los límites normales» (Fase I): las primeras muestras, con las que se conoce cómo se comporta el proceso.", False),
        ("«Monitoreo» (Fase II): las muestras que se comparan con los límites ya fijados.", False),
        ("", False),
        ("Variables incluidas", True),
    ]
    for v in meta["variables"]:
        fi = sum(f["fase"] == "I" for f in v["filas"])
        fii = sum(f["fase"] == "II" for f in v["filas"])
        lineas.append((f"• {v['nombre']} — hoja «{v['hoja']}»: {NOMBRE_TIPO[v['tipo_carta']].lower()}, {fi} muestras para "
                       f"establecer límites y {fii} de monitoreo" + (" (variable nueva: se creará al subir el archivo)."
                                                                     if v["nueva"] else "."), False))
    lineas += [("", False), ("Cuando termines", True),
               ("En la aplicación: Ingeniería → Plantilla de carga → «Subir plantilla llenada». Antes de guardar verás un "
                "informe con lo que se cargará y cualquier error encontrado, con la hoja y la muestra.", False)]
    for i, (texto, es_titulo) in enumerate(lineas, start=5):
        c = ws.cell(i, 2, texto)
        c.font = Font(name=F_TITULO if es_titulo else F_TEXTO, size=13 if es_titulo else 10, bold=es_titulo,
                      color=PETROLEO if es_titulo else TINTA)
        c.alignment = Alignment(wrap_text=True, vertical="top")


# ---------------------------------------------------------------------------
# Lectura y validación
# ---------------------------------------------------------------------------

def _a_numero(x):
    """Número de una celda (acepta texto con coma decimal). None si está vacía; NaN si no es número."""
    if x is None or (isinstance(x, str) and not x.strip()):
        return None
    if isinstance(x, bool):
        return math.nan
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).strip().replace(" ", "").replace(",", "."))
    except ValueError:
        return math.nan


def _a_fecha(x) -> date | None | bool:
    if x is None or x == "":
        return None
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(str(x).strip(), fmt).date()
        except ValueError:
            pass
    return False


def _a_hora(x) -> time | None | bool:
    if x is None or x == "":
        return None
    if isinstance(x, datetime):
        return x.time()
    if isinstance(x, time):
        return x
    if isinstance(x, (int, float)) and 0 <= x < 1:  # fracción de día de Excel
        s = round(x * 86400)
        return time(s // 3600, (s % 3600) // 60)
    for fmt in ("%H:%M", "%H:%M:%S", "%H.%M"):
        try:
            return datetime.strptime(str(x).strip(), fmt).time()
        except ValueError:
            pass
    return False


def leer_meta(datos: bytes):
    """Abre el libro y devuelve (libro, meta). Lanza ErrorPlantilla si no es una plantilla de CEP."""
    try:
        wb = load_workbook(io.BytesIO(datos), data_only=True)
    except Exception as e:  # archivo dañado o de otro formato
        raise ErrorPlantilla("No se pudo abrir el archivo. Debe ser la plantilla .xlsx descargada de la aplicación.") from e
    if HOJA_META not in wb.sheetnames:
        raise ErrorPlantilla("Este archivo no es una plantilla generada por CEP. Descarga la plantilla desde "
                             "Ingeniería → Plantilla de carga y copia allí tus datos.")
    try:
        meta = json.loads(wb[HOJA_META]["A1"].value)
    except (TypeError, ValueError) as e:
        raise ErrorPlantilla("La plantilla está dañada: falta su descripción interna. Descarga una nueva.") from e
    if meta.get("version") != VERSION:
        raise ErrorPlantilla("La plantilla es de otra versión de la aplicación. Descarga una nueva.")
    return wb, meta


def leer_plantilla(datos: bytes) -> dict:
    """Lee una plantilla llenada: muestras completas, errores y avisos por variable."""
    wb, meta = leer_meta(datos)
    salida = {"id": meta["id"], "proceso": meta["proceso"], "variables": []}
    for v in meta["variables"]:
        salida["variables"].append(_leer_variable(wb, v))
    return salida


def _leer_variable(wb, v: dict) -> dict:
    res = {k: v[k] for k in ("clave", "id", "hoja", "nombre", "unidad", "tipo_carta", "n", "decimales", "lei",
                             "objetivo", "les", "frecuencia_min", "nueva")}
    res.update({"muestras": [], "errores": [], "avisos": [], "vacias": 0})
    if v["hoja"] not in wb.sheetnames:
        res["errores"].append({"numero": None, "texto": f"No se encontró la hoja «{v['hoja']}». No cambies los nombres de las hojas."})
        return res
    ws = wb[v["hoja"]]
    for c in v["columnas"]:
        if (ws.cell(FILA_ENCABEZADO, c["col"]).value or "").strip() != c["titulo"]:
            res["errores"].append({"numero": None, "texto": f"En la hoja «{v['hoja']}» se cambió o movió la columna «{c['titulo']}». "
                                                            "Usa la plantilla original sin modificar las columnas."})
            return res
    cols = {c["clave"]: c for c in v["columnas"]}
    valores_cols = [c for c in v["columnas"] if c["rol"] == "valor"]
    entrada = [c for c in v["columnas"] if c["rol"] in ("valor", "conteo")]
    t = v["tipo_carta"]
    ultimo_momento = None
    for f in v["filas"]:
        fila, numero = f["fila"], f["numero"]
        if ws.cell(fila, 1).value != numero:
            res["errores"].append({"numero": numero, "texto": f"Muestra {numero}: se cambió el número de la fila. No insertes ni borres filas."})
            continue
        crudos = [ws.cell(fila, c["col"]).value for c in entrada]
        llenos = [x for x in crudos if x is not None and str(x).strip() != ""]
        if not llenos:
            res["vacias"] += 1
            continue

        def err(texto):
            res["errores"].append({"numero": numero, "fase": f["fase"], "texto": f"Muestra {numero}: {texto}"})

        muestra = {"numero": numero, "fase": f["fase"], "fila": fila}
        if valores_cols:
            nums = [_a_numero(ws.cell(fila, c["col"]).value) for c in valores_cols]
            if any(isinstance(x, float) and math.isnan(x) for x in nums):
                malos = [c["titulo"] for c, x in zip(valores_cols, nums) if isinstance(x, float) and math.isnan(x)]
                err(f"no es un número en {', '.join(malos)}.")
                continue
            vacias = [c["titulo"] for c, x in zip(valores_cols, nums) if x is None]
            if vacias and not (t == "xbar_s" and len(vacias) <= len(nums) - 2):
                err(f"faltan valores en {', '.join(vacias)} (la muestra lleva {len(nums)}).")
                continue
            muestra["valores"] = [x for x in nums if x is not None]
            fuera = [x for x in muestra["valores"]
                     if (v.get("lei") is not None and x < v["lei"]) or (v.get("les") is not None and x > v["les"])]
            if fuera:
                res["avisos"].append({"numero": numero, "texto": f"Muestra {numero}: {len(fuera)} "
                                      f"{'valor quedó' if len(fuera) == 1 else 'valores quedaron'} fuera de lo aceptado."})
            if v.get("lei") is not None and v.get("les") is not None:
                tol = v["les"] - v["lei"]
                raros = [x for x in muestra["valores"] if x < v["lei"] - tol or x > v["les"] + tol]
                if raros:
                    res["avisos"].append({"numero": numero, "texto": f"Muestra {numero}: {', '.join(_num(x, v['decimales']) for x in raros)} "
                                          "está muy lejos de lo habitual. Revisa que esté bien escrito."})
        else:
            conteo = _a_numero(ws.cell(fila, cols["conteo"]["col"]).value)
            if conteo is None or math.isnan(conteo) or conteo < 0 or conteo != int(conteo):
                err(f"«{cols['conteo']['titulo']}» debe ser un número entero (0 o más).")
                continue
            muestra["conteo"] = int(conteo)
            if "revisadas" in cols:
                rev = _a_numero(ws.cell(fila, cols["revisadas"]["col"]).value)
                if rev is None or math.isnan(rev) or rev <= 0 or rev != int(rev):
                    err(f"«{cols['revisadas']['titulo']}» debe ser un número entero mayor que cero.")
                    continue
                if t == "np" and int(rev) != v["n"]:
                    err(f"en esta variable siempre se revisan {v['n']} unidades.")
                    continue
                if t in ("p", "np") and conteo > rev:
                    err(f"hay más defectuosas ({int(conteo)}) que unidades revisadas ({int(rev)}).")
                    continue
                muestra["tamano"] = int(rev)
        fecha = _a_fecha(ws.cell(fila, cols["fecha"]["col"]).value)
        hora = _a_hora(ws.cell(fila, cols["hora"]["col"]).value)
        if fecha is False or hora is False:
            err("la fecha (dd/mm/aaaa) o la hora (hh:mm) no se entienden.")
            continue
        if fecha is None:
            err("falta la fecha.")
            continue
        momento = datetime.combine(fecha, hora or time(0, 0))
        if ultimo_momento and momento < ultimo_momento:
            res["avisos"].append({"numero": numero, "texto": f"Muestra {numero}: la fecha y hora son anteriores a las de la muestra previa."})
        ultimo_momento = momento
        muestra["timestamp"] = momento.isoformat()
        for rol in ("lote", "operario", "obs"):
            if rol in cols:
                x = ws.cell(fila, cols[rol]["col"]).value
                muestra[rol] = str(x).strip() if x is not None and str(x).strip() else None
        res["muestras"].append(muestra)
    # Datos escritos debajo de la última fila prevista (filas agregadas a mano)
    ultima = v["filas"][-1]["fila"] if v["filas"] else FILA_ENCABEZADO
    for fila in range(ultima + 1, ultima + 30):
        if any(ws.cell(fila, c["col"]).value not in (None, "") for c in entrada):
            res["avisos"].append({"numero": None, "texto": f"Hay datos debajo de la última muestra de la hoja «{v['hoja']}» "
                                                           f"(fila {fila}); no se cargan. Descarga una plantilla con más muestras."})
            break
    return res
