import json
import zipfile

import pandas as pd
import pytest

from gastos import cli, metrics, publicar

CAB_DESP = ["DT_GERACAO", "SG_UF", "SQ_CANDIDATO", "NM_CANDIDATO", "DS_CARGO", "SG_PARTIDO",
            "NM_FORNECEDOR_RFB", "NR_CPF_CNPJ_FORNECEDOR", "DS_DESPESA", "DS_ORIGEM_DESPESA",
            "VR_DESPESA_CONTRATADA", "DT_DESPESA", "SQ_DESPESA", "TP_PRESTACAO_CONTAS", "DT_PRESTACAO_CONTAS"]
FB = "FACEBOOK SERVIÇOS ONLINE DO BRASIL LTDA"
OUTRO = "GRAFICA BOA LTDA"


def _csv(cab, linhas):
    def q(v):
        return '"' + str(v) + '"'
    return "\n".join(";".join(q(c) for c in cab) if i == 0 else ";".join(q(c) for c in l)
                     for i, l in enumerate([cab, *linhas])).encode("latin-1")


_seq = iter(range(1, 10_000))


def _desp(uf, sq, nome, cargo, forn, valor, ger="22/10/2026", prest="21/10/2026"):
    n = str(next(_seq))
    cnpj = "13347016000117" if forn == FB else "11111111000111"
    desc = "Impulsionamento de conteúdos" if forn == FB else "Material gráfico"
    return [ger, uf, sq, nome, cargo, "ZZPART", forn, cnpj, desc, "Despesa", valor, "10/09/2026", n, "Parcial", prest]


LINHAS = [
    # RN governador: g1 grande, g2 pequena (total < piso)
    _desp("RN", "1", "JOÃO D'ÁVILA", "Governador", FB, "10000,00"),
    _desp("RN", "1", "JOÃO D'ÁVILA", "Governador", OUTRO, "190000,00"),
    _desp("RN", "2", "ZÉ PEQUENO", "Governador", FB, "900,00"),
    # RN deputado federal
    _desp("RN", "3", "MARIA SOUZA", "Deputado Federal", FB, "20000,00"),
    _desp("RN", "3", "MARIA SOUZA", "Deputado Federal", OUTRO, "60000,00"),
    # RN deputado estadual sem gasto em plataforma
    _desp("RN", "4", "PEDRO LIMA", "Deputado Estadual", OUTRO, "70000,00", prest="15/10/2026"),
    # DF distrital
    _desp("DF", "5", "ANA DISTRITAL", "Deputado Distrital", FB, "5000,00"),
    _desp("DF", "5", "ANA DISTRITAL", "Deputado Distrital", OUTRO, "95000,00"),
    # AC: despesa declarada zerada; AP: so vice (fora de CARGOS_SITE); SP: candidato fora do cadastro
    _desp("AC", "8", "SEM VALOR", "Governador", OUTRO, "0,00"),
    _desp("AP", "9", "VICE AP", "Vice-Governador", FB, "1000,00"),
    _desp("SP", "7", "NOME SEM CADASTRO", "Governador", FB, "10000,00"),
    # Presidente
    _desp("BR", "6", "CARLOS PRESIDENTE", "Presidente", FB, "300000,00"),
    _desp("BR", "6", "CARLOS PRESIDENTE", "Presidente", OUTRO, "700000,00"),
]
CAB_CAND = ["SG_UF", "DS_CARGO", "SQ_CANDIDATO", "NM_CANDIDATO", "DS_SIT_TOT_TURNO", "NR_TURNO", "SG_PARTIDO"]
CANDS = [
    ["RN", "GOVERNADOR", "1", "JOÃO D'ÁVILA DA SILVA", "2º TURNO", "1", "ZZPART"],
    ["RN", "GOVERNADOR", "1", "JOÃO D'ÁVILA DA SILVA", "2º TURNO", "2", "ZZPART"],
    ["RN", "GOVERNADOR", "2", "ZÉ PEQUENO", "NÃO ELEITO", "1", "ZZPART"],
    ["RN", "DEPUTADO FEDERAL", "3", "MARIA DE SOUZA LIMA", "ELEITO", "1"],
    ["RN", "DEPUTADO FEDERAL", "30", "SEM DESPESA", "SUPLENTE", "1"],
    ["RN", "DEPUTADO ESTADUAL", "4", "PEDRO LIMA", "ELEITO", "1"],
    ["RN", "VICE-GOVERNADOR", "40", "VICE", "ELEITO", "1", "ZZPART"],
    ["DF", "DEPUTADO DISTRITAL", "5", "ANA DISTRITAL", "ELEITO", "1"],
    ["BR", "PRESIDENTE", "6", "CARLOS PRESIDENTE", "2º TURNO", "1", "ZZPART"],
]


