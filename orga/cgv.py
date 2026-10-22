"""
GPlanSiS|Peoples — Conversa de Valor: Conversas que Geram Valor.

O feedback estruturado da GPlanSiS|Peoples, descrito no manual de Marina Albuquerque Sá
(rev. junho 2026). Três conversas por ano entre líder e liderado — a Completa
(mar/abr) e dois check-ins (jul, nov) — em torno de quatro elementos: entregas,
valores GPlanSiS, PDI e carreira; mais o feedback que o liderado dá à liderança,
sobre as competências Liderar/Gerenciar/Responsabilizar-se.

Este módulo segue a mesma gramática do Skills, e pelos mesmos motivos:

**Deriva da estrutura, não de cadastro novo.** O organograma já sabe quem
responde a quem (`parent_id` é o gestor direto). A AGENDA da Conversa de Valor — quem conversa
com quem, e quantas conversas faltam — sai daí sem ninguém redigitar. Cada
pessoa com líder tem três conversas no ano; cada líder acumula as da sua equipe.

**Planilhas são modelo, não fonte.** Os três arquivos de `docs/CGV/` são os
formulários oficiais em Excel, oferecidos para download. O sistema não os
importa: quem preenche uma Conversa de Valor usa o Excel e o envia ao RH, como o manual manda.
O que o sistema guarda é o ACOMPANHAMENTO — status, data e nota por pessoa e por
ciclo —, e isso é a única coisa que persiste.

**O acompanhamento é a camada editável.** Vive em `Config.cgv_registros`, passa
por `commit` e entra no Desfazer como qualquer alteração. Derivado e registrado
convivem: a agenda é deduzida, o status é escrito, e a tela diz qual é qual.

**Sem nota de avaliação, e é decisão.** A Conversa de Valor é conversa de desenvolvimento, não
ranking. O manual é explícito: "não há régua de nota". Guardar aqui um score por
pessoa transformaria uma ferramenta de diálogo em base de mérito — que é o
Comitê de Meritocracia, outro processo, com outra guarda. O sistema registra que
a conversa aconteceu, não quanto a pessoa "valeu" nela.
"""
from __future__ import annotations

from . import dcr
from .dominio import sem_acento

# Módulo puro: o idioma vigente entra como estado, ajustado por
# `main.alinhar_idioma()` antes de emitir. Mesma convenção de `dcr` e `dominio`.
IDIOMA = "pt-BR"


def _t(texto: str, **p) -> str:
    from . import idiomas
    return idiomas.traduzir(texto, IDIOMA, **p)


# ---------------------------------------------------------------------------
# OS FORMULÁRIOS CONTROLADOS
# ---------------------------------------------------------------------------
# Duas frentes, dois formulários. O código e a revisão vão impressos porque é por
# eles que a qualidade rastreia qual modelo gerou o documento — a mesma razão do
# GEP-FOR-003 no Skills.
FORMULARIOS = {
    "equipe": {"codigo": "GEP-FOR-006", "revisao": "00",
               "titulo": "Feedback de Desenvolvimento para Equipe"},
    "lideranca": {"codigo": "GEP-FOR-005", "revisao": "00",
                  "titulo": "Feedback de Desenvolvimento para Liderança"},
}
# O PDF do acompanhamento sai no formulário da equipe: é a conversa que o líder
# conduz com cada liderado, o eixo do processo.
FORMULARIO = FORMULARIOS["equipe"]

# ---------------------------------------------------------------------------
# OS TRÊS CICLOS
# ---------------------------------------------------------------------------
# `codigo, rótulo, quando, minutos`. A ordem é a do ano, e é ela que a agenda e
# a ficha seguem — nunca a ordem de quem preencheu primeiro (RNF-02).
CICLOS = (
    ("completa", "Conversa de Valor Completa", "Março e Abril", 60),
    ("checkin1", "Check-in 1", "Julho", 40),
    ("checkin2", "Check-in 2", "Novembro", 40),
)
ROTULO_CICLO = {c: r for c, r, _q, _m in CICLOS}
COD_CICLOS = tuple(c for c, _r, _q, _m in CICLOS)

# ---------------------------------------------------------------------------
# STATUS DE CADA CONVERSA
# ---------------------------------------------------------------------------
# `codigo, rótulo`. O código é o que persiste e a régua de contagem usa; o rótulo
# é o que a tela imprime, traduzível. Só "realizada" conta como feito.
STATUS = (
    ("pendente", "Pendente"),
    ("agendada", "Agendada"),
    ("realizada", "Realizada"),
)
ROTULO_STATUS = {c: r for c, r in STATUS}
STATUS_VALIDOS = frozenset(c for c, _r in STATUS)
STATUS_PADRAO = "pendente"

