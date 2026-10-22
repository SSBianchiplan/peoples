"""
GPlanSiS|Peoples — Peoples Place to Work (Avaliação Mestre).

A pesquisa de clima da casa, conduzida 100% internamente, com o rigor de medição
que a GPlanSiS|Peoples já usa em chão de fábrica. O indicador-mestre é o **Peoples Trust
Index (PTI)**: o percentual de respostas positivas (4–5 na Likert) sobre as
válidas. Cinco pilares — Credibilidade, Respeito, Imparcialidade, Orgulho e
Camaradagem —, 60 afirmações (12 por pilar), 15 delas no pulso semestral.

Três decisões que este módulo carrega, e que o distinguem do Skills/Conversa de Valor/Mapa:

**A resposta é anônima — não tem dono.** Nenhuma linha guarda quem respondeu.
O vínculo com o sistema é pelos ESTRATOS (nível, área, vínculo, faixa de tempo
de casa) que o organograma já conhece, derivados da posição de quem responde no
momento do envio e gravados sem a identidade. Só o «modelo de trabalho»
(presencial/híbrido/remoto/campo) é perguntado — não é dado que a estrutura tem.

**Piso de 5 respondentes, inegociável.** Nenhum recorte com menos de cinco
respostas é publicado — o mesmo piso de amostra que o Skills aplica nas matrizes.
Com 271 pessoas e estratos finos (Diretoria tem 4), cruzar demais isolaria
indivíduos e quebraria o anonimato. Recorte pequeno sobe agregado.

**Idade e gênero ficam de fora (LGPD).** O organograma não guarda data de
nascimento nem gênero (LGPD-01/02); a pesquisa não os coleta. Recorte etário ou
de gênero, se preciso, é opt-in e fora daqui.
"""
from __future__ import annotations

from . import dominio
from .dominio import faixa_de_casa, sem_acento, tempo_de_casa

# Módulo puro: o idioma vigente entra como estado, ajustado por
# `main.alinhar_idioma()` antes de emitir. Mesma convenção de dcr/cgv/talentos.
IDIOMA = "pt-BR"


def _t(texto: str, **p) -> str:
    from . import idiomas
    return idiomas.traduzir(texto, IDIOMA, **p)


# ---------------------------------------------------------------------------
# OS PILARES — as cinco dimensões do Peoples Trust Index
# ---------------------------------------------------------------------------
# `codigo, rótulo, descrição`. A confiança é o pilar estruturante; os cinco
# medem-na sob a ótica do colaborador. A ordem é a do spec, e nunca a da nota.
PILARES = (
    ("credibilidade", "Credibilidade",
     "Os líderes comunicam com clareza, são competentes e íntegros."),
    ("respeito", "Respeito",
     "Os colaboradores se sentem apoiados profissional e pessoalmente."),
    ("imparcialidade", "Imparcialidade",
     "A empresa trata todos de forma justa e sem discriminação."),
    ("orgulho", "Orgulho",
     "O sentimento de orgulho pelo trabalho, equipe e empresa."),
    ("camaradagem", "Camaradagem",
     "A qualidade das relações interpessoais."),
)
ROTULO_PILAR = {c: r for c, r, _d in PILARES}
COD_PILAR = tuple(c for c, _r, _d in PILARES)

# ---------------------------------------------------------------------------
# A ESCALA LIKERT — cinco pontos
# ---------------------------------------------------------------------------
# `valor, rótulo`. Positivo é 4–5; é o que o PTI conta. 3 é neutro, não positivo.
LIKERT = (
    (1, "Discordo totalmente"),
    (2, "Discordo"),
    (3, "Neutro"),
    (4, "Concordo"),
    (5, "Concordo totalmente"),
)
ROTULO_LIKERT = {v: r for v, r in LIKERT}
PISO_POSITIVO = 4          # 4 e 5 contam como positivo no PTI

