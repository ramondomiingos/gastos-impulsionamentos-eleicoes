/* Funções puras do Radar do Impulsionamento (sem DOM). UMD: Node (testes) e navegador (window.Lib). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Lib = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var ORDEM_CARGOS = ["presidente", "governador", "senador", "deputado-federal", "deputado-estadual", "deputado-distrital"];
  var HASHTAG = "#TetoNoImpulsionamento";
  var TETOS_CARDS = [0.05, 0.1, 0.2];

  function num(x) {
    return typeof x === "number" && isFinite(x) ? x : 0;
  }

  function formatBRL(n) {
    var v = Math.round(num(n));
    return "R$ " + String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function formatPct(x) {
    return (num(x) * 100).toFixed(1).replace(".", ",") + "%";
  }

  /* Número grande do card 1: {valor: "R$ 574", unidade: " mil"}, {"R$ 20,4", " mi"}, {"R$ 105", " mi"} (sem decimal a partir de 100 mi), {"R$ 1,2", " bi"}. */
  function hero(n) {
    var v = num(n);
    if (v >= 1000000000) return { valor: "R$ " + (v / 1000000000).toFixed(1).replace(".", ","), unidade: " bi" };
    if (v >= 1000000 || Math.round(v / 1000) >= 1000) {
      var mi = v / 1000000;
      if (Number(mi.toFixed(1)) >= 100) return { valor: "R$ " + Math.round(mi), unidade: " mi" };
      return { valor: "R$ " + mi.toFixed(1).replace(".", ","), unidade: " mi" };
    }
    if (v >= 1000) return { valor: "R$ " + Math.round(v / 1000), unidade: " mil" };
    return { valor: formatBRL(v), unidade: "" };
  }

  /* Tamanho de fonte (px) do número grande para caber nos 904 px úteis do card (estimativa por caracteres). */
  function fonteHero(h) {
    var largura = String(h.valor).length * 0.5 + String(h.unidade).length * 0.22;
    return Math.max(60, Math.min(210, Math.floor(880 / largura)));
  }

  /* Tamanho de fonte (px) do endereço grande do card 5, para caber em uma linha de 904 px. */
  function fonteEndereco(e) {
    return Math.max(34, Math.min(72, Math.floor(880 / (String(e).length * 0.56))));
  }

  /* Marca neutra para valores pouco sustentados por plataforma citada. */
  function tagFraca(t) {
    var p = num(t && t.principal);
    if (!(p > 0)) return null;
    var c = num(t.confirmado);
    if (c === 0) return "valor todo sem plataforma citada na nota";
    if (c / p < 0.5) return "mais da metade sem plataforma citada";
    return null;
  }

  var ENDERECO_PADRAO = "radar-impulsionamento.netlify.app";

  /* Endereço do site para os cards: o host real, ou o padrão em localhost, arquivo local ou texto estranho. */
  function enderecoDoSite(host) {
    var h = String(host === null || host === undefined ? "" : host).toLowerCase();
    if (!/^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+(:\d+)?$/.test(h)) return ENDERECO_PADRAO;
    if (/^\d+(\.\d+){3}(:\d+)?$/.test(h) || /^localhost(\.|:|$)/.test(h)) return ENDERECO_PADRAO;
    return h;
  }

  /* Página aberta direto de um arquivo: o navegador bloqueia fetch() de arquivos locais. */
  function modoArquivoLocal(protocolo) {
    return protocolo === "file:";
  }

  var MSG_NOMES_OCULTOS = "Os nomes dos candidatos que ainda disputam o 2º turno ficam ocultos até o fim da votação (25/10/2026). Os números agregados deste recorte continuam disponíveis.";

  /* Com candidatos ainda no 2º turno, esconde nomes dos cargos que têm segundo turno (e da visão "todos"). */
  function ocultarNomes(dados, cargoKey) {
    var n = dados && dados.segundo_turno;
    if (typeof n !== "number" || !(n > 0)) return false;
    return cargoKey === "presidente" || cargoKey === "governador" || cargoKey === "todos";
  }

  /* "2026-10-23" -> "23/10/2026"; qualquer outra coisa -> "data indisponível". */
  function formatarData(iso) {
    var m = typeof iso === "string" && /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
    if (!m) return "data indisponível";
    var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    if (d.getUTCFullYear() !== +m[1] || d.getUTCMonth() !== +m[2] - 1 || d.getUTCDate() !== +m[3]) return "data indisponível";
    return m[3] + "/" + m[2] + "/" + m[1];
  }

  /* Caminho do JSON de uma UF, só se ela existe no índice. */
  function caminhoUf(indice, uf) {
    if (typeof uf !== "string") return null;
    var ok = ((indice && indice.ufs) || []).some(function (u) { return u.uf === uf; });
    return ok && /^[A-Z]{2}$/.test(uf) ? uf + ".json" : null;
  }

  function avisoTrocaUf(antiga, nova, cargo, rotulo) {
    if (!antiga || !nova || antiga.uf === nova.uf) return "";
    if (cargo === "presidente") return "Presidente é uma disputa nacional: o estado foi ajustado para " + nova.nome + ".";
    if (cargo === "deputado-distrital") return rotulo + " existe só no Distrito Federal: o estado foi ajustado para " + nova.nome + ".";
    if (antiga.uf === "BR") return "Escolha um estado: mostrando " + nova.nome + " por enquanto.";
    return "O cargo " + String(rotulo).toLowerCase() + " não existe em " + antiga.nome + ": o estado foi ajustado para " + nova.nome + ".";
  }

  function has(o, k) {
    return Object.prototype.hasOwnProperty.call(o, k);
  }

  /* Sempre devolve um recorte válido. ufsValidas: ["BR","AC",...]; cargosPorUf: {UF: [slugs]}. */
  function parseHash(hash, ufsValidas, cargosPorUf) {
    var padraoUf = ufsValidas.indexOf("BR") >= 0 ? "BR" : ufsValidas[0];
    var texto = String(hash || "").replace(/^#/, "");
    var partes = texto.split("/");
    var uf = decod(partes[0]).toUpperCase();
    if (ufsValidas.indexOf(uf) < 0 || !has(cargosPorUf, uf)) uf = padraoUf;
    var cargos = cargosPorUf[uf] || [];
    var cargo = decod(partes[1] || "").toLowerCase();
    if (cargos.indexOf(cargo) < 0) cargo = cargos[0];
    return { uf: uf, cargo: cargo };
  }

  function decod(s) {
    try {
      return decodeURIComponent(s);
    } catch (e) {
      return "";
    }
  }

  function buildHash(uf, cargo) {
    return "#" + uf + "/" + cargo;
  }

  /* Parcela paga com fundos públicos, ou null se os campos faltam ou nada foi pago. */
  function fontePublica(recorte) {
    if (!recorte) return null;
    var pago = recorte.pago;
    if (typeof pago !== "number" || typeof recorte.pct_publico !== "number" || !(pago > 0)) return null;
    return {
      pct: formatPct(recorte.pct_publico),
      cobertura: typeof recorte.cobertura_pago === "number" ? formatPct(recorte.cobertura_pago) : null,
      pago: pago,
      pagoPublico: num(recorte.pago_publico),
    };
  }

  var ORDEM_GLOBAL = ["presidente", "todos", "governador", "senador", "deputado-federal", "deputado-estadual", "deputado-distrital"];

  /* Lista global de cargos do seletor (Presidente primeiro), só os que existem em algum recorte do índice. */
  function cargosGlobais(indice) {
    var vistos = {};
    ((indice && indice.ufs) || []).forEach(function (u) {
      (u.cargos || []).forEach(function (c) { vistos[c] = true; });
    });
    var lista = ORDEM_GLOBAL.filter(function (c) { return vistos[c]; });
    Object.keys(vistos).forEach(function (c) { if (lista.indexOf(c) < 0) lista.push(c); });
    return lista;
  }

  /* Estados válidos para o cargo: Presidente só Brasil; os demais, os estados (sem Brasil) em ordem alfabética. */
  function ufsParaCargo(indice, cargo) {
    var ufs = ((indice && indice.ufs) || []).filter(function (u) { return (u.cargos || []).indexOf(cargo) >= 0; });
    if (cargo === "presidente") return ufs.filter(function (u) { return u.uf === "BR"; });
    return ufs.filter(function (u) { return u.uf !== "BR"; })
      .sort(function (a, b) { return String(a.nome).localeCompare(String(b.nome), "pt-BR"); });
  }

  /* Mantém a UF atual se ela serve ao cargo; senão, a primeira válida. */
  function escolherUf(indice, ufAtual, cargo) {
    var validas = ufsParaCargo(indice, cargo);
    if (validas.some(function (u) { return u.uf === ufAtual; })) return { uf: ufAtual, mudou: false };
    return { uf: validas.length ? validas[0].uf : ufAtual, mudou: true };
  }

  /* Segmentos do texto "Por que isso importa": [{t, forte?, posicao?}]. Sem pago*, nada de número nem de magnitude. */
  function importaSegmentos(recorte) {
    var fp = fontePublica(recorte);
    var segs = [];
    if (fp) {
      segs.push({ t: "As campanhas usam " });
      segs.push({ t: "dinheiro público", forte: true });
      segs.push({ t: " (Fundo Eleitoral e Fundo Partidário) para pagar anúncios. No recorte escolhido, " });
      segs.push({ t: fp.pct, forte: true });
      segs.push({ t: " do valor já pago em impulsionamento saiu desses fundos" + (fp.cobertura ? " (cobertura de " + fp.cobertura + " do contratado)" : "") + ". " });
    }
    segs.push({ t: "Esse dinheiro vai para plataformas estrangeiras. " });
    segs.push({ t: "Na nossa visão", posicao: true });
    segs.push({ t: ", elas empregam pouco no país, e esse dinheiro teria mais retorno para as pessoas se circulasse na economia local, em benfeitorias. Por isso propomos um teto percentual." });
    return segs;
  }

  function larguras(valores) {
    var max = Math.max.apply(null, valores.concat([0]));
    return valores.map(function (v) {
      return max > 0 ? Math.round((1000 * v) / max) / 10 : 0;
    });
  }

  function rodapeDe(dados, indice) {
    var g = dados.dt_geracao || (indice && indice.dt_geracao) || "data indisponível";
    var p = dados.dt_ultima_prestacao || (indice && indice.dt_ultima_prestacao) || "data indisponível";
    var atualizado = indice && formatarData(indice.gerado_em) !== "data indisponível" ? " Radar atualizado em " + formatarData(indice.gerado_em) + "." : "";
    return (
      "Fonte: TSE, dados abertos (despesas contratadas). Dados parciais: gerados em " + g +
      "; prestações de contas até " + p + "." + atualizado + " Valores são estimativas e incluem impulsionamento sem plataforma citada."
    );
  }

  function modeloCards(dados, cargoKey, indice, opcoes) {
    var endereco = (opcoes && opcoes.endereco) || ENDERECO_PADRAO;
    var recortes = (dados && dados.recortes) || {};
    var r = recortes[cargoKey] || {};
    var principal = num(r.principal);
    var rodape = rodapeDe(dados || {}, indice);
    var nome = (dados && dados.nome) || "";
    var artigo = (dados && dados.artigo) || "de";
    var todos = cargoKey === "todos";
    var cargoTxt = r.cargo ? String(r.cargo).toLowerCase() : cargoKey;

    // 1. gancho
    var gancho = {
      tipo: "gancho",
      kicker: "Eleições 2026 · " + nome,
      titulo: todos
        ? "Quanto as campanhas " + artigo + " " + nome + " gastaram com anúncios em plataformas estrangeiras?"
        : "Quanto as campanhas de " + cargoTxt + " " + artigo + " " + nome + " gastaram com anúncios em plataformas estrangeiras?",
      hero: hero(principal),
      texto:
        "em impulsionamento, somando as campanhas que já declararam despesas ao TSE (" +
        num(r.n_candidatos) + " candidatos com despesa declarada).",
      chip: formatPct(r.proporcao) + " de tudo que foi declarado · dados parciais",
      rodape: rodape,
    };

    // 2. por cargo (todos) ou confirmado x sem plataforma citada
    var barras;
    if (todos) {
      var chaves = Object.keys(recortes)
        .filter(function (k) { return k !== "todos"; })
        .sort(function (a, b) { return ORDEM_CARGOS.indexOf(a) - ORDEM_CARGOS.indexOf(b); });
      var larg = larguras(chaves.map(function (k) { return num(recortes[k].principal); }));
      barras = {
        tipo: "barras",
        kicker: nome + " · por cargo",
        titulo: "Quanto cada cargo declarou",
        linhas: chaves.map(function (k, i) {
          var c = recortes[k];
          return {
            rotulo: c.rotulo || k,
            valor: formatBRL(c.principal),
            largura: larg[i],
            pct: formatPct(c.proporcao) + " do total declarado",
            extra: num(c.n_gastaram) + " de " + num(c.n_candidatos) + " candidatos com gasto em plataformas",
          };
        }),
        nota: "Barras proporcionais ao valor em R$, somando todos os candidatos de cada cargo.",
        rodape: rodape,
      };
    } else {
      var conf = num(r.confirmado);
      var gen = num(r.generico);
      var l2 = larguras([conf, gen]);
      barras = {
        tipo: "barras",
        kicker: nome + " · " + (r.rotulo || cargoKey),
        titulo: "O que é confirmado e o que não cita a plataforma",
        linhas: [
          { rotulo: "Confirmado em plataformas", valor: formatBRL(conf), largura: l2[0], pct: "piso: a plataforma aparece na nota", extra: "" },
          { rotulo: "Impulsionamento sem plataforma citada", valor: formatBRL(gen), largura: l2[1], pct: "a nota não diz onde o anúncio rodou", extra: "" },
        ],
        nota: "O número principal soma os dois; o confirmado é o piso.",
        rodape: rodape,
      };
    }

    // 3. maiores valores declarados
    var oculto = ocultarNomes(dados, cargoKey);
    var top = !oculto && Array.isArray(r.top) ? r.top : [];
    var topCard = {
      tipo: "top",
      kicker: nome + " · " + (r.rotulo || cargoKey),
      titulo: "Maiores valores declarados",
      linhas: top.slice(0, 5).map(function (t, i) {
        return {
          n: i + 1,
          nome: t.nome,
          valor: formatBRL(t.principal),
          detalhe: formatPct(t.proporcao) + " do total da campanha" + (t.pequena ? " (campanha pequena)" : ""),
          tag: tagFraca(t),
        };
      }),
      vazio: top.length === 0,
      oculto: oculto,
      textoVazio: oculto ? MSG_NOMES_OCULTOS : "Nenhuma campanha deste recorte declarou impulsionamento em plataformas até agora.",
      nota: "Valores absolutos declarados; não é lista de irregularidades.",
      rodape: rodape,
    };

    // 4. tetos
    var elegiveis = num(r.n_elegiveis);
    var tetosR = Array.isArray(r.tetos) ? r.tetos : [];
    var linhasTetos = [];
    TETOS_CARDS.forEach(function (alvo) {
      var t = tetosR.filter(function (x) { return Math.abs(num(x.teto) - alvo) < 1e-9; })[0];
      if (!t) return;
      linhasTetos.push({
        teto: Math.round(alvo * 100) + "%",
        texto: num(t.n_acima) + " de " + elegiveis + " campanhas (" + formatPct(t.pct_acima) + ") ficariam acima do teto",
        detalhe: "Excedente somado: " + formatBRL(t.excedente),
      });
    });
    var piso = (indice && indice.piso_campanha) || 50000;
    var tetos = {
      tipo: "tetos",
      kicker: "A proposta",
      titulo: "E se existisse um teto percentual?",
      lead: "Anúncios em plataformas são legais e declarados. A discussão é o tamanho do limite sobre o total da campanha.",
      linhas: elegiveis > 0 ? linhasTetos : [],
      vazio: elegiveis === 0 || linhasTetos.length === 0,
      textoVazio: "Ainda não há campanhas deste recorte com despesas acima de " + formatBRL(piso) + " para simular os tetos.",
      nota: "Contadas só as campanhas com pelo menos " + formatBRL(piso) + " de despesas contratadas.",
      rodape: rodape,
    };

    // 5. convite
    var cta = {
      tipo: "cta",
      kicker: "Participe",
      titulo: "Quer ver os números do seu estado?",
      texto: "Escolha o estado e o cargo, veja quem declarou os maiores valores, baixe os cards e ajude a levar essa proposta adiante.",
      projeto: "Projeto aberto: contribua no GitHub",
      hashtag: HASHTAG,
      rodape: rodape,
    };

    var cards = [gancho, barras, topCard, tetos, cta];
    cards.forEach(function (c) { c.endereco = endereco; });
    return { cards: cards };
  }

  return {
    formatBRL: formatBRL,
    formatPct: formatPct,
    hero: hero,
    parseHash: parseHash,
    buildHash: buildHash,
    modeloCards: modeloCards,
    fonteHero: fonteHero,
    fonteEndereco: fonteEndereco,
    tagFraca: tagFraca,
    enderecoDoSite: enderecoDoSite,
    ENDERECO_PADRAO: ENDERECO_PADRAO,
    caminhoUf: caminhoUf,
    ocultarNomes: ocultarNomes,
    formatarData: formatarData,
    MSG_NOMES_OCULTOS: MSG_NOMES_OCULTOS,
    modoArquivoLocal: modoArquivoLocal,
    avisoTrocaUf: avisoTrocaUf,
    fontePublica: fontePublica,
    cargosGlobais: cargosGlobais,
    ufsParaCargo: ufsParaCargo,
    escolherUf: escolherUf,
    importaSegmentos: importaSegmentos,
    ORDEM_CARGOS: ORDEM_CARGOS,
    HASHTAG: HASHTAG,
  };
});