# ---------------------------------------------------------------------------
# OS VALORES GPlanSiS
# ---------------------------------------------------------------------------
# `codigo, sigla, rótulo, frase`. Os quatro valores GPlanSiS —
# Teamwork, Respect, Innovation, Ownership. Casa com o texto que a cultura já
# publica, para não haver duas versões do mesmo valor em duas telas.
VALORES_TRIO = (
    ("teamwork", "TEAMWORK", "Trabalho em equipe",
     "Acreditamos que só crescemos juntos."),
    ("respect", "RESPECT", "Respeito",
     "Somos abertos e acolhemos as diferenças."),
    ("innovation", "INNOVATION", "Inovação",
     "Superamos nossos desafios."),
    ("ownership", "OWNERSHIP", "Atitude de dono",
     "Somos conscientes e protagonistas."),
)

# ---------------------------------------------------------------------------
# AS COMPETÊNCIAS DA LIDERANÇA
# ---------------------------------------------------------------------------
# `codigo, rótulo, (comportamentos)`. É o formulário GEP-FOR-005: o que o
# liderado observa na sua liderança direta. Vem do manual, página "Elementos
# Formulário Lideranças".
COMPETENCIAS_LIDERANCA = (
    ("liderar", "Liderar", (
        "Inspira e é exemplo de comportamento.",
        "Constrói relações de confiança e respeito com a equipe.",
        "Contrata pessoas alinhadas com os valores da empresa.",
        "Incentiva e apoia o desenvolvimento das pessoas.",
        "Oferece feedback constante e construtivo.",
        "Promove uma cultura de trabalho positiva e motivadora.",
    )),
    ("gerenciar", "Gerenciar", (
        "Estabelece expectativas claras e faz acompanhamento.",
        "Delega tarefas de forma eficaz, conforme a competência e a "
        "maturidade de cada pessoa.",
        "Sistematiza e simplifica os processos para torná-los mais ágeis "
        "e eficazes.",
    )),
    ("responsabilizar", "Responsabilizar-se", (
        "Define a estratégia, os objetivos e as metas da equipe e se "
        "responsabiliza pelos resultados.",
        "Toma decisões difíceis em prol do propósito e dos valores da empresa.",
        "Assume riscos calculados e está à frente das mudanças necessárias.",
    )),
)

# ---------------------------------------------------------------------------
# OS QUATRO ELEMENTOS DA CONVERSA (formulário da equipe)
# ---------------------------------------------------------------------------
# `codigo, rótulo, o-que-fazer`. É o roteiro da Conversa de Valor Completa, na ordem do
# formulário GEP-FOR-006.
ELEMENTOS = (
    ("entregas", "Entregas e Resultados",
     "Principais contribuições do período. Reforçar os aspectos positivos, os "
     "aprendizados gerados e as oportunidades — visão de futuro."),
    ("valores", "Aderência aos Valores Organizacionais",
     "Comportamentos do dia a dia que endossam os valores GPlanSiS. Quais são "
     "pontos fortes a potencializar e quais merecem mais atenção."),
    ("pdi", "PDI — Plano de Desenvolvimento Individual",
     "Priorizar até três competências, definindo ações no formato 70/20/10 e "
     "prazos. O plano deve ser factível; o acompanhamento é do indivíduo, com "
     "o suporte da empresa."),
    ("carreira", "Expectativa de Carreira",
     "Os próximos passos desejados e como a organização pode apoiar. As etapas "
     "de desenvolvimento e o plano para alcançar a meta."),
)

# ---------------------------------------------------------------------------
# A RÉGUA 70/20/10 — aprendabilidade
# ---------------------------------------------------------------------------
REGRA_70_20_10 = (
    (70, "Aprendizado experimental",
     "Aprender fazendo: colocar o conhecimento em prática, experimentando."),
    (20, "Aprendizado social",
     "Aprender com os outros: ensinar, observar, modelar."),
    (10, "Aprendizado formal",
     "Aprender por cursos, leitura, documentários e vídeos."),
)

# ---------------------------------------------------------------------------
# PRINCÍPIOS DO FEEDBACK CONSTRUTIVO E CNV — o roteiro do manual interativo
# ---------------------------------------------------------------------------
PRINCIPIOS_FEEDBACK = (
    "Dar e receber feedback tem a ver com aprendizado e crescimento — intenção "
    "positiva.",
    "Um feedback de qualidade contextualiza a situação observada e a percepção "
    "sobre o comportamento.",
    "Oferecer ajuda para contribuir com o processo de aprendizado.",
    "Imaginar-se no lugar do outro em uma situação difícil.",
    "Enfatizar a perspectiva de pontos fortes — nossas qualidades como recursos "
    "para lidar com os desafios.",
    "O feedback deve olhar para frente.",
)

