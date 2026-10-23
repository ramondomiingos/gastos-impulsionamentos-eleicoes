# Site funcional: plano de implementação

> **Para quem executa:** use superpowers:subagent-driven-development (cada tarefa com seu implementador e revisão).

**Meta:** site estático onde se filtra por estado e cargo, vê os números e os 5 maiores valores declarados e baixa os cards de story; dados gerados por `gastos publicar`.

**Arquitetura:** `gastos publicar` carrega o arquivo nacional uma vez, classifica, agrega por UF × cargo e grava JSON em `site/data/`. O site (HTML/CSS/JS simples) lê esses JSON. Sem build.

**Desenho (autoridade):** `docs/superpowers/specs/2026-10-23-site-funcional-design.md` (formato exato dos JSON, comportamento da página, riscos). O desenho original está em `docs/superpowers/specs/2026-10-22-gasto-plataformas-estrangeiras-design.md`.

## Restrições globais

- Os JSON seguem **exatamente** o formato do desenho; **nenhum campo de partido**; nomes só em `top` (até 5 por recorte), vindos de `NM_CANDIDATO` do arquivo de candidatos do TSE, em caixa de título.
- Cargos do site (constante `CARGOS_SITE`): Brasil só `presidente`; estados `governador`, `senador`, `deputado-federal`, `deputado-estadual` e `deputado-distrital` (este só no DF), mais `todos`.
- `principal = confirmado + generico`; `provavel` nunca entra no principal; todos os números saem do mesmo pipeline (`loader` → `classify` → `metrics`), sem reimplementar regras.
- Ranking do `top`: `principal` desc, depois `total` desc, depois `sq_candidato` asc; só candidatos com `principal > 0`.
- Tetos de 5%, 10%, 15% e 20%, contados só entre candidatos com `total >= 50000` (`piso_campanha`).
- Testes offline (Python: `tests/` com fixtures; JavaScript: `node --test`, sem rede). Todo comportamento novo com teste que falha antes.
- `html2canvas` 1.4.1 hospedado em `site/vendor/` (sem CDN). Sem framework e sem build.
- A página não envia dados a lugar nenhum (sem analytics, sem cookies, sem chamadas externas).
- Textos em português; margens de segurança de story (topo ≥ 215 px, rodapé ≥ 190 px) nos cards; aviso de dados parciais e datas em todos os cards.
- Linguagem neutra: "Maiores valores declarados"; nunca "piores" ou "gastadores".

## Revisão (foco)

1. Número que não bate: soma das UFs mais Presidente ≠ total nacional; `principal` diferente do relatório de `gastos analisar` para o mesmo recorte.
2. Recorte vazio ou cargo inexistente na UF: a página não quebra e diz isso; `top` vazio mostra mensagem, não lista vazia.
3. Nome com acento, apóstrofo, aspas ou `<`: a página escapa (nunca injeta HTML) e o PNG sai legível.
4. Estado/cargo na URL (`#PB/governador`) inválido: volta para um recorte válido sem erro.
5. Falha ao carregar o JSON (arquivo ausente, rede): mensagem clara; nada em branco.

---

### Task 1: `gastos publicar` e dados reais

**Arquivos:** criar `src/gastos/publicar.py`, `tests/test_publicar.py`; alterar `src/gastos/cli.py` (subcomando `publicar`), `src/gastos/metrics.py` (ranking por valor), `src/gastos/eleitos.py` (leitura de nomes e contagens por UF, se ainda não houver).

