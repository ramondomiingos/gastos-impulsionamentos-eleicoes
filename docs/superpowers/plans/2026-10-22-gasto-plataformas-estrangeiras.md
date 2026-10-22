# Gasto com Plataformas Estrangeiras: Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pipeline em linha de comando que mede o gasto de campanhas com plataformas de anúncio estrangeiras a partir dos dados abertos do TSE, para qualquer recorte (UF, cargo, partido, candidato), e gera e-mails estaduais para parlamentares eleitos.

**Architecture:** Módulos pequenos em cadeia: `loader` (CSV do TSE para DataFrame normalizado) → `classify` (regras em YAML, três níveis) → `metrics` (totais, proporção, distribuição, impacto de tetos) → `evidence`/`report` (CSVs rastreáveis e relatório) → `emails` (modelos preenchidos por UF). Uma CLI (`gastos`) orquestra e salva cada execução numa pasta datada.

**Tech Stack:** Python 3.12 (`/opt/homebrew/bin/python3.12`; o `python3` padrão é 3.7 e não serve), pandas, PyYAML, Jinja2, pytest, requests. Venv em `.venv/`.

**Spec:** `docs/superpowers/specs/2026-10-22-gasto-plataformas-estrangeiras-design.md`

## Global Constraints

- Fonte: dados abertos do TSE, `https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2026.zip`. Não raspar o site de divulgação.
- CSV: separador `;`, encoding latin-1, decimal com vírgula. Remover bytes nulos ao ler (o arquivo BRASIL tem 2).
- Descartar linhas de preenchimento: `SQ_DESPESA == "-1"` (e `#NULO`).
- Base de cálculo: despesas **contratadas** (`VR_DESPESA_CONTRATADA`). Nunca somar contratadas com pagas.
- Só despesas de candidatos. Órgãos partidários ficam fora; o texto não pode sugerir que cobrem o partido.
- Só plataformas de anúncio estrangeiras (Meta, Google/YouTube, X, TikTok). Todo "impulsionamento" conta como plataforma estrangeira.
- Três níveis, cada gasto em exatamente um: `confirmado`, `generico`, `provavel` (mais `nenhum` para o resto). Número principal = confirmado + generico; confirmado aparece sempre como piso; `provavel` só em nota.
- Regras de classificação em arquivo de configuração (palavras e fornecedores), nunca no código.
- Identificador do candidato: `SQ_CANDIDATO` (CPF vem mascarado).
- Os dados são **parciais**. Todo texto de e-mail diz isso e traz a data de corte (`DT_GERACAO` dos dados).
- E-mails: só números do estado e do cargo (agregado). Não citam campanha, partido ou gasto do destinatário. Não dizem "dinheiro público". Não acusam. Tom sóbrio, em português.
- Pedido do e-mail: **teto percentual** do gasto de campanha com plataformas estrangeiras, mais convite ao parlamentar para ajudar. O percentual proposto é parâmetro, não valor fixo no código.
- Cada número publicado tem um CSV com as linhas que o compõem.
- Cada execução salva uma versão datada em `out/AAAA-MM-DD_<recorte>/`.
- `data/raw/`, `data/interim/` e `out/` fora do git (`.gitignore` já cobre `data/raw/` e `data/interim/`; adicionar `out/`).
- O pipeline não envia e-mail. O Ramon revisa e envia.
- O Ramon fornece os contatos em CSV com colunas `nome,cargo,uf,email`.

## Review Focus

1. Candidato com gasto total 0 ou sem nenhuma linha válida: a proporção não pode dar divisão por zero nem NaN no relatório; o candidato aparece com proporção 0 ou fica fora, de forma documentada.
2. Falsos positivos de palavras curtas ("Meta", "X", "Google" em nomes de agências): `Metodo Projetos`, `Metalúrgica`, "relatório X" não podem virar plataforma. Regras com limite de palavra.
3. Acentos e caixa nas descrições (`CONTEÚDOS`, `Conteudos`, `conteúdo`): a classificação não pode depender deles.
4. Mesmo `SQ_DESPESA` repetido (parcelamento): não pode contar duas vezes.
5. Parlamentar eleito sem correspondência nos dados, UF sem nenhum gasto classificado, ou nome ambíguo na lista de contatos: nunca gerar e-mail com número inventado ou vazio; listar em relatório de pendências.

