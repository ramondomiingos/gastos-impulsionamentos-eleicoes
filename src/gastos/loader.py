"""Leitor normalizado das despesas contratadas dos candidatos (TSE)."""
from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd

# coluna bruta do TSE -> coluna normalizada
COLUNAS = {
    "SG_UF": "uf",
    "SQ_CANDIDATO": "sq_candidato",
    "NM_CANDIDATO": "candidato",
    "DS_CARGO": "cargo",
    "SG_PARTIDO": "partido",
    "NM_FORNECEDOR_RFB": "fornecedor",
    "NR_CPF_CNPJ_FORNECEDOR": "cnpj_fornecedor",
    "DS_DESPESA": "descricao",
    "DS_ORIGEM_DESPESA": "origem",
    "VR_DESPESA_CONTRATADA": "valor",
    "DT_DESPESA": "data",
    "SQ_DESPESA": "sq_despesa",
    "DT_GERACAO": "dt_geracao",
    "TP_PRESTACAO_CONTAS": "tp_prestacao",
    "DT_PRESTACAO_CONTAS": "dt_prestacao",
}
PLACEHOLDERS = {"-1", "#NULO"}

csv.field_size_limit(10**7)


def clean_lines(lines: Iterable[str]) -> Iterator[str]:
    """Remove bytes nulos (o arquivo BRASIL do TSE traz alguns)."""
    for line in lines:
        yield line.replace("\0", "")


def _member(names: list[str], uf: str | None) -> str:
    sufixo = "BRASIL" if uf is None else uf.upper()
    alvo = f"despesas_contratadas_candidatos_2026_{sufixo}.csv"
    for name in names:
        if name.rsplit("/", 1)[-1].lower() == alvo.lower():
            return name
    ufs = sorted({m.group(1) for n in names
                  if (m := re.fullmatch(r"despesas_contratadas_candidatos_2026_([A-Za-z]{2})\.csv",
                                        n.rsplit("/", 1)[-1]))})
    if uf is not None and ufs:
        raise FileNotFoundError(
            f"UF {uf.upper()} nao encontrada no zip. UFs disponiveis: {', '.join(u.upper() for u in ufs)} "
            f"(ou BR para o pais)")
    raise FileNotFoundError(f"{alvo} nao encontrado no zip")


_VALOR_RE = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}$|^-?\d+,\d{2}$")


def parse_valor(texto: str) -> float:
    """Converte valor no formato TSE ("1.234,50"); outro formato e erro."""
    texto = texto.strip()
    if not texto or texto in PLACEHOLDERS:
        return 0.0
    if not _VALOR_RE.match(texto):
        raise ValueError(f"valor fora do formato TSE: {texto!r}")
    return float(texto.replace(".", "").replace(",", "."))


def load_despesas(zip_path: Path, uf: str | None = None) -> pd.DataFrame:
    """Le as despesas contratadas; uf=None le o arquivo BRASIL.

    Le em fluxo, guardando so as colunas necessarias, descarta linhas de
    preenchimento (SQ_DESPESA == "-1" / "#NULO") e remove apenas linhas
    totalmente identicas (todas as colunas normalizadas).
    """
    with zipfile.ZipFile(zip_path) as z:
        nome = _member(z.namelist(), uf)
        with z.open(nome) as raw:
            texto = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            reader = csv.reader(clean_lines(texto), delimiter=";", quotechar='"')
            header = next(reader)
            idx = [header.index(c) for c in COLUNAS]
            i_sq = header.index("SQ_DESPESA")
            linhas = []
            for row in reader:
                if len(row) <= max(idx):
                    continue
                sq = row[i_sq].strip()
                if sq in PLACEHOLDERS:
                    continue
                linhas.append([row[i] for i in idx])
    df = pd.DataFrame(linhas, columns=list(COLUNAS.values()), dtype=str)
    df["valor"] = df["valor"].map(parse_valor).astype(float)
    # So linhas totalmente identicas colapsam: um SQ_DESPESA repetido com
    # descricao/valor diferentes sao itens do mesmo documento, nao duplicata.
    return df.drop_duplicates().reset_index(drop=True)
