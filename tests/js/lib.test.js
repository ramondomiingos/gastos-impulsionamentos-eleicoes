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

test("escapeHtml", () => {
  assert.equal(Lib.escapeHtml(`<b>&"'`), "&lt;b&gt;&amp;&quot;&#39;");
  assert.equal(Lib.escapeHtml(null), "");
  assert.equal(Lib.escapeHtml(5), "5");
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
