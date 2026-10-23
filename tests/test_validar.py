import csv
import zipfile

import pandas as pd
import pytest

from gastos import classify, cli, validar

ORIGEM_IMP = "Despesa com Impulsionamento de Conteúdos"
ORIGEM_OUTRA = "Despesa com Atividades de Militância"


def _df(linhas):
    cols = ["uf", "fornecedor", "descricao", "origem", "valor", "nivel", "sq_despesa"]
    return pd.DataFrame(
        [(u, f, d, o, v, n, str(i)) for i, (u, f, d, o, v, n) in enumerate(linhas)], columns=cols
    )


def test_nucleo_e_periferia():
    df = _df([
        ("RN", "FACEBOOK", "Impulsionamento", ORIGEM_IMP, 800.0, "confirmado"),
        ("RN", "AGENCIA X", "Gestão de tráfego pago", ORIGEM_OUTRA, 150.0, "generico"),
        ("RN", "GRAFICA", "Material", ORIGEM_OUTRA, 999.0, "nenhum"),
        ("RN", "GATEWAY", "x", ORIGEM_OUTRA, 55.0, "provavel"),
    ])
    r = validar.analisar_recorte(df, "RN")
    assert r["principal"] == 950.0
    assert r["nucleo"] == 800.0
    assert r["periferia"] == 150.0
    assert r["pct_nucleo"] == pytest.approx(800 / 950)
    assert list(r["linhas_periferia"]["fornecedor"]) == ["AGENCIA X"]


def test_origem_normalizada_acento_e_caixa():
    df = _df([("RN", "A", "x", "DESPESA COM IMPULSIONAMENTO DE CONTEUDOS", 10.0, "generico")])
    assert validar.analisar_recorte(df, "RN")["nucleo"] == 10.0


def test_pct_nucleo_zero_sem_principal():
    df = _df([("RN", "GRAFICA", "Material", ORIGEM_OUTRA, 10.0, "nenhum")])
    r = validar.analisar_recorte(df, "RN")
    assert r["principal"] == 0 and r["pct_nucleo"] == 0


@pytest.mark.parametrize("texto", [
    "Impulsionamento de posts", "IMPULSIONAR conteúdo", "Anúncios no Instagram", "Meta Ads", "FACEBOOK",
    "Google Ads", "TikTok", "Tráfego Pago", "anuncio", "serviço de impulsão",
])
def test_perdas_casam(texto):
    assert validar.casa_perda(texto)


@pytest.mark.parametrize("texto", ["metodo", "Metalúrgica", "Material gráfico", "anunciante", "googles", "", None])
def test_perdas_nao_casam(texto):
    assert not validar.casa_perda(texto)


def test_possiveis_perdas_so_nenhum():
    df = _df([
        ("RN", "AG", "Gestão de tráfego pago", ORIGEM_OUTRA, 100.0, "nenhum"),
        ("RN", "AG", "Anúncio no Instagram", ORIGEM_OUTRA, 50.0, "confirmado"),
        ("RN", "AG", "Método de campanha", ORIGEM_OUTRA, 70.0, "nenhum"),
    ])
    r = validar.analisar_recorte(df, "RN")
    assert r["possiveis_perdas"] == 100.0
    assert len(r["linhas_perdas"]) == 1


def test_top_ordenado_e_desempate_deterministico():
    linhas = [("RN", f"F{i}", "d", ORIGEM_OUTRA, 10.0, "generico") for i in (3, 1, 2)]
    linhas.append(("RN", "GRANDE", "d", ORIGEM_OUTRA, 99.0, "generico"))
    a = validar.analisar_recorte(_df(linhas), "RN")["linhas_periferia"]
    b = validar.analisar_recorte(_df(linhas[::-1]), "RN")["linhas_periferia"]
    assert list(a["fornecedor"]) == ["GRANDE", "F1", "F2", "F3"]
    assert list(b["fornecedor"]) == list(a["fornecedor"])


def test_colunas_sem_partido_nem_cpf():
    df = _df([("RN", "F", "d", ORIGEM_OUTRA, 1.0, "generico")])
    df["partido"] = "ABC"
    df["candidato"] = "FULANO"
    df["cnpj_fornecedor"] = "123"
    r = validar.analisar_recorte(df, "RN")
    assert list(r["linhas_periferia"].columns) == ["fornecedor", "descricao", "origem", "valor", "nivel"]
    assert list(r["linhas_perdas"].columns) == ["fornecedor", "descricao", "origem", "valor", "nivel"]


# ---------- CLI ----------

HEAD = ('"DT_GERACAO";"SG_UF";"SQ_CANDIDATO";"NM_CANDIDATO";"DS_CARGO";"SG_PARTIDO";"NM_FORNECEDOR_RFB";'
        '"NR_CPF_CNPJ_FORNECEDOR";"DS_DESPESA";"DS_ORIGEM_DESPESA";"VR_DESPESA_CONTRATADA";"DT_DESPESA";'
        '"SQ_DESPESA";"TP_PRESTACAO_CONTAS";"DT_PRESTACAO_CONTAS"')


def _csv(linhas):
    out = [HEAD]
    for i, (uf, cargo, forn, desc, orig, val) in enumerate(linhas):
        out.append(f'"22/10/2026";"{uf}";"{i}";"CANDIDATO SECRETO";"{cargo}";"PARTIDOXYZ";"{forn}";"98765432100";'
                   f'"{desc}";"{orig}";"{val}";"10/09/2026";"{i + 1}";"Parcial";"03/10/2026"')
    return "\n".join(out).encode("latin-1")


