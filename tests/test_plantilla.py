"""Plantilla Excel paramétrica: construcción, validaciones de Excel y lectura con errores/avisos."""
import io
from datetime import date, time

import pytest
from openpyxl import load_workbook

from app.core import plantilla as pl


def spec(**extra):
    base = {
        "id": "abc123", "generada": "2026-11-23T08:00:00",
        "proceso": {"id": 1, "nombre": "Envasado", "linea": "L-04"},
        "opciones": {"lote": True, "operario": True, "observaciones": True},
        "variables": [
            {"clave": "v1", "id": 1, "nombre": "Peso neto", "unidad": "g", "tipo_carta": "xbar_r", "n": 3, "decimales": 2,
             "lei": 495.0, "objetivo": 500.0, "les": 505.0, "frecuencia_min": 30, "inicio_numero": 1, "fase_i": 4,
             "fase_ii": 2, "fecha_inicio": "2026-11-23T06:00:00"},
            {"clave": "v2", "id": None, "nombre": "Envases defectuosos", "unidad": "", "tipo_carta": "p", "n": 50,
             "decimales": 0, "lei": None, "objetivo": None, "les": None, "frecuencia_min": 60, "inicio_numero": 1,
             "fase_i": 3, "fase_ii": 0, "fecha_inicio": "2026-11-23T06:00:00"},
        ],
    }
    base.update(extra)
    return base


def libro(datos):
    return load_workbook(io.BytesIO(datos))


def test_estructura_del_libro():
    wb = libro(pl.construir_plantilla(spec()))
    assert wb.sheetnames == ["Instrucciones", "Peso neto", "Envases defectuosos", "_cep"]
    assert wb["_cep"].sheet_state == "veryHidden"
    ws = wb["Peso neto"]
    encabezado = [c.value for c in ws[pl.FILA_ENCABEZADO]]
    assert encabezado[:8] == ["Muestra", "Fecha", "Hora", "Unidad 1 (g)", "Unidad 2 (g)", "Unidad 3 (g)", "Promedio", "Rango"]
    assert ws.protection.sheet  # protegida: solo las celdas de datos son editables
    # Bloques: banda Fase I, 4 muestras, banda Fase II, 2 muestras; fecha y hora sugeridas cada 30 min.
    assert "Fase I" in ws.cell(6, 1).value and ws.cell(7, 1).value == 1 and ws.cell(10, 1).value == 4
    assert "Monitoreo" in ws.cell(11, 1).value and ws.cell(12, 1).value == 5
    assert ws.cell(8, 3).value == time(6, 30)
    assert ws.cell(7, 4).protection.locked is False and ws.cell(7, 1).protection.locked is True
    assert ws.cell(7, 7).value.startswith("=IF(COUNT(D7:F7)=3,AVERAGE")
    assert len(ws.data_validations.dataValidation) >= 3
    p = wb["Envases defectuosos"]
    assert [c.value for c in p[pl.FILA_ENCABEZADO]][3:6] == ["Revisadas", "Defectuosas", "% defectuosas"]
    assert p.cell(7, 4).value == 50  # revisadas sugeridas = n


def test_ambar_solo_en_celdas_con_numero():
    """El formato condicional usa ISNUMBER: una celda vacía (= 0 para Excel) no se pinta como «fuera de lo aceptado».
    Verificado también abriendo el archivo en Excel 16 (las vacías quedan sin ámbar)."""
    ws = libro(pl.construir_plantilla(spec()))["Peso neto"]
    reglas = [r for rango in ws.conditional_formatting for r in rango.rules]
    assert reglas and reglas[0].formula == ["AND(ISNUMBER(D7),OR(D7<495.0,D7>505.0))"]
    assert reglas[0].dxf.fill.bgColor.rgb.endswith("FEF3C7")  # Excel toma el color de bgColor
    assert ws.page_setup.orientation == "landscape" and ws.print_title_rows == "$5:$5"


def test_nombres_de_hoja_unicos_y_validos():
    s = spec()
    s["variables"][1]["nombre"] = "Peso neto"
    s["variables"][0]["nombre"] = "Peso: neto/bruto [g]"
    wb = libro(pl.construir_plantilla(s))
    assert wb.sheetnames[1:3] == ["Peso  neto bruto  g", "Peso neto"]


