"""Gera a página HTML de stories (4 cards 1080x1920) a partir de uma execução de `gastos analisar`."""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from gastos.emails import _nome_proprio
from gastos.text import normalize

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"
MAX_LINHAS = 8
PISO_CAMPANHA_PEQUENA = 50_000.0

UF_NOME = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará",
    "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins", "BR": "Brasil",
}
# artigo da UF ("do RN", "da Bahia", "do Brasil")
UF_ARTIGO = {
    "AC": "do", "AL": "de", "AP": "do", "AM": "do", "BA": "da", "CE": "do", "DF": "do", "ES": "do",
    "GO": "de", "MA": "do", "MT": "de", "MS": "de", "MG": "de", "PA": "do", "PB": "da", "PR": "do",
    "PE": "de", "PI": "do", "RJ": "do", "RN": "do", "RS": "do", "RO": "de", "RR": "de", "SC": "de",
    "SP": "de", "SE": "de", "TO": "do", "BR": "do",
}
# cargo normalizado -> (campanhas "ao governo", candidatos "ao governo")
CARGOS = {
    "governador": ("ao governo", "ao governo"),
    "presidente": ("à Presidência", "à Presidência"),
    "senador": ("ao Senado", "ao Senado"),
    "deputado federal": ("a deputado federal", "a deputado federal"),
    "deputado estadual": ("a deputado estadual", "a deputado estadual"),
    "deputado distrital": ("a deputado distrital", "a deputado distrital"),
}


# ordem e rótulos dos cargos na página do estado (chave = cargo normalizado)
ROTULOS_CARGO = {
    "governador": "Governo",
    "senador": "Senado",
    "deputado federal": "Deputados federais",
    "deputado estadual": "Deputados estaduais",
    "deputado distrital": "Deputados distritais",
}
TETOS_EXIBIDOS = (0.05, 0.10, 0.20)
# DS_SIT_TOT_TURNO (normalizado) de uma linha NR_TURNO 2 ja totalizada
SITUACOES_DECIDIDAS = {"eleito", "nao eleito"}


def brl(valor: float) -> str:
    return "R$ " + f"{valor:,.0f}".replace(",", ".")


def pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + "%"


def hero(valor: float) -> tuple[str, str]:
    """Número grande do card 1: ('R$ 574', ' mil') ou ('R$ 4,2', ' mi')."""
    if valor >= 1_000_000:
        return "R$ " + f"{valor / 1_000_000:.1f}".replace(".", ","), " mi"
    if valor >= 1_000:
        return "R$ " + f"{valor / 1_000:.0f}", " mil"
    return brl(valor), ""


def _data(s: str | None) -> str:
    return s if s else "data indisponível"


def linhas_barras(cands: pd.DataFrame, max_linhas: int = MAX_LINHAS, nomes: dict | None = None) -> list[dict]:
    """Uma linha por candidato (maior valor em plataformas primeiro), com largura relativa à maior barra."""
    ordenado = cands.sort_values(["principal", "total", "sq_candidato"], ascending=[False, False, True])
    topo = float(ordenado["principal"].max()) if len(ordenado) else 0.0
    linhas = []
    for _, r in ordenado.head(max_linhas).iterrows():
        pequena = r["total"] < PISO_CAMPANHA_PEQUENA
        linhas.append({
            "nome": _nome_proprio((nomes or {}).get(str(r["sq_candidato"]), str(r["candidato"]))),
            "valor": brl(r["principal"]),
            "largura": round(100 * r["principal"] / topo, 2) if topo > 0 else 0,
            "pct": pct(r["proporcao"]) + " do total da campanha",
            "nota": " (campanha pequena)" if pequena and r["principal"] > 0 else "",
        })
    return linhas


def linhas_consulta_cand(eleitos_zip: Path):
    """Linhas (dict) do arquivo BRASIL do consulta_cand do TSE (latin-1, sem bytes nulos)."""
    with zipfile.ZipFile(eleitos_zip) as z:
        membro = next(n for n in z.namelist() if n.upper().endswith("BRASIL.CSV"))
        texto = z.read(membro).replace(b"\0", b"").decode("latin-1")
    yield from csv.DictReader(io.StringIO(texto), delimiter=";")