# Os quatro componentes da Comunicação Não-Violenta, com o exemplo do manual.
CNV = (
    ("observação", "O que aconteceu, sem julgamento.",
     "Eu observei que o relatório não sairá no prazo combinado"),
    ("sentimento", "Como isso faz você se sentir.",
     "e isso me deixa preocupado, porque"),
    ("necessidade", "A necessidade por trás do sentimento.",
     "é importante para mim que o prazo seja cumprido, para que os colegas "
     "confiem em nós."),
    ("pedido", "Um pedido ou acordo positivo.",
     "O que podemos fazer para entregar até sexta?"),
)

# As três etapas da dinâmica do processo, do manual.
DINAMICA = (
    ("preparacao", "Preparação",
     "A liderança usa o formulário como preparação — um arquivo por pessoa — e "
     "agenda cada Conversa de Valor. O colaborador faz a autoavaliação e prepara o feedback "
     "para a liderança direta."),
    ("feedback", "Feedback",
     "O colaborador começa pela autoavaliação. A liderança contribui com suas "
     "observações. Registra-se a versão final de consenso. O colaborador dá "
     "feedback à liderança pelo formulário GEP-FOR-005."),
    ("encerramento", "Encerramento",
     "O colaborador envia à liderança o formulário da liderança. A liderança "
     "encaminha ao RH e ao colaborador a versão final do feedback e o que "
     "recebeu. O colaborador recebe a versão enviada ao RH."),
)

VAZIO = "—"
LIMITE_NOTA = 4000
LIMITE_CAMPO = 4000

# O ano-referência do processo. A Conversa de Valor é anual (Completa em mar/abr, check-ins em
# jul/nov), então o ano faz parte da CHAVE de cada registro — é o que permite
# consultar as conversas de anos anteriores em vez de sobrescrevê-las. O módulo
# é puro e não lê relógio; quem chama passa o ano (main usa `datetime.now`).
ANO_PADRAO = 2026


# ---------------------------------------------------------------------------
# O CONTEÚDO DA CONVERSA — o formulário inteiro, agora no sistema
# ---------------------------------------------------------------------------
# A Conversa de Valor deixa de depender do Excel: cada conversa guarda o formulário completo
# (GEP-FOR-006), e não só o status. São os quatro elementos do manual —
# entregas, aderência aos quatro valores GPlanSiS, PDI (até 3 competências, com ação
# no formato 70/20/10 e prazo) e expectativa de carreira. Vai como JSONB no
# Postgres e como dict no estado: a MESMA forma nos dois, para o histórico
# atravessar anos e o dado viver no sistema, não num arquivo que roda por e-mail.
PDI_MAX = 3


# Cada conversa carrega, além do formulário da equipe (GEP-FOR-006), o feedback
# que o liderado dá à liderança (GEP-FOR-005): as três competências de liderança,
# cada uma com o registro observado. São CINCO elementos no total.
COD_LIDERANCA = tuple(c for c, _r, _it in COMPETENCIAS_LIDERANCA)


def conteudo_vazio() -> dict:
    return {
        "entregas": "",
        "valores": {c: "" for c, _s, _r, _f in VALORES_TRIO},
        "pdi": [{"comp": "", "acao": "", "prazo": ""} for _ in range(PDI_MAX)],
        "carreira": "",
        "lideranca": {c: "" for c in COD_LIDERANCA},
    }


def normalizar_conteudo(bruto) -> dict:
    """Saneia o formulário. Entrada de formulário não é dado confiável: campos
    cortados no limite, valores só nas chaves conhecidas, PDI fixo em 3 itens."""
    b = bruto if isinstance(bruto, dict) else {}
    def txt(v, n=LIMITE_CAMPO):
        return str(v if v is not None else "").strip()[:n]
    val = b.get("valores") if isinstance(b.get("valores"), dict) else {}
    lid = b.get("lideranca") if isinstance(b.get("lideranca"), dict) else {}
    pdi_bruto = b.get("pdi") if isinstance(b.get("pdi"), list) else []
    pdi = []
    for i in range(PDI_MAX):
        item = pdi_bruto[i] if i < len(pdi_bruto) and isinstance(pdi_bruto[i], dict) else {}
        pdi.append({"comp": txt(item.get("comp")), "acao": txt(item.get("acao")),
                    "prazo": txt(item.get("prazo"), 60)})
    return {
        "entregas": txt(b.get("entregas")),
        "valores": {c: txt(val.get(c)) for c, _s, _r, _f in VALORES_TRIO},
        "pdi": pdi,
        "carreira": txt(b.get("carreira")),
        "lideranca": {c: txt(lid.get(c)) for c in COD_LIDERANCA},
    }


