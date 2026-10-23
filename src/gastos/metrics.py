"""Metricas de gasto com plataformas estrangeiras a partir das despesas classificadas.

Definicoes:
- total: soma de TODAS as linhas validas contratadas (todos os niveis).
- principal: confirmado + generico (provavel nunca entra).
- proporcao: principal / total; 0.0 quando total == 0 (nunca NaN/inf).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NIVEIS = ("confirmado", "generico", "provavel")
VALID_BY = ("uf", "cargo", "partido", "candidato")
ID_COLS = ("uf", "cargo", "partido", "candidato")


def _proporcao(principal: pd.Series, total: pd.Series) -> pd.Series:
    denom = total.where(total != 0, np.nan)
    return (principal / denom).fillna(0.0).astype(float)


def _aggregate(df: pd.DataFrame, keys: list[str], keep: list[str]) -> pd.DataFrame:
    work = df.assign(
        _total=df["valor"],
        **{f"_{n}": df["valor"].where(df["nivel"] == n, 0.0) for n in NIVEIS},
        _cand=df["sq_candidato"],
    )
    if keys:
        g = work.groupby(keys, sort=True, dropna=False)
    else:
        work = work.assign(_all=0)
        g = work.groupby("_all")
    agg = {"_total": "sum", **{f"_{n}": "sum" for n in NIVEIS}, "_cand": "nunique"}
    for k in keep:
        agg[k] = "first"
    out = g.agg(agg)
    out = out.reset_index(drop=not keys)
    out = out.rename(columns={"_total": "total", "_cand": "n_candidatos", **{f"_{n}": n for n in NIVEIS}})
    out["principal"] = out["confirmado"] + out["generico"]
    out["proporcao"] = _proporcao(out["principal"], out["total"])
    return out


def summarize(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Agrega por qualquer subconjunto de uf/cargo/partido/candidato ([] = total geral).

    "candidato" agrupa por sq_candidato e mantem o nome na coluna "candidato".
    """
    bad = [c for c in by if c not in VALID_BY]
    if bad:
        raise ValueError(f"chaves de agrupamento invalidas: {bad}")
    keys = ["sq_candidato" if c == "candidato" else c for c in by]
    keep = ["candidato"] if "candidato" in by else []
    out = _aggregate(df, keys, keep)
    cols = (["sq_candidato"] if "candidato" in by else []) + [c for c in by] + [
        "total", *NIVEIS, "principal", "proporcao", "n_candidatos",
    ]
    return out[list(dict.fromkeys(cols))].reset_index(drop=True)


def candidate_shares(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por sq_candidato, com uf/cargo/partido/candidato e as metricas."""
    keep = [c for c in ID_COLS if c in df.columns]
    extra = [c for c in ("cd_eleicao",) if c in df.columns]  # opcional: id da eleicao do TSE
    out = _aggregate(df, ["sq_candidato"], keep + extra)
    cols = ["sq_candidato", *keep, *extra, "total", *NIVEIS, "principal", "proporcao"]
    return out[cols].reset_index(drop=True)


def top_candidatos(shares: pd.DataFrame, n: int = 5, piso_total: float = 50000.0) -> pd.DataFrame:
    """Ate `n` candidatos com maior proporcao, entre os de total >= piso_total e principal > 0.

    Desempate deterministico: maior principal, depois menor sq_candidato.
    O piso evita que campanhas minusculas com proporcao absurda dominem a lista.
    """
    ok = shares[(shares["total"] >= piso_total) & (shares["principal"] > 0)]
    ok = ok.assign(_sq=ok["sq_candidato"].astype(str).str.zfill(20))
    ok = ok.sort_values(["proporcao", "principal", "_sq"], ascending=[False, False, True], kind="mergesort")
    return ok.drop(columns="_sq").head(n).reset_index(drop=True)


def maiores_valores(shares: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Ate `n` candidatos com maior valor absoluto em plataformas (principal > 0).

    Ordem: principal desc, total desc, sq_candidato asc (deterministico).
    """
    ok = shares[shares["principal"] > 0]
    ok = ok.assign(_sq=ok["sq_candidato"].astype(str).str.zfill(20))
    ok = ok.sort_values(["principal", "total", "_sq"], ascending=[False, False, True], kind="mergesort")
    return ok.drop(columns="_sq").head(n).reset_index(drop=True)


def cap_impact(shares: pd.DataFrame, caps: list[float]) -> pd.DataFrame:
    """Impacto de cada teto: n_acima, pct_acima (fracao dos candidatos com total > 0), excedente."""
    ativos = shares[shares["total"] > 0]
    rows = []
    for teto in caps:
        acima = ativos[ativos["proporcao"] > teto]
        rows.append(
            {
                "teto": teto,
                "n_acima": int(len(acima)),
                "pct_acima": float(len(acima) / len(ativos)) if len(ativos) else 0.0,
                "excedente": float((acima["principal"] - teto * acima["total"]).sum()),
            }
        )
    return pd.DataFrame(rows, columns=["teto", "n_acima", "pct_acima", "excedente"])


def distribution(shares: pd.DataFrame) -> dict:
    """Mediana, p75, p90 e max da proporcao entre candidatos com total > 0 (zeros se vazio)."""
    p = shares.loc[shares["total"] > 0, "proporcao"]
    if p.empty:
        return {"mediana": 0.0, "p75": 0.0, "p90": 0.0, "max": 0.0}
    return {
        "mediana": float(p.median()),
        "p75": float(p.quantile(0.75)),
        "p90": float(p.quantile(0.90)),
        "max": float(p.max()),
    }
