"""`gastos validar`: checagem da classificacao por recorte (UF e Presidente/BR).

Para cada recorte calcula, sobre o principal (confirmado + generico):
- nucleo: parcela cuja origem da despesa no TSE e "Despesa com Impulsionamento de Conteudos";
- periferia: parcela fora dessa origem (para um humano julgar: taxa de agencia, jingle etc.);
- possiveis perdas: linhas `nenhum` cuja descricao tem termos de anuncio (quase todas sao servicos de
  agencia, deliberadamente nao contados).
Nao grava partido, CPF nem nome de candidato.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

from gastos.report import CSV, _brl, _data_corte, _dt_ultima_prestacao, _pct, _tabela_md
from gastos.text import normalize

ORIGEM_NUCLEO = "impulsionamento de conteudos"
TOP = 10
TOP_ARQUIVO_TODAS = 50
COLUNAS_LINHA = ["fornecedor", "descricao", "origem", "valor", "nivel"]
_B = r"(?<![a-z0-9])"
_F = r"(?![a-z0-9])"
PADRAO_PERDAS = re.compile(
    _B + r"(?:impulsionamentos?|impulsionar(?:em)?|impulsiona(?:m)?|impulsionad[oa]s?|impulsionou|impulsione|meta ads|facebook|instagram|google ads|tiktok|trafego pago|anuncios?)" + _F
)


def casa_perda(descricao) -> bool:
    return bool(PADRAO_PERDAS.search(normalize(descricao)))


def _top(df: pd.DataFrame) -> pd.DataFrame:
    """Maiores valores primeiro; empate decidido por texto, independente da ordem de entrada."""
    cols = COLUNAS_LINHA
    base = df[cols].copy()
    chave = base.assign(_v=-pd.to_numeric(base["valor"], errors="coerce").fillna(0.0),
                        _f=base["fornecedor"].astype(str), _d=base["descricao"].astype(str),
                        _o=base["origem"].astype(str), _n=base["nivel"].astype(str))
    ordem = chave.sort_values(["_v", "_f", "_d", "_o", "_n"], kind="mergesort").index
    return base.loc[ordem].reset_index(drop=True)


def datas_ordenadas(datas) -> list[str]:
    """Datas dd/mm/aaaa validas e distintas, em ordem cronologica (invalidas e vazias sao ignoradas)."""
    vistas = {}
    for d in datas:
        t = pd.to_datetime(d, format="%d/%m/%Y", errors="coerce") if isinstance(d, str) else pd.NaT
        if not pd.isna(t):
            vistas[t] = t.strftime("%d/%m/%Y")
    return [vistas[t] for t in sorted(vistas)]


def _seguro(v):
    """Neutraliza injecao de formula em planilha: texto livre que comeca com = + - @ (ou tab/CR) ganha aspa."""
    t = str(v)
    if t[:1] in ("\t", "\r") or t.strip()[:1] in ("=", "+", "-", "@"):
        return "'" + t
    return t


def analisar_recorte(df: pd.DataFrame, uf: str) -> dict:
    """Metricas de um recorte ja classificado (colunas fornecedor, descricao, origem, valor, nivel)."""
    principal_df = df[df["nivel"].isin(["confirmado", "generico"])]
    eh_nucleo = principal_df["origem"].map(normalize).str.contains(ORIGEM_NUCLEO, regex=False).astype(bool)
    principal = float(principal_df["valor"].sum())
    nucleo = float(principal_df.loc[eh_nucleo, "valor"].sum())
    periferia_df = principal_df[~eh_nucleo]
    nenhum = df[df["nivel"] == "nenhum"]
    perdas_df = nenhum[nenhum["descricao"].map(casa_perda).astype(bool)]
    return {
        "uf": uf,
        "principal": principal,
        "nucleo": nucleo,
        "pct_nucleo": nucleo / principal if principal else 0.0,
        "periferia": float(periferia_df["valor"].sum()),
        "possiveis_perdas": float(perdas_df["valor"].sum()),
        "linhas_periferia": _top(periferia_df),
        "linhas_perdas": _top(perdas_df),
        "datas": {"geracao": _data_corte(df), "prestacao": _dt_ultima_prestacao(df)},
    }


def validar_recortes(df: pd.DataFrame, ufs: list[str] | None = None) -> list[dict]:
    """Um resultado por valor de `uf` em df (BR = presidente), na ordem pedida ou alfabetica."""
    ufs = ufs or sorted(df["uf"].unique())
    return [analisar_recorte(df[df["uf"] == u], u) for u in ufs]


def nome_pasta(uf: str | None) -> str:
    sufixo = f"_uf-{uf}" if uf else ""
    return f"{date.today().isoformat()}_validacao{sufixo}"


def _fmt_linhas(linhas: pd.DataFrame) -> pd.DataFrame:
    out = linhas.head(TOP).copy()
    for c in ("fornecedor", "descricao", "origem"):
        out[c] = out[c].map(lambda v: re.sub(r"\s+", " ", str(v)).strip()[:80])
    return out


def _md(res: list[dict]) -> str:
    ordem = sorted(res, key=lambda r: (-r["periferia"], r["uf"]))
    resumo = pd.DataFrame({
        "uf": [r["uf"] for r in ordem],
        "principal": [r["principal"] for r in ordem],
        "núcleo %": [r["pct_nucleo"] for r in ordem],
        "periferia": [r["periferia"] for r in ordem],
        "possíveis perdas": [r["possiveis_perdas"] for r in ordem],
    })
    fmt = {"principal": _brl, "núcleo %": _pct, "periferia": _brl, "possíveis perdas": _brl}
    geracao = datas_ordenadas(r["datas"]["geracao"] for r in res)
    prestacao = datas_ordenadas(r["datas"]["prestacao"] for r in res)
    tot = sum(r["principal"] for r in res)
    nuc = sum(r["nucleo"] for r in res)
    per = sum(r["periferia"] for r in res)
    perd = sum(r["possiveis_perdas"] for r in res)
    p = [
        "# Validação da classificação por recorte",
        "",
        f"Dados do TSE gerados em {', '.join(geracao) or 'data desconhecida'}; "
        f"última prestação de contas: {', '.join(prestacao[-1:]) or 'desconhecida'}. "
        f"Total: principal {_brl(tot)}, núcleo {_pct(nuc / tot if tot else 0)}, periferia {_brl(per)}, "
        f"possíveis perdas {_brl(perd)}.",
        "",
        "## Legenda",
        "",
        "- **principal**: confirmado + genérico (o número principal do projeto).",
        "- **núcleo**: parte do principal cuja origem da despesa no TSE é "
        "\"Despesa com Impulsionamento de Conteúdos\" (campo do próprio TSE, independe das regras de palavras).",
        "- **periferia**: parte do principal fora dessa origem. É o que um humano deve olhar: taxas de agência "
        "(\"gestão de tráfego pago\"), jingles com \"impulsionamento\" na descrição etc.",
        "- **possíveis perdas**: linhas classificadas `nenhum` cuja descrição cita termos de anúncio "
        "(impuls*, meta ads, facebook, instagram, google ads, tiktok, tráfego pago, anúncio). "
        "A maior parte são serviços de agência deliberadamente não contados, não erro.",
        "",
        "## Resumo (ordenado pela periferia)",
        "",
        _tabela_md(resumo, fmt),
    ]
    for r in ordem:
        p += ["", f"## {r['uf']}", "",
              f"Principal {_brl(r['principal'])}; núcleo {_pct(r['pct_nucleo'])}; periferia {_brl(r['periferia'])}; "
              f"possíveis perdas {_brl(r['possiveis_perdas'])}.", ""]
        for titulo, chave in (("Maiores linhas da periferia", "linhas_periferia"),
                              ("Maiores possíveis perdas (maioria é serviço de agência não contado)", "linhas_perdas")):
            p += [f"### {titulo}", ""]
            linhas = r[chave]
            p += [_tabela_md(_fmt_linhas(linhas), {"valor": _brl}) if len(linhas) else "Nenhuma linha."]
            p += [""]
    return "\n".join(p).rstrip() + "\n"


def escrever(res: list[dict], pasta: Path, completo: bool) -> Path:
    """Grava validacao.md/.csv e os CSV por UF (todas as linhas se `completo`, senao as 50 maiores)."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "validacao.md").write_text(_md(res), encoding="utf-8")
    cols = ["uf", "principal", "nucleo", "pct_nucleo", "periferia", "possiveis_perdas"]
    pd.DataFrame([{c: r[c] for c in cols} for r in res]).to_csv(pasta / "validacao.csv", **CSV)
    for r in res:
        if not re.fullmatch(r"[A-Z]{2}", str(r["uf"])):
            continue  # nunca monta nome de arquivo com UF fora do padrao
        for prefixo, chave in (("periferia", "linhas_periferia"), ("possiveis_perdas", "linhas_perdas")):
            linhas = r[chave] if completo else r[chave].head(TOP_ARQUIVO_TODAS)
            linhas = linhas.copy()
            for c in ("fornecedor", "descricao", "origem"):
                linhas[c] = linhas[c].map(_seguro)
            linhas.to_csv(pasta / f"{prefixo}_{r['uf']}.csv", **CSV)
    return pasta
