"""
GPlanSiS|Peoples — One-on-One: 1:1 (FUP), PRM e desenvolvimento por pessoa.

Módulo PURO como `cgv.py`/`talentos.py`/`dcr.py`: recebe `unidades` (+ `mapa_cc`),
devolve dicionários, roda sem servidor e sem estado. Deriva a base da estrutura
(`dcr.medir`); a camada editável é um overlay em `Config.onebyone`, espelhado no
Postgres `org.onebyone_item` quando há banco, e sempre no `estado.json`.

SIGILO (LGPD, nível pessoa) — a novidade deste módulo. Cada registro (uma conversa
1:1, um rock, um issue, uma missão…) pertence a DUAS pessoas: o liderado (`ref`) e o
líder no momento em que foi escrito (`lider_ref`). Guardamos as duas MATRÍCULAS, não
ids de nó (que se recriam a cada carga) — assim a conversa fica presa aos dois que a
tiveram: se a pessoa troca de gestor, o gestor novo NÃO herda o histórico privado; ele
começa os seus próprios 1:1. A leitura só é liberada para quem é participante — ou para
RH/compliance (uma concessão explícita e auditável, ver `pode_ver`). A cadeia de gestão
intermediária não vê. `visiveis()` é o funil por onde toda leitura passa.
"""
from __future__ import annotations

from datetime import date

from . import dcr
from . import dominio

IDIOMA = "pt-BR"


def _t(texto: str) -> str:
    from . import idiomas
    return idiomas.traduzir(texto, IDIOMA)


# ---------------------------------------------------------------------------
# Vocabulário — tipos de registro e enums (tuplas + dicts derivados, como a Conversa de Valor)
# ---------------------------------------------------------------------------
# Um só overlay guarda vários tipos de item, discriminados por `tipo`. Assim a
# pessoa tem, num lugar, suas conversas, rocks, issues, objetivos e missões — e a
# ACL de sigilo vale igual para todos.
TIPOS = ("conversa", "rock", "issue", "objetivo", "missao", "pulso", "ciclo")
ROTULO_TIPO = {
    "conversa": "Conversa 1:1", "rock": "Rock", "issue": "Issue",
    "objetivo": "Objetivo do trimestre", "missao": "Missão de evolução",
    "pulso": "Pulso", "ciclo": "Ciclo de vida",
}

TRIMESTRES = (1, 2, 3, 4)

CADENCIAS = (("semanal", "Semanal"), ("quinzenal", "Quinzenal"),
             ("mensal", "Mensal"), ("trimestral", "Trimestral"))
COD_CADENCIA = frozenset(c for c, _ in CADENCIAS)
DIAS_CADENCIA = {"semanal": 7, "quinzenal": 14, "mensal": 30, "trimestral": 90}

# EOS: rocks são as prioridades do trimestre; issues são a lista de pendências que
# a dinâmica IDS (Identificar, Discutir, Resolver) queima; missões vêm do PDI/Conversa de Valor.
STATUS_ROCK = (("on", "No trilho"), ("off", "Fora do trilho"), ("feito", "Concluído"))
STATUS_ISSUE = (("aberto", "Aberto"), ("discutindo", "Em discussão"),
                ("resolvido", "Resolvido"))
STATUS_OBJ = (("on", "No trilho"), ("risco", "Em risco"), ("atingido", "Atingido"))
STATUS_MISSAO = (("proposta", "Proposta"), ("andamento", "Em andamento"),
                 ("concluida", "Concluída"), ("parada", "Parada"))
ESTAGIOS = (("onboarding", "Onboarding"), ("desenvolvimento", "Desenvolvimento"),
            ("consolidado", "Consolidado"), ("transicao", "Transição"),
            ("desligamento", "Desligamento"))

ROTULO_STATUS = {c: r for c, r in
                 (*STATUS_ROCK, *STATUS_ISSUE, *STATUS_OBJ, *STATUS_MISSAO)}
