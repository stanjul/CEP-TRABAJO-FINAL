"""Cartas por variables validadas con los ejemplos resueltos de Montgomery (cap. 6)."""
import numpy as np
import pytest

from app.core import graficos_variables as gv
from tests.datos_montgomery import ANILLOS, ANILLOS_MEDIAS, ANILLOS_RANGOS, PRESTAMOS


class TestXbarRAnillos:
    """Anillos de pistón: X̿ = 74.001, R̄ = 0.023, LCS = 74.014, LCI = 73.988, LCS_R = 0.049."""

    res = gv.calcular_xbar_r(ANILLOS)

    def test_estadisticos_por_subgrupo(self):
        assert self.res["cartas"]["xbar"]["valores"] == pytest.approx(ANILLOS_MEDIAS, abs=6e-4)
        assert self.res["cartas"]["r"]["valores"] == pytest.approx(ANILLOS_RANGOS, abs=6e-4)

    def test_limites_libro(self):
        x, r = self.res["limites"]["xbar"], self.res["limites"]["r"]
        assert x["lc"] == pytest.approx(74.001, abs=5e-4)
        assert r["lc"] == pytest.approx(0.023, abs=5e-4)
        # El libro calcula con X̿ y R̄ ya redondeados (74.001 y 0.023); el valor exacto difiere
        # en la cuarta decimal (74.0146), por eso la tolerancia es de 1e-3.
        assert x["lcs"] == pytest.approx(74.014, abs=1e-3)
        assert x["lci"] == pytest.approx(73.988, abs=1e-3)
        assert r["lcs"] == pytest.approx(0.049, abs=5e-4)
        assert r["lci"] == 0

    def test_reproduce_redondeo_del_libro(self):
        """Con X̿ = 74.001 y R̄ = 0.023 (redondeados): LCS = 74.001 + 0.577·0.023 = 74.014."""
        assert 74.001 + 0.577 * 0.023 == pytest.approx(74.014, abs=5e-4)
        assert 74.001 - 0.577 * 0.023 == pytest.approx(73.988, abs=5e-4)
        assert 2.114 * 0.023 == pytest.approx(0.049, abs=5e-4)

    def test_en_control(self):
        """El libro concluye que el proceso está bajo control en la Fase I (regla N1)."""
        res = gv.calcular_xbar_r(ANILLOS, reglas=["N1"])
        assert res["puntos_con_senal"] == []
        assert res["fase"] == "I"
        assert res["sigma_hat"] == pytest.approx(0.023 / 2.326, abs=2e-4)

    def test_fase_ii_usa_limites_congelados(self):
        nuevos = [[74.03, 74.04, 74.035, 74.02, 74.03]]  # media 74.031 > LCS
        res2 = gv.calcular_xbar_r(nuevos, limites=self.res["limites"])
        assert res2["fase"] == "II"
        assert res2["cartas"]["xbar"]["lcs"] == self.res["limites"]["xbar"]["lcs"]
        assert res2["puntos_con_senal"] == [0]


class TestXbarSAnillos:
    """Anillos de pistón con X̄-S: s̄ = 0.0094, LCS = 74.014, LCI = 73.988, LCS_S = 0.0196."""

    res = gv.calcular_xbar_s(ANILLOS)

    def test_limites_libro(self):
        assert self.res["limites"]["s_barra"] == pytest.approx(0.0094, abs=5e-5)
        x, s = self.res["cartas"]["xbar"], self.res["cartas"]["s"]
        assert x["lcs"] == pytest.approx(74.014, abs=6e-4)
        assert x["lci"] == pytest.approx(73.988, abs=6e-4)
        assert s["lcs"] == pytest.approx(0.0196, abs=5e-5)
        assert s["lci"] == 0

    def test_n_variable_limites_por_subgrupo(self):
        grupos = [g[:4] if i % 3 == 0 else g for i, g in enumerate(ANILLOS)]
        res = gv.calcular_xbar_s(grupos)
        lcs = res["cartas"]["xbar"]["lcs"]
        assert isinstance(lcs, list)
        assert lcs[0] > lcs[1]  # n = 4 tiene límites más anchos que n = 5


class TestIMRPrestamos:
    """Préstamos hipotecarios: x̄ = 300.5, MR̄ = 7.79, LCS = 321.22, LCI = 279.78, LCS_MR = 25.45."""

    res = gv.calcular_imr(PRESTAMOS)

    def test_limites_libro(self):
        i, mr = self.res["limites"]["i"], self.res["limites"]["mr"]
        assert i["lc"] == pytest.approx(300.5, abs=0.01)
        assert mr["lc"] == pytest.approx(7.79, abs=0.005)
        assert i["lcs"] == pytest.approx(321.22, abs=0.01)
        assert i["lci"] == pytest.approx(279.78, abs=0.01)
        assert mr["lcs"] == pytest.approx(25.45, abs=0.01)

    def test_primer_mr_vacio(self):
        assert self.res["cartas"]["mr"]["valores"][0] is None


