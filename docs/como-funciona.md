# Como o projeto funciona

Este documento explica a arquitetura e as decisões de desenho, para quem for mexer no código. Para usar os comandos, veja o [guia de uso](uso.md); para a lógica de classificação, a [metodologia](metodologia.md).

## Fluxo de dados

```
TSE (zip, ~209 MB)
  └─ loader.load_despesas(zip, uf)        DataFrame normalizado, sem linhas de preenchimento
       └─ classify.classify(df, regras)   + colunas nivel e plataforma
            └─ metrics.*                  totais, proporção, distribuição, impacto dos tetos
                 ├─ report.write_run      pasta datada: relatório, CSVs, evidências, meta.json
                 │    ├─ emails.write_emails   rascunhos por estado + anexo + pendências
                 │    └─ story.renderizar      cards 1080×1920 para redes sociais
                 └─ publicar.publicar     site/data/*.json (+ loader.load_pagamentos: fonte do dinheiro)
                      └─ site/ (HTML + JS) filtros, maiores valores e 5 cards em PNG, no navegador
```

Cada etapa recebe e devolve DataFrames ou arquivos simples. Isso permite trocar o foco (um estado, um cargo, o país) sem mudar o código: o recorte é só um filtro aplicado depois de carregar.

## Módulos (`src/gastos/`)

| Módulo | Responsabilidade |
| --- | --- |
| `fetch.py` | baixa o zip do TSE para `data/raw/` (reaproveita o arquivo se já existir) |
| `loader.py` | lê o CSV de despesas contratadas (e, em `load_pagamentos`, o de despesas pagas) de dentro do zip, remove bytes nulos, valida o formato do valor, descarta linhas de preenchimento (não remove linhas repetidas) e avisa se um `SQ_DESPESA` aparece em mais de um tipo de prestação |
| `text.py` | normalização de texto (minúsculas, sem acento), usada na classificação e no casamento de nomes |
| `classify.py` | aplica as regras de `config/plataformas.yaml` e atribui um nível a cada despesa |
| `metrics.py` | agrega por UF, cargo, partido ou candidato; proporção; distribuição; impacto de tetos; ranking de candidatos |
| `report.py` | grava a pasta da execução (relatório, `qualidade.md`, CSVs, evidências, `meta.json`) |
| `eleitos.py` | baixa e lê a lista de eleitos (`consulta_cand`) e liga contatos a eleitos |
| `emails.py` | gera os rascunhos de e-mail por estado, o anexo de amostra e o `pendencias.md` |
| `links.py` | monta o link da prestação oficial, só para combinações verificadas |
| `publicar.py` | grava os JSON do site: carrega e classifica o país uma vez, reparte o valor pago por `SQ_DESPESA`, monta um recorte por estado e cargo e escolhe os 5 maiores valores |
| `story.py` | gera as páginas de story (por candidato e por estado) |
| `cli.py` | comandos `gastos analisar`, `gastos emails` e `gastos publicar` |

## O site (`site/`)

Estático, sem build nem CDN: `index.html`, `style.css`, `app.js` (interface), `lib.js` (funções puras, testadas com `node --test tests/js/*.test.js`) e `vendor/html2canvas.min.js` para gerar os PNG. O único contrato com o Python é o JSON de `site/data/`, descrito no [desenho do site](superpowers/specs/2026-10-23-site-funcional-design.md). Funcionamento e publicação: [site-e-publicacao.md](site-e-publicacao.md).

## Decisões importantes e por quê

- **Contratadas e pagas nunca se somam.** Somar as duas contaria o mesmo gasto duas vezes. Os números principais vêm só das contratadas; as **pagas** servem para medir a fonte do dinheiro (`gastos publicar`), sempre apresentadas como parcela do valor pago.
- **Só despesas de candidatos.** Órgãos partidários ficam fora; nenhum texto deve sugerir que cobrem o partido.
- **Sem deduplicação de linhas.** Nenhuma linha é removida além das de preenchimento (`SQ_DESPESA` = -1 ou `#NULO`). Linhas contratadas totalmente idênticas são itens reais distintos (por exemplo, o mesmo item contratado duas vezes): nas despesas pagas, o valor pago de cada `SQ_DESPESA` bate com a soma das linhas idênticas, não com uma só. A versão anterior removia essas linhas e subestimava o gasto (no RN, R$ 899.837,43). Como proteção contra dupla contagem, o carregamento emite um aviso se o mesmo `SQ_DESPESA` aparecer em mais de um tipo de prestação (nos dados de 22/10/2026, nenhum).
- **Número principal = confirmado + genérico.** Todo impulsionamento conta como plataforma estrangeira, porque não há rede social nacional para isso. O `confirmado` é sempre mostrado como piso, e o `provavel` nunca entra no número principal.
- **Regras em YAML, não no código.** Quem não programa consegue ajustar fornecedores e palavras. Todo texto é comparado sem acento e com limite de palavra.
- **Nunca adivinhar.** Links só saem para combinações verificadas; e-mail nunca sai sem números; contato ambíguo vai para pendências.
- **Nada é enviado.** O projeto gera rascunhos.
- **Sem partido no site.** O JSON e a página não têm campo de partido; os nomes só aparecem nos 5 maiores valores de cada recorte (um teste guarda isso).
- **Fonte do dinheiro com ressalvas.** Veja a [metodologia](metodologia.md#fonte-do-dinheiro-parte-paga-com-fundos-públicos).
- **Saídas para Excel brasileiro.** CSVs em UTF-8 com BOM, separador `;` e vírgula decimal.
- **Datas honestas.** A data de geração do arquivo do TSE e a da prestação mais recente vêm dos dados (`meta.json`), nunca da data de hoje.

## Testes

```bash
.venv/bin/pytest -q                      # Python
node --test tests/js/*.test.js           # site (a forma com diretório falha no Node 24)
```

Os testes não usam rede nem os arquivos grandes: usam dados de exemplo em `tests/fixtures/` e simulam downloads. Todo comportamento novo deve ter um teste que **falha antes** da mudança.

## Histórico do desenho

O desenho original e o plano de implementação estão em [`docs/superpowers/specs/`](superpowers/specs/2026-10-22-gasto-plataformas-estrangeiras-design.md) e [`docs/superpowers/plans/`](superpowers/plans/2026-10-22-gasto-plataformas-estrangeiras.md). O desenho tem um adendo sobre a amostra nominal em anexo nos e-mails. O site tem desenho e plano próprios: [desenho](superpowers/specs/2026-10-23-site-funcional-design.md) e [plano](superpowers/plans/2026-10-23-site-funcional.md).
