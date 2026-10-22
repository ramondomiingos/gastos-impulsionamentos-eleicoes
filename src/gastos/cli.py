"""CLI: `gastos analisar [--uf UF] [--cargo C] [--partido P] [--candidato N|SQ] [--tetos ...]`.

Fluxo: valida opcoes -> baixa (se preciso) -> carrega -> filtra -> classifica -> `report.write_run`.
`main` devolve o codigo de saida (0 ok, 2 opcao invalida, 1 recorte sem resultado); nao chama sys.exit.
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

from gastos.classify import classify, load_rules
from gastos.eleitos import download_resultados, load_eleitos
from gastos.emails import load_contatos, write_emails
from gastos.fetch import download_candidatos
from gastos.loader import load_despesas
from gastos.report import write_run
from gastos.text import normalize

CAPS_PADRAO = [0.05, 0.10, 0.15, 0.20]


class _Erro(Exception):
    def __init__(self, msg: str, codigo: int = 1):
        super().__init__(msg)
        self.codigo = codigo


def _parse_uf(valor: str) -> str | None:
    """Devolve a UF em maiusculas, ou None para o pais (BR)."""
    uf = valor.strip()
    if not re.fullmatch(r"[A-Za-z]{2}", uf):
        raise _Erro(f"--uf invalida: {valor!r} (use duas letras, ex. RN, ou BR para o pais)", 2)
    uf = uf.upper()
    return None if uf == "BR" else uf


def _parse_tetos(valor: str) -> list[float]:
    try:
        tetos = [float(p.strip()) for p in valor.split(",")]
    except ValueError:
        raise _Erro(f"--tetos invalido: {valor!r} (use numeros separados por virgula, ex. 0.05,0.10)", 2)
    if not tetos or any(t != t or t <= 0 or t > 1 for t in tetos):
        raise _Erro(f"--tetos invalido: {valor!r} (cada teto deve estar entre 0 e 1, ex. 0.05,0.10)", 2)
    return tetos


def _disponiveis(df: pd.DataFrame, col: str) -> str:
    return ", ".join(sorted(v for v in df[col].dropna().unique() if str(v).strip())) or "(nenhum)"


def _filtrar_candidato(df: pd.DataFrame, valor: str) -> pd.DataFrame:
    alvo = valor.strip()
    if alvo.isdigit():
        sub = df[df["sq_candidato"].astype(str).str.strip() == alvo]
    else:
        alvo_n = normalize(alvo)
        sub = df[df["candidato"].map(normalize) == alvo_n]
    if sub.empty:
        raise _Erro(f"Candidato nao encontrado no recorte: {valor!r}. Use o nome completo ou o SQ_CANDIDATO.")
    cands = sub[["sq_candidato", "candidato", "cargo", "partido"]].drop_duplicates("sq_candidato")
    if len(cands) > 1:
        linhas = "\n".join(
            f"  {r.sq_candidato} | {r.candidato} | {r.cargo} | {r.partido}"
            for r in cands.sort_values("sq_candidato").itertuples()
        )
        raise _Erro(
            f"Nome ambiguo: {valor!r} corresponde a {len(cands)} candidatos. "
            f"Use o SQ_CANDIDATO (sq_candidato | nome | cargo | partido):\n{linhas}"
        )
    return sub


def _filtrar(df: pd.DataFrame, cargo, partido, candidato) -> pd.DataFrame:
    base = df
    if cargo:
        df = df[df["cargo"].map(normalize) == normalize(cargo)]
    if partido:
        df = df[df["partido"].map(normalize) == normalize(partido)]
    if df.empty and (cargo or partido):
        raise _Erro(
            "Nenhuma despesa para esse recorte. Disponiveis neste recorte de UF:\n"
            f"  cargos: {_disponiveis(base, 'cargo')}\n  partidos: {_disponiveis(base, 'partido')}"
        )
    if candidato:
        df = _filtrar_candidato(df, candidato)
    return df.reset_index(drop=True)


def rodar_uf(zip_path: Path, uf: str, saida: Path, caps: list[float]) -> Path:
    """Analisa a UF inteira (todos os cargos) e grava a execucao. Caminho compartilhado com `emails`."""
    df = load_despesas(Path(zip_path), uf)
    if df.empty:
        raise _Erro(f"Nenhuma despesa encontrada para {uf}.")
    df = classify(df, load_rules())
    return write_run(df, {"uf": uf, "cargo": None, "partido": None, "candidato": None},
                     out_root=Path(saida), caps=caps)


def _parse_teto(valor: str) -> float:
    try:
        t = float(valor)
    except ValueError:
        t = float("nan")
    if not (0 < t <= 1):
        raise _Erro(f"--teto invalido: {valor!r} (fracao entre 0 e 1, ex. 0.10 para 10%)", 2)
    return t


def _emails(args) -> int:
    teto = _parse_teto(args.teto)
    try:
        contatos = load_contatos(Path(args.contatos))
    except ValueError as e:
        raise _Erro(str(e), 2)
    if args.zip and not (Path(args.zip).is_file() and zipfile.is_zipfile(args.zip)):
        raise _Erro(f"--zip inexistente ou ilegivel: {args.zip}", 1)
    zip_path = Path(args.zip) if args.zip else download_candidatos()
    eleitos = load_eleitos(Path(args.eleitos_zip) if args.eleitos_zip else download_resultados())
    saida = Path(args.saida)
    ufs = sorted({u for u in contatos["uf"].str.upper() if re.fullmatch(r"[A-Z]{2}", u) and u != "BR"})
    runs = {}
    for uf in ufs:
        try:
            runs[uf] = rodar_uf(zip_path, uf, saida / "runs", [teto])
        except (_Erro, FileNotFoundError, KeyError) as e:  # UF sem dados: vira pendencia
            print(f"Aviso: {uf} sem analise ({e})", file=sys.stderr)
    out = write_emails(Path(args.contatos), runs, teto, saida, eleitos=eleitos, assinatura=args.assinatura)
    print(f"E-mails gravados em {out / 'emails'}; veja {out / 'pendencias.md'}")
    return 0


def _analisar(args) -> int:
    uf = _parse_uf(args.uf) if args.uf is not None else None  # valida antes de baixar/carregar
    caps = _parse_tetos(args.tetos) if args.tetos is not None else CAPS_PADRAO
    zip_path = Path(args.zip) if args.zip else download_candidatos()
    df = load_despesas(zip_path, uf)
    df = _filtrar(df, args.cargo, args.partido, args.candidato)
    if df.empty:
        raise _Erro("Nenhuma despesa encontrada para o recorte.")
    df = classify(df, load_rules())
    recorte = {"uf": uf, "cargo": args.cargo, "partido": args.partido, "candidato": args.candidato}
    pasta = write_run(df, recorte, out_root=Path(args.saida), caps=caps)
    print(f"Execucao gravada em {pasta}")
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gastos", description="Gasto de campanha com plataformas estrangeiras (TSE).")
    sub = p.add_subparsers(dest="comando", required=True)
    a = sub.add_parser("analisar", help="baixa, classifica e grava o relatorio de um recorte")
    a.add_argument("--uf", help="duas letras (ex. RN) ou BR; padrao: pais")
    a.add_argument("--cargo", help="ex. 'Deputado Federal' (sem distincao de acento/caixa)")
    a.add_argument("--partido", help="sigla, ex. PT")
    a.add_argument("--candidato", help="nome completo ou SQ_CANDIDATO")
    a.add_argument("--tetos", help="tetos percentuais separados por virgula, ex. 0.05,0.10")
    a.add_argument("--zip", help="zip do TSE ja baixado (pula o download)")
    a.add_argument("--saida", default="out", help="pasta de saida (padrao: out)")
    e = sub.add_parser("emails", help="gera um e-mail por contato eleito, com os numeros da UF")
    e.add_argument("--contatos", required=True, help="CSV com nome,cargo,uf,email[,sq_candidato]")
    e.add_argument("--teto", required=True, help="teto proposto como fracao (0.10 = 10%%)")
    e.add_argument("--assinatura", default="[Seu nome]", help="assinatura dos e-mails")
    e.add_argument("--zip", help="zip de despesas do TSE ja baixado")
    e.add_argument("--eleitos-zip", dest="eleitos_zip", help="consulta_cand zip/CSV ja baixado")
    e.add_argument("--saida", default="out", help="pasta de saida (padrao: out)")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:  # argparse sai sozinho em erro/--help
        return e.code if isinstance(e.code, int) else 2
    try:
        return _emails(args) if args.comando == "emails" else _analisar(args)
    except _Erro as e:
        print(f"Erro: {e}", file=sys.stderr)
        return e.codigo
    except FileNotFoundError as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