def conteudo_tem_texto(c: dict) -> bool:
    c = c or {}
    if str(c.get("entregas") or "").strip() or str(c.get("carreira") or "").strip():
        return True
    if any(str(v or "").strip() for v in (c.get("valores") or {}).values()):
        return True
    if any(str(v or "").strip() for v in (c.get("lideranca") or {}).values()):
        return True
    return any(str(x or "").strip() for i in (c.get("pdi") or []) for x in i.values())


def conteudo_preenchido(c: dict) -> int:
    """Quantos dos CINCO elementos têm algum texto — o «N de 5» da tela."""
    c = c or {}
    n = 0
    n += 1 if str(c.get("entregas") or "").strip() else 0
    n += 1 if any(str(v or "").strip() for v in (c.get("valores") or {}).values()) else 0
    n += 1 if any(str(x or "").strip() for i in (c.get("pdi") or []) for x in i.values()) else 0
    n += 1 if str(c.get("carreira") or "").strip() else 0
    n += 1 if any(str(v or "").strip() for v in (c.get("lideranca") or {}).values()) else 0
    return n


def ref_de(linha: dict) -> str:
    """A identidade durável da pessoa para a Conversa de Valor: a matrícula (código SAP).

    Não o `id` da unidade: a unidade se recria a cada carga, e um histórico
    preso a ela se perderia na primeira reimportação. A matrícula sobrevive à
    pessoa mudar de área, de cargo e até de gestor — que é exatamente o que um
    histórico de Conversa de Valor precisa atravessar. Sem matrícula, cai no id da unidade
    prefixado, para a linha ainda ter chave.
    """
    return str(linha.get("codigo") or "").strip() or f"u:{linha['id']}"


# ---------------------------------------------------------------------------
# AGENDA — quem conversa com quem, derivado da árvore
# ---------------------------------------------------------------------------
def agenda(linhas: list[dict], overlay: list[dict] | None = None,
           ano: int = ANO_PADRAO) -> list[dict]:
    """Uma linha por pessoa, EM ORDEM HIERÁRQUICA, com o líder e o status dos 3
    ciclos do ano pedido.

    A ordem é a da árvore, não a do alfabeto: cada líder vem seguido da sua
    equipe. É a leitura que o processo pede — a Conversa de Valor acontece de cima para baixo,
    o líder conduz a conversa com quem reporta a ele, e ver o time logo abaixo de
    quem o lidera diz de relance quem falta conversar com quem. `profundidade`
    dá o degrau para a tela indentar o nome. Quem tem líder fora do recorte
    (porque o filtro o cortou) vira raiz local: a conversa existe, o interlocutor
    é que saiu da tela.
    """
    por_id = {l["id"]: l for l in linhas}
    reg = _indice_overlay(overlay)

    def entrada(l: dict) -> dict:
        ref = ref_de(l)
        lider = por_id.get(l["parent_id"])
        ciclos = {c: reg.get((ref, ano, c), {}).get("status", STATUS_PADRAO)
                  for c in COD_CICLOS}
        return {
            "id": l["id"], "ref": ref, "ano": ano, "nome": l["nome"],
            "cargo": l["cargo"], "papel": l["papel"],
            "papel_rotulo": dcr.ROTULO_PAPEL.get(l["papel"], l["papel"]),
            "setor": l["setor"], "bu": l["bu"], "vertical": l["vertical"],
            "lider_id": (lider or {}).get("id", ""),
            "lider_nome": (lider or {}).get("nome", ""),
            "lider_cargo": (lider or {}).get("cargo", ""),
            "ciclos": ciclos,
            "realizadas": sum(1 for s in ciclos.values() if s == "realizada"),
        }

    # Filhos por líder, cada grupo ordenado por nível de cargo e depois nome —
    # dentro de um mesmo time, quem tem papel mais alto aparece antes.
    filhos: dict[str, list[dict]] = {}
    for l in linhas:
        filhos.setdefault(l["parent_id"], []).append(l)
    ordem_grupo = lambda l: (dcr.ORDEM_PAPEL.get(l["papel"], 99), sem_acento(l["nome"]))

    # Raízes locais: quem não tem pai NESTE recorte. Ordenadas pelo mesmo
    # critério, para a lista sair estável a cada emissão (RNF-02).
    raizes = sorted((l for l in linhas if l["parent_id"] not in por_id),
                    key=ordem_grupo)

    saida, pilha = [], [(l, 0) for l in reversed(raizes)]
    vistos = set()
    while pilha:
        l, prof = pilha.pop()
        if l["id"] in vistos:                       # guarda contra ciclo de dados
            continue
        vistos.add(l["id"])
        e = entrada(l)
        e["profundidade"] = prof
        saida.append(e)
        for f in sorted(filhos.get(l["id"], []), key=ordem_grupo, reverse=True):
            pilha.append((f, prof + 1))
    return saida