**Interfaces (produz):**
- `metrics.maiores_valores(shares: pd.DataFrame, n: int = 5) -> pd.DataFrame` (ranking do desenho; `shares` = saída de `candidate_shares`).
- `publicar.slug_cargo(cargo: str) -> str` (`"Deputado Federal"` → `"deputado-federal"`).
- `publicar.montar_recorte(shares: pd.DataFrame, rotulo: str, cargo: str | None, nomes: dict[str, str], tetos: list[float], piso_campanha: float) -> dict` (formato `Recorte` do desenho).
- `publicar.montar_uf(df: pd.DataFrame, uf: str, nomes: dict[str, str], info: dict, tetos, piso_campanha, meta: dict) -> dict` (formato `<UF>.json`).
- `publicar.publicar(zip_path, eleitos_zip, saida: Path, tetos=..., piso_campanha=50000.0, hoje=None) -> Path` grava `index.json`, `BR.json` e um `<UF>.json` por estado; carrega o arquivo nacional **uma vez**.
- CLI: `gastos publicar [--zip PATH] [--eleitos-zip PATH] [--saida site/data] [--piso-campanha 50000]` (mesmo tratamento de erros e de download que `analisar`; sem rede nos testes).

**Testes (nomes e asserções):**
- `test_top_ranks_by_value_then_total_then_sq`; `test_top_excludes_zero_principal`; `test_top_limit_five`.
- `test_recorte_fields_and_principal_is_confirmado_plus_generico`; `test_recorte_tetos_only_among_eligible_campaigns` (campanha com total < piso não entra em `n_elegiveis` nem nos `tetos`).
- `test_uf_has_todos_and_cargo_keys_only_for_existing_cargos`.
- `test_json_has_no_party_field_anywhere` (varre todas as chaves, recursivamente, e falha se achar `partido`).
- `test_names_title_case_with_accents_from_consulta_cand`.
- `test_br_has_only_presidente_recorte_and_states_exclude_presidente`; `test_index_lists_cargos_per_uf` (Brasil só `presidente`; estados com `todos` e os cargos existentes; DF com `deputado-distrital` e sem `deputado-estadual`).
- `test_publicar_writes_index_and_one_file_per_uf_deterministically` (rodar duas vezes gera arquivos idênticos).
- `test_cli_publicar_invalid_piso_exit_2` e `test_cli_publicar_missing_zip_exit_1`.

- [ ] Escrever os testes, ver falhar, implementar, ver passar; suíte inteira verde.
- [ ] Rodar com os dados reais (`data/raw/prestacao_de_contas_eleitorais_candidatos_2026.zip` e `data/raw/consulta_cand_2026.zip`) para `site/data/`. Conferir e relatar: `RN.todos.principal` = R$ 4.240.709,51 e `RN.governador.principal` = R$ 574.064,22 (execuções de `gastos analisar` de 22/10/2026); `BR.presidente.principal` = R$ 20.425.733,00 e `.total` = R$ 187.080.180,86; a soma dos `todos.principal` dos 27 estados mais `BR.presidente.principal` = R$ 435.968.358,91 (total nacional de `gastos analisar`); tamanho total dos JSON.
- [ ] Commit do código e, em commit separado, de `site/data/`.

---

### Task 2: `gastos publicar` com a parcela paga com fundos públicos

**Arquivos:** alterar `src/gastos/publicar.py`, `src/gastos/loader.py` (leitura do arquivo de despesas pagas, em função própria), `tests/test_publicar.py`; fixtures em `tests/` conforme preciso.

**Contrato:** campos `pago`, `pago_publico`, `pct_publico` e `cobertura_pago` em cada `Recorte`, como no desenho (seção "Fonte do dinheiro"). Fontes públicas: exatamente "Fundo Especial de Financiamento de Campanha" e "Fundo Partidário" (`DS_FONTE_DESPESA`); o resto ("Outros Recursos") não é público. Arquivo: `despesas_pagas_candidatos_2026_BRASIL.csv` dentro do mesmo zip (cerca de 317 MB; ler em fluxo, só as colunas `SQ_DESPESA`, `DS_FONTE_DESPESA` e `VR_PAGTO_DESPESA`, com o mesmo tratamento de bytes nulos, encoding latin-1 e vírgula decimal do loader).