ROTULO_ESTAGIO = {c: r for c, r in ESTAGIOS}
ROTULO_CADENCIA = {c: r for c, r in CADENCIAS}

# Escala de sentimento/energia do pulso (Escuta Ativa) — 1 (baixo) a 5 (alto).
SENTIMENTO_MIN, SENTIMENTO_MAX = 1, 5

LIMITE_CAMPO = 4000
CAMPOS_SNAP = ("nome", "cargo", "lider")     # retrato de como a pessoa estava
ANO_PADRAO = 2026

# Especificação de conteúdo por tipo: campos de texto, inteiros (com faixa) e enums
# (com o conjunto de códigos válidos). Tudo type-specific mora em `conteudo`, como o
# formulário da Conversa de Valor — o topo do registro é só identidade + sigilo.
_CAMPOS = {
    "conversa": {"texto": ("pauta", "notas", "proximos_passos"),
                 "int": {"sentimento": (SENTIMENTO_MIN, SENTIMENTO_MAX)},
                 "enum": {"cadencia": COD_CADENCIA}},
    "rock": {"texto": ("titulo", "descricao"),
             "int": {"progresso": (0, 100)},
             "enum": {"status": frozenset(c for c, _ in STATUS_ROCK)}},
    "issue": {"texto": ("titulo", "descricao", "resolucao"), "int": {},
              "enum": {"status": frozenset(c for c, _ in STATUS_ISSUE)}},
    "objetivo": {"texto": ("titulo", "descricao", "metrica"), "int": {},
                 "enum": {"status": frozenset(c for c, _ in STATUS_OBJ)}},
    "missao": {"texto": ("titulo", "acao", "evolucao", "prazo", "origem"), "int": {},
               "enum": {"status": frozenset(c for c, _ in STATUS_MISSAO)}},
    "pulso": {"texto": ("comentario",),
              "int": {"sentimento": (SENTIMENTO_MIN, SENTIMENTO_MAX),
                      "energia": (SENTIMENTO_MIN, SENTIMENTO_MAX)}, "enum": {}},
    "ciclo": {"texto": ("nota",), "int": {},
              "enum": {"estagio": frozenset(c for c, _ in ESTAGIOS)}},
}


# ---------------------------------------------------------------------------
# Identidade e sigilo
# ---------------------------------------------------------------------------
def ref_de(linha: dict) -> str:
    """Identidade durável da pessoa = matrícula (`codigo`, SAP), como na Conversa de Valor. O id
    do nó se recria a cada import; a matrícula sobrevive a troca de área/cargo/gestor."""
    return str(linha.get("codigo") or f"u:{linha.get('id')}").strip()[:60]


def matricula_do_no(unidades: dict, node_id: str | None) -> str:
    """Matrícula de quem está logado (o nó `usuario_id`), para casar com `ref`/
    `lider_ref` na ACL. Vazio se o nó não existe (login sem vínculo no organograma)."""
    u = (unidades or {}).get(node_id or "")
    return (str(u.codigo).strip()[:60] if u and u.codigo else "")


def participantes(reg: dict) -> set[str]:
    """As duas matrículas que podem ler o registro: o liderado e o líder que o
    escreveu. Conjunto (uma delas pode faltar — líder externo/desligado)."""
    return {m for m in (str(reg.get("ref") or "").strip(),
                        str(reg.get("lider_ref") or "").strip()) if m}


def pode_ver(reg: dict, matricula: str, rh: bool = False) -> bool:
    """A ACL de sigilo, PURA. Vê quem é participante (líder OU liderado) — ou quem
    tem a concessão de RH/compliance (`rh=True`, resolvida no `main` a partir de
    Admin/superadmin ou de um grant explícito). A cadeia intermediária não entra.
    Fail-closed: sem matrícula e sem RH, não vê."""
    return bool(rh) or (bool(matricula) and matricula in participantes(reg))


