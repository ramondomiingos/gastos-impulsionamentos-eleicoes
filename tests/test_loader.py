import csv
import io

import pytest

from gastos.loader import clean_lines, load_despesas, parse_valor

COLS = ["uf", "sq_candidato", "candidato", "cargo", "partido", "fornecedor",
        "cnpj_fornecedor", "descricao", "origem", "valor", "data", "sq_despesa",
        "dt_geracao", "tp_prestacao", "dt_prestacao"]


def test_columns(zip_path):
    assert list(load_despesas(zip_path, "RN").columns) == COLS


def test_drops_placeholder_rows(zip_path):
    d = load_despesas(zip_path, "RN")
    assert (d.sq_despesa == "-1").sum() == 0


def test_identical_rows_are_all_kept_and_summed(zip_path):
    # linhas contratadas identicas sao itens reais distintos (o pago bate com a soma delas): nenhuma e removida
    d = load_despesas(zip_path, "RN")
    iguais = d[d.sq_despesa == "1002"]
    assert len(iguais) == 2
    assert iguais.valor.sum() == 2 * 1234.5
    itens = d[d.sq_despesa == "1004"]
    assert sorted(itens.valor) == [50.0, 100.0]


def test_load_does_not_change_row_count(zip_path):
    d = load_despesas(zip_path, "RN")
    # linhas do CSV sem as de preenchimento (SQ_DESPESA -1 / #NULO)
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        texto = z.read("despesas_contratadas_candidatos_2026_RN.csv").replace(b"\0", b"").decode("latin-1")
    linhas = [r for r in csv.reader(io.StringIO(texto), delimiter=";")][1:]
    assert len(d) == sum(1 for r in linhas if r and r[12].strip() not in ("-1", "#NULO"))


def _zip_tipos(tmp_path, tipos):
    import zipfile
    cab = ('"SG_UF";"SQ_CANDIDATO";"NM_CANDIDATO";"DS_CARGO";"SG_PARTIDO";"NM_FORNECEDOR_RFB";'
           '"NR_CPF_CNPJ_FORNECEDOR";"DS_DESPESA";"DS_ORIGEM_DESPESA";"VR_DESPESA_CONTRATADA";'
           '"DT_DESPESA";"SQ_DESPESA";"DT_GERACAO";"TP_PRESTACAO_CONTAS";"DT_PRESTACAO_CONTAS"')
    linhas = [cab] + [f'"RN";"1";"A";"Senador";"X";"F";"1";"d";"o";"{v}";"01/01/2026";"{sq}";"22/10/2026";"{tp}";"03/10/2026"'
                      for sq, tp, v in tipos]
    z = tmp_path / "t.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("despesas_contratadas_candidatos_2026_RN.csv", "\n".join(linhas).encode("latin-1"))
    return z


def test_warns_when_sq_despesa_appears_under_more_than_one_tipo(tmp_path):
    z = _zip_tipos(tmp_path, [("5", "Parcial", "100,00"), ("5", "Final", "100,00"), ("6", "Parcial", "10,00")])
    with pytest.warns(UserWarning, match=r"1 SQ_DESPESA.*mais de um tipo de prestação.*R\$ 200,00"):
        d = load_despesas(z, "RN")
    assert len(d) == 3  # o aviso nao altera os dados


def test_no_warning_for_normal_fixture(zip_path):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        load_despesas(zip_path, "RN")


def test_parses_decimal_comma(zip_path):
    d = load_despesas(zip_path, "RN")
    assert d.loc[d.sq_despesa == "1001", "valor"].iloc[0] == 2500.0
    assert d.loc[d.sq_despesa == "1002", "valor"].iloc[0] == 1234.5
    assert d.valor.dtype == float


def test_strips_nul_bytes(zip_path):
    d = load_despesas(zip_path, "RN")
    nul = d[d.sq_despesa == "1003"]
    assert len(nul) == 1
    assert nul.candidato.iloc[0] == "PEDRO LIMA"
    for col in d.select_dtypes(exclude="number").columns:
        assert not d[col].str.contains("\0", regex=False).any(), col
    out = list(clean_lines(["a\0b;c\n"]))
    assert out == ["ab;c\n"]
    rows = list(csv.reader(io.StringIO("".join(out)), delimiter=";"))
    assert rows == [["ab", "c"]]


def test_uf_none_reads_brasil(zip_path):
    assert set(load_despesas(zip_path, None).uf) == {"BR"}
    assert set(load_despesas(zip_path, "RN").uf) == {"RN"}


def test_parse_valor_formats():
    assert parse_valor("1.234,50") == 1234.5
    assert parse_valor("2500,00") == 2500.0
    assert parse_valor("-10,00") == -10.0


@pytest.mark.parametrize("bad", ["2500.00", "1,5", "12.34,50", "abc"])
def test_parse_valor_rejects_other_shapes(bad):
    with pytest.raises(ValueError, match=bad.replace(".", r"\.")):
        parse_valor(bad)


def test_dt_prestacao_loaded(zip_path):
    d = load_despesas(zip_path, "RN")
    assert set(d.dt_prestacao) <= {"03/10/2026", "05/10/2026", "04/10/2026", "15/10/2026", "09/10/2026"}
    assert "15/10/2026" in set(d.dt_prestacao)


def test_cd_eleicao_optional_column(tmp_path):
    import zipfile
    from gastos import loader
    linhas = ['"SG_UF";"SQ_CANDIDATO";"NM_CANDIDATO";"DS_CARGO";"SG_PARTIDO";"NM_FORNECEDOR_RFB";'
              '"NR_CPF_CNPJ_FORNECEDOR";"DS_DESPESA";"DS_ORIGEM_DESPESA";"VR_DESPESA_CONTRATADA";'
              '"DT_DESPESA";"SQ_DESPESA";"DT_GERACAO";"TP_PRESTACAO_CONTAS";"DT_PRESTACAO_CONTAS";"CD_ELEICAO"',
              '"RN";"1";"A";"Senador";"X";"F";"1";"d";"o";"10,00";"01/01/2026";"5";"22/10/2026";"Parcial";"03/10/2026";"6259"']
    z = tmp_path / "t.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("despesas_contratadas_candidatos_2026_RN.csv", "\n".join(linhas).encode("latin-1"))
    assert loader.load_despesas(z, "RN")["cd_eleicao"].tolist() == ["6259"]
