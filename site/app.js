/* Radar do Impulsionamento: interface. Sem frameworks; nada de dados vai para fora da página. */
(function () {
  "use strict";

  var ROTULOS_CARGO = {
    todos: "Todos os cargos",
    presidente: "Presidente",
    governador: "Governador",
    senador: "Senador",
    "deputado-federal": "Deputado federal",
    "deputado-estadual": "Deputado estadual",
    "deputado-distrital": "Deputado distrital",
  };
  var NOMES_CARDS = ["gancho", "por-cargo", "maiores-valores", "tetos", "convite"];

  var BASE = baseDados();
  var indice = null;
  var cacheUf = {};
  var atual = { uf: null, cargo: null, dados: null, modelo: null };
  var seq = 0;
  var hashProprio = null;

  function $(id) { return document.getElementById(id); }

  function el(tag, cls, texto) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (texto !== undefined && texto !== null) e.textContent = texto;
    return e;
  }

  // Parâmetro de desenvolvimento ?dados=caminho/ (só caminho relativo simples); por padrão lê data/.
  function baseDados() {
    try {
      var p = new URLSearchParams(location.search).get("dados");
      if (p && /^[A-Za-z0-9_\-./]+$/.test(p) && p.indexOf("..") < 0 && p.charAt(0) !== "/") return p.replace(/\/?$/, "/");
    } catch (e) { /* usa o padrão */ }
    return "data/";
  }

  function buscar(nome) {
    return fetch(BASE + nome, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status + " em " + nome);
      return r.json();
    });
  }

  function mostrarErro(msg, semNovaTentativa) {
    $("status").textContent = "";
    $("erro-msg").textContent = msg;
    $("erro-cmd").hidden = true;
    $("btn-tentar").hidden = !!semNovaTentativa;
    $("erro").hidden = false;
    $("painel").hidden = true;
  }

  function limparErro() { $("erro").hidden = true; }

  function avisoArquivoLocal() {
    mostrarErro("Esta página precisa ser aberta por um servidor, porque o navegador bloqueia a leitura dos dados quando ela vem direto de um arquivo. Na pasta do projeto, rode o comando abaixo e abra http://localhost:8000", true);
    var cmd = $("erro-cmd");
    cmd.textContent = "python3 -m http.server -d site 8000";
    cmd.hidden = false;
  }

  function iniciar() {
    if (Lib.modoArquivoLocal(location.protocol)) { avisoArquivoLocal(); return; }
    limparErro();
    $("status").textContent = "Carregando os dados…";
    buscar("index.json").then(function (idx) {
      if (!idx || !Array.isArray(idx.ufs) || !idx.ufs.length) throw new Error("index.json sem a lista de estados");
      indice = idx;
      montarSeletores();
      aplicarHash();
    }).catch(function (e) {
      mostrarErro("Não foi possível carregar a lista de estados (" + e.message + "). Verifique a conexão e tente de novo.");
    });
  }

  function cargosPorUf() {
    var m = {};
    indice.ufs.forEach(function (u) { m[u.uf] = u.cargos || []; });
    return m;
  }

  function montarSeletores() {
    var sel = $("sel-cargo");
    sel.textContent = "";
    Lib.cargosGlobais(indice).forEach(function (c) {
      var o = el("option", "", ROTULOS_CARGO[c] || c);
      o.value = c;
      sel.appendChild(o);
    });
    sel.disabled = false;
  }

  // Estados válidos para o cargo; com uma opção só (Presidente, Deputado distrital) o seletor fica desabilitado, mas visível.
  function preencherUfs(cargo, ufEscolhida) {
    var sel = $("sel-uf");
    var ufs = Lib.ufsParaCargo(indice, cargo);
    sel.textContent = "";
    ufs.forEach(function (u) {
      var o = el("option", "", u.nome);
      o.value = u.uf;
      sel.appendChild(o);
    });
    sel.value = ufEscolhida;
    sel.disabled = ufs.length <= 1;
    var ajuda = "";
    if (cargo === "presidente") ajuda = "Presidente é uma disputa nacional: não há divisão por estado.";
    else if (cargo === "deputado-distrital") ajuda = "Deputado distrital existe só no Distrito Federal.";
    $("ajuda-uf").textContent = ajuda;
  }

  function avisoFiltro(texto) {
    var p = $("msg-filtro");
    p.textContent = texto || "";
    p.hidden = !texto;
  }

  function aplicarHash() {
    var uf = Lib.parseHash(location.hash, indice.ufs.map(function (u) { return u.uf; }), cargosPorUf());
    mostrar(uf.uf, uf.cargo, true);
  }

  function escolher(uf, cargo) {
    var h = Lib.buildHash(uf, cargo);
    if (location.hash === h) { mostrar(uf, cargo, false); return; }
    hashProprio = h;
    location.hash = h; // dispara hashchange
  }

  function mostrar(uf, cargo, corrigirHash) {
    var meu = ++seq;
    $("sel-cargo").value = cargo;
    preencherUfs(cargo, uf);
    if (corrigirHash && location.hash !== Lib.buildHash(uf, cargo)) {
      try { history.replaceState(null, "", Lib.buildHash(uf, cargo)); } catch (e) { /* ignora */ }
    }
    $("status").textContent = "Carregando " + nomeUf(uf) + "…";
    var caminho = Lib.caminhoUf(indice, uf);
    if (!caminho) { mostrarErro("Estado inválido: " + uf + "."); return; }
    var p = cacheUf[uf] ? Promise.resolve(cacheUf[uf]) : buscar(caminho).then(function (d) { cacheUf[uf] = d; return d; });
    p.then(function (dados) {
      if (meu !== seq) return;
      limparErro();
      atual = { uf: uf, cargo: cargo, dados: dados };
      renderizar();
      var r0 = (dados.recortes || {})[cargo];
      $("status").textContent = "Dados de " + dados.nome + " · " + ((r0 && r0.rotulo) || ROTULOS_CARGO[cargo] || cargo) + " carregados.";
    }).catch(function (e) {
      if (meu !== seq) return;
      mostrarErro("Não foi possível carregar os dados de " + nomeUf(uf) + " (" + e.message + "). Tente de novo.");
    });
  }

  function nomeUf(uf) {
    var u = indice.ufs.filter(function (x) { return x.uf === uf; })[0];
    return u ? u.nome : uf;
  }

  function limpar(no) { while (no.firstChild) no.removeChild(no.firstChild); }

  function renderizar() {
    var dados = atual.dados;
    var r = (dados.recortes || {})[atual.cargo];
    $("painel").hidden = false;
    renderResumo(dados, r);
    renderImporta(r);
    renderMaiores(r);
    renderCards();
  }

  function renderResumo(dados, r) {
    var rotulo = r ? r.rotulo || ROTULOS_CARGO[atual.cargo] : ROTULOS_CARGO[atual.cargo];
    $("resumo-titulo").textContent = dados.nome + " · " + rotulo;
    var fatos = $("resumo-fatos");
    limpar(fatos);
    var vazio = $("resumo-vazio");
    if (!r) {
      $("resumo-valor").textContent = "Sem dados";
      $("resumo-legenda").textContent = "";
      vazio.hidden = false;
      vazio.textContent = "Não há dados para este cargo neste estado.";
    } else {
      $("resumo-valor").textContent = Lib.formatBRL(r.principal);
      $("resumo-legenda").textContent = "em impulsionamento em plataformas estrangeiras (confirmado mais impulsionamento sem plataforma citada).";
      vazio.hidden = !(r.principal === 0);
      vazio.textContent = "Nenhuma campanha deste recorte declarou impulsionamento até agora.";
      [
        [Lib.formatBRL(r.confirmado), "confirmado: o piso, com a plataforma citada na nota"],
        [Lib.formatPct(r.proporcao), "do total declarado em despesas (" + Lib.formatBRL(r.total) + ")"],
        [String(r.n_candidatos), "candidatos já declararam despesas (" + r.n_gastaram + " com gasto em plataformas)"],
      ].forEach(function (f) {
        var li = el("li");
        li.appendChild(el("b", "", f[0]));
        li.appendChild(el("span", "", f[1]));
        fatos.appendChild(li);
      });
    }
    var g = dados.dt_geracao || indice.dt_geracao || "data indisponível";
    var p = dados.dt_ultima_prestacao || indice.dt_ultima_prestacao || "data indisponível";
    $("resumo-datas").textContent = "Dados gerados pelo TSE em " + g + "; prestações mais recentes até " + p + ".";
    $("resumo-atualizacao").textContent = "Atualizado no Radar em " + Lib.formatarData(indice.gerado_em) + ". Os números mudam conforme o TSE recebe novas prestações de contas; este site é atualizado de tempos em tempos, confira as datas.";
    var parcial = "Dados parciais: as campanhas ainda entregam prestações e os números podem mudar. São estimativas.";
    if (dados.segundo_turno > 0) parcial += " Há " + dados.segundo_turno + " candidatura(s) em 2º turno, ainda em disputa.";
    $("resumo-parcial").textContent = parcial;
  }

  function renderImporta(r) {
    var alvo = $("importa-texto");
    limpar(alvo);
    Lib.importaSegmentos(r).forEach(function (seg) {
      if (seg.forte) alvo.appendChild(el("strong", "", seg.t));
      else if (seg.posicao) alvo.appendChild(el("mark", "posicao", seg.t));
      else alvo.appendChild(document.createTextNode(seg.t));
    });
  }

  function renderMaiores(r) {
    var lista = $("maiores-lista");
    limpar(lista);
    var top = r && Array.isArray(r.top) ? r.top : [];
    var vazio = $("maiores-vazio");
    $("maiores-sub").textContent = top.length
      ? "Até 5 candidaturas com maior valor declarado em plataformas neste recorte, em ordem de valor."
      : "";
    vazio.hidden = top.length > 0;
    vazio.textContent = "Nenhuma campanha deste recorte declarou impulsionamento em plataformas até agora.";
    top.forEach(function (t) {
      var li = el("li");
      var nome = el("span", "nome", t.nome);
      if (t.pequena) nome.appendChild(el("span", "etiqueta", "campanha pequena"));
      li.appendChild(nome);
      li.appendChild(el("span", "meta", t.cargo + " · " + t.uf));
      var vl = el("span", "valor", Lib.formatBRL(t.principal) + " em plataformas");
      var tg = Lib.tagFraca(t);
      if (tg) vl.appendChild(el("span", "tag", tg));
      li.appendChild(vl);
      li.appendChild(el("span", "meta", "Confirmado: " + Lib.formatBRL(t.confirmado) + " · Total da campanha: " + Lib.formatBRL(t.total) +
        " · " + Lib.formatPct(t.proporcao) + " do total"));
      lista.appendChild(li);
    });
  }

  // ---------- cards ----------
  var CONSTRUTORES = {
    gancho: function (s, c) {
      s.appendChild(el("h2", "", c.titulo));
      var h = el("div", "hero", c.hero.valor);
      h.style.fontSize = Lib.fonteHero(c.hero) + "px";
      h.appendChild(el("small", "", c.hero.unidade));
      s.appendChild(h);
      s.appendChild(el("p", "sub", c.texto));
      s.appendChild(el("span", "chip", c.chip));
    },
    barras: function (s, c) {
      s.appendChild(el("h2", "", c.titulo));
      var bars = el("div", "bars");
      c.linhas.forEach(function (l) {
        var row = el("div", "row");
        var tl = el("div", "topo-linha");
        tl.appendChild(el("span", "nome", l.rotulo));
        tl.appendChild(el("span", "val", l.valor));
        row.appendChild(tl);
        var tr = el("div", "track");
        var f = el("div", "fill");
        f.style.width = l.largura + "%";
        tr.appendChild(f);
        row.appendChild(tr);
        row.appendChild(el("div", "pct", l.pct));
        if (l.extra) row.appendChild(el("div", "pct", l.extra));
        bars.appendChild(row);
      });
      s.appendChild(bars);
      s.appendChild(el("p", "nota", c.nota));
    },
    top: function (s, c) {
      s.appendChild(el("h2", "", c.titulo));
      if (c.vazio) {
        s.appendChild(el("div", "vazio", c.textoVazio));
      } else {
        var it = el("div", "itens");
        c.linhas.forEach(function (l) {
          var item = el("div", "item");
          item.appendChild(el("div", "n", String(l.n)));
          var t = el("div", "t");
          t.appendChild(el("b", "", l.nome));
          var ln = el("div", "linha");
          ln.appendChild(el("span", "valor", l.valor));
          ln.appendChild(el("span", "det", l.detalhe));
          t.appendChild(ln);
          if (l.tag) t.appendChild(el("span", "tag", l.tag));
          item.appendChild(t);
          it.appendChild(item);
        });
        s.appendChild(it);
      }
      s.appendChild(el("p", "nota", c.nota));
    },
    tetos: function (s, c) {
      s.appendChild(el("h2", "", c.titulo));
      s.appendChild(el("p", "lead", c.lead));
      if (c.vazio) {
        s.appendChild(el("div", "vazio", c.textoVazio));
      } else {
        var st = el("div", "stats");
        c.linhas.forEach(function (l) {
          var b = el("div", "stat");
          b.appendChild(el("div", "teto", l.teto));
          var tx = el("div", "txt", l.texto);
          tx.appendChild(el("small", "", l.detalhe));
          b.appendChild(tx);
          st.appendChild(b);
        });
        s.appendChild(st);
      }
      s.appendChild(el("p", "nota", c.nota));
    },
    cta: function (s, c) {
      s.appendChild(el("h2", "", c.titulo));
      s.appendChild(el("p", "lead", c.texto));
      var sg = el("div", "site-grande", c.endereco);
      sg.style.fontSize = Lib.fonteEndereco(c.endereco) + "px";
      s.appendChild(sg);
      s.appendChild(el("p", "projeto", c.projeto));
      s.appendChild(el("div", "hashtag", c.hashtag));
    },
  };

  function construirCard(c, id) {
    var s = el("section", "card card-" + c.tipo);
    s.id = id;
    s.appendChild(el("div", "kicker", c.kicker));
    CONSTRUTORES[c.tipo](s, c);
    s.appendChild(el("div", "spacer"));
    if (c.tipo !== "cta") s.appendChild(el("div", "site", c.endereco));
    s.appendChild(el("p", "source", c.rodape));
    return s;
  }

  function descricaoCard(c) {
    var partes = [c.kicker, c.titulo];
    if (c.hero) partes.push(c.hero.valor + c.hero.unidade);
    if (c.linhas) c.linhas.forEach(function (l) {
      partes.push([l.rotulo || l.nome || l.teto, l.valor || l.texto].filter(Boolean).join(": "));
    });
    if (c.vazio && c.textoVazio) partes.push(c.textoVazio);
    return partes.join(". ");
  }

  function nomeArquivo(i) {
    return "radar-impulsionamento-" + atual.uf.toLowerCase() + "-" + atual.cargo + "-" + (i + 1) + "-" + NOMES_CARDS[i] + ".png";
  }

  function renderCards() {
    var modelo = Lib.modeloCards(atual.dados, atual.cargo, indice, { endereco: Lib.enderecoDoSite(location.host) });
    atual.modelo = modelo;
    var grade = $("grade");
    limpar(grade);
    modelo.cards.forEach(function (c, i) {
      var slot = el("div", "slot");
      slot.appendChild(el("h3", "", "Card " + (i + 1) + " de 5"));
      var prev = el("div", "preview");
      prev.setAttribute("role", "img");
      prev.setAttribute("aria-label", "Pré-visualização do card " + (i + 1) + ". " + descricaoCard(c));
      prev.appendChild(construirCard(c, "card-" + (i + 1)));
      slot.appendChild(prev);
      var ac = el("div", "acoes");
      var b = el("button", "btn", "Baixar PNG");
      b.type = "button";
      b.setAttribute("aria-label", "Baixar PNG do card " + (i + 1));
      b.addEventListener("click", function () { baixar(i, b); });
      ac.appendChild(b);
      slot.appendChild(ac);
      grade.appendChild(slot);
    });
    ajustarEscala();
  }

  function ajustarEscala() {
    var slots = document.querySelectorAll(".slot");
    for (var i = 0; i < slots.length; i++) {
      var prev = slots[i].querySelector(".preview");
      var card = prev.firstChild;
      var larg = Math.min(360, slots[i].clientWidth || 360);
      var esc = larg / 1080;
      prev.style.width = larg + "px";
      prev.style.height = Math.round(1920 * esc) + "px";
      card.style.transform = "scale(" + esc + ")";
    }
  }

  // ---------- download ----------
  function capturar(i) {
    if (typeof html2canvas === "undefined") return Promise.reject(new Error("gerador de imagem indisponível"));
    var original = $("card-" + (i + 1));
    var palco = el("div");
    palco.style.cssText = "position:fixed;left:-20000px;top:0;width:1080px;height:1920px;pointer-events:none;";
    palco.setAttribute("aria-hidden", "true");
    var clone = original.cloneNode(true);
    clone.removeAttribute("id");
    clone.style.transform = "none";
    palco.appendChild(clone);
    document.body.appendChild(palco);
    return html2canvas(clone, { width: 1080, height: 1920, scale: 1, backgroundColor: "#0f1b2d", logging: false })
      .then(function (canvas) { document.body.removeChild(palco); return canvas; },
        function (e) { document.body.removeChild(palco); throw e; });
  }

  function salvarCanvas(canvas, nome) {
    return new Promise(function (resolve, reject) {
      function entregar(url, revogar) {
        var a = document.createElement("a");
        a.download = nome;
        a.href = url;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        if (revogar) setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
        resolve();
      }
      if (canvas.toBlob) {
        canvas.toBlob(function (blob) {
          if (!blob) { reject(new Error("imagem vazia")); return; }
          entregar(URL.createObjectURL(blob), true);
        }, "image/png");
      } else {
        try { entregar(canvas.toDataURL("image/png"), false); } catch (e) { reject(e); }
      }
    });
  }

  function msg(t) { $("msg-download").textContent = t; }

  function baixar(i, botao) {
    botao.disabled = true;
    msg("Gerando o card " + (i + 1) + "…");
    return capturar(i).then(function (c) { return salvarCanvas(c, nomeArquivo(i)); })
      .then(function () { msg("Card " + (i + 1) + " baixado."); })
      .catch(function (e) { msg("Não deu para gerar a imagem (" + e.message + "). Use o print de tela do card."); })
      .then(function () { botao.disabled = false; });
  }

  function baixarTodos() {
    var b = $("btn-todos");
    b.disabled = true;
    var i = 0;
    function proximo() {
      if (i >= 5) { msg("Os 5 cards foram gerados. Se o navegador pediu permissão para vários downloads, autorize."); b.disabled = false; return Promise.resolve(); }
      msg("Gerando o card " + (i + 1) + " de 5…");
      var n = i++;
      return capturar(n).then(function (c) { return salvarCanvas(c, nomeArquivo(n)); })
        .then(function () { return new Promise(function (ok) { setTimeout(ok, 400); }); })
        .then(proximo);
    }
    proximo().catch(function (e) {
      msg("Não deu para gerar todas as imagens (" + e.message + "). Use o print de tela ou baixe um a um.");
      b.disabled = false;
    });
  }

  // ---------- eventos ----------
  function ligar() {
    $("sel-uf").addEventListener("change", function () {
      avisoFiltro("");
      escolher($("sel-uf").value, $("sel-cargo").value);
    });
    $("sel-cargo").addEventListener("change", function () {
      var cargo = $("sel-cargo").value;
      var ufAntiga = atual.uf || $("sel-uf").value;
      var r = Lib.escolherUf(indice, ufAntiga, cargo);
      avisoFiltro(Lib.avisoTrocaUf({ uf: ufAntiga, nome: nomeUf(ufAntiga) }, { uf: r.uf, nome: nomeUf(r.uf) }, cargo, ROTULOS_CARGO[cargo] || cargo));
      escolher(r.uf, cargo);
    });
    window.addEventListener("hashchange", function () {
      if (location.hash !== hashProprio) avisoFiltro(""); // hash editado à mão: o aviso antigo não vale mais
      hashProprio = null;
      if (indice) aplicarHash();
    });
    window.addEventListener("resize", ajustarEscala);
    $("btn-tentar").addEventListener("click", function () {
      if (!indice) iniciar(); else mostrar(atual.uf || "BR", atual.cargo || "presidente", true);
    });
    $("btn-todos").addEventListener("click", baixarTodos);
  }

  ligar();
  iniciar();
})();