# ---------------------------------------------------------------------------
# AS 60 AFIRMAÇÕES — o Anexo A do spec, fonte única
# ---------------------------------------------------------------------------
# `id, pilar, texto, pulso`. `pulso=True` marca as 15 (★) do pulso semestral —
# três por pilar. Redação na primeira pessoa, sob a ótica do colaborador; a
# «liderança» é sempre o gestor direto do organograma.
AFIRMACOES = (
    # Pilar 1 — Credibilidade
    (1, "credibilidade", "Meu gestor direto comunica com clareza o que se espera do meu trabalho.", True),
    (2, "credibilidade", "A liderança mantém a equipe informada sobre decisões que nos afetam.", False),
    (3, "credibilidade", "Meu gestor é tecnicamente competente para conduzir o time.", True),
    (4, "credibilidade", "As promessas e combinados feitos pela liderança são cumpridos.", False),
    (5, "credibilidade", "Recebo respostas honestas quando faço perguntas difíceis.", False),
    (6, "credibilidade", "A comunicação flui bem entre squads e equipes de projeto, não só dentro da minha área.", False),
    (7, "credibilidade", "Confio nas informações que a empresa divulga internamente.", False),
    (8, "credibilidade", "A liderança age de forma coerente com o que fala.", False),
    (9, "credibilidade", "Sei a quem recorrer quando preciso de uma decisão.", True),
    (10, "credibilidade", "As mudanças de rota em projetos são explicadas, não apenas impostas.", False),
    (11, "credibilidade", "A liderança admite quando erra.", False),
    (12, "credibilidade", "Tenho clareza sobre a estratégia da minha área.", False),
    # Pilar 2 — Respeito
    (13, "respeito", "Tenho acesso a capacitação técnica relevante (trilhas, certificações técnicas).", True),
    (14, "respeito", "Minha opinião é considerada nas decisões que afetam meu trabalho.", False),
    (15, "respeito", "Consigo equilibrar vida pessoal e profissional, considerando viagens e deslocamentos a cliente.", True),
    (16, "respeito", "A empresa apoia meu desenvolvimento de carreira.", False),
    (17, "respeito", "Tenho os recursos e ferramentas necessários para fazer um bom trabalho.", False),
    (18, "respeito", "Sou tratado como pessoa, não apenas como recurso de projeto.", False),
    (19, "respeito", "O modelo de trabalho (presencial/híbrido/remoto/campo) que exerço é compatível com minhas entregas.", True),
    (20, "respeito", "A liderança se importa com meu bem-estar.", False),
    (21, "respeito", "Recebo reconhecimento pelo esforço, não só pelo resultado.", False),
    (22, "respeito", "Há flexibilidade quando surgem necessidades pessoais legítimas.", False),
    (23, "respeito", "Meu tempo é respeitado (reuniões, prazos, horas extras).", False),
    (24, "respeito", "A empresa investe em quem está começando (estagiários e menos de 1 ano de casa).", False),
    # Pilar 3 — Imparcialidade
    (25, "imparcialidade", "Promoções e oportunidades são baseadas em mérito, não em preferências pessoais.", True),
    (26, "imparcialidade", "A alocação de projetos é justa entre as pessoas do time.", False),
    (27, "imparcialidade", "Pessoas em vínculos diferentes (CLT, PJ, estágio) são tratadas com o mesmo respeito.", True),
    (28, "imparcialidade", "Não percebo favoritismo na distribuição de reconhecimento.", False),
    (29, "imparcialidade", "Sou tratado de forma justa independentemente de gênero, raça, orientação ou idade.", False),
    (30, "imparcialidade", "Os critérios de avaliação são claros e aplicados igualmente.", False),
    (31, "imparcialidade", "Áreas técnicas, comerciais e de suporte têm peso equivalente nas decisões.", False),
    (32, "imparcialidade", "Conflitos são resolvidos de forma imparcial.", False),
    (33, "imparcialidade", "Tenho as mesmas chances de crescer que meus pares.", True),
    (34, "imparcialidade", "A remuneração percebida é coerente com a responsabilidade (percepção, não valor).", False),
    (35, "imparcialidade", "Quem entrega mais é reconhecido por isso.", False),
    (36, "imparcialidade", "Não há «panelinhas» que definem quem sobe.", False),
    # Pilar 4 — Orgulho
    (37, "orgulho", "Tenho orgulho do trabalho que entrego.", True),
    (38, "orgulho", "Sinto que meu trabalho tem significado e impacto.", False),
    (39, "orgulho", "Tenho orgulho das entregas do meu time.", True),
    (40, "orgulho", "Recomendaria a GPlanSiS|Peoples como um bom lugar para trabalhar.", False),
    (41, "orgulho", "Tenho orgulho da reputação da GPlanSiS|Peoples no mercado.", False),
    (42, "orgulho", "Sinto que contribuo para algo maior que minhas tarefas.", False),
    (43, "orgulho", "As soluções que construímos me deixam orgulhoso.", False),
    (44, "orgulho", "Sinto que pertenço a esta empresa.", False),
    (45, "orgulho", "Vejo futuro para mim aqui.", False),
    (46, "orgulho", "O que fazemos aqui melhora a indústria dos nossos clientes.", False),
    (47, "orgulho", "Falo bem da empresa para pessoas de fora.", False),
    (48, "orgulho", "Vale a pena o esforço que dedico aqui.", True),
    # Pilar 5 — Camaradagem
    (49, "camaradagem", "Fui bem acolhido quando entrei na empresa.", True),
    (50, "camaradagem", "Posso ser eu mesmo no ambiente de trabalho.", False),
    (51, "camaradagem", "Conto com meus colegas quando preciso de ajuda.", True),
    (52, "camaradagem", "Há um senso de comunidade entre as unidades e times.", False),
    (53, "camaradagem", "As relações no trabalho são autênticas.", False),
    (54, "camaradagem", "Novos colegas e estagiários são bem integrados.", False),
    (55, "camaradagem", "Celebramos as conquistas juntos.", False),
    (56, "camaradagem", "Existe informalidade saudável no dia a dia.", False),
    (57, "camaradagem", "Sinto que faço parte de um time, não apenas de um projeto.", True),
    (58, "camaradagem", "As pessoas aqui se importam umas com as outras.", False),
    (59, "camaradagem", "Há espaço para momentos de descontração.", False),
    (60, "camaradagem", "Me sinto à vontade para discordar de um colega com respeito.", False),
)
IDS_AFIRMACAO = frozenset(a[0] for a in AFIRMACOES)
IDS_PULSO = tuple(a[0] for a in AFIRMACOES if a[3])          # as 15 do pulso
PILAR_DE = {a[0]: a[1] for a in AFIRMACOES}
# A afirmação 40 é o proxy de recomendação para o eNPS (não há questão 0–10 no
# instrumento; o eNPS aqui é derivado dela, e rotulado como proxy).
ID_RECOMENDACAO = 40