CAB_PAGO = ["SQ_DESPESA", "DS_FONTE_DESPESA", "VR_PAGTO_DESPESA"]
FEFC = "Fundo Especial de Financiamento de Campanha"
FP = "Fundo Partidário"
OR = "Outros Recursos"


def _sq(i):
    return LINHAS[i][12]


PAGOS = [
    [_sq(0), FEFC, "6000,00"], [_sq(0), FP, "2000,00"], [_sq(0), OR, "1000,00"],  # RN gov, ad
    [_sq(1), FEFC, "50000,00"],            # RN gov, item que nao e anuncio: fora de `pago`
    [_sq(2), FEFC, "900,00"],              # RN gov pequena
    [_sq(3), OR, "5000,00"],               # RN dep. federal, so recurso nao publico
    ["999999", FEFC, "123,00"],            # sem linha contratada
]


@pytest.fixture
def zips(tmp_path):
    z = tmp_path / "desp.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("despesas_contratadas_candidatos_2026_BRASIL.csv", _csv(CAB_DESP, LINHAS))
        f.writestr("despesas_pagas_candidatos_2026_BRASIL.csv", _csv(CAB_PAGO, PAGOS))
    e = tmp_path / "cand.zip"
    with zipfile.ZipFile(e, "w") as f:
        f.writestr("consulta_cand_2026_BRASIL.csv", _csv(CAB_CAND, CANDS))
        f.writestr("consulta_cand_2026_RN.csv", b"lixo")
    return z, e


def _shares(rows, pago=None, pago_publico=None):
    df = pd.DataFrame(rows, columns=["sq_candidato", "uf", "cargo", "partido", "candidato", "total",
                                     "confirmado", "generico", "provavel"])
    df["principal"] = df["confirmado"] + df["generico"]
    df["pago"] = 0.0 if pago is None else pago
    df["pago_publico"] = 0.0 if pago_publico is None else pago_publico
    df["proporcao"] = (df["principal"] / df["total"].where(df["total"] != 0)).fillna(0.0)
    return df


def _sh(sq, total, conf, gen=0.0, prov=0.0, cargo="Governador", uf="RN"):
    return (sq, uf, cargo, "X", f"NOME {sq}", total, conf, gen, prov)


# --- ranking ---

def test_top_ranks_by_value_then_total_then_sq():
    s = _shares([_sh("3", 100.0, 10.0), _sh("1", 100.0, 10.0), _sh("2", 500.0, 10.0), _sh("4", 90.0, 50.0)])
    assert list(metrics.maiores_valores(s)["sq_candidato"]) == ["4", "2", "1", "3"]


def test_top_excludes_zero_principal():
    s = _shares([_sh("1", 100.0, 0.0, 0.0, 30.0), _sh("2", 100.0, 5.0)])
    assert list(metrics.maiores_valores(s)["sq_candidato"]) == ["2"]


def test_top_limit_five():
    s = _shares([_sh(str(i), 1000.0, float(i)) for i in range(1, 9)])
    top = metrics.maiores_valores(s)
    assert len(top) == 5 and list(top["sq_candidato"]) == ["8", "7", "6", "5", "4"]
    assert len(metrics.maiores_valores(s, n=2)) == 2


# --- recorte ---

