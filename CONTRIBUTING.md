# Como contribuir

Obrigado por querer ajudar. Este projeto lida com dados de pessoas reais e vai embasar um pedido a parlamentares, então **a precisão importa mais que a velocidade**. Este guia diz por onde começar e quais são as regras.

## Preparando o ambiente

Precisa de Python 3.10+ (o projeto usa 3.12):

```bash
git clone https://github.com/ramondomiingos/gastos-impulsionamentos-eleicoes.git
cd gastos-impulsionamentos-eleicoes
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q
node --test tests/js/*.test.js    # testes do site; precisa de Node 22+ (a forma `node --test tests/js` falha no Node 24)
```

Os testes rodam offline e levam poucos segundos. Para rodar o pipeline com dados reais, veja o [guia de uso](docs/uso.md). Antes de mexer no código, leia [como o projeto funciona](docs/como-funciona.md).

## Onde ajudar

| Tarefa | Precisa de | Como começar |
| --- | --- | --- |
| **Validar a classificação em outro estado** | olhar planilhas, sem programar | rode `gastos validar --uf XX` (a [checagem automática](docs/metodologia.md#validação-por-estado-checagem-automática)) e siga o passo a passo de [como validar](docs/metodologia.md#como-validar-um-estado-novo); abra uma issue com os achados |
| **Decidir a regra dos honorários de agência** | opinião fundamentada | veja os números em [docs/metodologia.md](docs/metodologia.md#o-que-o-método-ainda-erra-conhecido) (cerca de R$ 6,7 milhões de periferia incerta) e comente na issue |
| **Melhorar o site** | HTML/JS | leia [docs/site-e-publicacao.md](docs/site-e-publicacao.md); acessibilidade, celular e textos são bem-vindos; rode `node --test tests/js/*.test.js` |
| **Rotina agendada de atualização** | GitHub Actions | baixar o TSE, rodar `gastos publicar` e abrir um PR com `site/data/` (veja [como atualizar](docs/site-e-publicacao.md#como-atualizar-os-dados)) |
| **Verificar os links das prestações** | uma rede que o portal do TSE aceite | rode `scripts/verificar_links.py` (veja o [guia de uso](docs/uso.md#links-da-prestação-de-contas-o-que-é-verificado-e-o-que-não-é)) e envie o YAML atualizado |
| **Achar fontes oficiais de contato de parlamentares** | pesquisa | o TSE não publica e-mail de candidato (`DS_EMAIL` vem "NÃO DIVULGÁVEL"); procure canais oficiais (por exemplo das casas legislativas) e abra uma issue com a fonte, sem colar contatos pessoais |
| **Melhorar documentação e testes** | qualquer pessoa | sempre bem-vindo |

Se não tiver certeza por onde começar, abra uma issue descrevendo o que você gostaria de fazer.

## Etiquetas das issues

| Etiqueta | Uso |
| --- | --- |
| `erro-de-dados` | número, nome ou texto incorreto no site ou nos dados (formulário "Reportar erro") |
| `feature` | ideia de funcionalidade nova |
| `question` | decisão em aberto, que precisa de discussão |
| `help wanted`, `good first issue` | onde a ajuda é mais bem-vinda, e boas primeiras tarefas |
| `accessibility` | barreiras de acessibilidade |

## Fluxo de trabalho

1. Abra uma **issue** (ou comente numa existente) antes de mudanças grandes.
2. Crie uma branch a partir da `main` (`feat/...`, `fix/...`, `docs/...`).
3. Faça mudanças pequenas e focadas, com commits claros.
4. Rode `.venv/bin/pytest -q` e `node --test tests/js/*.test.js`. O CI roda os mesmos testes no pull request.
5. Abra o **pull request** explicando o quê e por quê. Mudanças de regra ou de texto precisam dos números antes e depois.

## Padrões de código

- **Teste primeiro.** Todo comportamento novo tem um teste que falha antes da mudança. Os testes **não** podem usar rede nem os arquivos grandes; use `tests/fixtures/` e simule downloads.
- **Código e textos em português** (nomes de dados do TSE ficam como no original); mensagens de erro claras, que digam o que a pessoa deve fazer.
- Siga o estilo dos módulos vizinhos; evite abstração antes de precisar.
- **Nunca adivinhe um dado:** se não dá para verificar (um link, um nome, um número), o código deve dizer "indisponível" e registrar um aviso.

## Regras de conteúdo (importantes)

Estas regras vêm do desenho do projeto e não mudam sem discussão aberta:

- O corpo dos e-mails **não cita candidatos nem partidos**, não diz "dinheiro público" e informa que os dados são parciais e a data deles. Nomes só aparecem no anexo de amostra.
- O número principal é `confirmado + generico`; o `confirmado` aparece sempre como piso; o `provavel` nunca entra no número principal.
- **Nada é enviado automaticamente**: o projeto gera rascunhos para uma pessoa revisar e enviar.
- Não versione dados baixados (`data/raw/`), saídas (`out/`) nem páginas geradas com nomes de candidatos (`divulgacao/`). Não inclua dados pessoais de contatos reais; use dados fictícios, como em `contatos.exemplo.csv`.
- Nunca escreva "dinheiro público" sem o percentual medido e as ressalvas da [metodologia](docs/metodologia.md#fonte-do-dinheiro-parte-paga-com-fundos-públicos).
- Mudar uma regra de classificação (`config/plataformas.yaml`) exige **evidência**: as linhas de despesa que justificam, os valores e o efeito no total antes e depois.

## Dados de pessoas

O site lista os **5 maiores valores declarados por recorte, pelo nome**, sem partido e com linguagem neutra ("Maiores valores declarados"; nunca "piores" ou "gastadores"). É dado público, mas cita pessoas reais, então:

- **Não adicione partido, CPF, e-mail, telefone ou qualquer dado de contato** ao site, aos JSON ou ao repositório. Há um teste que barra o partido nos JSON.
- Mantenha o texto neutro e com a ressalva de que o valor inclui impulsionamento sem plataforma citada e de que não é lista de irregularidades.
- Correções chegam pelo canal público: [issues do repositório](https://github.com/ramondomiingos/gastos-impulsionamentos-eleicoes/issues). Responda rápido e corrija.

## Segurança e privacidade

- Não inclua senhas, tokens nem endereços de e-mail pessoais no repositório.
- Dados baixados são tratados como não confiáveis: o código só lê, nunca executa nada vindo deles.
- Ao reportar um problema de segurança, não abra uma issue pública: fale diretamente com o mantenedor.

## Licença

O projeto usa a licença [MIT](LICENSE). Ao contribuir, você concorda que sua contribuição seja distribuída sob essa licença.
