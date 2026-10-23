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
```

Os testes rodam offline e levam poucos segundos. Para rodar o pipeline com dados reais, veja o [guia de uso](docs/uso.md). Antes de mexer no código, leia [como o projeto funciona](docs/como-funciona.md).

## Onde ajudar

| Tarefa | Precisa de | Como começar |
| --- | --- | --- |
| **Validar a classificação em outro estado** | olhar planilhas, sem programar | siga o passo a passo de [docs/metodologia.md](docs/metodologia.md#como-validar-um-estado-novo) e abra uma issue com os achados |
| **Decidir a regra dos honorários de agência** | opinião fundamentada | veja os números em [docs/metodologia.md](docs/metodologia.md#o-que-o-método-ainda-erra-conhecido) e comente na issue |
| **Verificar os links das prestações** | uma rede que o portal do TSE aceite | rode `scripts/verificar_links.py` (veja o [guia de uso](docs/uso.md#links-da-prestação-de-contas-o-que-é-verificado-e-o-que-não-é)) e envie o YAML atualizado |
| **Construir o site estático** | HTML/JS | leia [docs/site-e-publicacao.md](docs/site-e-publicacao.md) |
| **Criar `gastos publicar`** (exportar JSON) | Python/pandas | siga o estilo de `report.py` e escreva os testes antes |
| **Melhorar documentação e testes** | qualquer pessoa | sempre bem-vindo |

Se não tiver certeza por onde começar, abra uma issue descrevendo o que você gostaria de fazer.

## Fluxo de trabalho

1. Abra uma **issue** (ou comente numa existente) antes de mudanças grandes.
2. Crie uma branch a partir da `main` (`feat/...`, `fix/...`, `docs/...`).
3. Faça mudanças pequenas e focadas, com commits claros.
4. Rode `.venv/bin/pytest -q`. O CI roda os mesmos testes no pull request.
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
- Mudar uma regra de classificação (`config/plataformas.yaml`) exige **evidência**: as linhas de despesa que justificam, os valores e o efeito no total antes e depois.

## Segurança e privacidade

- Não inclua senhas, tokens nem endereços de e-mail pessoais no repositório.
- Dados baixados são tratados como não confiáveis: o código só lê, nunca executa nada vindo deles.
- Ao reportar um problema de segurança, não abra uma issue pública: fale diretamente com o mantenedor.

## Licença

Ainda não há licença definida; ela será escolhida pelo mantenedor. Ao contribuir, você concorda que sua contribuição seja distribuída sob a licença que o projeto adotar.
