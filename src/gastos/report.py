"""Evidencia rastreavel e relatorio por execucao.

Cada execucao grava `out/AAAA-MM-DD_<recorte>/` com:
- evidencia_<nivel>.csv: linhas completas classificadas de cada nivel (confirmado/generico/provavel);
  a soma de `valor` de cada arquivo e igual ao numero publicado em resumo.csv e relatorio.md;
- resumo.csv, candidatos.csv, tetos.csv: saidas de `metrics`;
- qualidade.md: totais por nivel e amostras (inclui as maiores linhas `nenhum`, para achar omissoes);
- relatorio.md: número principal (confirmado + generico), piso (confirmado), distribuicao, tetos.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd

from gastos import metrics

NIVEIS_EVIDENCIA = ("confirmado", "generico", "provavel")
CHAVES = ("uf", "cargo", "partido", "candidato")
AMOSTRA = 10
CSV = dict(index=False, sep=";", decimal=",", encoding="utf-8-sig")  # Excel pt-BR
COLUNAS_AMOSTRA = ["sq_candidato", "candidato", "uf", "cargo", "fornecedor", "descricao", "valor", "plataforma"]


def _slug(texto: str) -> str:
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _nome_recorte(recorte: dict) -> str:
    partes = []
    for k in CHAVES:
        v = recorte.get(k)
        if v is None or str(v).strip() == "":
            continue
        if k == "uf":
            uf = str(v).strip()
            if not re.fullmatch(r"[A-Za-z]{2}", uf):
                raise ValueError(f"uf invalida (esperado 2 letras, ex. RN ou BR): {v!r}")
            partes.append(f"uf-{uf.upper()}")  # UF em maiusculas (uf-RN)
        else:  # demais valores: slug ascii minusculo
            partes.append(f"{k}-{_slug(v)}")
    return "_".join(partes) if partes else "brasil"


def _brl(x: float) -> str:
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + "%"


def _data_corte(df: pd.DataFrame) -> str | None:
    if "dt_geracao" not in df.columns:
        return None
    datas = pd.to_datetime(df["dt_geracao"], format="%d/%m/%Y", errors="coerce").dropna()
    return None if datas.empty else datas.max().strftime("%d/%m/%Y")


def _dt_ultima_prestacao(df: pd.DataFrame) -> str | None:
    if "dt_prestacao" not in df.columns:
        return None
    datas = pd.to_datetime(df["dt_prestacao"], format="%d/%m/%Y", errors="coerce").dropna()
    return None if datas.empty else datas.max().strftime("%d/%m/%Y")


def _tabela_md(df: pd.DataFrame, formatos: dict | None = None) -> str:
    formatos = formatos or {}
    cab = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "|".join(" --- " for _ in df.columns) + "|"
    linhas = [
        "| " + " | ".join(
            formatos.get(c, str)(v).replace("|", "/") for c, v in zip(df.columns, row)
        ) + " |"
        for row in df.itertuples(index=False)
    ]
    return "\n".join([cab, sep, *linhas])


def _limpa(v, n: int = 80) -> str:
    t = re.sub(r"\s+", " ", str(v)).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _amostra(df: pd.DataFrame, nivel: str) -> pd.DataFrame:
    sub = df[df["nivel"] == nivel].sort_values(["valor", "sq_despesa"], ascending=[False, True], kind="mergesort")
    cols = [c for c in COLUNAS_AMOSTRA if c in sub.columns]
    out = sub.head(AMOSTRA)[cols].copy()
    for c in ("descricao", "fornecedor"):
        if c in out.columns:
            out[c] = out[c].map(_limpa)
    return out


def _qualidade(df: pd.DataFrame) -> str:
    out = ["# Qualidade da classificação", ""]
    linhas = []
    for n in (*NIVEIS_EVIDENCIA, "nenhum"):
        sub = df[df["nivel"] == n]
        linhas.append((n, len(sub), float(sub["valor"].sum())))
    out += [
        "## Totais por nível", "",
        _tabela_md(pd.DataFrame(linhas, columns=["nível", "linhas", "valor"]), {"valor": _brl, "linhas": str}),
        "",
    ]
    if "tp_prestacao" in df.columns:
        por_tp = (df.groupby("tp_prestacao", dropna=False)["valor"].agg(["size", "sum"])
                  .reset_index().sort_values("sum", ascending=False))
        por_tp.columns = ["tipo", "linhas", "valor"]
        out += ["## Por tipo de prestação", "",
                "Mistura de prestações no recorte (valor contratado e número de linhas).", "",
                _tabela_md(por_tp, {"valor": _brl, "linhas": str}), ""]
    for n in (*NIVEIS_EVIDENCIA, "nenhum"):
        titulo = (
            f"## Amostra de `{n}` (até {AMOSTRA} linhas de maior valor)"
            if n != "nenhum"
            else f"## As {AMOSTRA} maiores linhas `nenhum` (para conferir omissões)"
        )
        a = _amostra(df, n)
        out += [titulo, ""]
        out += [_tabela_md(a, {"valor": _brl}) if len(a) else "_Sem linhas._", ""]
    return "\n".join(out)


def _relatorio(df, recorte, resumo, shares, tetos, dist) -> str:
    r = resumo.iloc[0]
    corte = _data_corte(df)
    recorte_txt = ", ".join(f"{k}: {v}" for k, v in recorte.items() if v) or "Brasil (todos)"
    ger, ult = corte, _dt_ultima_prestacao(df)
    datas_txt = (
        f"dados gerados pelo TSE em **{ger or 'data não informada'}**; as prestações de contas mais "
        f"recentes incluídas foram entregues até **{ult or 'data não informada'}**"
    )
    corte_txt = (
        f"Os dados são **parciais**: {datas_txt}. Reúnem prestações parciais e relatórios financeiros "
        f"(algumas campanhas já entregaram a prestação final); os valores podem mudar até a prestação "
        f"final de todas."
    )
    tabela_tetos = _tabela_md(
        tetos,
        {"teto": _pct, "n_acima": str, "pct_acima": _pct, "excedente": _brl},
    )
    return f"""# Gasto de campanha com plataformas de anúncio estrangeiras

