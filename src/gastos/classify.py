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


def _lista(valor, caminho, onde) -> list:
    """Lista de termos; None (chave sem valor) ou tipo errado e erro. [] e valido."""
    if not isinstance(valor, list):
        raise ValueError(f"{caminho}: '{onde}' deve ser uma lista (use [] para vazio)")
    return valor


def _secao(cfg, chave, caminho):
    if not isinstance(cfg, dict) or chave not in cfg or cfg[chave] is None:
        raise ValueError(f"{caminho}: chave obrigatoria ausente ou vazia: '{chave}'")
    return cfg[chave]


def load_rules(path: Path = DEFAULT_RULES) -> Rules:
    caminho = Path(path)
    cfg = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    plataformas = _secao(cfg, "plataformas", caminho)
    imp = _secao(cfg, "origem_impulsionamento", caminho)
    gateways = _lista(cfg.get("gateways"), caminho, "gateways") if "gateways" in cfg else None
    if gateways is None:
        raise ValueError(f"{caminho}: chave obrigatoria ausente ou vazia: 'gateways'")
    if not isinstance(plataformas, dict):
        raise ValueError(f"{caminho}: 'plataformas' deve ser um mapa plataforma -> regras")
    fornecedores, palavras = [], []
    for plataforma, spec in plataformas.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{caminho}: plataforma '{plataforma}' deve ser um mapa")
        for campo, destino in (("fornecedores", fornecedores), ("palavras", palavras)):
            termos = _lista(spec.get(campo), caminho, f"plataformas.{plataforma}.{campo}")
            destino.append((plataforma, _alternation(termos)))
    origens = _lista(imp.get("origens"), caminho, "origem_impulsionamento.origens")
    termos = _lista(imp.get("termos_descricao"), caminho, "origem_impulsionamento.termos_descricao")
    return Rules(
        fornecedores=tuple(fornecedores),
        palavras=tuple(palavras),
        origens=frozenset(normalize(o) for o in origens),
        termos_impulsionamento=_alternation(termos),
        gateways=_alternation(gateways),
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
