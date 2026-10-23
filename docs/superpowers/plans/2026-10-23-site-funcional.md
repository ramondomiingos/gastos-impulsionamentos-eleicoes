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

### Task 2: página do site

**Arquivos:** criar `site/lib.js`, `site/app.js`, `site/style.css`, `site/vendor/html2canvas.min.js` (1.4.1) com `site/vendor/LEIAME.md` (origem, versão, licença MIT, SHA-256), `tests/js/lib.test.js`; alterar `site/index.html`, `.github/workflows/tests.yml` (passo `node --test tests/js`).

**Interfaces:** `site/lib.js` exporta (UMD: `module.exports` no Node e `window.Lib` no navegador): `formatBRL(n)`, `formatPct(x)`, `hero(n) -> {valor, unidade}`, `parseHash(hash, ufsValidas, cargosPorUf) -> {uf, cargo}` (recorte válido sempre), `buildHash(uf, cargo)`, `modeloCards(dados, cargoKey, indice) -> {cards: [...]}` (dados já prontos para os 5 cards, sem tocar no DOM), `escapeHtml(s)`.

**Comportamento:** conforme a seção "Comportamento da página" do desenho. Seletores Estado e Cargo, resumo, bloco "Maiores valores declarados" (com aviso e link para `https://divulgacandcontas.tse.jus.br/`), 5 cards 1080×1920 com pré-visualização a 1/3 e download em PNG (`html2canvas`), "Baixar todos", perfil editável do card 5 (guardado em `localStorage` dentro de `try/catch`), seção "Como medimos", aviso "Encontrou um erro?" com link para as issues do repositório (`https://github.com/ramondomiingos/gastos-impulsionamentos-eleicoes/issues`), estado na URL (`#PB/governador`). Layout responsivo (celular a 360 px sem rolagem horizontal), tema claro e escuro, foco visível e rótulos nos controles.

**Testes (`node --test`):** `formatBRL`/`formatPct`/`hero` com os valores do projeto (R$ 363.000, 12,0%, R$ 574 mil, R$ 20,4 mi); `parseHash` cai para recorte válido com UF ou cargo inválidos; `buildHash`; `modeloCards` para "todos" e para um cargo, com `top` vazio e com 5 nomes; `escapeHtml` com `<`, `&`, aspas e apóstrofo; nenhum card contém a palavra "partido" nem "dinheiro público".

- [ ] Testes primeiro (falham), depois `lib.js`; depois `app.js`, `style.css` e `index.html` usando os dados reais de `site/data/`.
- [ ] Servir `site/` localmente e verificar no Chrome sem janela (capturas de tela): Brasil/Todos, PB/Todos, RN/Governador, um cargo com `top` de 5 nomes, e a largura de 360 px. Relatar o que viu e corrigir estouros de texto.
- [ ] Commit.

---

### Task 3: documentação e fechamento

**Arquivos:** alterar `docs/site-e-publicacao.md`, `docs/uso.md` (`gastos publicar`), `docs/como-funciona.md` (módulo `publicar`), `README.md`, `CONTRIBUTING.md` (tarefas), `site/index.html` (se algum texto ficar desatualizado).

- [ ] Atualizar a documentação para o que existe (status: site funcional; como atualizar os dados com `gastos publicar` e `git push`; decisão de mostrar só os 5 maiores por recorte).
- [ ] Revisão final do branch por um revisor independente (modelo mais capaz).
- [ ] Correções da revisão em uma rodada.
- [ ] Mesclar na `main` e fazer push **só com a confirmação do mantenedor**.
