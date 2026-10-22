import os
import time
import zipfile
from pathlib import Path

import pandas as pd
import pytest

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


def test_sq_candidato_must_agree_with_uf_and_cargo():
    e = load_eleitos(FIX / "eleitos.csv")
    c = pd.read_csv(FIX / "contatos.csv", dtype=str, keep_default_na=False)
    casados, pendentes = match_contatos(c, e)
    # "Ze da Silva" declara Senador, mas o sq 1002 e Deputada Federal: nao casa
    ze = pendentes[pendentes.email == "ze@example.org"]
    assert list(ze.motivo) == ["sq_diverge"]
    assert "ze@example.org" not in set(casados.email)
    assert set(pendentes.email) == {"fulano@example.org", "joao@example.org",
                                    "bairro@example.org", "ze@example.org"}


def test_sq_candidato_agreeing_wins_over_name():
    e = load_eleitos(FIX / "eleitos.csv")
    c = _contatos(("Nome Qualquer", "Deputado Federal", "rn", "a@x.org"))
    c["sq_candidato"] = "1002"
    casados, pendentes = match_contatos(c, e)
    assert pendentes.empty and list(casados.sq_candidato) == ["1002"]
    c["uf"] = "SP"
    casados, pendentes = match_contatos(c, e)
    assert casados.empty and list(pendentes.motivo) == ["sq_diverge"]


def test_sq_not_elected_is_sem_correspondencia():
    e = load_eleitos(FIX / "eleitos.csv")
    c = _contatos(("José da Silva", "Deputado Federal", "RN", "a@x.org"))
    c["sq_candidato"] = "9999"
    casados, pendentes = match_contatos(c, e)
    assert casados.empty and list(pendentes.motivo) == ["sem_correspondencia"]


def test_duplicate_contacts_same_eleito():
    e = load_eleitos(FIX / "eleitos.csv")
    c = _contatos(("José da Silva", "Deputado Federal", "RN", "a@x.org"),
                  ("Ze da Silva", "Deputado Federal", "RN", "b@x.org"))
    casados, pendentes = match_contatos(c, e)
    assert list(casados.email) == ["a@x.org"]
    assert list(pendentes.motivo) == ["duplicado"]
    assert list(pendentes.email) == ["b@x.org"]


def test_vice_never_matches_governador(tmp_path):
    f = tmp_path / "e.csv"
    f.write_bytes((FIX / "eleitos.csv").read_bytes() +
                  '"22/10/2026";"RN";"VICE-GOVERNADOR";"2001";"LUIZ GOMES";"LUIZ";"PSB";"ELEITO"\n'.encode("latin-1"))
    e = load_eleitos(f)
    assert "2001" in set(e.sq_candidato)
    c = _contatos(("Luiz Gomes", "Governador", "RN", "l@x.org"))
    casados, pendentes = match_contatos(c, e)
    assert casados.empty and list(pendentes.motivo) == ["sem_correspondencia"]


def test_missing_columns_raise(tmp_path):
    e = load_eleitos(FIX / "eleitos.csv")
    with pytest.raises(ValueError, match="uf"):
        match_contatos(pd.DataFrame({"nome": ["a"], "cargo": ["Senador"]}), e)
    f = tmp_path / "x.csv"
    f.write_bytes(b'"SG_UF";"DS_CARGO"\n"RN";"SENADOR"\n')
    with pytest.raises(ValueError, match="SQ_CANDIDATO"):
        load_eleitos(f)


def _fake_download(monkeypatch, calls):
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass
        def iter_content(self, n):
            return [_zip_bytes()]
    def get(*a, **k):
        calls.append(1)
        return R()
    monkeypatch.setattr(el.requests, "get", get)


def _zip_bytes():
    import io
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("x.csv", "novo")
    return b.getvalue()


def _cache(tmp_path, content=None, idade_h=0):
    alvo = tmp_path / "consulta_cand_2026.zip"
    alvo.write_bytes(_zip_bytes() if content is None else content)
    t = time.time() - idade_h * 3600
    os.utime(alvo, (t, t))
    return alvo


def test_download_fresh_cache_reused(tmp_path, monkeypatch, caplog):
    calls = []
    _fake_download(monkeypatch, calls)
    alvo = _cache(tmp_path, idade_h=1)
    with caplog.at_level("INFO"):
        assert el.download_resultados(tmp_path) == alvo
    assert calls == []
    assert "consulta_cand_2026.zip" in caplog.text


def test_download_old_cache_redownloaded(tmp_path, monkeypatch):
    calls = []
    _fake_download(monkeypatch, calls)
    alvo = _cache(tmp_path, idade_h=el.MAX_IDADE_HORAS + 1)
    assert el.download_resultados(tmp_path) == alvo
    assert calls == [1] and not alvo.with_suffix(".part").exists()


def test_download_invalid_cache_redownloaded(tmp_path, monkeypatch):
    for conteudo in (b"", b"nao e zip"):
        calls = []
        _fake_download(monkeypatch, calls)
        _cache(tmp_path, content=conteudo)
        el.download_resultados(tmp_path)
        assert calls == [1]


def test_download_force(tmp_path, monkeypatch):
    calls = []
    _fake_download(monkeypatch, calls)
    _cache(tmp_path)
    el.download_resultados(tmp_path, force=True)
    assert calls == [1]
