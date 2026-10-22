import pytest

from gastos import links

EXEMPLO = ("https://divulgacandcontas.tse.jus.br/divulga/#/candidato/NORDESTE/RN/20322002026/"
           "200002534001/2026/RN/prestacao/despesas")


def test_link_prestacao_matches_user_example():
    assert links.link_prestacao("RN", "200002534001", "20322002026") == EXEMPLO
    assert links.link_prestacao("rn", "200002534001", "20322002026") == EXEMPLO


@pytest.mark.parametrize("uf,regiao", [("AC", "NORTE"), ("BA", "NORDESTE"), ("SP", "SUDESTE"),
                                       ("RS", "SUL"), ("DF", "CENTRO-OESTE"), ("TO", "NORTE")])
def test_regioes(uf, regiao):
    assert f"/candidato/{regiao}/{uf}/" in links.link_prestacao(uf, "1", "2")


def test_all_ufs_have_region():
    assert len(links.REGIOES) == 27 and set(links.REGIOES.values()) == {
        "NORTE", "NORDESTE", "SUDESTE", "SUL", "CENTRO-OESTE"}


@pytest.mark.parametrize("uf,sq,eid", [("R", "1", "2"), ("RNN", "1", "2"), ("BR", "1", "2"), ("XX", "1", "2"),
                                       ("RN", "abc", "2"), ("RN", "", "2"), ("RN", "1", "2/3"),
                                       ("RN", "1", ""), ("RN", "1 ", "x")])
def test_invalid_inputs(uf, sq, eid):
    with pytest.raises(ValueError):
        links.link_prestacao(uf, sq, eid)


def test_verified_mapping_only(tmp_path):
    cfg = tmp_path / "v.yaml"
    cfg.write_text("""
verificados:
  - {cd_eleicao: "6259", uf: RN, cargo: GOVERNADOR, id_eleicao: "20322002026"}
""", encoding="utf-8")
    ver = links.carregar_verificados(cfg)
    assert links.link_ou_indisponivel("RN", "200002534001", "Governador", "6259", ver) == EXEMPLO
    for uf, cargo, cd in [("RN", "Senador", "6259"), ("PB", "Governador", "6259"),
                          ("RN", "Governador", "6260"), ("RN", "Governador", None), ("RN", "Governador", "")]:
        assert links.link_ou_indisponivel(uf, "200002534001", cargo, cd, ver) == links.INDISPONIVEL
    assert links.INDISPONIVEL == "link indisponível"


def test_verified_missing_file_is_empty(tmp_path):
    assert links.carregar_verificados(tmp_path / "nao-existe.yaml") == {}


def test_verified_bad_entry_ignored_or_error(tmp_path):
    cfg = tmp_path / "v.yaml"
    cfg.write_text("verificados:\n  - {cd_eleicao: '1', uf: RN, cargo: SENADOR, id_eleicao: 'x/y'}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        links.carregar_verificados(cfg)


def test_shipped_config_loads():
    ver = links.carregar_verificados()
    assert all(k[1] in links.REGIOES for k in ver)
