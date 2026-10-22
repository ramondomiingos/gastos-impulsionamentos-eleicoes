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
Se a resposta trouxer o id da eleicao, ele e comparado com o id testado (divergente = nao grava; ausente =
grava com fonte `api-sem-conferencia-da-eleicao`). Em 403, erro de rede ou timeout o script PARA, mas grava
o que ja foi coletado. Sem --saida apenas imprime o resultado. Os ids de eleicao candidatos vem de `eleicao/ordinarias`
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


def _ids_candidato(j) -> list[dict]:
    """Normaliza a resposta (objeto ou lista de objetos) em lista de dicts."""
    if isinstance(j, dict):
        return [j]
    return [x for x in j if isinstance(x, dict)] if isinstance(j, list) else []


def _id_eleicao_resposta(item: dict) -> str | None:
    """Id de eleicao presente na resposta (campo idEleicao ou eleicao.{id,idEleicao}), se houver."""
    for k in ("idEleicao", "id_eleicao"):
        if item.get(k) not in (None, ""):
            return str(item[k])
    e = item.get("eleicao")
    if isinstance(e, dict):
        for k in ("id", "idEleicao"):
            if e.get(k) not in (None, ""):
                return str(e[k])
    return None


def _confere(r, sq: str, eleicao_id: str) -> tuple[bool, str]:
    """(registrar?, fonte). Exige HTTP 200 com o mesmo SQ; confere o id da eleicao quando a resposta o traz."""
    if r.status_code != 200:
        return False, ""
    try:
        itens = _ids_candidato(r.json())
    except ValueError:
        return False, ""
    achado = [x for x in itens if str(x.get("id")) == sq]
    if not achado:
        return False, ""
    eid = _id_eleicao_resposta(achado[0])
    if eid is None:
        return True, "api-sem-conferencia-da-eleicao"
    return (eid == eleicao_id), f"api-200 em {time.strftime('%Y-%m-%d')}"


def _gravar(p: Path, achados: list[dict]) -> None:
    """Atualiza as entradas preservando o bloco de comentarios do cabecalho do arquivo."""
    cabecalho, atual = "", {}
    if p.is_file():
        texto = p.read_text(encoding="utf-8")
        linhas = texto.splitlines(keepends=True)
        n = 0
        while n < len(linhas) and (linhas[n].startswith("#") or not linhas[n].strip()):
            n += 1
        cabecalho, atual = "".join(linhas[:n]), yaml.safe_load(texto) or {}
    if not cabecalho:
        cabecalho = "# Gerado por scripts/verificar_links.py (veja o README).\n"
    chave = lambda e: (str(e["cd_eleicao"]), e["uf"], e["cargo"].upper())  # noqa: E731
    novos = {chave(e): e for e in (atual.get("verificados") or [])} | {chave(e): e for e in achados}
    p.write_text(cabecalho + yaml.safe_dump({"verificados": list(novos.values())}, allow_unicode=True,
                                            sort_keys=False), encoding="utf-8")
    print(f"{len(achados)} combinacao(oes) gravada(s) em {p}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true", help="so lista eleicao/ordinarias")
    ap.add_argument("--eleicao-id", help="id do portal a testar (ex. 20322002026)")
    ap.add_argument("--ufs", default="RN", help="UFs separadas por virgula")
    ap.add_argument("--consulta-cand", default="data/raw/consulta_cand_2026.zip")
    ap.add_argument("--ano", type=int, default=2026)
    ap.add_argument("--saida", help="YAML a atualizar (ex. config/links_verificados.yaml)")
    a = ap.parse_args(argv)
    try:
        if a.listar:
            r = _get(f"{API}/eleicao/ordinarias")
            print(r.status_code, r.text[:4000])
            return 0 if r.ok else 1
    except requests.RequestException as e:
        print(f"Erro de rede: {e}", file=sys.stderr)
        return 1
    if not a.eleicao_id or not a.eleicao_id.isdigit():
        ap.error("--eleicao-id (so digitos) e obrigatorio")
    d = _consulta(Path(a.consulta_cand))
    d = d[d["NR_TURNO"] == "1"]
    achados, rc = [], 0
    for uf in [u.strip().upper() for u in a.ufs.split(",") if u.strip()]:
        if rc:
            break
        sub = d[(d["SG_UF"] == uf) & ~d["DS_CARGO"].str.contains("SUPLENTE")]
        for (cd, cargo), g in sub.groupby(["CD_ELEICAO", "DS_CARGO"]):
            sq = g.sort_values("SQ_CANDIDATO").iloc[0]["SQ_CANDIDATO"]
            try:
                r = _get(f"{API}/candidatura/buscar/{a.ano}/{uf}/{a.eleicao_id}/candidato/{sq}")
            except requests.RequestException as e:
                print(f"Erro de rede em {uf} {cargo}: {e}; parando.", file=sys.stderr)
                rc = 1
                break
            ok, fonte = _confere(r, sq, a.eleicao_id)
            print(f"{uf} {cargo} CD_ELEICAO={cd} sq={sq} -> HTTP {r.status_code} {'OK' if ok else 'nao verificado'}")
            if r.status_code == 403:
                print("Bloqueado pelo portal (403): parando (o que ja foi coletado sera gravado).", file=sys.stderr)
                rc = 1
                break
            if ok:
                achados.append({"cd_eleicao": cd, "uf": uf, "cargo": cargo, "id_eleicao": a.eleicao_id,
                                "fonte": fonte})
    if a.saida and achados:
        _gravar(Path(a.saida), achados)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
