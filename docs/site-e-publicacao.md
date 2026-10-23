# Site público e publicação

> **Status: planejado.** Hoje o diretório `site/` tem só uma página provisória. Este documento descreve o plano e como ligar o repositório à hospedagem, para que mais gente possa ajudar.

## O que será

Um **site estático** (sem servidor, banco ou API), em um subdomínio do mantenedor, onde qualquer pessoa filtra por **estado e cargo** e **gera os stories** em imagem (PNG) direto no navegador. O site mostra a data dos dados e o aviso de que são parciais.

O WordPress do mantenedor não hospeda isso: ele só linka para o site (ou o incorpora com um iframe).

## Como será feito

```
site/
  index.html          página: filtros e geração dos cards (HTML + JavaScript)
  data/
    index.json        versão dos dados, datas (geração do TSE e prestação mais recente), lista de UFs
    <UF>.json         números do estado: total, por cargo, efeito dos tetos
```

- Os JSON são gerados pelo pipeline (um comando de exportação **a criar**, `gastos publicar`). O país inteiro deve pesar cerca de 2,5 MB, uns 90 KB por estado.
- O JavaScript carrega só o JSON do estado escolhido.
- O gerador de stories do repositório (`story.py` e os templates) é a base visual: o site reproduz os mesmos 4 cards.

### Decisão em aberto: o que aparece nos JSON

Uma página pública com todos os candidatos expõe o percentual de cada pessoa a qualquer busca, o que pode ser lido como acusação mesmo sendo dado público. As opções em discussão:

1. só **agregados** (estado, cargo, partido), sem nomes (a mais segura para começar);
2. agregados **mais busca por candidato**, com aviso de método (confirmado versus sem plataforma citada);
3. agregados mais os **5 maiores por estado**, sem busca livre por nome.

O que for decidido define o formato do `<UF>.json`. Participe da decisão abrindo uma issue.

## Hospedagem: Netlify

O site é uma pasta (`site/`), então qualquer hospedagem estática serve. O plano é a **Netlify** (plano grátis). Notas:

- Desde setembro de 2025 o plano grátis é por créditos (300 por mês, segundo fontes de terceiros). Banda e cada publicação consomem créditos; **confira os limites atuais na página oficial de preços**, porque podem mudar e as fontes divergem em detalhes.
- Como o site é uma pasta, trocar de hospedagem depois (por exemplo Cloudflare Pages) é simples.

### Ligar o repositório à Netlify (passo a passo, para o mantenedor)

1. Crie uma conta em [netlify.com](https://www.netlify.com).
2. **Add new site → Import an existing project → GitHub** e escolha este repositório. Autorize o acesso.
3. Configurações de deploy: **branch de produção** `main`; **build command** vazio (não há build; o `netlify.toml` já cobre isso); **publish directory** `site`.
4. Publique. A Netlify gera um endereço `https://<nome>.netlify.app`; confirme que a página provisória abre.
5. Domínio próprio: **Site configuration → Domain management → Add a domain** (por exemplo `gastos.ramondomingos.com.br`). No provedor de DNS do domínio, crie um registro **CNAME** do subdomínio apontando para o endereço `<nome>.netlify.app`. O HTTPS é emitido automaticamente.
6. A partir daí, **todo push na `main` republica o site**. Pull requests geram uma prévia (deploy preview) para revisão.

## Como atualizar os dados

O TSE refaz os arquivos conforme chegam as prestações de contas, e as prestações finais ainda vão mudar os números. Fluxo previsto:

1. **Manual (primeiro):** atualizar os dados e regenerar os JSON (`gastos publicar`, a criar; hoje `gastos analisar --uf XX` para cada estado), conferir a data de atualização, fazer commit em `site/data/` e dar push. A Netlify republica sozinha.
2. **Automático (depois):** uma rotina agendada (GitHub Actions) baixa os dados do TSE, roda o pipeline e abre um pull request com os JSON novos. Alguém revisa e aprova. O download do TSE tem cerca de 209 MB, então a rotina roda no máximo algumas vezes por semana.

Em qualquer caso, a página mostra a **data de geração dos dados do TSE** e a da prestação mais recente, para o visitante saber o quão atual é o número.

## O que falta fazer

- Decidir o que aparece nos JSON (acima).
- Criar o comando `gastos publicar` (exportação dos JSON).
- Construir `site/index.html` com os filtros e a geração dos cards.
- Verificar os links das prestações (veja o [CONTRIBUTING](../CONTRIBUTING.md)).
- Criar a rotina agendada de atualização.