---

### Task 1: Scaffold, download e leitor normalizado

**Files:**
- Create: `pyproject.toml`, `src/gastos/__init__.py`, `src/gastos/fetch.py`, `src/gastos/loader.py`
- Create: `tests/conftest.py`, `tests/fixtures/despesas_contratadas_2026_XX.csv`, `tests/test_loader.py`
- Modify: `.gitignore` (adicionar `out/`)

**Interfaces:**
- Produces: `fetch.download_candidatos(dest: Path = Path("data/raw")) -> Path` (baixa o zip se ainda não existir, retorna o caminho).
- Produces: `loader.load_despesas(zip_path: Path, uf: str | None = None) -> pd.DataFrame`. `uf=None` lê o arquivo BRASIL. Colunas do retorno: `uf, sq_candidato, candidato, cargo, partido, fornecedor, cnpj_fornecedor, descricao, origem, valor (float), data, sq_despesa, dt_geracao, tp_prestacao`. Já sem linhas de preenchimento e sem `sq_despesa` repetido.
- Produces: `loader.clean_lines(lines: Iterable[str]) -> Iterator[str]` (remove `\0`).

- [ ] **Step 1: Criar o venv e o `pyproject.toml`**

Run: `/opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
Expected: instalação sem erro. `pyproject.toml` declara pandas, pyyaml, jinja2, requests; dev: pytest. Entry point `gastos = gastos.cli:main` (o módulo vem na Task 6).

- [ ] **Step 2: Escrever os testes do leitor (falham)**

Fixture CSV pequeno (latin-1, `;`, aspas) com: 1 despesa real do RN, 1 linha de preenchimento (`SQ_DESPESA=-1`), 1 `SQ_DESPESA` repetido e uma linha com byte nulo. `tests/test_loader.py`:
- `test_drops_placeholder_rows`: nenhuma linha com `sq_despesa == "-1"`.
- `test_dedupes_sq_despesa`: o id repetido aparece uma vez (Review Focus 4).
- `test_parses_decimal_comma`: `"2500,00"` vira `2500.0`.
- `test_strips_nul_bytes`: o arquivo com `\0` é lido sem `csv.Error`.
- `test_uf_none_reads_brasil`: com zip de teste contendo `..._BRASIL.csv`, `uf=None` lê esse arquivo; `uf="RN"` lê só o do RN.

- [ ] **Step 3: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_loader.py -v`
Expected: FAIL (`ModuleNotFoundError: gastos.loader`).

- [ ] **Step 4: Implementar `loader.py` e `fetch.py`**

Ler o CSV de dentro do zip com `zipfile`, `clean_lines` e `pandas.read_csv(sep=";", dtype=str, encoding="latin-1")` (ou `csv.DictReader` se pandas não aceitar o iterador). Converter `valor` com troca de `.`/`,`. Dedupe por `sq_despesa` mantendo a primeira.

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_loader.py -v`
Expected: 5 passed.

- [ ] **Step 6: Conferir com os dados reais do RN**

Run: `.venv/bin/python -c "from gastos.fetch import download_candidatos; from gastos.loader import load_despesas; d=load_despesas(download_candidatos(), 'RN'); print(len(d), d.sq_candidato.nunique(), round(d.valor.sum(),2))"`
Expected: 244 candidatos. Anotar o total e as linhas removidas por dedupe no commit (antes da dedupe eram 15.103 linhas reais e R$ 93.539.994,51).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore src tests
git commit -m "feat: loader normalizado dos dados do TSE"
```

---

### Task 2: Classificação em três níveis

**Files:**
- Create: `config/plataformas.yaml`, `src/gastos/classify.py`, `tests/test_classify.py`

**Interfaces:**
- Consumes: DataFrame do `load_despesas`.
- Produces: `classify.load_rules(path: Path = Path("config/plataformas.yaml")) -> Rules`.
- Produces: `classify.classify(df: pd.DataFrame, rules: Rules) -> pd.DataFrame`. Acrescenta `nivel` (`confirmado|generico|provavel|nenhum`) e `plataforma` (`meta|google|x|tiktok|desconhecida|""`).

