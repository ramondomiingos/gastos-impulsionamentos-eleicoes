const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Lib = require("../../site/lib.js");

const fx = (n) => JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", n), "utf8"));
const indice = fx("index.json");
const rn = fx("RN.json");
const semPago = fx("RN_sem_pago.json");
const vazio = fx("RN_vazio.json");
const br = fx("BR.json");
const hostil = fx("RN_hostil.json");
const turno2 = fx("RN_turno2.json");
const HOSTIL = `<img src=x onerror=alert(1)> & "Zé" O'Brien`;

test("formatBRL", () => {
  assert.equal(Lib.formatBRL(363000), "R$ 363.000");
  assert.equal(Lib.formatBRL(0), "R$ 0");
  assert.equal(Lib.formatBRL(19662447.54), "R$ 19.662.448");
  assert.equal(Lib.formatBRL(999.4), "R$ 999");
});

test("formatPct", () => {
  assert.equal(Lib.formatPct(0.12), "12,0%");
  assert.equal(Lib.formatPct(0.119661), "12,0%");
  assert.equal(Lib.formatPct(1), "100,0%");
  assert.equal(Lib.formatPct(0), "0,0%");
});

test("hero", () => {
  assert.deepEqual(Lib.hero(574064.22), { valor: "R$ 574", unidade: " mil" });
  assert.deepEqual(Lib.hero(20425733), { valor: "R$ 20,4", unidade: " mi" });
  assert.deepEqual(Lib.hero(500), { valor: "R$ 500", unidade: "" });
  assert.deepEqual(Lib.hero(999600), { valor: "R$ 1,0", unidade: " mi" });
  assert.deepEqual(Lib.hero(99940000), { valor: "R$ 99,9", unidade: " mi" });
  assert.deepEqual(Lib.hero(99960000), { valor: "R$ 100", unidade: " mi" });
  assert.deepEqual(Lib.hero(100000000), { valor: "R$ 100", unidade: " mi" });
  assert.deepEqual(Lib.hero(105219594.91), { valor: "R$ 105", unidade: " mi" });
  assert.deepEqual(Lib.hero(1200000000), { valor: "R$ 1,2", unidade: " bi" });
});

test("parseHash valido", () => {
  const ufs = ["BR", "RN", "DF"];
  const cargos = { BR: ["presidente"], RN: ["todos", "governador"], DF: ["todos", "deputado-distrital"] };
  assert.deepEqual(Lib.parseHash("#RN/governador", ufs, cargos), { uf: "RN", cargo: "governador" });
  assert.deepEqual(Lib.parseHash("#rn/Governador", ufs, cargos), { uf: "RN", cargo: "governador" });
  assert.deepEqual(Lib.parseHash("#BR", ufs, cargos), { uf: "BR", cargo: "presidente" });
});

test("parseHash invalido cai para recorte valido", () => {
  const ufs = ["BR", "RN"];
  const cargos = { BR: ["presidente"], RN: ["todos", "governador"] };
  assert.deepEqual(Lib.parseHash("", ufs, cargos), { uf: "BR", cargo: "presidente" });
  assert.deepEqual(Lib.parseHash(undefined, ufs, cargos), { uf: "BR", cargo: "presidente" });
  assert.deepEqual(Lib.parseHash("#XX/governador", ufs, cargos), { uf: "BR", cargo: "presidente" });
  assert.deepEqual(Lib.parseHash("#RN/prefeito", ufs, cargos), { uf: "RN", cargo: "todos" });
  assert.deepEqual(Lib.parseHash("#BR/governador", ufs, cargos), { uf: "BR", cargo: "presidente" });
  assert.deepEqual(Lib.parseHash("#RN/%E0%A4%A", ufs, cargos), { uf: "RN", cargo: "todos" });
  assert.deepEqual(Lib.parseHash("#__proto__/x", ufs, cargos), { uf: "BR", cargo: "presidente" });
});

test("buildHash", () => {
  assert.equal(Lib.buildHash("PB", "governador"), "#PB/governador");
  assert.equal(Lib.buildHash("BR", "presidente"), "#BR/presidente");
});

const todosTexto = (m) => JSON.stringify(m).toLowerCase();

