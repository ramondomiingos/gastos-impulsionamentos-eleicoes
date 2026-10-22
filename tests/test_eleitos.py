import zipfile
from pathlib import Path

import pandas as pd

from gastos import eleitos as el
from gastos.eleitos import load_eleitos, match_contatos

FIX = Path(__file__).parent / "fixtures"


def _contatos(*linhas):
    return pd.DataFrame(linhas, columns=["nome", "cargo", "uf", "email"])


def test_only_elected_loaded():
    e = load_eleitos(FIX / "eleitos.csv")
    assert list(e.columns[:5]) == ["nome", "cargo", "uf", "partido", "sq_candidato"]
    assert sorted(e.sq_candidato) == ["1001", "1002", "1005", "1009", "1010", "1011"]
    # suplentes, nao eleitos, #NULO, 2o turno e cargos de suplente ficam fora
    assert not {"1003", "1004", "1006", "1007", "1008"} & set(e.sq_candidato)


def test_load_eleitos_from_zip(tmp_path):
    z = tmp_path / "c.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("consulta_cand_2026_BRASIL.csv", (FIX / "eleitos.csv").read_bytes())
        zf.writestr("consulta_cand_2026_RN.csv", b"lixo")
    assert len(load_eleitos(z)) == 6


def test_match_by_normalized_name_uf_cargo():
    e = load_eleitos(FIX / "eleitos.csv")
    c = _contatos(("José da Silva", "Deputado Federal", "rn", "a@x.org"))
    casados, pendentes = match_contatos(c, e)
    assert len(pendentes) == 0
    assert casados.iloc[0].sq_candidato == "1001"
    assert casados.iloc[0].email == "a@x.org"


def test_match_by_ballot_name_and_cargo_variants():
    e = load_eleitos(FIX / "eleitos.csv")
    c = _contatos(("Maria do Povo", "Deputada Federal", "RN", "m@x.org"),
                  ("Carlos Alberto", "senador", "RN", "c@x.org"))
    casados, pendentes = match_contatos(c, e)
    assert sorted(casados.sq_candidato) == ["1002", "1005"]
    assert pendentes.empty


def test_unmatched_goes_to_pendentes():
    e = load_eleitos(FIX / "eleitos.csv")
    c = _contatos(("Fulano Inexistente", "Deputado Federal", "RN", "f@x.org"),
                  ("José da Silva", "Deputado Federal", "SP", "j@x.org"),  # UF errada
                  ("José da Silva", "Cargo Estranho", "RN", "j@x.org"))
    casados, pendentes = match_contatos(c, e)
    assert casados.empty
    assert list(pendentes.motivo) == ["sem_correspondencia"] * 3


def test_ambiguous_goes_to_pendentes():
    e = load_eleitos(FIX / "eleitos.csv")
    # 1009 (nome legal) e 1010/1011 (urna "JOAO DO BAIRRO") -> mesmo nome normalizado
    c = _contatos(("João Pereira", "Deputado Estadual", "SP", "j@x.org"),
                  ("Joao do Bairro", "Dep. Estadual", "SP", "b@x.org"))
    casados, pendentes = match_contatos(c, e)
    assert casados.empty
    assert list(pendentes.motivo) == ["ambiguo", "ambiguo"]


def test_sq_candidato_column_wins():
    e = load_eleitos(FIX / "eleitos.csv")
    c = pd.read_csv(FIX / "contatos.csv", dtype=str, keep_default_na=False)
    casados, pendentes = match_contatos(c, e)
    ze = casados[casados.email == "ze@example.org"]
    assert list(ze.sq_candidato) == ["1002"]  # sq vence o nome
    assert set(pendentes.email) == {"fulano@example.org", "joao@example.org", "bairro@example.org"}
    # sq informado mas nao eleito: nao cai no casamento por nome
    c2 = _contatos(("José da Silva", "Deputado Federal", "RN", "a@x.org"))
    c2["sq_candidato"] = "9999"
    casados, pendentes = match_contatos(c2, e)
    assert casados.empty and list(pendentes.motivo) == ["sem_correspondencia"]


def test_download_resultados_uses_existing_file(tmp_path, monkeypatch):
    alvo = tmp_path / "consulta_cand_2026.zip"
    alvo.write_bytes(b"x")
    monkeypatch.setattr(el.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("rede")))
    assert el.download_resultados(tmp_path) == alvo