- [ ] **Step 1: Escrever os testes (falham)**

Casos reais do RN, cada um em uma linha de DataFrame:
- `test_confirmado_por_fornecedor`: fornecedor `FACEBOOK SERVICOS ONLINE DO BRASIL LTDA.` → `confirmado`, `meta`.
- `test_confirmado_por_descricao_via_gateway`: fornecedor `DLOCAL BRASIL INSTITUICAO DE PAGAMENTO S.A.` com descrição `Impulsionamento Facebook` → `confirmado`, `meta`.
- `test_generico`: origem `Despesa com Impulsionamento de Conteúdos`, descrição `IMPULSIONAMENTO DE CONTEUDOS`, fornecedor qualquer → `generico`, `desconhecida`.
- `test_provavel_gateway_descricao_vaga`: fornecedor `EBANX PAGAMENTOS LTDA`, descrição `Serviços` e origem não é impulsionamento → `provavel`.
- `test_falso_positivo_metodo`: fornecedor `METODO PROJETOS E SERVICOS LTDA`, descrição `Material gráfico` → `nenhum` (Review Focus 2).
- `test_agencia_nao_e_plataforma`: fornecedor `KEYMAP COMUNICACAO E PRODUCAO LTDA`, descrição `Produção de vídeo` → `nenhum`.
- `test_acentos_e_caixa`: `Impulsionamento de Conteúdo` e `IMPULSIONAMENTO DE CONTEUDO` dão o mesmo nível (Review Focus 3).
- `test_each_row_exactly_one_level`: o resultado tem um único valor de `nivel` por linha.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_classify.py -v`
Expected: FAIL.

- [ ] **Step 3: Escrever `config/plataformas.yaml`**

Seções: `plataformas` (para cada uma: `fornecedores` por nome RFB, `palavras` com limite de palavra, exemplos: Meta → facebook, instagram, "meta ads", "meta anuncios"; Google → google, youtube; X → twitter, "x ads"; TikTok → tiktok), `origem_impulsionamento` (valores de `DS_ORIGEM_DESPESA` e termos de descrição que indicam impulsionamento), `gateways` (DLOCAL, EBANX). Palavras curtas como `meta` e `x` só valem como palavra inteira ou em frases fixas.

- [ ] **Step 4: Implementar `classify.py`**

Normalizar texto (minúsculas, sem acento) e aplicar na ordem: confirmado (fornecedor ou descrição cita plataforma) → generico (origem/descrição de impulsionamento sem plataforma) → provavel (gateway sem os anteriores) → nenhum. Regex compiladas das regras do YAML.

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_classify.py -v`
Expected: 8 passed.

- [ ] **Step 6: Validar nos dados reais do RN e ajustar as regras**

Rodar a classificação no RN e listar, por nível, o top 15 de pares (fornecedor, descrição) e a soma. Revisar a amostra de `nenhum` com valor alto e de `generico`/`provavel` e corrigir `plataformas.yaml` se houver falso positivo ou perda. Registrar os totais por nível no commit.

- [ ] **Step 7: Commit**

```bash
git add config src/gastos/classify.py tests/test_classify.py
git commit -m "feat: classificação em três níveis com regras em YAML"
```

---

### Task 3: Métricas, proporção e impacto de tetos

**Files:**
- Create: `src/gastos/metrics.py`, `tests/test_metrics.py`

**Interfaces:**
- Consumes: DataFrame com `nivel` (saída de `classify.classify`).
- Produces: `metrics.summarize(df: pd.DataFrame, by: list[str]) -> pd.DataFrame` com colunas: as de `by`, `total`, `confirmado`, `generico`, `provavel`, `principal` (= confirmado + generico), `proporcao` (= principal ÷ total, 0 se total = 0), `n_candidatos`.
- Produces: `metrics.candidate_shares(df) -> pd.DataFrame` (uma linha por `sq_candidato` com `total`, `principal`, `proporcao`).
- Produces: `metrics.cap_impact(shares: pd.DataFrame, caps: list[float]) -> pd.DataFrame` com, para cada teto: `n_acima` (candidatos com proporção acima do teto), `pct_acima`, `excedente` (soma do que passa do teto: `principal − teto × total`, só dos que passam).
- Produces: `metrics.distribution(shares) -> dict` com `mediana`, `p75`, `p90`, `max`.

