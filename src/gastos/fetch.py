"""Download dos dados abertos de prestacao de contas do TSE."""
from __future__ import annotations

from pathlib import Path

import requests

URL = ("https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/"
       "prestacao_de_contas_eleitorais_candidatos_2026.zip")


def download_candidatos(dest: Path = Path("data/raw")) -> Path:
    """Baixa o zip se ainda nao existir e devolve o caminho."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    alvo = dest / URL.rsplit("/", 1)[-1]
    if alvo.exists():
        return alvo
    parcial = alvo.with_suffix(".part")
    with requests.get(URL, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(parcial, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    parcial.rename(alvo)
    return alvo