def por_lider(ag: list[dict]) -> list[dict]:
    """A agenda enrolada por líder: quantas conversas cada um conduz, e quantas
    já realizou. É a leitura de quem cobra o processo — o líder é o dono da
    conversa com a sua equipe."""
    grupos: dict[str, dict] = {}
    for a in ag:
        if not a["lider_id"]:
            continue
        g = grupos.setdefault(a["lider_id"], {
            "id": a["lider_id"], "nome": a["lider_nome"],
            "cargo": a["lider_cargo"], "liderados": 0,
            "conversas": 0, "realizadas": 0})
        g["liderados"] += 1
        g["conversas"] += len(COD_CICLOS)
        g["realizadas"] += a["realizadas"]
    for g in grupos.values():
        g["pct"] = round(100 * g["realizadas"] / g["conversas"]) if g["conversas"] else 0
    return sorted(grupos.values(),
                  key=lambda g: (g["pct"], -g["liderados"], sem_acento(g["nome"])))


def resumo(ag: list[dict]) -> dict:
    """Os números do topo: pessoas, conversas previstas e feitas, por ciclo."""
    previstas = len(ag) * len(COD_CICLOS)
    realizadas = sum(a["realizadas"] for a in ag)
    por_ciclo = []
    for c, rot, quando, _m in CICLOS:
        feitas = sum(1 for a in ag if a["ciclos"][c] == "realizada")
        agendadas = sum(1 for a in ag if a["ciclos"][c] == "agendada")
        por_ciclo.append({
            "codigo": c, "rotulo": rot, "quando": quando,
            "realizadas": feitas, "agendadas": agendadas,
            "pendentes": len(ag) - feitas - agendadas,
            "pct": round(100 * feitas / len(ag)) if ag else 0,
        })
    return {
        "pessoas": len(ag),
        "lideres": len({a["lider_id"] for a in ag if a["lider_id"]}),
        "sem_lider": sum(1 for a in ag if not a["lider_id"]),
        "previstas": previstas,
        "realizadas": realizadas,
        "pct": round(100 * realizadas / previstas) if previstas else 0,
        "por_ciclo": por_ciclo,
    }


# ---------------------------------------------------------------------------
# A CAMADA EDITÁVEL — acompanhamento por pessoa, ANO e ciclo
# ---------------------------------------------------------------------------
# A chave é (ref, ano, ciclo): a matrícula, o ano do processo e qual das três
# conversas. O ano na chave é o que faz o histórico existir — 2026 e 2027 da
# mesma pessoa coexistem em vez de um sobrescrever o outro.
CAMPOS_SNAP = ("nome", "cargo", "lider")   # snapshot: como estava quando gravado


def _indice_overlay(overlay: list[dict] | None) -> dict:
    return {(r["ref"], int(r["ano"]), r["ciclo"]): r for r in (overlay or [])
            if r.get("ref") and r.get("ciclo") in COD_CICLOS and r.get("ano")}


def normalizar_overlay(bruto: list[dict] | None) -> list[dict]:
    """Saneia o acompanhamento. Entrada de formulário não é dado confiável.

    Uma linha por (ref, ano, ciclo). Status fora da lista vira o padrão; data e
    nota são cortadas no limite; o ano precisa ser plausível. Registro sem nada
    além do status padrão não ocupa lugar — gravá-lo faria a agenda parecer
    preenchida sem ninguém ter tocado nela.
    """
    saida: dict[tuple, dict] = {}
    for r in bruto or []:
        ref = str((r or {}).get("ref") or "").strip()[:60]
        ciclo = str(r.get("ciclo") or "").strip()
        try:
            ano = int(r.get("ano"))
        except (TypeError, ValueError):
            continue
        if not ref or ciclo not in COD_CICLOS or not (2000 <= ano <= 2100):
            continue
        status = r.get("status")
        status = status if status in STATUS_VALIDOS else STATUS_PADRAO
        conteudo = normalizar_conteudo(r.get("conteudo"))
        linha = {
            "ref": ref, "ano": ano, "ciclo": ciclo, "status": status,
            "data": str(r.get("data") or "").strip()[:10],
            "nota": str(r.get("nota") or "").strip()[:LIMITE_NOTA],
            "conteudo": conteudo,
        }
        for c in CAMPOS_SNAP:
            linha[c] = str(r.get(c) or "").strip()[:120]
        # Persiste se há QUALQUER sinal de que alguém tocou: status fora do
        # padrão, data, nota ou conteúdo preenchido. Sem isso, um formulário
        # aberto e fechado sem gravar poluiria a base com registros vazios.
        if (status != STATUS_PADRAO or linha["data"] or linha["nota"]
                or conteudo_tem_texto(conteudo)):
            saida[(ref, ano, ciclo)] = linha
    return sorted(saida.values(),
                  key=lambda r: (r["ref"], -r["ano"], COD_CICLOS.index(r["ciclo"])))