# ---------------------------------------------------------------------------
# AS PERGUNTAS ABERTAS — 10, qualitativas
# ---------------------------------------------------------------------------
ABERTAS = (
    (1, "O que mais te dá orgulho aqui?"),
    (2, "O que mais te incomoda?"),
    (3, "O que a liderança poderia fazer diferente?"),
    (4, "Descreva um momento em que se sentiu valorizado."),
    (5, "O que faria você recomendar (ou não) a empresa?"),
    (6, "Que apoio falta ao seu desenvolvimento?"),
    (7, "O que melhoraria seu equilíbrio vida-trabalho?"),
    (8, "Como é a integração entre áreas/projetos na sua visão?"),
    (9, "Uma sugestão concreta de melhoria."),
    (10, "Algo que não perguntamos e você gostaria de dizer."),
)
IDS_ABERTA = frozenset(a[0] for a in ABERTAS)

# ---------------------------------------------------------------------------
# MODELO DE TRABALHO — a única demografia perguntada (não vem da estrutura)
# ---------------------------------------------------------------------------
MODELOS_TRABALHO = (
    ("presencial", "Presencial"),
    ("hibrido", "Híbrido"),
    ("remoto", "Remoto"),
    ("campo", "Campo"),
)
ROTULO_MODELO = {c: r for c, r in MODELOS_TRABALHO}
COD_MODELO = tuple(c for c, _r in MODELOS_TRABALHO)

# ---------------------------------------------------------------------------
# OS CICLOS — anual (completa) e pulso (semestral, 15 afirmações)
# ---------------------------------------------------------------------------
CICLOS = (
    ("anual", "Pesquisa anual", "60 afirmações · mar/abr"),
    ("pulso", "Pulso semestral", "15 afirmações-chave · jul/nov"),
)
ROTULO_CICLO = {c: r for c, r, _q in CICLOS}
COD_CICLOS = tuple(c for c, _r, _q in CICLOS)
CICLO_PADRAO = "anual"

