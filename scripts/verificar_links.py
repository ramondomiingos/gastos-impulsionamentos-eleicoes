#!/usr/bin/env python3
"""Verifica (somente leitura) o id de eleicao do DivulgaCandContas para cada (CD_ELEICAO, UF, cargo).

Uso:
    .venv/bin/python scripts/verificar_links.py --eleicao-id 20322002026 --ufs RN,PB \
        --consulta-cand data/raw/consulta_cand_2026.zip [--saida config/links_verificados.yaml]

Para cada (UF, cargo) escolhe UM candidato de consulta_cand e faz um GET na API publica do portal
(`/divulga/rest/v1/candidatura/buscar/<ano>/<UF>/<id_eleicao>/candidato/<SQ>`). Se responder HTTP 200 com o
mesmo SQ_CANDIDATO, a combinacao (CD_ELEICAO, UF, cargo) -> id_eleicao e gravada como verificada.
Nunca escreve no portal, so GET, com timeout e pausa entre requisicoes. Se o portal responder 403
(bloqueio por origem/robo), o script PARA e nada e gravado: nao contorna o bloqueio.
Sem --saida apenas imprime o resultado. Os ids de eleicao candidatos vem de `eleicao/ordinarias`
(--listar) ou do que o portal mostra na URL de um candidato.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests
import yaml

API = "https://divulgacandcontas.tse.jus.br/divulga/rest/v1"
HEADERS = {"User-Agent": "analise-gasto-partidario/0.1 (pesquisa; leitura de dados publicos)",
           "Accept": "application/json"}


def _get(url: str) -> requests.Response:
    r = requests.get(url, headers=HEADERS, timeout=30)
    time.sleep(1.0)
    return r


def _consulta(path: Path) -> pd.DataFrame:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            raw = z.read("consulta_cand_2026_BRASIL.csv")
    else:
        raw = path.read_bytes()
    txt = raw.replace(b"\0", b"").decode("latin-1")
    return pd.read_csv(io.StringIO(txt), sep=";", dtype=str, keep_default_na=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true", help="so lista eleicao/ordinarias")
    ap.add_argument("--eleicao-id", help="id do portal a testar (ex. 20322002026)")
    ap.add_argument("--ufs", default="RN", help="UFs separadas por virgula")
    ap.add_argument("--consulta-cand", default="data/raw/consulta_cand_2026.zip")
    ap.add_argument("--ano", type=int, default=2026)
    ap.add_argument("--saida", help="YAML a atualizar (ex. config/links_verificados.yaml)")
    a = ap.parse_args(argv)
    if a.listar:
        r = _get(f"{API}/eleicao/ordinarias")
        print(r.status_code, r.text[:4000])
        return 0 if r.ok else 1
    if not a.eleicao_id or not a.eleicao_id.isdigit():
        ap.error("--eleicao-id (so digitos) e obrigatorio")
    d = _consulta(Path(a.consulta_cand))
    d = d[d["NR_TURNO"] == "1"]
    achados = []
    for uf in [u.strip().upper() for u in a.ufs.split(",") if u.strip()]:
        sub = d[(d["SG_UF"] == uf) & ~d["DS_CARGO"].str.contains("SUPLENTE")]
        for (cd, cargo), g in sub.groupby(["CD_ELEICAO", "DS_CARGO"]):
            sq = g.sort_values("SQ_CANDIDATO").iloc[0]["SQ_CANDIDATO"]
            r = _get(f"{API}/candidatura/buscar/{a.ano}/{uf}/{a.eleicao_id}/candidato/{sq}")
            ok = False
            if r.status_code == 200:
                try:
                    ok = str(r.json().get("id")) == sq
                except ValueError:
                    ok = False
            print(f"{uf} {cargo} CD_ELEICAO={cd} sq={sq} -> HTTP {r.status_code} {'OK' if ok else 'nao verificado'}")
            if r.status_code == 403:
                print("Bloqueado pelo portal (403): parando sem gravar.", file=sys.stderr)
                return 1
            if ok:
                achados.append({"cd_eleicao": cd, "uf": uf, "cargo": cargo, "id_eleicao": a.eleicao_id,
                                "fonte": f"api-200 em {time.strftime('%Y-%m-%d')}"})
    if a.saida and achados:
        p = Path(a.saida)
        atual = yaml.safe_load(p.read_text(encoding="utf-8")) if p.is_file() else {}
        lista = (atual or {}).get("verificados") or []
        chave = lambda e: (str(e["cd_eleicao"]), e["uf"], e["cargo"].upper())  # noqa: E731
        novos = {chave(e): e for e in lista} | {chave(e): e for e in achados}
        p.write_text("# Gerado por scripts/verificar_links.py (veja o README).\n" + yaml.safe_dump(
            {"verificados": list(novos.values())}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"{len(achados)} combinacao(oes) gravada(s) em {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
