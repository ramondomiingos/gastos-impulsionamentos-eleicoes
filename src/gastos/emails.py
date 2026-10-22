"""Modelos de e-mail por estado, a partir das execucoes de `report.write_run`.

Os numeros sao SEMPRE os da UF inteira (todos os cargos e candidatos), lidos de
`resumo.csv` e `candidatos.csv` da pasta da execucao. Nenhum e-mail e gerado
sem numeros: UF sem execucao, sem gasto classificado ou sem data de corte vai
para `pendencias.md`. O pipeline nao envia nada.
"""
from __future__ import annotations

import csv
import math
import shutil
from pathlib import Path

import jinja2
import pandas as pd

from gastos import metrics
from gastos.eleitos import cargo_tse, match_contatos
from gastos.report import _brl, _pct, _slug
from gastos.text import normalize

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"
OBRIGATORIAS = ("nome", "cargo", "uf", "email")
UF_NOMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará",
    "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins",
}
_CSV_LEITURA = dict(sep=";", decimal=",", encoding="utf-8-sig")


# ------------------------------------------------------------------ contatos

def _email_valido(e: str) -> bool:
    if e.count("@") != 1 or " " in e:
        return False
    local, dominio = e.split("@")
    return bool(local) and "." in dominio and not dominio.startswith(".") and not dominio.endswith(".")


def load_contatos(path: Path) -> pd.DataFrame:
    """Le o CSV de contatos (utf-8-sig, `;` ou `,`). Colunas: nome, cargo, uf, email (+ sq_candidato)."""
    texto = Path(path).read_text(encoding="utf-8-sig")
    if not texto.strip():
        raise ValueError(f"Arquivo de contatos vazio: {path}")
    cab = texto.splitlines()[0]
    sep = ";" if cab.count(";") > cab.count(",") else ","
    linhas = list(csv.reader(texto.splitlines(), delimiter=sep))
    colunas = [c.strip().lower() for c in linhas[0]]
    faltam = [c for c in OBRIGATORIAS if c not in colunas]
    if faltam:
        raise ValueError(f"Coluna(s) ausente(s) nos contatos: {', '.join(faltam)} (esperado: nome,cargo,uf,email)")
    registros = []
    for n, lin in enumerate(linhas[1:], start=2):  # n = numero da linha no arquivo
        vals = [v.strip() for v in lin] + [""] * (len(colunas) - len(lin))
        if not any(vals):
            continue
        registros.append({"_linha": n, **dict(zip(colunas, vals))})
    if not registros:
        raise ValueError(f"Arquivo de contatos vazio (sem linhas de dados): {path}")
    d = pd.DataFrame(registros)
    ruins = [int(r["_linha"]) for _, r in d.iterrows() if not _email_valido(r["email"])]
    if ruins:
        raise ValueError("E-mail invalido nas linhas: " + ", ".join(map(str, ruins)))
    d["uf"] = d["uf"].str.upper()
    ordem = list(OBRIGATORIAS) + [c for c in colunas if c not in OBRIGATORIAS]
    return d[list(dict.fromkeys(ordem))].reset_index(drop=True)


# -------------------------------------------------------------------- numeros

def _dt_corte(pasta: Path) -> str | None:
    datas = []
    for f in sorted(pasta.glob("evidencia_*.csv")):
        d = pd.read_csv(f, dtype=str, **{k: v for k, v in _CSV_LEITURA.items() if k != "decimal"})
        if "dt_geracao" in d.columns:
            datas.append(pd.to_datetime(d["dt_geracao"], format="%d/%m/%Y", errors="coerce"))
    if not datas:
        return None
    s = pd.concat(datas).dropna()
    return None if s.empty else s.max().strftime("%d/%m/%Y")