**Regra de alocação:** para cada `SQ_DESPESA`, o valor pago por fonte é repartido entre as linhas contratadas do mesmo `SQ_DESPESA` proporcionalmente ao valor contratado de cada linha; só entra em `pago` a fração que cabe às linhas de nível `confirmado` ou `generico`. A UF e o cargo de cada pagamento vêm da linha contratada correspondente. Pagamento sem linha contratada correspondente é ignorado (e contado em um aviso no resultado de `publicar`, não no JSON).

**Testes:** `test_pago_publico_allocates_by_fonte` (fixture com FEFC, Fundo Partidário e Outros Recursos); `test_pago_split_proportionally_when_sq_has_non_ad_items`; `test_pct_publico_zero_when_nothing_paid`; `test_cobertura_pago_is_pago_over_principal`; `test_unmatched_payments_ignored`; `test_publicar_fields_present_in_every_recorte`.

**Itens do review da Task 1 (fazer junto):** (a) `test_json_has_no_party_field_anywhere` deve reprovar qualquer chave que contenha "partido" (sem diferenciar maiúsculas) e qualquer valor/texto bruto que contenha a sigla de partido da fixture (`SG_PARTIDO`); (b) `recortes["todos"]` só é criado se a UF tiver linhas em `CARGOS_SITE`; (c) `json.dumps(..., allow_nan=False)` ao gravar; (d) testes para UF sem despesa declarada e para candidato fora do arquivo de candidatos no fluxo completo de `publicar`.

- [ ] Testes primeiro (falham), implementar, suíte inteira verde.
- [ ] Regerar `site/data/` com os dados reais e conferir: para `RN.todos`, `pago` ≈ R$ 4.075.106,55 e `pct_publico` ≈ 0,793 (medição ad hoc de 22/10/2026, que usou ligação direta por `SQ_DESPESA`; pequena diferença é esperada por causa da repartição proporcional, relate e explique). Relatar também `pct_publico` e `cobertura_pago` de Brasil/Presidente, de PB e de SP, e quaisquer recortes com `cobertura_pago` muito baixa.
- [ ] Commits separados: código/testes e, depois, `site/data/`.

---

### Task 3: página do site

**Arquivos:** criar `site/lib.js`, `site/app.js`, `site/style.css`, `site/vendor/html2canvas.min.js` (1.4.1) com `site/vendor/LEIAME.md` (origem, versão, licença MIT, SHA-256), `tests/js/lib.test.js`; alterar `site/index.html`, `.github/workflows/tests.yml` (passo `node --test tests/js`).

**Interfaces:** `site/lib.js` exporta (UMD: `module.exports` no Node e `window.Lib` no navegador): `formatBRL(n)`, `formatPct(x)`, `hero(n) -> {valor, unidade}`, `parseHash(hash, ufsValidas, cargosPorUf) -> {uf, cargo}` (recorte válido sempre), `buildHash(uf, cargo)`, `modeloCards(dados, cargoKey, indice) -> {cards: [...]}` (dados já prontos para os 5 cards, sem tocar no DOM), `escapeHtml(s)`.

**Comportamento:** conforme a seção "Comportamento da página" do desenho. Seletores Estado e Cargo, resumo, bloco "Maiores valores declarados" (com aviso e link para `https://divulgacandcontas.tse.jus.br/`), 5 cards 1080×1920 com pré-visualização a 1/3 e download em PNG (`html2canvas`), "Baixar todos", card 5 que convida a visitar o site (endereço em destaque, sem perfil pessoal), seção "Como medimos", aviso "Encontrou um erro?" com link para as issues do repositório (`https://github.com/ramondomiingos/gastos-impulsionamentos-eleicoes/issues`), estado na URL (`#PB/governador`). Layout responsivo (celular a 360 px sem rolagem horizontal), tema claro e escuro, foco visível e rótulos nos controles.

