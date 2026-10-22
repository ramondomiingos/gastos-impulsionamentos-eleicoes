import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from gastos import cli, emails, loader, report
from gastos.classify import classify, load_rules
from gastos.eleitos import load_eleitos

FIX = Path(__file__).parent / "fixtures"
PARTIDOS = ["PT", "PSD", "PL", "NOVO", "MDB", "ABC"]


@pytest.fixture
def stats():
    return {
        "total": 100000.0, "principal": 12345.67, "confirmado": 8000.5, "provavel": 777.77,
        "proporcao": 0.1235, "mediana": 0.05, "p90": 0.42, "max": 0.9,
        "n_candidatos": 200, "n_gastaram": 60,
        "impacto_teto": {"n_acima": 7, "pct_acima": 0.25, "excedente": 4321.0},
    }


@pytest.fixture
def contato():
    return pd.Series({"nome": "Maria Exemplo", "cargo": "Deputada Federal", "uf": "RN",
                      "email": "m@example.org"})


def render(contato, stats, **kw):
    return emails.render_email(contato, stats, 0.10, "22/10/2026", **kw)


def test_email_mentions_partial_and_cutoff(contato, stats):
    t = render(contato, stats)
    assert "parcia" in t.lower() and "22/10/2026" in t


def test_email_has_state_numbers_and_floor(contato, stats):
    t = render(contato, stats)
    assert "R$ 12.345,67" in t
    assert "R$ 8.000,50" in t and "pelo menos" in t
    assert "12,3%" in t  # proporcao
    assert "60 de 200 candidatos que declararam gasto de campanha (30,0%)" in t
    assert "cerca de 1 em cada 10" in t and "42,0%" in t
    assert "7 candidatos, 25,0% dos 200 que declararam gasto de campanha," in t
    assert "**Gasto estimado com plataformas estrangeiras:** R$ 12.345,67" in t
    assert "mediana" not in t.lower() and "excedente" not in t.lower()
    assert "ultrapassaria esse limite somaria R$ 4.321,00" in t


def test_email_proposes_percentage_ceiling_and_invites(contato, stats):
    t = render(contato, stats)
    assert "10%" in t and "teto" in t.lower()
    assert "ajud" in t.lower()
    assert re.search(r"\bPL\s*\d|projeto de lei n", t, re.I) is None


def test_email_first_line_subject_and_signature(contato, stats):
    t = render(contato, stats)
    assert t.splitlines()[0].startswith("Assunto: ")
    assert "[Seu nome]" in t
    assert "Ana Silva" in render(contato, stats, assinatura="Ana Silva")
    assert "Prezado(a) Deputado(a) Federal Maria Exemplo," in t


def test_email_forbidden_content(zip_path, tmp_path):
    df = loader.load_despesas(zip_path, "RN")
    nomes = {n.strip() for n in df["candidato"] if n.strip()}
    partidos = {p.strip() for p in df["partido"] if p.strip()}
    assert nomes and partidos
    pasta = cli.rodar_uf(zip_path, "RN", tmp_path / "runs", [0.10])
    stats, corte = emails.stats_from_run(pasta, 0.10)
    t = emails.render_email(pd.Series({"nome": "Maria Exemplo", "cargo": "Senador", "uf": "RN"}),
                            stats, 0.10, corte)
    low = t.lower()
    assert "dinheiro público" not in low and "dinheiro publico" not in low
    for n in nomes:
        assert n.lower() not in low
    for p in partidos:
        assert re.search(rf"\b{re.escape(p)}\b", t, re.I) is None


def test_provavel_only_in_note(contato, stats):
    t = render(contato, stats)
    assert t.count("R$ 777,77") == 1
    idx = t.index("R$ 777,77")
    assert idx > t.index("pelo menos") and idx > t.index("parcia")
    assert "não incluído" in t[idx:idx + 300]
    assert t.strip().endswith("(não incluído).")
    # nunca somado: principal+provavel nao aparece
    assert "R$ 13.123,44" not in t