test("modeloCards todos: 5 cards, por cargo, top de 5 nomes", () => {
  const m = Lib.modeloCards(rn, "todos", indice);
  assert.equal(m.cards.length, 5);
  assert.deepEqual(m.cards.map((c) => c.tipo), ["gancho", "barras", "top", "tetos", "cta"]);
  assert.equal(m.cards[0].hero.valor.startsWith("R$"), true);
  assert.deepEqual(m.cards[1].linhas.map((l) => l.rotulo), ["Governo", "Senado"]);
  assert.equal(m.cards[2].linhas.length, 5);
  assert.equal(m.cards[2].vazio, false);
  assert.equal(m.cards[3].linhas.length, 3);
  assert.deepEqual(m.cards[3].linhas.map((l) => l.teto), ["5%", "10%", "20%"]);
});

test("modeloCards por cargo: confirmado versus sem plataforma citada", () => {
  const m = Lib.modeloCards(rn, "governador", indice);
  assert.equal(m.cards[0].hero.valor, "R$ 574");
  assert.equal(m.cards[0].hero.unidade, " mil");
  const rotulos = m.cards[1].linhas.map((l) => l.rotulo);
  assert.equal(rotulos.length, 2);
  assert.match(rotulos[0], /Confirmado/);
  assert.match(rotulos[1], /sem plataforma citada/);
  assert.equal(m.cards[1].linhas[0].valor, "R$ 423.864");
  assert.equal(m.cards[2].linhas[0].nome, "Carlos Eduardo Xavier");
  assert.equal(m.cards[3].linhas[0].texto.includes("1 de 3"), true);
});

test("modeloCards Brasil/presidente", () => {
  const m = Lib.modeloCards(br, "presidente", indice);
  assert.equal(m.cards[0].hero.valor, "R$ 20,4");
  assert.equal(m.cards.length, 5);
});

test("modeloCards com top vazio", () => {
  const m = Lib.modeloCards(vazio, "senador", indice);
  assert.equal(m.cards.length, 5);
  assert.equal(m.cards[2].vazio, true);
  assert.equal(m.cards[2].linhas.length, 0);
  assert.ok(m.cards[2].textoVazio.length > 10);
  assert.equal(m.cards[3].vazio, true);
  assert.equal(m.cards[1].linhas.every((l) => l.largura === 0), true);
  assert.doesNotMatch(todosTexto(m), /undefined|nan|null/);
});

test("modeloCards: aviso de dados parciais e datas em todos os cards", () => {
  const m = Lib.modeloCards(rn, "todos", indice);
  for (const c of m.cards) {
    assert.match(c.rodape, /parciais/i);
    assert.match(c.rodape, /22\/10\/2026/);
  }
});

test("modeloCards: nenhum card cita partido nem dinheiro publico", () => {
  for (const [d, k] of [[rn, "todos"], [rn, "governador"], [semPago, "todos"], [vazio, "senador"], [br, "presidente"]]) {
    const t = todosTexto(Lib.modeloCards(d, k, indice));
    assert.doesNotMatch(t, /partido/);
    assert.doesNotMatch(t, /dinheiro p.blico/);
    assert.doesNotMatch(t, /undefined/);
  }
});

test("modeloCards funciona sem os campos pago*", () => {
  const m = Lib.modeloCards(semPago, "todos", indice);
  assert.equal(m.cards.length, 5);
});

test("modeloCards cargo inexistente nao quebra", () => {
  const m = Lib.modeloCards(rn, "deputado-distrital", indice);
  assert.equal(m.cards.length, 5);
  assert.equal(m.cards[2].vazio, true);
});

test("fontePublica: com e sem campos", () => {
  const com = Lib.fontePublica(rn.recortes.governador);
  assert.equal(com.pct, "71,6%");
  assert.equal(com.cobertura, "100,0%");
  assert.equal(Lib.fontePublica(semPago.recortes.governador), null);
  assert.equal(Lib.fontePublica(vazio.recortes.senador), null);
});

test("cargosGlobais: Presidente primeiro, depois Todos e os demais na ordem", () => {
  assert.deepEqual(Lib.cargosGlobais(indice), ["presidente", "todos", "governador", "senador", "deputado-federal", "deputado-estadual", "deputado-distrital"]);
  const so = { ufs: [{ uf: "BR", cargos: ["presidente"] }, { uf: "AC", cargos: ["todos", "senador"] }] };
  assert.deepEqual(Lib.cargosGlobais(so), ["presidente", "todos", "senador"]);
});

