"""GPlanSiS|Peoples — a mesma estrutura vista por equipe, não por pessoa.

O canvas é *person-centric*: cada nó é uma posição ocupada por alguém, e com
267 cards a leitura de "como a empresa é organizada" se perde no meio de "quem
é quem". Este módulo responde à outra pergunta — quais times existem, quem
responde a quem entre eles — recolhendo as pessoas dentro do seu time.

**Não é uma segunda verdade.** Nada aqui é gravado: as equipes são derivadas do
mesmo dicionário de unidades a cada render, e o resultado é um dicionário de
`Unidade` como qualquer outro. Por isso o modo por equipe atravessa o motor de
layout, o SVG, o PDF e o CSV sem que nenhum deles saiba que ele existe — quem
produz coordenada continua sendo `dominio.calcular_layout`, e só ele (ADR-011).

Quatro decisões que estão no código, e não neste texto:

**A chave é N3 + Departamento, nunca o nome sozinho.** `Managers Team` existe em
80.20, 81.20, 82.20 e 89.20; `Hardware Design Team`, em quatro verticais. Agrupar
por nome fundiria quatro times distintos num nó só e diria uma inverdade sobre a
empresa. É a mesma chave do cadastro de centros de custo, de propósito: duas
regras de identidade para a mesma coisa divergiriam no primeiro ajuste.

**O pai de uma equipe é a equipe de quem chefia a âncora.** A âncora é o membro
cujo gestor está fora do time — quem liga aquele time ao resto. Havendo mais de
um, vence o mais raso; empatou, decide (ordem, nome, id), porque duas execuções
têm de desenhar igual (RNF-02).

**Ciclo é quebrado, não propagado.** Dois times podem chefiar um ao outro por
caminhos diferentes — acontece quando alguém responde a um par de outra área. O
laço é cortado prendendo o time na raiz, porque um organograma com ciclo não
desenha, e cair de pé mostrando a estrutura vale mais do que não desenhar.

**Pessoa sem time não é escondida.** Quem não tem departamento vira uma equipe
de um: sumir com ela deixaria a soma dos cards menor que o quadro de pessoal, e
ninguém confia num organograma que não fecha a conta.
"""
from __future__ import annotations

from . import centros
from . import idiomas
from .dominio import Unidade, mapa_filhos, profundidades, raiz, sem_acento

IDIOMA = idiomas.PADRAO


def _t(texto: str, **p) -> str:
    return idiomas.traduzir(texto, IDIOMA, **p)


PREFIXO = "EQ"


def chave_equipe(u: Unidade) -> str:
    """(N3, Departamento) — a mesma identidade do cadastro de centros de custo."""
    return centros.chave(centros.n3_de(u.centro_custo), u.area)


def _identificador(chave: str) -> str:
    """`80.30|hardware design team` → `EQ-80.30-hardware-design-team`.

    Legível de propósito: este id aparece no DOM, no rótulo ARIA e no CSV
    exportado, e um hash ali obrigaria a abrir o depurador para saber de que
    time se está falando.
    """
    n3, _, nome = chave.partition("|")
    limpo = "".join(c if c.isalnum() else "-" for c in nome).strip("-")
    while "--" in limpo:
        limpo = limpo.replace("--", "-")
    return f"{PREFIXO}-{n3 or 'sem-cc'}-{limpo or 'sem-area'}"[:64]


def _rotulo(u: Unidade) -> str:
    return u.area.strip() or _t("Sem departamento")


def agrupar(unidades: dict[str, Unidade],
            extras: dict[str, dict] | None = None) -> dict:
    """Pessoas → equipes. Devolve o desenho e o que ele recolheu.

    `{"unidades": …, "membros": {id_equipe: [pessoas]}, "extras": …}` — os
    extras saem prontos para o layout, com o registro de CC da âncora, senão a
    linha de código do card perderia a vertical de negócio.
    """
    ex = extras or {}
    if not unidades:
        return {"unidades": {}, "membros": {}, "extras": {}, "equipe_de": {}}

    prof = profundidades(unidades)
    filhos = mapa_filhos(unidades)
    ordem_irmao = {u.id: i for fs in filhos.values() for i, u in enumerate(fs)}

    # ---- quem está em qual time -------------------------------------------
    equipe_de: dict[str, str] = {}
    membros: dict[str, list[Unidade]] = {}
    for u in unidades.values():
        cid = _identificador(chave_equipe(u))
        equipe_de[u.id] = cid
        membros.setdefault(cid, []).append(u)

    # Dentro do time, a ordem é a mesma da árvore: raso primeiro, e o desempate
    # é o mesmo de `mapa_filhos`, para o painel listar igual a cada render.
    for lista in membros.values():
        lista.sort(key=lambda p: (prof.get(p.id, 0), ordem_irmao.get(p.id, 0),
                                  sem_acento(p.nome), p.id))

    # ---- a âncora: quem liga o time ao resto da empresa ---------------------
    ancora: dict[str, Unidade] = {}
    for cid, lista in membros.items():
        fora = [p for p in lista
                if p.parent_id is None or equipe_de.get(p.parent_id) != cid]
        ancora[cid] = (fora or lista)[0]

    id_raiz_pessoa = raiz(unidades).id
    cid_raiz = equipe_de[id_raiz_pessoa]

    # ---- pai de cada equipe, com o laço cortado ----------------------------
    #
    # Só a raiz fica sem pai. Qualquer outro time que não resolva um pai — a
    # âncora aponta para dentro do próprio time, ou não aponta para lugar
    # nenhum — é preso em `cid_raiz`, que é o que o cabeçalho deste módulo
    # promete ("o laço é cortado prendendo o time na raiz").
    #
    # Fazia `pai = None`, e aí nascia uma SEGUNDA raiz: `enraizado()` devolve
    # True de imediato para quem já tem pai None, então o reparo abaixo pulava o
    # caso, e `dominio.raiz()` — que pega `mapa_filhos[None][0]` — ficava com uma
    # e descartava a subárvore da outra em silêncio. Some time do desenho, e a
    # soma dos cards deixa de fechar com o efetivo, que é a única coisa que este
    # módulo promete não fazer.
    pai: dict[str, str | None] = {}
    for cid, a in ancora.items():
        if cid == cid_raiz:
            pai[cid] = None
            continue
        acima = equipe_de.get(a.parent_id) if a.parent_id else None
        pai[cid] = acima if acima is not None and acima != cid else cid_raiz

    def enraizado(cid: str) -> bool:
        visto = {cid}
        atual = pai.get(cid)
        while atual is not None:
            if atual in visto:
                return False
            visto.add(atual)
            atual = pai.get(atual)
        return True

    for cid in sorted(pai):
        if cid != cid_raiz and not enraizado(cid):
            pai[cid] = cid_raiz            # RF-03: a raiz continua única

    # ---- os nós ------------------------------------------------------------
    novas: dict[str, Unidade] = {}
    extras_equipe: dict[str, dict] = {}
    for i, cid in enumerate(sorted(membros)):
        lista = membros[cid]
        a = ancora[cid]
        novas[cid] = Unidade(
            id=cid,
            codigo=centros.n3_de(a.centro_custo) or a.codigo,
            nome=_rotulo(a),
            tipo=a.tipo,                   # a fita colorida lê a senioridade de quem lidera
            parent_id=pai[cid],
            ordem=i,
            responsavel=a.nome,
            cargo=a.cargo,
            area=_t("{n} pessoa(s)", n=len(lista)),
            centro_custo="",               # o código já abre o card; repetir seria ruído
            vertical=a.vertical,
            vinculo=a.vinculo,
            responsabilidades=_escopos(lista),
            competencias=_competencias(lista),
        )
        extras_equipe[cid] = ex.get(a.id, {})

    return {"unidades": novas, "membros": membros, "extras": extras_equipe,
            "equipe_de": equipe_de}


