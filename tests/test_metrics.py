import math

import pandas as pd
import pytest

from gastos import metrics


def _df():
    rows = [
        # uf, sq, candidato, cargo, partido, valor, nivel
        ("RN", "1", "A", "DEPUTADO", "P1", 100.0, "confirmado"),
        ("RN", "1", "A", "DEPUTADO", "P1", 50.0, "generico"),
        ("RN", "1", "A", "DEPUTADO", "P1", 30.0, "provavel"),
        ("RN", "1", "A", "DEPUTADO", "P1", 820.0, "nenhum"),
        ("RN", "2", "B", "SENADOR", "P2", 200.0, "nenhum"),
        ("PB", "3", "C", "DEPUTADO", "P1", 40.0, "confirmado"),
        ("PB", "3", "C", "DEPUTADO", "P1", 60.0, "nenhum"),
    ]
    return pd.DataFrame(
        rows,
        columns=["uf", "sq_candidato", "candidato", "cargo", "partido", "valor", "nivel"],
    )


def test_principal_is_confirmado_plus_generico():
    r = metrics.summarize(_df(), ["uf"]).set_index("uf")
    assert r.loc["RN", "confirmado"] == 100.0
    assert r.loc["RN", "generico"] == 50.0
    assert r.loc["RN", "principal"] == 150.0
    assert r.loc["RN", "total"] == 1200.0
    assert r.loc["RN", "proporcao"] == pytest.approx(150 / 1200)
    assert r.loc["RN", "n_candidatos"] == 2


def test_provavel_not_in_principal():
    r = metrics.summarize(_df(), []).iloc[0]
    assert r["provavel"] == 30.0
    assert r["principal"] == 190.0
    assert r["total"] == 1300.0


def test_proporcao_zero_total():
    df = pd.DataFrame(
        [("RN", "9", "Z", "DEPUTADO", "P", 0.0, "nenhum")],
        columns=["uf", "sq_candidato", "candidato", "cargo", "partido", "valor", "nivel"],
    )
    for r in (metrics.summarize(df, ["uf"]), metrics.candidate_shares(df)):
        assert r["proporcao"].iloc[0] == 0.0
        assert not r["proporcao"].isna().any()
    empty = df.iloc[0:0]
    assert len(metrics.summarize(empty, ["uf"])) == 0


@pytest.mark.parametrize(
    "by",
    [[], ["uf"], ["cargo"], ["partido"], ["candidato"], ["uf", "cargo"], ["uf", "cargo", "partido", "candidato"]],
)
def test_summarize_by_keys_sum_to_grand_total(by):
    df = _df()
    r = metrics.summarize(df, by)
    for c in by:
        assert c in r.columns
    assert r["total"].sum() == pytest.approx(df["valor"].sum())
    assert r["principal"].sum() == pytest.approx(190.0)
    assert not r["proporcao"].isna().any()
    if by == ["candidato"]:
        assert len(r) == 3
        assert r["n_candidatos"].eq(1).all()


def test_candidate_shares():
    s = metrics.candidate_shares(_df()).set_index("sq_candidato")
    assert len(s) == 3
    assert s.loc["1", "proporcao"] == pytest.approx(150 / 1000)
    assert s.loc["2", "proporcao"] == 0.0
    assert s.loc["3", "uf"] == "PB"
    for c in ("cargo", "partido", "candidato"):
        assert c in s.columns


def test_cap_impact():
    shares = pd.DataFrame(
        {
            "sq_candidato": ["a", "b", "c", "d"],
            "total": [100.0, 100.0, 100.0, 0.0],
            "principal": [2.0, 8.0, 30.0, 0.0],
            "proporcao": [0.02, 0.08, 0.30, 0.0],
        }
    )
    r = metrics.cap_impact(shares, [0.05, 0.10]).set_index("teto")
    assert r.loc[0.05, "n_acima"] == 2
    assert r.loc[0.05, "excedente"] == pytest.approx((8 - 5) + (30 - 5))
    assert r.loc[0.05, "pct_acima"] == pytest.approx(2 / 3)  # total 0 fora do denominador
    assert r.loc[0.10, "n_acima"] == 1
    assert r.loc[0.10, "excedente"] == pytest.approx(30 - 10)


def test_distribution():
    shares = pd.DataFrame({"proporcao": [0.0, 0.1, 0.2, 0.3, 0.4], "total": [1.0] * 5})
    d = metrics.distribution(shares)
    assert set(d) == {"mediana", "p75", "p90", "max"}
    assert d["mediana"] == pytest.approx(0.2)
    assert d["max"] == pytest.approx(0.4)
    assert not math.isnan(metrics.distribution(shares.iloc[0:0])["max"])


# ---------------- top_candidatos ----------------

def _sh(rows):
    return pd.DataFrame(rows, columns=["sq_candidato", "total", "principal", "confirmado", "proporcao"])


def test_top_candidatos_ranks_by_proporcao_desc():
    s = _sh([("1", 100000.0, 10000.0, 5000.0, 0.10), ("2", 100000.0, 30000.0, 1000.0, 0.30),
             ("3", 100000.0, 20000.0, 0.0, 0.20)])
    r = metrics.top_candidatos(s)
    assert list(r["sq_candidato"]) == ["2", "3", "1"]
    assert "confirmado" in r.columns


def test_top_candidatos_tie_break_principal_then_sq():
    s = _sh([("9", 100000.0, 20000.0, 0.0, 0.2), ("5", 200000.0, 40000.0, 0.0, 0.2),
             ("3", 200000.0, 40000.0, 0.0, 0.2)])
    assert list(metrics.top_candidatos(s)["sq_candidato"]) == ["3", "5", "9"]


def test_top_candidatos_piso_excludes_small_campaigns():
    s = _sh([("1", 1000.0, 1000.0, 1000.0, 1.0), ("2", 49999.99, 40000.0, 0.0, 0.8),
             ("3", 50000.0, 5000.0, 0.0, 0.1)])
    assert list(metrics.top_candidatos(s)["sq_candidato"]) == ["3"]
    assert list(metrics.top_candidatos(s, piso_total=1000.0)["sq_candidato"]) == ["1", "2", "3"]


def test_top_candidatos_excludes_zero_principal_and_limits_n():
    s = _sh([(str(i), 100000.0, float(i * 1000), 0.0, i / 100) for i in range(0, 9)])
    r = metrics.top_candidatos(s)
    assert len(r) == 5 and "0" not in set(r["sq_candidato"])
    assert list(r["sq_candidato"]) == ["8", "7", "6", "5", "4"]
    assert len(metrics.top_candidatos(s, n=2)) == 2


def test_top_candidatos_fewer_than_n_and_empty():
    s = _sh([("1", 100000.0, 10000.0, 0.0, 0.1)])
    assert len(metrics.top_candidatos(s)) == 1
    assert metrics.top_candidatos(_sh([])).empty
    assert list(metrics.top_candidatos(_sh([])).columns) == list(_sh([]).columns)


def test_candidate_shares_has_confirmado():
    assert "confirmado" in metrics.candidate_shares(_df()).columns
