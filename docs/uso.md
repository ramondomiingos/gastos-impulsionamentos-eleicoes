# Guia de uso

Referência completa dos comandos. Para uma visão geral do projeto, veja o [README](../README.md).

Mede quanto as campanhas de candidatos gastam com anúncios em plataformas estrangeiras (Meta, Google/YouTube, X, TikTok), a partir dos dados abertos de prestação de contas do TSE (despesas **contratadas** dos candidatos; órgãos partidários ficam fora). O objetivo é embasar um pedido de teto percentual para esse tipo de gasto. Cada número publicado tem um CSV com as linhas que o compõem.

## Instalação

Precisa de Python 3.10 ou superior (o projeto usa 3.12). O `python3` padrão da máquina pode ser o 3.7; nesse caso use um interpretador mais novo para criar o venv:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/gastos --help
```

## Dados

O download é automático: na primeira execução o zip do TSE é salvo em `data/raw/` (cerca de 250 MB em 28/10/2026) e reaproveitado depois, **sem nunca ser baixado de novo**: para atualizar, mova ou apague o zip antigo antes de rodar. Para pular o download, passe `--zip caminho.zip`. O mesmo zip traz as despesas **pagas**, usadas por `gastos publicar` para medir a fonte do dinheiro. A lista de candidatos e eleitos (`consulta_cand`, usada por `gastos emails` e `gastos publicar`) fica em `data/raw/consulta_cand_2026.zip` e é baixada de novo quando o cache tem mais de 12 h. `data/raw/`, `data/interim/` e `out/` não vão para o git.

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

Exemplo real do RN (dados de 28/10/2026): as duas primeiras linhas acima geram `out/2026-10-28_uf-RN` e `out/2026-10-28_uf-RN_cargo-deputado-federal`.

| recorte | principal (confirmado + genérico) | piso (confirmado) | proporção sobre o total |
| --- | --- | --- | --- |
| RN, todos os cargos | R$ 4.399.788,26 | R$ 3.079.527,00 | 4,6% |
| RN, Deputado Federal | R$ 1.256.133,48 | R$ 817.739,03 | 3,3% |

## `gastos publicar`: JSON do site

Grava os arquivos que o [site](site-e-publicacao.md) lê: o país e cada estado, por cargo. Carrega e classifica o arquivo nacional **uma vez** e fatia por estado.

```bash
gastos publicar                              # baixa o que faltar e grava em site/data/
gastos publicar --zip data/raw/<zip> --eleitos-zip data/raw/consulta_cand_2026.zip
gastos publicar --saida /tmp/teste --piso-campanha 100000
```

| opção | efeito |
| --- | --- |
| `--zip` | zip de despesas do TSE já baixado (pula o download) |
| `--eleitos-zip` | zip `consulta_cand` já baixado (pula o download) |
| `--saida` | pasta de saída (padrão `site/data`) |
| `--piso-campanha` | total mínimo da campanha, em R$, para entrar na contagem dos tetos (padrão 50000) |

**Saída:** `index.json` (datas, piso, tetos, lista de UFs e cargos), `BR.json` (só o recorte Presidente) e um `<UF>.json` por estado (recorte `todos` mais um por cargo: governador, senador, deputado federal, estadual e, no DF, distrital). Cada recorte tem total, principal, confirmado, genérico, provável, proporção, contagens, a **fonte do dinheiro** (`pago`, `pago_publico`, `pct_publico`, `cobertura_pago`), o efeito dos tetos e os **5 maiores valores declarados** por nome (sem partido). Formato completo no [desenho do site](superpowers/specs/2026-10-23-site-funcional-design.md#formato-dos-dados-contrato-entre-gastos-publicar-e-o-site).

**Custo:** cerca de 40 s e 2 GB de RAM com os dados nacionais. **Avisos** (stderr): despesas pagas sem linha contratada correspondente (ignoradas) e fontes de despesa não reconhecidas (tratadas como não públicas). Depois de rodar, confira as datas em `site/data/index.json`, rode os testes e faça `commit` e `push`; a Netlify republica.

## `gastos validar`: checagem por estado

Confere a classificação de cada recorte sem scripts avulsos. Sem `--uf`, carrega o arquivo nacional **uma vez** (cerca de 35 s) e fatia por estado, mais o recorte BR (Presidente).

```bash
gastos validar --uf RN                               # um estado, linhas completas
gastos validar --zip data/raw/<zip> --saida /tmp/v   # todos os estados e BR
```

| opção | efeito |
| --- | --- |
| `--uf` | duas letras (ex. RN) ou BR (Presidente); padrão: todas as UFs mais BR |
| `--zip` | zip de despesas do TSE já baixado (pula o download) |
| `--saida` | pasta de saída (padrão `out/<data>_validacao[_uf-XX]`) |

**Saída:** `validacao.md` (tabela por estado ordenada pela periferia, legenda, datas e as 10 maiores linhas de periferia e de possíveis perdas por estado), `validacao.csv` (`;`, vírgula decimal, uma linha por estado) e `periferia_<UF>.csv` e `possiveis_perdas_<UF>.csv`. Com `--uf` os dois últimos trazem todas as linhas; sem `--uf`, as 50 maiores por estado. **Núcleo** é o principal cuja origem no TSE é "Despesa com Impulsionamento de Conteúdos"; **periferia** é o principal fora dela; **possíveis perdas** são linhas `nenhum` com termos de anúncio na descrição (a maioria é serviço de agência deliberadamente não contado). Os CSV de linhas (`periferia_*`, `possiveis_perdas_*`) trazem texto livre das despesas (fornecedor e descrição), que pode conter nomes ou números digitados pelas campanhas: revise antes de compartilhar publicamente. As colunas nunca incluem partido, CPF, CNPJ nem nome de candidato. Erros: UF inválida sai com código 2; zip inexistente ou UF ausente do zip, com 1.

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

`--teto` é a fração proposta (0.10 = 10%). O comando liga cada contato à lista de eleitos (por nome, ou por `sq_candidato` quando preenchido), analisa as UFs envolvidas e grava em `out/` (ou `--saida`): `emails/<uf>/*.md`, `emails/<uf>/amostra-<uf>.csv` (anexo, veja abaixo), `indice.csv` (com a coluna `anexo`), `pendencias.md` (contatos sem correspondência, ambíguos ou UF sem números) e `runs/` com a análise de cada UF. O corpo do texto usa só números agregados do estado (sem nomes de candidatos nem de partidos), informa que os dados são parciais e traz as datas dos dados (gerados pelo TSE em X; prestações mais recentes entregues até Y). O `pendencias.md` traz uma legenda do que fazer em cada motivo (`sem_correspondencia`, `ambiguo`, `sq_diverge`, `duplicado`, `execução ilegível`, `falha ao gerar e-mail`). **O pipeline nunca envia e-mail**: você revisa e envia.

### Anexo: amostra nominal por UF

Cada UF com candidatos elegíveis ganha **um** `emails/<uf>/amostra-<uf>.csv` (UTF-8 com BOM, `;`, vírgula decimal), referenciado pelo nome em todos os e-mails da UF e na coluna `anexo` do `indice.csv`. Colunas: posição, candidato (nome do TSE em caixa de título), cargo, uf, gasto em plataformas (principal), piso confirmado, total da campanha, proporção e link da prestação. **Não há coluna de partido.** O corpo do e-mail continua sem nomes; só o anexo é nominal. A frase do e-mail só promete o link da prestação quando o anexo realmente os traz (todos, alguns ou nenhum: o texto muda) (dados públicos do TSE, prestações parciais).

- **Regra do ranking:** os 5 candidatos da UF com maior proporção (principal ÷ total contratado da campanha), entre os que têm total >= piso e principal > 0. Desempate: maior valor em plataformas, depois menor `sq_candidato`.
- **Piso:** `--piso-amostra` (padrão R$ 50.000, número positivo; inválido sai com código 2). Evita que campanhas minúsculas com proporção absurda dominem a lista.
- **UF sem ninguém acima do piso:** sem anexo, o e-mail omite a frase do anexo e o fato vai para a seção "Avisos" do `pendencias.md`.
- **Destinatário na amostra:** o e-mail é gerado normalmente e o `pendencias.md` (seção "Avisos") nomeia o contato e a UF para você conferir antes de enviar.

**Atenção:** `runs/` (cópia das execuções) contém nomes de candidatos e dados de partido; não anexe essa pasta aos e-mails. Só o `amostra-<uf>.csv` vai em anexo.

### Links da prestação de contas (o que é verificado e o que não é)

O link tem o formato `https://divulgacandcontas.tse.jus.br/divulga/#/candidato/<REGIAO>/<UF>/<ID_ELEICAO>/<SQ_CANDIDATO>/2026/<UF>/prestacao/despesas` (`gastos.links.link_prestacao`). A região vem da UF (IBGE). O `ID_ELEICAO` do portal (ex. `20322002026`) **não é** o `CD_ELEICAO` dos dados abertos (ex. `6259`, que o pipeline já guarda por candidato): a relação só vale se confirmada na API do portal. Por isso o código **nunca adivinha**: só emite o link para combinações (CD_ELEICAO, UF, cargo) listadas em `config/links_verificados.yaml`; as demais saem como `link indisponível` no anexo e entram no `pendencias.md` (seção "Avisos").

Estado atual (22/10/2026): a API do portal respondeu **403 (Access Denied)** ao ambiente em que isto foi desenvolvido, então **nenhuma combinação foi verificada pela API**. A única entrada do YAML é um exemplo real copiado do portal pelo mantenedor (governador do RN, `fonte: exemplo-do-usuario`); ela cobre só esse cargo/UF. Na prática, os links saem `link indisponível` até alguém rodar, de uma rede que o portal aceite:

```bash
.venv/bin/python scripts/verificar_links.py --listar                       # eleicao/ordinarias (ajuda a achar o id)
.venv/bin/python scripts/verificar_links.py --eleicao-id 20322002026 --ufs RN,PB --saida config/links_verificados.yaml
```

O script é **somente leitura** (GET na API pública, com timeout e pausa; para no primeiro 403 sem contornar o bloqueio), testa um candidato por (UF, cargo) e só grava o que responder HTTP 200 com o mesmo `SQ_CANDIDATO` (se a resposta trouxer o id da eleição, ele precisa bater com o testado; se não trouxer, a entrada fica com `fonte: api-sem-conferencia-da-eleicao`). Em 403, erro de rede ou timeout ele para, mas grava o que já coletou, e preserva o cabeçalho do YAML. O endpoint de candidato usado no script (`/divulga/rest/v1/candidatura/buscar/<ano>/<UF>/<id>/candidato/<SQ>`) foi escrito de memória e **não foi testado**; confira a resposta antes de confiar nele. Mesmo verificado pela API, o portal é um app JS: abra alguns links à mão. Os testes não usam rede.

## Stories (imagens para redes sociais)

Gera uma página HTML com 4 cards no formato de story (1080×1920), com botão para baixar cada um em PNG. (O [site](site-e-publicacao.md) já gera 5 cards no navegador, para qualquer estado e cargo, sem rodar nada.) Funciona a partir de uma pasta já gerada por `gastos analisar` e **não** faz parte do comando `gastos` (use `python -m gastos.story`):

```bash
# por candidato (cargo + UF): quem gastou quanto
gastos analisar --uf PI --cargo Governador
python -m gastos.story --run out/<pasta> --uf PI --cargo Governador --saida divulgacao/stories-governador-pi.html

# por estado (todos os cargos, sem nomes): total, por cargo e efeito dos tetos
gastos analisar --uf PB
python -m gastos.story --run out/<pasta> --uf PB --saida divulgacao/stories-estado-pb.html

# nacional (presidente)
gastos analisar --cargo Presidente
python -m gastos.story --run out/<pasta> --uf BR --cargo Presidente --saida divulgacao/stories-presidente-brasil.html
```

Opções: `--eleitos-zip` (padrão `data/raw/consulta_cand_2026.zip`, usado para contar candidatos e 2º turno e para os nomes com acento) e `--site` (endereço do site mostrado no rodapé de todos os cards e em destaque no último; só o host, padrão `radar-impulsionamento.netlify.app`, valores com `http://`, caminho ou espaços encerram com erro). A pasta `divulgacao/` é ignorada pelo git: as páginas geradas citam candidatos pelo nome e não devem ser versionadas sem decisão do mantenedor. Cargos aceitos na versão por candidato: governador, presidente, senador, deputado federal/estadual/distrital.

## Limitações

- Os dados são **parciais**: reúnem prestações parciais e relatórios financeiros (algumas campanhas já entregaram a prestação final). `relatorio.md` e os e-mails dizem "dados gerados pelo TSE em X; as prestações de contas mais recentes incluídas foram entregues até Y" (as duas datas também estão em `meta.json`). Os números mudam até a prestação final de todas.
- A classificação foi validada à mão, linha a linha, apenas no RN. Nos outros estados os números são estimativas (há uma [checagem automática por estado](metodologia.md#validação-por-estado-checagem-automática)); olhe `qualidade.md` antes de usar.
- Desde 28/10/2026 o arquivo de resultados do TSE traz o 2º turno totalizado; quem tem resultado no 2º turno deixa de contar como "em 2º turno" no site e nos stories. Se algum cargo ainda estiver sem totalização, os eleitos dele podem faltar na lista usada pelo `emails`.
- O CPF vem mascarado; o candidato é identificado por `SQ_CANDIDATO`.