def visiveis(overlay, matricula: str, rh: bool = False) -> list[dict]:
    """O funil único de leitura: filtra o overlay pela ACL. Toda vista, lista, CSV
    e export DEVE passar por aqui — nunca ler o overlay cru."""
    return [r for r in (overlay or []) if pode_ver(r, matricula, rh)]


# ---------------------------------------------------------------------------
# Normalização (entrada de formulário não é dado confiável)
# ---------------------------------------------------------------------------
def normalizar_conteudo(tipo: str, bruto) -> dict:
    """Saneia o `conteudo` conforme o tipo: texto cortado no limite, inteiros
    presos à faixa, enums validados contra o conjunto do tipo (fora vira '')."""
    spec = _CAMPOS.get(tipo)
    if not spec:
        return {}
    c = bruto if isinstance(bruto, dict) else {}
    out: dict = {}
    for f in spec["texto"]:
        out[f] = str(c.get(f) or "").strip()[:LIMITE_CAMPO]
    for f, (lo, hi) in spec["int"].items():
        try:
            out[f] = max(lo, min(hi, int(c.get(f))))
        except (TypeError, ValueError):
            out[f] = 0
    for f, validos in spec["enum"].items():
        v = str(c.get(f) or "").strip()
        out[f] = v if v in validos else ""
    return out


def conteudo_tem_sinal(tipo: str, c: dict) -> bool:
    """Há QUALQUER coisa preenchida? Texto, inteiro > 0 ou enum escolhido. Registro
    sem sinal não ocupa lugar — um formulário aberto e fechado não polui a base."""
    if not isinstance(c, dict):
        return False
    return (any((c.get(f) or "").strip() for f in _CAMPOS.get(tipo, {}).get("texto", ()))
            or any(int(c.get(f) or 0) > 0 for f in _CAMPOS.get(tipo, {}).get("int", {}))
            or any(c.get(f) for f in _CAMPOS.get(tipo, {}).get("enum", {})))


def item_vazio(tipo: str, ref: str = "", lider_ref: str = "",
               ano: int = 0, trimestre: int = 0) -> dict:
    return {"id": "", "tipo": tipo, "ref": ref, "lider_ref": lider_ref,
            "ano": ano, "trimestre": trimestre, "data": "",
            "conteudo": normalizar_conteudo(tipo, {}),
            **{c: "" for c in CAMPOS_SNAP}, "por": ""}


def normalizar_overlay(bruto: list[dict] | None) -> list[dict]:
    """Uma linha por `id`. Tipo válido; `ref` obrigatório; ano plausível (ou 0 =
    item datado sem ano, como uma conversa); trimestre em 1..4 (ou 0). Só persiste
    o que tem sinal no conteúdo ou uma data."""
    saida: dict[str, dict] = {}
    for r in bruto or []:
        r = r or {}
        tipo = str(r.get("tipo") or "").strip()
        if tipo not in TIPOS:
            continue
        rid = str(r.get("id") or "").strip()[:40]
        ref = str(r.get("ref") or "").strip()[:60]
        if not rid or not ref:
            continue
        try:
            ano = int(r.get("ano") or 0)
        except (TypeError, ValueError):
            ano = 0
        if ano and not (2000 <= ano <= 2100):
            continue
        try:
            tri = int(r.get("trimestre") or 0)
        except (TypeError, ValueError):
            tri = 0
        tri = tri if tri in TRIMESTRES else 0
        conteudo = normalizar_conteudo(tipo, r.get("conteudo"))
        linha = {
            "id": rid, "tipo": tipo, "ref": ref,
            "lider_ref": str(r.get("lider_ref") or "").strip()[:60],
            "ano": ano, "trimestre": tri,
            "data": str(r.get("data") or "").strip()[:10],
            "conteudo": conteudo,
        }
        for c in CAMPOS_SNAP:
            linha[c] = str(r.get(c) or "").strip()[:120]
        linha["por"] = str(r.get("por") or "").strip()[:120]
        if conteudo_tem_sinal(tipo, conteudo) or linha["data"]:
            saida[rid] = linha
    return sorted(saida.values(),
                  key=lambda r: (r["ref"], -(r["ano"] or 0), r["tipo"], r["data"]))


