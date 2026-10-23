# Metodologia

Como cada despesa vira (ou não) "gasto com plataforma estrangeira", o que o método ainda erra e como conferir um estado novo.

## Fonte e base de cálculo

- Fonte: [dados abertos do TSE](https://dadosabertos.tse.jus.br), conjunto "Prestação de Contas Eleitorais - 2026", arquivo de candidatos (despesas contratadas).
- Base: despesas **contratadas** dos candidatos (as despesas **pagas** entram só na seção da fonte do dinheiro, abaixo). O total de uma campanha é a soma de todas as suas despesas válidas, e é o denominador da proporção.
- Os dados são **parciais**: o arquivo mistura prestações parciais, relatórios financeiros e algumas prestações finais. Os números mudam até a prestação final de todas as campanhas.

## Os níveis

Cada despesa recebe exatamente um nível, na ordem abaixo:

| Nível | Regra | Entra no número principal? |
| --- | --- | --- |
| `confirmado` | o fornecedor ou a descrição nomeia a plataforma (Facebook, Instagram, Google Ads, YouTube, X/Twitter, TikTok…) | sim, e forma o **piso** |
| `generico` | a despesa é de impulsionamento (pela origem da despesa ou pela descrição), sem plataforma nomeada | sim |
| `provavel` | pista fraca, como pagamento a gateway (dLocal, Ebanx) com descrição vaga | **não**; aparece só em nota |
| `nenhum` | o resto | não |

A regra de que **todo impulsionamento conta** como plataforma estrangeira é uma decisão de desenho: não existe rede social nacional para esse tipo de anúncio. Por isso o `generico` entra no número principal. Quem quiser a leitura mais conservadora usa o piso (`confirmado`).

Os fornecedores e as palavras ficam em `config/plataformas.yaml`. Todo texto é comparado sem acento e com **limite de palavra**: "meta" não casa em "método", "x ads" não casa em "maxx ads".

## O que o método ainda erra (conhecido)

Medido com os dados de 22/10/2026; revisado à mão, linha a linha, só no RN:

- **Honorários de agência no `confirmado`.** Pagamentos como "GESTÃO META ADS" são serviço de agência brasileira, não gasto na plataforma. Nacionalmente somam cerca de R$ 3,9 milhões.
- **Impulsionamento embutido em contrato de agência** (jingle, produção de vídeo) cai em `generico`: cerca de R$ 2,7 milhões nacionalmente.
- Esses dois casos (a periferia incerta) somam cerca de R$ 6,7 milhões, perto de 1,5% do principal nacional (R$ 438,3 milhões). Excluir os honorários é uma decisão **em aberto** (veja o [CONTRIBUTING](../CONTRIBUTING.md)).
- Fornecedores como "Google Brasil" não distorcem: o valor pago a eles é pequeno.
- Cerca de R$ 14,6 milhões de linhas `nenhum` mencionam termos de anúncio, quase todas "gestão de tráfego pago" (honorários de agência), que **de propósito não entram** no número.

Proporção do principal sobre o total declarado em 22/10/2026 (por UF, todos os cargos): SP 15,9%, DF 12,2%, PR 12,1%, CE 11,3%, PE 11,0%, RJ 10,1%, RN 4,5%. A Presidência é 10,9% e o nacional, 9,3%. As diferenças entre estados refletem gasto real, não ruído de regra, segundo a revisão.

## Fonte do dinheiro (parte paga com fundos públicos)

O site mostra, por recorte, quanto do valor **já pago** em impulsionamento saiu de fundos públicos. Como é calculado (`gastos publicar`):

1. Do arquivo de despesas **pagas**, soma-se o pago por fonte (`DS_FONTE_DESPESA`): **Fundo Especial de Financiamento de Campanha (FEFC) e Fundo Partidário contam como públicos**; "Outros Recursos" (doações e recursos próprios, que não dá para separar) não contam. Fonte não reconhecida não conta como pública e é avisada na execução.
2. O pago de cada `SQ_DESPESA` é repartido entre as linhas contratadas desse `SQ_DESPESA` **proporcionalmente ao valor contratado**, e só as linhas `confirmado` e `generico` recebem.
3. `pct_publico = pago_publico / pago`. `cobertura_pago = pago / principal` (quanto do contratado já foi pago), **limitada a 1** (aditivos podem fazer o pago passar do contratado).

Ressalvas: é medida sobre o valor **pago**, não sobre o contratado; "Outros Recursos" mistura doações e recursos próprios, então o restante **não** é necessariamente privado; e a parcela varia muito: RN 79%, PB 85%, SP 82%, Presidente 48%. Por isso a frase "dinheiro público" só aparece no site junto com o percentual do recorte e essa ressalva.

## Decisão revogada: deduplicação de linhas idênticas

Em 23/10/2026 a remoção de linhas contratadas idênticas foi **revogada**. A evidência mostrou que são itens reais e separados: no RN, 114 das 121 despesas afetadas têm valor pago igual ao contratado **sem** deduplicar. Hoje nenhuma linha é removida além das de preenchimento. Como proteção, o carregamento avisa se o mesmo `SQ_DESPESA` aparece em mais de um tipo de prestação (nenhum caso no arquivo real).

## Validação por estado (checagem automática)

Em 23/10/2026 conferiu-se, para cada recorte, quanto do principal vem de linhas cuja **origem da despesa** é "Despesa com Impulsionamento de Conteúdos" (campo do próprio TSE, independente das regras de palavras):

- Nacional: **98,5%** do principal (R$ 431,6 milhões de R$ 438,3 milhões).
- **26 dos 28 recortes** (27 UFs mais Brasil) ficam em 95% ou mais; os menores são AC (90,4%) e RR (94,3%).

Isso mostra que o núcleo é sólido, mas **não substitui** a revisão linha a linha, feita só no RN. Hoje a checagem é automática: `gastos validar` (todas as UFs mais Brasil) ou `gastos validar --uf XX` calcula o núcleo (origem "Despesa com Impulsionamento de Conteúdos"), a periferia e as possíveis perdas de cada recorte. Em dados de 22/10/2026 ele reproduz os números acima (principal R$ 438.271.144,99; periferia R$ 6,7 milhões; possíveis perdas R$ 14,6 milhões, em sua maioria serviços de agência deliberadamente não contados). O recorte BR é o de Presidente. Os CSV de linhas (`periferia_*`, `possiveis_perdas_*`) trazem texto livre das despesas (fornecedor e descrição), que pode conter nomes ou números digitados pelas campanhas: revise antes de compartilhar publicamente. As colunas nunca incluem partido, CPF, CNPJ nem nome de candidato.

## Como validar um estado novo

A classificação foi conferida à mão só no RN. Para outro estado:

1. Rode `gastos validar --uf XX` e abra `out/<data>_validacao_uf-XX/validacao.md` (a [checagem automática](#validação-por-estado-checagem-automática)). Se o núcleo ficar abaixo de 95%, ou a periferia ou as possíveis perdas forem grandes, siga os passos abaixo. Rode também `gastos analisar --uf XX` para ter `qualidade.md` e as evidências.
2. Em `validacao.md` e `periferia_XX.csv`, confira se as maiores linhas da periferia são mesmo anúncios em plataforma (e não taxa de agência ou jingle). Em `possiveis_perdas_XX.csv`, veja o que ficou de fora: quase tudo é serviço de agência de propósito, mas um anúncio direto numa plataforma seria erro de regra.
3. Para um achado, abra `evidencia_confirmado.csv` ou `evidencia_generico.csv` e agrupe por fornecedor e por descrição.
4. Se for erro de regra, proponha a mudança em `config/plataformas.yaml` **com as linhas de exemplo e os valores** (veja o [CONTRIBUTING](../CONTRIBUTING.md)). Se for ruído isolado, só registre.
5. Confira o efeito: rode de novo e compare o total antes e depois.

## O que o projeto não faz

- Não julga a legalidade de nenhum gasto: impulsionamento é legal e declarado.
- Não mede gasto de órgãos partidários nem outros tipos de despesa com empresas estrangeiras.
- Não compara o gasto com outras fontes de dinheiro além da parcela paga com fundos públicos descrita acima; o número principal é sobre o gasto total contratado da campanha.
