"""Informe PDF con LaTeX (Fase E): escape de textos, contenido descriptivo, compilación y respaldo.

Las pruebas que compilan se omiten si el equipo no tiene pdflatex.
"""
import pytest
from fastapi.testclient import TestClient

from app.core import graficos_atributos as ga
from app.core import reporte_latex as rl
from app.db import sesion
from tests.test_reportes_archivos import contenido  # noqa: F401  (fixture compartido, sin base de datos)

HAY_LATEX = bool(rl.disponible()["pdflatex"])
requiere_latex = pytest.mark.skipif(not HAY_LATEX, reason="pdflatex no está instalado")


# ---------------------------------------------------------------------------
# Escape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto,esperado", [
    ("50% & $10 #1 a_b {x}", r"50\% \& \$10 \#1 a\_b \{x\}"),
    ("σ = 0,8", r"$\sigma$ = 0,8"),
    ("X̄ y σ̂", r"$\bar{X}$ y $\hat{\sigma}$"),
    ("d₂ ≥ 1,33", r"d\textsubscript{2} $\geq$ 1,33"),
    ("Año ñandú «ok» — fin", "Año ñandú «ok» — fin"),
    ("alerta ⚠ ✓", "alerta  "),
    (None, "—"),
])
def test_escape(texto, esperado):
    assert rl.esc(texto) == esperado


# ---------------------------------------------------------------------------
# Contenido del .tex (sin compilar)
# ---------------------------------------------------------------------------

def test_tex_descriptivo_y_completo(contenido, tmp_path):  # noqa: F811
    tex = rl.generar_tex(contenido, tmp_path)
    for seccion in ("En pocas palabras", "Indicadores principales", "Cómo se comportó el proceso",
                    "Cumplimiento de lo que acepta el cliente", "Verificación de los datos", "Inspección de lotes",
                    "Historial de cambios", "Glosario"):
        assert seccion in tex, seccion
    assert (tmp_path / "carta.png").exists() and (tmp_path / "histograma.png").exists()
    # Solo describe: sin recomendaciones ni índices fuera del alcance del curso.
    for prohibido in ("Investigue", "Registre la causa", "excluya", "debería", "Ppk", "Pp "):
        assert prohibido not in tex, prohibido
    assert tex.count("recomendaciones") == 1  # solo la aclaración final
    assert r"\usepackage{lmodern}" in tex  # fuente predeterminada de LaTeX (Latin Modern)
    assert "Cpk = 1,63" in tex  # coma decimal
    assert "Plano rev. B" in tex and "Máximo aceptado" in tex  # historial en palabras


def test_tex_solo_modulos_pedidos(contenido, tmp_path):  # noqa: F811
    tex = rl.generar_tex({**contenido, "modulos": ["resumen"]}, tmp_path)
    assert "En pocas palabras" in tex and "Glosario" in tex
    assert "Historial de cambios" not in tex and "Inspección de lotes" not in tex
    assert "Verificación de los datos" not in tex


def test_tex_atributos(contenido, tmp_path):  # noqa: F811
    conteos, tamanos = [12, 15, 8, 10, 4, 7, 16, 9, 14, 10], [50] * 10
    carta = ga.calcular_carta_atributos("p", conteos, tamanos)
    carta["etiquetas"] = list(range(1, 11))
    carta["subgrupos"] = [{"numero": i + 1, "timestamp": "2026-11-20T06:00:00", "conteo": c, "tamano": 50}
                          for i, c in enumerate(conteos)]
    v = {"nombre": "Envases defectuosos", "unidad": "envases", "tipo_carta": "p", "n": 50, "fase": "I", "decimales": 0,
         "lei": None, "les": None, "objetivo": None, "frecuencia_min": 60, "k_sigma": 3.0}
    plan = {"textos": {"carga": "Se toma 1 muestra por hora.", "deteccion": "Si el nivel de defectos pasa de 20 % a 40 %…",
                       "falsa_alarma": "Una falsa alarma cada 385 muestras."}}
    tex = rl.generar_tex({**contenido, "variable": v, "carta": carta, "capacidad": None, "supuestos": None,
                          "plan": plan}, tmp_path)
    assert "de las unidades revisadas fue defectuoso" in tex
    assert "Plan de muestreo" in tex and "1 muestra por hora" in tex
    assert "Cumplimiento de lo que acepta el cliente" not in tex


