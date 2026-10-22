"""Sincronização do centro de custo com o Microsoft 365.

Nenhum teste aqui toca a rede. `m365.analisar` recebe a lista de usuários já
buscada justamente para que os degraus da comparação sejam exercitáveis sem
tenant, sem credencial e sem internet — é a mesma razão pela qual
`dominio.calcular_layout` é pura.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import m365                                                       # noqa: E402
from orga.dominio import Unidade                                       # noqa: E402


def _u(uid, nome, email, cc="", vinculo="clt", area="Engineering"):
    return Unidade(id=uid, codigo=uid, nome=nome, tipo="celula", parent_id="ORG-0001",
                   ordem=0, email=email, centro_custo=cc, area=area, vinculo=vinculo)


def _g(nome, email, department=None):
    u = {"id": "aad-" + email, "displayName": nome, "mail": email,
         "userPrincipalName": email, "accountEnabled": True}
    if department is not None:
        u["department"] = department
    return u


@pytest.fixture(autouse=True)
def atributo_padrao(monkeypatch):
    monkeypatch.delenv("CC_ATTRIBUTE", raising=False)


# ---------------------------------------------------------------------------
# LEITURA DO ATRIBUTO
# ---------------------------------------------------------------------------
def test_filtro_pede_conta_habilitada_e_licenciada():
    """Sem o segundo termo entram sala, caixa compartilhada e conta de serviço,
    que não são pessoas e sujariam o relatório inteiro."""
    assert "accountEnabled eq true" in m365.FILTRO_USUARIOS
    assert "assignedLicenses/$count ne 0" in m365.FILTRO_USUARIOS


def test_select_pede_department_por_padrao():
    assert "department" in m365.campos_graph()
    assert "employeeOrgData" not in m365.campos_graph()


def test_select_troca_para_employee_org_data_quando_o_cc_e_costcenter(monkeypatch):
    monkeypatch.setenv("CC_ATTRIBUTE", "costCenter")
    campos = m365.campos_graph()
    assert "employeeOrgData" in campos
    assert "department" not in campos


@pytest.mark.parametrize("bruto,esperado", [
    ("83 - OTC", "83"),
    ("90.11 Board", "90.11"),
    ("80.31", "80.31"),
    ("  80.31 Automation  ", "80.31"),
    ("80.0 - Engineering", "80.0"),
    ("88.35 Montador", "88.35"),
    ("Engineering", None),
    ("", None),
    (None, None),
])
def test_extrai_so_o_numero(bruto, esperado):
    """No tenant da GPlanSiS|Peoples o campo traz o cargo junto do código, e o cargo
    varia entre as fontes. Só o número é lido: ele é o que não muda."""
    assert m365.extrair_cc(bruto) == esperado


def test_codigo_no_fim_do_texto_tambem_e_lido():
    """`Manutenção 95.31` existe no tenant. Sem isto, essa pessoa cairia em
    'sem o campo' tendo centro de custo declarado."""
    assert m365.extrair_cc("Manutenção 95.31") == "95.31"


@pytest.mark.parametrize("texto", ["Suporte 24h", "Turno 2", "Sala 101",
                                   "Almoxarifado", "Contas a Receber"])
def test_numero_solto_no_meio_nao_vira_centro_de_custo(texto):
    """A busca fora do início exige a forma NN.N — senão `Suporte 24h` viraria
    centro de custo 24 e a pessoa mudaria de vertical sozinha."""
    assert m365.extrair_cc(texto) is None


# ---------------------------------------------------------------------------
# DEGRAUS DA NUMERAÇÃO
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cc,nivel", [
    ("80", 1),        # LogicalCC
    ("80.0", 2),      # N2, a vertical
    ("80.30", 3),     # N3, o agrupador
    ("80.31", 4),     # N4, a equipe
    ("GBE", 0),       # não é código
    ("", 0),
    (None, 0),
])
def test_nivel_reconhece_o_esquema_do_cadastro(cc, nivel):
    """Contar pontos não descreve o esquema: `80.0` e `80.31` têm um ponto cada
    e são coisas diferentes. N3 é o N4 com o último dígito zerado."""
    assert m365.nivel_cc(cc) == nivel


@pytest.mark.parametrize("cc,nivel,esperado", [
    ("87.41", 1, "87"),
    ("87.41", 2, "87.0"),
    ("87.41", 3, "87.40"),
    ("87.41", 4, "87.41"),
])
def test_truncar_sobe_um_degrau(cc, nivel, esperado):
    assert m365.truncar(cc, nivel) == esperado


def test_cc_vem_de_employee_org_data_quando_configurado(monkeypatch):
    monkeypatch.setenv("CC_ATTRIBUTE", "employeeOrgData.costCenter")
    assert m365.cc_do_usuario({"employeeOrgData": {"costCenter": "90.11 Board"}}) == "90.11"


def test_usuario_sem_atributo_nao_tem_cc():
    assert m365.cc_do_usuario({}) is None


def test_email_prefere_mail_sobre_login():
    """`userPrincipalName` é o login e nem sempre é o endereço de verdade."""
    assert m365.email_do_usuario(
        {"mail": "Ana@gplansis.com", "userPrincipalName": "ana.ext@outro.com"}
    ) == "ana@gplansis.com"
    assert m365.email_do_usuario({"userPrincipalName": "B@x.com"}) == "b@x.com"
    assert m365.email_do_usuario({}) == ""


# ---------------------------------------------------------------------------
# COMPATIBILIDADE DE CÓDIGOS
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("m,o", [("83", "83.11"), ("80.31", "80.31"), ("80", "80.30")])
def test_tronco_igual_e_concordancia(m, o):
    assert m365.compativel(m, o)


@pytest.mark.parametrize("m,o", [("87.0", "87.41"), ("80.0", "80.31"),
                                 ("88.30", "88.31")])
def test_vertical_no_m365_concorda_com_a_equipe_gravada(m, o):
    """Caso real do tenant: o RH escreveu `80.0 - Engineering` e o organograma
    tem `80.31`. As duas fontes concordam no que o MS365 sabe — marcar isso
    como divergência aplicável gravaria a vertical por cima da equipe."""
    assert m365.compativel(m, o)


def test_prefixo_no_meio_do_numero_nao_conta():
    """Sem descer por degrau, `8` casaria com a empresa inteira."""
    assert not m365.compativel("8", "83.11")
    assert not m365.compativel("80", "8031")


@pytest.mark.parametrize("m,o", [("83", "80.31"), ("90.12", "90.11"),
                                 ("81", "80"), ("81.0", "80.31")])
def test_codigos_que_discordam_nao_sao_compativeis(m, o):
    assert not m365.compativel(m, o)


def test_codigo_gravado_que_nao_e_numero_nunca_concorda():
    """A base tem `GBE` gravado como centro de custo em uma pessoa. Não é
    código: o do MS365 é uma melhora, não um empate."""
    assert not m365.compativel("88.01", "GBE")


def test_mais_especifico_no_m365_nao_concorda_com_o_menos_especifico():
    """`80.31` no MS365 contra `80` gravado não é concordância: o organograma
    está menos preciso, e é ele que deve ganhar o código completo."""
    assert not m365.compativel("80.31", "80")


# ---------------------------------------------------------------------------
# ANÁLISE
# ---------------------------------------------------------------------------
def test_classifica_cada_pessoa_no_degrau_certo():
    unidades = {
        "U1": _u("U1", "Ana", "ana@x.com", "80.31"),      # MS365 diz 80.31 -> igual
        "U2": _u("U2", "Bia", "bia@x.com", "80.20"),      # MS365 diz 80.31 -> divergente
        "U3": _u("U3", "Caio", "caio@x.com", ""),         # sem CC -> a preencher
        "U4": _u("U4", "Davi", "davi@x.com", "83.11"),    # MS365 diz 83 -> compatível
        "U5": _u("U5", "Eva", "eva@x.com", "80.31"),      # MS365 diz 90 -> conflito
        "U6": _u("U6", "Fabi", "fabi@x.com", "80.31"),    # MS365 sem department
        "U7": _u("U7", "Gui", "gui@x.com", "80.31", vinculo="pj"),   # fora do MS365
    }
    usuarios = [
        _g("Ana", "ana@x.com", "80.31 Automation"),
        _g("Bia", "bia@x.com", "80.31 Automation"),
        _g("Caio", "caio@x.com", "80.31 Automation"),
        _g("Davi", "davi@x.com", "83 - OTC"),
        _g("Eva", "eva@x.com", "90 Board"),
        _g("Fabi", "fabi@x.com", "Engineering"),
        _g("Zoe", "zoe@x.com", "80.31"),                  # não existe no organograma
    ]
    a = m365.analisar(usuarios, unidades)

    assert [i["id"] for i in a["divergentes"]] == ["U2"]
    assert [i["id"] for i in a["a_preencher"]] == ["U3"]
    assert [i["id"] for i in a["compativeis"]] == ["U1", "U4"]
    assert [i["id"] for i in a["conflitos"]] == ["U5"]
    assert [i["id"] for i in a["sem_cc_no_m365"]] == ["U6"]
    assert [i["id"] for i in a["fora_do_m365"]] == ["U7"]
    assert [i["email"] for i in a["sem_par"]] == ["zoe@x.com"]
    assert a["total_m365"] == 7


def test_raiz_sintetica_nao_conta_como_pessoa_ausente_do_m365():
    """A raiz é um nó, não gente. Nasce sem e-mail em `montar_unidades`, então
    conta nenhuma do Graph pode casar com ela — e o aviso saía permanentemente
    errado por um, contra um card que não é pessoa. `importador.analisar` já
    excluía a raiz da lista de ausentes pelo mesmo motivo."""
    unidades = {
        "R": Unidade(id="R", codigo="ORG-0001", nome="Board", tipo="diretoria",
                     parent_id=None, ordem=0, area="Governança"),
        "U1": _u("U1", "Ana", "ana@x.com", "80.31"),
    }
    a = m365.analisar([_g("Ana", "ana@x.com", "80.31 Automation")], unidades)
    assert [i["id"] for i in a["fora_do_m365"]] == []
    assert not any("não têm conta habilitada" in v for v in a["avisos"])


def test_conta_do_m365_sem_par_nao_vira_unidade():
    """O recorte que pedimos ao Graph não traz gestor: criar aqui penduraria a
    pessoa na raiz, que é o mesmo erro que a carga da planilha recusa."""
    unidades = {}
    a = m365.analisar([_g("Zoe", "zoe@x.com", "80.31")], unidades)
    m365.aplicar(a, unidades, atualizar=True, preencher=True)
    assert unidades == {}
    assert len(a["sem_par"]) == 1


def test_quem_nao_esta_no_m365_nunca_e_removido():
    """Prestador não tem licença — ausência no Graph não é ausência na empresa."""
    unidades = {"U1": _u("U1", "Gui", "gui@x.com", "80.31", vinculo="pj")}
    a = m365.analisar([], unidades)
    m365.aplicar(a, unidades, atualizar=True, preencher=True)
    assert "U1" in unidades
    assert unidades["U1"].centro_custo == "80.31"
    assert a["fora_do_m365"][0]["vinculo"] == "pj"


def test_usuario_do_graph_sem_email_nenhum_e_ignorado():
    a = m365.analisar([{"displayName": "Sala 3", "accountEnabled": True}], {})
    assert a["sem_par"] == []


# ---------------------------------------------------------------------------
# APLICAÇÃO
# ---------------------------------------------------------------------------
def test_aplicar_grava_so_a_classe_marcada():
    unidades = {"U2": _u("U2", "Bia", "bia@x.com", "80.20"),
                "U3": _u("U3", "Caio", "caio@x.com", "")}
    usuarios = [_g("Bia", "bia@x.com", "80.31"), _g("Caio", "caio@x.com", "80.31")]
    a = m365.analisar(usuarios, unidades)

    m365.aplicar(a, unidades, atualizar=False, preencher=True)
    assert unidades["U2"].centro_custo == "80.20"      # não marcado, intacto
    assert unidades["U3"].centro_custo == "80.31"

    resumo = m365.aplicar(a, unidades, atualizar=True, preencher=True)
    assert unidades["U2"].centro_custo == "80.31"
    assert resumo["alterados"] == 1                    # U3 já estava gravado


def test_conflito_nunca_e_aplicado_mesmo_com_atualizar_ligado():
    """Gravar `90` por cima de `80.31` apagaria a equipe e quebraria a
    resolução do cadastro de centros de custo, que casa por N3."""
    unidades = {"U5": _u("U5", "Eva", "eva@x.com", "80.31")}
    a = m365.analisar([_g("Eva", "eva@x.com", "90 Board")], unidades)
    assert len(a["conflitos"]) == 1

    resumo = m365.aplicar(a, unidades, atualizar=True, preencher=True)
    assert unidades["U5"].centro_custo == "80.31"
    assert resumo["alterados"] == 0


def test_aplicar_nao_toca_em_nada_alem_do_centro_de_custo():
    """A sincronização é do CC. Nome, cargo, área e vínculo têm outra origem —
    e accountability nasce no canvas, nunca numa fonte externa."""
    unidades = {"U2": _u("U2", "Bia", "bia@x.com", "80.20", area="Engineering")}
    antes = (unidades["U2"].nome, unidades["U2"].cargo, unidades["U2"].area,
             unidades["U2"].vinculo, unidades["U2"].parent_id)
    a = m365.analisar([_g("Bia Souza", "bia@x.com", "80.31 Automation")], unidades)
    m365.aplicar(a, unidades, atualizar=True, preencher=True)

    u = unidades["U2"]
    assert (u.nome, u.cargo, u.area, u.vinculo, u.parent_id) == antes
    assert u.centro_custo == "80.31"


# ---------------------------------------------------------------------------
# O LIMITE DA ONDA
# ---------------------------------------------------------------------------
def test_o_modulo_nao_escreve_no_microsoft_365():
    """A promessa é `User.Read.All`. Se alguém acrescentar um POST, PATCH ou
    DELETE contra o Graph, este teste cai — e a permissão pedida ao Entra teria
    de mudar junto, o que é decisão de quem administra o tenant, não do código.
    """
    fonte = (RAIZ_PROJETO / "orga" / "m365.py").read_text(encoding="utf-8")
    corpo = fonte.split('"""', 2)[-1]          # fora do docstring do módulo
    for proibido in ('method="POST"', "method='POST'", 'method="PATCH"',
                     "method='PATCH'", 'method="DELETE"', "method='DELETE'"):
        assert proibido not in corpo, f"escrita no Graph: {proibido}"
    # O único `data=` legítimo é o do token; qualquer outro seria corpo de escrita.
    assert corpo.count("data=corpo") == 1


