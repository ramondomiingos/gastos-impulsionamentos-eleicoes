# Gasto de campanha com plataformas estrangeiras

Mede quanto as campanhas de candidatos gastam com anúncios em plataformas estrangeiras (Meta, Google/YouTube, X, TikTok), a partir dos dados abertos de prestação de contas do TSE (despesas **contratadas** dos candidatos; órgãos partidários ficam fora). O objetivo é embasar um pedido de teto percentual para esse tipo de gasto. Cada número publicado tem um CSV com as linhas que o compõem.

## Instalação

Precisa de Python 3.10 ou superior (o projeto usa 3.12). O `python3` padrão da máquina pode ser o 3.7; nesse caso use um interpretador mais novo para criar o venv:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/gastos --help
```

## Dados

O download é automático: na primeira execução o zip do TSE é salvo em `data/raw/` (cerca de 209 MB) e reaproveitado depois. Para pular o download, passe `--zip caminho.zip`. A lista de eleitos (usada só por `gastos emails`) fica em `data/raw/consulta_cand_2026.zip` e é baixada de novo quando o cache tem mais de 12 h. `data/raw/`, `data/interim/` e `out/` não vão para o git.

## Rodando `gastos analisar`

Sem opções, analisa o país todo. Cada recorte grava uma pasta datada em `out/` (`--saida` muda a pasta).

```bash
gastos analisar --uf RN                                  # um estado
gastos analisar --uf RN --cargo "Deputado Federal"       # estado + cargo (sem distinção de acento/caixa)
gastos analisar --uf RN --partido PT                     # estado + partido
gastos analisar --uf RN --candidato 200002533841         # um candidato (SQ_CANDIDATO ou nome completo)
gastos analisar --uf RN --tetos 0.05,0.10                # tetos testados (padrão: 5%, 10%, 15%, 20%)
gastos analisar                                          # país inteiro
```

(use `.venv/bin/gastos` se o venv não estiver ativo; `--zip` aceita o zip já baixado.) Nome ambíguo é recusado e a mensagem lista os `SQ_CANDIDATO` possíveis.

Exemplo real do RN (dados de 22/10/2026): as duas primeiras linhas acima geram `out/2026-10-22_uf-RN` e `out/2026-10-22_uf-RN_cargo-deputado-federal`.

| recorte | principal (confirmado + genérico) | piso (confirmado) | proporção sobre o total |
| --- | --- | --- | --- |
| RN, todos os cargos | R$ 4.240.709,51 | R$ 2.930.448,25 | 4,6% |
| RN, Deputado Federal | R$ 1.145.454,73 | R$ 707.060,28 | 3,1% |

## O que sai na pasta

| arquivo | conteúdo |
| --- | --- |
| `relatorio.md` | número principal, piso, distribuição entre candidatos, impacto dos tetos, nota sobre o provável |
| `qualidade.md` | totais por nível, valor e linhas por tipo de prestação (Parcial, Relatório Financeiro, Final) e amostras de linhas, para conferir a classificação |
| `resumo.csv` | totais do recorte (total, confirmado, generico, provavel, principal, proporcao, n_candidatos) |
| `candidatos.csv` | os mesmos valores por candidato |
| `tetos.csv` | para cada teto: candidatos acima, % acima e excedente |
| `evidencia_confirmado.csv`, `evidencia_generico.csv`, `evidencia_provavel.csv` | as linhas de despesa que compõem cada nível; a soma de `valor` bate com `resumo.csv` |
| `meta.json` | `dt_geracao` (data em que o TSE gerou o arquivo) e `dt_ultima_prestacao` (prestação mais recente entregue no recorte) |

Os CSVs são escritos para o Excel brasileiro: UTF-8 com BOM (`utf-8-sig`), separador `;` e vírgula decimal.

## Classificação

Cada gasto cai em exatamente um nível:

- `confirmado`: fornecedor ou descrição nomeia a plataforma (ex.: Facebook, Google Ads).
- `generico`: impulsionamento sem plataforma nomeada; todo impulsionamento conta como plataforma estrangeira.
- `provavel`: pista fraca (ex.: gateways de pagamento como dLocal e Ebanx). **Não** entra no número principal; aparece só em nota.
- `nenhum`: o resto.

O número principal é `confirmado + generico`; o `confirmado` aparece sempre como piso. As regras (fornecedores, palavras, gateways) ficam em `config/plataformas.yaml`, comparadas sem acento e com limite de palavra (`meta` não casa em `metodo`). Para ajustar: edite o YAML, rode `analisar` de novo e confira `qualidade.md`.

## E-mails

`gastos emails` gera um rascunho por contato eleito, com os números agregados da UF dele (todos os cargos). Formato do CSV de contatos (veja `contatos.exemplo.csv`, com dados fictícios):

```
nome,cargo,uf,email[,sq_candidato]
```

```bash
gastos emails --contatos contatos.csv --teto 0.10 --assinatura "Seu nome"
```

`--teto` é a fração proposta (0.10 = 10%). O comando liga cada contato à lista de eleitos (por nome, ou por `sq_candidato` quando preenchido), analisa as UFs envolvidas e grava em `out/` (ou `--saida`): `emails/<uf>/*.md`, `indice.csv`, `pendencias.md` (contatos sem correspondência, ambíguos ou UF sem números) e `runs/` com a análise de cada UF. O texto usa só números agregados do estado, informa que os dados são parciais e traz as datas dos dados (gerados pelo TSE em X; prestações mais recentes entregues até Y). O `pendencias.md` traz uma legenda do que fazer em cada motivo (`sem_correspondencia`, `ambiguo`, `sq_diverge`, `duplicado`, `execução ilegível`, `falha ao gerar e-mail`). **O pipeline nunca envia e-mail**: você revisa e envia.

## Limitações

- Os dados são **parciais**: reúnem prestações parciais e relatórios financeiros (algumas campanhas já entregaram a prestação final). `relatorio.md` e os e-mails dizem "dados gerados pelo TSE em X; as prestações de contas mais recentes incluídas foram entregues até Y" (as duas datas também estão em `meta.json`). Os números mudam até a prestação final de todas.
- A classificação foi validada à mão apenas no RN. Em outros estados, olhe `qualidade.md` antes de usar os números.
- Em 22/10/2026 o arquivo de resultados do TSE não tinha totalização de alguns cargos (ex.: senadores e governador da PB; disputas de 2º turno), então esses eleitos podem faltar na lista usada pelo `emails`.
- O CPF vem mascarado; o candidato é identificado por `SQ_CANDIDATO`.