def test_estado_general():
    base = {"variable": {"fase": "II"}, "capacidad": None}
    assert rl._estado({**base, "carta": None})["titulo"].startswith("Todavía no hay datos")
    # Fase II recién iniciada: sin muestras no se afirma que el proceso "se mantuvo estable".
    vacia = {"puntos_con_senal": [], "cartas": {}, "subgrupos": [], "limites_congelados": {"m_usados": 19}}
    e = rl._estado({**base, "carta": vacia})
    assert e["color"] == "neutro" and "19 muestras" in e["texto"]
    carta = {"puntos_con_senal": [], "cartas": {}, "subgrupos": [{"numero": 1}]}
    assert rl._estado({**base, "carta": carta})["color"] == "verde"
    assert rl._estado({**base, "carta": {**carta, "puntos_con_senal": [3]}})["color"] == "rojo"
    f1 = {"variable": {"fase": "I"}, "capacidad": None, "carta": {**carta, "puntos_con_senal": [3]}}
    assert rl._estado(f1)["color"] == "ambar"
    marginal = {**base, "carta": carta, "capacidad": {"veredicto": {"nivel": "marginal"}}}
    assert "poco margen" in rl._estado(marginal)["titulo"]


# ---------------------------------------------------------------------------
# Compilación y API
# ---------------------------------------------------------------------------

@requiere_latex
def test_compila_pdf(contenido):  # noqa: F811
    pdf = rl.construir_pdf_latex(contenido)
    assert pdf[:5] == b"%PDF-" and len(pdf) > 50_000


def test_sin_latex_lanza_error(contenido, monkeypatch):  # noqa: F811
    monkeypatch.setenv("CEP_SIN_LATEX", "1")
    with pytest.raises(rl.ErrorLatex):
        rl.construir_pdf_latex(contenido)


@pytest.fixture
def c(tmp_path):
    sesion.configurar(f"sqlite:///{(tmp_path / 'latex.db').as_posix()}")
    from app.main import app

    with TestClient(app) as cliente:
        yield cliente


def test_vista_previa_con_textos_del_informe(c):
    prev = c.post("/api/reportes/vista-previa", json={"variable_id": 2, "plantilla": "integral"}).json()
    inf = prev["informe"]
    assert inf["estado"]["color"] == "ambar"  # señales en Fase I
    assert any("defectuoso" in h for h in inf["hallazgos"])
    assert inf["indicadores"][0][0] == "Muestras analizadas"


def test_api_usa_respaldo_sin_latex(c, monkeypatch):
    monkeypatch.setenv("CEP_SIN_LATEX", "1")
    r = c.post("/api/reportes/generar", json={"variable_id": 1, "plantilla": "control", "formato": "pdf"}).json()
    assert r["motor"] == "reportlab" and "pdflatex" in r["aviso"]
    assert c.get("/api/reportes/plantillas").json()["latex"] is False


def test_respaldo_y_excel_sin_recomendaciones(c):
    from app.api.reportes import armar_contenido, conclusiones_descriptivas
    from app.api.util import limpiar_json

    db = sesion.SesionLocal()
    try:
        from app.api import servicios as sv
        contenido = limpiar_json(armar_contenido(db, sv.obtener_variable(db, 2), "integral", None, "Ana"))
    finally:
        db.close()
    concl = conclusiones_descriptivas(contenido)
    assert concl[0]["seccion"] == "sintesis" and concl[0]["nivel"] == "advertencia"
    textos = " ".join(x["texto"] for x in concl)
    for prohibido in ("Investigue", "Registre", "excluya", "recalcule"):
        assert prohibido not in textos


@requiere_latex
def test_api_genera_con_latex(c):
    r = c.post("/api/reportes/generar", json={"variable_id": 1, "plantilla": "integral", "formato": "pdf"}).json()
    assert r["motor"] == "latex" and r["aviso"] is None
    pdf = c.get(f"/api/reportes/{r['id']}/descargar").content
    assert pdf[:5] == b"%PDF-"
    assert c.get(f"/api/reportes/{r['id']}/verificar").json()["integro"]