def test_paginacao_tem_teto():
    """`@odata.nextLink` que não termina deixaria a tela girando para sempre."""
    import inspect
    assert "limite_paginas" in inspect.signature(m365.buscar_usuarios).parameters


# ---------------------------------------------------------------------------
# ROTAS
# ---------------------------------------------------------------------------
@pytest.fixture
def cli():
    from fastapi.testclient import TestClient
    from orga import main
    return TestClient(main.app)


@pytest.mark.parametrize("rota", ["/config/m365/analisar", "/config/m365/aplicar"])
def test_so_admin_sincroniza(cli, rota):
    """Sincronizar reescreve o CC de gente: é configuração, não edição.
    A recusa devolve 200 com a tela intacta e um aviso (INT-06), nunca 4xx."""
    from orga import configuracao as cfgmod
    from orga import main

    antes = main.ESTADO.config.perfil
    try:
        for perfil in (cfgmod.VIEWER, cfgmod.EDITOR):
            main.ESTADO.config.perfil = perfil
            main.ESTADO.sincronizacao = None
            r = cli.post(rota)
            assert r.status_code == 200
            assert "Ação negada" in r.text
    finally:
        main.ESTADO.config.perfil = antes


def test_aplicar_sem_analise_avisa_em_vez_de_quebrar(cli):
    from orga import main

    main.ESTADO.sincronizacao = None
    r = cli.post("/config/m365/aplicar", data={"atualizar": "1"})
    assert r.status_code == 200
    assert "Nenhuma análise em andamento" in r.text


def test_falha_do_graph_nao_derruba_a_tela(cli, monkeypatch):
    """Credencial errada é o caso comum, e a frase do Entra é a que resolve o
    chamado. A tela continua de pé e o estado não é tocado."""
    from orga import main

    def _explode():
        raise RuntimeError("segredo expirado")

    monkeypatch.setattr(m365, "buscar_usuarios", _explode)
    antes = main.ESTADO.config.perfil
    try:
        main.ESTADO.config.perfil = "org.admin"
        r = cli.post("/config/m365/analisar")
        assert r.status_code == 200
        assert "segredo expirado" in r.text
        assert main.ESTADO.sincronizacao is None
    finally:
        main.ESTADO.config.perfil = antes
