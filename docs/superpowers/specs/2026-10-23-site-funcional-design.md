# Site funcional (agregados por estado e cargo): desenho

Data: 2026-10-23. Complementa o [desenho original](2026-10-22-gasto-plataformas-estrangeiras-design.md).

## Intenção

Um site público e estático (Netlify, endereço atual `https://gastos-eleicoes.netlify.app`) onde qualquer pessoa escolhe **estado** e **cargo**, vê quanto as campanhas gastaram com impulsionamento em plataformas estrangeiras e **baixa os cards de story** (PNG) para divulgar a iniciativa. Para cada recorte, o site mostra também os **5 candidatos com maior valor declarado** em plataformas, por nome. Os números vêm do mesmo pipeline do projeto.

## Objetivos

1. Filtros por estado e cargo, com cargos diferentes por nível (decisão do mantenedor):
   - **Brasil:** só **Presidente**.
   - **Estado (27 UFs):** Senador, Deputado Estadual e Deputado Federal. Por minha conta, também **Governador** (cargo estadual que o projeto já analisa) e **Deputado Distrital** (só existe no DF, que não tem deputado estadual), além de "Todos os cargos" como visão geral do estado. A lista fica numa constante (`CARGOS_SITE`) e é fácil de reduzir.
2. Os números e as 4 imagens refletem o recorte; a escolha vai no endereço (`#PB/governador`), para compartilhar.
3. Mostrar sempre a **data dos dados** do TSE, o aviso de que são **parciais** e o **piso confirmado** ao lado do número principal.
4. Atualizar os dados é regenerar arquivos JSON (`gastos publicar`) e dar push; a Netlify republica sozinha.
5. Funcionar no celular, sem servidor, sem banco e sem depender de CDN de terceiros.
6. Para cada recorte (estado × cargo), listar os **5 candidatos com maior valor em plataformas**, com nome, valor, total da campanha, proporção e o piso confirmado (decisão do mantenedor).

## Não objetivos (nesta versão)

- **Sem busca livre por candidato** e sem lista completa de candidatos: só os **5 maiores por recorte**.
- **Sem partido** do candidato em nenhum lugar do site (para a leitura não ser partidária).
- Sem links para a prestação individual de cada candidato enquanto eles não forem verificados; no lugar, um link para o portal de consulta do TSE, com a instrução de buscar pelo nome.
- Sem domínio próprio (será configurado depois).
- Sem automação de atualização (rotina agendada fica para depois).

## Decisões (minhas; o mantenedor pode mudar)

- **Nomes só dos 5 maiores por recorte**, a pedido do mantenedor. Ranking pelo **valor absoluto** em plataformas (`principal`), desempate por maior total da campanha e depois por `sq_candidato`. Nome como no cadastro do TSE (`NM_CANDIDATO`), em caixa de título, sem partido.
- **Linguagem neutra:** a lista se chama "Maiores valores declarados"; nunca "piores" ou "gastadores". Cada nome vem com o `confirmado` (piso) e a proporção sobre o total da campanha, para o leitor ver o tamanho relativo, e com a marca "campanha pequena" quando o total é menor que `piso_campanha`.
- **Canal de correção:** a página tem um aviso "Encontrou um erro? Abra uma issue no repositório" com o link, porque o site cita pessoas.
- **Tetos contados só entre campanhas com pelo menos R$ 50.000** de despesas contratadas (`piso_campanha`). Sem isso, campanhas minúsculas que gastaram quase tudo em anúncio (100%) entram em todos os tetos e inflam a contagem. O site diz isso explicitamente.
- O número principal continua `confirmado + generico`, com o `confirmado` sempre visível como piso; o `provavel` nunca entra no principal.
- `html2canvas` 1.4.1 (MIT) fica **dentro do repositório** (`site/vendor/`), para o site não depender de CDN.
- Sem build, sem framework: HTML, CSS e JavaScript simples; as funções puras ficam em `site/lib.js` e têm testes com `node --test`.

## Formato dos dados (contrato entre `gastos publicar` e o site)

Arquivos em `site/data/`: `index.json` e um `<UF>.json` por estado, mais `BR.json` (o país inteiro). Valores monetários em reais (número), proporções como fração (0,05 = 5%).

`index.json`:

```json
{
  "versao": 1,
  "gerado_em": "2026-10-23",
  "dt_geracao": "22/10/2026",
  "dt_ultima_prestacao": "21/10/2026",
  "piso_campanha": 50000,
  "tetos": [0.05, 0.10, 0.15, 0.20],
  "ufs": [
    {"uf": "BR", "nome": "Brasil", "artigo": "do", "cargos": ["presidente"]},
    {"uf": "AC", "nome": "Acre", "artigo": "do", "cargos": ["todos", "governador", "senador", "deputado-federal", "deputado-estadual"]}
  ]
}
```

`<UF>.json` (`dt_*` e `uf` do próprio recorte):

