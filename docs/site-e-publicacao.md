# Site público e publicação

> **Status: funcional.** O site está em <https://radar-impulsionamento.netlify.app> (se ainda mostrar a página provisória antiga, a versão nova ainda não foi mesclada e publicada). A atualização dos dados é manual; a rotina agendada e o domínio próprio ficam para depois.

## O que é

Um **site estático** (sem servidor, banco, API nem CDN de terceiros): `site/index.html` mais JavaScript que lê os JSON de `site/data/`, gerados por `gastos publicar`. Qualquer pessoa escolhe **cargo e estado**, vê os números, os **5 maiores valores declarados** do recorte (por nome, sem partido) e baixa **5 cards** de story em PNG, gerados no navegador.

```
site/
  index.html     página
  app.js         comportamento (filtros, resumo, lista, cards, download)
  lib.js         funções puras (formatação, textos, escolha de cargo/estado); testadas em tests/js/
  style.css
  vendor/        html2canvas 1.4.1 (MIT), dentro do repositório; veja vendor/LEIAME.md
  data/
    index.json   datas, piso da campanha, tetos e a lista de UFs com seus cargos
    BR.json      país: só o recorte `presidente`
    <UF>.json    um por estado: `todos` mais um recorte por cargo
```

## Contrato dos dados (resumo)

O formato completo, campo a campo, está no [desenho do site](superpowers/specs/2026-10-23-site-funcional-design.md#formato-dos-dados-contrato-entre-gastos-publicar-e-o-site). O essencial:

| Arquivo | Conteúdo |
| --- | --- |
| `index.json` | `versao`, `gerado_em`, `dt_geracao`, `dt_ultima_prestacao`, `piso_campanha`, `tetos`, `ufs[]` (`uf`, `nome`, `artigo`, `cargos`) |
| `<UF>.json` | datas, `segundo_turno`, `n_candidatos_total` e `recortes` (chaves: `todos`, `governador`, `senador`, `deputado-federal`, `deputado-estadual`, `deputado-distrital`) |
| cada recorte | `total`, `principal`, `confirmado`, `generico`, `provavel`, `proporcao`, contagens, **fonte do dinheiro** (`pago`, `pago_publico`, `pct_publico`, `cobertura_pago`, esta limitada a 1), `tetos[]` e `top[]` (até 5 candidatos) |

Valores em reais; proporções como fração (0,05 = 5%). Os `top[]` trazem nome, cargo, UF, valor, piso confirmado, total da campanha e proporção, e **nenhum campo de partido** (um teste garante). Veja a [metodologia](metodologia.md#fonte-do-dinheiro-parte-paga-com-fundos-públicos) para o que `pct_publico` mede.

## Como a página se comporta

- **Cargo** vem antes de **Estado**. Brasil só tem Presidente; nos estados: Todos os cargos, Governador, Senador, Deputado federal e Deputado estadual (Deputado distrital só no DF). Escolher **Presidente** desabilita o seletor de Estado (disputa nacional, sem divisão por estado); trocar para um cargo que não existe no estado escolhido ajusta a seleção e avisa.
- A escolha vai no endereço (`#PB/governador`), para compartilhar.
- **Resumo:** número principal, piso confirmado, proporção sobre o total declarado, candidatos que já declararam, datas dos dados e aviso de dados parciais.
- **Por que isso importa:** só afirma que o dinheiro é público com a parcela medida (`pct_publico`) e a ressalva de que é sobre o valor já pago; a frase sobre retorno para o país é a posição dos autores e vem marcada como tal.
- **Maiores valores declarados:** 5 por recorte, ordenados por valor absoluto, com piso confirmado, total e proporção, "campanha pequena" abaixo do piso, e link para o [portal de consulta do TSE](https://divulgacandcontas.tse.jus.br/) (buscar pelo nome; não há link individual, porque os links ainda não foram verificados).
- **5 cards** (1080×1920): gancho com o número; por cargo (ou confirmado versus sem plataforma citada); maiores valores; efeito dos tetos de 5%, 10% e 20%; convite para visitar o site. Botões "Baixar PNG" e "Baixar todos".
- **Como medimos**, aviso "Encontrou um erro?" (link para as issues, porque o site cita pessoas) e rodapé com a fonte. Erros de carregamento mostram mensagem e botão "Tentar de novo".

Os tetos contam só campanhas com pelo menos R$ 50.000 de despesas contratadas (`--piso-campanha`), para campanhas minúsculas não inflarem a conta.

## Como atualizar os dados

O TSE refaz os arquivos conforme chegam as prestações de contas. Fluxo **manual** (o atual):

1. Ter os zips em `data/raw/` (ou deixar o comando baixar) e rodar `gastos publicar`: leva cerca de 40 s e usa uns 2 GB de RAM. Detalhes de opções em [uso.md](uso.md#gastos-publicar-json-do-site).
2. Conferir as datas em `site/data/index.json` (`dt_geracao`, `dt_ultima_prestacao`) e rodar os testes: `.venv/bin/pytest -q` e `node --test tests/js/*.test.js`.
3. `git commit` de `site/data/` e `git push`. A Netlify republica sozinha.

Fluxo **automático** (depois): uma rotina agendada (GitHub Actions) baixa os dados do TSE, roda `gastos publicar` e abre um pull request com os JSON novos, para alguém revisar. O download tem cerca de 209 MB, então deve rodar no máximo algumas vezes por semana.

## Hospedagem: Netlify

O site é uma pasta (`site/`), então qualquer hospedagem estática serve. O `netlify.toml` publica `site/` sem build. Notas:

- Desde setembro de 2025 o plano grátis é por créditos (300 por mês, segundo fontes de terceiros). **Confira os limites atuais na página oficial de preços**: podem mudar.
- Trocar de hospedagem depois (por exemplo Cloudflare Pages) é simples.

### Ligar o repositório à Netlify (feito; fica como referência)

O site `radar-impulsionamento` já está ligado a este repositório. Os passos, caso precise refazer:

1. Conta em [netlify.com](https://www.netlify.com).
2. **Add new site → Import an existing project → GitHub** e escolha este repositório.
3. **Branch de produção** `main`; **build command** vazio (o `netlify.toml` já cobre); **publish directory** `site`.
4. Publique e confirme que `https://<nome>.netlify.app` abre.
5. Todo push na `main` republica o site; pull requests geram uma prévia (deploy preview).

### Domínio próprio (para depois)

**Site configuration → Domain management → Add a domain** (por exemplo `gastos.ramondomingos.com.br`). No provedor de DNS, crie um registro **CNAME** do subdomínio apontando para `radar-impulsionamento.netlify.app`. O HTTPS é emitido automaticamente.

## O que falta fazer

- Domínio próprio.
- Rotina agendada de atualização dos dados (GitHub Actions).
- Verificar os links das prestações (veja o [CONTRIBUTING](../CONTRIBUTING.md)) para linkar cada candidato.
- Decidir a regra dos honorários de agência (veja a [metodologia](metodologia.md#o-que-o-método-ainda-erra-conhecido)).