**Complementos decididos depois do desenho (valem para esta tarefa):**
- **Nome:** o projeto se chama **Radar do Impulsionamento**; frase de apoio: "Quanto as campanhas gastam com anúncios em plataformas estrangeiras, e por que um teto faz sentido." Título da página, cabeçalho e rodapé usam isso. Hashtag sugerida no último card: `#TetoNoImpulsionamento`.
- **Seção "Por que isso importa"** (visível, logo abaixo do resumo), com este texto, adaptando o número ao recorte escolhido: "As campanhas são financiadas, em grande parte, com **dinheiro público** (Fundo Eleitoral e Fundo Partidário). {no recorte: X% do valor já pago em impulsionamento saiu desses fundos}. Esse dinheiro vai para plataformas estrangeiras que empregam pouco no país. **Na nossa visão**, ele teria mais retorno para as pessoas se circulasse na economia local, em benfeitorias. Por isso propomos um teto percentual." O `X%` vem de `pct_publico` do recorte, com a ressalva "(sobre o valor já pago; cobertura de Y% do contratado)" usando `cobertura_pago`. A frase de opinião fica marcada como posição dos autores ("Na nossa visão").
- **Campos `pago`, `pago_publico`, `pct_publico`, `cobertura_pago` podem não existir ainda** nos JSON de `site/data/` (a Tarefa 2 os adiciona em paralelo, em outra cópia do repositório). A página deve funcionar sem eles: se faltarem, a seção "Por que isso importa" omite o número e a frase sobre fundos públicos, sem quebrar nem mostrar "undefined". Os testes cobrem os dois casos.
- **Desenvolvimento e testes sem depender da Tarefa 2:** crie dados de exemplo em `tests/js/fixtures/` (cópias reduzidas de `site/data/` com e sem os campos novos) e **não altere `site/data/`** (ele é regerado pela Tarefa 2). Para ver a página inteira com dados completos, sirva `site/` com um arquivo temporário de dados de teste fora do repositório ou use as fixtures por parâmetro de URL de desenvolvimento (`?dados=...`), à sua escolha, desde que a versão publicada leia `data/` por padrão.
- **Cards (5):** margens de segurança de story no topo (≥ 215 px) e no rodapé (≥ 190 px); nada de partido; aviso de dados parciais e datas.

**Testes (`node --test`):** `formatBRL`/`formatPct`/`hero` com os valores do projeto (R$ 363.000, 12,0%, R$ 574 mil, R$ 20,4 mi); `parseHash` cai para recorte válido com UF ou cargo inválidos; `buildHash`; `modeloCards` para "todos" e para um cargo, com `top` vazio e com 5 nomes; `escapeHtml` com `<`, `&`, aspas e apóstrofo; nenhum card contém a palavra "partido" nem "dinheiro público".

- [ ] Testes primeiro (falham), depois `lib.js`; depois `app.js`, `style.css` e `index.html` usando os dados reais de `site/data/`.
- [ ] Servir `site/` localmente e verificar no Chrome sem janela (capturas de tela): Brasil/Todos, PB/Todos, RN/Governador, um cargo com `top` de 5 nomes, e a largura de 360 px. Relatar o que viu e corrigir estouros de texto.
- [ ] Commit.

---

### Task 4: documentação e fechamento

**Arquivos:** alterar `docs/site-e-publicacao.md`, `docs/uso.md` (`gastos publicar`), `docs/como-funciona.md` (módulo `publicar`), `README.md`, `CONTRIBUTING.md` (tarefas), `site/index.html` (se algum texto ficar desatualizado).

- [ ] Atualizar a documentação para o que existe (status: site funcional; como atualizar os dados com `gastos publicar` e `git push`; decisão de mostrar só os 5 maiores por recorte).
- [ ] Revisão final do branch por um revisor independente (modelo mais capaz).
- [ ] Correções da revisão em uma rodada.
- [ ] Mesclar na `main` e fazer push **só com a confirmação do mantenedor**.