```json
{
  "uf": "PB", "nome": "Paraíba", "artigo": "da",
  "dt_geracao": "22/10/2026", "dt_ultima_prestacao": "21/10/2026",
  "segundo_turno": 0,
  "n_candidatos_total": 419,
  "recortes": {
    "todos": { "rotulo": "Todos os cargos", "cargo": null, "...": "campos de Recorte abaixo" },
    "governador": { "rotulo": "Governo", "cargo": "Governador", "...": "..." }
  }
}
```

`Recorte` (igual em `todos` e em cada cargo):

```json
{
  "rotulo": "Governo", "cargo": "Governador",
  "total": 19662447.54,        "principal": 1861487.96,
  "confirmado": 492000.0,      "generico": 1369487.96,   "provavel": 0.0,
  "proporcao": 0.0947,
  "n_candidatos": 3,           "n_gastaram": 3,
  "n_elegiveis": 3,
  "tetos": [{"teto": 0.05, "n_acima": 3, "pct_acima": 1.0, "excedente": 123.45}],
  "top": [
    {"sq": "200002534001", "nome": "Carlos Eduardo Xavier", "cargo": "Governador", "uf": "RN",
     "principal": 363000.0, "confirmado": 333000.0, "total": 3033561.29, "proporcao": 0.1197, "pequena": false}
  ]
}
```

- `n_candidatos`: candidatos com despesa declarada (total > 0). `n_gastaram`: com `principal > 0`. `n_elegiveis`: com total >= `piso_campanha` (base dos `tetos`).
- `tetos[].pct_acima` é fração de `n_elegiveis`; `excedente` = soma de `principal - teto × total` só dos que passam do teto.
- Chaves de cargo (slug): `presidente`, `governador`, `senador`, `deputado-federal`, `deputado-estadual`, `deputado-distrital`. Só aparecem os cargos de `CARGOS_SITE` que existem no recorte. **`BR.json` tem somente o recorte `presidente`** (sem `todos`). Os arquivos de estado têm `todos` (todos os cargos de `CARGOS_SITE` no estado) mais cada cargo existente; a candidatura a Presidente não entra nos estados.
- `segundo_turno`: candidatos do recorte ainda em "2º turno" no arquivo de candidatos do TSE (0 quando não há).
- `top`: até 5 candidatos do recorte (com `principal > 0`), na ordem do ranking acima. Nome completo do TSE em caixa de título (com acentos, vindo do arquivo de candidatos). **Nenhum campo de partido.** `pequena` é verdadeiro quando `total < piso_campanha`. Em `todos`, o ranking é entre todos os cargos do recorte; em `BR`, entre todos os candidatos do país.

## Comportamento da página

- Seletores **Estado** (Brasil primeiro) e **Cargo** (os de `ufs[].cargos` do estado escolhido: no Brasil só Presidente; nos estados, "Todos os cargos" e os cargos existentes). Ao mudar o estado, o cargo volta para o primeiro da lista (Presidente no Brasil, "Todos" nos estados) se o cargo escolhido não existir.
- Painel de resumo: número principal grande, piso confirmado, proporção sobre o total declarado, quantos candidatos já declararam, datas dos dados, aviso de dados parciais.
- Bloco **"Maiores valores declarados"** com os 5 do recorte: nome, cargo, valor em plataformas, confirmado, total da campanha e proporção; aviso de que o valor inclui impulsionamento sem plataforma citada; link para o portal de consulta do TSE (`https://divulgacandcontas.tse.jus.br/`) com a orientação de buscar pelo nome.
- Pré-visualização dos **5 cards** (1080×1920, exibidos a 1/3): (1) gancho com o número; (2) por cargo (quando "todos") ou confirmado versus sem plataforma citada (quando um cargo); (3) os 5 maiores valores declarados do recorte; (4) efeito dos tetos de 5%, 10% e 20%; (5) convite, com o perfil editável (guardado no navegador, se possível). Margens de segurança de story no topo e no rodapé.
- Botões "Baixar PNG" por card e "Baixar todos".
- Seção "Como medimos" curta, com os três níveis e o link do repositório; rodapé com a fonte e o aviso de que impulsionamento é legal e declarado.
- Erros de carregamento mostram uma mensagem clara; nada quebra em silêncio.

## Atualização dos dados

1. `gastos publicar` (baixa o TSE se preciso, classifica e grava `site/data/`).
2. Conferir `index.json` (datas) e rodar os testes.
3. `git commit` + `git push`: a Netlify republica.

## Riscos e cuidados

- **Classificação validada à mão só no RN:** a página mostra o piso confirmado ao lado do número principal e linka a metodologia.
- **Dados parciais e 2º turno:** aviso visível em todos os cards e no resumo.
- **Números por estado ainda sem revisão manual fora do RN:** o site diz que os dados são estimativas.
- **O site cita pessoas:** os valores incluem impulsionamento sem plataforma citada (`generico`), então cada nome mostra o `confirmado` ao lado; a lista é de valores declarados, não de irregularidades; há canal de correção; o ranking é por valor absoluto, o que naturalmente destaca campanhas grandes (a proporção aparece ao lado para dar contexto).
- **Homônimos:** a linha mostra cargo e UF, e o link leva ao portal de consulta, não a uma pessoa específica.