@pytest.mark.parametrize("provavel,aparece", [
    (0.0, False), (100.0, False), (123.4, False), (123.4567, True), (777.77, True)])
def test_provavel_note_threshold_one_percent(contato, stats, provavel, aparece):
    stats["provavel"] = provavel
    t = render(contato, stats)
    assert ("não incluído" in t) is aparece
    assert "R$ 12.345,67" in t  # principal inalterado


@pytest.mark.parametrize("campo,valor", [
    ("principal", None), ("principal", float("nan")), ("principal", 0.0), ("total", 0.0),
    ("confirmado", None), ("n_gastaram", None), ("n_candidatos", 0), ("p90", None),
    ("impacto_teto", None),
])
def test_never_rendered_without_numbers(contato, stats, campo, valor):
    stats[campo] = valor
    with pytest.raises(ValueError):
        render(contato, stats)


def test_missing_key_or_cutoff_raises(contato, stats):
    del stats["proporcao"]
    with pytest.raises(ValueError):
        render(contato, stats)


def test_no_cutoff_raises(contato, stats):
    with pytest.raises(ValueError):
        emails.render_email(contato, stats, 0.10, "")


# ---------------- load_contatos ----------------

def _csv(tmp_path, texto, enc="utf-8-sig"):
    p = tmp_path / "c.csv"
    p.write_bytes(texto.encode(enc))
    return p


def test_load_contatos_semicolon_and_comma(tmp_path):
    a = emails.load_contatos(_csv(tmp_path, "nome;cargo;uf;email\n Ana ; Senador ;rn; a@x.org \n"))
    b = emails.load_contatos(_csv(tmp_path, "nome,cargo,uf,email\nAna,Senador,RN,a@x.org\n"))
    assert a.iloc[0]["nome"] == "Ana" and a.iloc[0]["email"] == "a@x.org"
    assert list(a.columns)[:4] == ["nome", "cargo", "uf", "email"]
    assert b.iloc[0]["uf"] == "RN" and a.iloc[0]["uf"] == "RN"


def test_load_contatos_optional_sq_and_blank_rows(tmp_path):
    d = emails.load_contatos(_csv(tmp_path, "nome,cargo,uf,email,sq_candidato\nAna,Senador,RN,a@x.org,12\n,,,,\n \n"))
    assert len(d) == 1 and d.iloc[0]["sq_candidato"] == "12"


def test_load_contatos_missing_column(tmp_path):
    with pytest.raises(ValueError, match="email"):
        emails.load_contatos(_csv(tmp_path, "nome,cargo,uf\nAna,Senador,RN\n"))


def test_load_contatos_empty(tmp_path):
    with pytest.raises(ValueError, match="vazio"):
        emails.load_contatos(_csv(tmp_path, ""))
    with pytest.raises(ValueError, match="vazio"):
        emails.load_contatos(_csv(tmp_path, "nome,cargo,uf,email\n,,,\n"))


def test_load_contatos_invalid_emails_list_rows(tmp_path):
    txt = "nome,cargo,uf,email\nAna,Senador,RN,a@x.org\nBia,Senador,RN,sem-arroba\nCa,Senador,RN,c@semponto\nDi,Senador,RN,\n"
    with pytest.raises(ValueError) as e:
        emails.load_contatos(_csv(tmp_path, txt))
    msg = str(e.value)
    assert msg.split(":")[-1].split(", ") == [" 3", "4", "5"]


# ---------------- pipeline ----------------

@pytest.fixture
def uf_runs(zip_path, tmp_path):
    pasta = cli.rodar_uf(zip_path, "RN", tmp_path / "runs", [0.10])
    return {"RN": pasta}


