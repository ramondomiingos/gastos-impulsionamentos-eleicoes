import importlib.util
from pathlib import Path

import pytest
import requests
import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verificar_links.py"
spec = importlib.util.spec_from_file_location("verificar_links", SCRIPT)
vl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vl)

CC = ('"NR_TURNO";"CD_ELEICAO";"SG_UF";"DS_CARGO";"SQ_CANDIDATO"\n'
      '"1";"6259";"RN";"SENADOR";"11"\n"1";"6259";"RN";"GOVERNADOR";"22"\n"1";"6259";"RN";"1º SUPLENTE";"33"\n')
HEADER = "# cabecalho explicativo\n# segunda linha\n"


class R:
    def __init__(self, status, payload=None):
        self.status_code, self._p = status, payload
        self.ok = status < 400
        self.text = str(payload)

    def json(self):
        if isinstance(self._p, Exception):
            raise self._p
        return self._p


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    cc = tmp_path / "cc.csv"
    cc.write_bytes(CC.encode("latin-1"))
    saida = tmp_path / "v.yaml"
    saida.write_text(HEADER + "verificados:\n- {cd_eleicao: '6259', uf: PB, cargo: SENADOR, id_eleicao: '9'}\n",
                     encoding="utf-8")
    monkeypatch.setattr(vl.time, "sleep", lambda s: None)
    return cc, saida


def _rodar(cc, saida, monkeypatch, resp):
    chamadas = []

    def get(url, **kw):
        chamadas.append(url)
        r = resp(url, len(chamadas))
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(vl.requests, "get", get)
    rc = vl.main(["--eleicao-id", "20322002026", "--ufs", "RN", "--consulta-cand", str(cc), "--saida", str(saida)])
    return rc, chamadas


def test_403_stops_but_writes_collected_and_keeps_header(ambiente, monkeypatch, capsys):
    cc, saida = ambiente
    rc, ch = _rodar(cc, saida, monkeypatch,
                    lambda u, n: R(200, {"id": 22, "idEleicao": "20322002026"}) if n == 1 else R(403))
    txt = saida.read_text(encoding="utf-8")
    assert rc == 1 and len(ch) == 2
    assert txt.startswith(HEADER)
    ents = yaml.safe_load(txt)["verificados"]
    assert {(e["uf"], e["cargo"]) for e in ents} == {("PB", "SENADOR"), ("RN", "GOVERNADOR")}


def test_list_response_ok_without_traceback(ambiente, monkeypatch):
    cc, saida = ambiente
    rc, _ = _rodar(cc, saida, monkeypatch, lambda u, n: R(200, [{"id": 11}, {"id": 22}]))
    assert rc == 0
    ents = [e for e in yaml.safe_load(saida.read_text(encoding="utf-8"))["verificados"] if e["uf"] == "RN"]
    assert len(ents) == 2 and all(e["fonte"] == "api-sem-conferencia-da-eleicao" for e in ents)


def test_election_id_mismatch_not_recorded(ambiente, monkeypatch):
    cc, saida = ambiente
    rc, _ = _rodar(cc, saida, monkeypatch, lambda u, n: R(200, {"id": 22 if "22" in u else 11,
                                                                 "idEleicao": "999"}))
    assert not [e for e in yaml.safe_load(saida.read_text(encoding="utf-8"))["verificados"] if e["uf"] == "RN"]


def test_request_exception_clean(ambiente, monkeypatch, capsys):
    cc, saida = ambiente
    rc, _ = _rodar(cc, saida, monkeypatch, lambda u, n: requests.Timeout("lento"))
    assert rc == 1
    assert "lento" in capsys.readouterr().err
