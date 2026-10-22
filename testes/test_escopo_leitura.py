"""Escopo de LEITURA: cada um vê só o seu, pela hierarquia.

Antes o escopo só barrava EDIÇÃO; a leitura era aberta. Agora as vistas humanas
(Tabela, Canvas, fichas, módulos) mostram só o universo que o escopo permite —
com a flag `ver_tudo` como válvula de escape (vê tudo sem poder editar tudo). O
que estes testes provam: nenhum nó de fora do escopo aparece, o escopo torto
FECHA (não abre), e Admin/`tudo`/`ver_tudo` continuam vendo tudo.

    pytest testes/test_escopo_leitura.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import configuracao as cfgmod                                   # noqa: E402
from orga import main                                                     # noqa: E402
from orga.dominio import Unidade                                          # noqa: E402


@pytest.fixture()
def org():
    """Org de teste: R(raiz) → G(gestor, Dept A) → L(analista, Dept A); S(gestor,
    Dept B); L2(analista, Dept C, sob S). Vertical 'V-ALM' = {G, L, L2} fica
    DESCONEXO (G no ramo de G, L2 no ramo de S), exercitando a floresta virtual."""
    e = main.ESTADO
    snap = (e.unidades, e.foco, e.colapsados, e.filtros, e.agrupamento)
    e.unidades = {
        "R": Unidade(id="R", codigo="ORG-0001", nome="Diretoria", tipo="diretoria",
                     parent_id=None, ordem=0),
        "G": Unidade(id="G", codigo="C-G", nome="Gestor A", tipo="gerencia",
                     parent_id="R", ordem=0, vertical="V-ALM", area="Dept A"),
        "L": Unidade(id="L", codigo="C-L", nome="Analista A", tipo="celula",
                     parent_id="G", ordem=0, vertical="V-ALM", area="Dept A"),
        "S": Unidade(id="S", codigo="C-S", nome="Gestor B", tipo="gerencia",
                     parent_id="R", ordem=1, vertical="V-ENG", area="Dept B"),
        "L2": Unidade(id="L2", codigo="C-L2", nome="Analista A2", tipo="celula",
                      parent_id="S", ordem=0, vertical="V-ALM", area="Dept C"),
    }
    e.foco, e.colapsados, e.filtros, e.agrupamento = None, set(), main.filtros_vazios(), "pessoa"
    main.esquecer_equipes()
    yield e.unidades
    e.unidades, e.foco, e.colapsados, e.filtros, e.agrupamento = snap
    main.esquecer_equipes()


@pytest.fixture()
def como():
    """Ajusta a sessão nos campos do Config global (fallback sem cookie) e restaura."""
    cfg = main.ESTADO.config
    campos = ("perfil", "escopo_tipo", "escopo_valor", "escopo_id",
              "usuario_id", "ver_tudo", "modulos_visiveis")
    snap = {k: getattr(cfg, k) for k in campos}

    def setar(perfil=cfgmod.VIEWER, tipo="tudo", valor="", uid=None, ver_tudo=False):
        cfg.perfil, cfg.escopo_tipo, cfg.escopo_valor = perfil, tipo, valor
        cfg.escopo_id, cfg.usuario_id, cfg.ver_tudo = None, uid, ver_tudo
    yield setar
    for k, v in snap.items():
        setattr(cfg, k, v)


@pytest.fixture()
def cli():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


def _ids_tabela():
    return {linha["u"].id for linha in main.linhas_tabela()}


def _ids_canvas():
    return {n["id"] for n in main.layout_atual(None)["nos"]}


# ---------------------------------------------------------------------------
# Admin / tudo: sem regressão
# ---------------------------------------------------------------------------
def test_admin_ve_tudo(org, como):
    como(perfil=cfgmod.ADMIN, tipo="tudo")
    assert main.universo_visivel() is None
    assert _ids_tabela() == set(org)


# ---------------------------------------------------------------------------
# Escopo ESTRITO por vista
# ---------------------------------------------------------------------------
def test_subarvore_so_a_propria_subarvore(org, como):
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="G")
    assert set(main.universo_visivel()) == {"G", "L"}
    assert _ids_tabela() == {"G", "L"}          # sem R (chefe) nem S/L2


def test_vertical_recorta_pela_vertical(org, como):
    como(perfil=cfgmod.EDITOR, tipo="vertical", valor="V-ALM")
    assert set(main.universo_visivel()) == {"G", "L", "L2"}
    assert _ids_tabela() == {"G", "L", "L2"}    # V-ENG (S) fica de fora


def test_proprio_ve_o_card_e_a_lideranca(org, como):
    """Só o próprio nó: vê o seu card + a liderança acima (cadeia até o topo)."""
    como(perfil=cfgmod.VIEWER, tipo="proprio", uid="L")
    assert main.escopo_permitido() == {"L"}                    # edita só o seu
    assert set(main.universo_visivel()) == {"L", "G", "R"}     # vê L + a chefia
    assert _ids_tabela() == {"L", "G", "R"}


def test_subarvore_vazia_usa_o_gestor_direto(org, como):
    """Subárvore com valor vazio: a base é o GESTOR direto (o pai) — o time dele."""
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="", uid="L")
    assert set(main.universo_visivel()) == {"G", "L"}          # o time do gestor G
    assert "R" not in _ids_tabela()


def test_departamento_mostra_o_gestor(org, como):
    """Por departamento: a equipe/departamento + o gestor imediato (a quem responde)."""
    como(perfil=cfgmod.VIEWER, tipo="departamento", valor="Dept A")
    assert main.escopo_permitido() == {"G", "L"}               # edita o departamento
    assert set(main.universo_visivel()) == {"G", "L", "R"}     # + o gestor R
    assert _ids_tabela() == {"G", "L", "R"}


def test_tabela_nao_mostra_ancestral_como_passagem(org, como):
    """O bug clássico da árvore: mostrar o chefe esmaecido como 'passagem'. No
    escopo estrito, R (chefe de G) NÃO pode aparecer em linha nenhuma."""
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="G")
    assert "R" not in _ids_tabela()


# ---------------------------------------------------------------------------
# Canvas: subárvore conexa e vertical desconexa (raiz virtual)
# ---------------------------------------------------------------------------
def test_canvas_subarvore_nao_desenha_o_chefe(org, como):
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="G")
    ids = _ids_canvas()
    assert ids <= {"G", "L"} and "R" not in ids and "S" not in ids


def test_canvas_escopo_abre_a_raiz_do_recorte(org, como):
    """Regressão: o colapso global dobra tudo em profundidade >= 1 (medido do topo
    da empresa). O canvas do escopo é re-rootado num nó fundo (G), que JÁ vinha
    dobrado nesse colapso — o gestor via só o próprio nó como '+N'. A base do
    recorte tem de abrir, como o canvas cheio abre a partir da raiz."""
    main.ESTADO.colapsados = {"G"}               # G dobrado no colapso global
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="G")
    ids = _ids_canvas()
    assert "G" in ids and "L" in ids             # a base abre e mostra o time
    # e o colapso global não é mutado — a correção é só na leitura do canvas
    assert main.ESTADO.colapsados == {"G"}


def test_canvas_proprio_desenha_a_cadeia_da_lideranca(org, como):
    """Próprio: o Canvas desenha a cadeia raiz→gestor→você (conjunto conexo, raiz
    única = o topo), sem os ramos de fora."""
    como(perfil=cfgmod.VIEWER, tipo="proprio", uid="L")
    assert _ids_canvas() == {"R", "G", "L"}      # a liderança + o próprio; sem S/L2


def test_canvas_vertical_desconexa_usa_raiz_virtual(org, como):
    como(perfil=cfgmod.EDITOR, tipo="vertical", valor="V-ALM")  # {G,L,L2} desconexo
    ids = _ids_canvas()
    assert "ESC-RAIZ" in ids                     # a raiz virtual da floresta
    assert (ids - {"ESC-RAIZ"}) <= {"G", "L", "L2"}
    assert "R" not in ids and "S" not in ids


# ---------------------------------------------------------------------------
# FAIL-CLOSED: escopo configurado mas não-resolvível FECHA, não abre
# ---------------------------------------------------------------------------
def test_fail_closed_subarvore_base_inexistente(org, como):
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="NAO-EXISTE")
    assert main.escopo_permitido() == set()      # set(), não None
    assert main.universo_visivel() == {}
    assert _ids_tabela() == set()


def test_fail_closed_vertical_sem_valor(org, como):
    como(perfil=cfgmod.EDITOR, tipo="vertical", valor="")
    assert main.escopo_permitido() == set()
    assert _ids_tabela() == set()


# ---------------------------------------------------------------------------
# A flag ver_tudo: abre a LEITURA sem abrir a EDIÇÃO
# ---------------------------------------------------------------------------
def test_ver_tudo_abre_leitura_mas_nao_edicao(org, como):
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="G", ver_tudo=True)
    # leitura: vê o organograma inteiro
    assert main.escopo_leitura() is None
    assert main.universo_visivel() is None
    assert _ids_tabela() == set(org)
    # edição: continua presa à subárvore de G (a flag não mexe na edição)
    assert main.escopo_permitido() == {"G", "L"}


# ---------------------------------------------------------------------------
# Ficha por URL: não abre a de quem está fora do escopo
# ---------------------------------------------------------------------------
def test_ficha_de_fora_do_escopo_nao_abre(org, como, cli):
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="G")   # vê {G, L}
    fora = cli.get("/unidades/S/ficha")                        # S está fora
    assert "encontrada" in fora.text.lower()                   # "não encontrada"
    dentro = cli.get("/unidades/L/ficha")                      # L está dentro
    assert "Analista A" in dentro.text


# ---------------------------------------------------------------------------
# Portas dos fundos que a caça adversarial achou (regressão)
# ---------------------------------------------------------------------------
def test_csv_export_recorta_ao_escopo(org, como, cli):
    """O CSV da Tabela não pode baixar a organização inteira para quem tem escopo."""
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="G")   # vê {G, L}
    txt = cli.get("/export.csv").text
    assert "Gestor A" in txt and "Analista A" in txt            # dentro
    assert "Diretoria" not in txt and "Gestor B" not in txt     # R, S fora


def test_export_json_e_so_de_admin(org, como, cli):
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="G")   # não-admin, escopo
    assert cli.get("/export.json").status_code == 403
    como(perfil=cfgmod.ADMIN, tipo="tudo")
    assert cli.get("/export.json").status_code == 200


def test_canvas_fail_closed_nao_desenha_a_raiz_real(org, como):
    """Escopo não-resolvível não pode cair na raiz(ESTADO.unidades) = o CEO."""
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="NAO-EXISTE")
    ids = _ids_canvas()
    assert "R" not in ids and "S" not in ids                   # topo real não vaza
    assert ids <= {"ESC-RAIZ"}                                  # só a raiz virtual


def test_menu_de_fora_do_escopo_vem_vazio(org, como, cli):
    """/fragmentos/menu/{uid} não pode revelar o nome de um nó de fora do escopo."""
    como(perfil=cfgmod.EDITOR, tipo="subarvore", valor="G")   # vê {G, L}
    assert cli.get("/fragmentos/menu/S").text.strip() == ""    # S fora: vazio
    assert "C-L" in cli.get("/fragmentos/menu/L").text         # L dentro