def test_recorte_fields_and_principal_is_confirmado_plus_generico():
    s = _shares([_sh("1", 200000.0, 10000.0, 20000.0, 5000.0), _sh("2", 900.0, 900.0)])
    r = publicar.montar_recorte(s, "Governo", "Governador", {"1": "Nome Um"}, [0.05, 0.10], 50000.0)
    assert list(r) == ["rotulo", "cargo", "total", "principal", "confirmado", "generico", "provavel",
                       "proporcao", "n_candidatos", "n_gastaram", "n_elegiveis", "pago", "pago_publico",
                       "pct_publico", "cobertura_pago", "tetos", "top"]
    assert r["principal"] == 30900.0 and r["confirmado"] == 10900.0 and r["generico"] == 20000.0
    assert r["provavel"] == 5000.0 and r["total"] == 200900.0
    assert r["proporcao"] == round(30900.0 / 200900.0, 6)
    assert (r["n_candidatos"], r["n_gastaram"], r["n_elegiveis"]) == (2, 2, 1)
    assert list(r["top"][0]) == ["sq", "nome", "cargo", "uf", "principal", "confirmado", "total",
                                 "proporcao", "pequena"]
    assert r["top"][0]["nome"] == "Nome Um" and r["top"][0]["pequena"] is False
    assert r["top"][1]["nome"] == "Nome 2" and r["top"][1]["pequena"] is True  # fallback: nome dos gastos
    assert r["top"][0]["cargo"] == "Governador" and r["top"][0]["uf"] == "RN"
    assert list(r["tetos"][0]) == ["teto", "n_acima", "pct_acima", "excedente"]


def test_recorte_tetos_only_among_eligible_campaigns():
    s = _shares([_sh("1", 200000.0, 100000.0), _sh("2", 1000.0, 1000.0), _sh("3", 100000.0, 1000.0)])
    r = publicar.montar_recorte(s, "Governo", "Governador", {}, [0.05, 0.50], 50000.0)
    assert r["n_elegiveis"] == 2 and r["n_candidatos"] == 3
    t05, t50 = r["tetos"]
    assert t05["n_acima"] == 1 and t05["pct_acima"] == 0.5
    assert t05["excedente"] == 100000.0 - 0.05 * 200000.0
    assert t50["n_acima"] == 0 and t50["excedente"] == 0.0


def test_recorte_todos_has_null_cargo_and_empty_top_is_list():
    s = _shares([_sh("1", 1000.0, 0.0)])
    r = publicar.montar_recorte(s, "Todos os cargos", None, {}, [0.05], 50000.0)
    assert r["cargo"] is None and r["top"] == [] and r["n_gastaram"] == 0


def test_slug_cargo():
    assert publicar.slug_cargo("Deputado Federal") == "deputado-federal"
    assert publicar.slug_cargo("DEPUTADO ESTADUAL") == "deputado-estadual"
    assert publicar.slug_cargo("Presidente") == "presidente"


# --- publicar ---

def _pub(zips, saida, **kw):
    z, e = zips
    return publicar.publicar(z, e, saida, hoje=pd.Timestamp("2026-10-23").date(), **kw)


def _ler(saida, nome):
    return json.loads((saida / f"{nome}.json").read_text(encoding="utf-8"))