def por_pessoa(overlay, ref: str, tipo: str | None = None) -> list[dict]:
    """Os itens de uma pessoa (por matrícula), opcionalmente de um tipo. Não aplica
    a ACL — quem chama já filtrou com `visiveis()`."""
    return [r for r in (overlay or [])
            if r.get("ref") == ref and (tipo is None or r.get("tipo") == tipo)]


# ---------------------------------------------------------------------------
# Base derivada da estrutura (uma linha por pessoa) — reusa dcr.medir
# ---------------------------------------------------------------------------
def base(unidades: dict, mapa_cc: dict | None = None) -> list[dict]:
    """Uma linha por pessoa (id, codigo/matrícula, nome, cargo, setor, líder…),
    exatamente como a Conversa de Valor: `dcr.medir`. É sobre esta base que o overlay se apoia."""
    return dcr.medir(unidades, mapa_cc)


# ---------------------------------------------------------------------------
# Conversas 1:1 (FUP) e cadência — a vista
# ---------------------------------------------------------------------------
def _iso(v):
    try:
        a, m, d = (int(x) for x in str(v).split("-")[:3])
        return date(a, m, d)
    except Exception:
        return None


def proxima_data(ultima: str, cadencia: str) -> str:
    """A próxima 1:1 = última + os dias da cadência. '' se não há última data."""
    from datetime import timedelta
    d = _iso(ultima)
    if not d:
        return ""
    return (d + timedelta(days=DIAS_CADENCIA.get(cadencia, 14))).isoformat()


def conversas_de(overlay, ref: str) -> list[dict]:
    """As conversas 1:1 de uma pessoa (por matrícula), da mais recente para a mais
    antiga. Quem chama já passou o overlay por `visiveis()` — o sigilo vale antes."""
    cs = [r for r in (overlay or []) if r.get("tipo") == "conversa" and r.get("ref") == ref]
    return sorted(cs, key=lambda r: r.get("data") or "", reverse=True)


def status_1a1(overlay, ref: str, hoje=None) -> dict:
    """O pulso da cadência de uma pessoa: quantas conversas, a última, a cadência
    vigente (da última), a próxima prevista e se está atrasada."""
    hoje = hoje or date.today()
    cs = conversas_de(overlay, ref)
    ultima = cs[0] if cs else None
    cad = ((ultima or {}).get("conteudo", {}).get("cadencia") or "quinzenal")
    prox = proxima_data(ultima["data"], cad) if ultima and ultima.get("data") else ""
    return {"n": len(cs), "ultima": (ultima or {}).get("data", ""), "cadencia": cad,
            "proxima": prox, "atrasada": bool(prox and prox < hoje.isoformat()),
            "ultimo_sentimento": (ultima or {}).get("conteudo", {}).get("sentimento", 0)}


def equipe_de(linhas, eu_id: str) -> list[dict]:
    """Os liderados diretos de quem está logado (conexão da equipe pela hierarquia):
    as linhas cujo `parent_id` é o nó do líder."""
    return [l for l in linhas if l.get("parent_id") == eu_id]


def agenda(roster, overlay, hoje=None) -> list[dict]:
    """A agenda de 1:1: um cartão por pessoa do `roster` (os liderados diretos de
    quem está logado, ou toda a base para RH/admin), com o status da cadência.
    `overlay` já vem filtrado pelo sigilo (`visiveis`)."""
    hoje = hoje or date.today()
    saida = []
    for l in roster:
        st = status_1a1(overlay, l["codigo"], hoje)
        saida.append({"id": l["id"], "ref": l["codigo"], "nome": l["nome"],
                      "cargo": l.get("cargo", ""), "setor": l.get("setor", ""),
                      **st})
    # Atrasadas primeiro; depois quem nunca teve 1:1; depois por nome.
    saida.sort(key=lambda x: (not x["atrasada"], x["n"] > 0, x["nome"].lower()))
    return saida


