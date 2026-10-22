"""
Painel de RH / Departamento Pessoal — o motor de indicadores.

Como `dcr` e `tempo`, `painel_rh` é puro: recebe unidades, mapa de CC e log de
acessos, e devolve os agregados que a vista e o Excel consomem. Estes testes não
sobem o app — exercitam os números direto, com uma data de referência fixa (o
motor nunca chama `date.today()` sozinho quando `ref` é dado).

    pytest testes/test_painel_rh.py -q
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

import pytest                                                            # noqa: E402
from fastapi.testclient import TestClient                                # noqa: E402

from orga import main                                                     # noqa: E402
from orga import painel_rh                                                # noqa: E402
from orga.configuracao import ADMIN, VIEWER                               # noqa: E402
from orga.dominio import Unidade                                          # noqa: E402

REF = date(2026, 8, 15)


def _p(uid, nome, pai, *, tipo="celula", area="Eng", vertical="83.0",
       vinculo="clt", data="", status="Ativo", n5="", cargo="Analista"):
    return Unidade(id=uid, codigo=uid, nome=nome, tipo=tipo, parent_id=pai,
                   ordem=0, cargo=cargo, area=area, vertical=vertical,
                   vinculo=vinculo, data_inicio=data, status=status, n5=n5)


def _org():
    """Raiz + gestor + quatro pessoas, com datas e vínculos variados."""
    return {u.id: u for u in [
        Unidade(id="R", codigo="ORG-RAIZ", nome="Board", tipo="diretoria",
                parent_id=None, ordem=0, vinculo="nao_aplicavel"),
        _p("g", "Gina", "R", tipo="gerencia", area="Eng", data="2015-03-01"),
        _p("a", "Ana", "g", area="Eng", data="2026-08-03", vinculo="clt"),
        _p("b", "Bea", "g", area="Doc", data="2024-01-10", vinculo="pj"),
        _p("c", "Caio", "g", area="Doc", data="2020-06-20", vinculo="estagio"),
    ]}


# --- KPIs -------------------------------------------------------------------
def test_kpis_conta_gente_gestor_e_vinculo():
    k = painel_rh.kpis(_org(), ref=REF)
    assert k["total"] == 5
    assert k["gestores"] == 2           # Board (tem Gina) e Gina (tem 3)
    assert k["departamentos"] == 2      # Eng, Doc
    # três terceirizados? não: só Bea (pj) e Caio (estagio) contam
    assert k["terceiros"] == 2
    assert k["clt"] == 2                 # Gina e Ana
    assert 0 <= k["pct_clt"] <= 100


def test_tempo_medio_de_casa_usa_a_data_de_referencia():
    # só Gina (2015) e Caio (2020) e Bea (2024) e Ana (2026): média > 0
    k = painel_rh.kpis(_org(), ref=REF)
    assert k["tempo_medio"] > 0


def test_kpis_nao_estoura_com_org_vazia():
    k = painel_rh.kpis({}, ref=REF)
    assert k["total"] == 0
    assert k["tempo_medio"] == 0
    assert k["pct_clt"] == 0


# --- Distribuições ----------------------------------------------------------
def test_serie_traz_barra_proporcional_e_pct():
    dist = painel_rh.distribuicoes(_org(), {}, [], ref=REF)
    total = sum(it["valor"] for it in dist["vinculo"])
    assert total == 5
    # a maior fatia tem barra 100
    assert max(it["barra"] for it in dist["vinculo"]) == 100


def test_admissao_por_ano_ordena_cronologico():
    anos = [it["chave"] for it in painel_rh.distribuicoes(_org(), {}, [], ref=REF)["admissao_ano"]]
    assert anos == sorted(anos)
    assert "2026" in anos


def test_departamento_limita_ao_top_12():
    org = {f"u{i}": _p(f"u{i}", f"P{i}", "R", area=f"Dept {i}") for i in range(20)}
    serie = painel_rh.distribuicoes(org, {}, [], ref=REF)["departamento"]
    assert len(serie) == 12


# --- Contratações -----------------------------------------------------------
def test_ultimas_contratacoes_mais_recentes_primeiro():
    c = painel_rh.ultimas_contratacoes(_org(), ref=REF)
    datas = [x["data"] for x in c]
    assert datas == sorted(datas, reverse=True)
    assert c[0]["nome"] == "Ana"        # 2026-08-03 é a mais recente


def test_contratacoes_do_mes_marca_o_mes_corrente():
    domes = painel_rh.contratacoes_do_mes(_org(), ref=REF)
    assert [x["nome"] for x in domes] == ["Ana"]   # ago/2026
    assert all(x["no_mes"] for x in domes)


# --- Movimentação (log de acesso) -------------------------------------------
def test_movimentacao_lista_saidas_e_inativos():
    org = _org()
    log = [
        {"usuario_id": "g", "evento": "entrar", "quando": "2026-08-14T09:00",
         "nome": "Gina", "email": "gina@x"},
        {"usuario_id": "g", "evento": "sair", "quando": "2026-08-14T18:00",
         "nome": "Gina", "email": "gina@x"},
    ]
    mov = painel_rh.movimentacao(log, org, ref=REF, dias_inativo=30)
    assert mov["saidas"] and mov["saidas"][0]["nome"] == "Gina"
    # Gina saiu ontem: não é inativa. Os outros nunca acessaram.
    nomes_inativos = {x["nome"] for x in mov["inativos"]}
    assert "Gina" not in nomes_inativos
    assert mov["n_nunca"] == 4          # Board, Ana, Bea, Caio


def test_movimentacao_conta_inatividade_por_dias():
    org = _org()
    log = [{"usuario_id": "a", "evento": "entrar", "quando": "2026-01-01T09:00",
            "nome": "Ana", "email": "ana@x"}]
    mov = painel_rh.movimentacao(log, org, ref=REF, dias_inativo=30)
    ana = next(x for x in mov["inativos"] if x["nome"] == "Ana")
    assert ana["nunca"] is False
    assert ana["dias"] and ana["dias"] > 30


# --- Lista por fatia (clique numa barra/segmento) ---------------------------
def test_colaboradores_por_bate_com_a_barra():
    org = _org()
    # a fatia "Doc" do gráfico de departamento tem Bea e Caio
    doc = painel_rh.colaboradores_por(org, "departamento", "Doc", ref=REF)
    assert {p["nome"] for p in doc} == {"Bea", "Caio"}
    # ordenada por nome
    assert [p["nome"] for p in doc] == ["Bea", "Caio"]


def test_colaboradores_por_vinculo_e_ano():
    org = _org()
    clt = painel_rh.colaboradores_por(org, "vinculo", "clt", ref=REF)
    assert {p["nome"] for p in clt} == {"Gina", "Ana"}
    y2026 = painel_rh.colaboradores_por(org, "admissao_ano", "2026", ref=REF)
    assert {p["nome"] for p in y2026} == {"Ana"}


def test_colaboradores_por_dim_desconhecida_vazia():
    assert painel_rh.colaboradores_por(_org(), "inventada", "x", ref=REF) == []


# --- Desligamentos (status do RH, não logout) -------------------------------
def test_desligamentos_le_o_status_inativo():
    org = _org()
    org["c"].status = "Inativo"          # Caio foi desligado
    fora = painel_rh.desligamentos(org, ref=REF)
    assert [p["nome"] for p in fora] == ["Caio"]
    assert fora[0]["status"].lower() != "ativo"


def test_desligamentos_vazio_quando_todos_ativos():
    assert painel_rh.desligamentos(_org(), ref=REF) == []


# --- Curva de crescimento ---------------------------------------------------
def test_crescimento_e_acumulado_e_monotonico():
    c = painel_rh.crescimento(_org(), ref=REF)
    acc = [p["acumulado"] for p in c]
    assert acc == sorted(acc)            # nunca decresce
    assert c[-1]["acumulado"] == 4       # 4 pessoas com data (todas menos a raiz)
    # coordenadas normalizadas dentro de 0..100
    assert all(0 <= p["x"] <= 100 and 0 <= p["y"] <= 100 for p in c)


def test_crescimento_vazio_sem_datas():
    org = {u.id: u for u in _org().values()}
    for u in org.values():
        u.data_inicio = ""
    assert painel_rh.crescimento(org, ref=REF) == []


# --- Sincronização do N5 ----------------------------------------------------
def test_sincronizar_n5_preenche_do_mapa_de_cc():
    org = _org()
    mapa = {"a": {"n5": "ENG"}, "b": {"n5": "DOC"}, "c": {}}
    r = painel_rh.sincronizar_n5(org, mapa)
    assert org["a"].n5 == "ENG"
    assert org["b"].n5 == "DOC"
    assert r["atualizados"] == 2
    assert r["sem_cc"] >= 1             # Caio e os que não estão no mapa


def test_sincronizar_n5_nao_reescreve_o_que_ja_esta_certo():
    org = _org()
    org["a"].n5 = "ENG"
    mapa = {"a": {"n5": "ENG"}}
    r = painel_rh.sincronizar_n5(org, mapa)
    assert r["ja_corretos"] == 1
    assert r["atualizados"] == 0


def test_sincronizar_n5_so_toca_o_n5():
    org = _org()
    antes = {uid: (u.cargo, u.area, u.vertical, u.vinculo) for uid, u in org.items()}
    painel_rh.sincronizar_n5(org, {"a": {"n5": "ENG"}})
    depois = {uid: (u.cargo, u.area, u.vertical, u.vinculo) for uid, u in org.items()}
    assert antes == depois             # nada além do N5 mudou


# --- Rotas (o app, com estado isolado) --------------------------------------
@pytest.fixture(autouse=True)
def estado_isolado(tmp_path):
    """Seed fixo da SPEC — nunca toca o estado real de produção. Restaura o perfil
    ao sair: um teste que baixa para VIEWER não pode deixar a sessão sem edição
    para o próximo arquivo de testes (o /salvar do provisionamento depende disso)."""
    perfil_antes = main.ESTADO.config.perfil
    main.ARQUIVO_ESTADO = tmp_path / "estado.json"
    main.semear(spec=True)
    main.ESTADO.config.perfil = ADMIN
    main.ESTADO.historico.clear()
    yield
    main.ESTADO.config.perfil = perfil_antes


@pytest.fixture
def cli():
    return TestClient(main.app)


def test_painel_rh_e_a_primeira_aba(cli):
    r = cli.get("/?vista=painel_rh")
    assert r.status_code == 200
    assert 'hx-get="/vistas/painel_rh"' in r.text
    # é o primeiro módulo do cabeçalho: aparece antes do Canvas
    assert r.text.index('/vistas/painel_rh"') < r.text.index('/vistas/canvas"')


def test_corpo_traz_os_kpis(cli):
    r = cli.get("/painel-rh/corpo")
    assert r.status_code == 200
    # KPIs + os cards em colunas explícitas (rosca+curva no par, barras no trio)
    assert "rh-kpis" in r.text and "rh-par" in r.text and "rh-trio" in r.text


def test_sincronizar_n5_pela_rota(cli):
    r = cli.post("/painel-rh/sincronizar-n5")
    assert r.status_code == 200
    assert "rh-kpis" in r.text          # devolve o corpo re-renderizado


def test_export_xlsx_devolve_planilha(cli):
    r = cli.get("/painel-rh/export.xlsx")
    assert r.status_code == 200
    assert "spreadsheetml.sheet" in r.headers.get("content-type", "")
    assert r.content[:2] == b"PK"       # um .xlsx é um zip


def test_lista_por_fatia_abre_modal(cli):
    # vínculo clt cobre todo o seed — a lista traz gente, com link pra ficha
    r = cli.get("/painel-rh/lista?dim=vinculo&chave=clt")
    assert r.status_code == 200
    assert "rh-lista-modal" in r.text
    assert "/unidades/" in r.text          # cada pessoa abre a ficha


def test_lista_desligamentos_usa_status(cli):
    # marca alguém como inativo e confirma que entra na lista de desligamentos
    uid = next(iter(main.ESTADO.unidades))
    main.ESTADO.unidades[uid].status = "Inativo"
    r = cli.get("/painel-rh/lista?dim=desligamentos")
    assert r.status_code == 200
    assert main.ESTADO.unidades[uid].nome in r.text


def test_corpo_tem_rosca_e_curva(cli):
    # dá datas de admissão pra curva ter o que traçar
    for i, u in enumerate(main.ESTADO.unidades.values()):
        u.data_inicio = f"20{15 + i % 8:02d}-06-01"
    r = cli.get("/painel-rh/corpo")
    assert "rh-rosca" in r.text          # a rosca de vínculo
    assert "rh-curva" in r.text          # a curva de crescimento
    # a antiga "saídas (logout)" saiu; entra "Desligamentos"
    assert "logout" not in r.text.lower()


def test_export_e_sync_sao_so_de_admin(cli):
    main.ESTADO.config.perfil = VIEWER
    x = cli.get("/painel-rh/export.xlsx")
    # negado: volta um alerta HTML, não o binário do Excel
    assert "spreadsheetml" not in x.headers.get("content-type", "")
    s = cli.post("/painel-rh/sincronizar-n5")
    assert "rh-kpis" not in s.text
