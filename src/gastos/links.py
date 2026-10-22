"""Links da prestacao de contas oficial (DivulgaCandContas, TSE).

Formato: https://divulgacandcontas.tse.jus.br/divulga/#/candidato/<REGIAO>/<UF>/<ID_ELEICAO>/<SQ>/<ano>/<UF>/prestacao/despesas

O `id_eleicao` do portal (ex. 20322002026) NAO e o `CD_ELEICAO` dos dados abertos (ex. 6259): a relacao so
vale se confirmada na API do portal. Por isso o link so e emitido para combinacoes (CD_ELEICAO, UF, cargo)
listadas em `config/links_verificados.yaml`; as demais saem como "link indisponivel" (nunca um palpite).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from gastos.eleitos import cargo_tse

BASE = "https://divulgacandcontas.tse.jus.br/divulga/#/candidato"
INDISPONIVEL = "link indisponível"
CONFIG = Path(__file__).resolve().parents[2] / "config" / "links_verificados.yaml"

REGIOES = {
    **dict.fromkeys(["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "NORTE"),
    **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "NORDESTE"),
    **dict.fromkeys(["ES", "MG", "RJ", "SP"], "SUDESTE"),
    **dict.fromkeys(["PR", "RS", "SC"], "SUL"),
    **dict.fromkeys(["DF", "GO", "MS", "MT"], "CENTRO-OESTE"),
}


def link_prestacao(uf: str, sq_candidato: str, id_eleicao: str, ano: int = 2026) -> str:
    """Monta o link das despesas do candidato. ValueError para UF (nao BR) ou ids invalidos."""
    uf_n = str(uf).strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", uf_n) or uf_n not in REGIOES:
        raise ValueError(f"uf invalida: {uf!r} (candidaturas nacionais nao tem formato verificado)")
    sq, eid = str(sq_candidato).strip(), str(id_eleicao).strip()
    if not sq.isascii() or not sq.isdigit():
        raise ValueError(f"sq_candidato invalido: {sq_candidato!r}")
    if not eid.isascii() or not eid.isdigit():
        raise ValueError(f"id_eleicao invalido: {id_eleicao!r}")
    return f"{BASE}/{REGIOES[uf_n]}/{uf_n}/{eid}/{sq}/{int(ano)}/{uf_n}/prestacao/despesas"


def carregar_verificados(path: Path = CONFIG) -> dict[tuple[str, str, str], str]:
    """Le o YAML de mapeamentos verificados: {(cd_eleicao, uf, CARGO): id_eleicao}. Ausente = vazio."""
    path = Path(path)
    if not path.is_file():
        return {}
    dados = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {}
    for e in dados.get("verificados") or []:
        try:
            chave = (str(e["cd_eleicao"]).strip(), str(e["uf"]).strip().upper(), str(e["cargo"]).strip().upper())
            eid = str(e["id_eleicao"]).strip()
        except (KeyError, TypeError, AttributeError) as err:
            raise ValueError(f"entrada invalida em {path}: {e!r}") from err
        link_prestacao(chave[1], "1", eid)  # valida uf e id
        out[chave] = eid
    return out


def link_ou_indisponivel(uf, sq_candidato, cargo, cd_eleicao, verificados: dict) -> str:
    """Link verificado, ou o texto "link indisponivel" quando a combinacao nao foi verificada."""
    cargo_n = cargo_tse(cargo) or str(cargo or "").strip().upper()
    chave = (str(cd_eleicao or "").strip(), str(uf or "").strip().upper(), cargo_n)
    eid = verificados.get(chave)
    if not eid:
        return INDISPONIVEL
    try:
        return link_prestacao(chave[1], sq_candidato, eid)
    except ValueError:
        return INDISPONIVEL