def llenar(datos, celdas: dict[str, dict]):
    wb = libro(datos)
    for hoja, valores in celdas.items():
        for ref, x in valores.items():
            wb[hoja][ref] = x
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_lectura_con_errores_y_avisos():
    datos = llenar(pl.construir_plantilla(spec()), {
        "Peso neto": {
            "D7": 500.1, "E7": "499,8", "F7": 500.4,        # muestra 1 completa (texto con coma decimal)
            "D8": 500.0, "E8": 501.0,                        # muestra 2 incompleta → error
            "D9": 506.0, "E9": 500.0, "F9": 499.0,           # muestra 3 con un valor fuera de lo aceptado → aviso
            "D10": 5000, "E10": 500, "F10": 500, "I10": "L-9",  # muestra 4: valor sospechoso → aviso; lote
            "D12": "abc", "E12": 1, "F12": 1,                # muestra 5 (Fase II): no es número → error
        },
        "Envases defectuosos": {"E7": 3, "E8": 60, "E9": 2, "D9": 40, "B9": "25/11/2026", "C9": "14:30"},
    })
    r = pl.leer_plantilla(datos)
    peso, env = r["variables"]
    assert [m["numero"] for m in peso["muestras"]] == [1, 3, 4]
    assert peso["muestras"][0]["valores"] == [500.1, 499.8, 500.4]
    assert peso["muestras"][2]["lote"] == "L-9"
    assert peso["vacias"] == 1  # la muestra 6 (Fase II) está vacía
    errores = " ".join(e["texto"] for e in peso["errores"])
    assert "Muestra 2: faltan valores en Unidad 3 (g)" in errores and "Muestra 5: no es un número" in errores
    avisos = " ".join(a["texto"] for a in peso["avisos"])
    assert "Muestra 3: 1 valor quedó fuera de lo aceptado" in avisos and "Muestra 4: 5.000,00 está muy lejos" in avisos
    assert [m["conteo"] for m in env["muestras"]] == [3, 2]
    assert env["muestras"][1] == {**env["muestras"][1], "tamano": 40, "timestamp": "2026-11-25T14:30:00"}
    assert "más defectuosas (60) que unidades revisadas (50)" in env["errores"][0]["texto"]


def test_columnas_modificadas_se_detectan():
    datos = llenar(pl.construir_plantilla(spec()), {"Peso neto": {"E5": "Otra cosa", "D7": 1}})
    peso = pl.leer_plantilla(datos)["variables"][0]
    assert "se cambió o movió la columna «Unidad 2 (g)»" in peso["errores"][0]["texto"] and not peso["muestras"]


def test_datos_debajo_de_la_ultima_fila():
    datos = llenar(pl.construir_plantilla(spec()), {"Peso neto": {"D20": 500}})
    assert any("debajo de la última muestra" in a["texto"] for a in pl.leer_plantilla(datos)["variables"][0]["avisos"])


def test_no_es_plantilla():
    from openpyxl import Workbook
    buf = io.BytesIO()
    Workbook().save(buf)
    with pytest.raises(pl.ErrorPlantilla, match="no es una plantilla generada por CEP"):
        pl.leer_plantilla(buf.getvalue())
    with pytest.raises(pl.ErrorPlantilla, match="No se pudo abrir"):
        pl.leer_plantilla(b"esto no es un excel")


@pytest.mark.parametrize("tipo,titulos", [
    ("imr", ["Valor (g)"]), ("c", ["Fallas"]), ("u", ["Unidades revisadas", "Fallas", "Fallas por unidad"]),
])
def test_columnas_por_tipo(tipo, titulos):
    v = {"tipo_carta": tipo, "n": 4, "unidad": "g"}
    cols = [c["titulo"] for c in pl.columnas_de(v, {"lote": False, "operario": False, "observaciones": False})]
    assert cols == ["Muestra", "Fecha", "Hora", *titulos]


def test_lectura_conversiones():
    assert pl._a_numero("1 234,5") == 1234.5 and pl._a_numero(None) is None
    assert pl._a_fecha("05/01/2026") == date(2026, 1, 5) and pl._a_fecha("31/31/2026") is False
    assert pl._a_hora(0.5) == time(12, 0) and pl._a_hora("7:05") == time(7, 5)
