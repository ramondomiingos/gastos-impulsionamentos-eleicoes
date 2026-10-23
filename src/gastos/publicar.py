"""`gastos publicar`: grava os JSON do site (`site/data/`) a partir do pipeline loader -> classify -> metrics.

Formato: ver docs/superpowers/specs/2026-10-23-site-funcional-design.md. O arquivo nacional e carregado e
classificado UMA vez; cada UF e fatiada em memoria. Sem campo de partido; nomes so em `top`.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from gastos import metrics
from gastos.classify import classify, load_rules
from gastos.emails import _nome_proprio
from gastos.loader import load_despesas, load_pagamentos
from gastos.report import _data_corte, _dt_ultima_prestacao
from gastos.story import UF_ARTIGO, UF_NOME, linhas_consulta_cand
from gastos.text import normalize

TETOS_PADRAO = [0.05, 0.10, 0.15, 0.20]
PISO_CAMPANHA = 50_000.0
TOP_N = 5

# slug -> (nome do cargo no TSE, rotulo na pagina). A ordem e a dos cargos nos arquivos.
CARGOS_SITE = {
    "presidente": ("Presidente", "Presidência"),
    "governador": ("Governador", "Governo"),
    "senador": ("Senador", "Senado"),
    "deputado-federal": ("Deputado Federal", "Deputados federais"),
    "deputado-estadual": ("Deputado Estadual", "Deputados estaduais"),
    "deputado-distrital": ("Deputado Distrital", "Deputados distritais"),
}
CARGOS_ESTADO = [s for s in CARGOS_SITE if s != "presidente"]
ROTULO_TODOS = "Todos os cargos"
# DS_FONTE_DESPESA comparado apos `normalize` (sem acento/caixa/espacos extras)
FONTES_PUBLICAS = ("fundo especial de financiamento de campanha", "fundo partidario")
FONTES_NAO_PUBLICAS = ("outros recursos",)
NIVEIS_PRINCIPAL = ("confirmado", "generico")
VERSAO = 1


class Resultado(NamedTuple):
    pasta: Path
    pagamentos_sem_linha: int  # pagamentos (SQ_DESPESA) sem linha contratada correspondente
    valor_sem_linha: float
    fontes_desconhecidas: dict  # DS_FONTE_DESPESA nao reconhecida (tratada como nao publica) -> valor pago


def alocar_pagamentos(df: pd.DataFrame, pagos: pd.DataFrame) -> tuple[pd.DataFrame, tuple[int, float], dict]:
    """Acrescenta `pago` e `pago_publico` as linhas contratadas de `df`.

    O pago de cada SQ_DESPESA e repartido entre suas linhas contratadas proporcionalmente ao valor;
    so linhas de nivel confirmado/generico recebem (as demais ficam em 0). Devolve tambem
    (quantidade de SQ_DESPESA pagos sem linha contratada, valor pago correspondente) e as fontes
    desconhecidas ({texto original: valor pago}); estas nao contam como publicas.
    """
    norm = pagos["fonte"].map(normalize)
    desconhecidas = (pagos[~norm.isin(FONTES_PUBLICAS + FONTES_NAO_PUBLICAS)]
                     .groupby("fonte")["valor"].sum().round(2).to_dict())
    por_sq = pagos.assign(_pub=pagos["valor"].where(norm.isin(FONTES_PUBLICAS), 0.0))
    por_sq = por_sq.groupby("sq_despesa").agg(_pago=("valor", "sum"), _pub=("_pub", "sum"))
    contratado = df.groupby("sq_despesa")["valor"].sum()
    com_linha = por_sq.index.isin(contratado[contratado != 0].index)
    sem = por_sq[~com_linha]
    out = df.copy()
    peso = (out["valor"] / out["sq_despesa"].map(contratado).replace(0, float("nan"))).fillna(0.0)
    peso = peso.where(out["nivel"].isin(NIVEIS_PRINCIPAL), 0.0)
    out["pago"] = peso * out["sq_despesa"].map(por_sq["_pago"]).fillna(0.0)
    out["pago_publico"] = peso * out["sq_despesa"].map(por_sq["_pub"]).fillna(0.0)
    return out, (int(len(sem)), float(sem["_pago"].sum())), {k: float(v) for k, v in desconhecidas.items()}


def slug_cargo(cargo: str) -> str:
    return normalize(cargo).replace(" ", "-")


def _dinheiro(x) -> float:
    return round(float(x), 2)


def _prop(x) -> float:
    return round(float(x), 6)


def montar_recorte(shares: pd.DataFrame, rotulo: str, cargo: str | None, nomes: dict[str, str],
                   tetos: list[float], piso_campanha: float) -> dict:
    """Formato `Recorte` do desenho a partir de `candidate_shares` do recorte."""
    total = float(shares["total"].sum())
    principal = float(shares["principal"].sum())
    if not {"pago", "pago_publico"} <= set(shares.columns):
        raise ValueError("montar_recorte: `shares` sem as colunas pago/pago_publico (use alocar_pagamentos)")
    pago = float(shares["pago"].sum())
    pago_publico = float(shares["pago_publico"].sum())
    elegiveis = shares[shares["total"] >= piso_campanha]
    impacto = metrics.cap_impact(elegiveis, tetos)
    top = []
    for r in metrics.maiores_valores(shares, TOP_N).itertuples(index=False):
        sq = str(r.sq_candidato)
        nome_cargo = CARGOS_SITE.get(slug_cargo(r.cargo), (str(r.cargo),))[0]
        top.append({
            "sq": sq,
            "nome": nomes.get(sq) or _nome_proprio(r.candidato),
            "cargo": nome_cargo,
            "uf": str(r.uf),
            "principal": _dinheiro(r.principal),
            "confirmado": _dinheiro(r.confirmado),
            "total": _dinheiro(r.total),
            "proporcao": _prop(r.proporcao),
            "pequena": bool(r.total < piso_campanha),
        })
    return {
        "rotulo": rotulo,
        "cargo": cargo,
        "total": _dinheiro(total),
        "principal": _dinheiro(principal),
        "confirmado": _dinheiro(shares["confirmado"].sum()),
        "generico": _dinheiro(shares["generico"].sum()),
        "provavel": _dinheiro(shares["provavel"].sum()),
        "proporcao": _prop(principal / total) if total else 0.0,
        "n_candidatos": int((shares["total"] > 0).sum()),
        "n_gastaram": int((shares["principal"] > 0).sum()),
        "n_elegiveis": int(len(elegiveis)),
        "pago": _dinheiro(pago),
        "pago_publico": _dinheiro(pago_publico),
        "pct_publico": _prop(pago_publico / pago) if pago else 0.0,
        # limitada a 1: pago pode passar do principal (aditivos pagos acima do contratado)
        "cobertura_pago": _prop(min(1.0, pago / principal)) if principal else 0.0,
        "tetos": [{"teto": float(t.teto), "n_acima": int(t.n_acima), "pct_acima": _prop(t.pct_acima),
                   "excedente": _dinheiro(t.excedente)} for t in impacto.itertuples(index=False)],
        "top": top,
    }


def _slugs(df: pd.DataFrame) -> pd.Series:
    return df["cargo"].map(slug_cargo)


def _shares(df: pd.DataFrame) -> pd.DataFrame:
    """`candidate_shares` mais `pago`/`pago_publico` por candidato, quando `df` os traz."""
    shares = metrics.candidate_shares(df)
    if "pago" in df.columns:
        soma = df.groupby("sq_candidato")[["pago", "pago_publico"]].sum()
        shares = shares.join(soma, on="sq_candidato")
    return shares


def _cargos_do_recorte(uf: str) -> list[str]:
    return ["presidente"] if uf == "BR" else CARGOS_ESTADO


def montar_uf(df: pd.DataFrame, uf: str, nomes: dict[str, str], info: dict, tetos: list[float],
              piso_campanha: float, meta: dict | None = None) -> dict:
    """Conteudo de `<UF>.json`. `df` = despesas classificadas da UF (BR: so Presidente).

    `info`: {"n_candidatos_total": int, "segundo_turno": int}. `meta` (opcional) sobrepoe
    dt_geracao/dt_ultima_prestacao; sem ele as datas saem do proprio `df`, como em `report.write_run`.
    """
    meta = meta or {}
    permitidos = _cargos_do_recorte(uf)
    df = df[_slugs(df).isin(permitidos)]
    slugs = _slugs(df)
    recortes = {}
    if uf != "BR" and not df.empty:
        recortes["todos"] = montar_recorte(_shares(df), ROTULO_TODOS, None, nomes,
                                           tetos, piso_campanha)
    for slug in permitidos:
        sub = df[slugs == slug]
        if sub.empty:
            continue
        nome_cargo, rotulo = CARGOS_SITE[slug]
        recortes[slug] = montar_recorte(_shares(sub), rotulo, nome_cargo, nomes,
                                        tetos, piso_campanha)
    return {
        "uf": uf,
        "nome": UF_NOME[uf],
        "artigo": UF_ARTIGO[uf],
        "dt_geracao": meta.get("dt_geracao", _data_corte(df)),
        "dt_ultima_prestacao": meta.get("dt_ultima_prestacao", _dt_ultima_prestacao(df)),
        "segundo_turno": int(info["segundo_turno"]),
        "n_candidatos_total": int(info["n_candidatos_total"]),
        "recortes": recortes,
    }


def _ler_candidatos(eleitos_zip: Path) -> tuple[dict[str, str], dict[str, dict]]:
    """(nome em caixa de titulo por SQ, {uf: {"n_candidatos_total", "segundo_turno"}}) dos cargos do site."""
    nomes: dict[str, str] = {}
    sqs: dict[str, set] = {}
    seg: dict[str, set] = {}
    for r in linhas_consulta_cand(eleitos_zip):
        slug = slug_cargo(r["DS_CARGO"])
        uf = r["SG_UF"]
        if slug not in CARGOS_SITE or (slug == "presidente") != (uf == "BR"):
            continue
        sq = r["SQ_CANDIDATO"]
        sqs.setdefault(uf, set()).add(sq)
        nomes[sq] = _nome_proprio(r["NM_CANDIDATO"])
        if normalize(r["DS_SIT_TOT_TURNO"]).startswith("2") and r.get("NR_TURNO", "1") == "1":
            seg.setdefault(uf, set()).add(sq)
    info = {uf: {"n_candidatos_total": len(s), "segundo_turno": len(seg.get(uf, ()))} for uf, s in sqs.items()}
    return nomes, info


def _num(x: float):
    return int(x) if float(x).is_integer() else float(x)


def _gravar(caminho: Path, dados: dict) -> None:
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")


def publicar(zip_path, eleitos_zip, saida: Path, tetos: list[float] | None = None,
             piso_campanha: float = PISO_CAMPANHA, hoje: date | None = None) -> Resultado:
    """Grava `index.json`, `BR.json` e um `<UF>.json` por estado em `saida`; devolve pasta e aviso de pagamentos sem linha."""
    if not (piso_campanha > 0) or piso_campanha == float("inf"):
        raise ValueError(f"piso_campanha invalido: {piso_campanha!r}")
    tetos = list(TETOS_PADRAO if tetos is None else tetos)
    hoje = hoje or date.today()
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)

    nomes, infos = _ler_candidatos(Path(eleitos_zip))
    df = load_despesas(Path(zip_path), None)
    if df.empty:
        raise FileNotFoundError("Nenhuma despesa no arquivo nacional.")
    df = classify(df, load_rules())
    df, (n_sem, v_sem), desconhecidas = alocar_pagamentos(df, load_pagamentos(Path(zip_path)))
    meta = {"dt_geracao": _data_corte(df), "dt_ultima_prestacao": _dt_ultima_prestacao(df)}

    vazio = {"n_candidatos_total": 0, "segundo_turno": 0}
    entradas = []
    ufs = ["BR", *sorted(u for u in df["uf"].unique() if u in UF_NOME and u != "BR")]
    for uf in ufs:
        dados = montar_uf(df[df["uf"] == uf], uf, nomes, infos.get(uf, vazio), tetos, piso_campanha,
                          meta if uf == "BR" else None)
        if not dados["recortes"]:
            continue
        _gravar(saida / f"{uf}.json", dados)
        entradas.append({"uf": uf, "nome": dados["nome"], "artigo": dados["artigo"],
                         "cargos": list(dados["recortes"])})
    _gravar(saida / "index.json", {
        "versao": VERSAO,
        "gerado_em": hoje.strftime("%Y-%m-%d"),
        "dt_geracao": meta["dt_geracao"],
        "dt_ultima_prestacao": meta["dt_ultima_prestacao"],
        "piso_campanha": _num(piso_campanha),
        "tetos": tetos,
        "ufs": entradas,
    })
    return Resultado(saida, n_sem, round(v_sem, 2), desconhecidas)