def _chaves(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _chaves(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _chaves(v)


def test_uf_has_todos_and_cargo_keys_only_for_existing_cargos(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    rn, df_ = _ler(tmp_path / "o", "RN"), _ler(tmp_path / "o", "DF")
    assert list(rn["recortes"]) == ["todos", "governador", "deputado-federal", "deputado-estadual"]
    assert list(df_["recortes"]) == ["todos", "deputado-distrital"]
    assert list(rn) == ["uf", "nome", "artigo", "dt_geracao", "dt_ultima_prestacao", "segundo_turno",
                        "n_candidatos_total", "recortes"]
    assert (rn["uf"], rn["nome"], rn["artigo"]) == ("RN", "Rio Grande do Norte", "do")
    assert rn["recortes"]["todos"]["rotulo"] == "Todos os cargos"
    assert rn["recortes"]["governador"]["rotulo"] == "Governo"
    assert rn["recortes"]["todos"]["total"] == 200000.0 + 900.0 + 80000.0 + 70000.0
    assert rn["recortes"]["todos"]["principal"] == 10000.0 + 900.0 + 20000.0
    assert rn["dt_ultima_prestacao"] == "21/10/2026" and rn["dt_geracao"] == "22/10/2026"
    assert rn["n_candidatos_total"] == 5  # SQ 1, 2, 3, 30 e 4 (vice-governador fora de CARGOS_SITE)
    assert rn["segundo_turno"] == 1  # SQ 1, contado uma vez (NR_TURNO 1)


def test_json_has_no_party_field_anywhere(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    arquivos = list((tmp_path / "o").glob("*.json"))
    assert arquivos
    for f in arquivos:
        texto = f.read_text(encoding="utf-8")
        chaves = set(_chaves(json.loads(texto)))
        assert not [k for k in chaves if "partido" in k.lower()], f.name
        assert "ZZPART" not in texto and "zzpart" not in texto.lower(), f.name


def test_names_title_case_with_accents_from_consulta_cand(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    top = _ler(tmp_path / "o", "RN")["recortes"]["governador"]["top"]
    assert [t["nome"] for t in top] == ["João D'Ávila da Silva", "Zé Pequeno"]
    assert top[0]["sq"] == "1" and top[0]["pequena"] is False and top[1]["pequena"] is True
    raw = (tmp_path / "o" / "RN.json").read_text(encoding="utf-8")
    assert "Ávila" in raw  # UTF-8, sem escapes


def test_br_has_only_presidente_recorte_and_states_exclude_presidente(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    br = _ler(tmp_path / "o", "BR")
    assert list(br["recortes"]) == ["presidente"]
    p = br["recortes"]["presidente"]
    assert (p["rotulo"], p["cargo"], p["total"], p["principal"]) == ("Presidência", "Presidente", 1000000.0, 300000.0)
    assert (br["uf"], br["nome"], br["artigo"], br["n_candidatos_total"], br["segundo_turno"]) == \
        ("BR", "Brasil", "do", 1, 1)
    for uf in ("RN", "DF"):
        rec = _ler(tmp_path / "o", uf)["recortes"]
        assert "presidente" not in rec
        assert all(t["uf"] != "BR" for r in rec.values() for t in r["top"])
        assert rec["todos"]["total"] < 1000000.0


def test_index_lists_cargos_per_uf(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    idx = _ler(tmp_path / "o", "index")
    assert list(idx) == ["versao", "gerado_em", "dt_geracao", "dt_ultima_prestacao", "piso_campanha",
                         "tetos", "ufs"]
    assert idx["versao"] == 1 and idx["gerado_em"] == "2026-10-23" and idx["piso_campanha"] == 50000
    assert idx["tetos"] == [0.05, 0.1, 0.15, 0.2]
    assert idx["dt_geracao"] == "22/10/2026" and idx["dt_ultima_prestacao"] == "21/10/2026"
    por_uf = {u["uf"]: u for u in idx["ufs"]}
    assert idx["ufs"][0]["uf"] == "BR"
    assert por_uf["BR"] == {"uf": "BR", "nome": "Brasil", "artigo": "do", "cargos": ["presidente"]}
    assert por_uf["RN"]["cargos"] == ["todos", "governador", "deputado-federal", "deputado-estadual"]
    assert por_uf["DF"]["cargos"] == ["todos", "deputado-distrital"]
    assert "deputado-estadual" not in por_uf["DF"]["cargos"]


def test_publicar_writes_index_and_one_file_per_uf_deterministically(zips, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _pub(zips, a)
    _pub(zips, b)
    nomes = sorted(p.name for p in a.iterdir())
    assert nomes == ["AC.json", "BR.json", "DF.json", "RN.json", "SP.json", "index.json"]
    for n in nomes:
        assert (a / n).read_bytes() == (b / n).read_bytes()
    assert (a / "RN.json").read_text(encoding="utf-8").startswith('{\n "uf": "RN"')


def test_publicar_rejects_bad_piso(zips, tmp_path):
    with pytest.raises(ValueError):
        _pub(zips, tmp_path / "o", piso_campanha=0)


# --- CLI ---

def test_cli_publicar_invalid_piso_exit_2(zips, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "download_candidatos", lambda *a, **k: pytest.fail("rede"))
    monkeypatch.setattr(cli, "download_resultados", lambda *a, **k: pytest.fail("rede"))
    for ruim in ("abc", "0", "-5", "nan", "inf"):
        assert cli.main(["publicar", "--piso-campanha", ruim, "--saida", str(tmp_path / "o")]) == 2


def test_cli_publicar_missing_zip_exit_1(zips, tmp_path, capsys):
    assert cli.main(["publicar", "--zip", str(tmp_path / "nao.zip"), "--eleitos-zip", str(zips[1]),
                     "--saida", str(tmp_path / "o")]) == 1
    assert "zip" in capsys.readouterr().err
    assert cli.main(["publicar", "--zip", str(zips[0]), "--eleitos-zip", str(tmp_path / "nao.zip"),
                     "--saida", str(tmp_path / "o")]) == 1


def test_cli_publicar_ok(zips, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "download_candidatos", lambda *a, **k: pytest.fail("rede"))
    assert cli.main(["publicar", "--zip", str(zips[0]), "--eleitos-zip", str(zips[1]),
                     "--saida", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "index.json").is_file()


# --- fonte do dinheiro (despesas pagas) ---

def test_pago_publico_allocates_by_fonte(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    rn = _ler(tmp_path / "o", "RN")["recortes"]
    gov = rn["governador"]
    assert gov["pago"] == 6000.0 + 2000.0 + 1000.0 + 900.0
    assert gov["pago_publico"] == 6000.0 + 2000.0 + 900.0  # FEFC + Fundo Partidario; Outros Recursos nao
    assert gov["pct_publico"] == round(8900.0 / 9900.0, 6)
    assert rn["deputado-federal"]["pago"] == 5000.0 and rn["deputado-federal"]["pago_publico"] == 0.0
    assert rn["todos"]["pago"] == 14900.0 and rn["todos"]["pago_publico"] == 8900.0
    assert rn["todos"]["pct_publico"] == round(8900.0 / 14900.0, 6)


def test_pago_split_proportionally_when_sq_has_non_ad_items():
    df = pd.DataFrame({
        "sq_despesa": ["10", "10", "11"], "sq_candidato": ["1", "1", "2"],
        "valor": [1000.0, 3000.0, 500.0], "nivel": ["confirmado", "nenhum", "generico"],
    })
    pagos = pd.DataFrame({"sq_despesa": ["10", "10", "11"], "fonte": [FEFC, OR, FP],
                          "valor": [2000.0, 2000.0, 500.0]})
    out, sem_linha, desconhecidas = publicar.alocar_pagamentos(df, pagos)
    assert list(out["pago"]) == [1000.0, 0.0, 500.0]  # 4000 pagos x 1000/4000; item "nenhum" fora
    assert list(out["pago_publico"]) == [500.0, 0.0, 500.0]
    assert sem_linha == (0, 0.0) and desconhecidas == {}


def test_pct_publico_zero_when_nothing_paid(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    pres = _ler(tmp_path / "o", "BR")["recortes"]["presidente"]
    assert (pres["pago"], pres["pago_publico"], pres["pct_publico"], pres["cobertura_pago"]) == (0.0, 0.0, 0.0, 0.0)
    ac = _ler(tmp_path / "o", "AC")["recortes"]["todos"]
    assert ac["principal"] == 0.0 and ac["cobertura_pago"] == 0.0 and ac["proporcao"] == 0.0


def test_cobertura_pago_is_pago_over_principal(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    gov = _ler(tmp_path / "o", "RN")["recortes"]["governador"]
    assert gov["principal"] == 10900.0
    assert gov["cobertura_pago"] == round(9900.0 / 10900.0, 6)


def test_unmatched_payments_ignored(zips, tmp_path):
    res = _pub(zips, tmp_path / "o")
    assert res.pagamentos_sem_linha == 1 and res.valor_sem_linha == 123.0
    assert res.pasta == tmp_path / "o"
    total_pago = sum(_ler(tmp_path / "o", u)["recortes"]["todos"]["pago"] for u in ("RN", "DF", "SP", "AC"))
    assert total_pago == 14900.0  # os 123 sem linha e os 50000 de item que nao e anuncio nao entram


def test_publicar_fields_present_in_every_recorte(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    campos = ["pago", "pago_publico", "pct_publico", "cobertura_pago"]
    for f in (tmp_path / "o").glob("[A-Z][A-Z].json"):
        for r in json.loads(f.read_text(encoding="utf-8"))["recortes"].values():
            keys = list(r)
            assert keys[keys.index("n_elegiveis") + 1: keys.index("n_elegiveis") + 5] == campos
            assert "cobertura_pago" in r and r["tetos"] is not None


def test_missing_paid_file_in_zip_is_error(zips, tmp_path):
    z = tmp_path / "sem_pagas.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("despesas_contratadas_candidatos_2026_BRASIL.csv", _csv(CAB_DESP, LINHAS))
    with pytest.raises(FileNotFoundError):
        publicar.publicar(z, zips[1], tmp_path / "o")


# --- itens do review da Task 1 ---

def test_uf_without_declared_expenses_has_zeroed_valid_json(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    ac = _ler(tmp_path / "o", "AC")
    assert list(ac["recortes"]) == ["todos", "governador"]
    r = ac["recortes"]["governador"]
    assert (r["total"], r["n_candidatos"], r["n_gastaram"], r["n_elegiveis"], r["top"]) == (0.0, 0, 0, 0, [])
    assert all(t["n_acima"] == 0 and t["pct_acima"] == 0.0 for t in r["tetos"])


def test_uf_without_site_cargos_has_no_file_nor_index_entry(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    assert not (tmp_path / "o" / "AP.json").exists()
    assert "AP" not in [u["uf"] for u in _ler(tmp_path / "o", "index")["ufs"]]


def test_candidate_missing_from_consulta_cand_falls_back_to_expense_name(zips, tmp_path):
    _pub(zips, tmp_path / "o")
    sp = _ler(tmp_path / "o", "SP")
    assert sp["recortes"]["todos"]["top"][0]["nome"] == "Nome Sem Cadastro"
    assert (sp["n_candidatos_total"], sp["segundo_turno"]) == (0, 0)


def test_gravar_rejects_nan(tmp_path):
    with pytest.raises(ValueError):
        publicar._gravar(tmp_path / "x.json", {"a": float("nan")})


# --- fix round 1 ---

def _rec(s):
    return publicar.montar_recorte(s, "Governo", "Governador", {}, [0.05], 50000.0)


def test_cobertura_clamped_at_one_when_pago_exceeds_principal():
    r = _rec(_shares([_sh("1", 1000.0, 100.0)], pago=130.0, pago_publico=65.0))
    assert r["cobertura_pago"] == 1.0
    assert r["pago"] == 130.0 and r["pct_publico"] == 0.5  # pago e pct_publico nao mudam


def test_cobertura_not_clamped_below_one_and_zero_without_principal():
    r = _rec(_shares([_sh("1", 1000.0, 100.0)], pago=40.0, pago_publico=0.0))
    assert r["cobertura_pago"] == 0.4
    r0 = _rec(_shares([_sh("1", 1000.0, 0.0)], pago=0.0, pago_publico=0.0))
    assert r0["cobertura_pago"] == 0.0


def test_montar_recorte_requires_pago_columns():
    s = _shares([_sh("1", 1000.0, 100.0)]).drop(columns=["pago", "pago_publico"])
    with pytest.raises(ValueError, match="pago"):
        _rec(s)


def test_fonte_matching_ignores_accent_case_and_spaces_and_reports_unknown():
    df = pd.DataFrame({"sq_despesa": ["1", "2", "3", "4", "5"], "sq_candidato": ["a"] * 5,
                       "valor": [100.0] * 5, "nivel": ["confirmado"] * 5})
    pagos = pd.DataFrame({
        "sq_despesa": ["1", "2", "3", "4", "5"],
        "fonte": ["FUNDO ESPECIAL DE FINANCIAMENTO DE CAMPANHA", "  fundo  partidario ", "Fundo Partidário",
                  "outros recursos", "Fonte Nova"],
        "valor": [10.0, 20.0, 30.0, 40.0, 50.0]})
    out, _, desconhecidas = publicar.alocar_pagamentos(df, pagos)
    assert list(out["pago_publico"]) == [10.0, 20.0, 30.0, 0.0, 0.0]
    assert list(out["pago"]) == [10.0, 20.0, 30.0, 40.0, 50.0]
    assert desconhecidas == {"Fonte Nova": 50.0}


def test_paid_sq_with_zero_contracted_total_is_unmatched():
    df = pd.DataFrame({"sq_despesa": ["1"], "sq_candidato": ["a"], "valor": [0.0], "nivel": ["confirmado"]})
    pagos = pd.DataFrame({"sq_despesa": ["1"], "fonte": [FEFC], "valor": [70.0]})
    out, sem_linha, _ = publicar.alocar_pagamentos(df, pagos)
    assert sem_linha == (1, 70.0) and list(out["pago"]) == [0.0]


def _zip_custom(tmp_path, linhas, pagos):
    z = tmp_path / "c.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("despesas_contratadas_candidatos_2026_BRASIL.csv", _csv(CAB_DESP, linhas))
        f.writestr("despesas_pagas_candidatos_2026_BRASIL.csv", _csv(CAB_PAGO, pagos))
    return z


def _l(uf, sq, cargo, forn, valor, sqd):
    r = _desp(uf, sq, "NOME " + sq, cargo, forn, valor)
    r[12] = sqd
    return r


def test_full_flow_two_fontes_partial_ad_lines_and_no_cross_uf_attribution(zips, tmp_path):
    # mesmo padrao de SQ_DESPESA em duas UFs/cargos, com fontes diferentes: atribuicao errada de UF falharia
    linhas = [
        _l("RN", "1", "Governador", FB, "1000,00", "5001"), _l("RN", "1", "Governador", OUTRO, "3000,00", "5001"),
        _l("DF", "2", "Deputado Distrital", FB, "1000,00", "5002"), _l("DF", "2", "Deputado Distrital", OUTRO, "3000,00", "5002"),
    ]
    pagos = [["5001", FEFC, "2000,00"], ["5001", OR, "2000,00"],
             ["5002", FP, "1000,00"], ["5002", OR, "3000,00"]]
    z = _zip_custom(tmp_path, linhas, pagos)
    res = publicar.publicar(z, zips[1], tmp_path / "o")
    rn = _ler(tmp_path / "o", "RN")["recortes"]["governador"]
    df_ = _ler(tmp_path / "o", "DF")["recortes"]["deputado-distrital"]
    # RN: pago 4000 x 1000/4000 = 1000 (FEFC 2000 -> 500 publico)
    assert (rn["pago"], rn["pago_publico"], rn["pct_publico"]) == (1000.0, 500.0, 0.5)
    # DF: pago 4000 x 1/4 = 1000 (Fundo Partidario 1000 -> 250 publico)
    assert (df_["pago"], df_["pago_publico"], df_["pct_publico"]) == (1000.0, 250.0, 0.25)
    assert res.pagamentos_sem_linha == 0 and res.fontes_desconhecidas == {}


def test_publicar_reports_unknown_fontes(zips, tmp_path, capsys):
    linhas = [_l("RN", "1", "Governador", FB, "1000,00", "5001")]
    z = _zip_custom(tmp_path, linhas, [["5001", "Fonte Misteriosa", "300,00"]])
    res = publicar.publicar(z, zips[1], tmp_path / "o")
    assert res.fontes_desconhecidas == {"Fonte Misteriosa": 300.0}
    assert _ler(tmp_path / "o", "RN")["recortes"]["governador"]["pago_publico"] == 0.0
    assert cli.main(["publicar", "--zip", str(z), "--eleitos-zip", str(zips[1]), "--saida", str(tmp_path / "p")]) == 0
    assert "Fonte Misteriosa" in capsys.readouterr().err
