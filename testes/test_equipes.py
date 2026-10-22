"""A estrutura vista por equipe.

A derivação é pura: recebe unidades, devolve unidades. Por isso tudo aqui roda
sem servidor, sem estado e sem navegador — a mesma razão pela qual
`dominio.calcular_layout` é testável em Python puro.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import equipes                                                    # noqa: E402
from orga.dominio import Unidade, calcular_layout, raiz                # noqa: E402


def _p(uid, nome, pai, area, cc, tipo="celula", cargo="", resp=None, comp=None):
    return Unidade(id=uid, codigo=uid, nome=nome, tipo=tipo, parent_id=pai,
                   ordem=0, area=area, centro_custo=cc, cargo=cargo,
                   responsabilidades=resp or [], competencias=comp or [])


def _base():
    """Board → dois gerentes em times diferentes, cada um com a sua gente."""
    return {u.id: u for u in [
        _p("R", "Board", None, "Board", "90.11", "diretoria"),
        _p("G1", "Ana", "R", "Engineering", "80.31", "gerencia"),
        _p("P1", "Bia", "G1", "Engineering", "80.31"),
        _p("P2", "Caio", "G1", "Engineering", "80.32"),
        _p("G2", "Davi", "R", "Managers Team", "81.21", "gerencia"),
        _p("P3", "Eva", "G2", "Managers Team", "81.21"),
    ]}


# ---------------------------------------------------------------------------
# IDENTIDADE DA EQUIPE
# ---------------------------------------------------------------------------
def test_a_chave_e_n3_mais_departamento():
    """`Managers Team` existe em quatro verticais. Agrupar por nome fundiria
    quatro times num nó só e diria uma inverdade sobre a empresa."""
    a = _p("A", "Ana", "R", "Managers Team", "80.21")
    b = _p("B", "Bia", "R", "Managers Team", "81.21")
    assert equipes.chave_equipe(a) != equipes.chave_equipe(b)


def test_o_mesmo_n3_junta_n4_diferentes():
    """80.31 e 80.32 são equipes do mesmo agrupador N3 (80.30)."""
    a = _p("A", "Ana", "R", "Engineering", "80.31")
    b = _p("B", "Bia", "R", "Engineering", "80.32")
    assert equipes.chave_equipe(a) == equipes.chave_equipe(b)


def test_o_identificador_e_legivel():
    """Ele aparece no DOM, no rótulo ARIA e no CSV: um hash obrigaria a abrir o
    depurador para saber de que time se fala."""
    uid = equipes._identificador("80.30|hardware design team")
    assert uid == "EQ-80.30-hardware-design-team"
    assert equipes.e_equipe(uid)
    assert not equipes.e_equipe("ORG-0009")


def test_acento_e_caixa_nao_criam_time_novo():
    a = _p("A", "Ana", "R", "Produção", "80.31")
    b = _p("B", "Bia", "R", "PRODUCAO", "80.31")
    assert equipes.chave_equipe(a) == equipes.chave_equipe(b)


# ---------------------------------------------------------------------------
# HIERARQUIA
# ---------------------------------------------------------------------------
def test_pessoas_viram_times_e_ninguem_se_perde():
    unidades = _base()
    r = equipes.agrupar(unidades)
    assert len(r["unidades"]) == 3                      # Board, Engineering, Managers
    assert sum(len(m) for m in r["membros"].values()) == len(unidades)


def test_o_pai_da_equipe_e_a_equipe_de_quem_chefia_a_ancora():
    r = equipes.agrupar(_base())
    eng = r["unidades"][equipes._identificador("80.30|engineering")]
    board = r["unidades"][equipes._identificador("90.10|board")]
    assert eng.parent_id == board.id
    assert board.parent_id is None


def test_a_raiz_continua_unica():
    """RF-03 vale no desenho derivado como vale no gravado."""
    r = equipes.agrupar(_base())
    assert len([u for u in r["unidades"].values() if u.parent_id is None]) == 1
    assert raiz(r["unidades"]).nome == "Board"


def test_ancora_e_quem_tem_gestor_fora_do_time():
    r = equipes.agrupar(_base())
    eng = r["unidades"][equipes._identificador("80.30|engineering")]
    assert eng.responsavel == "Ana"          # e não Bia nem Caio


def test_ciclo_entre_times_e_cortado_na_raiz():
    """Dois times podem chefiar um ao outro por caminhos diferentes. Um
    organograma com ciclo não desenha, e cair de pé vale mais."""
    unidades = {u.id: u for u in [
        _p("R", "Board", None, "Board", "90.11", "diretoria"),
        _p("A1", "Ana", "B1", "Alfa", "80.31"),      # Alfa responde a Beta
        _p("B1", "Bia", "A2", "Beta", "81.31"),      # Beta responde a Alfa
        _p("A2", "Caio", "R", "Alfa", "80.31"),
    ]}
    r = equipes.agrupar(unidades)
    assert len([u for u in r["unidades"].values() if u.parent_id is None]) == 1
    calcular_layout(r["unidades"])            # o que importa: desenha


def test_ancora_que_aponta_para_dentro_do_proprio_time_prende_na_raiz():
    """A outra porta para o mesmo estrago, e a que estava aberta.

    Quando NENHUM membro tem gestor fora do time, a âncora aponta para o
    próprio time. O corte punha `pai = None` em vez de `cid_raiz`, e nascia uma
    segunda raiz — que `enraizado()` aprova de imediato (já tem pai None), então
    o reparo pulava o caso. `dominio.raiz()` fica com uma e a subárvore da outra
    some do desenho, que é justamente o que este módulo promete não fazer.
    """
    unidades = {u.id: u for u in [
        _p("R", "Board", None, "Board", "90.11", "diretoria"),
        _p("X", "Xis", "Y", "Anel", "80.31"),       # o par responde a si mesmo,
        _p("Y", "Ipsilon", "X", "Anel", "80.31"),   # e ninguém sai do time
    ]}
    r = equipes.agrupar(unidades)
    assert len([u for u in r["unidades"].values() if u.parent_id is None]) == 1

    # E nenhum card fica órfão: a soma tem de fechar com o efetivo.
    from orga.dominio import mapa_filhos
    filhos, alcancaveis, pilha = mapa_filhos(r["unidades"]), 1, [raiz(r["unidades"]).id]
    while pilha:
        for f in filhos.get(pilha.pop(), []):
            alcancaveis += 1
            pilha.append(f.id)
    assert alcancaveis == len(r["unidades"])
    assert sum(len(v) for v in r["membros"].values()) == len(unidades)


def test_times_irmaos_nao_sao_empilhados_pelo_numero_de_pessoas():
    """O motor empilha folhas irmãs por `area`, que na pessoa é o departamento.

    No nó derivado `area` carrega o efetivo ("1 pessoa(s)"), então o padrão
    juntava num bloco só todos os times de mesmo tamanho — e o empilhamento,
    que existe para responder "quem faz o que", passava a agrupar por número de
    pessoas, que não quer dizer nada. Quem desenha o derivado passa a sua chave.

    Seis times porque `pilha_minimo` é 6: abaixo disso a fileira não empilha e
    o defeito não aparece.
    """
    unidades = {u.id: u for u in [
        _p("R", "Board", None, "Board", "90.11", "diretoria")]}
    for i, nome in enumerate(("Alfa", "Beta", "Gama", "Delta", "Epsilon", "Zeta")):
        unidades[nome] = _p(nome, f"P{i}", "R", nome, f"8{i}.31")

    r = equipes.agrupar(unidades)
    times = {u.id for u in r["unidades"].values() if u.parent_id is not None}
    assert len(times) == 6
    assert len({u.area for u in r["unidades"].values()}) == 1   # todos "1 pessoa(s)"

    def colunas(**kw):
        lay = calcular_layout(r["unidades"], **kw)
        return {round(n["x"], 2) for n in lay["nos"] if n["id"] in times}

    from orga import main
    assert len(colunas()) == 2, "premissa: pelo padrão os seis viram um bloco só"
    assert len(colunas(chave_bloco=main._bloco_por_equipe)) == 6


def test_pessoa_sem_departamento_nao_some():
    """Sumir com ela deixaria a soma dos cards menor que o quadro de pessoal."""
    unidades = _base()
    unidades["X"] = _p("X", "Fabi", "R", "", "")
    r = equipes.agrupar(unidades)
    assert sum(len(m) for m in r["membros"].values()) == len(unidades)
    assert any("Sem departamento" in u.nome for u in r["unidades"].values())


def test_duas_execucoes_dao_o_mesmo_desenho():
    """RNF-02: sem desempate estável, dois times trocariam de lugar entre
    execuções e o SVG deixaria de ser byte-idêntico."""
    unidades = _base()
    a = equipes.agrupar(unidades)
    b = equipes.agrupar(unidades)
    assert [u.id for u in a["unidades"].values()] == [u.id for u in b["unidades"].values()]
    assert [(u.id, u.ordem, u.parent_id) for u in a["unidades"].values()] == \
           [(u.id, u.ordem, u.parent_id) for u in b["unidades"].values()]


# ---------------------------------------------------------------------------
# O CARD DA EQUIPE
# ---------------------------------------------------------------------------
def test_o_card_conta_quantas_pessoas_recolheu():
    r = equipes.agrupar(_base())
    eng = r["unidades"][equipes._identificador("80.30|engineering")]
    assert "3" in eng.area                     # Ana, Bia e Caio


def test_a_fita_lê_a_senioridade_de_quem_lidera():
    r = equipes.agrupar(_base())
    eng = r["unidades"][equipes._identificador("80.30|engineering")]
    assert eng.tipo == "gerencia"


def test_accountability_delegada_nao_entra_no_card_do_time():
    """A delegada de um líder é o time de um subordinado — que neste desenho é
    um nó vizinho, e apareceria duas vezes."""
    unidades = _base()
    unidades["G1"].responsabilidades = [
        {"descricao": "Managers Team", "origem": "delegada"},
        {"descricao": "Planejamento de capacidade", "origem": "propria"},
    ]
    r = equipes.agrupar(unidades)
    eng = r["unidades"][equipes._identificador("80.30|engineering")]
    descricoes = [x["descricao"] for x in eng.responsabilidades]
    assert descricoes == ["Planejamento de capacidade"]


def test_escopo_repetido_no_time_aparece_uma_vez():
    unidades = _base()
    for uid in ("G1", "P1", "P2"):
        unidades[uid].responsabilidades = [{"descricao": "Projetos", "origem": "propria"}]
    r = equipes.agrupar(unidades)
    eng = r["unidades"][equipes._identificador("80.30|engineering")]
    assert len(eng.responsabilidades) == 1


def test_competencias_saem_por_frequencia_e_nao_pela_uniao():
    """A união de 12 pessoas vira uma lista que ninguém lê."""
    unidades = _base()
    unidades["G1"].competencias = ["CLP", "Gestão"]
    unidades["P1"].competencias = ["CLP"]
    unidades["P2"].competencias = ["CLP", "SCADA"]
    r = equipes.agrupar(unidades)
    eng = r["unidades"][equipes._identificador("80.30|engineering")]
    assert eng.competencias[0] == "CLP"
    assert len(eng.competencias) <= 6


# ---------------------------------------------------------------------------
# O DESENHO
# ---------------------------------------------------------------------------
def test_o_agrupado_atravessa_o_motor_de_layout_sem_saber_dele():
    """Nada em `calcular_layout` sabe que existe modo por equipe — é o que faz
    o SVG, o PDF e o CSV virem de graça."""
    r = equipes.agrupar(_base())
    layout = calcular_layout(r["unidades"], "invertida")
    assert len(layout["nos"]) == 3
    ys = {n["id"]: n["y"] for n in layout["nos"]}
    board = equipes._identificador("90.10|board")
    eng = equipes._identificador("80.30|engineering")
    assert ys[board] > ys[eng]                 # liderança na base (LAY-01)


def test_base_vazia_nao_quebra():
    r = equipes.agrupar({})
    assert r["unidades"] == {} and r["membros"] == {}


# ---------------------------------------------------------------------------
# A HIERARQUIA DENTRO DO TIME
# ---------------------------------------------------------------------------
def test_a_indentacao_e_quem_responde_a_quem():
    """Uma lista alfabética de doze nomes não responde "como este time se
    organiza" — e essa é a pergunta que sobra quando o card diz "12 pessoas"."""
    r = equipes.agrupar(_base())
    cid = equipes._identificador("80.30|engineering")
    linhas = equipes.hierarquia(r["membros"][cid])
    por_nome = {l["u"].nome: l for l in linhas}
    assert por_nome["Ana"]["nivel"] == 0          # gestora está fora do time
    assert por_nome["Bia"]["nivel"] == 1
    assert por_nome["Caio"]["nivel"] == 1
    assert por_nome["Ana"]["chefia"] == 2


def test_quem_chefia_fora_do_time_entra_no_topo_da_arvore():
    r = equipes.agrupar(_base())
    cid = equipes._identificador("81.20|managers team")
    linhas = equipes.hierarquia(r["membros"][cid])
    assert linhas[0]["u"].nome == "Davi" and linhas[0]["nivel"] == 0


def test_a_arvore_do_time_nao_perde_ninguem():
    """O painel não pode mostrar menos gente do que o card contou."""
    r = equipes.agrupar(_base())
    for cid, membros in r["membros"].items():
        assert len(equipes.hierarquia(membros)) == len(membros)


def test_ciclo_dentro_do_time_nao_repete_nem_some():
    unidades = {u.id: u for u in [
        _p("R", "Board", None, "Board", "90.11", "diretoria"),
        _p("A", "Ana", "B", "Alfa", "80.31"),        # Ana responde a Bia
        _p("B", "Bia", "A", "Alfa", "80.31"),        # e Bia responde a Ana
    ]}
    r = equipes.agrupar(unidades)
    cid = equipes._identificador("80.30|alfa")
    linhas = equipes.hierarquia(r["membros"][cid])
    assert len(linhas) == 2
    assert len({l["u"].id for l in linhas}) == 2