def registro_de(ref: str, ano: int, ciclo: str,
                overlay: list[dict] | None) -> dict:
    return _indice_overlay(overlay).get(
        (ref, ano, ciclo),
        {"ref": ref, "ano": ano, "ciclo": ciclo,
         "status": STATUS_PADRAO, "data": "", "nota": "",
         "conteudo": conteudo_vazio(), **{c: "" for c in CAMPOS_SNAP}})


def historico(ref: str, overlay: list[dict] | None,
              exceto_ano: int | None = None) -> list[dict]:
    """As conversas REALIZADAS de uma pessoa em anos/ciclos anteriores.

    É o "sempre consultar os CGVs anteriores": todo registro realizado da
    matrícula, do mais recente para o mais antigo, opcionalmente escondendo o
    ano corrente (que já está na ficha aberta). Só realizadas — pendente e
    agendada são intenção, não histórico.
    """
    anos: dict[int, list[dict]] = {}
    for r in _indice_overlay(overlay).values():
        if r["ref"] != ref or r["status"] != "realizada":
            continue
        if exceto_ano is not None and int(r["ano"]) == exceto_ano:
            continue
        anos.setdefault(int(r["ano"]), []).append(r)
    saida = []
    for ano in sorted(anos, reverse=True):
        conversas = sorted(anos[ano], key=lambda r: COD_CICLOS.index(r["ciclo"]))
        saida.append({
            "ano": ano,
            "conversas": [{
                "ciclo": r["ciclo"], "rotulo": ROTULO_CICLO.get(r["ciclo"], r["ciclo"]),
                "data": r["data"], "nota": r["nota"],
                "cargo": r.get("cargo", ""), "lider": r.get("lider", ""),
            } for r in conversas],
        })
    return saida


# ---------------------------------------------------------------------------
# FICHA — o acompanhamento de uma pessoa, os três ciclos do ano
# ---------------------------------------------------------------------------
def ficha(ref: str, linhas: list[dict], overlay: list[dict] | None = None,
          ano: int = ANO_PADRAO) -> dict | None:
    """A Conversa de Valor de uma pessoa no ANO: quem é, quem a lidera, os três ciclos, e o
    histórico dos anos anteriores. `None` quando a matrícula não existe no
    recorte — a rota transforma isso em aviso, não em 500."""
    por_ref = {ref_de(l): l for l in linhas}
    l = por_ref.get(ref)
    if l is None:
        return None
    por_id = {l["id"]: l for l in linhas}
    lider = por_id.get(l["parent_id"])
    ciclos = []
    for c, rot, quando, minutos in CICLOS:
        r = registro_de(ref, ano, c, overlay)
        conteudo = normalizar_conteudo(r.get("conteudo"))
        ciclos.append({
            "codigo": c, "rotulo": rot, "quando": quando, "minutos": minutos,
            "status": r["status"],
            "status_rotulo": ROTULO_STATUS.get(r["status"], r["status"]),
            "data": r["data"], "nota": r["nota"],
            "conteudo": conteudo,
            "preenchidas": conteudo_preenchido(conteudo),
        })
    return {
        "id": l["id"],
        "ref": ref,
        "ano": ano,
        "nome": l["nome"],
        "cargo": l["cargo"],
        "papel": dcr.ROTULO_PAPEL.get(l["papel"], l["papel"]),
        "papel_codigo": l["papel"],
        "setor": l["setor"],
        "bu": l["bu"],
        "vertical": l["vertical"],
        "lider_nome": (lider or {}).get("nome", ""),
        "lider_cargo": (lider or {}).get("cargo", ""),
        "ciclos": ciclos,
        "realizadas": sum(1 for c in ciclos if c["status"] == "realizada"),
        "historico": historico(ref, overlay, exceto_ano=ano),
    }