def _consulta_cand(eleitos_zip: Path, uf: str, cargo: str | None) -> tuple[int, int, dict]:
    """(candidatos no cargo/UF, quantos seguem no 2º turno, nome completo por SQ) a partir do consulta_cand do TSE."""
    sq_todos, sq_2turno, decididos, nomes = set(), set(), set(), {}
    for r in linhas_consulta_cand(eleitos_zip):
        if r["SG_UF"] != uf:
            continue
        if cargo is None:
            if normalize(r["DS_CARGO"]) not in ROTULOS_CARGO:
                continue
        elif normalize(r["DS_CARGO"]) != normalize(cargo):
            continue
        sq_todos.add(r["SQ_CANDIDATO"])
        nomes[r["SQ_CANDIDATO"]] = r["NM_CANDIDATO"]
        if normalize(r["DS_SIT_TOT_TURNO"]).startswith("2") and r.get("NR_TURNO", "1") == "1":
            sq_2turno.add(r["SQ_CANDIDATO"])
        if r.get("NR_TURNO") == "2" and normalize(r["DS_SIT_TOT_TURNO"]) in SITUACOES_DECIDIDAS:
            decididos.add(r["SQ_CANDIDATO"])
    return len(sq_todos), len(sq_2turno - decididos), nomes


def montar(run: Path, uf: str, cargo: str, n_total: int, n_2turno: int, nomes: dict | None = None) -> dict:
    uf = uf.upper()
    if uf not in UF_NOME:
        raise ValueError(f"UF inválida: {uf!r}")
    chave = normalize(cargo)
    if chave not in CARGOS:
        raise ValueError(f"cargo sem texto definido: {cargo!r} (use um de: {', '.join(sorted(CARGOS))})")
    prep_cargo, prep_curto = CARGOS[chave]
    cands = pd.read_csv(run / "candidatos.csv", sep=";", decimal=",", encoding="utf-8-sig", dtype={"sq_candidato": str})
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    declarados = cands[cands["total"] > 0]
    if declarados.empty:
        raise ValueError("nenhum candidato com despesa declarada nesse recorte")
    principal = float(declarados["principal"].sum())
    h_valor, h_unidade = hero(principal)
    n_decl = len(declarados)
    n_total = max(n_total, n_decl)
    linhas = linhas_barras(declarados, nomes=nomes)
    ocultos = n_decl - len(linhas)
    nota = f"Mostra os {n_decl} candidatos que já declararam despesas ao TSE (de {n_total})."
    if ocultos > 0:
        nota += f" Outros {ocultos}, com valores menores, não aparecem."
    aviso = (f"{n_2turno} candidato{'s seguem' if n_2turno != 1 else ' segue'} no 2º turno: os valores ainda vão crescer."
             if n_2turno > 0 else "Os valores podem mudar até a prestação final.")
    uf_prep = f"{UF_ARTIGO[uf]} {UF_NOME[uf]}"
    return {
        "template": "story.html.j2",
        "titulo": f"anúncios nas campanhas {prep_cargo} {uf_prep}",
        "uf_nome": UF_NOME[uf],
        "uf_nome_prep": uf_prep,
        "prep_cargo": prep_cargo,
        "prep_cargo_curto": prep_curto,
        "hero_valor": h_valor, "hero_unidade": h_unidade,
        "n_declarados": n_decl, "n_total": n_total,
        "linhas": linhas, "compacto": len(linhas) > 6,
        "nota_candidatos": nota, "aviso_valores": aviso,
        "dt_geracao": _data(meta.get("dt_geracao")), "dt_prestacao": _data(meta.get("dt_ultima_prestacao")),
    }


def _fmt_teto(x: float) -> str:
    return f"{x * 100:.0f}%" if abs(x * 100 - round(x * 100)) < 1e-9 else pct(x)


def linhas_por_cargo(cands: pd.DataFrame) -> list[dict]:
    """Uma linha por cargo: valor em plataformas, % do total declarado e quantos candidatos gastaram."""
    chave = cands["cargo"].map(normalize)
    ordem = [c for c in ROTULOS_CARGO if c in set(chave)]
    por_cargo = {c: cands[chave == c] for c in ordem}
    maior = max((float(g["principal"].sum()) for g in por_cargo.values()), default=0.0)
    linhas = []
    for c in ordem:
        g = por_cargo[c]
        valor, total = float(g["principal"].sum()), float(g["total"].sum())
        declarantes = g[g["total"] > 0]
        gastaram = int((declarantes["principal"] > 0).sum())
        linhas.append({
            "rotulo": ROTULOS_CARGO[c],
            "valor": brl(valor),
            "largura": round(100 * valor / maior, 2) if maior > 0 else 0,
            "pct": pct(valor / total if total else 0.0) + " do total declarado nesse cargo",
            "gastaram": f"{gastaram} de {len(declarantes)} candidatos declararam gasto com essas plataformas",
        })
    return linhas