def stats_from_run(pasta: Path, teto: float) -> tuple[dict, str | None]:
    """Numeros da UF inteira a partir da pasta da execucao: (stats, dt_corte)."""
    pasta = Path(pasta)
    r = pd.read_csv(pasta / "resumo.csv", **_CSV_LEITURA).iloc[0]
    shares = pd.read_csv(pasta / "candidatos.csv", **_CSV_LEITURA)
    dist = metrics.distribution(shares)
    imp = metrics.cap_impact(shares, [teto]).iloc[0]
    stats = {
        "total": float(r["total"]), "principal": float(r["principal"]),
        "confirmado": float(r["confirmado"]), "provavel": float(r.get("provavel", 0.0) or 0.0),
        "proporcao": float(r["proporcao"]), "mediana": dist["mediana"], "p90": dist["p90"],
        "impacto_teto": {"n_acima": int(imp["n_acima"]), "pct_acima": float(imp["pct_acima"]),
                         "excedente": float(imp["excedente"])},
    }
    return stats, _dt_corte(pasta)


# --------------------------------------------------------------------- e-mail

def _num(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"numero ausente ou invalido: {v!r}")
    if not math.isfinite(f):
        raise ValueError(f"numero ausente ou invalido: {v!r}")
    return f


def _teto_txt(t: float) -> str:
    p = round(t * 100, 2)
    return (f"{int(p)}" if p == int(p) else f"{p}".replace(".", ",")) + "%"


def render_email(contato: pd.Series, stats: dict, teto_proposto: float, dt_corte: str,
                 assinatura: str = "[Seu nome]") -> str:
    """Renderiza o e-mail. Levanta ValueError se faltar qualquer numero (nunca renderiza vazio)."""
    if not dt_corte or not str(dt_corte).strip():
        raise ValueError("data de corte ausente")
    _num(teto_proposto)
    try:
        imp = stats["impacto_teto"]
        v = {k: _num(stats[k]) for k in ("total", "principal", "confirmado", "proporcao", "mediana", "p90")}
        n_acima, pct_acima, exced = int(_num(imp["n_acima"])), _num(imp["pct_acima"]), _num(imp["excedente"])
    except (KeyError, TypeError) as e:
        raise ValueError(f"estatistica ausente: {e}")
    if v["total"] <= 0 or v["principal"] <= 0:
        raise ValueError("UF sem gasto classificado: nao ha numero para o e-mail")
    provavel = stats.get("provavel")
    provavel = _num(provavel) if provavel not in (None, "") else 0.0
    uf = str(contato["uf"]).strip().upper()
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES), undefined=jinja2.StrictUndefined,
                             keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True)
    return env.get_template("email_estado.md.j2").render(
        nome=str(contato["nome"]).strip(), cargo=str(contato["cargo"]).strip(), uf=uf,
        uf_nome=UF_NOMES.get(uf, uf), principal=_brl(v["principal"]), confirmado=_brl(v["confirmado"]),
        proporcao=_pct(v["proporcao"]), mediana=_pct(v["mediana"]), p90=_pct(v["p90"]),
        teto=_teto_txt(teto_proposto), n_acima=n_acima, pct_acima=_pct(pct_acima), excedente=_brl(exced),
        provavel=_brl(provavel) if provavel > 0 else "", dt_corte=str(dt_corte).strip(),
        assinatura=assinatura,
    )


# ------------------------------------------------------------------ gravacao

def _ufs_com_numeros(uf_runs: dict[str, Path], teto: float) -> tuple[dict, dict]:
    """Devolve ({uf: (stats, dt_corte)}, {uf: motivo}) para as UFs com/sem numeros."""
    ok, falhas = {}, {}
    for uf, pasta in uf_runs.items():
        try:
            stats, corte = stats_from_run(pasta, teto)
            if stats["total"] <= 0 or stats["principal"] <= 0:
                falhas[uf] = "sem gasto classificado como plataforma estrangeira"
            elif not corte:
                falhas[uf] = "sem data de corte nos dados"
            else:
                ok[uf] = (stats, corte)
        except (FileNotFoundError, KeyError, IndexError, ValueError) as e:
            falhas[uf] = f"execucao ilegivel ({e})"
    return ok, falhas


def _linha_contato(c) -> str:
    return f"{c['nome']} | {c['cargo']} | {c['uf']} | {c['email']}"