def markdown(f: dict) -> str:
    """A ficha de acompanhamento em Markdown, para o motor de `relatorio.py`.

    Markdown e não PDF direto pelo mesmo motivo do Skills: `relatorio.py` já pagina,
    quebra linha medindo largura real e imprime a procedência. Um segundo montador
    de PDF divergiria do primeiro na terceira correção de entrelinha.
    """
    L = [f"# {_t('Conversas que Geram Valor')}", ""]
    L.append(f"**{_t('Colaborador')}:** {f['nome']}")
    L.append("")
    L.append(f"**{_t('Cargo')}:** {f['cargo'] or VAZIO}")
    L.append("")
    L.append(f"**{_t('Líder direto')}:** {f['lider_nome'] or VAZIO}")
    L.append("")
    L.append(f"**{_t('Área')}:** {f['setor'] or VAZIO}")
    L.append("")
    for c in f["ciclos"]:
        L.append(f"## {_t(c['rotulo'])} · {_t(c['quando'])}")
        L.append("")
        L.append(f"**{_t('Status')}:** {_t(c['status_rotulo'])}"
                 + (f" · {c['data']}" if c["data"] else ""))
        L.append("")
        ct = c.get("conteudo") or {}
        # Entregas
        L.append(f"### {_t('Entregas e Resultados')}")
        L.append(str(ct.get("entregas") or "").strip() or VAZIO)
        L.append("")
        # Valores GPlanSiS — o descritor e a observação registrada
        L.append(f"### {_t('Aderência aos Valores Organizacionais')}")
        for cod, sig, rot, frase in VALORES_TRIO:
            obs = str((ct.get("valores") or {}).get(cod) or "").strip()
            L.append(f"- **{sig}** ({_t(rot)}): {obs or VAZIO}")
        L.append("")
        # PDI — competência / ação 70·20·10 / prazo
        L.append(f"### {_t('PDI — Plano de Desenvolvimento Individual')}")
        itens = [p for p in (ct.get("pdi") or [])
                 if any(str(v or "").strip() for v in p.values())]
        if not itens:
            L.append(VAZIO)
        for i, p in enumerate(itens, 1):
            L.append(f"{i}. **{_t('Competência')}:** {p.get('comp') or VAZIO}")
            L.append(f"   - **{_t('Ação (70/20/10)')}:** {p.get('acao') or VAZIO}")
            L.append(f"   - **{_t('Prazo')}:** {p.get('prazo') or VAZIO}")
        L.append("")
        # Carreira
        L.append(f"### {_t('Expectativa de Carreira')}")
        L.append(str(ct.get("carreira") or "").strip() or VAZIO)
        L.append("")
        # Feedback à liderança — as três competências (GEP-FOR-005)
        L.append(f"### {_t('Aderência às Competências de Liderança')}")
        lid = ct.get("lideranca") or {}
        for cod, rot, _itens in COMPETENCIAS_LIDERANCA:
            obs = str(lid.get(cod) or "").strip()
            L.append(f"- **{_t(rot)}:** {obs or VAZIO}")
        L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# REFERÊNCIA — o conteúdo do manual, para a tela e o passo a passo
# ---------------------------------------------------------------------------
def referencia() -> dict:
    """Tudo o que a aba de referência e o manual interativo desenham. Uma fonte
    só: a tela e o deck leem daqui, e não de dois textos que divergiriam."""
    return {
        "ciclos": CICLOS,
        "elementos": ELEMENTOS,
        "valores": VALORES_TRIO,
        "competencias": COMPETENCIAS_LIDERANCA,
        "regra": REGRA_70_20_10,
        "principios": PRINCIPIOS_FEEDBACK,
        "cnv": CNV,
        "dinamica": DINAMICA,
        "formularios": FORMULARIOS,
    }


def panorama(unidades, mapa_cc: dict | None = None,
             overlay: list[dict] | None = None,
             ano: int = ANO_PADRAO) -> dict:
    """Tudo o que a vista precisa, numa passada só sobre as unidades."""
    linhas = dcr.medir(unidades, mapa_cc)
    ag = agenda(linhas, overlay, ano)
    return {
        "linhas": linhas,
        "agenda": ag,
        "resumo": resumo(ag),
        "por_lider": por_lider(ag),
        "ciclos": CICLOS,
        "status": STATUS,
        "ano": ano,
        **referencia(),
    }