test("ufsParaCargo", () => {
  assert.deepEqual(Lib.ufsParaCargo(indice, "presidente").map((u) => u.uf), ["BR"]);
  assert.deepEqual(Lib.ufsParaCargo(indice, "deputado-distrital").map((u) => u.uf), ["DF"]);
  const g = Lib.ufsParaCargo(indice, "governador").map((u) => u.uf);
  assert.deepEqual(g, ["DF", "RN"]);
  assert.equal(g.includes("BR"), false);
  assert.deepEqual(Lib.ufsParaCargo(indice, "inexistente"), []);
});

test("ufsParaCargo ordena por nome (pt-BR)", () => {
  const i = { ufs: [{ uf: "BR", nome: "Brasil", cargos: ["presidente"] }, { uf: "SP", nome: "São Paulo", cargos: ["todos"] }, { uf: "AC", nome: "Acre", cargos: ["todos"] }, { uf: "AP", nome: "Amapá", cargos: ["todos"] }] };
  assert.deepEqual(Lib.ufsParaCargo(i, "todos").map((u) => u.uf), ["AC", "AP", "SP"]);
});

test("escolherUf: mantém a UF quando serve; senão a primeira válida", () => {
  assert.deepEqual(Lib.escolherUf(indice, "RN", "governador"), { uf: "RN", mudou: false });
  assert.deepEqual(Lib.escolherUf(indice, "RN", "presidente"), { uf: "BR", mudou: true });
  assert.deepEqual(Lib.escolherUf(indice, "RN", "deputado-distrital"), { uf: "DF", mudou: true });
  assert.deepEqual(Lib.escolherUf(indice, "BR", "governador"), { uf: "DF", mudou: true });
  assert.deepEqual(Lib.escolherUf(indice, "BR", "presidente"), { uf: "BR", mudou: false });
});

const juntar = (segs) => segs.map((s) => s.t).join("");

test("importaSegmentos com pago*: frase de fundos medida, sem palavras de magnitude", () => {
  const t = juntar(Lib.importaSegmentos(rn.recortes.governador));
  assert.match(t, /As campanhas usam dinheiro público \(Fundo Eleitoral e Fundo Partidário\) para pagar anúncios\./);
  assert.match(t, /No recorte escolhido, 71,6% do valor já pago em impulsionamento saiu desses fundos \(cobertura de 100,0% do contratado\)\./);
  assert.match(t, /Na nossa visão.*empregam pouco no país/);
  assert.doesNotMatch(t, /\. Esse dinheiro vai para plataformas estrangeiras que empregam/);
  assert.doesNotMatch(t, /grande parte|maior parte/);
  const fortes = Lib.importaSegmentos(rn.recortes.governador).filter((s) => s.forte).map((s) => s.t);
  assert.deepEqual(fortes, ["dinheiro público", "71,6%"]);
});

test("importaSegmentos com pct_publico baixo (48%) não afirma magnitude", () => {
  const r = Object.assign({}, br.recortes.presidente, { pct_publico: 0.48, pago: 1000, cobertura_pago: 0.9 });
  const t = juntar(Lib.importaSegmentos(r));
  assert.match(t, /48,0% do valor já pago/);
  assert.doesNotMatch(t, /grande parte|maior parte|maioria/);
});

test("importaSegmentos sem pago*: sem número, sem dinheiro público e sem magnitude", () => {
  const t = juntar(Lib.importaSegmentos(semPago.recortes.governador));
  assert.match(t, /Esse dinheiro vai para plataformas estrangeiras\./);
  assert.match(t, /Na nossa visão/);
  assert.doesNotMatch(t, /dinheiro público|%|grande parte|maior parte|undefined/);
  assert.doesNotMatch(juntar(Lib.importaSegmentos(undefined)), /undefined|dinheiro público/);
});

test("fonteHero: encolhe só quando precisa", () => {
  assert.equal(Lib.fonteHero(Lib.hero(20425733)), 210);
  assert.equal(Lib.fonteHero(Lib.hero(105219594)), 210);
  assert.equal(Lib.fonteHero(Lib.hero(574064)), 210);
  const longo = { valor: "R$ 123.456.789", unidade: " mi" };
  const f = Lib.fonteHero(longo);
  assert.ok(f < 210 && f >= 60);
});

