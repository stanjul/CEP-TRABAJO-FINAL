"""Reglas de Nelson / Western Electric con secuencias sintéticas (LC = 0, σ = 1, límites ±3)."""
import pytest

from app.core.reglas import PRESETS, evaluar_reglas


def evaluar(valores, reglas, incluidos=None):
    return evaluar_reglas(valores, 0.0, 3.0, -3.0, 1.0, reglas, incluidos)


def indices(viol, regla):
    return [v["indice"] for v in viol if v["regla"] == regla]


def test_n1_punto_fuera():
    v = evaluar([0, 0.5, 3.2, -0.1, -3.5], ["N1"])
    assert indices(v, "N1") == [2, 4]
    assert [x["lado"] for x in v] == ["+", "-"]


def test_n1_justo_en_el_limite_no_dispara():
    assert evaluar([3.0, -3.0], ["N1"]) == []


def test_n2_nueve_del_mismo_lado():
    serie = [0.5] * 9
    assert indices(evaluar(serie, ["N2"]), "N2") == [8]
    assert evaluar([0.5] * 8, ["N2"]) == []


def test_n2_punto_en_lc_rompe_racha():
    serie = [0.5] * 5 + [0.0] + [0.5] * 5
    assert evaluar(serie, ["N2"]) == []


def test_we4_ocho_del_mismo_lado():
    assert indices(evaluar([-0.2] * 8, ["WE4"]), "WE4") == [7]


def test_n3_tendencia_de_seis():
    assert indices(evaluar([-1, -0.5, 0, 0.5, 1, 1.5], ["N3"]), "N3") == [5]
    assert evaluar([-1, -0.5, 0, 0.5, 1], ["N3"]) == []
    # Un empate rompe la tendencia.
    assert evaluar([-1, -0.5, 0, 0, 1, 1.5], ["N3"]) == []


def test_n4_catorce_alternados():
    serie = [0.5 if i % 2 else -0.5 for i in range(14)]
    assert indices(evaluar(serie, ["N4"]), "N4") == [13]
    assert evaluar(serie[:13], ["N4"]) == []


def test_n5_dos_de_tres_en_zona_a():
    v = evaluar([0, 2.5, 0.1, 2.2], ["N5"])
    assert indices(v, "N5") == [3]
    assert v[0]["puntos"] == [1, 3]
    # Lados opuestos no cuentan.
    assert evaluar([2.5, 0, -2.5], ["N5"]) == []


def test_n6_cuatro_de_cinco_en_zona_b():
    assert indices(evaluar([1.5, 1.2, 0.2, 1.1, 1.8], ["N6"]), "N6") == [4]


def test_n7_estratificacion():
    assert indices(evaluar([0.1, -0.1] * 7 + [0.2], ["N7"]), "N7") == [14]


def test_n8_mezcla():
    assert indices(evaluar([1.5, -1.5] * 4, ["N8"]), "N8") == [7]


def test_excluidos_no_participan_y_conservan_indices():
    serie = [0.5] * 4 + [5.0] + [0.5] * 5
    incl = [True] * 10
    incl[4] = False
    v = evaluar(serie, ["N1", "N2"], incl)
    assert indices(v, "N1") == []
    assert indices(v, "N2") == [9]  # 9 puntos incluidos del mismo lado
    assert 4 not in v[0]["puntos"]


def test_inicio_de_racha():
    v = evaluar([0.5] * 11, ["N2"])
    assert [x["inicio"] for x in v] == [True, False, False]


def test_limites_variables():
    # Límites por punto (como en la carta p con n variable).
    v = evaluar_reglas([0.3, 0.3], 0.2, [0.35, 0.28], [0.05, 0.12], [0.05, 0.027], ["N1"])
    assert indices(v, "N1") == [1]


def test_presets():
    assert PRESETS["western_electric"] == ["N1", "N5", "N6", "WE4"]
    assert len(PRESETS["nelson"]) == 8


@pytest.mark.parametrize("regla", PRESETS["nelson"])
def test_serie_aleatoria_estable_sin_n1(regla):
    import numpy as np
    rng = np.random.default_rng(1)
    v = evaluar(rng.normal(0, 0.5, 30), [regla])
    if regla == "N1":
        assert v == []


def test_explicaciones_en_palabras_simples():
    """Cada regla tiene un texto para el operario, sin jerga (σ, LC, zona)."""
    from app.core.reglas import CATALOGO, explicar
    for rid in CATALOGO:
        texto = explicar(rid, "+")
        assert texto and "{" not in texto
        assert not any(j in texto for j in ("σ", "LCS", "LCI", " LC", "zona"))
    assert explicar("N1", "+") == "Un valor quedó por encima de los límites normales del proceso."
    assert "por debajo del promedio" in explicar("N2", "-")
    assert "bajaron" in explicar("N3", "-")
    assert explicar("XX") == ""