def _escopos(lista: list[Unidade]) -> list[dict]:
    """O escopo próprio do time, sem repetir o que já é de outro card.

    Só accountability **própria** entra: a delegada de um líder é, por
    definição, o time de um subordinado — que neste desenho é um nó vizinho, e
    apareceria duas vezes.
    """
    vistos: set[str] = set()
    saida: list[dict] = []
    for p in lista:
        for r in p.responsabilidades:
            if r.get("origem") == "delegada":
                continue
            desc = (r.get("descricao") or "").strip()
            marca = sem_acento(desc)
            if desc and marca not in vistos:
                vistos.add(marca)
                saida.append({"descricao": desc, "origem": "propria"})
    return saida


def _competencias(lista: list[Unidade]) -> list[str]:
    """As competências mais frequentes do time, e não a união.

    A união de 12 pessoas vira uma lista que ninguém lê. A frequência responde
    o que a equipe de fato sabe fazer; o empate desempata por nome para o
    desenho não mudar entre execuções.
    """
    contagem: dict[str, int] = {}
    rotulo: dict[str, str] = {}
    for p in lista:
        for c in p.competencias:
            marca = sem_acento(c)
            if not marca:
                continue
            contagem[marca] = contagem.get(marca, 0) + 1
            rotulo.setdefault(marca, c.strip())
    ordenado = sorted(contagem, key=lambda m: (-contagem[m], m))
    return [rotulo[m] for m in ordenado[:6]]


def e_equipe(uid: str | None) -> bool:
    """Id derivado não é unidade gravada — quem muta precisa saber a diferença."""
    return bool(uid) and str(uid).startswith(PREFIXO + "-")


def hierarquia(membros: list[Unidade]) -> list[dict]:
    """A árvore de comando **dentro** do time, achatada em pré-ordem.

    Uma lista alfabética de doze nomes não responde "como este time se
    organiza" — e essa é justamente a pergunta que sobra quando o card diz
    apenas "12 pessoas". Aqui a indentação é o dado: quem responde a quem
    dentro daquele departamento.

    Quem tem gestor fora do time entra no nível 0: do ponto de vista do time,
    ele é o topo, mesmo que na empresa inteira responda a alguém.
    """
    dentro = {m.id for m in membros}
    por_pai: dict[str | None, list[Unidade]] = {}
    for m in membros:
        chefe = m.parent_id if m.parent_id in dentro else None
        por_pai.setdefault(chefe, []).append(m)

    # A ordem de `membros` já vem estável de `agrupar`; preservá-la aqui é o que
    # mantém o painel idêntico entre dois renders.
    posicao = {m.id: i for i, m in enumerate(membros)}
    for lista in por_pai.values():
        lista.sort(key=lambda m: posicao[m.id])

    linhas: list[dict] = []
    vistos: set[str] = set()

    def descer(pai: str | None, nivel: int) -> None:
        for m in por_pai.get(pai, []):
            if m.id in vistos:               # ciclo dentro do time não repete ninguém
                continue
            vistos.add(m.id)
            filhos = [f for f in por_pai.get(m.id, []) if f.id not in vistos]
            linhas.append({"u": m, "nivel": nivel, "chefia": len(filhos)})
            descer(m.id, nivel + 1)

    descer(None, 0)
    # Rede de segurança: ciclo puro entre membros deixaria gente de fora, e o
    # painel não pode mostrar menos pessoas do que o card contou.
    for m in membros:
        if m.id not in vistos:
            linhas.append({"u": m, "nivel": 0, "chefia": 0})
    return linhas