# ---------------------------------------------------------------------------
# PERSISTÊNCIA EM POSTGRES — o histórico durável
# ---------------------------------------------------------------------------
# A Conversa de Valor é o primeiro módulo que ESCREVE no Postgres, e não só o lê como alvo de
# carga. O motivo é o histórico: `estado.json` é o retrato de agora, some numa
# reimportação e não guarda anos de conversas. O banco guarda.
#
# Mas o banco é OPCIONAL neste sistema (a suíte e o dev rodam sem ele), então a
# camada `Config.cgv_registros` continua sendo a verdade viva — editável, no
# Desfazer, testável. O Postgres é o espelho durável: toda gravação vai para lá
# QUANDO ele existe, e o histórico prefere lê-lo; sem banco, tudo funciona pelo
# overlay, com o histórico limitado ao que o `estado.json` carrega.
#
# `slug` casa com `banco.sql_carga` — um organograma por slug.
def banco_pronto() -> bool:
    from . import banco
    return banco.situacao().get("pronto", False)


def _conectar():
    from . import banco
    pg = banco.driver()
    return pg.connect(banco.dsn(), connect_timeout=8) if pg and banco.dsn() else None


def salvar_no_banco(reg: dict, slug: str = "peoples") -> tuple[bool, str]:
    """UPSERT de um registro no Postgres. Idempotente por (slug, ref, ano, ciclo):
    editar a mesma conversa atualiza a linha, não empilha uma nova. Silencioso
    se o banco não estiver pronto — o overlay já guardou; o banco é o extra."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return False, "sem banco"
        import json as _json
        conteudo = _json.dumps(normalizar_conteudo(reg.get("conteudo")),
                               ensure_ascii=False)
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO org.cgv_registro (slug, ref, ano, ciclo, status, "
                "data_conversa, nota, conteudo, pessoa_nome, pessoa_cargo, "
                "lider_nome, registrado_por) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s) "
                "ON CONFLICT (slug, ref, ano, ciclo) DO UPDATE SET "
                "status=EXCLUDED.status, data_conversa=EXCLUDED.data_conversa, "
                "nota=EXCLUDED.nota, conteudo=EXCLUDED.conteudo, "
                "pessoa_nome=EXCLUDED.pessoa_nome, "
                "pessoa_cargo=EXCLUDED.pessoa_cargo, lider_nome=EXCLUDED.lider_nome, "
                "registrado_por=EXCLUDED.registrado_por, atualizado_em=now()",
                (slug, reg["ref"], reg["ano"], reg["ciclo"], reg["status"],
                 reg.get("data") or None, reg.get("nota") or "", conteudo,
                 reg.get("nome") or "", reg.get("cargo") or "",
                 reg.get("lider") or "", reg.get("por") or ""))
        con.commit()
        return True, "gravado no banco"
    except Exception as erro:                          # noqa: BLE001
        return False, str(erro).strip().splitlines()[0][:200]
    finally:
        if con is not None:
            con.close()


def carregar_do_banco(slug: str = "peoples") -> list[dict]:
    """Todos os registros do banco, no formato do overlay. É a leitura durável:
    traz anos que o `estado.json` corrente já não carrega. `[]` sem banco."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return []
        with con.cursor() as cur:
            cur.execute(
                "SELECT ref, ano, ciclo, status, "
                "to_char(data_conversa,'YYYY-MM-DD'), nota, conteudo, pessoa_nome, "
                "pessoa_cargo, lider_nome FROM org.cgv_registro WHERE slug=%s",
                (slug,))
            return [{"ref": r[0], "ano": r[1], "ciclo": r[2], "status": r[3],
                     "data": r[4] or "", "nota": r[5] or "",
                     "conteudo": r[6] if isinstance(r[6], dict) else {},
                     "nome": r[7] or "", "cargo": r[8] or "", "lider": r[9] or ""}
                    for r in cur.fetchall()]
    except Exception:                                  # noqa: BLE001
        return []
    finally:
        if con is not None:
            con.close()


def fundir(overlay: list[dict] | None,
           do_banco: list[dict] | None) -> list[dict]:
    """Overlay vivo + histórico do banco, sem duplicar. O overlay vence no
    conflito de mesma chave: é o que o operador acabou de editar nesta sessão,
    ainda não necessariamente espelhado. O banco preenche os anos que o overlay
    não tem."""
    idx = {(r["ref"], int(r["ano"]), r["ciclo"]): r
           for r in normalizar_overlay(do_banco)}
    idx.update({(r["ref"], int(r["ano"]), r["ciclo"]): r
                for r in normalizar_overlay(overlay)})
    return sorted(idx.values(),
                  key=lambda r: (r["ref"], -r["ano"], COD_CICLOS.index(r["ciclo"])))
