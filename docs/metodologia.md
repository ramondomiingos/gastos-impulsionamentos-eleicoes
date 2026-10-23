# Metodologia

Como cada despesa vira (ou não) "gasto com plataforma estrangeira", o que o método ainda erra e como conferir um estado novo.

## Fonte e base de cálculo

- Fonte: [dados abertos do TSE](https://dadosabertos.tse.jus.br), conjunto "Prestação de Contas Eleitorais - 2026", arquivo de candidatos (despesas contratadas).
- Base: despesas **contratadas** dos candidatos. O total de uma campanha é a soma de todas as suas despesas válidas, e é o denominador da proporção.
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

Medido com os dados de 22/10/2026 e revisado à mão no RN:

- **Honorários de agência no `confirmado`.** Pagamentos como "GESTÃO META ADS" são serviço de agência brasileira, não gasto na plataforma. Nacionalmente somam cerca de R$ 3,9 milhões.
- **Impulsionamento embutido em contrato de agência** (jingle, produção de vídeo) cai em `generico`: cerca de R$ 2,7 milhões nacionalmente.
- Os dois casos juntos inflam o número principal em cerca de **1 ponto percentual** (aproximadamente 4% do principal nacional). Excluir os honorários é uma decisão **em aberto** (veja o [CONTRIBUTING](../CONTRIBUTING.md)).
- Fornecedores como "Google Brasil" não distorcem: o valor pago a eles é pequeno.
- Cerca de 96% do principal nacional vem de pagamentos à Facebook Serviços Online e aos gateways dLocal e Ebanx, com origem "Despesa com Impulsionamento de Conteúdos". Esse núcleo é sólido.

Proporção do principal sobre o total declarado em 22/10/2026 (por UF, todos os cargos): SP 15,8%, DF 12,2%, PR 12,1%, CE 11,5%, PE 11,1%, RJ 10,2%, RN 4,6%. O nacional é 9,3%. As diferenças entre estados refletem gasto real, não ruído de regra, segundo a revisão.

## Como validar um estado novo

A classificação foi conferida à mão só no RN. Para outro estado:

1. Rode `gastos analisar --uf XX` e abra `out/<pasta>/qualidade.md`.
2. Em cada nível, olhe as 10 maiores linhas e confira se são mesmo anúncios em plataforma. Olhe também as 10 maiores linhas de `nenhum`, para achar o que ficou de fora.
3. Para um achado, abra `evidencia_confirmado.csv` ou `evidencia_generico.csv` e agrupe por fornecedor e por descrição.
4. Se for erro de regra, proponha a mudança em `config/plataformas.yaml` **com as linhas de exemplo e os valores** (veja o [CONTRIBUTING](../CONTRIBUTING.md)). Se for ruído isolado, só registre.
5. Confira o efeito: rode de novo e compare o total antes e depois.

## O que o projeto não faz

- Não julga a legalidade de nenhum gasto: impulsionamento é legal e declarado.
- Não mede gasto de órgãos partidários nem outros tipos de despesa com empresas estrangeiras.
- Não compara com outras fontes de dinheiro (fundo eleitoral, doações): o número é sobre o gasto total da campanha.
