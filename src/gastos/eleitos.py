"""Lista de eleitos (TSE, consulta_cand) e ligacao com os contatos do Ramon.

Fonte: consulta_cand_2026.zip (arquivo BRASIL), coluna DS_SIT_TOT_TURNO.
Nunca ha casamento aproximado: so nome normalizado exato (legal ou de urna)
+ UF + cargo, ou SQ_CANDIDATO informado no CSV de contatos.
"""
from __future__ import annotations

import io
import logging
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

from gastos.text import normalize

URL = ("https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/"
       "consulta_cand_2026.zip")
MAX_IDADE_HORAS = 12
log = logging.getLogger(__name__)
MEMBRO_BRASIL = "consulta_cand_2026_BRASIL.csv"

# Situacoes de totalizacao que contam como eleito (texto exato do TSE).
SITUACOES_ELEITO = ("ELEITO", "ELEITO POR QP", "ELEITO POR MÉDIA")
# Candidatos a suplente de senador aparecem como "ELEITO" junto com o titular.
CARGOS_EXCLUIDOS = ("1º SUPLENTE", "2º SUPLENTE")

COLUNAS_TSE = ["SQ_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "DS_CARGO",
               "SG_UF", "SG_PARTIDO", "DS_SIT_TOT_TURNO"]
COLUNAS = ["nome", "cargo", "uf", "partido", "sq_candidato", "nome_urna"]

# Texto livre de cargo (normalizado) -> DS_CARGO do TSE.
_CARGOS = {
    "deputado federal": "DEPUTADO FEDERAL",
    "dep federal": "DEPUTADO FEDERAL",
    "deputado estadual": "DEPUTADO ESTADUAL",
    "dep estadual": "DEPUTADO ESTADUAL",
    "deputado distrital": "DEPUTADO DISTRITAL",
    "dep distrital": "DEPUTADO DISTRITAL",
    "senador": "SENADOR",
    "governador": "GOVERNADOR",
    "vice governador": "VICE-GOVERNADOR",
}


def _cache_valido(alvo: Path) -> bool:
    return alvo.exists() and alvo.stat().st_size > 0 and zipfile.is_zipfile(alvo)


