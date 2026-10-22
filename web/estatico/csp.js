/* GPlanSiS|Peoples — ponte para a CSP sem 'unsafe-inline'.
 *
 * A Content-Security-Policy do aplicativo só executa script do próprio site ou
 * com o nonce da página. Manipuladores inline (onclick="...") e hx-on deixaram
 * de rodar; no lugar deles os templates usam `data-on-<evento>="fn(args)"`, que
 * este arquivo liga como ouvinte DIRETO no elemento (mesma ordem e mesma
 * propagação do onclick antigo).
 *
 * A expressão NÃO é avaliada como JavaScript: é uma lista de chamadas
 * `nome(arg, ...)` separadas por `;`, com argumentos literais (texto entre
 * aspas simples, número, true/false/null) ou `this`, `event`, `this.href`,
 * `this.textContent`, `this.value`, `this.checked`. Só funções desta lista
 * branca podem ser chamadas — um atributo injetado não vira código.
 */
(function () {
  'use strict';

  var PERMITIDAS = {
    'ORGA_GRADE.alternarEdicao': 1, aba: 1, abaSeHouver: 1, abrirChat: 1,
    abrirModal: 1, abrirPop: 1, ajustar: 1, ajustarLargura: 1, alternarConta: 1,
    alternarFiltros: 1, alternarGaveta: 1, alternarGavetaManual: 1,
    alternarLarguraChat: 1, alternarMaria: 1, alternarMenuTopo: 1, alternarOrg: 1,
    alternarPresenca: 1, alternarTema: 1, clicarArquivo: 1, enviarArquivo: 1,
    esvaziar: 1, esvaziarSeSucesso: 1, fecharChat: 1, fecharConta: 1,
    fecharDetalheMaria: 1, fecharFundo: 1, fecharMaria: 1, fecharMenu: 1,
    fecharModal: 1, fecharOrg: 1, filtrarAcessos: 1, filtrarPop: 1,
    filtrarTabela: 1, focarNo: 1, impedir: 1, limparCampo: 1,
    marcarTodosModulos: 1, mcEnviando: 1, menuExportar: 1, menuNo: 1,
    menuZoom: 1, pararChat: 1, pararEvento: 1, pdfMaria: 1, perguntarChat: 1,
    previaTema: 1, renomearOrg: 1, rolarParaDetalhe: 1,
    sincronizarTodosModulos: 1, teclaAlterna: 1, toggleGrupo: 1, tourAndar: 1,
    tourDoCanvas: 1, tourFechar: 1, zoom: 1, zoomPara: 1
  };
  var PROPS = { href: 1, textContent: 1, value: 1, checked: 1 };
  var EVENTOS = {
    click: 'click', change: 'change', contextmenu: 'contextmenu',
    dblclick: 'dblclick', input: 'input', keydown: 'keydown', keyup: 'keyup',
    submit: 'submit', 'htmx-after-request': 'htmx:afterRequest',
    'htmx-before-request': 'htmx:beforeRequest'
  };

  // --- ações que antes eram expressões soltas no atributo ------------------
  window.esvaziar = function (id) {
    var el = document.getElementById(id);
    if (el) el.innerHTML = '';
  };
  window.fecharFundo = function (ev, el) { if (ev.target === el) el.innerHTML = ''; };
  window.abaSeHouver = function () { if (typeof window.aba === 'function') window.aba(null); };
  window.previaTema = function (el) { document.documentElement.dataset.tema = el.value; };
  window.clicarArquivo = function (el) { el.form.arquivo.click(); };
  window.enviarArquivo = function (el) { if (el.files.length) el.form.requestSubmit(); };
  window.pararEvento = function (ev) { ev.stopPropagation(); };
  window.impedir = function (ev) { ev.preventDefault(); };
  window.teclaAlterna = function (ev, el) {
    if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); window.toggleGrupo(el); }
  };
  window.esvaziarSeSucesso = function (ev, id) {
    if (ev.detail && ev.detail.successful) window.esvaziar(id);
  };

  // --- funções que viviam em <script> dentro de fragmentos htmx -------------
  window.renomearOrg = function (slug, botao) {
    var atual = botao.closest('tr').querySelector('b').textContent.trim();
    var nome = window.prompt(botao.dataset.prompt || '', atual);
    if (nome === null || !nome.trim()) return;
    htmx.ajax('POST', '/organogramas/renomear', {
      target: '#area', swap: 'innerHTML',
      values: { slug: slug, nome: nome.trim() }
    });
  };
  window.filtrarAcessos = function (inp) {
    var t = (inp.value || '').toLowerCase().trim();
    document.querySelectorAll('#tab-acessos tbody tr').forEach(function (tr) {
      tr.style.display = (!t || (tr.dataset.busca || '').indexOf(t) >= 0) ? '' : 'none';
    });
  };
  window.marcarTodosModulos = function (master) {
    document.querySelectorAll('#mod-grade input[name="modulos"]').forEach(function (c) {
      c.checked = master.checked;
    });
  };
  window.sincronizarTodosModulos = function () {
    var cs = Array.prototype.slice.call(
      document.querySelectorAll('#mod-grade input[name="modulos"]'));
    var m = document.getElementById('mod-todos');
    if (!m) return;
    var n = cs.filter(function (c) { return c.checked; }).length;
    m.checked = n === cs.length;
    m.indeterminate = n > 0 && n < cs.length;
  };

  // --- o mini-intérprete --------------------------------------------------
  function dividir(texto, sep) {
    var partes = [], atual = '', aspas = false, nivel = 0;
    for (var i = 0; i < texto.length; i++) {
      var c = texto[i];
      if (c === "'" && texto[i - 1] !== '\\') aspas = !aspas;
      if (!aspas) {
        if (c === '(') nivel++;
        if (c === ')') nivel--;
        if (c === sep && nivel === 0) { partes.push(atual); atual = ''; continue; }
      }
      atual += c;
    }
    if (atual.trim()) partes.push(atual);
    return partes;
  }

  function valor(arg, el, ev) {
    var a = arg.trim();
    if (a === 'this') return el;
    if (a === 'event') return ev;
    if (a === 'true') return true;
    if (a === 'false') return false;
    if (a === 'null') return null;
    if (a.indexOf('this.') === 0 && PROPS[a.slice(5)]) return el[a.slice(5)];
    if (a.length >= 2 && a[0] === "'" && a[a.length - 1] === "'") {
      return a.slice(1, -1).replace(/\\'/g, "'");
    }
    if (/^-?\d+(\.\d+)?$/.test(a)) return parseFloat(a);
    throw new Error('argumento não suportado: ' + a);
  }

  function compilar(expr) {
    return dividir(expr, ';').map(function (chamada) {
      var m = /^\s*([A-Za-z_][\w.]*)\s*\(([\s\S]*)\)\s*$/.exec(chamada);
      if (!m || !PERMITIDAS[m[1]]) throw new Error('chamada não permitida: ' + chamada);
      return { nome: m[1], args: m[2].trim() ? dividir(m[2], ',') : [] };
    });
  }

  function resolver(nome) {
    var alvo = window, partes = nome.split('.');
    for (var i = 0; i < partes.length - 1; i++) alvo = alvo && alvo[partes[i]];
    var fn = alvo && alvo[partes[partes.length - 1]];
    return typeof fn === 'function' ? { fn: fn, dono: alvo } : null;
  }

  function ligar(el) {
    if (!el.attributes) return;
    for (var i = 0; i < el.attributes.length; i++) {
      var at = el.attributes[i].name;
      if (at.indexOf('data-on-') !== 0) continue;
      var chave = at.slice(8), tipo = EVENTOS[chave];
      if (!tipo) continue;
      el.__csp = el.__csp || {};
      if (el.__csp[chave]) continue;
      var passos;
      try { passos = compilar(el.getAttribute(at)); }
      catch (e) { console.error('[csp] ' + e.message); continue; }
      el.__csp[chave] = true;
      el.addEventListener(tipo, (function (passos) {
        return function (ev) {
          for (var j = 0; j < passos.length; j++) {
            var r = resolver(passos[j].nome);
            if (!r) { console.error('[csp] função ausente: ' + passos[j].nome); continue; }
            var args = passos[j].args.map(function (a) { return valor(a, this, ev); }, this);
            r.fn.apply(r.dono, args);
          }
        };
      })(passos));
    }
  }

  function varrer(raiz) {
    if (raiz.nodeType !== 1) return;
    ligar(raiz);
    var todos = raiz.querySelectorAll('*');
    for (var i = 0; i < todos.length; i++) ligar(todos[i]);
    if (raiz.querySelector('#mod-grade') || raiz.id === 'mod-grade') window.sincronizarTodosModulos();
  }

  function iniciar() {
    varrer(document.documentElement);
    new MutationObserver(function (lista) {
      lista.forEach(function (m) {
        for (var i = 0; i < m.addedNodes.length; i++) varrer(m.addedNodes[i]);
      });
    }).observe(document.documentElement, { childList: true, subtree: true });
  }

  // `keyup[key=='Enter']` do hx-trigger pedia eval: o gatilho virou o evento
  // `teclaEnter`, disparado daqui.
  document.addEventListener('keyup', function (ev) {
    if (ev.key !== 'Enter' || !window.htmx) return;
    var el = ev.target.closest && ev.target.closest('[hx-trigger*="teclaEnter"]');
    if (el) htmx.trigger(el, 'teclaEnter');
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