def resumo_agenda(ag: list[dict]) -> dict:
    return {"equipe": len(ag), "atrasadas": sum(1 for x in ag if x["atrasada"]),
            "sem_1a1": sum(1 for x in ag if x["n"] == 0),
            "conversas": sum(x["n"] for x in ag)}


def ficha(ref: str, linhas, overlay, ano: int = 0, trimestre: int = 0,
          hoje=None, carreira=None) -> dict | None:
    """A ficha completa de uma pessoa: identidade + conversas 1:1 + rocks e objetivo
    do trimestre + issues + carreira (o quê é puxado da Conversa de Valor/Talentos vem em
    `carreira`). Tudo já filtrado pelo sigilo por quem chamou. `None` se a matrícula
    não está na base (vira aviso, não erro)."""
    porref = {ref_de(l): l for l in linhas}
    l = porref.get(ref)
    if not l:
        return None
    return {"ref": ref, "id": l["id"], "nome": l["nome"], "cargo": l.get("cargo", ""),
            "setor": l.get("setor", ""), "lider": l.get("lider_nome", ""),
            "parent_id": l.get("parent_id"), "ano": ano, "trimestre": trimestre,
            "conversas": conversas_de(overlay, ref),
            "status": status_1a1(overlay, ref, hoje),
            "rocks": rocks(overlay, ref, ano, trimestre),
            "issues": issues(overlay, ref),
            "objetivo": objetivo(overlay, ref, ano, trimestre),
            "carreira_obj": carreira_longo_prazo(overlay, ref),
            "carreira": carreira or {},
            "pulsos": pulsos_de(overlay, ref)[:6],
            "ciclo": ciclo_atual(overlay, ref),
            "missoes": missoes(overlay, ref)}


# ---------------------------------------------------------------------------
# Rocks (prioridades do trimestre), Issues (IDS) e Objetivos — EOS por pessoa
# ---------------------------------------------------------------------------
def trimestre_atual(hoje=None) -> int:
    hoje = hoje or date.today()
    return (hoje.month - 1) // 3 + 1


def campos_do_tipo(tipo: str) -> list[str]:
    """Todos os nomes de campo do `conteudo` de um tipo — para o servidor ler do
    formulário exatamente o que aquele tipo tem."""
    spec = _CAMPOS.get(tipo, {})
    return list(spec.get("texto", ())) + list(spec.get("int", {})) + list(spec.get("enum", {}))


def itens(overlay, ref: str, tipo: str, ano=None, trimestre=None) -> list[dict]:
    """Os itens de um tipo de uma pessoa, opcionalmente presos a ano/trimestre.
    `overlay` já veio filtrado pelo sigilo."""
    out = [r for r in (overlay or []) if r.get("tipo") == tipo and r.get("ref") == ref]
    if ano is not None:
        out = [r for r in out if (r.get("ano") or 0) == ano]
    if trimestre is not None:
        out = [r for r in out if (r.get("trimestre") or 0) == trimestre]
    return out


def rocks(overlay, ref: str, ano: int, trimestre: int) -> list[dict]:
    """Os rocks (prioridades) da pessoa no trimestre, por título."""
    return sorted(itens(overlay, ref, "rock", ano, trimestre),
                  key=lambda r: r.get("conteudo", {}).get("titulo", "").lower())


_ORDEM_ISSUE = {"aberto": 0, "discutindo": 1, "resolvido": 2}


def issues(overlay, ref: str) -> list[dict]:
    """Os issues (IDS) da pessoa: abertos primeiro, resolvidos por último."""
    return sorted(itens(overlay, ref, "issue"),
                  key=lambda r: (_ORDEM_ISSUE.get(r.get("conteudo", {}).get("status"), 3),
                                 r.get("conteudo", {}).get("titulo", "").lower()))


