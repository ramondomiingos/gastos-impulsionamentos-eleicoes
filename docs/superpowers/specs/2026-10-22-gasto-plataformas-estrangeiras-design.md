# Análise do gasto de campanhas com plataformas de anúncio estrangeiras: desenho

Data: 2026-10-22. Dono: Ramon Domingos.

## Intenção

Campanhas eleitorais brasileiras gastam muito dinheiro público (Fundo Especial de Financiamento de Campanha e fundo partidário) com impulsionamento de conteúdo em redes sociais. Todas as redes que existem para isso são estrangeiras (Meta, Google/YouTube, X, TikTok). Esse dinheiro sai do país e quase não gera emprego aqui.

O Ramon quer **medir** quanto foi gasto e **usar o número** em e-mails a deputados e senadores eleitos. Cada e-mail faz um pedido: criar um teto para esse tipo de gasto. O que importa no resultado: o parlamentar entende o problema e quer ajudar a resolvê-lo. Um número simples, fácil de repetir e difícil de contestar vale mais que uma tabela enorme.

## Objetivos

1. Pipeline repetível que baixa os dados oficiais do TSE e calcula o gasto com plataformas estrangeiras de anúncio.
2. O recorte é um parâmetro: estado, cargo, partido, candidato. Começa pelo RN. Depois outros estados e regiões, e por fim o país.
3. Cada número publicado pode ser conferido: existe um arquivo com as linhas que o compõem.
4. Geração de e-mails a partir de modelos, com os números do **estado do destinatário**.
5. Os números aparecem como valor absoluto e como proporção do gasto total da campanha. A proporção sustenta um teto percentual.

## Não objetivos

- Medir qualquer gasto com empresa de fora do país. Só plataformas de anúncio estrangeiras entram (decisão do Ramon).
- Raspar o site de divulgação do TSE. Há dados abertos oficiais.
- Enviar e-mails. O pipeline gera textos, o Ramon revisa e envia.
- Análise nacional agora. Se for necessária, o Ramon volta a pedir. O pipeline já aceita o recorte nacional, mas os e-mails são estaduais.
- Julgar a legalidade dos gastos. O pedido é um teto futuro, não uma denúncia.

## Anti-objetivos (seria um fracasso mesmo que o código funcione)

- Um número que um assessor derrube em 5 minutos: dupla contagem, ruído (agências, nomes de empresas parecidos) ou classificação sem critério.
- Esconder que os dados são parciais.
- Apresentar o nível "provável" como se fosse certo.
- Texto que soa como acusação a candidatos ou partidos específicos.

## Restrições e fatos sobre os dados (verificados em 2026-10-22)

- Fonte: portal de dados abertos do TSE, conjunto "Prestação de Contas Eleitorais - 2026". Arquivo: `https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2026.zip` (209 MB). Existe um CSV por UF e um BRASIL; BRASIL = soma das UFs + "BR" (candidaturas nacionais). Conferido: 1.078.728 linhas e 14.956 candidatos com despesa, iguais nos dois lados.
- Os dados são de prestação **parcial** (datas de 13/09 e 03/10/2026), gerados em 22/10/2026. A final ainda virá. Os e-mails devem dizer que os números são parciais.
- Formato: `;` como separador, latin-1, decimal com vírgula (`2500,00`). O BRASIL tem 2 bytes nulos soltos, que o leitor precisa remover.
- Arquivos de despesa:
  - `despesas_contratadas_candidatos_2026_<UF>.csv`: tem candidato, cargo, partido, fornecedor (`NM_FORNECEDOR_RFB`, CNPJ), `DS_DESPESA`, `DS_ORIGEM_DESPESA` e `VR_DESPESA_CONTRATADA`.
  - `despesas_pagas_candidatos_2026_<UF>.csv`: sem nome de candidato nem fornecedor. Liga-se por `SQ_PRESTADOR_CONTAS` e `SQ_DESPESA`.
- Linhas de preenchimento: `SQ_DESPESA = -1` e `#NULO` marcam candidatos sem despesa. Descartar.
- Há dois campos úteis para classificar: `DS_ORIGEM_DESPESA` (existe o valor "Despesa com Impulsionamento de Conteúdos") e `DS_DESPESA` (texto livre).
- Teste no RN: 244 candidatos, R$ 93,5 milhões contratados no total. Uma busca ampla por palavras de anúncio deu R$ 4,7 milhões. Esse valor **não é** o resultado, porque inclui ruído de agências.
- Caso importante: parte do dinheiro passa por intermediários com CNPJ brasileiro (`FACEBOOK SERVICOS ONLINE DO BRASIL LTDA.`, `DLOCAL BRASIL INSTITUICAO DE PAGAMENTO S.A.`, `EBANX PAGAMENTOS LTDA`). Classificar só pelo fornecedor perde esses gastos.
- O CPF de candidatos vem mascarado (`-4`). O identificador do candidato é `SQ_CANDIDATO`.

