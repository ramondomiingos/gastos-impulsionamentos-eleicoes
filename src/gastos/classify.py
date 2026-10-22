"""Classificacao das despesas em niveis, a partir de regras em YAML."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from gastos.text import normalize

DEFAULT_RULES = Path("config/plataformas.yaml")
DESCONHECIDA = "desconhecida"


@dataclass(frozen=True)
class Rules:
    fornecedores: tuple  # (plataforma, regex)
    palavras: tuple  # (plataforma, regex)
    origens: frozenset  # origens normalizadas
    termos_impulsionamento: re.Pattern
    gateways: re.Pattern


def _alternation(terms) -> re.Pattern:
    """Regex com limite de palavra sobre termos ja normalizados.

    Limite = fora de [a-z0-9]; assim "_" separa palavras ("facebook_direct_br")
    e "meta" continua sem casar em "metodo".
    """
    parts = [re.escape(normalize(t)) for t in terms if normalize(t)]
    if not parts:
        return re.compile(r"(?!x)x")  # nunca casa
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(parts) + r")(?![a-z0-9])")


def load_rules(path: Path = DEFAULT_RULES) -> Rules:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    fornecedores, palavras = [], []
    for plataforma, spec in cfg["plataformas"].items():
        fornecedores.append((plataforma, _alternation(spec.get("fornecedores", []))))
        palavras.append((plataforma, _alternation(spec.get("palavras", []))))
    imp = cfg["origem_impulsionamento"]
    return Rules(
        fornecedores=tuple(fornecedores),
        palavras=tuple(palavras),
        origens=frozenset(normalize(o) for o in imp.get("origens", [])),
        termos_impulsionamento=_alternation(imp.get("termos_descricao", [])),
        gateways=_alternation(cfg.get("gateways", [])),
    )


def _classify_row(fornecedor: str, descricao: str, origem: str, rules: Rules) -> tuple:
    f, d, o = normalize(fornecedor), normalize(descricao), normalize(origem)
    for (plataforma, rf), (_, rd) in zip(rules.fornecedores, rules.palavras):
        if rf.search(f) or rd.search(d):
            return "confirmado", plataforma
    if o in rules.origens or rules.termos_impulsionamento.search(d):
        return "generico", DESCONHECIDA
    if rules.gateways.search(f):
        return "provavel", DESCONHECIDA
    return "nenhum", ""


def classify(df: pd.DataFrame, rules: Rules) -> pd.DataFrame:
    """Devolve copia de df com `nivel` e `plataforma` (um nivel por linha)."""
    out = df.copy()
    pares = [
        _classify_row(f, d, o, rules)
        for f, d, o in zip(out["fornecedor"], out["descricao"], out["origem"])
    ]
    out["nivel"] = [p[0] for p in pares]
    out["plataforma"] = [p[1] for p in pares]
    return out
