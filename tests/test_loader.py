import csv
import io

from gastos.loader import clean_lines, load_despesas

COLS = ["uf", "sq_candidato", "candidato", "cargo", "partido", "fornecedor",
        "cnpj_fornecedor", "descricao", "origem", "valor", "data", "sq_despesa",
        "dt_geracao", "tp_prestacao"]


def test_columns(zip_path):
    assert list(load_despesas(zip_path, "RN").columns) == COLS


def test_drops_placeholder_rows(zip_path):
    d = load_despesas(zip_path, "RN")
    assert (d.sq_despesa == "-1").sum() == 0


def test_dedupes_only_identical_rows(zip_path):
    d = load_despesas(zip_path, "RN")
    # linhas identicas (apos normalizar) colapsam
    assert (d.sq_despesa == "1002").sum() == 1
    # mesmo sq_despesa com descricao/valor diferentes: ambas ficam
    itens = d[d.sq_despesa == "1004"]
    assert sorted(itens.valor) == [50.0, 100.0]
    assert len(d) == 5


def test_parses_decimal_comma(zip_path):
    d = load_despesas(zip_path, "RN")
    assert d.loc[d.sq_despesa == "1001", "valor"].iloc[0] == 2500.0
    assert d.loc[d.sq_despesa == "1002", "valor"].iloc[0] == 1234.5
    assert d.valor.dtype == float


def test_strips_nul_bytes(zip_path):
    d = load_despesas(zip_path, "RN")
    assert "PEDRO LIMA" in set(d.candidato)
    out = list(clean_lines(["a\0b;c\n"]))
    assert out == ["ab;c\n"]
    rows = list(csv.reader(io.StringIO("".join(out)), delimiter=";"))
    assert rows == [["ab", "c"]]


def test_uf_none_reads_brasil(zip_path):
    assert set(load_despesas(zip_path, None).uf) == {"BR"}
    assert set(load_despesas(zip_path, "RN").uf) == {"RN"}
