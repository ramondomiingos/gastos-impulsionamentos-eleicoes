import json

import pandas as pd
import pytest

from gastos import story


def _run(tmp_path, linhas, meta=None):
    pasta = tmp_path / "run"
    pasta.mkdir()
    pd.DataFrame(linhas).to_csv(pasta / "candidatos.csv", sep=";", decimal=",", encoding="utf-8-sig", index=False)
    (pasta / "meta.json").write_text(json.dumps(meta or {"dt_geracao": "22/10/2026", "dt_ultima_prestacao": "12/10/2026"}))
    return pasta


def _cand(sq, nome, partido, total, principal, confirmado=None):
    return {"sq_candidato": sq, "uf": "PI", "cargo": "Governador", "partido": partido, "candidato": nome,
            "cd_eleicao": 6259, "total": total, "confirmado": principal if confirmado is None else confirmado,
            "generico": 0.0, "provavel": 0.0, "principal": principal,
            "proporcao": (principal / total) if total else 0.0}


DADOS = [
    _cand("1", "JOEL RODRIGUES DA SILVA", "PP", 2_068_164.51, 300_000.0),
    _cand("2", "RAFAEL TAJRA FONTELES", "PT", 6_021_255.59, 268_468.0),
    _cand("3", "GUSTAVO HENRIQUE LEITE FEIJO", "AVANTE", 2_500.0, 2_500.0),
    _cand("4", "GERALDO DO NASCIMENTO CARVALHO", "PSTU", 21_000.0, 0.0),
    _cand("5", "SEM DESPESA", "XYZ", 0.0, 0.0),
]


def test_format_helpers():
    assert story.brl(363000) == "R$ 363.000"
    assert story.pct(0.1197) == "12,0%"
    assert story.hero(574064.22) == ("R$ 574", " mil")
    assert story.hero(4_240_709.51) == ("R$ 4,2", " mi")
    assert story.hero(950) == ("R$ 950", "")


def test_bars_rank_by_value_and_scale_to_largest():
    linhas = story.linhas_barras(pd.DataFrame(DADOS[:4]))
    assert [l["nome"] for l in linhas][:2] == ["Joel Rodrigues da Silva", "Rafael Tajra Fonteles"]
    assert linhas[0]["largura"] == 100
    assert linhas[1]["largura"] == pytest.approx(89.49, abs=0.01)
    assert linhas[3]["valor"] == "R$ 0" and linhas[3]["largura"] == 0


def test_small_campaign_is_flagged_only_when_it_has_spend():
    linhas = {l["nome"]: l for l in story.linhas_barras(pd.DataFrame(DADOS[:4]))}
    assert "campanha pequena" in linhas["Gustavo Henrique Leite Feijo"]["nota"]
    assert linhas["Geraldo do Nascimento Carvalho"]["nota"] == ""  # sem gasto em plataformas: sem nota


def test_bars_truncated_to_max():
    muitos = [_cand(str(i), f"CAND {i}", "P", 10_000.0, float(i)) for i in range(12)]
    assert len(story.linhas_barras(pd.DataFrame(muitos))) == story.MAX_LINHAS


def test_montar_counts_only_declared_candidates_and_dates(tmp_path):
    ctx = story.montar(_run(tmp_path, DADOS), "PI", "Governador", n_total=11, n_2turno=0)
    assert ctx["n_declarados"] == 4 and ctx["n_total"] == 11  # o candidato sem despesa não conta como declarado
    assert (ctx["hero_valor"], ctx["hero_unidade"]) == ("R$ 571", " mil")
    assert ctx["dt_prestacao"] == "12/10/2026"
    assert "prestação final" in ctx["aviso_valores"]


def test_second_round_notice(tmp_path):
    run = _run(tmp_path, DADOS)
    um = story.montar(run, "RN", "Governador", 11, 1)["aviso_valores"]
    dois = story.montar(run, "RN", "Governador", 11, 2)["aviso_valores"]
    assert "1 candidato segue no 2º turno" in um
    assert "2 candidatos seguem no 2º turno" in dois


def test_html_has_numbers_and_never_the_party(tmp_path):
    ctx = story.montar(_run(tmp_path, DADOS), "PI", "Governador", 11, 0)
    html = story.renderizar(ctx)
    assert "R$ 571" in html and "Joel Rodrigues da Silva" in html and "R$ 300.000" in html
    assert "Piauí" in html and "declararam despesas ao TSE (4 de 11" in html
    for sigla in ("AVANTE", "PSTU", "PP<", ">PT<", "XYZ"):
        assert sigla not in html
    assert "dinheiro público" not in html.lower()


def test_html_escapes_names_and_profile(tmp_path):
    dados = [_cand("1", "ANA <b>X</b>", "P", 100_000.0, 1_000.0)]
    html = story.renderizar(story.montar(_run(tmp_path, dados), "PI", "Governador", 1, 0, perfil="@a<script>"))
    assert "<b>X</b>" not in html and "<script>" not in html.split("<body>")[1].split("html2canvas")[0]


def test_unknown_uf_and_cargo_rejected(tmp_path):
    run = _run(tmp_path, DADOS)
    with pytest.raises(ValueError, match="UF inválida"):
        story.montar(run, "ZZ", "Governador", 1, 0)
    with pytest.raises(ValueError, match="cargo sem texto"):
        story.montar(run, "PI", "Prefeito", 1, 0)


