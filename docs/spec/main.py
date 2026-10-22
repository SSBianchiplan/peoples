"""
GPlanSiS|Peoples - Canvas Twin do Organograma Invertido
SPEC-GPLANSIS-ORG-001 - ondas W5' (HTMX) e W9 (edicao no canvas)

Arquitetura: HTMX server-driven.
  - Toda mutacao devolve o fragmento <svg id="canvas"> re-renderizado.
  - O layout e calculado no servidor (fonte unica de verdade geometrica).
  - O cliente so cuida de efemero: selecao, menu de contexto, pan e zoom.

Execucao:  uvicorn main:app --reload --port 8080
"""
from __future__ import annotations

import copy
import hashlib
import json
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).parent
ARQUIVO_ESTADO = BASE / "dados" / "estado.json"

# ---------------------------------------------------------------------------
# TOKENS DE LAYOUT  (SPEC 9.6)
# ---------------------------------------------------------------------------
CARD_W = 210
CARD_PAD = 12
GAP_H = 26
GAP_V = 78
MARGEM = 40
TRILHO_X = 26          # cota de nivel (elemento-assinatura)
MAX_BULLETS = 7

TIPOS = {
    "gerencia": "Gerência",
    "coordenacao": "Coordenação",
    "area": "Área",
    "celula": "Célula",
    "apoio": "Apoio",
}


# ---------------------------------------------------------------------------
# DOMINIO
# ---------------------------------------------------------------------------
@dataclass
class Unidade:
    id: str
    codigo: str
    nome: str
    tipo: str
    parent_id: str | None
    ordem: int
    responsavel: str = ""
    cargo: str = ""
    responsabilidades: list[dict] = field(default_factory=list)


@dataclass
class Estado:
    unidades: dict[str, Unidade] = field(default_factory=dict)
    eventos: list[dict] = field(default_factory=list)
    orientacao: str = "invertida"
    selecionado: str | None = None
    historico: list[str] = field(default_factory=list)   # snapshots JSON p/ desfazer


ESTADO = Estado()


def novo_id() -> str:
    return uuid.uuid4().hex[:12]


def proximo_codigo() -> str:
    n = len(ESTADO.unidades) + 1
    usados = {u.codigo for u in ESTADO.unidades.values()}
    while f"ORG-{n:04d}" in usados:
        n += 1
    return f"ORG-{n:04d}"


# ---------------------------------------------------------------------------
# LEDGER HASH-ENCADEADO  (SPEC 7.2)
# ---------------------------------------------------------------------------
def registrar(acao: str, entidade_id: str, motivo: str, payload: dict) -> None:
    anterior = ESTADO.eventos[-1]["hash"] if ESTADO.eventos else "GENESIS"
    quando = datetime.now(timezone.utc).isoformat(timespec="seconds")
    corpo = "|".join([
        anterior, quando, "operador@local", acao, entidade_id, motivo,
        json.dumps(payload, sort_keys=True, ensure_ascii=False),
    ])
    ESTADO.eventos.append({
        "seq": len(ESTADO.eventos) + 1,
        "quando": quando,
        "ator": "operador@local",
        "acao": acao,
        "entidade_id": entidade_id,
        "motivo": motivo,
        "payload": payload,
        "hash_anterior": anterior,
        "hash": hashlib.sha256(corpo.encode()).hexdigest(),
    })


def verificar_cadeia() -> dict:
    anterior = "GENESIS"
    for ev in ESTADO.eventos:
        corpo = "|".join([
            anterior, ev["quando"], ev["ator"], ev["acao"],
            ev["entidade_id"], ev["motivo"],
            json.dumps(ev["payload"], sort_keys=True, ensure_ascii=False),
        ])
        if hashlib.sha256(corpo.encode()).hexdigest() != ev["hash"]:
            return {"integro": False, "seq_falha": ev["seq"]}
        anterior = ev["hash"]
    return {"integro": True, "seq_falha": None}


