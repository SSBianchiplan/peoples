"""
RBAC por pessoa (Fase D): papéis atribuíveis + escopo.

O perfil deixou de ser um valor GLOBAL e passou a ser RESOLVIDO no login a partir
de `Config.acessos` — a atribuição que o Admin faz por colaborador (papel +
escopo). O escopo diz ONDE o papel vale: tudo, só o próprio nó, a subárvore
abaixo (gestor), ou por vertical/departamento. Estes testes guardam a resolução e
a autorização; sem login (dev/testes) nada disso muda o comportamento de sempre.

    pytest testes/test_acessos.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import configuracao as cfgmod                                   # noqa: E402
from orga import main                                                     # noqa: E402
from orga.dominio import Unidade, descendentes, mapa_filhos, raiz         # noqa: E402


def test_normalizar_acessos_sanea_entrada_torta():
    a = cfgmod.normalizar_acessos({
        "n1": {"papel": "org.editor", "escopo": {"tipo": "subarvore", "valor": "x"}},
        "n2": {"papel": "lixo", "escopo": {"tipo": "invalido"}},
        "":   {"papel": "org.admin"},          # sem ref: fora
        "n3": "não é dict",                     # valor torto: fora
    })
    assert a["n1"]["papel"] == "org.editor"
    assert a["n1"]["escopo"] == {"tipo": "subarvore", "valor": "x"}
    assert a["n2"]["papel"] == cfgmod.VIEWER          # papel inválido -> viewer
    assert a["n2"]["escopo"]["tipo"] == "tudo"        # tipo inválido -> tudo
    assert "" not in a and "n3" not in a


@pytest.fixture()
def org_tres_niveis():
    """Uma organização mínima de TRÊS níveis (raiz → gestor → folha, com um
    segundo ramo), em memória.

    A base real de quem desenvolve tem profundidade de sobra, mas `estado.json`
    é gitignorado: na CI, sem planilha e sem banco, o sistema semeia um exemplo
    RASO (uma raiz + folhas diretas, nenhum gestor no meio). Os testes de
    subárvore e de sugestão pela hierarquia precisam de um nó que tenha gente
    abaixo E um chefe acima — senão `next(...)` não acha e cai em StopIteration.
    Fixar a estrutura aqui torna-os independentes do que está semeado."""
    orig = main.ESTADO.unidades
    main.ESTADO.unidades = {
        "R": Unidade(id="R", codigo="ORG-0001", nome="Diretoria",
                     tipo="diretoria", parent_id=None, ordem=0),
        "G": Unidade(id="G", codigo="C-G", nome="Gestor",
                     tipo="gerencia", parent_id="R", ordem=0),
        "L": Unidade(id="L", codigo="C-L", nome="Analista",
                     tipo="celula", parent_id="G", ordem=0),
        "S": Unidade(id="S", codigo="C-S", nome="Outra área",
                     tipo="gerencia", parent_id="R", ordem=1),
    }
    yield main.ESTADO.unidades
    main.ESTADO.unidades = orig


@pytest.fixture()
def cfg_isolado():
    cfg = main.ESTADO.config
    campos = ("perfil", "escopo_tipo", "escopo_valor", "escopo_id", "usuario_id",
              "modulos_visiveis")
    snap = {k: getattr(cfg, k) for k in campos}
    snap_acessos = dict(cfg.acessos)
    yield cfg
    for k, v in snap.items():
        setattr(cfg, k, v)
    cfg.acessos = snap_acessos


def test_bootstrap_sem_acessos_entra_admin(cfg_isolado):
    """Sistema não trancado ainda: sem acessos, todo login é Admin — é o que
    deixa o primeiro admin montar as atribuições."""
    cfg = cfg_isolado
    cfg.acessos = {}
    main.aplicar_acesso("quem-quer-que-seja")
    assert cfg.perfil == cfgmod.ADMIN


def test_resolve_atribuido_e_nega_o_resto(cfg_isolado):
    cfg = cfg_isolado
    algum = next(iter(main.ESTADO.unidades))
    cfg.acessos = {algum: {"papel": "org.editor",
                           "escopo": {"tipo": "subarvore", "valor": algum}}}
    main.aplicar_acesso(algum)
    assert cfg.perfil == "org.editor"
    assert cfg.escopo_tipo == "subarvore" and cfg.escopo_valor == algum
    main.aplicar_acesso("desconhecido")        # acessos não vazio -> viewer
    assert cfg.perfil == cfgmod.VIEWER and cfg.escopo_tipo == "tudo"


def test_escopo_admin_e_tudo_sao_irrestritos(cfg_isolado):
    cfg = cfg_isolado
    cfg.perfil = cfgmod.ADMIN
    assert main.escopo_permitido() is None
    cfg.perfil, cfg.escopo_tipo = "org.editor", "tudo"
    assert main.escopo_permitido() is None


def test_escopo_subarvore(cfg_isolado):
    cfg = cfg_isolado
    filhos = mapa_filhos(main.ESTADO.unidades)
    base = next(nid for nid, f in filhos.items() if nid and f)
    cfg.perfil, cfg.escopo_tipo, cfg.escopo_valor = "org.editor", "subarvore", base
    esperado = {base} | descendentes(main.ESTADO.unidades, base)
    assert main.escopo_permitido() == esperado


def test_escopo_vertical(cfg_isolado):
    """'Por vertical' recorta pelo campo `vertical` (o preenchido nas pessoas)."""
    cfg = cfg_isolado
    us = main.ESTADO.unidades
    alvo = next((u.vertical for u in us.values() if u.vertical), None)
    if not alvo:
        pytest.skip("base sem vertical")
    cfg.perfil, cfg.escopo_tipo, cfg.escopo_valor = "org.editor", "vertical", alvo
    assert main.escopo_permitido() == {i for i, u in us.items() if u.vertical == alvo}


def test_negado_respeita_o_escopo_da_subarvore(cfg_isolado, org_tres_niveis):
    cfg = cfg_isolado
    us = org_tres_niveis
    filhos = mapa_filhos(us)
    # Um gestor de verdade: tem gente abaixo E tem chefe (não é a raiz). Se fosse
    # a raiz, a subárvore seria a organização inteira e não haveria "fora".
    base = next(nid for nid, f in filhos.items() if nid and f and us[nid].parent_id)
    dentro = descendentes(us, base)
    um_dentro = next(iter(dentro))
    fora = next(i for i in us if i != base and i not in dentro)
    cfg.perfil, cfg.escopo_tipo, cfg.escopo_valor = "org.editor", "subarvore", base
    cfg.usuario_id = base
    assert main.negado(main.NIVEL_EDITOR, um_dentro) is None      # dentro: ok
    assert main.negado(main.NIVEL_EDITOR, fora) is not None       # fora: negado


def test_viewer_nao_edita_nada(cfg_isolado):
    cfg = cfg_isolado
    cfg.perfil, cfg.escopo_tipo = cfgmod.VIEWER, "tudo"
    algum = next(iter(main.ESTADO.unidades))
    assert main.negado(main.NIVEL_EDITOR, algum) is not None


def test_escopo_visivel_bate_com_a_edicao(cfg_isolado):
    """Ver e editar respeitam o MESMO conjunto — nunca duas regras que divergem."""
    cfg = cfg_isolado
    filhos = mapa_filhos(main.ESTADO.unidades)
    base = next(nid for nid, f in filhos.items() if nid and f)
    cfg.perfil, cfg.escopo_tipo, cfg.escopo_valor = "org.editor", "subarvore", base
    ids, _ = main.escopo_visivel()
    assert ids == main.escopo_permitido()


# ---------------------------------------------------------------------------
# UI: atribuir/remover acesso (HTTP), e a trava anti-lockout
# ---------------------------------------------------------------------------
def _cli():
    from fastapi.testclient import TestClient
    return TestClient(main.app)


def test_rota_atribui_e_remove_acesso(cfg_isolado):
    cfg = cfg_isolado
    cfg.acessos = {}
    cfg.usuario_id = None                    # sem admin logado (sem trava)
    alvo = next(iter(main.ESTADO.unidades))
    with _cli() as c:
        r = c.post("/config/acessos/salvar", data={
            "ref": alvo, "papel": "org.editor",
            "escopo_tipo": "subarvore", "escopo_valor": ""})
        assert r.status_code == 200
        assert alvo in cfg.acessos and cfg.acessos[alvo]["papel"] == "org.editor"
        r = c.post("/config/acessos/remover", data={"ref": alvo})
        assert r.status_code == 200 and alvo not in cfg.acessos


def test_trava_anti_lockout_mantem_o_admin(cfg_isolado):
    """Popular acessos de OUTROS não pode trancar o admin que está montando."""
    cfg = cfg_isolado
    cfg.acessos = {}
    eu = next(iter(main.ESTADO.unidades))
    outro = next(i for i in main.ESTADO.unidades if i != eu)
    cfg.usuario_id = eu                       # admin logado
    with _cli() as c:
        c.post("/config/acessos/salvar", data={
            "ref": outro, "papel": "org.viewer", "escopo_tipo": "tudo"})
    assert eu in cfg.acessos and cfg.acessos[eu]["papel"] == cfgmod.ADMIN


# ---------------------------------------------------------------------------
# Visibilidade de módulos por pessoa
# ---------------------------------------------------------------------------
def test_modulo_visivel(cfg_isolado):
    cfg = cfg_isolado
    cfg.perfil = cfgmod.ADMIN
    assert main.modulo_visivel("gptw") is True          # admin vê tudo
    cfg.perfil, cfg.modulos_visiveis = "org.viewer", []
    assert main.modulo_visivel("gptw") is True          # lista vazia = todos
    cfg.modulos_visiveis = ["canvas", "tabela"]
    assert main.modulo_visivel("tabela") is True
    assert main.modulo_visivel("gptw") is False


def test_aplicar_acesso_resolve_modulos(cfg_isolado):
    cfg = cfg_isolado
    algum = next(iter(main.ESTADO.unidades))
    cfg.acessos = {algum: {"papel": "org.viewer",
                           "escopo": {"tipo": "tudo", "valor": ""},
                           "modulos": ["canvas", "dcr"]}}
    main.aplicar_acesso(algum)
    assert cfg.modulos_visiveis == ["canvas", "dcr"]


def test_rota_salvar_guarda_modulos_e_editar_responde(cfg_isolado):
    cfg = cfg_isolado
    cfg.acessos = {}
    cfg.usuario_id = None
    alvo = next(iter(main.ESTADO.unidades))
    with _cli() as c:
        r = c.post("/config/acessos/salvar", data={
            "ref": alvo, "papel": "org.viewer", "escopo_tipo": "tudo",
            "modulos": ["canvas", "gptw"]})
        assert r.status_code == 200
        assert cfg.acessos[alvo]["modulos"] == ["canvas", "gptw"]
        r = c.get(f"/config/acessos/editar?ref={alvo}")
        assert r.status_code == 200 and "Módulos" in r.text


def test_rota_vista_barra_modulo_oculto(cfg_isolado):
    """A guarda de módulo barra a entrada pela URL, não só esconde a aba."""
    cfg = cfg_isolado
    cfg.perfil, cfg.modulos_visiveis = "org.viewer", ["canvas"]
    with _cli() as c:
        r = c.get("/vistas/gptw")
        assert "indispon" in r.text.lower()             # barrado
        assert c.get("/vistas/canvas").status_code == 200  # liberado


# ---------------------------------------------------------------------------
# Sugestão de acesso pela hierarquia + preenchimento em massa
# ---------------------------------------------------------------------------
def test_sugestao_pela_hierarquia(org_tres_niveis):
    us = org_tres_niveis
    filhos = mapa_filhos(us)
    assert main._sugerir_acesso(raiz(us), filhos)["papel"] == cfgmod.ADMIN
    gestor = next(us[n] for n, f in filhos.items() if n and f and us[n].parent_id)
    s = main._sugerir_acesso(gestor, filhos)
    assert s["papel"] == "org.editor" and s["escopo"]["tipo"] == "subarvore"
    folha = next(u for u in us.values() if u.parent_id and not filhos.get(u.id))
    s2 = main._sugerir_acesso(folha, filhos)
    assert s2["papel"] == cfgmod.VIEWER and s2["escopo"]["tipo"] == "proprio"


def test_rota_hierarquia_preenche_sem_clobber(cfg_isolado):
    cfg = cfg_isolado
    cfg.acessos = {}
    cfg.usuario_id = None
    nao_raiz = [u.id for u in main.ESTADO.unidades.values() if u.parent_id]
    with _cli() as c:
        r = c.post("/config/acessos/hierarquia")
        assert r.status_code == 200
    assert len(cfg.acessos) == len(nao_raiz)             # todos os não-raiz
    # roda de novo com um definido à mão: não sobrescreve
    alvo = nao_raiz[0]
    cfg.acessos = {alvo: {"papel": "org.admin",
                          "escopo": {"tipo": "tudo", "valor": ""}, "modulos": []}}
    with _cli() as c:
        c.post("/config/acessos/hierarquia")
    assert cfg.acessos[alvo]["papel"] == "org.admin"     # preservado