test("tagFraca", () => {
  assert.equal(Lib.tagFraca({ principal: 100, confirmado: 0 }), "valor todo sem plataforma citada na nota");
  assert.equal(Lib.tagFraca({ principal: 100, confirmado: 20 }), "mais da metade sem plataforma citada");
  assert.equal(Lib.tagFraca({ principal: 100, confirmado: 49.9 }), "mais da metade sem plataforma citada");
  assert.equal(Lib.tagFraca({ principal: 100, confirmado: 50 }), null);
  assert.equal(Lib.tagFraca({ principal: 100, confirmado: 90 }), null);
  assert.equal(Lib.tagFraca({ principal: 0, confirmado: 0 }), null);
  assert.equal(Lib.tagFraca({}), null);
});

test("modeloCards: card 3 traz a tag de apoio fraco", () => {
  const m = Lib.modeloCards(rn, "governador", indice);
  const l = m.cards[2].linhas;
  assert.equal(l[0].tag, null); // Carlos: 333k de 363k
  assert.equal(l[1].tag, "valor todo sem plataforma citada na nota"); // Álvaro: confirmado 0
});

test("nenhum texto renderizável contém partido (campos de partido nos dados são ignorados)", () => {
  assert.ok(JSON.stringify(rn).includes("ZZPARTIDO"), "fixture precisa ter partido");
  for (const [d, k] of [[rn, "todos"], [rn, "governador"], [rn, "senador"], [br, "presidente"], [vazio, "senador"], [semPago, "todos"]]) {
    const t = JSON.stringify(Lib.modeloCards(d, k, indice));
    assert.doesNotMatch(t, /ZZPARTIDO/);
    assert.doesNotMatch(t.toLowerCase(), /partido\b/);
  }
  const fs2 = fs.readFileSync(path.join(__dirname, "../../site/app.js"), "utf8");
  assert.doesNotMatch(fs2, /partido/i);
});

test("nome hostil permanece texto inerte no modelo e app.js nunca usa innerHTML", () => {
  const m = Lib.modeloCards(hostil, "governador", indice);
  assert.equal(m.cards[2].linhas[0].nome, HOSTIL);
  const app = fs.readFileSync(path.join(__dirname, "../../site/app.js"), "utf8");
  assert.doesNotMatch(app, /innerHTML|outerHTML|insertAdjacentHTML|document\.write/);
  assert.equal(Lib.escapeHtml, undefined);
});

test("caminhoUf: UF fora do índice nunca vira caminho de fetch", () => {
  assert.equal(Lib.caminhoUf(indice, "RN"), "RN.json");
  assert.equal(Lib.caminhoUf(indice, "BR"), "BR.json");
  assert.equal(Lib.caminhoUf(indice, "XX"), null);
  assert.equal(Lib.caminhoUf(indice, "../index"), null);
  assert.equal(Lib.caminhoUf(indice, "rn"), null);
  assert.equal(Lib.caminhoUf(indice, undefined), null);
  assert.equal(Lib.caminhoUf(indice, "__proto__"), null);
});

test("avisoTrocaUf", () => {
  const BR = { uf: "BR", nome: "Brasil" }, AC = { uf: "AC", nome: "Acre" }, DF = { uf: "DF", nome: "Distrito Federal" }, PB = { uf: "PB", nome: "Paraíba" };
  assert.equal(Lib.avisoTrocaUf(AC, AC, "governador", "Governador"), "");
  assert.match(Lib.avisoTrocaUf(BR, AC, "governador", "Governador"), /Escolha um estado/);
  assert.match(Lib.avisoTrocaUf(BR, AC, "governador", "Governador"), /Acre/);
  assert.doesNotMatch(Lib.avisoTrocaUf(BR, AC, "governador", "Governador"), /não existe/);
  assert.match(Lib.avisoTrocaUf(PB, BR, "presidente", "Presidente"), /nacional/);
  assert.match(Lib.avisoTrocaUf(PB, DF, "deputado-distrital", "Deputado distrital"), /só existe no Distrito Federal|existe só no Distrito Federal/);
  assert.match(Lib.avisoTrocaUf(BR, DF, "deputado-distrital", "Deputado distrital"), /Distrito Federal/);
});

