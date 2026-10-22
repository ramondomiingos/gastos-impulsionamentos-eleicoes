"""Normalizacao de texto compartilhada (classificacao e casamento de nomes)."""
from __future__ import annotations

import re
import unicodedata


def normalize(s) -> str:
    """Minusculas, sem acentos, espacos colapsados. None/NaN viram ''."""
    if s is None or (isinstance(s, float) and s != s):
        return ""
    decomposed = unicodedata.normalize("NFKD", str(s))
    sem_acento = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()
