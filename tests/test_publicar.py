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
    return [ger, uf, sq, nome, cargo, "ABC", forn, cnpj, desc, "Despesa", valor, "10/09/2026", n, "Parcial", prest]


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
    # Presidente
    _desp("BR", "6", "CARLOS PRESIDENTE", "Presidente", FB, "300000,00"),
    _desp("BR", "6", "CARLOS PRESIDENTE", "Presidente", OUTRO, "700000,00"),
]
CAB_CAND = ["SG_UF", "DS_CARGO", "SQ_CANDIDATO", "NM_CANDIDATO", "DS_SIT_TOT_TURNO", "NR_TURNO"]
CANDS = [
    ["RN", "GOVERNADOR", "1", "JOÃO D'ÁVILA DA SILVA", "2º TURNO", "1"],
    ["RN", "GOVERNADOR", "1", "JOÃO D'ÁVILA DA SILVA", "2º TURNO", "2"],
    ["RN", "GOVERNADOR", "2", "ZÉ PEQUENO", "NÃO ELEITO", "1"],
    ["RN", "DEPUTADO FEDERAL", "3", "MARIA DE SOUZA LIMA", "ELEITO", "1"],
    ["RN", "DEPUTADO FEDERAL", "30", "SEM DESPESA", "SUPLENTE", "1"],
    ["RN", "DEPUTADO ESTADUAL", "4", "PEDRO LIMA", "ELEITO", "1"],
    ["RN", "VICE-GOVERNADOR", "40", "VICE", "ELEITO", "1"],
    ["DF", "DEPUTADO DISTRITAL", "5", "ANA DISTRITAL", "ELEITO", "1"],
    ["BR", "PRESIDENTE", "6", "CARLOS PRESIDENTE", "2º TURNO", "1"],
]


@pytest.fixture
def zips(tmp_path):
    z = tmp_path / "desp.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("despesas_contratadas_candidatos_2026_BRASIL.csv", _csv(CAB_DESP, LINHAS))
    e = tmp_path / "cand.zip"
    with zipfile.ZipFile(e, "w") as f:
        f.writestr("consulta_cand_2026_BRASIL.csv", _csv(CAB_CAND, CANDS))
        f.writestr("consulta_cand_2026_RN.csv", b"lixo")
    return z, e


def _shares(rows):
    df = pd.DataFrame(rows, columns=["sq_candidato", "uf", "cargo", "partido", "candidato", "total",
                                     "confirmado", "generico", "provavel"])
    df["principal"] = df["confirmado"] + df["generico"]
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
                       "proporcao", "n_candidatos", "n_gastaram", "n_elegiveis", "tetos", "top"]
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
    for f in (tmp_path / "o").glob("*.json"):
        assert "partido" not in set(_chaves(json.loads(f.read_text(encoding="utf-8")))), f.name


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
    assert nomes == ["BR.json", "DF.json", "RN.json", "index.json"]
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
