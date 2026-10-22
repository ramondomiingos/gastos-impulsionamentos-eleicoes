import re
import zipfile

import pandas as pd
import pytest

from gastos import cli, emails, loader
from gastos.eleitos import load_eleitos

FIX = emails.Path(__file__).parent / "fixtures"
PARTIDOS = ["PT", "PSD", "PL", "NOVO", "MDB", "ABC"]


@pytest.fixture
def stats():
    return {
        "total": 100000.0, "principal": 12345.67, "confirmado": 8000.5, "provavel": 777.77,
        "proporcao": 0.1235, "mediana": 0.05, "p90": 0.3,
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
    assert "5,0%" in t and "30,0%" in t  # mediana e p90
    assert "R$ 4.321,00" in t and "25,0%" in t


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
    assert "Prezado(a) Maria Exemplo" in t and "Deputada Federal" in t


def test_email_forbidden_content(contato, stats):
    t = render(contato, stats)
    assert "dinheiro público" not in t.lower() and "dinheiro publico" not in t.lower()
    for nome in ("JOSE DA SILVA", "JOÃO DA SILVA", "MARIA SOUZA"):
        assert nome.lower() not in t.lower()
    for p in PARTIDOS:
        assert re.search(rf"\b{p}\b", t) is None


def test_provavel_only_in_note(contato, stats):
    t = render(contato, stats)
    assert t.count("R$ 777,77") == 1
    idx = t.index("R$ 777,77")
    assert idx > t.index("pelo menos") and idx > t.index("parcia")
    assert "não incluído" in t[idx:idx + 300]
    # nunca somado: principal+provavel nao aparece
    assert "R$ 13.123,44" not in t


def test_provavel_note_omitted_when_zero(contato, stats):
    stats["provavel"] = 0.0
    assert "não incluído" not in render(contato, stats)


@pytest.mark.parametrize("campo,valor", [
    ("principal", None), ("principal", float("nan")), ("principal", 0.0), ("total", 0.0),
    ("confirmado", None), ("mediana", float("nan")), ("p90", None),
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