def download_resultados(dest: Path = Path("data/raw"), force: bool = False) -> Path:
    """Baixa consulta_cand_2026.zip (candidatos + situacao de totalizacao).

    O cache so vale se for zip valido e tiver menos de MAX_IDADE_HORAS (pelo
    mtime); os resultados mudam apos o 2o turno. `force` ignora o cache.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    alvo = dest / URL.rsplit("/", 1)[-1]
    if not force and _cache_valido(alvo):
        idade_h = (time.time() - alvo.stat().st_mtime) / 3600
        if idade_h < MAX_IDADE_HORAS:
            log.info("Usando cache %s (%.1f h de idade)", alvo, idade_h)
            return alvo
    parcial = alvo.with_suffix(".part")
    with requests.get(URL, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(parcial, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    parcial.replace(alvo)
    return alvo


def _ler_bytes(path: Path) -> bytes:
    path = Path(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            return z.read(MEMBRO_BRASIL)
    return path.read_bytes()


def load_eleitos(path: Path) -> pd.DataFrame:
    """Le zip (arquivo BRASIL) ou CSV e devolve so os eleitos.

    Colunas: nome, cargo, uf, partido, sq_candidato (+ nome_urna).
    Suplentes, nao eleitos, #NULO (sem totalizacao) e "2º TURNO" ficam fora.
    """
    raw = _ler_bytes(path).replace(b"\0", b"").decode("latin-1")
    d = pd.read_csv(io.StringIO(raw), sep=";", dtype=str, keep_default_na=False)
    faltam = [c for c in COLUNAS_TSE if c not in d.columns]
    if faltam:
        raise ValueError(f"Coluna(s) ausente(s) no arquivo do TSE: {', '.join(faltam)}")
    d = d[d["DS_SIT_TOT_TURNO"].str.strip().isin(SITUACOES_ELEITO)]
    d = d[~d["DS_CARGO"].str.strip().isin(CARGOS_EXCLUIDOS)]
    out = pd.DataFrame({
        "nome": d["NM_CANDIDATO"].str.strip(),
        "cargo": d["DS_CARGO"].str.strip(),
        "uf": d["SG_UF"].str.strip().str.upper(),
        "partido": d["SG_PARTIDO"].str.strip(),
        "sq_candidato": d["SQ_CANDIDATO"].str.strip(),
        "nome_urna": d["NM_URNA_CANDIDATO"].str.strip(),
    })
    return out.reset_index(drop=True)[COLUNAS]


def cargo_tse(texto) -> str | None:
    """Mapeia 'Deputada Federal', 'Dep. Estadual', 'Senador' -> DS_CARGO."""
    t = normalize(texto).replace(".", " ").replace("-", " ")
    t = " ".join(t.split())
    for fem, masc in (("deputada", "deputado"), ("senadora", "senador"),
                      ("governadora", "governador")):
        t = t.replace(fem, masc)
    return _CARGOS.get(t)


def match_contatos(contatos: pd.DataFrame, eleitos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Liga contatos a eleitos. Retorna (casados, pendentes).

    Se o contato trouxer `sq_candidato` nao vazio, ele vence o nome, mas uf e
    cargo devem concordar (senao sq_diverge); sq fora dos eleitos vira
    sem_correspondencia. Contato repetido para o mesmo eleito -> duplicado. Senao: nome normalizado
    (legal ou de urna) + uf + cargo. Mais de um candidato distinto -> "ambiguo".
    """
    faltam = [c for c in ("nome", "cargo", "uf") if c not in contatos.columns]
    if faltam:
        raise ValueError(f"Coluna(s) ausente(s) nos contatos: {', '.join(faltam)}")
    indice: dict[tuple[str, str, str], set[str]] = {}
    for r in eleitos.itertuples(index=False):
        for nome in (r.nome, getattr(r, "nome_urna", "")):
            n = normalize(nome)
            if n:
                indice.setdefault((n, str(r.uf).upper(), r.cargo), set()).add(r.sq_candidato)
    por_sq = eleitos.drop_duplicates("sq_candidato").set_index("sq_candidato")

    casados, pendentes, usados = [], [], set()
    for c in contatos.to_dict("records"):
        sq_in = str(c.get("sq_candidato") or "").strip()
        if sq_in.lower() == "nan":
            sq_in = ""
        motivo, sq = None, None
        if sq_in:
            if sq_in in por_sq.index:
                e = por_sq.loc[sq_in]
                uf_c = str(c.get("uf") or "").strip().upper()
                if uf_c == e["uf"] and cargo_tse(c.get("cargo")) == e["cargo"]:
                    sq = sq_in
                else:
                    motivo = "sq_diverge"
            else:
                motivo = "sem_correspondencia"
        else:
            cargo = cargo_tse(c.get("cargo"))
            chave = (normalize(c.get("nome")), str(c.get("uf") or "").strip().upper(), cargo)
            achados = indice.get(chave, set()) if cargo and chave[0] else set()
            if len(achados) == 1:
                sq = next(iter(achados))
            else:
                motivo = "ambiguo" if achados else "sem_correspondencia"
        if sq is not None and sq in usados:
            sq, motivo = None, "duplicado"
        if sq is None:
            pendentes.append({**c, "motivo": motivo})
        else:
            usados.add(sq)
            e = por_sq.loc[sq]
            casados.append({**c, "sq_candidato": sq, "nome_eleito": e["nome"],
                            "cargo_tse": e["cargo"], "uf_eleito": e["uf"],
                            "partido": e["partido"]})
    cols = list(contatos.columns)
    casados_df = pd.DataFrame(casados, columns=list(dict.fromkeys(
        cols + ["sq_candidato", "nome_eleito", "cargo_tse", "uf_eleito", "partido"])))
    pend_df = pd.DataFrame(pendentes, columns=cols + ["motivo"])
    return casados_df, pend_df