# ---------------------------------------------------------------------------
# OS NÍVEIS DE MATURIDADE — §5 do spec
# ---------------------------------------------------------------------------
# `piso do PTI, código, rótulo, descrição`. Do topo para baixo — o primeiro cujo
# piso o PTI alcança é o nível.
MATURIDADE = (
    (90, "excelencia", "Excelência",
     "Cultura de referência, candidata a benchmarks externos."),
    (75, "alto", "Alto Desempenho",
     "Ambiente forte, com pontos de melhoria pontuais."),
    (60, "desenvolvimento", "Em Desenvolvimento",
     "Base sólida, exige planos de ação estruturados."),
    (45, "alerta", "Alerta",
     "Problemas recorrentes que afetam retenção e engajamento."),
    (0, "critico", "Crítico",
     "Necessidade de intervenção cultural imediata."),
)

# As dimensões de segmentação — os estratos que o organograma dá, mais o modelo.
DIMENSOES = (
    ("nivel", "Nível hierárquico"),
    ("area", "Área"),
    ("vinculo", "Vínculo"),
    ("faixa", "Tempo de casa"),
    ("modelo", "Modelo de trabalho"),
)

PISO_ESTRATO = 5           # nenhum recorte com menos de 5 respostas é publicado
META_PARTICIPACAO = 70     # % — Fase 1 do spec
META_GTI_PILAR = 60        # nenhum pilar abaixo disto (KPI §7)
LIMITE_ABERTA = 4000


# ---------------------------------------------------------------------------
# ESTRATOS — derivados da posição de quem responde, sem a identidade
# ---------------------------------------------------------------------------
def estrato_de(unidade, hoje=None) -> dict:
    """Os quatro estratos de uma pessoa, do organograma. É o que se guarda com a
    resposta — nunca quem ela é. `modelo` NÃO sai daqui: é perguntado."""
    if unidade is None:
        return {"nivel": "", "area": "", "vinculo": "", "faixa": ""}
    anos = tempo_de_casa(getattr(unidade, "data_inicio", None), hoje)
    return {
        "nivel": getattr(unidade, "tipo", "") or "",
        "area": getattr(unidade, "area", "") or "",
        "vinculo": getattr(unidade, "vinculo", "") or "",
        "faixa": faixa_de_casa(anos) if anos is not None and anos >= 0 else "",
    }


def elegiveis(unidades) -> int:
    """Quantas pessoas o recorte tem — a base da taxa de participação."""
    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    return sum(1 for u in us if getattr(u, "parent_id", None) is not None)


# ---------------------------------------------------------------------------
# A RESPOSTA — anônima, um envio
# ---------------------------------------------------------------------------
def _clamp_valor(v):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 5 else None


def normalizar_resposta(bruto) -> dict | None:
    """Saneia um envio. Valor fora de 1–5 cai; id de afirmação inválido some;
    ciclo e ano precisam ser plausíveis. Sem nenhuma resposta, é `None` — envio
    vazio não ocupa lugar. NUNCA carrega identidade: se vier `ref`/`usuario_id`,
    é descartado aqui, não gravado."""
    b = bruto if isinstance(bruto, dict) else {}
    try:
        ano = int(b.get("ano"))
    except (TypeError, ValueError):
        return None
    if not (2000 <= ano <= 2100):
        return None
    ciclo = b.get("ciclo") if b.get("ciclo") in ROTULO_CICLO else CICLO_PADRAO
    respostas = {}
    for aid, val in (b.get("respostas") or {}).items():
        try:
            aid = int(aid)
        except (TypeError, ValueError):
            continue
        v = _clamp_valor(val)
        if aid in IDS_AFIRMACAO and v is not None:
            respostas[aid] = v
    if not respostas:
        return None
    abertas = {}
    for qid, txt in (b.get("abertas") or {}).items():
        try:
            qid = int(qid)
        except (TypeError, ValueError):
            continue
        t = str(txt or "").strip()[:LIMITE_ABERTA]
        if qid in IDS_ABERTA and t:
            abertas[qid] = t
    return {
        "id": str(b.get("id") or "").strip()[:40],
        "ciclo": ciclo, "ano": ano, "respostas": respostas, "abertas": abertas,
        "nivel": str(b.get("nivel") or "")[:60],
        "area": str(b.get("area") or "")[:120],
        "vinculo": str(b.get("vinculo") or "")[:40],
        "faixa": str(b.get("faixa") or "")[:20],
        "modelo": b.get("modelo") if b.get("modelo") in ROTULO_MODELO else "",
    }


