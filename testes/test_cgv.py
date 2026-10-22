"""
Conversa de Valor — Conversas que Geram Valor.

O motor é puro como `dcr.py` e `tempo.py`: recebe unidades, devolve dicionários,
roda sem servidor. A agenda deriva de quem-lidera-quem; o acompanhamento é a
camada editável, com ANO na chave para o histórico atravessar os anos.

    pytest testes/test_cgv.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import cgv                                                      # noqa: E402
from orga import dcr                                                      # noqa: E402
from orga import main                                                     # noqa: E402
from orga.configuracao import ADMIN, VIEWER                               # noqa: E402
from orga.dominio import Unidade                                          # noqa: E402


def _p(uid, nome, pai, cargo, tipo="celula"):
    return Unidade(id=uid, codigo=uid, nome=nome, tipo=tipo, parent_id=pai,
                   ordem=0, cargo=cargo, area="Eng", centro_custo="80.31")


def _base():
    """Raiz + gerente + coordenador + dois analistas."""
    return {u.id: u for u in [
        Unidade(id="R", codigo="ORG-RAIZ", nome="Board", tipo="diretoria",
                parent_id=None, ordem=0),
        _p("g", "Gina", "R", "Gerente", tipo="gerencia"),
        _p("c", "Caio", "g", "Coordenador", tipo="coordenacao"),
        _p("a", "Ana", "c", "Analista"),
        _p("b", "Bia", "c", "Analista"),
    ]}


def _linhas(unidades=None):
    return dcr.medir(unidades or _base())


# ---------------------------------------------------------------------------
# Agenda — derivada da árvore
# ---------------------------------------------------------------------------
def test_agenda_tem_uma_linha_por_pessoa_com_o_lider():
    ag = cgv.agenda(_linhas(), ano=2026)
    porref = {a["ref"]: a for a in ag}
    # Ana e Bia reportam a Caio; Caio a Gina; Gina à raiz (sem líder pessoa).
    assert porref["a"]["lider_nome"] == "Caio"
    assert porref["c"]["lider_nome"] == "Gina"
    assert porref["g"]["lider_nome"] == ""      # a raiz não é gente


def test_agenda_comeca_todos_pendentes_sem_overlay():
    ag = cgv.agenda(_linhas(), ano=2026)
    assert all(s == "pendente" for a in ag for s in a["ciclos"].values())
    assert all(a["realizadas"] == 0 for a in ag)


def test_ref_prefere_a_matricula():
    linha = {"id": "u1", "codigo": "SAP-9", "nome": "x", "parent_id": None}
    assert cgv.ref_de(linha) == "SAP-9"
    assert cgv.ref_de({"id": "u1", "codigo": "", "parent_id": None}) == "u:u1"


# ---------------------------------------------------------------------------
# Overlay — chave (ref, ano, ciclo), e o ano é o que faz o histórico
# ---------------------------------------------------------------------------
def test_normalizar_descarta_o_padrao_e_o_invalido():
    bruto = [
        {"ref": "a", "ano": 2026, "ciclo": "completa", "status": "realizada",
         "data": "2026-03-10", "nota": "ok"},
        {"ref": "a", "ano": 2026, "ciclo": "checkin1", "status": "pendente"},  # padrão
        {"ref": "a", "ano": 1500, "ciclo": "completa", "status": "realizada"},  # ano fora
        {"ref": "", "ano": 2026, "ciclo": "completa", "status": "realizada"},   # sem ref
        {"ref": "a", "ano": 2026, "ciclo": "inexistente", "status": "realizada"},
    ]
    reg = cgv.normalizar_overlay(bruto)
    assert len(reg) == 1
    assert reg[0]["ref"] == "a" and reg[0]["ciclo"] == "completa"


def test_o_ano_faz_registros_coexistirem():
    reg = cgv.normalizar_overlay([
        {"ref": "a", "ano": 2026, "ciclo": "completa", "status": "realizada", "data": "2026-03-01"},
        {"ref": "a", "ano": 2025, "ciclo": "completa", "status": "realizada", "data": "2025-03-01"},
    ])
    assert len(reg) == 2                      # não sobrescreve


def test_status_invalido_vira_padrao():
    reg = cgv.normalizar_overlay([
        {"ref": "a", "ano": 2026, "ciclo": "completa", "status": "inventado", "nota": "x"}])
    assert reg[0]["status"] == "pendente"


# ---------------------------------------------------------------------------
# Histórico — só realizadas, anos anteriores
# ---------------------------------------------------------------------------
def test_historico_traz_so_realizadas_de_anos_anteriores():
    overlay = cgv.normalizar_overlay([
        {"ref": "a", "ano": 2026, "ciclo": "completa", "status": "realizada", "data": "2026-03-01"},
        {"ref": "a", "ano": 2025, "ciclo": "completa", "status": "realizada", "data": "2025-03-01"},
        {"ref": "a", "ano": 2025, "ciclo": "checkin1", "status": "agendada"},  # não realizada
        {"ref": "a", "ano": 2024, "ciclo": "checkin2", "status": "realizada", "data": "2024-11-01"},
    ])
    hist = cgv.historico("a", overlay, exceto_ano=2026)
    anos = [h["ano"] for h in hist]
    assert anos == [2025, 2024]                # desc, e sem 2026
    assert len(hist[0]["conversas"]) == 1      # a agendada de 2025 não entra


def test_ficha_reune_ciclos_do_ano_e_historico():
    overlay = cgv.normalizar_overlay([
        {"ref": "a", "ano": 2026, "ciclo": "completa", "status": "realizada", "data": "2026-03-01"},
        {"ref": "a", "ano": 2025, "ciclo": "completa", "status": "realizada", "data": "2025-03-01"},
    ])
    f = cgv.ficha("a", _linhas(), overlay, ano=2026)
    assert f["nome"] == "Ana" and f["lider_nome"] == "Caio"
    assert [c["status"] for c in f["ciclos"]] == ["realizada", "pendente", "pendente"]
    assert [h["ano"] for h in f["historico"]] == [2025]


def test_ficha_de_matricula_ausente_e_none():
    assert cgv.ficha("fantasma", _linhas(), []) is None


# ---------------------------------------------------------------------------
# Resumo e por-líder
# ---------------------------------------------------------------------------
def test_resumo_conta_previstas_e_realizadas():
    overlay = cgv.normalizar_overlay([
        {"ref": "a", "ano": 2026, "ciclo": "completa", "status": "realizada", "data": "2026-03-01"}])
    ag = cgv.agenda(_linhas(), overlay, ano=2026)
    r = cgv.resumo(ag)
    assert r["pessoas"] == 4 and r["previstas"] == 12   # 4 pessoas × 3 ciclos
    assert r["realizadas"] == 1
    assert r["por_ciclo"][0]["realizadas"] == 1


def test_por_lider_enrola_a_agenda():
    ag = cgv.agenda(_linhas(), ano=2026)
    grupos = {g["nome"]: g for g in cgv.por_lider(ag)}
    assert grupos["Caio"]["liderados"] == 2 and grupos["Caio"]["conversas"] == 6


# ---------------------------------------------------------------------------
# Fusão overlay + banco
# ---------------------------------------------------------------------------
def test_fundir_o_overlay_vence_e_o_banco_preenche_anos():
    overlay = [{"ref": "a", "ano": 2026, "ciclo": "completa",
                "status": "realizada", "data": "2026-03-15", "nota": "novo"}]
    banco = [
        {"ref": "a", "ano": 2026, "ciclo": "completa", "status": "realizada",
         "data": "2026-03-01", "nota": "antigo do banco"},          # perde p/ overlay
        {"ref": "a", "ano": 2024, "ciclo": "completa", "status": "realizada",
         "data": "2024-03-01", "nota": "só no banco"},              # entra
    ]
    fund = cgv.fundir(overlay, banco)
    por = {(r["ref"], r["ano"], r["ciclo"]): r for r in fund}
    assert por[("a", 2026, "completa")]["nota"] == "novo"           # overlay venceu
    assert por[("a", 2024, "completa")]["nota"] == "só no banco"    # banco preencheu


def test_markdown_tem_colaborador_ciclos_e_trio():
    f = cgv.ficha("a", _linhas(), [], ano=2026)
    md = cgv.markdown(f)
    assert "Ana" in md and "TEAMWORK" in md and "Conversa de Valor Completa" in md


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def estado_isolado(tmp_path):
    main.ARQUIVO_ESTADO = tmp_path / "estado.json"
    main.semear(spec=True)
    main.ESTADO.config.cgv_registros = []
    main.ESTADO.config.perfil = ADMIN
    main.ESTADO.historico.clear()
    yield


@pytest.fixture
def cli():
    return TestClient(main.app)


def _um_ref() -> str:
    linhas = dcr.medir(main.ESTADO.unidades, main.mapa_cc())
    return cgv.agenda(linhas)[0]["ref"]


def test_a_vista_esta_na_barra_do_topo(cli):
    r = cli.get("/?vista=cgv")
    assert r.status_code == 200 and "Conversa de Valor" in r.text


def test_cada_secao_do_modulo_responde(cli):
    for secao in cgv_secoes():
        r = cli.get(f"/vistas/cgv?aba={secao}")
        assert r.status_code == 200, secao


def cgv_secoes():
    return main.SECOES_CGV


def test_aba_invalida_cai_na_primeira_e_nao_em_erro(cli):
    r = cli.get("/vistas/cgv?aba=inventada")
    assert r.status_code == 200


def test_ficha_abre_com_os_tres_ciclos(cli):
    r = cli.get(f"/cgv/ficha/{_um_ref()}")
    assert r.status_code == 200 and "Check-in" in r.text


def test_ficha_de_matricula_ausente_responde_200_com_aviso(cli):
    r = cli.get("/cgv/ficha/nao-existe")
    assert r.status_code == 200 and "fora do recorte" in r.text


def test_gravar_ciclo_persiste_o_formulario_inteiro(cli):
    ref = _um_ref()
    eventos = len(main.ESTADO.eventos)
    r = cli.post(f"/cgv/ficha/{ref}/completa", data={
        "ano": "2026", "status": "realizada", "data": "2026-03-20",
        "entregas": "Entregou o projeto no prazo.",
        "val_teamwork": "Colabora bem.", "val_innovation": "Trouxe ideia nova.",
        "pdi1_comp": "Inglês", "pdi1_acao": "70/20/10", "pdi1_prazo": "dez",
        "carreira": "Quer ser especialista."})
    assert r.status_code == 200
    reg = cgv.registro_de(ref, 2026, "completa", main.ESTADO.config.cgv_registros)
    assert reg["status"] == "realizada"
    c = reg["conteudo"]
    assert c["entregas"] == "Entregou o projeto no prazo."
    assert c["valores"]["teamwork"] == "Colabora bem."
    assert c["pdi"][0]["comp"] == "Inglês" and c["pdi"][0]["prazo"] == "dez"
    assert c["carreira"] == "Quer ser especialista."
    assert len(main.ESTADO.eventos) == eventos + 1
    assert "Conversa de Valor de" in main.ESTADO.eventos[-1]["motivo"]


def test_gravar_um_ciclo_nao_apaga_os_outros(cli):
    ref = _um_ref()
    cli.post(f"/cgv/ficha/{ref}/completa", data={"ano": "2026", "status": "realizada"})
    cli.post(f"/cgv/ficha/{ref}/checkin1", data={"ano": "2026", "status": "agendada"})
    assert cgv.registro_de(ref, 2026, "completa", main.ESTADO.config.cgv_registros)["status"] == "realizada"
    assert cgv.registro_de(ref, 2026, "checkin1", main.ESTADO.config.cgv_registros)["status"] == "agendada"


def test_gravar_entra_no_desfazer(cli):
    ref = _um_ref()
    cli.post(f"/cgv/ficha/{ref}/completa", data={
        "ano": "2026", "status": "realizada", "data": "2026-03-20"})
    cli.post("/desfazer")
    reg = cgv.registro_de(ref, 2026, "completa", main.ESTADO.config.cgv_registros)
    assert reg["status"] == "pendente"


def test_ciclo_invalido_e_404(cli):
    assert cli.post(f"/cgv/ficha/{_um_ref()}/inventado",
                    data={"ano": "2026"}).status_code == 404


def test_visualizador_nao_grava(cli):
    ref = _um_ref()
    main.ESTADO.config.perfil = VIEWER
    r = cli.post(f"/cgv/ficha/{ref}/completa", data={
        "ano": "2026", "status": "realizada"})
    assert r.status_code == 200
    assert main.ESTADO.config.cgv_registros == []


def test_csv_tem_cabecalho_de_contrato(cli):
    r = cli.get("/cgv.csv")
    assert r.status_code == 200
    cabecalho = r.text.splitlines()[0]
    assert "ref;colaborador;cargo" in cabecalho and "realizadas;ano" in cabecalho


def test_pdf_sai_no_formulario_controlado(cli):
    r = cli.get(f"/cgv/ficha/{_um_ref()}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_pdf_de_matricula_ausente_e_404(cli):
    assert cli.get("/cgv/ficha/nao-existe/pdf").status_code == 404


def test_manual_e_modelos_servem(cli):
    # O manual em PDF e os formulários .xlsx são documentos internos e não
    # acompanham o repositório público; a rota responde 404 sem eles.
    cgv = RAIZ_PROJETO / "docs" / "CGV"
    if not (cgv / "Manual_Feedback_CGV_rev2026.pdf").exists():
        pytest.skip("manual e formulários da Conversa de Valor não versionados")
    assert cli.get("/cgv/manual").status_code == 200
    assert cli.get("/cgv/modelo/equipe").status_code == 200
    assert cli.get("/cgv/modelo/lideranca").status_code == 200
    assert cli.get("/cgv/modelo/inventado").status_code == 404


def test_passo_a_passo_interativo_serve(cli):
    r = cli.get("/cgv/interativo")
    assert r.status_code == 200 and "Conversas que" in r.text


def test_filtrar_de_dentro_do_cgv_devolve_o_corpo_do_cgv(cli):
    r = cli.post("/filtros?vista=cgv", data={"texto": "Ana"})
    assert r.status_code == 200
