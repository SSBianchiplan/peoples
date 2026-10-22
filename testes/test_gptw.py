"""
Peoples Place to Work — a pesquisa de clima anônima.

O motor é puro como dcr/cgv/talentos: recebe respostas, devolve dicionários. A
resposta NÃO tem dono; liga-se ao sistema pelos estratos. O PTI é o % de
respostas 4–5 sobre as válidas; nenhum recorte com menos de 5 respondentes é
publicado.

    pytest testes/test_gptw.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

import pytest                                                            # noqa: E402
from fastapi.testclient import TestClient                                # noqa: E402

from orga import gptw                                                    # noqa: E402
from orga import main                                                    # noqa: E402
from orga.configuracao import ADMIN                                      # noqa: E402
from orga.dominio import Unidade                                         # noqa: E402


def _resp(i, valor=5, **estr):
    base = {"id": f"r{i}", "ciclo": "anual", "ano": 2026,
            "respostas": {aid: valor for aid, _p, _t, _pu in gptw.AFIRMACOES},
            "nivel": "celula", "area": "Eng", "vinculo": "clt",
            "faixa": "1a3", "modelo": "hibrido"}
    base.update(estr)
    return base


# ---------------------------------------------------------------------------
# O instrumento — 60 afirmações, 5 pilares, 15 no pulso
# ---------------------------------------------------------------------------
def test_sessenta_afirmacoes_doze_por_pilar():
    assert len(gptw.AFIRMACOES) == 60
    from collections import Counter
    por = Counter(a[1] for a in gptw.AFIRMACOES)
    assert set(por) == set(gptw.COD_PILAR)
    assert all(n == 12 for n in por.values())


def test_quinze_no_pulso_tres_por_pilar():
    assert len(gptw.IDS_PULSO) == 15
    from collections import Counter
    por = Counter(gptw.PILAR_DE[i] for i in gptw.IDS_PULSO)
    assert all(n == 3 for n in por.values())


def test_dez_perguntas_abertas():
    assert len(gptw.ABERTAS) == 10


# ---------------------------------------------------------------------------
# Anonimato e saneamento
# ---------------------------------------------------------------------------
def test_resposta_nunca_guarda_identidade():
    r = gptw.normalizar_resposta({
        "id": "x", "ano": 2026, "ciclo": "anual", "ref": "SAP-9",
        "usuario_id": "u1", "respostas": {1: 5}, "nivel": "celula"})
    assert "ref" not in r and "usuario_id" not in r
    assert r["nivel"] == "celula"


def test_valor_fora_da_escala_cai():
    r = gptw.normalizar_resposta({"ano": 2026, "respostas": {1: 9, 2: 0, 3: 4}})
    assert r["respostas"] == {3: 4}          # só o válido ficou


def test_afirmacao_inexistente_e_descartada():
    r = gptw.normalizar_resposta({"ano": 2026, "respostas": {999: 5, 1: 4}})
    assert r["respostas"] == {1: 4}


def test_envio_sem_respostas_e_none():
    assert gptw.normalizar_resposta({"ano": 2026, "respostas": {}}) is None
    assert gptw.normalizar_resposta({"ano": 2026, "abertas": {1: "oi"}}) is None


def test_ano_invalido_e_none():
    assert gptw.normalizar_resposta({"ano": 1500, "respostas": {1: 5}}) is None
    assert gptw.normalizar_resposta({"respostas": {1: 5}}) is None


def test_modelo_de_trabalho_validado():
    r = gptw.normalizar_resposta({"ano": 2026, "respostas": {1: 5}, "modelo": "lua"})
    assert r["modelo"] == ""
    r2 = gptw.normalizar_resposta({"ano": 2026, "respostas": {1: 5}, "modelo": "campo"})
    assert r2["modelo"] == "campo"


# ---------------------------------------------------------------------------
# PTI
# ---------------------------------------------------------------------------
def test_gti_e_percentual_de_positivas():
    # 3 respostas: valores 5,4,2 → positivas 2 de 3 válidas = 67%
    r = gptw.normalizar_overlay([{"id": "a", "ano": 2026,
        "respostas": {1: 5, 2: 4, 3: 2}}])
    assert gptw.gti(r)["gti"] == 67


def test_gti_sem_respostas_e_none():
    assert gptw.gti([])["gti"] is None


def test_gti_por_pilar_isola_as_afirmacoes():
    # Credibilidade toda 5 (positiva); resto toda 1 (negativa).
    cred = {a[0] for a in gptw.AFIRMACOES if a[1] == "credibilidade"}
    respostas = {aid: (5 if aid in cred else 1) for aid, *_ in gptw.AFIRMACOES}
    r = gptw.normalizar_overlay([{"id": "a", "ano": 2026, "respostas": respostas}])
    porp = {p["codigo"]: p["gti"] for p in gptw.gti_por_pilar(r)}
    assert porp["credibilidade"] == 100
    assert porp["respeito"] == 0


def test_maturidade_segue_as_faixas():
    assert gptw.maturidade(95)["codigo"] == "excelencia"
    assert gptw.maturidade(80)["codigo"] == "alto"
    assert gptw.maturidade(65)["codigo"] == "desenvolvimento"
    assert gptw.maturidade(50)["codigo"] == "alerta"
    assert gptw.maturidade(30)["codigo"] == "critico"
    assert gptw.maturidade(None)["codigo"] == ""


# ---------------------------------------------------------------------------
# Piso de 5 — a guarda de anonimato
# ---------------------------------------------------------------------------
def test_estrato_com_menos_de_cinco_nao_publica():
    resp = gptw.normalizar_overlay(
        [_resp(i, vinculo="clt") for i in range(6)]      # 6 CLT — publica
        + [_resp(100 + i, vinculo="pj") for i in range(3)])  # 3 PJ — oculta
    pe = gptw.por_estrato(resp, "vinculo")
    chaves = {g["chave"] for g in pe["grupos"]}
    assert "clt" in chaves and "pj" not in chaves
    assert pe["ocultos"] == 1 and pe["respostas_ocultas"] == 3


def test_comentarios_so_com_piso():
    poucos = gptw.normalizar_overlay(
        [{"id": f"r{i}", "ano": 2026, "respostas": {1: 5}, "abertas": {1: "bom"}}
         for i in range(3)])
    assert gptw.comentarios(poucos, 1) == []            # 3 < piso
    muitos = gptw.normalizar_overlay(
        [{"id": f"r{i}", "ano": 2026, "respostas": {1: 5}, "abertas": {1: "bom"}}
         for i in range(5)])
    assert len(gptw.comentarios(muitos, 1)) == 5


# ---------------------------------------------------------------------------
# eNPS e participação
# ---------------------------------------------------------------------------
def test_enps_proxy_da_afirmacao_40():
    resp = gptw.normalizar_overlay(
        [{"id": f"p{i}", "ano": 2026, "respostas": {40: 5}} for i in range(7)]   # promotores
        + [{"id": f"d{i}", "ano": 2026, "respostas": {40: 2}} for i in range(3)])  # detratores
    e = gptw.enps(resp)
    assert e["promotores"] == 7 and e["detratores"] == 3
    assert e["enps"] == 40           # 70% - 30%


def test_participacao_sobre_a_base():
    resp = gptw.normalizar_overlay([_resp(i) for i in range(10)])
    p = gptw.participacao(resp, 100)
    assert p["respostas"] == 10 and p["pct"] == 10 and not p["atingiu"]
    assert p["faltam"] == 60         # 70% de 100 = 70; faltam 60


# ---------------------------------------------------------------------------
# Estratos derivados do organograma
# ---------------------------------------------------------------------------
def test_estrato_deriva_da_unidade_sem_identidade():
    u = Unidade(id="a", codigo="a", nome="Ana", tipo="celula", parent_id="r",
                ordem=0, area="Engenharia", vinculo="clt", data_inicio="2022-01-01")
    e = gptw.estrato_de(u)
    assert e["nivel"] == "celula" and e["area"] == "Engenharia"
    assert e["vinculo"] == "clt" and e["faixa"]        # faixa resolvida
    assert "nome" not in e and "id" not in e


# ---------------------------------------------------------------------------
# Fusão overlay + banco — sem contar em dobro
# ---------------------------------------------------------------------------
def test_fundir_nao_duplica_por_id():
    overlay = [{"id": "r1", "ano": 2026, "respostas": {1: 5}}]
    banco = [{"id": "r1", "ano": 2026, "respostas": {1: 5}},   # mesma — já espelhada
             {"id": "r2", "ano": 2026, "respostas": {1: 4}}]   # só no banco
    fund = gptw.fundir(overlay, banco)
    assert len({r["id"] for r in fund}) == 2


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def estado_isolado(tmp_path):
    main.ARQUIVO_ESTADO = tmp_path / "estado.json"
    main.semear(spec=True)
    main.ESTADO.config.gptw_respostas = []
    main.ESTADO.config.gptw_programacao = {}
    main.ESTADO.config.perfil = ADMIN
    main.ESTADO.historico.clear()
    yield


@pytest.fixture
def cli():
    return TestClient(main.app)


def test_a_vista_esta_na_barra_do_topo(cli):
    r = cli.get("/?vista=gptw")
    assert r.status_code == 200 and "Peoples Place to Work" in r.text


def test_cada_secao_do_modulo_responde(cli):
    for secao in main.SECOES_GPTW:
        r = cli.get(f"/vistas/gptw?aba={secao}")
        assert r.status_code == 200, secao


def test_aba_invalida_cai_na_primeira_e_nao_em_erro(cli):
    assert cli.get("/vistas/gptw?aba=inventada").status_code == 200


def test_questionario_serve_as_afirmacoes(cli):
    r = cli.get("/gptw/responder")
    assert r.status_code == 200
    assert "Meu gestor direto comunica" in r.text     # afirmação 1


def test_pulso_traz_menos_afirmacoes(cli):
    completo = cli.get("/gptw/responder?ciclo=anual").text
    pulso = cli.get("/gptw/responder?ciclo=pulso").text
    assert completo.count('class="gptw-af"') == 60    # uma por afirmação
    assert pulso.count('class="gptw-af"') == 15


def test_enviar_grava_resposta_anonima(cli):
    dados = {"ciclo": "anual", "ano": "2026", "modelo": "hibrido"}
    for aid, *_ in gptw.AFIRMACOES:
        dados[f"af_{aid}"] = "5"
    r = cli.post("/gptw/responder", data=dados)
    assert r.status_code == 200
    resp = main.ESTADO.config.gptw_respostas
    assert len(resp) == 1
    # anonimato: nenhuma chave de identidade
    assert "ref" not in resp[0] and "usuario_id" not in resp[0]
    assert resp[0]["respostas"].get(1) == 5


def test_enviar_sem_resposta_nao_grava(cli):
    r = cli.post("/gptw/responder", data={"ciclo": "anual", "ano": "2026"})
    assert r.status_code == 200
    assert main.ESTADO.config.gptw_respostas == []


def test_painel_mostra_gti_apos_respostas(cli):
    for _ in range(6):
        dados = {"ciclo": "anual", "ano": "2026", "modelo": "hibrido"}
        for aid, *_ in gptw.AFIRMACOES:
            dados[f"af_{aid}"] = "5"
        cli.post("/gptw/responder", data=dados)
    r = cli.get("/vistas/gptw?aba=painel")
    assert r.status_code == 200 and "100" in r.text     # PTI 100%


def test_csv_tem_cabecalho_de_contrato(cli):
    r = cli.get("/gptw.csv")
    assert r.status_code == 200
    cab = r.text.splitlines()[0]
    assert "pilar;afirmacao;gti" in cab


def test_todas_as_vistas_renderizam_em_pt(cli):
    r = cli.get("/?vista=gptw")
    assert '<html lang="pt-BR"' in r.text


# ---------------------------------------------------------------------------
# Programação da pesquisa + notificação (envio a configurar)
# ---------------------------------------------------------------------------
def test_secao_programar_serve(cli):
    r = cli.get("/vistas/gptw?aba=programar")
    assert r.status_code == 200 and "Programar" in r.text


def test_programar_salva_e_marca_email_pendente(cli):
    r = cli.post("/gptw/programar", data={
        "ciclo": "anual", "abertura": "2026-03-01",
        "fechamento": "2026-03-20", "notificar": "1"})
    assert r.status_code == 200
    prog = main.ESTADO.config.gptw_programacao
    assert prog["status"] == "programada" and prog["ciclo"] == "anual"
    assert prog["abertura"] == "2026-03-01" and prog["notificar"] is True
    assert "programada" in r.text.lower()


def test_notificar_prepara_mas_nao_envia():
    n = gptw.notificar({"a": None} and {}, {"ciclo": "anual"})  # sem unidades
    assert n["enviados"] == 0 and n["pendente"] is True


def test_programar_entra_no_desfazer(cli):
    cli.post("/gptw/programar", data={"ciclo": "pulso", "notificar": "1"})
    assert main.ESTADO.config.gptw_programacao["status"] == "programada"
    cli.post("/desfazer")
    p = main.ESTADO.config.gptw_programacao
    assert p == {} or p.get("status") != "programada"


# ---------------------------------------------------------------------------
# Botões: um único seletor de ciclo (o duplicado do questionário sumiu)
# ---------------------------------------------------------------------------
def test_responder_sem_ciclo_duplicado(cli):
    html = cli.get("/gptw/responder").text
    assert 'name="__ciclo"' not in html          # o toggle duplicado (bugado) sumiu
    assert "gptw-resp-selo" in html               # virou selo de leitura


def test_pulso_pelo_seletor_do_topo_reduz_afirmacoes(cli):
    # o seletor de ciclo do topo (aba) troca o questionário — a função corrigida
    pulso = cli.get("/vistas/gptw?aba=responder&ciclo=pulso").text
    anual = cli.get("/vistas/gptw?aba=responder&ciclo=anual").text
    assert pulso.count('class="gptw-af"') == 15
    assert anual.count('class="gptw-af"') == 60