- [ ] **Step 1: Escrever os testes (falham)**

Em um DataFrame pequeno e feito à mão:
- `test_principal_is_confirmado_plus_generico`.
- `test_proporcao_zero_total`: candidato com total 0 → `proporcao == 0.0`, sem NaN (Review Focus 1).
- `test_provavel_not_in_principal`.
- `test_summarize_by_uf_cargo_partido_candidato`: cada chave de agrupamento funciona e a soma dos grupos é igual ao total geral.
- `test_cap_impact`: com 3 candidatos de proporção 0.02, 0.08 e 0.30 e tetos `[0.05, 0.10]`, os valores de `n_acima` são 2 e 1, e `excedente` bate com a conta manual.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_metrics.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `metrics.py`**

`groupby` com somas condicionais por nível; `proporcao` com tratamento de zero.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_metrics.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/gastos/metrics.py tests/test_metrics.py
git commit -m "feat: métricas, distribuição e impacto de tetos"
```

---

### Task 4: Evidência rastreável e relatório

**Files:**
- Create: `src/gastos/report.py`, `tests/test_report.py`

**Interfaces:**
- Consumes: saídas das Tasks 2 e 3.
- Produces: `report.write_run(df: pd.DataFrame, recorte: dict, out_root: Path = Path("out"), caps: list[float] = [0.05, 0.10, 0.15, 0.20]) -> Path`. Cria `out/AAAA-MM-DD_<recorte>/` e retorna o caminho. Conteúdo: `evidencia_confirmado.csv`, `evidencia_generico.csv`, `evidencia_provavel.csv` (linhas completas), `resumo.csv` (de `summarize`), `candidatos.csv` (de `candidate_shares`), `tetos.csv` (de `cap_impact`), `qualidade.md` e `relatorio.md`.
- `recorte` é um dict como `{"uf": "RN", "cargo": None, "partido": None, "candidato": None}`; `<recorte>` no nome da pasta usa só as chaves preenchidas.

- [ ] **Step 1: Escrever os testes (falham)**

- `test_evidence_sums_match_summary`: a soma de `valor` em `evidencia_confirmado.csv` + `evidencia_generico.csv` é igual a `principal` do `resumo.csv` (cada número é conferível).
- `test_qualidade_lists_level_totals_and_sample`: `qualidade.md` traz o total por nível e uma amostra de linhas por nível.
- `test_relatorio_states_partial_data_and_cutoff`: `relatorio.md` contém "parcial" e a data de corte vinda de `dt_geracao`.
- `test_run_folder_is_dated_and_versioned`: duas execuções em dias diferentes criam duas pastas.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_report.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `report.py`**

Escrever os CSVs com pandas e os Markdown com Jinja2 ou f-strings. Usar a data de hoje para o nome da pasta (parâmetro `today` com padrão `date.today()` para facilitar o teste).

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_report.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/gastos/report.py tests/test_report.py
git commit -m "feat: evidência rastreável e relatório por execução"
```

---

### Task 5: CLI de análise com recortes

