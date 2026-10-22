import pandas as pd
import pytest

from gastos.classify import classify, load_rules

IMPULS = "Despesa com Impulsionamento de Conteúdos"


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def _row(fornecedor="", descricao="", origem="Outros"):
    return {"fornecedor": fornecedor, "descricao": descricao, "origem": origem}


def _one(rules, **kw):
    out = classify(pd.DataFrame([_row(**kw)]), rules)
    return out.iloc[0]["nivel"], out.iloc[0]["plataforma"]


def test_confirmado_por_fornecedor(rules):
    assert _one(rules, fornecedor="FACEBOOK SERVICOS ONLINE DO BRASIL LTDA.") == ("confirmado", "meta")


def test_confirmado_por_descricao_via_gateway(rules):
    assert _one(
        rules,
        fornecedor="DLOCAL BRASIL INSTITUICAO DE PAGAMENTO S.A.",
        descricao="Impulsionamento Facebook",
    ) == ("confirmado", "meta")


def test_generico(rules):
    assert _one(
        rules, fornecedor="QUALQUER LTDA", descricao="IMPULSIONAMENTO DE CONTEUDOS", origem=IMPULS
    ) == ("generico", "desconhecida")


def test_provavel_gateway_descricao_vaga(rules):
    nivel, _ = _one(rules, fornecedor="EBANX PAGAMENTOS LTDA", descricao="Serviços")
    assert nivel == "provavel"


def test_falso_positivo_metodo(rules):
    assert _one(rules, fornecedor="METODO PROJETOS E SERVICOS LTDA", descricao="Material gráfico")[0] == "nenhum"


def test_falso_positivo_palavras_curtas(rules):
    assert _one(rules, fornecedor="METALURGICA SILVA LTDA", descricao="Relatório X de gestão")[0] == "nenhum"
    assert _one(rules, fornecedor="GOOGLEMANIA PUBLICIDADE LTDA", descricao="Arte")[0] == "nenhum"


def test_agencia_nao_e_plataforma(rules):
    assert _one(rules, fornecedor="KEYMAP COMUNICACAO E PRODUCAO LTDA", descricao="Produção de vídeo")[0] == "nenhum"


def test_acentos_e_caixa(rules):
    a = _one(rules, descricao="Impulsionamento de Conteúdo")
    b = _one(rules, descricao="IMPULSIONAMENTO DE CONTEUDO")
    assert a == b
    assert a[0] == "generico"


def test_each_row_exactly_one_level(rules):
    df = pd.DataFrame(
        [
            _row("FACEBOOK SERVICOS ONLINE DO BRASIL LTDA."),
            _row("X", "IMPULSIONAMENTO DE CONTEUDOS", IMPULS),
            _row("EBANX PAGAMENTOS LTDA", "Serviços"),
            _row("Y", "Material"),
        ]
    )
    out = classify(df, rules)
    assert len(out) == len(df)
    assert out["nivel"].isin(["confirmado", "generico", "provavel", "nenhum"]).all()
    assert list(out["nivel"]) == ["confirmado", "generico", "provavel", "nenhum"]
    assert "nivel" not in df.columns  # nao muta a entrada


def test_underscore_separa_palavras(rules):
    # caso real do RN: "Facebook_Direct_BR" via gateway
    assert _one(rules, fornecedor="DLOCAL BRASIL INSTITUICAO DE PAGAMENTO S.A.", descricao="Facebook_Direct_BR") == (
        "confirmado",
        "meta",
    )
