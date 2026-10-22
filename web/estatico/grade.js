/* GPlanSiS|Peoples — a grade editável da Tabela (AG Grid Community, MIT).
 *
 * A tabela continua sendo desenhada no servidor. Este arquivo monta a grade
 * POR CIMA dela: se o JavaScript estiver desligado, se a biblioteca não
 * carregar ou se `/grade/dados` responder erro, o `<table>` renderizado fica
 * na tela e a vista funciona como sempre funcionou. É a mesma escada de
 * melhoria progressiva do resto do sistema.
 *
 * O cliente não é fonte de verdade (ADR-010 / ADR-011). Cada edição vai ao
 * servidor por rota própria, passa pelas guardas do painel — permissão, ciclo,
 * renumeração, ledger, ponto de desfazer — e a resposta traz a grade inteira de
 * volta. Não há estado de árvore mantido aqui: mudar o centro de custo de uma
 * pessoa troca N5, vertical e natureza na mesma linha, e só o servidor sabe
 * disso. Um cache local seria uma segunda verdade, e a primeira briga entre as
 * duas ninguém saberia arbitrar.
 *
 * Duas coisas que a AG Grid Community não tem, e que estão escritas aqui à mão:
 * a HIERARQUIA (Tree Data é Enterprise) e o MENU DE BOTÃO DIREITO (idem). A
 * hierarquia não custa nada porque o servidor já entrega as linhas achatadas
 * em pré-ordem, com a profundidade em cada uma — é o mesmo que a tabela usa
 * para indentar. O menu reaproveita o do canvas, que já existia.
 */