def objetivo(overlay, ref: str, ano: int, trimestre: int) -> dict | None:
    """O objetivo principal do trimestre (um só). `None` se não há."""
    os_ = itens(overlay, ref, "objetivo", ano, trimestre)
    return os_[0] if os_ else None


def carreira_longo_prazo(overlay, ref: str) -> dict | None:
    """O objetivo de carreira / longo prazo — 'até onde posso chegar'. É um objetivo
    com trimestre 0 (não pertence a um trimestre): a meta que atravessa os anos."""
    os_ = [r for r in itens(overlay, ref, "objetivo") if (r.get("trimestre") or 0) == 0]
    return os_[0] if os_ else None


# ---------------------------------------------------------------------------
# PRM — Escuta Ativa (pulso/sentimento), alertas de burnout, ciclo de vida
# ---------------------------------------------------------------------------
LIMIAR_SPAN = 8            # a partir de quantos liderados diretos o span pesa
CLIMA_BAIXO = 2            # sentimento 1–2 acende o alerta
# Os sinais de burnout, como texto — traduzidos na tela por variável. Constante
# para o i18n enxergar (chaves_indiretas) e para o código não repetir a string.
SINAL_ATRASO, SINAL_CLIMA, SINAL_SPAN = "1:1 atrasado", "clima baixo", "span alto"
SINAIS_BURNOUT = (SINAL_ATRASO, SINAL_CLIMA, SINAL_SPAN)


def pulsos_de(overlay, ref: str) -> list[dict]:
    return sorted((r for r in (overlay or []) if r.get("tipo") == "pulso"
                   and r.get("ref") == ref),
                  key=lambda r: r.get("data") or "", reverse=True)


def ultimo_clima(overlay, ref: str) -> int:
    """O sinal de sentimento mais recente (1–5): do último pulso, ou da última
    conversa 1:1. 0 = sem sinal."""
    p = pulsos_de(overlay, ref)
    if p and p[0].get("conteudo", {}).get("sentimento"):
        return p[0]["conteudo"]["sentimento"]
    c = conversas_de(overlay, ref)
    if c and c[0].get("conteudo", {}).get("sentimento"):
        return c[0]["conteudo"]["sentimento"]
    return 0


def ciclo_atual(overlay, ref: str) -> dict | None:
    cs = itens(overlay, ref, "ciclo")
    return cs[0] if cs else None


def alertas_burnout(roster, overlay, filhos_por: dict, hoje=None) -> list[dict]:
    """Os sinais de risco de burnout, DERIVADOS — não é um campo que ninguém
    mantém. O GATILHO é de ENGAJAMENTO: 1:1 atrasado (cadência furada) ou clima
    baixo (pulso/conversa 1–2). O span alto (muitos liderados diretos) NÃO alerta
    sozinho — é fator AGRAVANTE, entra só quando já há um sinal de engajamento.
    Assim o painel não grita 'burnout' para quem apenas tem um time grande: sem
    dado de engajamento, ninguém acende. Insumo da conversa, não veredito."""
    hoje = hoje or date.today()
    alertas = []
    for l in roster:
        ref = l["codigo"]
        sinais = []
        if status_1a1(overlay, ref, hoje)["atrasada"]:
            sinais.append(SINAL_ATRASO)
        clima = ultimo_clima(overlay, ref)
        if 1 <= clima <= CLIMA_BAIXO:
            sinais.append(SINAL_CLIMA)
        # Span alto só conta como agravante de um sinal de engajamento já aceso.
        n_reports = len(filhos_por.get(l["id"], []))
        if sinais and n_reports >= LIMIAR_SPAN:
            sinais.append(SINAL_SPAN)
        if sinais:
            alertas.append({"ref": ref, "nome": l["nome"], "cargo": l.get("cargo", ""),
                            "sinais": sinais, "n": len(sinais), "clima": clima,
                            "reports": n_reports})
    alertas.sort(key=lambda a: (-a["n"], a["clima"] or 9))
    return alertas