## Decisões do Ramon

- Só plataformas de anúncio estrangeiras: Meta, Google, X, TikTok.
- Todo "impulsionamento" conta como plataforma estrangeira, porque não existe rede social nacional para isso.
- Gateways internacionais com CNPJ brasileiro podem esconder o gasto, e isso deve ser tratado.
- Usar os dados parciais agora, dizendo isso no e-mail.
- Várias visões: por estado, cargo, partido e candidato.
- E-mails com os números do estado do destinatário, para mais de um parlamentar.
- A destinatária/destinatário final é gente eleita (senadores e deputados). O Ramon fornece a lista e os contatos.

## Escolhas minhas (o Ramon ainda não confirmou)

- Python com pandas, linha de comando, dados baixados para `data/raw/` (fora do versionamento).
- Três níveis de classificação, cada gasto em exatamente um deles:
  1. **Confirmado:** fornecedor é a plataforma, ou a descrição cita a plataforma.
  2. **Impulsionamento genérico:** `DS_ORIGEM_DESPESA` é impulsionamento e a plataforma não é citada.
  3. **Provável:** passou por gateway de pagamento com descrição vaga. Separado dos outros.
- Regras de classificação em arquivo de configuração (palavras e fornecedores), não no código.
- Base principal: despesas **contratadas**. As pagas servem de conferência. Nunca somar as duas.
- Saídas em CSV e Markdown. E-mails a partir de modelos, em Markdown ou texto.

## Deixado para quem for construir

- Estrutura de pastas, nomes dos módulos, interface de linha de comando.
- Como evitar dupla contagem entre linhas, por exemplo o mesmo `SQ_DESPESA` repetido por parcelamento.
- Como obter a lista de eleitos. A eleição foi em 04/10/2026. O TSE tem dados de resultados, que ainda não foram verificados.
- Textos dos modelos de e-mail, em tom sóbrio e objetivo, em português.
- Testes para as regras de classificação, com exemplos reais do RN, incluindo os falsos positivos.
- Um relatório de qualidade que mostra quanto ficou em cada nível e uma amostra de linhas para revisão manual.

## Decisões tomadas após a revisão do desenho (minhas, marcadas para conferência)

- **Número principal do e-mail:** níveis 1 + 2 (confirmado + impulsionamento genérico), seguindo a regra do Ramon de que todo impulsionamento é plataforma estrangeira. O nível 1 aparece sempre ao lado como piso ("pelo menos X confirmados"). O nível 3 (provável) fica fora do número principal e aparece só em nota.
- **Linhas que contam:** só despesas de candidatos (o conjunto é de candidatos). Despesas de órgãos partidários ficam fora desta versão, e o texto não deve sugerir que cobrem o partido. Estornos e devoluções, se existirem nos dados, são tratados e documentados pelo builder.
- **Lista de eleitos:** vem dos dados de resultado do TSE. O Ramon fornece só os contatos (nome, cargo, UF, e-mail), em CSV. A ligação é por nome + UF + cargo, com conferência manual dos casos ambíguos.
- **O que o e-mail diz sobre o destinatário:** só números do estado e do cargo no nível agregado. Não cita campanha, partido ou gasto do próprio destinatário, para não soar como acusação.
- **Atualização:** os números levam a data de corte dos dados. Cada execução salva uma versão datada, para comparar com a prestação final quando sair.
- **Fonte do dinheiro:** o campo `DS_FONTE_DESPESA` (por exemplo, Fundo Especial de Financiamento de Campanha) existe só nos arquivos de despesas **pagas**, não nos contratados. O pipeline calcula o recorte por fonte a partir das pagas, e o builder avalia a cobertura.

## Respostas do Ramon às perguntas em aberto

- **Pedido do e-mail:** um **teto percentual** do gasto de campanha com plataformas estrangeiras, e um convite ao parlamentar para ajudar a resolver. O e-mail não acusa ninguém. Consequência para o builder: o pipeline calcula, por estado e por cargo, a proporção (gasto em plataformas estrangeiras ÷ gasto total contratado) e a distribuição dessa proporção entre candidatos (mediana, percentis, quantos candidatos passam de certos percentuais). O e-mail pode mostrar o que cada percentual de teto teria afetado. A escolha do percentual proposto é do Ramon e entra como parâmetro do modelo, não como valor fixo no código.
- **Base do número:** **todo o gasto da campanha**, sem separar dinheiro público de doações. O texto do e-mail não deve dizer "dinheiro público". Base: despesas contratadas. O recorte por fonte (campo `DS_FONTE_DESPESA`, que só existe nas despesas pagas) fica como extra opcional, fora do e-mail por enquanto.

## Perguntas em aberto

Nenhuma. Falta a aprovação do Ramon sobre este documento.