test("enderecoDoSite", () => {
  assert.equal(Lib.enderecoDoSite("gastos-eleicoes.netlify.app"), "gastos-eleicoes.netlify.app");
  assert.equal(Lib.enderecoDoSite("radar.exemplo.org.br"), "radar.exemplo.org.br");
  assert.equal(Lib.enderecoDoSite("RADAR.Exemplo.org"), "radar.exemplo.org");
  for (const h of ["localhost", "localhost:8765", "127.0.0.1", "127.0.0.1:8000", "", null, undefined, "a b.com", "<x>.com", "evil.com/x", "http://x.com", "semponto", "[::1]", "x.com?a=1"]) {
    assert.equal(Lib.enderecoDoSite(h), Lib.ENDERECO_PADRAO, String(h));
  }
  assert.equal(Lib.ENDERECO_PADRAO, "radar-impulsionamento.netlify.app");
});

test("modeloCards: todos os cards trazem o endereço; o card 5 também", () => {
  const m = Lib.modeloCards(rn, "todos", indice);
  for (const c of m.cards) assert.equal(c.endereco, Lib.ENDERECO_PADRAO);
  const m2 = Lib.modeloCards(rn, "todos", indice, { endereco: "meu.site.com" });
  for (const c of m2.cards) assert.equal(c.endereco, "meu.site.com");
});

test("card 5: convite para o site, sem perfil pessoal", () => {
  const c = Lib.modeloCards(rn, "todos", indice, { endereco: "meu.site.com" }).cards[4];
  assert.equal(c.tipo, "cta");
  assert.equal(c.endereco, "meu.site.com");
  assert.equal(c.titulo, "Quer ver os números do seu estado?");
  assert.match(c.texto, /Escolha o estado e o cargo/);
  assert.match(c.projeto, /contribua no GitHub/);
  assert.equal(c.hashtag, "#TetoNoImpulsionamento");
  const j = JSON.stringify(c).toLowerCase();
  assert.doesNotMatch(j, /@|perfil/);
});

test("app.js e index.html não têm mais perfil pessoal nem localStorage", () => {
  const app = fs.readFileSync(path.join(__dirname, "../../site/app.js"), "utf8");
  const html = fs.readFileSync(path.join(__dirname, "../../site/index.html"), "utf8");
  assert.doesNotMatch(app + html, /perfil|localStorage/i);
});

test("modoArquivoLocal", () => {
  assert.equal(Lib.modoArquivoLocal("file:"), true);
  assert.equal(Lib.modoArquivoLocal("http:"), false);
  assert.equal(Lib.modoArquivoLocal("https:"), false);
  assert.equal(Lib.modoArquivoLocal(undefined), false);
});

test("fonteEndereco: uma linha para endereços curtos e longos", () => {
  assert.equal(Lib.fonteEndereco("a.com.br"), 72);
  const f = Lib.fonteEndereco(Lib.ENDERECO_PADRAO);
  assert.ok(f >= 40 && f < 72);
  assert.ok(Lib.fonteEndereco("x".repeat(80) + ".com") >= 34);
});

test("nomes sempre visíveis, inclusive com 2º turno em curso (decisão do dono)", () => {
  assert.equal(Lib.ocultarNomes, undefined);
  assert.equal(Lib.MSG_NOMES_OCULTOS, undefined);
  for (const [d, k] of [[turno2, "governador"], [turno2, "todos"], [turno2, "senador"], [br, "presidente"]]) {
    assert.ok(d.segundo_turno > 0);
    const m = Lib.modeloCards(d, k, indice);
    const nomes = d.recortes[k].top.map((x) => x.nome);
    assert.equal(nomes.length, 5);
    assert.deepEqual(m.cards[2].linhas.map((l) => l.nome), nomes);
    assert.equal(m.cards[2].vazio, false);
  }
});

test("formatarData", () => {
  assert.equal(Lib.formatarData("2026-10-23"), "23/10/2026");
  assert.equal(Lib.formatarData("2026-01-05"), "05/01/2026");
  for (const v of [undefined, null, "", "23/10/2026", "2026-13-01", "2026-10-32", "abc", "2026-10", 20261023, "2026-02-30"]) {
    assert.equal(Lib.formatarData(v), "data indisponível", String(v));
  }
});

test("rodapé dos cards traz a data de atualização do Radar", () => {
  const m = Lib.modeloCards(rn, "todos", indice);
  for (const c of m.cards) assert.match(c.rodape, /Radar atualizado em 23\/10\/2026/);
  const sem = Lib.modeloCards(rn, "todos", Object.assign({}, indice, { gerado_em: undefined }));
  for (const c of sem.cards) assert.doesNotMatch(c.rodape, /Radar atualizado/);
});