class TestFaseI:
    def test_excluir_y_recalcular(self):
        datos = [list(g) for g in ANILLOS]
        datos[5] = [v + 0.03 for v in datos[5]]  # se introduce una causa asignable
        res = gv.calcular_xbar_r(datos, reglas=["N1"])
        assert 5 in res["puntos_con_senal"]
        recalc = gv.calcular_xbar_r(datos, excluidos=[5], reglas=["N1"])
        assert recalc["limites"]["m_usados"] == 24
        assert recalc["limites"]["xbar"]["lc"] < res["limites"]["xbar"]["lc"]
        # El excluido se sigue graficando pero no participa en las reglas.
        assert recalc["cartas"]["xbar"]["valores"][5] is not None
        assert 5 not in recalc["puntos_con_senal"]

    def test_simular_exclusion(self):
        datos = [list(g) for g in ANILLOS]
        datos[5] = [v + 0.03 for v in datos[5]]
        sim = gv.simular_exclusion("xbar_r", datos, [], [5], reglas=["N1"])
        assert sim["delta"]["lc"] < 0
        assert sim["despues"]["lcs"] == pytest.approx(sim["antes"]["lcs"] + sim["delta"]["lcs"])

    def test_k_distinto_de_3(self):
        r3 = gv.calcular_xbar_r(ANILLOS)
        r2 = gv.calcular_xbar_r(ANILLOS, k=2)
        ancho3 = r3["limites"]["xbar"]["lcs"] - r3["limites"]["xbar"]["lc"]
        ancho2 = r2["limites"]["xbar"]["lcs"] - r2["limites"]["xbar"]["lc"]
        assert ancho2 == pytest.approx(ancho3 * 2 / 3, rel=2e-3)

    def test_n_variable_en_xbar_r_falla(self):
        with pytest.raises(ValueError):
            gv.calcular_xbar_r([[1, 2, 3], [1, 2]])

    def test_despachador(self):
        assert gv.calcular_carta("imr", [[v] for v in PRESTAMOS])["tipo"] == "imr"
        with pytest.raises(ValueError):
            gv.calcular_carta("zzz", ANILLOS)


# ---------------------------------------------------------------------------
# Límites con σ fijada (estándar dado) y recomendación de carta
# ---------------------------------------------------------------------------

class TestLimitesConSigma:
    """Límites con estándares dados (Montgomery §6.2): n = 5 ⇒ D2 = 4.918, B6 = 1.964."""

    def test_factores_tabulados_n5(self):
        lim = gv.limites_con_sigma("xbar_r", 0.0, 1.0, 5)
        assert lim["xbar"]["lcs"] == pytest.approx(3 / np.sqrt(5))
        assert lim["r"]["lcs"] == pytest.approx(4.918, abs=1e-3)
        assert lim["r"]["lci"] == 0
        s = gv.limites_con_sigma("xbar_s", 0.0, 1.0, 5)
        assert s["s"]["lcs"] == pytest.approx(1.964, abs=1e-3)
        assert s["s"]["lc"] == pytest.approx(0.9400, abs=1e-4)  # c4(5)

    def test_con_sigma_estimada_coincide_con_fase_i(self):
        """Con σ = R̄/d2 y centro X̿, los límites coinciden con los de la Fase I
        (A2·R̄ = 3σ/√n y D4·R̄ = (d2 + 3·d3)·σ)."""
        f1 = gv.calcular_xbar_r(ANILLOS)["limites"]
        lim = gv.limites_con_sigma("xbar_r", f1["xbar"]["lc"], f1["sigma_hat"], 5)
        # La Fase I usa los factores tabulados con 3 decimales (A2 = 0.577, D4 = 2.114) y la
        # fórmula con σ usa los exactos (3/(d2√n) = 0.5768…): difieren en ~5e-6, por eso abs=1e-5.
        for clave in ("lc", "lcs", "lci"):
            assert lim["xbar"][clave] == pytest.approx(f1["xbar"][clave], abs=1e-5)
            assert lim["r"][clave] == pytest.approx(f1["r"][clave], abs=1e-5)

    def test_sirve_como_limites_de_fase_ii(self):
        lim = gv.limites_con_sigma("xbar_r", 74.0, 0.01, 5)
        res = gv.calcular_xbar_r(ANILLOS, limites=lim)
        assert res["sigma_hat"] == 0.01
        assert res["cartas"]["xbar"]["lcs"] == pytest.approx(74.0 + 0.03 / np.sqrt(5))
        assert gv.centro_de_limites(lim) == 74.0

    def test_xbar_s_e_imr(self):
        res = gv.calcular_xbar_s(ANILLOS, limites=gv.limites_con_sigma("xbar_s", 74.0, 0.01, 5))
        assert res["cartas"]["xbar"]["lcs"] == pytest.approx(74.0 + 0.03 / np.sqrt(5))
        i = gv.limites_con_sigma("imr", 10.0, 2.0, 1)
        assert i["i"]["lcs"] == 16.0 and i["mr"]["lc"] == pytest.approx(1.128 * 2, abs=1e-3)
        assert gv.centro_de_limites(i) == 10.0

    def test_sigma_invalida(self):
        with pytest.raises(ValueError):
            gv.limites_con_sigma("xbar_r", 0, 0, 5)
        with pytest.raises(ValueError):
            gv.limites_con_sigma("xbar_r", 0, 1, 1)


@pytest.mark.parametrize("n,constante,esperada", [(1, True, "imr"), (5, True, "xbar_r"), (10, True, "xbar_r"),
                                                 (12, True, "xbar_s"), (5, False, "xbar_s")])
def test_recomendar_carta_variables(n, constante, esperada):
    r = gv.recomendar_carta_variables(n, constante)
    assert r["carta"] == esperada
    assert r["razon"]