(function () {
  "use strict";

  var api = null;          // a instância viva da grade
  var dados = null;        // o último payload do servidor
  var editando = false;    // o botão Editar
  var menu = null;         // o <div> do botão direito, quando aberto

  /* ---- conversa com o servidor ------------------------------------------ */

  /* Toda mutação responde com a grade inteira. Devolver só a célula deixaria a
     linha contando três histórias: o nível repinta o chip, o CC troca N5,
     vertical e natureza, e o departamento pode abrir um provisionamento. */
  function pedir(rota, corpo) {
    var opcoes = { method: corpo ? "POST" : "GET" };
    if (corpo) {
      opcoes.headers = { "Content-Type": "application/x-www-form-urlencoded" };
      opcoes.body = new URLSearchParams(corpo).toString();
    }
    return fetch(rota, opcoes).then(function (r) {
      if (!r.ok) throw new Error(rota + " respondeu " + r.status);
      return r.json();
    });
  }

  /* O servidor recusa devolvendo 200 com o motivo (INT-06): a grade continua
     de pé e a pessoa lê por que não deu, em vez de ver a tela sumir. */
  function aplicar(resposta) {
    if (resposta.aviso) avisar(resposta.aviso);
    if (!resposta.ok && !resposta.linhas) return false;
    dados = resposta;
    if (api) {
      api.setGridOption("rowData", dados.linhas);
      api.refreshCells({ force: true });
      ajustarAltura();
      ajustarLarguras();
    }
    return true;
  }

  /* A grade cresce com o conteúdo até um teto, em vez de reservar sempre a
     mesma altura. Com a árvore recolhida em doze linhas, a altura fixa deixava
     meia tela de vazio abaixo da última — e vazio, numa tela de dados, lê-se
     como "acabou de carregar" ou "o filtro não achou nada". */
  function ajustarAltura() {
    var caixa = document.getElementById("grade");
    if (!caixa || !api) return;
    var linhas = api.getDisplayedRowCount();
    var teto = Math.max(280, Math.round(window.innerHeight * 0.72));
    /* +2 pela borda, +14 pela barra horizontal quando ela aparece. */
    caixa.style.height = Math.min(teto, 36 + linhas * 34 + 16) + "px";
  }

  /* Cada coluna do tamanho do texto que ela tem, até o teto. `autoSizeAllColumns`
     mede o conteúdo RENDERIZADO, então roda depois de a grade pintar — e de
     novo a cada recarga, porque filtrar troca quais linhas estão na tela e "o
     maior texto" passa a ser outro. O `false` é `skipHeader`: o título também
     entra na medida, senão a coluna sai mais estreita que a palavra que nomeia
     o dado.

     E para por aí. Esticar o que sobra para preencher a largura desfaz a
     medida logo depois de tirá-la: `Vertical` tem três letras e voltava a
     ocupar noventa pixels. Sobrando espaço, ele fica vazio à direita. */
  function ajustarLarguras() {
    if (!api) return;
    api.autoSizeAllColumns(false);
    var larg = larguraDoNome();
    if (larg) api.setColumnWidths([{ key: "nome", newWidth: larg }]);
  }

  /* A largura da coluna do nome, calculada do dado — e não medida do DOM.
   *
   * Ela é a única coluna cuja largura necessária MUDA com o que está aberto: o
   * recuo é `profundidade × 16`, então abrir um galho de N5 pede setenta pixels
   * a mais que a mesma tela recolhida em N1. E é a coluna que não pode esconder
   * texto — cortar o nome é esconder de quem se está falando.
   *
   * Medir pelo DOM não serve aqui: o `<b>` do nome tem `text-overflow`, então
   * já chega ao medidor com a largura que o corte lhe deu, e a coluna se
   * estabilizaria no tamanho errado. Medindo o texto com o canvas, na fonte
   * real da célula, a conta é do que o nome PRECISA, e não do que ele coube.
   */
  function larguraDoNome() {
    if (!api || !dados) return 0;
    var cel = document.querySelector("#grade .ag-cell");
    if (!cel) return 0;
    var estilo = getComputedStyle(cel);
    var lona = larguraDoNome._lona ||
               (larguraDoNome._lona = document.createElement("canvas"));
    var ctx = lona.getContext("2d");
    /* `600` porque quem tem subordinado sai em negrito, e negrito é mais
       largo: medir tudo no peso normal deixaria justamente os gestores — os
       nomes que mais importam nesta coluna — cortados. */
    ctx.font = "600 " + estilo.fontSize + " " + estilo.fontFamily;

    /* A árvore INTEIRA, e não as linhas visíveis: a largura passa a ser a
       mesma em qualquer nível aberto. Medindo só o que está na tela, a coluna
       encolhia com a árvore recolhida e cortava nomes no instante em que
       alguém abria um galho — e mudava de largura a cada dobra, que é a pior
       coisa que uma coluna pode fazer com o olho de quem está lendo. */
    var todas = dados.arvore || dados.linhas.map(function (l) {
      return [l.d, l.nome];
    });
    var maior = 0;
    for (var i = 0; i < todas.length; i++) {
      var texto = ctx.measureText(todas[i][1] || "").width;
      /* recuo + alça + respiro da alça + o texto + o padding da célula */
      maior = Math.max(maior, todas[i][0] * 16 + 17 + 6 + texto + 24);
    }
    /* Piso para a coluna não desaparecer numa base de nomes curtos; teto
       generoso, para um nome fora do comum não tomar a tela inteira — esse
       caso o `title` resolve. */
    return Math.min(560, Math.max(180, Math.ceil(maior)));
  }

  function avisar(texto) {
    var caixa = document.getElementById("gradeAviso");
    if (!caixa) return;
    caixa.textContent = texto;
    caixa.hidden = false;
    clearTimeout(avisar._t);
    avisar._t = setTimeout(function () { caixa.hidden = true; }, 6000);
  }

  /* ---- a coluna da hierarquia ------------------------------------------- */

  /* Indentação, alça de dobrar e o nome. É a primeira coluna porque é a que
     carrega a árvore: tirá-la da frente deixaria a indentação órfã no meio da
     grade, apontando para uma hierarquia que não se lê mais. */
  function pintarNome(p) {
    if (!p.data) return "";
    var caixa = document.createElement("div");
    caixa.className = "gr-no";
    caixa.style.paddingLeft = (p.data.d * 16) + "px";

    if (p.data.filhos) {
      var alca = document.createElement("button");
      alca.type = "button";
      alca.className = "gr-alca";
      alca.textContent = p.data.colapsado ? "+" : "−";
      alca.title = p.data.colapsado
        ? rotulo("abrir", "Abrir") + " (" + p.data.descendentes + ")"
        : rotulo("dobrar", "Dobrar");
      alca.setAttribute("aria-expanded", p.data.colapsado ? "false" : "true");
      alca.addEventListener("click", function (ev) {
        ev.stopPropagation();
        pedir("/grade/no", { uid: p.data.id, acao: "alternar" }).then(aplicar);
      });
      caixa.appendChild(alca);
    } else {
      var vazio = document.createElement("span");
      vazio.className = "gr-alca gr-vazia";
      vazio.setAttribute("aria-hidden", "true");
      caixa.appendChild(vazio);
    }

    var nome = document.createElement("b");
    nome.textContent = p.value || "";
    if (!p.data.filhos) nome.style.fontWeight = "400";
    caixa.appendChild(nome);
    return caixa;
  }

  /* O chip do nível, com a cor do token — a mesma da tabela e do card. A cor
     nunca carrega a informação sozinha: o rótulo vai escrito ao lado. */
  function pintarNivel(p) {
    if (!p.data) return "";
    var s = document.createElement("span");
    s.className = "tag";
    s.style.borderColor = "var(--k-cor_" + corDoNivel(p.data.tipo) + ")";
    s.textContent = rotuloDoDominio("tipo", p.data.tipo);
    return s;
  }

  function corDoNivel(codigo) {
    var mapa = (window.ORGA_CORES_NIVEL || {});
    return mapa[codigo] || "cinza";
  }

  function rotuloDoDominio(nome, valor) {
    var lista = (dados && dados.dominios && dados.dominios[nome]) || [];
    for (var i = 0; i < lista.length; i++) {
      if (lista[i].v === valor) return lista[i].r;
    }
    return valor || "";
  }

  function rotulo(chave, padrao) {
    return (window.ORGA_T && window.ORGA_T[chave]) || padrao;
  }

  /* ---- editor de lista com digitação livre ------------------------------ */

  /* Cargo e departamento têm vocabulário, mas o vocabulário cresce: um
     `<select>` puro recusaria o cargo que nasceu ontem, e um texto livre
     convidaria a digitar "Gerencia" ao lado de "Gerência". O `<datalist>`
     resolve os dois — sugere o que existe e aceita o que não existe ainda.
     (`agRichSelectCellEditor` faria isto, mas é Enterprise.) */
  function EditorAberto() {}
  EditorAberto.prototype.init = function (params) {
    this.valor = params.value == null ? "" : String(params.value);
    var id = "dl-" + params.column.getColId();
    this.el = document.createElement("div");
    this.el.className = "gr-editor";
    this.campo = document.createElement("input");
    this.campo.type = "text";
    this.campo.value = this.valor;
    this.campo.setAttribute("list", id);
    var dl = document.createElement("datalist");
    dl.id = id;
    ((dados.dominios || {})[params.dominio] || []).forEach(function (o) {
      var op = document.createElement("option");
      op.value = o.v;
      if (o.r && o.r !== o.v) op.label = o.r;
      dl.appendChild(op);
    });
    this.el.appendChild(this.campo);
    this.el.appendChild(dl);
  };
  EditorAberto.prototype.getGui = function () { return this.el; };
  EditorAberto.prototype.afterGuiAttached = function () {
    this.campo.focus();
    this.campo.select();
  };
  EditorAberto.prototype.getValue = function () { return this.campo.value; };
  EditorAberto.prototype.isPopup = function () { return false; };

  /* ---- colunas ---------------------------------------------------------- */

  /* Quanto de folga cada coluna recebe quando sobra largura. As de texto longo
     crescem; código, N, CC e contagem ficam do tamanho que precisam — esticar
     um código de quatro dígitos até 200 px só afasta as colunas que se leem
     juntas. Ausente daqui, a coluna não flexiona. */
  /* Teto por coluna. A largura sai do CONTEÚDO — cada coluna fica do tamanho do
     maior texto que ela tem —, mas sem teto uma única linha manda em tudo: há
     gente com onze accountabilities encadeadas, e essa linha sozinha esticaria
     a coluna para mil e oitocentos pixels, empurrando as outras para fora da
     tela por causa de um caso. O teto corta o exagero, e o que passa dele
     continua legível na dica e na gaveta.

     Não há piso por coluna nem `flex`. Os dois puxavam a largura para longe do
     texto em direções opostas: o piso segurava a coluna larga mesmo quando o
     conteúdo era curto — `Vertical` tem três letras e ocupava noventa e dois
     pixels —, e o `flex` esticava tudo o que sobrava de largura, desfazendo a
     medida logo depois de tirá-la. Sobrando espaço, ele agora fica vazio à
     direita: é o que "ajustar ao texto" quer dizer. */
  /* `nome` NÃO tem teto: é a coluna que carrega a árvore, e esconder um nome
     ali é esconder de quem se está falando. Ela é calculada à parte, em
     `larguraDoNome`. */
  var TETO = { cargo: 300, area: 220, accountabilities: 380,
               email: 240, tipo_cc: 150 };
  var PISO = 54;   // cabe "N5", "CC" e a seta de ordenação

  /* Colunas cuja célula mostra o RÓTULO em vez do código. Só onde o código é
     opaco: `coordenacao` não quer dizer nada para quem lê. Centro de custo
     fica de fora porque o código É como as pessoas o chamam — `90.11` — e o
     rótulo do cadastro repetiria o Departamento da coluna ao lado. */
  var ROTULADAS = { tipo: 1, vinculo: 1, status: 1 };

  function montarColunas() {
    /* As três primeiras ficam ancoradas à esquerda, NA ORDEM em que a tabela
       as declara: Código, N, Unidade / pessoa. Ancorar só o nome o trazia para
       a frente do código, e a grade passava a abrir com uma ordem que nenhuma
       outra tela usa. Ancoradas as três, a identificação da linha continua
       visível enquanto o resto rola para o lado. */
    var visiveis = dados.colunas.filter(function (c) { return c.on; });
    var ancoradas = ["codigo", "nivel_n", "nome"];
    return visiveis.map(function (c) {
        var col = {
          field: c.chave,
          headerName: c.rotulo,
          /* A largura declarada é o PISO, não um palpite. Com um piso genérico
             de 72 px as colunas de texto encolhiam até lá assim que as fixas
             enchiam a linha, e Cargo passava a mostrar sete caracteres e
             reticências. Doze colunas não cabem em mil pixels: o honesto é a
             grade rolar na horizontal dentro de si mesma — a página nunca rola
             — e cada coluna mostrar o que precisa. */
          minWidth: PISO,
          maxWidth: TETO[c.chave] || undefined,
          /* A dica traz o valor inteiro. Coluna dimensionada pelo conteúdo
             ainda corta o que passa do teto, e cortar sem dar como ler o resto
             esconde dado — o `title` devolve o texto completo sem custar
             largura nenhuma. */
          tooltipValueGetter: function (p) {
            return p.value == null ? "" : String(p.value);
          },
          resizable: true,
          sortable: true,
          /* Sem o filtro por coluna da AG Grid, e sem o funil no cabeçalho.
             A vista já tem a barra de filtros do sistema, que recorta o
             SERVIDOR — é ela que os chips, as pílulas, o contador do cabeçalho
             e as demais telas leem. Um segundo filtro, só do cliente e só
             desta grade, produziria uma tela mostrando dez linhas enquanto o
             resto do sistema diz duzentas, e ninguém saberia qual acreditar. */
          filter: false,
          suppressHeaderMenuButton: true,
          editable: function () { return editando && !!c.editor; },
        };
        /* Largura de partida só para o primeiro quadro não pular; logo em
           seguida `ajustarLarguras` a substitui pela medida do conteúdo. */
        col.width = c.largura;
        if (ancoradas.indexOf(c.chave) >= 0) col.pinned = "left";
        /* Derivada: não se edita, e a dica diz onde se muda de verdade. Sem
           isso a célula recusaria a edição em silêncio, e silêncio numa grade
           editável lê-se como defeito. */
        if (!c.editor) {
          col.cellClass = "gr-derivada";
          if (c.porque) col.headerTooltip = c.porque;
          col.tooltipValueGetter = function () { return c.porque; };
        }
        if (c.chave === "nome") {
          col.cellRenderer = pintarNome;
          col.rowDrag = function () { return editando; };
          /* A coluna do nome carrega a indentação: o piso precisa caber o
             recuo mais fundo mais um nome curto, senão a árvore some. */
          col.minWidth = 150;
        }
        if (c.chave === "tipo") col.cellRenderer = pintarNivel;
        if (c.editor === "suspensa") {
          col.cellEditor = "agSelectCellEditor";
          col.cellEditorParams = {
            values: ((dados.dominios[c.dominio] || []).map(function (o) {
              return o.v;
            })),
            /* O `<select>` mostra o rótulo e grava o código: sem isto a lista
               ofereceria "coordenacao" onde a tela inteira diz "Coordenação". */
            formatValue: function (v) { return rotuloDoDominio(c.dominio, v); },
          };
          /* Só onde o código é OPACO a célula mostra o rótulo. `coordenacao` não
             quer dizer nada para quem lê, e ali o rótulo é obrigatório. Já o
             centro de custo é o próprio código em toda a empresa — `90.11` é
             como as pessoas o chamam. Mostrando o rótulo do cadastro, a célula
             virava `90.11 · Managers Team`, repetia o Departamento da coluna
             ao lado e sozinha esticava a coluna a 395 px. Na LISTA o rótulo
             continua, porque na hora de escolher é ele que orienta. */
          if (ROTULADAS[c.chave]) {
            col.valueFormatter = function (p) {
              return rotuloDoDominio(c.dominio, p.value);
            };
          }
        }
        if (c.editor === "aberta") {
          col.cellEditor = EditorAberto;
          col.cellEditorParams = { dominio: c.dominio };
        }
        if (c.editor === "longo") {
          col.cellEditor = "agLargeTextCellEditor";
          col.cellEditorPopup = true;
          col.cellEditorParams = { maxLength: 4000, rows: 10, cols: 60 };
          col.autoHeight = false;
        }
        if (c.editor === "data") {
          col.cellEditor = "agDateStringCellEditor";
          col.cellEditorParams = { min: "1900-01-01" };
        }
        return col;
      });
  }

  /* ---- menu de botão direito -------------------------------------------- */

  function fecharMenu() {
    if (menu) { menu.remove(); menu = null; }
  }

  function abrirMenu(ev, linha) {
    fecharMenu();
    ev.preventDefault();
    var pode = dados.podeEditar;
    var itens = [
      ["abrir-gaveta", rotulo("gaveta", "Abrir na gaveta"), true, function () {
        abrirGaveta(linha.id);
      }],
      ["editar-celula", rotulo("editar-celula", "Editar esta célula"), pode,
       function () {
         if (!editando) alternarEdicao(true);
         var col = api.getFocusedCell();
         if (col) api.startEditingCell({ rowIndex: col.rowIndex,
                                         colKey: col.column.getColId() });
       }],
      null,
      ["dobrar", linha.colapsado ? rotulo("abrir", "Abrir")
                                 : rotulo("dobrar", "Dobrar"),
       !!linha.filhos, function () {
         pedir("/grade/no", { uid: linha.id, acao: "alternar" }).then(aplicar);
       }],
      null,
      ["indentar", rotulo("indentar", "Indentar") + "  ⇥", pode, function () {
        mover(linha.id, "indentar");
      }],
      ["promover", rotulo("promover", "Promover") + "  ⇧⇥", pode, function () {
        mover(linha.id, "promover");
      }],
      ["subir", rotulo("subir", "Subir entre os irmãos"), pode, function () {
        mover(linha.id, "subir");
      }],
      ["descer", rotulo("descer", "Descer entre os irmãos"), pode, function () {
        mover(linha.id, "descer");
      }],
      null,
      ["filho", rotulo("filho", "Nova unidade aqui dentro"), pode, function () {
        pedir("/grade/no", { uid: linha.id, acao: "filho" }).then(aplicar);
      }],
      ["duplicar", rotulo("duplicar", "Duplicar"), pode, function () {
        pedir("/grade/no", { uid: linha.id, acao: "duplicar" }).then(aplicar);
      }],
      null,
      ["copiar", rotulo("copiar", "Copiar a linha"), true, function () {
        copiar(linha);
      }],
      ["csv", rotulo("csv", "Exportar a grade em CSV"), true, function () {
        api.exportDataAsCsv({ fileName: "organograma.csv" });
      }],
      null,
      ["excluir", rotulo("excluir", "Excluir"), pode && !!linha.pai, function () {
        if (!window.confirm(rotulo("confirmar-excluir",
            "Excluir esta unidade? Os subordinados sobem para o gestor acima.")))
          return;
        pedir("/grade/no", { uid: linha.id, acao: "excluir" }).then(aplicar);
      }],
    ];

    menu = document.createElement("div");
    menu.className = "gr-menu";
    menu.setAttribute("role", "menu");
    itens.forEach(function (item) {
      if (!item) {
        var hr = document.createElement("hr");
        menu.appendChild(hr);
        return;
      }
      var b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "menuitem");
      b.textContent = item[1];
      b.disabled = !item[2];
      /* Desabilitado com o motivo no título: a diferença entre "não existe" e
         "não é para você" não pode ficar por conta de adivinhação (INT-03). */
      if (!item[2] && !dados.podeEditar && dados.motivo) b.title = dados.motivo;
      b.addEventListener("click", function () { fecharMenu(); item[3](); });
      menu.appendChild(b);
    });

    document.body.appendChild(menu);
    /* Posiciona depois de medir: perto da borda o menu abriria metade fora da
       tela, e a metade de fora é justamente onde ficam Excluir e Duplicar. */
    var l = Math.min(ev.clientX, window.innerWidth - menu.offsetWidth - 8);
    var t = Math.min(ev.clientY, window.innerHeight - menu.offsetHeight - 8);
    menu.style.left = Math.max(4, l) + "px";
    menu.style.top = Math.max(4, t) + "px";
    var primeiro = menu.querySelector("button:not([disabled])");
    if (primeiro) primeiro.focus();
  }

  function copiar(linha) {
    var texto = dados.colunas.filter(function (c) { return c.on; })
      .map(function (c) { return linha[c.chave]; }).join("\t");
    if (navigator.clipboard) navigator.clipboard.writeText(texto);
    avisar(rotulo("copiada", "Linha copiada."));
  }

  /* A gaveta é a mesma do canvas e da tabela: um fragmento no `#painel`, pela
     rota de sempre. `vista=tabela` para que o formulário dela saiba para onde
     devolver a edição — apontar para `#canvas` a partir daqui não daria erro,
     só faria a edição não sair do navegador (INT-01). */
  function abrirGaveta(id) {
    if (!window.htmx) return;
    htmx.ajax("GET", "/fragmentos/painel/" + id + "?canvas=0&vista=tabela",
              { target: "#painel", swap: "innerHTML" });
    var gaveta = document.getElementById("painel");
    if (gaveta && gaveta.classList.contains("recolhida")) {
      gaveta.classList.remove("recolhida");
    }
  }

  function mover(uid, acao) {
    pedir("/grade/mover", { uid: uid, acao: acao }).then(aplicar);
  }

  /* ---- o botão Editar --------------------------------------------------- */

  function alternarEdicao(ligar) {
    editando = ligar === undefined ? !editando : !!ligar;
    var bt = document.getElementById("btEditarGrade");
    if (bt) {
      bt.setAttribute("aria-pressed", editando ? "true" : "false");
      bt.classList.toggle("on", editando);
    }
    var caixa = document.getElementById("grade");
    if (caixa) caixa.classList.toggle("editando", editando);
    if (api) {
      /* As colunas leem `editando` por função, mas `rowDrag` é resolvido uma
         vez: sem redefinir, arrastar continuaria ligado depois de sair da
         edição — e arrastar sem querer reparenta gente. */
      api.setGridOption("columnDefs", montarColunas());
      api.refreshCells({ force: true });
    }
    if (editando) {
      avisar(rotulo("editando",
        "Edição ligada. Enter edita, Tab indenta, Shift+Tab promove, " +
        "botão direito abre as ações."));
    }
  }

  /* ---- montagem --------------------------------------------------------- */

  function montar() {
    var caixa = document.getElementById("grade");
    if (!caixa || !window.agGrid || caixa.dataset.montada || api) return;
    /* No celular a grade editável (AG Grid) seria um grid apertado de rolagem
       horizontal — catorze colunas em 390 px. A tabela do servidor já se
       empilha em cartões nesse tamanho (o layout mobile desenhado para isto),
       e é a leitura certa no telefone. Não montamos a grade: os cartões ficam,
       o botão Editar continua escondido. Casa com o @media (max-width:680px)
       que vira a tabela em cartão. */
    if (window.matchMedia && window.matchMedia("(max-width:680px)").matches) return;
    /* A marca é gravada AGORA, e não quando os dados chegam. `htmx:load` dispara
       uma vez por elemento carregado, e `DOMContentLoaded` dispara junto: com a
       marca depois do `fetch`, várias chamadas passavam pela guarda antes de a
       primeira responder e cada uma criava uma grade dentro do MESMO `<div>` —
       a tela terminava com três tabelas empilhadas, todas vivas. */
    caixa.dataset.montada = "1";

    pedir("/grade/dados").then(function (d) {
      dados = d;
      var tabela = document.querySelector("#tabelaCorpo .rolagem-x");
      if (tabela) tabela.hidden = true;      // só agora: a grade está de pé
      caixa.hidden = false;
      /* O botão nasce escondido no HTML e só aparece agora: sem grade montada
         ele prometeria uma edição que não existe — a tabela do servidor é, e
         sempre foi, só leitura. */
      var bt = document.getElementById("btEditarGrade");
      if (bt) bt.hidden = false;

      api = agGrid.createGrid(caixa, {
        columnDefs: montarColunas(),
        rowData: dados.linhas,
        getRowId: function (p) { return p.data.id; },
        /* Sem animação de linha: cada mutação recarrega a grade inteira, e
           272 linhas animando ao mesmo tempo lê-se como travamento. */
        animateRows: false,
        rowHeight: 34,
        headerHeight: 36,
        suppressCellFocus: false,
        stopEditingWhenCellsLoseFocus: true,
        preventDefaultOnContextMenu: true,
        rowDragManaged: false,
        tooltipShowDelay: 300,
        localeText: window.ORGA_GRADE_TEXTOS || {},
        defaultColDef: { minWidth: 60, flex: 0 },
        onGridReady: ajustarAltura,
        onFirstDataRendered: function () { ajustarAltura(); ajustarLarguras(); },
        /* Fora do modo Editar, clicar numa linha abre a gaveta — o mesmo gesto
           da tabela do servidor e do card do canvas. Sem isto a grade era a
           única tela onde clicar numa pessoa não fazia nada, e a gaveta ficava
           inalcançável exatamente para quem só quer ler e ajustar um campo.

           Dentro do modo Editar o clique pertence à célula: abrir a gaveta ali
           roubaria o foco de quem está prestes a digitar. */
        onCellClicked: function (ev) {
          if (editando || !ev.data || !window.htmx) return;
          abrirGaveta(ev.data.id);
        },
        getRowClass: function (p) {
          if (!p.data) return "";
          /* O esmaecido é o mesmo do canvas: nó que só sustenta o caminho até
             um achado não é resultado da busca, e não pode parecer um. */
          return p.data.passagem ? "gr-passagem"
               : (p.data.achou ? "gr-achou" : "");
        },
        onCellValueChanged: function (ev) {
          var antes = ev.oldValue == null ? "" : String(ev.oldValue);
          var agora = ev.newValue == null ? "" : String(ev.newValue);
          if (antes === agora) return;
          pedir("/grade/celula", { uid: ev.data.id, campo: ev.colDef.field,
                                   valor: agora })
            .then(function (r) {
              if (!aplicar(r)) api.setGridOption("rowData", dados.linhas);
            });
        },
        onRowDragEnd: function (ev) {
          var alvo = ev.overNode && ev.overNode.data;
          if (!alvo || alvo.id === ev.node.data.id) return;
          pedir("/grade/mover", { uid: ev.node.data.id, destino: alvo.id })
            .then(aplicar);
        },
        onCellKeyDown: function (ev) {
          var e = ev.event;
          if (!e || e.key !== "Tab" || !editando || !ev.data) return;
          /* Tab indenta em vez de andar para a próxima célula: numa grade de
             hierarquia é o gesto que todo mundo tenta primeiro. Fora da
             edição o Tab continua sendo o Tab, senão o teclado perderia a
             única saída da grade. */
          e.preventDefault();
          mover(ev.data.id, e.shiftKey ? "promover" : "indentar");
        },
      });

      /* O menu sai de um `contextmenu` no contêiner, e não do evento
         `onCellContextMenu` da biblioteca: a linha é achada pelo atributo
         `row-id`, que é DOM público e estável. Depender do evento da AG Grid
         amarraria o menu — que é código nosso — ao plumbing interno dela, e o
         menu de botão direito é justamente o que a edição Community não
         oferece. Um `addEventListener` resolve, e sobrevive a atualização. */
      caixa.addEventListener("contextmenu", function (ev) {
        var linha = ev.target.closest && ev.target.closest(".ag-row[row-id]");
        if (!linha) return;
        var id = linha.getAttribute("row-id");
        var achada = (dados.linhas || []).filter(function (l) {
          return l.id === id;
        })[0];
        if (achada) abrirMenu(ev, achada);
      });
    }).catch(function (erro) {
      /* A tabela do servidor continua na tela: é exatamente o caso para o qual
         ela foi mantida. A marca sai para que uma próxima troca de fragmento
         possa tentar de novo — falha de rede não pode aposentar a grade até
         alguém recarregar a página. */
      console.warn("grade não montou:", erro);
      caixa.removeAttribute("data-montada");
      var bt = document.getElementById("btEditarGrade");
      if (bt) bt.hidden = true;
    });
  }

  function desmontar() {
    if (api) { api.destroy(); api = null; }
    var caixa = document.getElementById("grade");
    if (caixa) {
      caixa.removeAttribute("data-montada");
      caixa.innerHTML = "";
    }
    dados = null;
    editando = false;
    fecharMenu();
  }

  document.addEventListener("click", function (ev) {
    if (menu && !menu.contains(ev.target)) fecharMenu();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") fecharMenu();
  });

  /* A Tabela chega por troca de fragmento: `htmx:load` cobre a primeira
     pintura e todas as seguintes. Sem o desmonte, trocar de vista e voltar
     deixaria duas grades vivas disputando o mesmo `<div>`. */
  document.addEventListener("htmx:beforeSwap", function (ev) {
    var caixa = document.getElementById("grade");
    if (caixa && ev.detail.target && ev.detail.target.contains(caixa)) {
      desmontar();
    }
  });
  document.addEventListener("htmx:load", montar);
  document.addEventListener("DOMContentLoaded", montar);

  /* `api` sai como função, e não como valor: a grade é remontada a cada troca
     de fragmento, e uma referência capturada apontaria para a instância morta.
     Ela existe para o console e para a verificação em navegador — o sistema
     não a usa. */
  window.ORGA_GRADE = {
    montar: montar,
    alternarEdicao: alternarEdicao,
    api: function () { return api; },
    editando: function () { return editando; },
  };
})();