def normalizar_overlay(bruto) -> list[dict]:
    """A lista de respostas, saneada e sem duplicar por id. Resposta sem id
    ganha uma chave posicional estável só para dedupe interno."""
    saida: dict[str, dict] = {}
    for i, r in enumerate(bruto or []):
        limpo = normalizar_resposta(r)
        if limpo is None:
            continue
        chave = limpo["id"] or f"pos:{i}"
        saida[chave] = limpo
    return list(saida.values())


# ---------------------------------------------------------------------------
# PROGRAMAÇÃO DA PESQUISA — agendar a janela e convidar (o ENVIO fica p/ depois)
# ---------------------------------------------------------------------------
# A janela do ciclo e o convite por e-mail. A programação é REAL — salva e
# consultável. O disparo do e-mail, NÃO: depende de uma configuração de correio
# (SMTP/M365) que fica para depois, por decisão. `notificar` reúne quem seria
# convidado e monta a mensagem, mas retorna «pendente» em vez de enviar — ligar
# o envio é uma linha, quando a credencial existir.
def _data_iso(v) -> str:
    v = str(v or "").strip()[:10]
    return v if len(v) == 10 and v[4] == "-" and v[7] == "-" else ""


def normalizar_programacao(bruto) -> dict:
    """Saneia a programação: ciclo válido, datas ISO, status conhecido."""
    b = bruto if isinstance(bruto, dict) else {}
    return {
        "ciclo": b.get("ciclo") if b.get("ciclo") in ROTULO_CICLO else CICLO_PADRAO,
        "abertura": _data_iso(b.get("abertura")),
        "fechamento": _data_iso(b.get("fechamento")),
        "notificar": bool(b.get("notificar")),
        "status": b.get("status") if b.get("status") in ("rascunho", "programada") else "rascunho",
        "agendado_em": str(b.get("agendado_em") or "")[:32],
        "agendado_por": str(b.get("agendado_por") or "")[:120],
    }


def destinatarios(unidades) -> list[str]:
    """Os e-mails dos colaboradores — a quem o convite iria. Deriva do
    organograma, sem coleta nova. NÃO envia: só reúne o público."""
    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    saida = []
    for u in us:
        if getattr(u, "parent_id", None) is None:
            continue
        email = str(getattr(u, "email", "") or "").strip()
        if email and "@" in email and email not in saida:
            saida.append(email)
    return saida


def convite(prog: dict, tenant: str = "GPlanSiS|Peoples") -> dict:
    """O convite que os colaboradores receberiam — assunto e corpo, prontos."""
    rot = ROTULO_CICLO.get(prog.get("ciclo"), prog.get("ciclo") or "")
    janela = ""
    if prog.get("abertura") and prog.get("fechamento"):
        janela = " " + _t("A pesquisa fica aberta de {de} a {ate}.",
                          de=prog["abertura"], ate=prog["fechamento"])
    return {
        "assunto": _t("{tenant} · Pesquisa de Clima (Peoples Place to Work)", tenant=tenant),
        "corpo": _t("Sua opinião importa, e é anônima. Responda à pesquisa de clima "
                    "({ciclo}) — leva poucos minutos.{janela} O sistema não guarda "
                    "quem respondeu.", ciclo=_t(rot), janela=janela),
    }


def notificar(unidades, prog: dict, tenant: str = "GPlanSiS|Peoples") -> dict:
    """Prepara a notificação por e-mail — e NÃO envia ainda (por decisão).

    Reúne o público (e-mails do organograma) e monta a mensagem, mas o disparo
    depende de configuração de correio que fica para depois. Retorna o que está
    pronto e o que falta, para a tela ser honesta: «programado, não enviado».
    Ligar o envio é trocar o corpo deste método pela chamada ao correio/M365."""
    alvos = destinatarios(unidades)
    msg = convite(prog, tenant)
    return {
        "destinatarios": len(alvos),
        "assunto": msg["assunto"],
        "corpo": msg["corpo"],
        "enviados": 0,
        "pendente": True,
        "motivo": _t("envio de e-mail a configurar (SMTP/M365)"),
    }