LINHAS_RN = [
    ("RN", "Deputado Estadual", "FACEBOOK SERVICOS ONLINE", "Impulsionamento", ORIGEM_IMP, "900,00"),
    ("RN", "Deputado Estadual", "AGENCIA TRAFEGO", "Jingle com impulsionamento", ORIGEM_OUTRA, "100,00"),
    ("RN", "Deputado Estadual", "AGENCIA TRAFEGO", "Gestão de tráfego pago", ORIGEM_OUTRA, "40,00"),
]
LINHAS_BR = [
    ("BR", "Presidente", "GOOGLE BRASIL", "Google Ads", ORIGEM_IMP, "500,00"),
    ("RN", *LINHAS_RN[0][1:]),
    ("RN", *LINHAS_RN[1][1:]),
    ("RN", *LINHAS_RN[2][1:]),
]


@pytest.fixture
def zip_v(tmp_path):
    p = tmp_path / "v.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("despesas_contratadas_candidatos_2026_RN.csv", _csv(LINHAS_RN))
        z.writestr("despesas_contratadas_candidatos_2026_BRASIL.csv", _csv(LINHAS_BR))
    return p


def _ler(p):
    return pd.read_csv(p, sep=";", decimal=",", encoding="utf-8-sig")


def test_cli_uf_gera_arquivos(zip_v, tmp_path):
    saida = tmp_path / "s"
    assert cli.main(["validar", "--uf", "rn", "--zip", str(zip_v), "--saida", str(saida)]) == 0
    assert {p.name for p in saida.iterdir()} == {
        "validacao.md", "validacao.csv", "periferia_RN.csv", "possiveis_perdas_RN.csv"}
    raw = (saida / "validacao.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b";" in raw.splitlines()[0]
    v = _ler(saida / "validacao.csv")
    assert len(v) == 1 and v.loc[0, "uf"] == "RN"
    assert v.loc[0, "principal"] == 1000.0 and v.loc[0, "periferia"] == 100.0
    assert v.loc[0, "possiveis_perdas"] == 40.0
    assert "0,9" in raw.decode("utf-8-sig").splitlines()[1]  # virgula decimal
    assert len(_ler(saida / "periferia_RN.csv")) == 1


def test_cli_todas_ufs_inclui_br(zip_v, tmp_path):
    saida = tmp_path / "s"
    assert cli.main(["validar", "--zip", str(zip_v), "--saida", str(saida)]) == 0
    v = _ler(saida / "validacao.csv")
    assert set(v["uf"]) == {"RN", "BR"}
    assert v.set_index("uf").loc["BR", "principal"] == 500.0
    assert (saida / "periferia_BR.csv").exists()
    md = (saida / "validacao.md").read_text(encoding="utf-8")
    assert "BR" in md and "serviços de agência" in md


def test_cli_saidas_sem_partido_nem_cpf_nem_candidato(zip_v, tmp_path):
    saida = tmp_path / "s"
    cli.main(["validar", "--zip", str(zip_v), "--saida", str(saida)])
    for p in saida.iterdir():
        txt = p.read_text(encoding="utf-8-sig")
        for proibido in ("PARTIDOXYZ", "98765432100", "CANDIDATO SECRETO"):
            assert proibido not in txt, (p.name, proibido)
        if p.suffix == ".csv":
            cab = [c.lower() for c in next(csv.reader(txt.splitlines(), delimiter=";"))]
            assert not {"partido", "cpf", "candidato", "cnpj_fornecedor"} & set(cab)


def test_cli_pasta_padrao(zip_v, tmp_path, monkeypatch):
    regras = classify.load_rules()  # le config/ antes de sair da raiz do projeto
    monkeypatch.setattr(cli, "load_rules", lambda: regras)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["validar", "--uf", "RN", "--zip", str(zip_v)]) == 0
    nomes = [p.name for p in (tmp_path / "out").iterdir()]
    assert len(nomes) == 1 and nomes[0].endswith("_validacao_uf-RN")


@pytest.mark.parametrize("uf", ["R", "RNN", "1A", ""])
def test_cli_uf_invalida_sai_2(uf, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "download_candidatos", lambda *a, **k: pytest.fail("baixou"))
    assert cli.main(["validar", "--uf", uf, "--saida", str(tmp_path / "s")]) == 2
    assert "uf" in capsys.readouterr().err.lower()
    assert not (tmp_path / "s").exists()


def test_cli_zip_ruim_sai_1(tmp_path, capsys):
    assert cli.main(["validar", "--uf", "RN", "--zip", str(tmp_path / "nao.zip"), "--saida", str(tmp_path / "s")]) == 1
    assert "zip" in capsys.readouterr().err.lower()


def test_cli_uf_inexistente_sai_1(zip_v, tmp_path):
    assert cli.main(["validar", "--uf", "ZZ", "--zip", str(zip_v), "--saida", str(tmp_path / "s")]) == 1


def test_todas_ufs_limita_50_linhas(tmp_path):
    linhas = [("RN", "Deputado Estadual", f"F{i}", "Jingle com impulsionamento", ORIGEM_OUTRA, f"{i + 1},00")
              for i in range(60)]
    linhas.append(("RN", "Deputado Estadual", "FB", "Imp", ORIGEM_IMP, "10,00"))
    p = tmp_path / "g.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("despesas_contratadas_candidatos_2026_BRASIL.csv", _csv(linhas))
    assert cli.main(["validar", "--zip", str(p), "--saida", str(tmp_path / "s")]) == 0
    per = _ler(tmp_path / "s" / "periferia_RN.csv")
    assert len(per) == 50 and per["valor"].iloc[0] == 60.0