def write_emails(contatos_csv: Path, uf_runs: dict[str, Path], teto_proposto: float, out: Path,
                 eleitos: pd.DataFrame | None = None, assinatura: str = "[Seu nome]") -> Path:
    """Escreve `emails/<uf>/<slug>.md`, `pendencias.md`, `indice.csv` e copia as execucoes em `runs/`."""
    if eleitos is None:
        raise ValueError("eleitos e obrigatorio (use eleitos.load_eleitos)")
    out = Path(out)
    contatos = load_contatos(contatos_csv)
    casados, pendentes = match_contatos(contatos, eleitos)
    uf_runs = {k.upper(): v for k, v in uf_runs.items()}
    numeros, falhas = _ufs_com_numeros(uf_runs, teto_proposto)

    out.mkdir(parents=True, exist_ok=True)
    indice, sem_numero, usados = [], [], set()
    for c in casados.to_dict("records"):
        uf = str(c["uf_eleito"]).upper()
        if uf not in numeros:
            motivo = falhas.get(uf, "UF sem execucao de analise (sem dados)")
            sem_numero.append((c, motivo))
            continue
        stats, corte = numeros[uf]
        texto = render_email(pd.Series({**c, "uf": uf}), stats, teto_proposto, corte, assinatura)
        pasta = out / "emails" / uf.lower()
        pasta.mkdir(parents=True, exist_ok=True)
        slug = _slug(c["nome"]) or "contato"
        if (uf, slug) in usados:
            slug = f"{slug}-{c['sq_candidato']}"
        usados.add((uf, slug))
        arq = pasta / f"{slug}.md"
        arq.write_text(texto, encoding="utf-8")
        indice.append({"nome": c["nome"], "cargo": c["cargo"], "uf": uf, "email": c["email"],
                       "arquivo": str(arq.relative_to(out))})
    pd.DataFrame(indice, columns=["nome", "cargo", "uf", "email", "arquivo"]).to_csv(
        out / "indice.csv", index=False, sep=";", encoding="utf-8-sig")

    for uf, pasta in uf_runs.items():  # copia para conferir os numeros
        destino = out / "runs" / Path(pasta).name
        if Path(pasta).is_dir() and destino.resolve() != Path(pasta).resolve():
            shutil.copytree(pasta, destino, dirs_exist_ok=True)

    (out / "pendencias.md").write_text(
        _pendencias(pendentes, sem_numero, falhas, uf_runs, eleitos), encoding="utf-8")
    return out


def _pendencias(pendentes, sem_numero, falhas, uf_runs, eleitos) -> str:
    L = ["# Pendências", "", "Nenhum e-mail foi gerado para os itens abaixo.", ""]
    L += ["## Contatos sem e-mail gerado (ligação com a lista de eleitos)", ""]
    if pendentes.empty:
        L.append("Nenhum.")
    for c in pendentes.to_dict("records"):
        L.append(f"- {_linha_contato(c)} | motivo: {c['motivo']}")
    L += ["", "## UFs sem números (contatos casados, mas sem e-mail)", ""]
    if not sem_numero:
        L.append("Nenhuma.")
    for c, motivo in sem_numero:
        L.append(f"- {_linha_contato({**c, 'uf': c['uf_eleito']})} | UF {c['uf_eleito']}: {motivo}")
    for uf, motivo in sorted(falhas.items()):
        L.append(f"- UF {uf}: {motivo}")
    L += ["", "## Lista de eleitos possivelmente incompleta", ""]
    avisos = []
    tem = {(str(r.uf).upper(), r.cargo) for r in eleitos.itertuples(index=False)}
    for c in pendentes.to_dict("records"):
        cargo = cargo_tse(c.get("cargo"))
        uf = str(c.get("uf") or "").strip().upper()
        if cargo and (uf, cargo) not in tem:
            avisos.append(f"- {uf} / {cargo}: nenhum eleito na fonte do TSE; a lista parece incompleta "
                          f"(defasagem de dados, não erro do código). Contato: {c['nome']}")
    L += sorted(set(avisos)) or ["Nenhum aviso."]
    return "\n".join(L) + "\n"