Recorte: {recorte_txt}

{corte_txt}

## Número principal

- **Gasto com plataformas estrangeiras (confirmado + generico): {_brl(r['principal'])}**
- **Piso (apenas confirmado): {_brl(r['confirmado'])}**
- Proporção sobre o total de despesas contratadas dos candidatos ({_brl(r['total'])}): **{_pct(r['proporcao'])}**
- Candidatos no recorte: {int(r['n_candidatos'])}

Base: despesas contratadas dos candidatos (órgãos partidários ficam fora). Cada número tem as linhas
que o compõem em `evidencia_confirmado.csv` e `evidencia_generico.csv`.

## Distribuição da proporção entre candidatos

Candidatos com gasto total maior que zero.

| mediana | p75 | p90 | max |
| --- | --- | --- | --- |
| {_pct(dist['mediana'])} | {_pct(dist['p75'])} | {_pct(dist['p90'])} | {_pct(dist['max'])} |

## Impacto de tetos percentuais

Para cada teto: candidatos acima dele e o excedente (principal menos teto x total, só dos candidatos acima).

{tabela_tetos}

## Nota: gasto provável (fora do número principal)

Há {_brl(r['provavel'])} em despesas classificadas como `provavel` (por exemplo, gateways de pagamento
sem indicação da plataforma). Esse valor **não** está somado ao número principal; as linhas estão em
`evidencia_provavel.csv`.
"""


def write_run(
    df: pd.DataFrame,
    recorte: dict,
    out_root: Path = Path("out"),
    caps: list[float] = [0.05, 0.10, 0.15, 0.20],
    today: date | None = None,
) -> Path:
    """Grava a execucao datada e devolve a pasta. Mesmo dia + mesmo recorte sobrescreve os arquivos."""
    today = today or date.today()
    pasta = Path(out_root) / f"{today.isoformat()}_{_nome_recorte(recorte)}"
    pasta.mkdir(parents=True, exist_ok=True)

    for n in NIVEIS_EVIDENCIA:
        df[df["nivel"] == n].to_csv(pasta / f"evidencia_{n}.csv", **CSV)

    resumo = metrics.summarize(df, [])
    if resumo.empty:  # entrada vazia: linha zerada, sem NaN
        resumo = pd.DataFrame(
            [{"total": 0.0, "confirmado": 0.0, "generico": 0.0, "provavel": 0.0,
              "principal": 0.0, "proporcao": 0.0, "n_candidatos": 0}]
        )
    shares = metrics.candidate_shares(df)
    tetos = metrics.cap_impact(shares, caps)
    dist = metrics.distribution(shares)

    resumo.to_csv(pasta / "resumo.csv", **CSV)
    shares.to_csv(pasta / "candidatos.csv", **CSV)
    tetos.to_csv(pasta / "tetos.csv", **CSV)
    (pasta / "meta.json").write_text(
        json.dumps({"dt_geracao": _data_corte(df), "dt_ultima_prestacao": _dt_ultima_prestacao(df)},
                   ensure_ascii=False), encoding="utf-8")
    (pasta / "qualidade.md").write_text(_qualidade(df), encoding="utf-8")
    (pasta / "relatorio.md").write_text(_relatorio(df, recorte, resumo, shares, tetos, dist), encoding="utf-8")
    return pasta
