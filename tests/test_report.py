from datetime import date

import pandas as pd
import pytest

from gastos import report

COLS = ["uf", "sq_candidato", "candidato", "cargo", "partido", "fornecedor", "descricao",
        "valor", "dt_geracao", "tp_prestacao", "sq_despesa", "nivel", "plataforma"]
RECORTE = {"uf": "RN", "cargo": None, "partido": None, "candidato": None}


def _df():
    rows = [
        ("RN", "1", "A", "DEPUTADO FEDERAL", "P1", "Meta Platforms", "anuncio", 100.0, "20/10/2026", "Parcial", "a", "confirmado", "Meta"),
        ("RN", "1", "A", "DEPUTADO FEDERAL", "P1", "Agencia", "impulsionamento", 50.5, "22/10/2026", "Parcial", "b", "generico", "desconhecida"),
        ("RN", "1", "A", "DEPUTADO FEDERAL", "P1", "Gateway", "x", 30.0, "22/10/2026", "Parcial", "c", "provavel", "desconhecida"),
        ("RN", "1", "A", "DEPUTADO FEDERAL", "P1", "Grafica", "santinho", 819.5, "22/10/2026", "Parcial", "d", "nenhum", ""),
        ("RN", "2", "B", "SENADOR", "P2", "Grafica", "santinho", 200.0, "21/10/2026", "Parcial", "e", "nenhum", ""),
    ]
    return pd.DataFrame(rows, columns=COLS)


def _run(tmp_path, df=None, today=date(2026, 10, 22), recorte=RECORTE):
    return report.write_run(_df() if df is None else df, recorte, out_root=tmp_path, today=today)


def test_evidence_sums_match_summary(tmp_path):
    d = _run(tmp_path)
    resumo = pd.read_csv(d / "resumo.csv").iloc[0]
    ev = {n: pd.read_csv(d / f"evidencia_{n}.csv") for n in ("confirmado", "generico", "provavel")}
    for n, e in ev.items():
        assert e["valor"].sum() == pytest.approx(resumo[n])
        assert (e["nivel"] == n).all()
    assert ev["confirmado"]["valor"].sum() + ev["generico"]["valor"].sum() == pytest.approx(resumo["principal"])
    assert set(COLS) <= set(ev["confirmado"].columns)
    for f in ("candidatos.csv", "tetos.csv", "qualidade.md", "relatorio.md"):
        assert (d / f).exists()


def test_qualidade_lists_level_totals_and_sample(tmp_path):
    q = (_run(tmp_path) / "qualidade.md").read_text(encoding="utf-8")
    for n in ("confirmado", "generico", "provavel", "nenhum"):
        assert n in q
    assert "Meta Platforms" in q and "Gateway" in q and "Grafica" in q
    assert "1.019,50" in q  # total do nivel nenhum (819,5 + 200)


def test_relatorio_states_partial_data_and_cutoff(tmp_path):
    r = (_run(tmp_path) / "relatorio.md").read_text(encoding="utf-8")
    assert "parcial" in r.lower()
    assert "22/10/2026" in r
    assert "piso" in r.lower()
    assert "dinheiro público" not in r.lower()
    assert "nan" not in r.lower()


def test_run_folder_is_dated_and_versioned(tmp_path):
    a = _run(tmp_path, today=date(2026, 10, 22))
    b = _run(tmp_path, today=date(2026, 10, 23))
    assert a != b and a.exists() and b.exists()
    assert a.name == "2026-10-22_uf-RN"
    again = _run(tmp_path, today=date(2026, 10, 22))  # mesmo dia: sobrescreve
    assert again == a


def test_folder_slug(tmp_path):
    rec = {"uf": "RN", "cargo": "Deputado Federal", "partido": None, "candidato": None}
    assert _run(tmp_path, recorte=rec).name == "2026-10-22_uf-RN_cargo-deputado-federal"
    all_none = {"uf": None, "cargo": None, "partido": None, "candidato": None}
    assert _run(tmp_path, recorte=all_none).name == "2026-10-22_brasil"


def test_empty_input_no_nan(tmp_path):
    d = _run(tmp_path, df=_df().iloc[0:0])
    r = (d / "relatorio.md").read_text(encoding="utf-8")
    assert "nan" not in r.lower() and "inf" not in r.lower().replace("informa", "")
    zero = _df().assign(valor=0.0)
    r2 = (_run(tmp_path, df=zero, today=date(2026, 10, 25)) / "relatorio.md").read_text(encoding="utf-8")
    assert "nan" not in r2.lower()