# ---------------------------------------------------------------------------
# GRAU TRUST INDEX — o cálculo
# ---------------------------------------------------------------------------
def _gti_de_valores(valores: list[int]) -> dict:
    validos = [v for v in valores if 1 <= v <= 5]
    positivos = sum(1 for v in validos if v >= PISO_POSITIVO)
    return {"validas": len(validos), "positivas": positivos,
            "gti": round(100 * positivos / len(validos)) if validos else None}


def gti(respostas: list[dict], apenas: set | None = None) -> dict:
    """O PTI geral: % de respostas 4–5 sobre as válidas. `apenas` restringe a um
    conjunto de ids de afirmação (o pulso, ou um pilar)."""
    valores = []
    for r in respostas:
        for aid, v in r.get("respostas", {}).items():
            if apenas is None or aid in apenas:
                valores.append(v)
    return _gti_de_valores(valores)


def gti_por_pilar(respostas: list[dict]) -> list[dict]:
    """O PTI de cada pilar, na ordem do spec. O mais frágil é onde a devolutiva
    começa — mas a ordem não muda com a nota (RNF-02)."""
    ids_por_pilar = {c: {a[0] for a in AFIRMACOES if a[1] == c} for c in COD_PILAR}
    saida = []
    for cod, rot, desc in PILARES:
        g = gti(respostas, ids_por_pilar[cod])
        saida.append({"codigo": cod, "rotulo": rot, "descricao": desc,
                      "gti": g["gti"], "validas": g["validas"],
                      "maturidade": maturidade(g["gti"])})
    return saida


def por_afirmacao(respostas: list[dict], apenas_pulso: bool = False) -> list[dict]:
    """O PTI afirmação a afirmação — para achar as forças e as fragilidades."""
    saida = []
    for aid, pilar, texto, pulso in AFIRMACOES:
        if apenas_pulso and not pulso:
            continue
        valores = [r["respostas"][aid] for r in respostas if aid in r.get("respostas", {})]
        g = _gti_de_valores(valores)
        saida.append({"id": aid, "pilar": pilar, "pilar_rotulo": ROTULO_PILAR[pilar],
                      "texto": texto, "pulso": pulso, "gti": g["gti"],
                      "validas": g["validas"]})
    return saida


def maturidade(gti_valor) -> dict:
    """O nível de maturidade de um PTI. `None` quando não há amostra."""
    if gti_valor is None:
        return {"codigo": "", "rotulo": "", "descricao": ""}
    for piso, cod, rot, desc in MATURIDADE:
        if gti_valor >= piso:
            return {"codigo": cod, "rotulo": rot, "descricao": desc}
    return {"codigo": "critico", "rotulo": "Crítico", "descricao": ""}


def por_estrato(respostas: list[dict], dim: str) -> list[dict]:
    """O PTI por estrato de uma dimensão, com o PISO de 5 respondentes.

    Recorte com menos de cinco respostas NÃO é publicado — sobe agregado, para
    não isolar quem respondeu. É a guarda de anonimato, no ponto de exibição."""
    grupos: dict[str, list[dict]] = {}
    for r in respostas:
        grupos.setdefault(str(r.get(dim) or ""), []).append(r)
    publicos, ocultos, resp_ocultos = [], 0, 0
    for chave, gente in grupos.items():
        if len(gente) < PISO_ESTRATO:
            ocultos += 1
            resp_ocultos += len(gente)
            continue
        g = gti(gente)
        publicos.append({"chave": chave, "rotulo": _rotulo_estrato(dim, chave),
                         "n": len(gente), "gti": g["gti"],
                         "maturidade": maturidade(g["gti"])})
    publicos.sort(key=lambda x: (-(x["gti"] or 0), sem_acento(x["rotulo"])))
    return {"grupos": publicos, "ocultos": ocultos,
            "respostas_ocultas": resp_ocultos}


def _rotulo_estrato(dim: str, chave: str) -> str:
    if not chave:
        return _t("Não informado")
    if dim == "nivel":
        return dominio.TIPOS.get(chave, chave)
    if dim == "vinculo":
        par = dominio.VINCULOS.get(chave)
        return par[0] if par else chave
    if dim == "faixa":
        for c, rot, _p in dominio.FAIXAS_CASA:
            if c == chave:
                return rot
        return chave
    if dim == "modelo":
        return ROTULO_MODELO.get(chave, chave)
    return chave