def test_national_president_wording(tmp_path):
    dados = [dict(_cand("1", "FULANO", "P", 1_000_000.0, 100_000.0), uf="BR", cargo="Presidente")]
    ctx = story.montar(_run(tmp_path, dados), "BR", "Presidente", 1, 1)
    assert ctx["prep_cargo"] == "à Presidência" and ctx["uf_nome_prep"] == "do Brasil"
    assert "Brasil" in story.renderizar(ctx)


def test_no_declared_candidates_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="nenhum candidato"):
        story.montar(_run(tmp_path, [_cand("1", "A", "P", 0.0, 0.0)]), "PI", "Governador", 1, 0)


def test_names_come_from_consulta_cand_with_accents(tmp_path):
    ctx = story.montar(_run(tmp_path, DADOS), "PI", "Governador", 11, 0, nomes={"3": "GUSTAVO HENRIQUE LEITE FEIJÓ"})
    assert "Gustavo Henrique Leite Feijó" in [l["nome"] for l in ctx["linhas"]]


def test_compact_layout_only_with_many_rows(tmp_path):
    poucos = story.montar(_run(tmp_path, DADOS), "PI", "Governador", 11, 0)
    assert poucos["compacto"] is False
    muitos = [_cand(str(i), f"CAND {i}", "P", 10_000.0, float(i + 1)) for i in range(8)]
    pasta = tmp_path / "m"
    pasta.mkdir()
    assert story.montar(_run(pasta, muitos), "PI", "Governador", 8, 0)["compacto"] is True


# ---------- página no nível do estado (todos os cargos) ----------

def _cand_cargo(sq, cargo, total, principal, confirmado=0.0):
    c = _cand(sq, f"CAND {sq}", "P", total, principal, confirmado)
    c["cargo"] = cargo
    return c


def _run_estado(tmp_path, linhas, tetos=None):
    pasta = _run(tmp_path, linhas)
    tetos = tetos or [
        {"teto": 0.05, "n_acima": 3, "pct_acima": 0.6, "excedente": 1000.0},
        {"teto": 0.10, "n_acima": 2, "pct_acima": 0.4, "excedente": 500.0},
        {"teto": 0.20, "n_acima": 1, "pct_acima": 0.2, "excedente": 100.0},
    ]
    return pasta, tetos


ESTADO = [
    _cand_cargo("1", "Governador", 1_000_000.0, 100_000.0, 40_000.0),
    _cand_cargo("2", "Senador", 500_000.0, 50_000.0, 50_000.0),
    _cand_cargo("3", "Deputado Federal", 400_000.0, 20_000.0, 10_000.0),
    _cand_cargo("4", "Deputado Federal", 300_000.0, 0.0),
    _cand_cargo("5", "Deputado Estadual", 200_000.0, 10_000.0, 10_000.0),
    _cand_cargo("6", "Deputado Estadual", 0.0, 0.0),
]


def test_por_cargo_aggregates_and_orders(tmp_path):
    linhas = story.linhas_por_cargo(pd.DataFrame(ESTADO))
    assert [l["rotulo"] for l in linhas] == ["Governo", "Senado", "Deputados federais", "Deputados estaduais"]
    gov, sen, fed, est = linhas
    assert gov["valor"] == "R$ 100.000" and gov["largura"] == 100
    assert fed["valor"] == "R$ 20.000" and fed["largura"] == 20
    assert fed["gastaram"] == "1 de 2 candidatos declararam gasto com essas plataformas"
    assert est["pct"].startswith("5,0%")  # 10.000 / 200.000


def test_estado_context_totals_and_caps(tmp_path):
    pasta, tetos = _run_estado(tmp_path, ESTADO)
    ctx = story.montar_estado(pasta, "PB", n_total=9, n_2turno=0, tetos=tetos)
    assert (ctx["hero_valor"], ctx["hero_unidade"]) == ("R$ 180", " mil")
    assert ctx["n_declarados"] == 5 and ctx["n_total"] == 9  # candidato 6 tem total 0
    assert ctx["prop_total"] == "7,5%"  # 180.000 / 2.400.000
    assert [t["teto"] for t in ctx["tetos"]] == ["5%", "10%", "20%"]
    assert ctx["tetos"][1]["n_acima"] == 2 and ctx["tetos"][1]["pct"] == "40,0%"
    assert ctx["tetos"][1]["excedente"] == "R$ 500"


def test_estado_html_has_no_candidate_or_party_names(tmp_path):
    pasta, tetos = _run_estado(tmp_path, ESTADO)
    html = story.renderizar(story.montar_estado(pasta, "PB", 9, 0, tetos=tetos))
    assert "Paraíba" in html and "Deputados federais" in html and "R$ 180" in html
    assert "CAND 1" not in html and ">P<" not in html
    assert "dinheiro público" not in html.lower()
    assert "1 de 2 candidatos" in html
    assert html.count('class="card') == 4


def test_estado_without_tetos_still_renders(tmp_path):
    pasta, _ = _run_estado(tmp_path, ESTADO)
    html = story.renderizar(story.montar_estado(pasta, "PB", 9, 0, tetos=[]))
    assert "Paraíba" in html


def test_state_page_cli_without_cargo(tmp_path, monkeypatch):
    pasta, tetos = _run_estado(tmp_path, ESTADO)
    pd.DataFrame(tetos).to_csv(pasta / "tetos.csv", sep=";", decimal=",", encoding="utf-8-sig", index=False)
    monkeypatch.setattr(story, "_consulta_cand", lambda z, uf, cargo: (9, 0, {}))
    saida = tmp_path / "pb.html"
    assert story.main(["--run", str(pasta), "--uf", "PB", "--saida", str(saida)]) == 0
    assert "Deputados estaduais" in saida.read_text(encoding="utf-8")
