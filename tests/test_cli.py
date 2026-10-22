import pandas as pd
import pytest

from gastos import cli, loader


@pytest.fixture
def run(zip_path, tmp_path, monkeypatch):
    calls = {"download": 0, "load_uf": []}
    monkeypatch.setattr(cli, "download_candidatos", lambda *a, **k: (calls.__setitem__("download", calls["download"] + 1), zip_path)[1])
    real = loader.load_despesas

    def spy(p, uf=None):
        calls["load_uf"].append(uf)
        return real(p, uf)

    monkeypatch.setattr(cli, "load_despesas", spy)
    saida = tmp_path / "saida"

    def _run(*args):
        return cli.main(["analisar", *args, "--saida", str(saida)])

    _run.saida = saida
    _run.calls = calls
    return _run


def _pastas(saida):
    return list(saida.iterdir()) if saida.exists() else []


def _evid_total(pasta):
    total = 0
    for n in ("confirmado", "generico", "provavel"):
        total += len(pd.read_csv(pasta / f"evidencia_{n}.csv", sep=";", decimal=",", encoding="utf-8-sig"))
    return total


def test_analisar_uf_creates_run_folder(run):
    assert run("--uf", "RN") == 0
    pastas = _pastas(run.saida)
    assert len(pastas) == 1 and pastas[0].name.endswith("_uf-RN")
    assert (pastas[0] / "relatorio.md").exists()


def test_uf_is_case_insensitive(run):
    assert run("--uf", "rn") == 0
    assert _pastas(run.saida)[0].name.endswith("_uf-RN")


@pytest.mark.parametrize("uf", ["R", "RNN", "1A", ""])
def test_invalid_uf_exits_2_before_loading(run, uf, capsys):
    assert run("--uf", uf) == 2
    assert "uf" in capsys.readouterr().err.lower()
    assert run.calls["download"] == 0 and run.calls["load_uf"] == []
    assert _pastas(run.saida) == []


def test_filters_by_cargo_partido_candidato(run):
    def candidatos(*args):
        assert run("--uf", "RN", *args) == 0
        pasta = _pastas(run.saida)[-1] if len(_pastas(run.saida)) == 1 else max(_pastas(run.saida), key=lambda p: p.stat().st_mtime)
        df = pd.read_csv(pasta / "candidatos.csv", sep=";", decimal=",", encoding="utf-8-sig", dtype=str)
        for p in run.saida.iterdir():
            import shutil
            shutil.rmtree(p)
        return sorted(df["sq_candidato"])

    assert candidatos() == ["200001", "200002", "200003"]
    assert candidatos("--cargo", "deputado ESTADUAL") == ["200001"]
    assert candidatos("--partido", "abc") == ["200001", "200003"]
    assert candidatos("--candidato", "Maria Souza") == ["200002"]
    assert candidatos("--candidato", "pedro lima") == ["200003"]
    assert candidatos("--candidato", "200001") == ["200001"]
    assert candidatos("--partido", "ABC", "--cargo", "Prefeito") == ["200003"]


def test_accent_insensitive_candidate(run):
    assert run("--uf", "RN", "--candidato", "joao da silva") == 0


def test_unknown_candidate_returns_error(run, capsys):
    assert run("--uf", "RN", "--candidato", "Fulano Inexistente") != 0
    assert "Fulano Inexistente" in capsys.readouterr().err
    assert _pastas(run.saida) == []


def test_unknown_sq_candidate_returns_error(run):
    assert run("--uf", "RN", "--candidato", "999") != 0
    assert _pastas(run.saida) == []


def test_ambiguous_candidate_lists_options(run, zip_path, monkeypatch, capsys):
    real = cli.load_despesas

    def dup(p, uf=None):
        df = real(p, uf)
        extra = df[df["sq_candidato"] == "200002"].copy()
        extra["sq_candidato"] = "200009"
        extra["partido"] = "QWE"
        return pd.concat([df, extra], ignore_index=True)

    monkeypatch.setattr(cli, "load_despesas", dup)
    assert run("--uf", "RN", "--candidato", "maria souza") != 0
    err = capsys.readouterr().err
    assert "200002" in err and "200009" in err and "QWE" in err and "Vereador" in err
    assert _pastas(run.saida) == []
    assert run("--uf", "RN", "--candidato", "200009") == 0


def test_empty_slice_lists_available(run, capsys):
    assert run("--uf", "RN", "--cargo", "Senador") != 0
    err = capsys.readouterr().err
    assert "Prefeito" in err and "Vereador" in err and "ABC" in err and "XYZ" in err
    assert _pastas(run.saida) == []


def test_tetos_parsed(run):
    assert run("--uf", "RN", "--tetos", "0.05,0.10") == 0
    pasta = _pastas(run.saida)[0]
    tetos = pd.read_csv(pasta / "tetos.csv", sep=";", decimal=",", encoding="utf-8-sig")
    assert list(tetos["teto"]) == [0.05, 0.10]


def test_invalid_tetos_exit_2(run, capsys):
    assert run("--uf", "RN", "--tetos", "0.05,abc") == 2
    assert "tetos" in capsys.readouterr().err.lower()
    assert _pastas(run.saida) == []


def test_no_args_runs_national(run):
    assert run() == 0
    assert run.calls["load_uf"] == [None]
    assert _pastas(run.saida)[0].name.endswith("_brasil")


def test_uf_br_is_national(run):
    assert run("--uf", "BR") == 0
    assert run.calls["load_uf"] == [None]


def test_zip_option_skips_download(run, zip_path):
    assert run("--uf", "RN", "--zip", str(zip_path)) == 0
    assert run.calls["download"] == 0


def test_missing_command_returns_nonzero():
    assert cli.main([]) != 0
