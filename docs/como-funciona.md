# Como o projeto funciona

Este documento explica a arquitetura e as decisões de desenho, para quem for mexer no código. Para usar os comandos, veja o [guia de uso](uso.md); para a lógica de classificação, a [metodologia](metodologia.md).

## Fluxo de dados

```
TSE (zip, ~209 MB)
  └─ loader.load_despesas(zip, uf)        DataFrame normalizado, sem linhas de preenchimento
       └─ classify.classify(df, regras)   + colunas nivel e plataforma
            └─ metrics.*                  totais, proporção, distribuição, impacto dos tetos
                 └─ report.write_run      pasta datada: relatório, CSVs, evidências, meta.json
                      ├─ emails.write_emails   rascunhos por estado + anexo + pendências
                      └─ story.renderizar      cards 1080×1920 para redes sociais
```

Cada etapa recebe e devolve DataFrames ou arquivos simples. Isso permite trocar o foco (um estado, um cargo, o país) sem mudar o código: o recorte é só um filtro aplicado depois de carregar.

## Módulos (`src/gastos/`)

| Módulo | Responsabilidade |
| --- | --- |
| `fetch.py` | baixa o zip do TSE para `data/raw/` (reaproveita o arquivo se já existir) |
| `loader.py` | lê o CSV de dentro do zip, remove bytes nulos, valida o formato do valor, descarta linhas de preenchimento e linhas totalmente idênticas |
| `text.py` | normalização de texto (minúsculas, sem acento), usada na classificação e no casamento de nomes |
| `classify.py` | aplica as regras de `config/plataformas.yaml` e atribui um nível a cada despesa |
| `metrics.py` | agrega por UF, cargo, partido ou candidato; proporção; distribuição; impacto de tetos; ranking de candidatos |
| `report.py` | grava a pasta da execução (relatório, `qualidade.md`, CSVs, evidências, `meta.json`) |
| `eleitos.py` | baixa e lê a lista de eleitos (`consulta_cand`) e liga contatos a eleitos |
| `emails.py` | gera os rascunhos de e-mail por estado, o anexo de amostra e o `pendencias.md` |
| `links.py` | monta o link da prestação oficial, só para combinações verificadas |
| `story.py` | gera as páginas de story (por candidato e por estado) |
| `cli.py` | comandos `gastos analisar` e `gastos emails` |

## Decisões importantes e por quê

- **Só despesas contratadas, nunca somadas às pagas.** Somar as duas contaria o mesmo gasto duas vezes. O arquivo de despesas pagas serviria só para conferência.
- **Só despesas de candidatos.** Órgãos partidários ficam fora; nenhum texto deve sugerir que cobrem o partido.
- **Deduplicação conservadora.** Só linhas totalmente idênticas são removidas. O mesmo `SQ_DESPESA` aparece em várias linhas legítimas (itens do mesmo documento); remover por esse id sozinho apagaria gasto real (mais de R$ 20 milhões no RN).
- **Número principal = confirmado + genérico.** Todo impulsionamento conta como plataforma estrangeira, porque não há rede social nacional para isso. O `confirmado` é sempre mostrado como piso, e o `provavel` nunca entra no número principal.
- **Regras em YAML, não no código.** Quem não programa consegue ajustar fornecedores e palavras. Todo texto é comparado sem acento e com limite de palavra.
- **Nunca adivinhar.** Links só saem para combinações verificadas; e-mail nunca sai sem números; contato ambíguo vai para pendências.
- **Nada é enviado.** O projeto gera rascunhos.
- **Saídas para Excel brasileiro.** CSVs em UTF-8 com BOM, separador `;` e vírgula decimal.
- **Datas honestas.** A data de geração do arquivo do TSE e a da prestação mais recente vêm dos dados (`meta.json`), nunca da data de hoje.

## Testes

```bash
.venv/bin/pytest -q
```

Os testes não usam rede nem os arquivos grandes: usam dados de exemplo em `tests/fixtures/` e simulam downloads. Todo comportamento novo deve ter um teste que **falha antes** da mudança.

## Histórico do desenho

O desenho original e o plano de implementação estão em [`docs/superpowers/specs/`](superpowers/specs/2026-10-22-gasto-plataformas-estrangeiras-design.md) e [`docs/superpowers/plans/`](superpowers/plans/2026-10-22-gasto-plataformas-estrangeiras.md). O desenho tem um adendo sobre a amostra nominal em anexo nos e-mails.
