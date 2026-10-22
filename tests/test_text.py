from gastos.text import normalize


def test_normalize_acentos_caixa_espacos():
    assert normalize("  Impulsionamento   de CONTEÚDOS\n") == "impulsionamento de conteudos"


def test_normalize_none_e_nan():
    assert normalize(None) == ""
    assert normalize(float("nan")) == ""