def panorama_prm(roster, overlay, filhos_por: dict, hoje=None) -> dict:
    """O painel do PRM sobre o recorte: distribuição de clima, alertas de burnout e
    a distribuição por estágio do ciclo de vida."""
    hoje = hoje or date.today()
    climas = [c for l in roster if (c := ultimo_clima(overlay, l["codigo"]))]
    estagios = {}
    for l in roster:
        cv = ciclo_atual(overlay, l["codigo"])
        est = (cv or {}).get("conteudo", {}).get("estagio", "") if cv else ""
        if est:
            estagios[est] = estagios.get(est, 0) + 1
    alertas = alertas_burnout(roster, overlay, filhos_por, hoje)
    # Span alto é informação estrutural (fator de risco), não um alerta por si —
    # conta-se à parte para o painel mostrar o contexto sem inflar o burnout.
    span_alto = sum(1 for l in roster
                    if len(filhos_por.get(l["id"], [])) >= LIMIAR_SPAN)
    return {"clima_medio": round(sum(climas) / len(climas), 1) if climas else 0,
            "com_pulso": len(climas), "total": len(roster),
            "alertas": alertas, "n_alertas": len(alertas), "span_alto": span_alto,
            "limiar_span": LIMIAR_SPAN,
            "estagios": [{"cod": c, "rotulo": ROTULO_ESTAGIO.get(c, c), "n": n}
                         for c, n in sorted(estagios.items(), key=lambda x: -x[1])]}


# ---------------------------------------------------------------------------
# Missões de evolução — a ponte Conversa de Valor → GPlanSiS|OS
# ---------------------------------------------------------------------------
_ORDEM_MISSAO = {"proposta": 0, "andamento": 1, "parada": 2, "concluida": 3}
ORIGEM_CGV = "Conversa de Valor · PDI"


def missoes(overlay, ref: str) -> list[dict]:
    """As missões de evolução da pessoa: em aberto primeiro, concluídas por último."""
    return sorted(itens(overlay, ref, "missao"),
                  key=lambda r: (_ORDEM_MISSAO.get(r.get("conteudo", {}).get("status"), 1),
                                 r.get("conteudo", {}).get("titulo", "").lower()))


def missoes_do_cgv(ref: str, cgv_registros, ano=None) -> list[dict]:
    """Os rascunhos de missão vindos do PDI da Conversa de Valor (a 'ação imediata'/plano de
    desenvolvimento da pessoa). Cada competência do PDI vira uma missão proposta —
    o líder e o liderado acompanham a evolução aqui, sem reescrever o que a Conversa de Valor já
    tem. Integração INT-2."""
    cgvs = sorted((r for r in (cgv_registros or []) if r.get("ref") == ref),
                  key=lambda r: r.get("ano", 0), reverse=True)
    pdi = next((r.get("conteudo", {}).get("pdi") for r in cgvs
                if r.get("conteudo", {}).get("pdi")), []) or []
    drafts = []
    for p in pdi:
        comp = str((p or {}).get("comp") or "").strip()
        acao = str((p or {}).get("acao") or "").strip()
        if not (comp or acao):
            continue
        drafts.append({"titulo": comp or acao[:60], "acao": acao,
                       "prazo": str((p or {}).get("prazo") or "").strip(),
                       "origem": ORIGEM_CGV, "status": "proposta", "evolucao": ""})
    return drafts


# ---------------------------------------------------------------------------
# Persistência — dual (Postgres opcional + estado.json sempre), igual a Conversa de Valor
# ---------------------------------------------------------------------------
def banco_pronto() -> bool:
    from . import banco
    return banco.situacao().get("pronto", False)


def _conectar():
    from . import banco
    pg = banco.driver()
    return pg.connect(banco.dsn(), connect_timeout=8) if pg and banco.dsn() else None


