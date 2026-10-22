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


# --- limite de palavra: casos que FALHAM se o limite for removido ---
@pytest.mark.parametrize(
    "fornecedor,descricao",
    [
        ("XPTO ADS LTDA", "Arte"),
        ("AGENCIA", "Servico ADS METAADS"),
        ("MAXX ADS COMUNICACAO", "Arte"),
        ("TWITTERIA PUBLICIDADE LTDA", "Arte"),
        ("METAADS COMUNICACAO LTDA", "Arte"),
        ("AGENCIA", "Campanha TWITTERIA"),
        ("AGENCIA", "Anuncios metaanuncios"),
        ("AGENCIA", "Pacote MAXX ANUNCIOS"),
        ("AGENCIA", "Servico de ytiktok"),
        ("AGENCIA", "Conta googles"),
        # substring das frases fixas do YAML dentro de outra palavra (exigem o limite)
        ("AGENCIA", "Pacote MAXX ADS"),
        ("AGENCIA", "Servico mmeta ads"),
        ("AGENCIA", "Meta adsense"),
        ("AGENCIA", "X ADSENSE"),
        ("XTWITTER LTDA", "Arte"),
        ("AGENCIA", "Maxx anuncios"),
    ],
)
def test_limite_de_palavra_nao_casa_dentro_de_outra_palavra(rules, fornecedor, descricao):
    assert _one(rules, fornecedor=fornecedor, descricao=descricao)[0] == "nenhum"


@pytest.mark.parametrize(
    "descricao,plataforma",
    [
        ("Meta Ads", "meta"),
        ("X Ads", "x"),
        ("pagamento Google Ads", "google"),
        ("Anuncio no YouTube", "google"),
        ("TikTok", "tiktok"),
        ("Twitter", "x"),
    ],
)
def test_frase_inteira_confirmado_por_plataforma(rules, descricao, plataforma):
    assert _one(rules, fornecedor="AGENCIA", descricao=descricao) == ("confirmado", plataforma)


@pytest.mark.parametrize(
    "fornecedor,plataforma",
    [
        ("GOOGLE BRASIL INTERNET LTDA.", "google"),
        ("TIKTOK BRASIL LTDA", "tiktok"),
        ("TWITTER BRASIL REDE DE INFORMACAO LTDA", "x"),
    ],
)
def test_confirmado_por_fornecedor_outras_plataformas(rules, fornecedor, plataforma):
    assert _one(rules, fornecedor=fornecedor, descricao="Servico") == ("confirmado", plataforma)


# --- precedencia ---
def test_confirmado_vence_gateway(rules):
    assert _one(rules, fornecedor="DLOCAL BRASIL INSTITUICAO DE PAGAMENTO S.A.", descricao="Facebook Ads") == (
        "confirmado",
        "meta",
    )


def test_precedencia_confirmado_generico_provavel(rules):
    # confirmado vence generico (origem impulsionamento + gateway + plataforma)
    assert _one(rules, fornecedor="EBANX PAGAMENTOS LTDA", descricao="Instagram", origem=IMPULS) == (
        "confirmado",
        "meta",
    )
    # generico vence provavel (gateway + impulsionamento, sem plataforma)
    assert _one(rules, fornecedor="EBANX PAGAMENTOS LTDA", descricao="Servicos", origem=IMPULS) == (
        "generico",
        "desconhecida",
    )
    assert _one(rules, fornecedor="EBANX PAGAMENTOS LTDA", descricao="impulsionamento") == (
        "generico",
        "desconhecida",
    )
    # so gateway
    assert _one(rules, fornecedor="EBANX PAGAMENTOS LTDA", descricao="Servicos")[0] == "provavel"


# --- validacao do YAML ---
def _write(tmp_path, text):
    p = tmp_path / "r.yaml"
    p.write_text(text, encoding="utf-8")
    return p


VALID = """
plataformas:
  meta:
    fornecedores: [facebook]
    palavras: [facebook]
origem_impulsionamento:
  origens: [Impulsionamento]
  termos_descricao: [impulsionamento]
gateways: [dlocal]
"""


@pytest.mark.parametrize("chave", ["plataformas", "origem_impulsionamento", "gateways"])
def test_yaml_chave_ausente_levanta_valueerror(tmp_path, chave):
    linhas = {
        "plataformas": "plataformas:\n  meta:\n    fornecedores: [facebook]\n    palavras: [facebook]\n",
        "origem_impulsionamento": "origem_impulsionamento:\n  origens: [a]\n  termos_descricao: [b]\n",
        "gateways": "gateways: [dlocal]\n",
    }
    texto = "".join(v for k, v in linhas.items() if k != chave)
    p = _write(tmp_path, texto)
    with pytest.raises(ValueError) as e:
        load_rules(p)
    assert chave in str(e.value) and str(p) in str(e.value)


def test_yaml_lista_nula_levanta_valueerror(tmp_path):
    p = _write(tmp_path, VALID.replace("fornecedores: [facebook]", "fornecedores:"))
    with pytest.raises(ValueError) as e:
        load_rules(p)
    assert "fornecedores" in str(e.value) and str(p) in str(e.value)


def test_yaml_gateways_nulo_levanta_valueerror(tmp_path):
    p = _write(tmp_path, VALID.replace("gateways: [dlocal]", "gateways:"))
    with pytest.raises(ValueError, match="gateways"):
        load_rules(p)


def test_yaml_lista_vazia_valida_nunca_casa(tmp_path):
    p = _write(tmp_path, VALID.replace("gateways: [dlocal]", "gateways: []"))
    r = load_rules(p)
    assert _one(r, fornecedor="DLOCAL BRASIL", descricao="Servicos")[0] == "nenhum"
    assert _one(r, fornecedor="X", descricao="Facebook")[0] == "confirmado"