def _contatos(tmp_path, linhas):
    cab = "nome,cargo,uf,email,sq_candidato\n"
    p = tmp_path / "contatos.csv"
    p.write_text(cab + "\n".join(linhas) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def eleitos():
    return load_eleitos(FIX / "eleitos.csv")


def test_write_emails_same_uf_same_numbers(tmp_path, uf_runs, eleitos):
    c = _contatos(tmp_path, [
        "José da Silva,Deputado Federal,RN,jose@example.org,",
        "Carlos Alberto,Senador,RN,carlos@example.org,",
    ])
    out = emails.write_emails(c, uf_runs, 0.10, tmp_path / "saida", eleitos=eleitos)
    arqs = sorted((out / "emails" / "rn").glob("*.md"))
    assert len(arqs) == 2
    corpos = [re.sub(r"Prezado\(a\)[^\n]*", "", a.read_text(encoding="utf-8")) for a in arqs]
    assert corpos[0] == corpos[1]
    idx = pd.read_csv(out / "indice.csv", sep=";", encoding="utf-8-sig", dtype=str)
    assert list(idx.columns) == ["nome", "cargo", "uf", "email", "arquivo"] and len(idx) == 2
    assert (out / "pendencias.md").exists()
    assert any(p.is_dir() for p in (out / "runs").iterdir())  # copia da execucao


def test_write_emails_pendencias_and_no_file(tmp_path, uf_runs, eleitos):
    c = _contatos(tmp_path, [
        "José da Silva,Deputado Federal,RN,jose@example.org,",
        "Fulano Inexistente,Deputado Federal,RN,fulano@example.org,",
        "João Pereira,Deputado Estadual,SP,joao@example.org,",   # SP sem dados
    ])
    out = emails.write_emails(c, uf_runs, 0.10, tmp_path / "saida", eleitos=eleitos)
    pend = (out / "pendencias.md").read_text(encoding="utf-8")
    assert "Fulano Inexistente" in pend and "sem_correspondencia" in pend
    assert "João Pereira" in pend and "SP" in pend
    arquivos = list((out / "emails").rglob("*.md"))
    assert len(arquivos) == 1
    assert not (out / "emails" / "SP").exists()


def test_write_emails_uf_without_classified_spend(tmp_path, zip_path, eleitos):
    # corta todo o gasto classificado: run com principal 0
    pasta = tmp_path / "runs" / "x_RN"
    pasta.mkdir(parents=True)
    pd.DataFrame([{"total": 10.0, "confirmado": 0.0, "generico": 0.0, "provavel": 0.0,
                   "principal": 0.0, "proporcao": 0.0, "n_candidatos": 1}]).to_csv(
        pasta / "resumo.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
    pd.DataFrame([{"sq_candidato": "1", "total": 10.0, "principal": 0.0, "proporcao": 0.0}]).to_csv(
        pasta / "candidatos.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
    c = _contatos(tmp_path, ["José da Silva,Deputado Federal,RN,jose@example.org,"])
    out = emails.write_emails(c, {"RN": pasta}, 0.10, tmp_path / "saida", eleitos=eleitos)
    assert not list(out.rglob("emails/**/*.md"))
    assert "RN" in (out / "pendencias.md").read_text(encoding="utf-8")


def test_pendencias_warns_incomplete_eleitos(tmp_path, uf_runs, eleitos):
    c = _contatos(tmp_path, [
        "José da Silva,Deputado Federal,RN,jose@example.org,",
        "Rosilene,Senador,PB,r@example.org,",  # PB sem eleito para senador
    ])
    out = emails.write_emails(c, uf_runs, 0.10, tmp_path / "saida", eleitos=eleitos)
    pend = (out / "pendencias.md").read_text(encoding="utf-8")
    assert "incompleta" in pend and "PB" in pend


def test_cli_emails(tmp_path, zip_path, monkeypatch):
    c = _contatos(tmp_path, ["José da Silva,Deputado Federal,RN,jose@example.org,"])
    monkeypatch.setattr(cli, "download_candidatos", lambda *a, **k: zip_path)
    monkeypatch.setattr(cli, "download_resultados", lambda *a, **k: FIX / "eleitos.csv")
    saida = tmp_path / "saida"
    rc = cli.main(["emails", "--contatos", str(c), "--teto", "0.10", "--saida", str(saida),
                   "--assinatura", "Ana Silva"])
    assert rc == 0
    md = list((saida / "emails").rglob("*.md"))
    assert len(md) == 1 and "Ana Silva" in md[0].read_text(encoding="utf-8")


@pytest.mark.parametrize("teto", ["0", "-0.1", "1.5", "abc", "nan"])
def test_cli_emails_invalid_teto(tmp_path, teto, capsys):
    c = _contatos(tmp_path, ["José da Silva,Deputado Federal,RN,jose@example.org,"])
    assert cli.main(["emails", "--contatos", str(c), "--teto", teto, "--saida", str(tmp_path / "s")]) == 2


# ---------------- fix round 1 ----------------

def _c(nome, cargo="Deputado Federal", uf="RN"):
    return pd.Series({"nome": nome, "cargo": cargo, "uf": uf})


def test_greeting_neutral_cargo_and_title_case(stats):
    t = render(_c("EANN STYVENSON VALENTIM MENDES DA SILVA e souza", "Senadora"), stats)
    assert "Prezado(a) Senador(a) Eann Styvenson Valentim Mendes da Silva e Souza," in t
    assert "Prezado(a) Deputado(a) Estadual Ana," in render(_c("ANA", "Dep. Estadual"), stats)
    assert "Prezado(a) Governador(a) Ana," in render(_c("ana", "Governador"), stats)
    assert "Prezado(a) Vereador Ana," in render(_c("ana", "Vereador"), stats)


def test_markdown_escaped_in_name_and_signature(stats):
    t = render(_c("A*b_c|d`e\nf"), stats, assinatura="Zé *Bold*\n| x")
    assert "Deputado(a) Federal A\\*b\\_c\\|d\\`e F," in t
    assert "Zé \\*Bold\\* \\| x" in t


def test_metrics_among_spenders_only(tmp_path):
    pasta = tmp_path / "r"
    pasta.mkdir()
    pd.DataFrame([{"total": 1000.0, "confirmado": 100.0, "generico": 0.0, "provavel": 5.0,
                   "principal": 100.0, "proporcao": 0.1, "n_candidatos": 5}]).to_csv(
        pasta / "resumo.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
    pd.DataFrame({"sq_candidato": list("12345"), "total": [100.0] * 4 + [0.0],
                  "principal": [0.0, 0.0, 10.0, 50.0, 0.0],
                  "proporcao": [0.0, 0.0, 0.1, 0.5, 0.0]}).to_csv(
        pasta / "candidatos.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
    (pasta / "meta.json").write_text('{"dt_corte": "01/01/2026"}')
    st, corte = emails.stats_from_run(pasta, 0.10)
    assert corte == "01/01/2026"
    assert st["n_candidatos"] == 4 and st["n_gastaram"] == 2  # so quem declarou gasto
    assert st["max"] == 0.5 and 0.1 < st["p90"] <= 0.5       # entre os que gastaram


def test_stats_match_run_files(uf_runs):
    pasta = uf_runs["RN"]
    r = pd.read_csv(pasta / "resumo.csv", sep=";", decimal=",", encoding="utf-8-sig").iloc[0]
    t = pd.read_csv(pasta / "tetos.csv", sep=";", decimal=",", encoding="utf-8-sig")
    st, _ = emails.stats_from_run(pasta, 0.10)
    assert st["principal"] == pytest.approx(r["confirmado"] + r["generico"])
    assert st["principal"] != pytest.approx(r["confirmado"] + r["generico"] + r["provavel"]) or r["provavel"] == 0
    assert st["confirmado"] == pytest.approx(r["confirmado"]) and st["provavel"] == pytest.approx(r["provavel"])
    row = t[t["teto"].round(4) == 0.10].iloc[0]
    assert st["impacto_teto"]["n_acima"] == row["n_acima"]
    assert st["impacto_teto"]["excedente"] == pytest.approx(row["excedente"])
    assert st["impacto_teto"]["pct_acima"] == pytest.approx(row["pct_acima"])


def test_two_ufs_each_email_has_own_numbers(tmp_path, eleitos):
    runs = {}
    for uf, princ, conf in (("RN", 1111.11, 1000.0), ("SP", 2222.22, 2000.0)):
        p = tmp_path / "runs" / f"x_{uf}"
        p.mkdir(parents=True)
        pd.DataFrame([{"total": 10000.0, "confirmado": conf, "generico": princ - conf, "provavel": 0.0,
                       "principal": princ, "proporcao": princ / 10000, "n_candidatos": 2}]).to_csv(
            p / "resumo.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
        pd.DataFrame({"sq_candidato": ["1", "2"], "total": [5000.0, 5000.0],
                      "principal": [princ, 0.0], "proporcao": [princ / 5000, 0.0]}).to_csv(
            p / "candidatos.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
        (p / "meta.json").write_text(json.dumps({"dt_corte": "10/10/2026" if uf == "RN" else "11/11/2026"}))
        runs[uf] = p
    c = _contatos(tmp_path, ["José da Silva,Deputado Federal,RN,j@example.org,",
                             "João Pereira,Deputado Estadual,SP,jp@example.org,1009"])
    out = emails.write_emails(c, runs, 0.10, tmp_path / "s", eleitos=eleitos)
    rn = next((out / "emails" / "rn").glob("*.md")).read_text(encoding="utf-8")
    sp = next((out / "emails" / "sp").glob("*.md")).read_text(encoding="utf-8")
    assert "R$ 1.111,11" in rn and "R$ 2.222,22" not in rn and "10/10/2026" in rn and "11/11/2026" not in rn
    assert "R$ 2.222,22" in sp and "R$ 1.111,11" not in sp and "11/11/2026" in sp


def test_dt_corte_from_whole_slice(zip_path, tmp_path):
    df = classify(loader.load_despesas(zip_path, "RN"), load_rules())
    i = df.index[df["nivel"] == "nenhum"][0]
    df.loc[i, "dt_geracao"] = "30/10/2026"
    pasta = report.write_run(df, {"uf": "RN"}, out_root=tmp_path / "r", caps=[0.10])
    assert json.loads((pasta / "meta.json").read_text())["dt_corte"] == "30/10/2026"
    assert emails.stats_from_run(pasta, 0.10)[1] == "30/10/2026"


@pytest.mark.parametrize("conteudo", [None, "{ruim", '{"dt_corte": null}', '{"dt_corte": "xx"}'])
def test_missing_or_invalid_meta_goes_to_pendencias(tmp_path, uf_runs, eleitos, conteudo):
    meta = uf_runs["RN"] / "meta.json"
    if conteudo is None:
        meta.unlink()
    else:
        meta.write_text(conteudo)
    c = _contatos(tmp_path, ["José da Silva,Deputado Federal,RN,jose@example.org,"])
    out = emails.write_emails(c, uf_runs, 0.10, tmp_path / "s", eleitos=eleitos)
    assert not list(out.rglob("emails/**/*.md"))
    assert "execução ilegível" in (out / "pendencias.md").read_text(encoding="utf-8")


def test_rerun_removes_stale_emails(tmp_path, uf_runs, eleitos):
    saida = tmp_path / "s"
    c1 = _contatos(tmp_path, ["José da Silva,Deputado Federal,RN,jose@example.org,",
                              "Carlos Alberto,Senador,RN,carlos@example.org,"])
    emails.write_emails(c1, uf_runs, 0.10, saida, eleitos=eleitos)
    c2 = tmp_path / "c2.csv"
    c2.write_text("nome,cargo,uf,email\nCarlos Alberto,Senador,RN,carlos@example.org\n", encoding="utf-8")
    outro = saida / "emails" / "nota.txt"
    outro.write_text("meu")
    emails.write_emails(c2, uf_runs, 0.20, saida, eleitos=eleitos)
    arqs = sorted(p.name for p in (saida / "emails").rglob("*.md"))
    assert arqs == ["carlos-alberto.md"]
    idx = pd.read_csv(saida / "indice.csv", sep=";", encoding="utf-8-sig")
    assert len(idx) == 1
    assert outro.exists()  # so apaga o que a ferramenta escreve


def test_render_error_per_contact_goes_to_pendencias(tmp_path, uf_runs, eleitos):
    r = uf_runs["RN"] / "resumo.csv"
    d = pd.read_csv(r, sep=";", decimal=",", encoding="utf-8-sig")
    d["provavel"] = float("nan")
    d.to_csv(r, index=False, sep=";", decimal=",", encoding="utf-8-sig")
    c = _contatos(tmp_path, ["José da Silva,Deputado Federal,RN,jose@example.org,",
                             "Carlos Alberto,Senador,RN,carlos@example.org,"])
    out = emails.write_emails(c, uf_runs, 0.10, tmp_path / "s", eleitos=eleitos)
    assert not list(out.rglob("emails/**/*.md"))
    pend = (out / "pendencias.md").read_text(encoding="utf-8")
    assert "José da Silva" in pend and "Carlos Alberto" in pend and "falha ao gerar" in pend


def test_slug_collision_gets_suffix(tmp_path, uf_runs):
    el = pd.DataFrame([
        {"nome": "ANA SILVA", "cargo": "DEPUTADO FEDERAL", "uf": "RN", "partido": "X", "sq_candidato": "1", "nome_urna": "ANA"},
        {"nome": "ANA SILVA", "cargo": "SENADOR", "uf": "RN", "partido": "X", "sq_candidato": "2", "nome_urna": "ANA S"},
    ])
    c = _contatos(tmp_path, ["Ana Silva,Deputado Federal,RN,a@example.org,",
                             "Ana Silva,Senador,RN,b@example.org,"])
    out = emails.write_emails(c, uf_runs, 0.10, tmp_path / "s", eleitos=el)
    assert sorted(p.name for p in (out / "emails" / "rn").glob("*.md")) == ["ana-silva-2.md", "ana-silva.md"]


def test_cli_missing_zip_fails_fast(tmp_path, capsys):
    c = _contatos(tmp_path, ["José da Silva,Deputado Federal,RN,jose@example.org,"])
    rc = cli.main(["emails", "--contatos", str(c), "--teto", "0.1", "--saida", str(tmp_path / "s"),
                   "--zip", str(tmp_path / "nao_existe.zip")])
    assert rc == 1 and "nao_existe.zip" in capsys.readouterr().err
    assert not (tmp_path / "s").exists()
    ruim = tmp_path / "ruim.zip"
    ruim.write_text("nao e zip")
    assert cli.main(["emails", "--contatos", str(c), "--teto", "0.1", "--saida", str(tmp_path / "s"),
                     "--zip", str(ruim)]) == 1


@pytest.mark.parametrize("entrada,esperado", [
    ("MARIA-CLARA D'AVILA", "Maria-Clara D'Avila"),
    ("JOÃO DA SILVA II", "João da Silva II"),
    ("carlos de souza iv", "Carlos de Souza IV"),
    ("PEDRO LIMA JR", "Pedro Lima Jr"),
    ("jose alves JUNIOR", "Jose Alves Junior"),
    ("ZE FILHO", "Ze Filho"),
    ("DE LA CRUZ E SILVA III", "De La Cruz e Silva III"),
])
def test_nome_proprio(entrada, esperado):
    assert emails._nome_proprio(entrada) == esperado