def participacao(respostas: list[dict], base: int) -> dict:
    """Taxa de participação sobre a base elegível. Meta ≥ 70% (≥ 190 de 271)."""
    n = len(respostas)
    pct = round(100 * n / base) if base else 0
    return {"respostas": n, "elegiveis": base, "pct": pct,
            "meta": META_PARTICIPACAO, "atingiu": pct >= META_PARTICIPACAO,
            "faltam": max(0, -(-base * META_PARTICIPACAO // 100) - n)}


def enps(respostas: list[dict]) -> dict:
    """eNPS proxy, da afirmação 40 (Recomendaria a GPlanSiS|Peoples). Não há questão
    0–10 no instrumento; este eNPS é derivado da recomendação e rotulado como
    proxy: 5 = promotor, 4 = neutro, ≤3 = detrator. eNPS = %promotores −
    %detratores, de −100 a +100."""
    valores = [r["respostas"][ID_RECOMENDACAO] for r in respostas
               if ID_RECOMENDACAO in r.get("respostas", {})]
    if not valores:
        return {"enps": None, "promotores": 0, "neutros": 0, "detratores": 0,
                "n": 0, "meta": 30}
    prom = sum(1 for v in valores if v >= 5)
    det = sum(1 for v in valores if v <= 3)
    neu = len(valores) - prom - det
    val = round(100 * prom / len(valores) - 100 * det / len(valores))
    return {"enps": val, "promotores": prom, "neutros": neu, "detratores": det,
            "n": len(valores), "meta": 30}


def afirmacoes_do_ciclo(ciclo: str) -> tuple:
    """As afirmações de um ciclo: todas no anual, só as ★ no pulso."""
    if ciclo == "pulso":
        return tuple(a for a in AFIRMACOES if a[3])
    return AFIRMACOES


def destaques(respostas: list[dict], quantos: int = 3) -> dict:
    """Top forças e oportunidades: as afirmações de maior e menor PTI, com
    amostra suficiente. É o «top 3» que a devolutiva pede."""
    linhas = [a for a in por_afirmacao(respostas)
              if a["gti"] is not None and a["validas"] >= PISO_ESTRATO]
    fortes = sorted(linhas, key=lambda x: (-x["gti"], x["id"]))[:quantos]
    fracas = sorted(linhas, key=lambda x: (x["gti"], x["id"]))[:quantos]
    return {"forcas": fortes, "oportunidades": fracas}


def comentarios(respostas: list[dict], qid: int, limite: int = 40) -> list[str]:
    """Os comentários de uma pergunta aberta, agregados e sem dono. Só quando há
    o piso de respostas — comentário isolado pode identificar quem escreveu."""
    if len(respostas) < PISO_ESTRATO:
        return []
    return [r["abertas"][qid] for r in respostas
            if qid in r.get("abertas", {})][:limite]


def panorama(unidades, respostas: list[dict] | None = None,
             ano: int = 2026, ciclo: str = CICLO_PADRAO) -> dict:
    """Tudo o que a vista precisa, numa passada só. `respostas` já vem fundido
    (overlay + banco) e filtrado pelo recorte, se houver."""
    resp = [r for r in (respostas or []) if r.get("ano") == ano and r.get("ciclo") == ciclo]
    base = elegiveis(unidades)
    g = gti(resp)
    return {
        "respostas": resp, "ano": ano, "ciclo": ciclo,
        "gti": g["gti"], "gti_validas": g["validas"],
        "maturidade": maturidade(g["gti"]),
        "por_pilar": gti_por_pilar(resp),
        "participacao": participacao(resp, base),
        "enps": enps(resp),
        "destaques": destaques(resp),
        "dimensoes": DIMENSOES,
        "pilares": PILARES, "likert": LIKERT, "modelos": MODELOS_TRABALHO,
        "ciclos": CICLOS, "abertas": ABERTAS,
        "por_dimensao": {d: por_estrato(resp, d) for d, _r in DIMENSOES},
        "meta_gti_pilar": META_GTI_PILAR, "piso": PISO_ESTRATO,
    }


# ---------------------------------------------------------------------------
# PERSISTÊNCIA EM POSTGRES — as respostas duráveis, sempre anônimas
# ---------------------------------------------------------------------------
def banco_pronto() -> bool:
    from . import banco
    return banco.situacao().get("pronto", False)


def _conectar():
    from . import banco
    pg = banco.driver()
    return pg.connect(banco.dsn(), connect_timeout=8) if pg and banco.dsn() else None


def salvar_no_banco(reg: dict, slug: str = "peoples") -> tuple[bool, str]:
    """INSERT de uma resposta anônima. Sem coluna de identidade, por contrato: o
    que entra é estrato + respostas, nunca quem respondeu."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return False, "sem banco"
        import json as _json
        limpo = normalizar_resposta(reg)
        if limpo is None:
            return False, "resposta vazia"
        # A chave é o id da resposta em memória: com ela o INSERT vira UPSERT
        # (idempotente — espelhar duas vezes não duplica) e a leitura devolve a
        # mesma identidade que `fundir` usa para não contar em dobro (migr. 011).
        chave = limpo["id"] or None
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO org.gptw_resposta (slug, ciclo, ano, respostas, "
                "abertas, estrato_nivel, estrato_area, estrato_vinculo, "
                "estrato_faixa, modelo_trabalho, chave) "
                "VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s) "
                + ("ON CONFLICT (slug, chave) WHERE chave IS NOT NULL DO UPDATE SET "
                   "ciclo=EXCLUDED.ciclo, ano=EXCLUDED.ano, respostas=EXCLUDED.respostas, "
                   "abertas=EXCLUDED.abertas, estrato_nivel=EXCLUDED.estrato_nivel, "
                   "estrato_area=EXCLUDED.estrato_area, estrato_vinculo=EXCLUDED.estrato_vinculo, "
                   "estrato_faixa=EXCLUDED.estrato_faixa, modelo_trabalho=EXCLUDED.modelo_trabalho "
                   if chave else "")
                + " RETURNING id",
                (slug, limpo["ciclo"], limpo["ano"],
                 _json.dumps({str(k): v for k, v in limpo["respostas"].items()}),
                 _json.dumps({str(k): v for k, v in limpo["abertas"].items()},
                             ensure_ascii=False),
                 limpo["nivel"] or None, limpo["area"] or None,
                 limpo["vinculo"] or None, limpo["faixa"] or None,
                 limpo["modelo"] or None, chave))
            novo_id = cur.fetchone()[0]
        con.commit()
        return True, str(novo_id)
    except Exception as erro:                          # noqa: BLE001
        return False, str(erro).strip().splitlines()[0][:200]
    finally:
        if con is not None:
            con.close()


def carregar_do_banco(slug: str = "peoples") -> list[dict]:
    """Todas as respostas do banco, no formato do overlay. `[]` sem banco."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return []
        with con.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(chave, id::text), ciclo, ano, respostas, abertas, "
                "estrato_nivel, estrato_area, estrato_vinculo, estrato_faixa, "
                "modelo_trabalho FROM org.gptw_resposta WHERE slug=%s", (slug,))
            saida = []
            for r in cur.fetchall():
                saida.append({
                    "id": str(r[0]), "ciclo": r[1], "ano": r[2],
                    "respostas": r[3] if isinstance(r[3], dict) else {},
                    "abertas": r[4] if isinstance(r[4], dict) else {},
                    "nivel": r[5] or "", "area": r[6] or "",
                    "vinculo": r[7] or "", "faixa": r[8] or "",
                    "modelo": r[9] or ""})
            return saida
    except Exception:                                  # noqa: BLE001
        return []
    finally:
        if con is not None:
            con.close()


def fundir(overlay: list[dict] | None, do_banco: list[dict] | None) -> list[dict]:
    """Overlay vivo + banco, sem duplicar por id. Diferente da Conversa de Valor/Mapa, aqui
    não há «vencedor»: cada resposta é um envio único, então a união é simples —
    o que está no banco já foi espelhado do overlay e não se reedita."""
    idx: dict[str, dict] = {}
    for r in normalizar_overlay(do_banco):
        idx[r["id"] or f"b:{len(idx)}"] = r
    for r in normalizar_overlay(overlay):
        # Só entra se o id ainda não veio do banco — evita contar em dobro a
        # resposta que já foi espelhada.
        chave = r["id"] or f"o:{len(idx)}"
        if chave not in idx:
            idx[chave] = r
    return list(idx.values())