def _tetos(tetos) -> list[dict]:
    """Escolhe 5%, 10% e 20% (ou o que existir) e formata para os cards."""
    linhas = [dict(t) for t in (tetos.to_dict("records") if hasattr(tetos, "to_dict") else tetos)]
    escolhidos = [t for t in linhas if any(abs(float(t["teto"]) - x) < 1e-9 for x in TETOS_EXIBIDOS)] or linhas[:3]
    return [{"teto": _fmt_teto(float(t["teto"])), "n_acima": int(t["n_acima"]),
             "pct": pct(float(t["pct_acima"])), "excedente": brl(float(t["excedente"]))} for t in escolhidos]


def montar_estado(run: Path, uf: str, n_total: int, n_2turno: int,
                  tetos=None) -> dict:
    uf = uf.upper()
    if uf not in UF_NOME or uf == "BR":
        raise ValueError(f"UF inválida para a página do estado: {uf!r}")
    cands = pd.read_csv(run / "candidatos.csv", sep=";", decimal=",", encoding="utf-8-sig", dtype={"sq_candidato": str})
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    if tetos is None:
        arq = run / "tetos.csv"
        tetos = pd.read_csv(arq, sep=";", decimal=",", encoding="utf-8-sig") if arq.exists() else []
    declarados = cands[cands["total"] > 0]
    if declarados.empty:
        raise ValueError("nenhum candidato com despesa declarada nesse recorte")
    principal, total = float(cands["principal"].sum()), float(cands["total"].sum())
    h_valor, h_unidade = hero(principal)
    uf_prep = f"{UF_ARTIGO[uf]} {UF_NOME[uf]}"
    aviso = ("Candidatos ao governo seguem no 2º turno: os valores ainda vão crescer."
             if n_2turno > 0 else "Os valores podem mudar até a prestação final.")
    return {
        "template": "story_estado.html.j2",
        "titulo": f"anúncios nas campanhas {uf_prep}",
        "uf_nome": UF_NOME[uf], "uf_nome_prep": uf_prep,
        "hero_valor": h_valor, "hero_unidade": h_unidade,
        "prop_total": pct(principal / total if total else 0.0),
        "n_declarados": len(declarados), "n_total": max(n_total, len(declarados)),
        "linhas": linhas_por_cargo(cands), "tetos": _tetos(tetos),
        "aviso_valores": aviso,
        "dt_geracao": _data(meta.get("dt_geracao")), "dt_prestacao": _data(meta.get("dt_ultima_prestacao")),
    }


SITE_PADRAO = "radar-impulsionamento.netlify.app"
_HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*$")


def _host(valor: str) -> str:
    """Valida um host simples (letras, dígitos, pontos e hífens; sem esquema, caminho ou espaços)."""
    if not _HOST.match(valor):
        raise argparse.ArgumentTypeError(
            f"endereço inválido {valor!r}: use só o host, como radar-impulsionamento.netlify.app (sem http://, sem caminho, sem espaços)")
    return valor


def renderizar(contexto: dict) -> str:
    contexto = {"site": SITE_PADRAO, **contexto}
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    return env.get_template(contexto.get("template", "story.html.j2")).render(**contexto)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m gastos.story", description=__doc__)
    p.add_argument("--run", required=True, type=Path, help="pasta de uma execução de `gastos analisar` (com candidatos.csv e meta.json)")
    p.add_argument("--uf", required=True, help="UF do recorte, ou BR para candidaturas nacionais")
    p.add_argument("--cargo", default=None, help='cargo do recorte, por exemplo "Governador" ou "Presidente"; sem ele, gera a página do estado (todos os cargos)')
    p.add_argument("--eleitos-zip", type=Path, default=Path("data/raw/consulta_cand_2026.zip"))
    p.add_argument("--site", type=_host, default=SITE_PADRAO, help="endereço do site que aparece nos cards (só o host, sem http://)")
    p.add_argument("--saida", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if a.cargo is None and a.uf.upper() == "BR":
            raise ValueError("para BR informe --cargo (por exemplo Presidente)")
        n_total, n_2turno, nomes = _consulta_cand(a.eleitos_zip, a.uf.upper(), a.cargo)
        if a.cargo is None:
            ctx = montar_estado(a.run, a.uf, n_total, n_2turno)
        else:
            ctx = montar(a.run, a.uf, a.cargo, n_total, n_2turno, nomes=nomes)
    except (OSError, ValueError, StopIteration, zipfile.BadZipFile) as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1
    ctx["site"] = a.site
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    a.saida.write_text(renderizar(ctx), encoding="utf-8")
    print(f"Gravado em {a.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
