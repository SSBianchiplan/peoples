"""
Provisionamento de TI e diretório social.

As duas funcionalidades nascem de um mesmo fato: o organograma já sabe de coisas
que hoje viram trabalho manual. Mudança de área já está registrada — vira pedido
de acesso. Reconhecimento já acontece — só não fica em lugar nenhum.

Aqui se testa o que elas **recusam**: pedido vazio, acesso comum às duas áreas
saindo em ambas as listas, mural anônimo e remoção por quem não pode.

    pytest testes/test_provisionamento.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import main                                                     # noqa: E402
from orga import provisionamento as prov                                  # noqa: E402
from orga import social                                                   # noqa: E402


@pytest.fixture()
def cli():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def fila_limpa():
    antes = list(main.ESTADO.provisionamentos)
    main.ESTADO.provisionamentos = []
    yield main.ESTADO.provisionamentos
    main.ESTADO.provisionamentos = antes


@pytest.fixture()
def mural_limpo():
    antes = list(main.ESTADO.mural)
    main.ESTADO.mural = []
    yield main.ESTADO.mural
    main.ESTADO.mural = antes


# ---------------------------------------------------------------------------
# Diferença de software
# ---------------------------------------------------------------------------
IX = {"Eng": ["CAD", "PLC", "Office"], "Compras": ["ERP", "Office"]}


def test_diferenca_separa_revogar_de_conceder():
    revogar, conceder = prov.diferenca(IX, "Eng", "Compras")
    assert revogar == ["CAD", "PLC"]
    assert conceder == ["ERP"]


def test_software_comum_as_duas_areas_nao_entra_em_lista_nenhuma():
    """Sairia numa lista de revogar e noutra de conceder: TI tiraria e
    devolveria o mesmo acesso no mesmo chamado."""
    revogar, conceder = prov.diferenca(IX, "Eng", "Compras")
    assert "Office" not in revogar and "Office" not in conceder


def test_base_comum_nunca_aparece():
    ix = {"A": ["Microsoft 365", "Teams", "X"], "B": ["Microsoft 365", "Y"]}
    revogar, conceder = prov.diferenca(ix, "A", "B")
    assert revogar == ["X"] and conceder == ["Y"]


def test_destino_sem_catalogo_nao_abre_pedido():
    """Sem entrada para a área nova a diferença seria "revogar tudo, conceder
    nada" — e TI cortaria o acesso de alguém porque ninguém mapeou o destino.
    A falta vira aviso na tela, não revogação."""
    u = next(iter(main.ESTADO.unidades.values()))
    assert prov.abrir(u, "Eng", "Inexistente", IX) is None


# ---------------------------------------------------------------------------
# Abertura do pedido
# ---------------------------------------------------------------------------
def test_sem_diferenca_nao_abre_pedido():
    """Chamado vazio ensina a ignorar a fila."""
    u = next(iter(main.ESTADO.unidades.values()))
    assert prov.abrir(u, "Eng", "Eng", IX) is None
    assert prov.abrir(u, "X", "Y", {"X": ["A"], "Y": ["A"]}) is None


def test_mudanca_de_area_abre_pedido_pelo_painel(cli, fila_limpa):
    """Outros testes trocam a base pela semente da SPEC, então o alvo sai do
    catálogo vigente — cravar "Electrical Engineering" tornava este teste
    dependente da ordem de execução."""
    indice = prov.indexar(main.ESTADO.config.software_por_area)
    u = next(iter(main.ESTADO.unidades.values()))
    origem, destino = list(indice)[0], list(indice)[1]
    u.area = origem
    try:
        cli.post(f"/unidades/{u.id}/salvar",
                 data={"nome": u.nome, "tipo": u.tipo, "cargo": u.cargo,
                       "area": destino, "vista": "canvas"})
        abertas = prov.abertas(fila_limpa)
        assert len(abertas) == 1
        p = abertas[0]
        assert p["de"] == origem and p["para"] == destino
        esperado_revogar, esperado_conceder = prov.diferenca(indice, origem, destino)
        assert p["revogar"] == esperado_revogar
        assert p["conceder"] == esperado_conceder
    finally:
        u.area = ""


def test_editar_sem_mudar_area_nao_abre_pedido(cli, fila_limpa):
    u = next(x for x in main.ESTADO.unidades.values() if x.area)
    cli.post(f"/unidades/{u.id}/salvar",
             data={"nome": u.nome + " ", "tipo": u.tipo, "area": u.area,
                   "vista": "canvas"})
    assert prov.abertas(fila_limpa) == []


def test_pedido_guarda_os_nomes_e_nao_a_referencia(fila_limpa):
    """Catálogo editado depois não pode reescrever pedido já aberto: chamado
    que muda sozinho não é auditável."""
    u = next(iter(main.ESTADO.unidades.values()))
    ix = {"A": ["Antigo"], "B": ["Novo"]}
    p = prov.abrir(u, "A", "B", ix)
    ix["A"] = ["Outro"]
    assert p["revogar"] == ["Antigo"]


def test_concluir_fecha_uma_vez_so(fila_limpa):
    u = next(iter(main.ESTADO.unidades.values()))
    p = prov.abrir(u, "A", "B", {"A": ["X"], "B": ["Y"]})
    fila_limpa.append(p)
    assert prov.concluir(fila_limpa, p["id"], "eu") is True
    assert prov.concluir(fila_limpa, p["id"], "eu") is False
    assert prov.abertas(fila_limpa) == []


def test_destinatarios_saem_do_organograma():
    """Lista fixa desatualiza no dia em que alguém entra ou sai de TI, e
    ninguém percebe até um chamado não chegar.

    A semente da SPEC não tem equipe de TI: o que se garante aqui é a forma —
    e-mails de gente que está na estrutura — e não que haja alguém.
    """
    alvo = prov.destinatarios(main.ESTADO.unidades, main.mapa_cc())
    emails = {u.email for u in main.ESTADO.unidades.values() if u.email}
    assert all("@" in e and e in emails for e in alvo)


def test_areas_sem_catalogo_sao_declaradas():
    ix = prov.indexar(main.ESTADO.config.software_por_area)
    faltando = prov.areas_sem_catalogo(main.ESTADO.unidades, ix)
    assert isinstance(faltando, list)
    assert all(a not in ix for a in faltando)


def test_aba_de_provisionamento_responde(cli):
    r = cli.get("/vistas/configuracoes?aba=prov")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Diretório social
# ---------------------------------------------------------------------------
AUTOR = {"id": "a1", "nome": "Quem Escreve", "cargo": "Analista"}


def test_mural_nao_aceita_anonimo():
    """Reconhecimento anônimo perde a força; feedback anônimo é outra
    ferramenta, com outro cuidado."""
    assert social.publicar("u1", {}, "obrigado") is None
    assert social.publicar("u1", {"nome": ""}, "obrigado") is None


def test_mural_nao_aceita_vazio():
    assert social.publicar("u1", AUTOR, "   ") is None
    assert social.publicar("u1", AUTOR, "") is None


def test_mensagem_e_aparada_no_limite():
    m = social.publicar("u1", AUTOR, "x" * 5000)
    assert len(m["texto"]) == social.LIMITE


def test_tipo_invalido_cai_em_reconhecimento():
    assert social.publicar("u1", AUTOR, "oi", "xpto")["tipo"] == social.RECONHECIMENTO


def test_valor_invalido_e_descartado():
    assert social.publicar("u1", AUTOR, "oi", valor="inventado")["valor"] == ""
    assert social.publicar("u1", AUTOR, "oi", valor="teamwork")["valor"] == "teamwork"


def test_card_lista_do_mais_novo_para_o_mais_antigo():
    mural = [social.publicar("u1", AUTOR, f"m{i}") for i in range(3)]
    for i, m in enumerate(mural):
        m["quando"] = f"2026-01-0{i + 1}T00:00:00+00:00"
    assert [m["texto"] for m in social.do_card(mural, "u1")] == ["m2", "m1", "m0"]


def test_card_nao_mistura_pessoas():
    mural = [social.publicar("u1", AUTOR, "a"), social.publicar("u2", AUTOR, "b")]
    assert [m["texto"] for m in social.do_card(mural, "u1")] == ["a"]


@pytest.mark.parametrize("quem,pode", [
    ("a1", True),      # autor
    ("u1", True),      # dono do card
    ("outro", False),
    ("", False),
])
def test_quem_pode_remover(quem, pode):
    m = social.publicar("u1", AUTOR, "oi")
    assert social.pode_remover(m, quem) is bool(pode)


def test_admin_remove_qualquer_uma():
    m = social.publicar("u1", AUTOR, "oi")
    assert social.pode_remover(m, "estranho", admin=True) is True


def test_remover_por_quem_nao_pode_nao_apaga():
    mural = [social.publicar("u1", AUTOR, "oi")]
    assert social.remover(mural, mural[0]["id"], "estranho") is False
    assert len(mural) == 1


def test_card_e_aparado_no_teto():
    mural = []
    for i in range(social.MAX_POR_CARD + 10):
        m = social.publicar("u1", AUTOR, f"m{i}")
        m["quando"] = f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00"
        mural.append(m)
    social.aparar(mural, "u1")
    assert len(mural) == social.MAX_POR_CARD
    assert "m0" not in [m["texto"] for m in mural]      # as mais antigas saem


def test_publicar_pela_rota_exige_vinculo(cli, mural_limpo):
    antes = main.ESTADO.config.usuario_id
    u = next(iter(main.ESTADO.unidades.values()))
    try:
        main.ESTADO.config.usuario_id = None
        r = cli.post(f"/mural/{u.id}", data={"texto": "obrigado"})
        assert r.status_code == 200
        assert "assinado" in r.text
        assert mural_limpo == []
    finally:
        main.ESTADO.config.usuario_id = antes


def test_publicar_e_remover_pela_rota(cli, mural_limpo):
    antes = main.ESTADO.config.usuario_id
    us = list(main.ESTADO.unidades.values())
    eu, alvo = us[1], us[2]
    try:
        main.ESTADO.config.usuario_id = eu.id
        r = cli.post(f"/mural/{alvo.id}",
                     data={"texto": "ajudou muito", "tipo": "reconhecimento",
                           "valor": "teamwork"})
        assert r.status_code == 200 and len(mural_limpo) == 1
        assert mural_limpo[0]["autor"] == eu.nome

        mid = mural_limpo[0]["id"]
        r = cli.request("DELETE", f"/mural/{alvo.id}/{mid}")
        assert r.status_code == 200 and mural_limpo == []
    finally:
        main.ESTADO.config.usuario_id = antes


def test_ranking_de_valores_sai_da_soma(mural_limpo):
    for valor, n in (("teamwork", 3), ("respect", 1)):
        for _ in range(n):
            mural_limpo.append(social.publicar("u1", AUTOR, "oi", valor=valor))
    assert social.ranking_valores(mural_limpo)[0] == ("teamwork", 3)