# ---------------------------------------------------------------------------
# PERSISTENCIA (arquivo JSON; PostgreSQL em producao - ver schema.sql)
# ---------------------------------------------------------------------------
def serializar() -> str:
    return json.dumps({
        "unidades": {k: asdict(v) for k, v in ESTADO.unidades.items()},
        "eventos": ESTADO.eventos,
        "orientacao": ESTADO.orientacao,
    }, ensure_ascii=False, indent=1)


def gravar() -> None:
    ARQUIVO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_ESTADO.write_text(serializar(), encoding="utf-8")


def carregar() -> bool:
    if not ARQUIVO_ESTADO.exists():
        return False
    try:
        bruto = json.loads(ARQUIVO_ESTADO.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    ESTADO.unidades = {k: Unidade(**v) for k, v in bruto["unidades"].items()}
    ESTADO.eventos = bruto.get("eventos", [])
    ESTADO.orientacao = bruto.get("orientacao", "invertida")
    return True


def marcar_ponto() -> None:
    """Empilha snapshot para o botao desfazer."""
    ESTADO.historico.append(serializar())
    del ESTADO.historico[:-30]


def aplicar_snapshot(bruto: str) -> None:
    dados = json.loads(bruto)
    ESTADO.unidades = {k: Unidade(**v) for k, v in dados["unidades"].items()}
    ESTADO.eventos = dados.get("eventos", [])
    ESTADO.orientacao = dados.get("orientacao", "invertida")


# ---------------------------------------------------------------------------
# ARVORE
# ---------------------------------------------------------------------------
def mapa_filhos() -> dict[str | None, list[Unidade]]:
    m: dict[str | None, list[Unidade]] = defaultdict(list)
    for u in ESTADO.unidades.values():
        m[u.parent_id].append(u)
    for k in m:
        m[k].sort(key=lambda x: (x.ordem, x.nome, x.id))
    return m


def raiz() -> Unidade:
    return mapa_filhos()[None][0]


def descendentes(uid: str) -> set[str]:
    m = mapa_filhos()
    acc, pilha = set(), [uid]
    while pilha:
        atual = pilha.pop()
        for f in m.get(atual, []):
            acc.add(f.id)
            pilha.append(f.id)
    return acc


def renumerar(parent_id: str | None) -> None:
    for i, f in enumerate(mapa_filhos().get(parent_id, [])):
        f.ordem = (i + 1) * 10


# ---------------------------------------------------------------------------
# MOTOR DE LAYOUT  (SPEC 9 - contrato normativo)
# ---------------------------------------------------------------------------
def quebrar(texto: str, max_chars: int, max_linhas: int) -> list[str]:
    """Quebra por palavra e sinaliza corte com reticencia."""
    palavras = texto.split()
    linhas, atual, i = [], "", 0
    while i < len(palavras) and len(linhas) < max_linhas:
        p = palavras[i]
        tentativa = f"{atual} {p}".strip()
        if len(tentativa) <= max_chars:
            atual, i = tentativa, i + 1
        elif atual:
            linhas.append(atual)
            atual = ""
        else:
            linhas.append(p[: max_chars - 1] + "\u2026")
            i += 1
    if atual and len(linhas) < max_linhas:
        linhas.append(atual)
        i = len(palavras)
    if i < len(palavras) and linhas:
        ult = linhas[-1]
        corte = max_chars - 1
        linhas[-1] = (ult[:corte].rstrip() if len(ult) > corte else ult) + "\u2026"
    return linhas or [texto[:max_chars]]


def montar_card(u: Unidade, x: float, y: float) -> tuple[dict, float]:
    """Constroi o card em coordenadas absolutas e devolve (card, altura)."""
    cur = y + 20
    textos = [{"x": x + CARD_PAD, "y": cur, "cls": "t-cod", "txt": u.codigo}]
    cur += 16
    for ln in quebrar(u.nome, 25, 2):
        textos.append({"x": x + CARD_PAD, "y": cur, "cls": "t-nome", "txt": ln})
        cur += 16
    textos.append({
        "x": x + CARD_PAD, "y": cur + 2, "cls": "t-pes",
        "txt": u.responsavel or "sem responsável",
    })
    cur += 14
    regua = cur
    cur += 14

    itens, visiveis = [], u.responsabilidades[:MAX_BULLETS]
    for r in visiveis:
        itens.append({
            "x": x + CARD_PAD + 10, "y": cur,
            "mx": x + CARD_PAD + 2, "my": cur - 3.5,
            "txt": quebrar(r["descricao"], 28, 1)[0],
            "delegada": r.get("origem") == "delegada",
        })
        cur += 15
    resto = len(u.responsabilidades) - len(visiveis)
    if resto > 0:
        itens.append({
            "x": x + CARD_PAD + 10, "y": cur, "mx": None, "my": None,
            "txt": f"+ {resto} item(ns)", "delegada": False,
        })
        cur += 15

    altura = max(cur - y + CARD_PAD - 4, 92)
    card = {
        "id": u.id, "codigo": u.codigo, "nome": u.nome, "tipo": u.tipo,
        "x": x, "y": y, "w": CARD_W, "h": altura,
        "cx": x + CARD_W / 2,
        "regua": regua, "textos": textos, "itens": itens,
        "raiz": u.parent_id is None,
    }
    return card, altura


def calcular_layout(orientacao: str, selecionado: str | None) -> dict:
    invertida = orientacao == "invertida"
    filhos = mapa_filhos()
    r = raiz()

    # --- profundidade e altura de cada no --------------------------------
    prof: dict[str, int] = {}
    alt: dict[str, float] = {}

    def medir(u: Unidade, d: int) -> None:
        prof[u.id] = d
        _, h = montar_card(u, 0, 0)
        alt[u.id] = h
        for f in filhos.get(u.id, []):
            medir(f, d + 1)

    medir(r, 0)
    D = max(prof.values())

    # --- eixo transversal: folhas em sequencia, pais centralizados -------
    px: dict[str, float] = {}
    cursor = [0.0]

    def passo_x(u: Unidade) -> float:
        fs = filhos.get(u.id, [])
        if not fs:
            x = cursor[0]
            cursor[0] += CARD_W + GAP_H
        else:
            xs = [passo_x(f) for f in fs]
            x = (min(xs) + max(xs)) / 2
        px[u.id] = x
        return x

    passo_x(r)

    # --- eixo vertical: projecao da profundidade (SPEC 9.1) --------------
    alt_prof: dict[int, float] = defaultdict(float)
    for uid, d in prof.items():
        alt_prof[d] = max(alt_prof[d], alt[uid])

    # linha visual 0 = topo da tela
    alt_linha = {
        (D - d if invertida else d): h for d, h in alt_prof.items()
    }
    y_linha, acumulado = {}, float(MARGEM)
    for linha in range(D + 1):
        y_linha[linha] = acumulado
        acumulado += alt_linha[linha] + GAP_V
    altura_total = acumulado - GAP_V + MARGEM

    # --- cards ------------------------------------------------------------
    nos, indice = [], {}
    for uid, u in ESTADO.unidades.items():
        d = prof[uid]
        linha = (D - d) if invertida else d
        # invertida alinha pela base da faixa; vertical, pelo topo
        y = y_linha[linha] + (alt_linha[linha] - alt[uid] if invertida else 0)
        card, _ = montar_card(u, px[uid] + MARGEM + TRILHO_X, y)
        card["nivel"] = d
        card["sel"] = uid == selecionado
        card["ancora_pai"] = card["y"] if invertida else card["y"] + card["h"]
        card["ancora_filho"] = card["y"] + card["h"] if invertida else card["y"]
        nos.append(card)
        indice[uid] = card
    nos.sort(key=lambda c: (c["nivel"], c["x"]))

    # --- conectores (SPEC 9.3) -------------------------------------------
    sinal = -1 if invertida else 1
    conectores = []
    for u in ESTADO.unidades.values():
        fs = filhos.get(u.id, [])
        if not fs:
            continue
        p = indice[u.id]
        if len(fs) == 1:                                   # LAY-06
            f = indice[fs[0].id]
            conectores.append({"d": f"M {p['cx']:.2f} {p['ancora_pai']:.2f} "
                                    f"L {f['cx']:.2f} {f['ancora_filho']:.2f}"})
            continue
        y_bus = p["ancora_pai"] + sinal * (GAP_V / 2)
        cxs = [indice[f.id]["cx"] for f in fs]
        d = (f"M {p['cx']:.2f} {p['ancora_pai']:.2f} L {p['cx']:.2f} {y_bus:.2f} "
             f"M {min(cxs):.2f} {y_bus:.2f} L {max(cxs):.2f} {y_bus:.2f}")
        for f in fs:                                       # LAY-05
            c = indice[f.id]
            d += f" M {c['cx']:.2f} {y_bus:.2f} L {c['cx']:.2f} {c['ancora_filho']:.2f}"
        conectores.append({"d": d})

    # --- cota de nivel (elemento-assinatura) ------------------------------
    cotas = []
    for d in range(D + 1):
        linha = (D - d) if invertida else d
        cotas.append({
            "y": y_linha[linha],
            "y2": y_linha[linha] + alt_linha[linha],
            "meio": y_linha[linha] + alt_linha[linha] / 2,
            "rotulo": f"N{d}",
            "base": d == 0,
        })

    largura_total = cursor[0] - GAP_H + 2 * MARGEM + TRILHO_X
    return {
        "raiz_id": r.id,
        "trilho_y1": min(c["y"] for c in cotas),
        "trilho_y2": max(c["y2"] for c in cotas),
        "nos": nos,
        "conectores": conectores,
        "cotas": cotas,
        "trilho_x": MARGEM + TRILHO_X - 18,
        "viewbox": f"0 0 {largura_total:.0f} {altura_total:.0f}",
        "largura": largura_total,
        "altura": altura_total,
        "orientacao": orientacao,
        "invertida": invertida,
        "profundidade_max": D,
    }


# ---------------------------------------------------------------------------
# SEED DE REFERENCIA  (SPEC 13)
# ---------------------------------------------------------------------------
def semear() -> None:
    ESTADO.unidades.clear()
    ESTADO.eventos.clear()
    ESTADO.orientacao = "invertida"
    ESTADO.selecionado = None

    def add(codigo, nome, tipo, parent, ordem, resp, cargo, itens):
        uid = novo_id()
        ESTADO.unidades[uid] = Unidade(
            id=uid, codigo=codigo, nome=nome, tipo=tipo, parent_id=parent,
            ordem=ordem, responsavel=resp, cargo=cargo,
            responsabilidades=[
                {"descricao": d, "origem": o, "delegada_para": None}
                for d, o in itens
            ],
        )
        return uid

    r = add("ORG-0001", "Recursos Humanos", "gerencia", None, 0,
            "Marina Albuquerque Sá", "Gerente de RH", [
                ("L.G.R.", "delegada"),
                ("Atração e gestão de talentos", "delegada"),
                ("Desenvolvimento org. e cultura", "delegada"),
                ("Remuneração estratégica", "delegada"),
                ("Administração de pessoal", "delegada"),
            ])
    add("ORG-0002", "Remuneração Estratégica", "area", r, 10,
        "Beatriz Nogueira Pinto", "Analista sênior", [
            ("Remuneração", "propria"), ("Benefícios", "propria"),
            ("Gestão de talentos", "propria"), ("Indicadores", "propria"),
            ("Gestão PJ", "propria")])
    add("ORG-0003", "Administração de Pessoal", "area", r, 20,
        "Jaqueline Cavalcanti Cardoso", "Analista sênior", [
            ("L.G.R.", "propria"), ("Folha de pagamento", "propria"),
            ("Admissão / rescisão", "propria"), ("Ponto", "propria"),
            ("Férias", "propria")])
    add("ORG-0004", "Desenvolvimento Organizacional", "area", r, 30,
        "Daniela Fontes Ribeiro", "Analista", [
            ("Treinamentos", "propria"), ("Programas de capacitação", "propria"),
            ("Gestão de estagiários", "propria"), ("Eventos especiais", "propria"),
            ("GPTW", "propria")])
    add("ORG-0005", "Atração de Talentos", "area", r, 40,
        "Lucas Souza Brito", "Analista", [
            ("Recrutamento e seleção", "propria"), ("Onboarding", "propria"),
            ("Offboarding", "propria")])
    add("ORG-0006", "Documentação", "apoio", r, 50,
        "Elaine Moreira Lins", "Assistente", [
            ("Documentação de integração em clientes", "propria"),
            ("Obrigações acessórias", "propria"),
            ("Suporte no onboarding", "propria"),
            ("Suporte em eventos", "propria")])

    registrar("criar", r, "carga do seed de referência", {"unidades": len(ESTADO.unidades)})
    gravar()


if not carregar():
    semear()


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
app = FastAPI(title="GPlanSiS|Peoples - Canvas Twin")
app.mount("/vendor", StaticFiles(directory=str(BASE / "vendor")), name="vendor")
tpl = Jinja2Templates(directory=str(BASE / "templates"))


def render(nome: str, **ctx) -> str:
    return tpl.get_template(nome).render(**ctx)


def canvas(req: Request, extra: str = "") -> HTMLResponse:
    html = render("_canvas.html", request=req,
                  layout=calcular_layout(ESTADO.orientacao, ESTADO.selecionado))
    return HTMLResponse(html + extra)


def oob_painel(req: Request, uid: str | None) -> str:
    """Fragmento fora-de-banda para manter o painel lateral coerente."""
    if uid is None:
        corpo = render("_painel_vazio.html", request=req)
    else:
        corpo = corpo_painel(req, uid, com_canvas=False)
    return f'<aside id="painel" class="painel" hx-swap-oob="true">{corpo}</aside>'


def corpo_painel(req: Request, uid: str, com_canvas: bool = True) -> str:
    u = ESTADO.unidades[uid]
    filhos = mapa_filhos()
    nivel, atual = 0, u
    while atual.parent_id is not None:
        atual = ESTADO.unidades[atual.parent_id]
        nivel += 1
    return render(
        "_painel.html", request=req, u=u, tipos=TIPOS,
        pai=ESTADO.unidades.get(u.parent_id), u_nivel=nivel,
        n_filhos=len(filhos.get(uid, [])),
        texto="\n".join(
            ("> " if r.get("origem") == "delegada" else "") + r["descricao"]
            for r in u.responsabilidades),
        oob=com_canvas,
        layout=calcular_layout(ESTADO.orientacao, uid),
    )


def commit(acao: str, uid: str, motivo: str, payload: dict) -> None:
    registrar(acao, uid, motivo, payload)
    gravar()


@app.get("/", response_class=HTMLResponse)
def inicio(req: Request):
    return HTMLResponse(render("base.html", request=req,
        layout=calcular_layout(ESTADO.orientacao, ESTADO.selecionado)))


# --- vistas ---------------------------------------------------------------
@app.get("/vistas/canvas", response_class=HTMLResponse)
def vista_canvas(req: Request):
    return HTMLResponse(render("_vista_canvas.html", request=req,
        layout=calcular_layout(ESTADO.orientacao, ESTADO.selecionado)))


@app.get("/vistas/tabela", response_class=HTMLResponse)
def vista_tabela(req: Request):
    filhos = mapa_filhos()
    linhas = []

    def caminhar(u: Unidade, d: int):
        linhas.append({"u": u, "d": d, "tipo": TIPOS.get(u.tipo, u.tipo)})
        for f in filhos.get(u.id, []):
            caminhar(f, d + 1)

    caminhar(raiz(), 0)
    return HTMLResponse(render("_tabela.html", request=req, linhas=linhas))


@app.get("/vistas/auditoria", response_class=HTMLResponse)
def vista_auditoria(req: Request):
    return HTMLResponse(render("_auditoria.html", request=req,
        eventos=list(reversed(ESTADO.eventos)), cadeia=verificar_cadeia()))


# --- fragmentos -----------------------------------------------------------
@app.get("/fragmentos/menu/{uid}", response_class=HTMLResponse)
def fragmento_menu(req: Request, uid: str):
    u = ESTADO.unidades[uid]
    filhos = mapa_filhos()
    irmaos = filhos.get(u.parent_id, [])
    idx = [x.id for x in irmaos].index(uid) if u.parent_id or len(irmaos) > 1 else 0
    return HTMLResponse(render(
        "_menu.html", request=req, u=u,
        raiz=u.parent_id is None,
        pode_esquerda=u.parent_id is not None and idx > 0,
        pode_direita=u.parent_id is not None and idx < len(irmaos) - 1,
        pode_rebaixar=u.parent_id is not None and idx > 0,
        pode_promover=(u.parent_id is not None
                       and ESTADO.unidades[u.parent_id].parent_id is not None)))


@app.get("/fragmentos/painel/{uid}", response_class=HTMLResponse)
def fragmento_painel(req: Request, uid: str):
    ESTADO.selecionado = uid
    return HTMLResponse(corpo_painel(req, uid))


@app.get("/fragmentos/painel-vazio", response_class=HTMLResponse)
def fragmento_painel_vazio(req: Request):
    ESTADO.selecionado = None
    return HTMLResponse(render("_painel_vazio.html", request=req))


# --- mutacoes -------------------------------------------------------------
@app.post("/unidades/{uid}/filho", response_class=HTMLResponse)
def add_filho(req: Request, uid: str):
    marcar_ponto()
    novo = Unidade(
        id=novo_id(), codigo=proximo_codigo(), nome="Nova unidade", tipo="area",
        parent_id=uid, ordem=(len(mapa_filhos().get(uid, [])) + 1) * 10,
        responsavel="", cargo="", responsabilidades=[],
    )
    ESTADO.unidades[novo.id] = novo
    ESTADO.selecionado = novo.id
    commit("criar", novo.id, "novo subordinado pelo canvas", {"parent_id": uid})
    return canvas(req, oob_painel(req, novo.id))


@app.post("/unidades/{uid}/duplicar", response_class=HTMLResponse)
def duplicar(req: Request, uid: str):
    marcar_ponto()
    orig = ESTADO.unidades[uid]
    novo = Unidade(
        id=novo_id(), codigo=proximo_codigo(), nome=f"{orig.nome} (cópia)",
        tipo=orig.tipo, parent_id=orig.parent_id, ordem=orig.ordem + 5,
        responsavel="", cargo=orig.cargo,
        responsabilidades=copy.deepcopy(orig.responsabilidades),
    )
    ESTADO.unidades[novo.id] = novo
    renumerar(novo.parent_id)
    ESTADO.selecionado = novo.id
    commit("criar", novo.id, "duplicação pelo canvas", {"origem": uid})
    return canvas(req, oob_painel(req, novo.id))


@app.post("/unidades/{uid}/reordenar", response_class=HTMLResponse)
def reordenar(req: Request, uid: str, direcao: str = "direita"):
    marcar_ponto()
    u = ESTADO.unidades[uid]
    u.ordem += 15 if direcao == "direita" else -15
    renumerar(u.parent_id)
    commit("alterar", uid, f"reordenar para {direcao}", {"ordem": u.ordem})
    return canvas(req)


@app.post("/unidades/{uid}/promover", response_class=HTMLResponse)
def promover(req: Request, uid: str):
    marcar_ponto()
    u = ESTADO.unidades[uid]
    avo = ESTADO.unidades[u.parent_id].parent_id
    if avo is not None:
        u.parent_id = avo
        renumerar(avo)
        commit("mover", uid, "promover um nível", {"novo_pai": avo})
    return canvas(req)


@app.post("/unidades/{uid}/rebaixar", response_class=HTMLResponse)
def rebaixar(req: Request, uid: str):
    """Vira filho do irmao imediatamente anterior."""
    marcar_ponto()
    u = ESTADO.unidades[uid]
    irmaos = mapa_filhos().get(u.parent_id, [])
    ids = [x.id for x in irmaos]
    idx = ids.index(uid)
    if idx > 0:
        alvo = ids[idx - 1]
        u.parent_id = alvo
        u.ordem = (len(mapa_filhos().get(alvo, [])) + 1) * 10
        commit("mover", uid, "rebaixar um nível", {"novo_pai": alvo})
    return canvas(req)


@app.post("/unidades/{uid}/mover", response_class=HTMLResponse)
def mover(req: Request, uid: str, destino: str = Form(...)):
    """Reparent explicito. Guarda de ciclo: SPEC RF-02 / INV-02."""
    marcar_ponto()
    u = ESTADO.unidades[uid]
    if destino == uid or destino in descendentes(uid):
        ESTADO.historico.pop()
        return canvas(req, '<div id="alerta" class="alerta">Movimento recusado: '
                           'o destino é descendente da unidade (ciclo detectado).</div>')
    u.parent_id = destino
    u.ordem = (len(mapa_filhos().get(destino, [])) + 1) * 10
    commit("mover", uid, "reparent pelo painel", {"novo_pai": destino})
    return canvas(req)


@app.post("/unidades/{uid}/salvar", response_class=HTMLResponse)
def salvar(req: Request, uid: str,
           nome: str = Form(...), tipo: str = Form(...),
           responsavel: str = Form(""), cargo: str = Form(""),
           responsabilidades: str = Form("")):
    marcar_ponto()
    u = ESTADO.unidades[uid]
    u.nome = nome.strip() or u.nome
    u.tipo = tipo
    u.responsavel = responsavel.strip()
    u.cargo = cargo.strip()
    itens = []
    for linha in responsabilidades.splitlines():
        texto = linha.strip()
        if not texto:
            continue
        delegada = texto.startswith(">")
        itens.append({
            "descricao": texto.lstrip("> ").strip()[:200],
            "origem": "delegada" if delegada else "propria",
            "delegada_para": None,
        })
    u.responsabilidades = itens
    commit("alterar", uid, "edição pelo painel", {"nome": u.nome, "itens": len(itens)})
    return canvas(req)


@app.delete("/unidades/{uid}", response_class=HTMLResponse)
def excluir(req: Request, uid: str):
    marcar_ponto()
    u = ESTADO.unidades[uid]
    if u.parent_id is None:
        return canvas(req)
    for f in mapa_filhos().get(uid, []):        # filhos sobem para o avo
        f.parent_id = u.parent_id
    del ESTADO.unidades[uid]
    renumerar(u.parent_id)
    if ESTADO.selecionado == uid:
        ESTADO.selecionado = None
    commit("inativar", uid, "exclusão pelo canvas", {"nome": u.nome})
    return canvas(req, oob_painel(req, None))


# --- comandos de canvas ---------------------------------------------------
@app.post("/orientacao", response_class=HTMLResponse)
def alternar(req: Request):
    ESTADO.orientacao = "vertical" if ESTADO.orientacao == "invertida" else "invertida"
    gravar()
    return canvas(req)


@app.post("/desfazer", response_class=HTMLResponse)
def desfazer(req: Request):
    if ESTADO.historico:
        aplicar_snapshot(ESTADO.historico.pop())
        gravar()
    return canvas(req)


@app.post("/restaurar", response_class=HTMLResponse)
def restaurar(req: Request):
    marcar_ponto()
    semear()
    return canvas(req)


@app.get("/export.svg")
def export_svg(req: Request):
    svg = render("_canvas.html", request=req,
                 layout=calcular_layout(ESTADO.orientacao, None))
    return Response(svg, media_type="image/svg+xml", headers={
        "Content-Disposition": 'attachment; filename="organograma.svg"'})


@app.get("/export.json")
def export_json():
    return JSONResponse(json.loads(serializar()), headers={
        "Content-Disposition": 'attachment; filename="organograma.json"'})