def salvar_no_banco(reg: dict, slug: str = "peoples") -> tuple[bool, str]:
    """UPSERT idempotente por (slug, id). Silencioso sem banco — o overlay já
    guardou; o Postgres é o espelho durável que atravessa reimportações."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return False, "sem banco"
        import json as _json
        conteudo = _json.dumps(normalizar_conteudo(reg.get("tipo"), reg.get("conteudo")),
                               ensure_ascii=False)
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO org.onebyone_item (id, slug, tipo, ref, lider_ref, "
                "ano, trimestre, data_item, conteudo, pessoa_nome, pessoa_cargo, "
                "lider_nome, registrado_por) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s) "
                "ON CONFLICT (slug, id) DO UPDATE SET "
                "tipo=EXCLUDED.tipo, ref=EXCLUDED.ref, lider_ref=EXCLUDED.lider_ref, "
                "ano=EXCLUDED.ano, trimestre=EXCLUDED.trimestre, "
                "data_item=EXCLUDED.data_item, conteudo=EXCLUDED.conteudo, "
                "pessoa_nome=EXCLUDED.pessoa_nome, pessoa_cargo=EXCLUDED.pessoa_cargo, "
                "lider_nome=EXCLUDED.lider_nome, "
                "registrado_por=EXCLUDED.registrado_por, atualizado_em=now()",
                (reg["id"], slug, reg["tipo"], reg["ref"], reg.get("lider_ref") or "",
                 reg.get("ano") or 0, reg.get("trimestre") or 0,
                 reg.get("data") or None, conteudo,
                 reg.get("nome") or "", reg.get("cargo") or "",
                 reg.get("lider") or "", reg.get("por") or ""))
        con.commit()
        return True, "gravado no banco"
    except Exception as erro:                          # noqa: BLE001
        return False, str(erro).strip().splitlines()[0][:200]
    finally:
        if con is not None:
            con.close()


def apagar_do_banco(item_id: str, slug: str = "peoples") -> tuple[bool, str]:
    """Remove um item do banco (o usuário pode apagar uma conversa/rock). Só o
    overlay já basta em dev; o banco acompanha quando existe."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return False, "sem banco"
        with con.cursor() as cur:
            cur.execute("DELETE FROM org.onebyone_item WHERE slug=%s AND id=%s",
                        (slug, item_id))
        con.commit()
        return True, "apagado do banco"
    except Exception as erro:                          # noqa: BLE001
        return False, str(erro).strip().splitlines()[0][:200]
    finally:
        if con is not None:
            con.close()


def carregar_do_banco(slug: str = "peoples") -> list[dict]:
    """Todos os itens do banco, no formato do overlay. `[]` sem banco."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return []
        with con.cursor() as cur:
            cur.execute(
                "SELECT id, tipo, ref, lider_ref, ano, trimestre, "
                "to_char(data_item,'YYYY-MM-DD'), conteudo, pessoa_nome, "
                "pessoa_cargo, lider_nome FROM org.onebyone_item WHERE slug=%s",
                (slug,))
            return [{"id": r[0], "tipo": r[1], "ref": r[2], "lider_ref": r[3] or "",
                     "ano": r[4] or 0, "trimestre": r[5] or 0, "data": r[6] or "",
                     "conteudo": r[7] if isinstance(r[7], dict) else {},
                     "nome": r[8] or "", "cargo": r[9] or "", "lider": r[10] or ""}
                    for r in cur.fetchall()]
    except Exception:                                  # noqa: BLE001
        return []
    finally:
        if con is not None:
            con.close()


def fundir(overlay: list[dict] | None, do_banco: list[dict] | None) -> list[dict]:
    """Overlay vivo + histórico do banco, sem duplicar. O overlay vence no conflito
    de mesmo `id` (é o que acabou de ser editado nesta sessão)."""
    idx = {r["id"]: r for r in normalizar_overlay(do_banco)}
    idx.update({r["id"]: r for r in normalizar_overlay(overlay)})
    return sorted(idx.values(),
                  key=lambda r: (r["ref"], -(r["ano"] or 0), r["tipo"], r["data"]))