**Files:**
- Create: `src/gastos/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `cli.main(argv: list[str] | None = None) -> int` com subcomando `analisar` e opções `--uf`, `--cargo`, `--partido`, `--candidato` (nome ou `SQ_CANDIDATO`), `--tetos 0.05,0.10`. Sem nenhuma opção, roda o país (BRASIL). Faz: baixa se preciso → carrega → filtra → classifica → `report.write_run`.
- Consumes: `fetch.download_candidatos`, `loader.load_despesas`, `classify`, `report.write_run`.

- [ ] **Step 1: Escrever os testes (falham)**

Com o zip de teste da Task 1 (monkeypatch em `download_candidatos`):
- `test_analisar_uf_creates_run_folder`: `main(["analisar","--uf","RN"])` retorna 0 e cria a pasta com `relatorio.md`.
- `test_filters_by_cargo_partido_candidato`: cada filtro reduz as linhas ao esperado.
- `test_unknown_candidate_returns_error`: candidato inexistente retorna código ≠ 0 e uma mensagem clara, sem criar pasta.
- `test_no_args_runs_national`: sem opções, o recorte é nacional (`uf=None`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `cli.py` com `argparse`**

Filtros por igualdade normalizada (sem acento, sem caixa) para cargo, partido e candidato.

- [ ] **Step 4: Rodar e ver passar; rodar no RN real**

Run: `.venv/bin/pytest tests/test_cli.py -v` → 4 passed.
Run: `.venv/bin/gastos analisar --uf RN`
Expected: pasta `out/<hoje>_uf-RN/` com todos os arquivos, e `relatorio.md` legível.

- [ ] **Step 5: Commit**

```bash
git add src/gastos/cli.py tests/test_cli.py
git commit -m "feat: CLI analisar com recortes por UF, cargo, partido e candidato"
```

---

### Task 6: Lista de eleitos e contatos

**Files:**
- Create: `src/gastos/eleitos.py`, `tests/test_eleitos.py`, `tests/fixtures/contatos.csv`, `tests/fixtures/eleitos.csv`

**Interfaces:**
- Produces: `eleitos.download_resultados(dest: Path = Path("data/raw")) -> Path`. Baixa o arquivo de resultados de 2026 do portal de dados abertos do TSE.
- Produces: `eleitos.load_eleitos(path: Path) -> pd.DataFrame` com `nome, cargo, uf, partido, sq_candidato` só dos eleitos.
- Produces: `eleitos.match_contatos(contatos: pd.DataFrame, eleitos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`. Retorna `(casados, pendentes)`. Ligação por nome normalizado + `uf` + `cargo`. `pendentes` leva `motivo` (`sem_correspondencia` ou `ambiguo`).

- [ ] **Step 1: Descobrir o arquivo de resultados do TSE**

Procurar na API do portal de dados abertos (`package_search`) o conjunto de resultados/candidatos de 2026 que traz a situação de totalização ("Eleito"). Anotar a URL, as colunas e a situação para "eleito" (inclui "eleito por QP" e "eleito por média", se existirem). Se o resultado ainda não estiver publicado, parar e avisar o Ramon; as Tasks 7 e 8 podem seguir com um arquivo de eleitos fornecido por ele.

- [ ] **Step 2: Escrever os testes (falham)**

- `test_match_by_normalized_name_uf_cargo`: `"José da Silva"` casa com `JOSE DA SILVA`.
- `test_unmatched_goes_to_pendentes`: contato sem eleito correspondente → `motivo == "sem_correspondencia"` (Review Focus 5).
- `test_ambiguous_goes_to_pendentes`: dois eleitos com o mesmo nome, UF e cargo → `motivo == "ambiguo"`; nunca casa automático.
- `test_only_elected_loaded`: `load_eleitos` ignora suplentes e não eleitos.

- [ ] **Step 3: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_eleitos.py -v`
Expected: FAIL.

- [ ] **Step 4: Implementar `eleitos.py`**

Normalização igual à de `classify` (reutilizar a função de normalização; se estiver em `classify`, extrair para `gastos/text.py` e importar dos dois lados).

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_eleitos.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/gastos tests
git commit -m "feat: lista de eleitos e ligação com contatos"
```

---

### Task 7: Modelos de e-mail por estado

**Files:**
- Create: `templates/email_estado.md.j2`, `src/gastos/emails.py`, `tests/test_emails.py`
- Modify: `src/gastos/cli.py` (subcomando `emails`)

**Interfaces:**
- Consumes: `metrics.summarize`, `metrics.candidate_shares`, `metrics.cap_impact`, `metrics.distribution`, `eleitos.match_contatos`.
- Produces: `emails.render_email(contato: pd.Series, stats: dict, teto_proposto: float, dt_corte: str) -> str`. `stats` traz, para a UF e o cargo do destinatário: `total`, `principal`, `confirmado`, `proporcao`, `mediana`, `p90`, `impacto_teto` (`n_acima`, `pct_acima`, `excedente` para `teto_proposto`).
- Produces: `emails.write_emails(contatos_csv: Path, uf_runs: dict[str, Path], teto_proposto: float, out: Path) -> Path`. Escreve um `.md` por contato casado e `pendencias.md`.
- CLI: `gastos emails --contatos contatos.csv --teto 0.10`. Roda a análise de cada UF dos contatos e gera os e-mails.

- [ ] **Step 1: Escrever os testes (falham)**

- `test_email_mentions_partial_and_cutoff`: o texto contém "parcial" e a data de corte.
- `test_email_has_state_numbers_and_floor`: traz o valor principal da UF e o valor confirmado como piso.
- `test_email_proposes_percentage_ceiling_and_invites`: contém o teto proposto (por exemplo "10%") e um convite à ação.
- `test_email_forbidden_content`: não contém "dinheiro público", o nome de nenhum candidato, nem partido (Global Constraints).
- `test_email_never_rendered_without_numbers`: UF sem dados ou sem gasto classificado vai para `pendencias.md` e não gera arquivo (Review Focus 5).
- `test_provavel_only_in_note`: o valor `provavel` aparece só numa nota ao fim, nunca somado ao principal.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_emails.py -v`
Expected: FAIL.

- [ ] **Step 3: Escrever o modelo `email_estado.md.j2` e implementar `emails.py`**

Estrutura do texto: apresentação do problema em duas frases; números do estado (valor principal, piso confirmado, proporção do gasto de campanha, mediana e P90 por candidato); o impacto do teto proposto; pedido de ajuda; nota sobre dados parciais, data de corte, e nota sobre `provavel`. Português, tom sóbrio.

- [ ] **Step 4: Rodar e ver passar; gerar para o RN com um contato de exemplo**

Run: `.venv/bin/pytest tests/test_emails.py -v` → 6 passed.
Run: `.venv/bin/gastos emails --contatos tests/fixtures/contatos.csv --teto 0.10`
Expected: pasta com os `.md`. O Ramon lê um e-mail completo antes de usar.

- [ ] **Step 5: Commit**

```bash
git add templates src tests
git commit -m "feat: geração de e-mails estaduais com teto percentual"
```

---

### Task 8: README e execução de ponta a ponta no RN

**Files:**
- Create: `README.md`

- [ ] **Step 1: Escrever o `README.md`**

Como instalar o venv, baixar os dados, rodar `analisar` com cada recorte, editar `config/plataformas.yaml`, gerar e-mails e ler a pasta de saída. Curto, com um exemplo para o RN.

- [ ] **Step 2: Rodar toda a suíte e o fluxo completo**

Run: `.venv/bin/pytest -v` → todos passam.
Run: `.venv/bin/gastos analisar --uf RN` e `.venv/bin/gastos analisar --uf RN --cargo "Deputado Federal"`
Expected: duas pastas em `out/` com evidências cujas somas batem com o `resumo.csv`.

- [ ] **Step 3: Revisão manual dos números do RN com o Ramon**

Apresentar o `relatorio.md` e a amostra de `qualidade.md` do RN. Ajustar `plataformas.yaml` se o Ramon apontar erro. O RN só é considerado pronto depois dessa conferência.

- [ ] **Step 4: Commit**

```bash
git add README.md config
git commit -m "docs: README e conferência do RN"
```

---

## Autoavaliação (feita ao escrever)

- **Cobertura do desenho:** classificação em três níveis e regras em configuração (Task 2); recortes por UF, cargo, partido, candidato (Tasks 3 e 5); proporção, distribuição e impacto de tetos (Task 3); evidência por número e versão datada (Task 4); eleitos e contatos (Task 6); e-mail estadual, parcial, sem "dinheiro público", sem citar campanha do destinatário (Task 7); base contratada e linhas válidas (Task 1).
- **Consistência de tipos:** `nivel`, `principal`, `proporcao` e `dt_geracao` são definidos nas Tasks 1 a 3 e usados com os mesmos nomes nas Tasks 4 a 7.
- **Fora do plano por decisão do desenho:** despesas pagas e recorte por fonte (extra opcional), análise nacional por e-mail, envio de e-mails.
