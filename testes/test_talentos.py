"""
Avaliação — GEP-FOR-004.

O motor é puro como `dcr.py`, `cgv.py` e `tempo.py`: recebe unidades, devolve
dicionários, roda sem servidor. A base deriva do organograma (cargo, líder,
tempo de casa); a leitura de sucessão é a camada editável, com ANO na chave. O
9-box cruza risco × impacto de perda.

    pytest testes/test_talentos.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

import pytest                                                            # noqa: E402
from fastapi.testclient import TestClient                                # noqa: E402

from orga import dcr                                                      # noqa: E402
from orga import main                                                     # noqa: E402
from orga import talentos                                                 # noqa: E402
from orga.configuracao import ADMIN, VIEWER                               # noqa: E402
from orga.dominio import Unidade                                          # noqa: E402


def _p(uid, nome, pai, cargo, tipo="celula", inicio="2020-01-01"):
    return Unidade(id=uid, codigo=uid, nome=nome, tipo=tipo, parent_id=pai,
                   ordem=0, cargo=cargo, area="Eng", centro_custo="80.31",
                   data_inicio=inicio)


def _base():
    """Raiz + gerente + coordenador + dois analistas."""
    return {u.id: u for u in [
        Unidade(id="R", codigo="ORG-RAIZ", nome="Board", tipo="diretoria",
                parent_id=None, ordem=0),
        _p("g", "Gina", "R", "Gerente", tipo="gerencia", inicio="2015-01-01"),
        _p("c", "Caio", "g", "Coordenador", tipo="coordenacao", inicio="2018-06-01"),
        _p("a", "Ana", "c", "Analista", inicio="2022-03-01"),
        _p("b", "Bia", "c", "Analista", inicio="2024-09-01"),
    ]}


def _linhas(unidades=None):
    return talentos.medir(unidades or _base())


# ---------------------------------------------------------------------------
# Derivação — a base sai da estrutura, com tempo de casa
# ---------------------------------------------------------------------------
def test_medir_traz_tempo_de_casa_por_pessoa():
    linhas = _linhas()
    porref = {talentos.ref_de(l): l for l in linhas}
    # Gina (2015) tem mais anos de casa que Bia (2024).
    assert porref["g"]["anos_casa"] > porref["b"]["anos_casa"]
    assert porref["a"]["faixa_casa"]           # a faixa foi resolvida


def test_ref_prefere_a_matricula():
    linha = {"id": "u1", "codigo": "SAP-9", "nome": "x", "parent_id": None}
    assert talentos.ref_de(linha) == "SAP-9"
    assert talentos.ref_de({"id": "u1", "codigo": "", "parent_id": None}) == "u:u1"


def test_agenda_uma_linha_por_pessoa_com_o_lider():
    ag = talentos.agenda(_linhas(), ano=2026)
    porref = {a["ref"]: a for a in ag}
    assert porref["a"]["lider_nome"] == "Caio"
    assert porref["c"]["lider_nome"] == "Gina"
    assert porref["g"]["lider_nome"] == ""      # a raiz não é gente


def test_agenda_comeca_sem_classificacao_sem_overlay():
    ag = talentos.agenda(_linhas(), ano=2026)
    assert all(not a["mapeado"] for a in ag)
    assert all(a["risco_perda"] == "" for a in ag)


# ---------------------------------------------------------------------------
# Overlay — chave (ref, ano); enums validados; texto no limite
# ---------------------------------------------------------------------------
def test_normalizar_descarta_o_vazio_e_o_invalido():
    bruto = [
        {"ref": "a", "ano": 2026, "risco_perda": "alto", "impacto_perda": "alto"},
        {"ref": "b", "ano": 2026},                                   # sem sinal
        {"ref": "c", "ano": 1500, "risco_perda": "alto"},            # ano fora
        {"ref": "", "ano": 2026, "risco_perda": "alto"},             # sem ref
    ]
    reg = talentos.normalizar_overlay(bruto)
    assert len(reg) == 1 and reg[0]["ref"] == "a"


def test_enum_fora_da_lista_vira_vazio():
    reg = talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026, "risco_perda": "altissimo",
         "prontidao": "amanha", "acao": "demissao", "impacto_perda": "medio"}])
    assert reg[0]["risco_perda"] == ""          # inválido caiu
    assert reg[0]["impacto_perda"] == "medio"   # válido ficou
    assert reg[0]["prontidao"] == "" and reg[0]["acao"] == ""


def test_o_ano_faz_registros_coexistirem():
    reg = talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026, "risco_perda": "alto"},
        {"ref": "a", "ano": 2025, "risco_perda": "baixo"},
    ])
    assert len(reg) == 2                         # não sobrescreve


def test_texto_e_cortado_no_limite():
    reg = talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026, "conteudo": {"trajetoria": "x" * 9000}}])
    assert len(reg[0]["conteudo"]["trajetoria"]) == talentos.LIMITE_CAMPO


def test_conteudo_so_com_texto_persiste():
    reg = talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026, "conteudo": {"perfil": "Comunicativo."}}])
    assert len(reg) == 1 and reg[0]["conteudo"]["perfil"] == "Comunicativo."


def test_valores_trio_no_conteudo():
    reg = talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026,
         "conteudo": {"valores": {"teamwork": "Colabora."}}}])
    assert reg[0]["conteudo"]["valores"]["teamwork"] == "Colabora."


# ---------------------------------------------------------------------------
# 9-box — Risco × Impacto de perda
# ---------------------------------------------------------------------------
def _overlay_9box():
    return talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026, "risco_perda": "alto", "impacto_perda": "alto"},
        {"ref": "c", "ano": 2026, "risco_perda": "baixo", "impacto_perda": "alto"},
        {"ref": "g", "ano": 2026, "risco_perda": "medio", "impacto_perda": "medio"},
    ])


def test_nine_box_coloca_cada_um_na_celula_certa():
    ag = talentos.agenda(_linhas(), _overlay_9box(), ano=2026)
    nb = talentos.nine_box(ag)
    celulas = {(l["risco"], c["impacto"]): c
               for l in nb["grade"] for c in l["celulas"]}
    assert celulas[("alto", "alto")]["n"] == 1
    assert celulas[("alto", "alto")]["critica"] is True
    assert celulas[("baixo", "alto")]["n"] == 1
    assert nb["mapeados"] == 3 and nb["sem_classificar"] == 1   # Bia sem mapa


def test_nine_box_nomes_por_celula():
    ag = talentos.agenda(_linhas(), _overlay_9box(), ano=2026)
    nb = talentos.nine_box(ag)
    critica = next(c for l in nb["grade"] for c in l["celulas"] if c["critica"])
    assert critica["pessoas"][0]["nome"] == "Ana"


def test_prontidao_distribui_por_prazo():
    overlay = talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026, "prontidao": "agora"},
        {"ref": "c", "ano": 2026, "prontidao": "agora"},
        {"ref": "g", "ano": 2026, "prontidao": "2anos"},
    ])
    ag = talentos.agenda(_linhas(), overlay, ano=2026)
    dist = {p["codigo"]: p for p in talentos.prontidao(ag)}
    assert dist["agora"]["n"] == 2 and dist["2anos"]["n"] == 1


def test_por_acao_agrupa_indicados():
    overlay = talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026, "acao": "promocao"},
        {"ref": "c", "ano": 2026, "acao": "meritocracia"},
    ])
    ag = talentos.agenda(_linhas(), overlay, ano=2026)
    pa = talentos.por_acao(ag)
    assert len(pa["promocao"]["pessoas"]) == 1
    assert pa["promocao"]["pessoas"][0]["nome"] == "Ana"


def test_resumo_conta_mapeados_criticos_e_prontos():
    overlay = talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026, "risco_perda": "alto", "impacto_perda": "alto",
         "prontidao": "agora", "acao": "promocao"},
        {"ref": "c", "ano": 2026, "risco_perda": "baixo", "impacto_perda": "baixo"},
    ])
    ag = talentos.agenda(_linhas(), overlay, ano=2026)
    r = talentos.resumo(ag)
    assert r["pessoas"] == 4 and r["mapeados"] == 2
    assert r["criticos"] == 1 and r["prontos_agora"] == 1 and r["indicados"] == 1


# ---------------------------------------------------------------------------
# Ficha e markdown
# ---------------------------------------------------------------------------
def test_ficha_reune_derivado_e_editado():
    overlay = talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026, "risco_perda": "alto", "impacto_perda": "medio",
         "prontidao": "1ano", "acao": "meritocracia",
         "conteudo": {"idade": "29", "trajetoria": "Entrou como estagiária."}}])
    f = talentos.ficha("a", _linhas(), overlay, ano=2026)
    assert f["nome"] == "Ana" and f["lider_nome"] == "Caio"
    assert f["risco_perda"] == "alto" and f["prontidao"] == "1ano"
    assert f["conteudo"]["idade"] == "29"
    assert f["anos_casa"] is not None          # tempo de casa derivado


def test_ficha_de_matricula_ausente_e_none():
    assert talentos.ficha("fantasma", _linhas(), []) is None


def test_ficha_puxa_trio_e_pdi_do_cgv():
    """INT-1/INT-3: quando há Conversa de Valor, o Mapa exibe a aderência aos valores GPlanSiS e o PDI dela, em
    vez de reperguntar."""
    from orga import cgv
    cgv_reg = cgv.normalizar_overlay([{
        "ref": "a", "ano": 2026, "ciclo": "completa", "status": "realizada",
        "data": "2026-03-01",
        "conteudo": {"valores": {"teamwork": "Puxa a equipe."},
                     "pdi": [{"comp": "Inglês", "acao": "curso", "prazo": "dez"}]}}])
    f = talentos.ficha("a", _linhas(), [], ano=2026, cgv_registros=cgv_reg)
    assert f["cgv"]["tem"] is True
    assert f["cgv"]["valores"]["teamwork"] == "Puxa a equipe."
    assert f["cgv"]["pdi"][0]["comp"] == "Inglês"


def test_ficha_sem_cgv_nao_marca_puxado():
    f = talentos.ficha("a", _linhas(), [], ano=2026, cgv_registros=[])
    assert f["cgv"]["tem"] is False


def test_markdown_tem_colaborador_9box_e_trio():
    overlay = talentos.normalizar_overlay([
        {"ref": "a", "ano": 2026, "risco_perda": "alto", "impacto_perda": "alto"}])
    f = talentos.ficha("a", _linhas(), overlay, ano=2026)
    md = talentos.markdown(f)
    assert "Ana" in md and "TEAMWORK" in md and "Avaliação" in md


# ---------------------------------------------------------------------------
# Fusão overlay + banco
# ---------------------------------------------------------------------------
def test_fundir_o_overlay_vence_e_o_banco_preenche_anos():
    overlay = [{"ref": "a", "ano": 2026, "risco_perda": "alto",
                "impacto_perda": "alto"}]
    banco = [
        {"ref": "a", "ano": 2026, "risco_perda": "baixo",     # perde p/ overlay
         "impacto_perda": "baixo"},
        {"ref": "a", "ano": 2024, "risco_perda": "medio",     # entra
         "impacto_perda": "medio"},
    ]
    fund = talentos.fundir(overlay, banco)
    por = {(r["ref"], r["ano"]): r for r in fund}
    assert por[("a", 2026)]["risco_perda"] == "alto"          # overlay venceu
    assert por[("a", 2024)]["risco_perda"] == "medio"         # banco preencheu


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def estado_isolado(tmp_path):
    main.ARQUIVO_ESTADO = tmp_path / "estado.json"
    main.semear(spec=True)
    main.ESTADO.config.mapa_talentos = []
    main.ESTADO.config.perfil = ADMIN
    main.ESTADO.historico.clear()
    yield


@pytest.fixture
def cli():
    return TestClient(main.app)


def _ref_sistema() -> str:
    linhas = talentos.medir(main.ESTADO.unidades, main.mapa_cc())
    return talentos.agenda(linhas)[0]["ref"]


def test_a_vista_esta_na_barra_do_topo(cli):
    r = cli.get("/?vista=talentos")
    assert r.status_code == 200 and "Avaliação" in r.text


def test_cada_secao_do_modulo_responde(cli):
    for secao in main.SECOES_TALENTOS:
        r = cli.get(f"/vistas/talentos?aba={secao}")
        assert r.status_code == 200, secao


def test_aba_invalida_cai_na_primeira_e_nao_em_erro(cli):
    r = cli.get("/vistas/talentos?aba=inventada")
    assert r.status_code == 200


def test_ficha_abre_com_os_campos(cli):
    r = cli.get(f"/talentos/ficha/{_ref_sistema()}")
    assert r.status_code == 200 and "Avaliação" in r.text


def test_ficha_de_matricula_ausente_responde_200_com_aviso(cli):
    r = cli.get("/talentos/ficha/nao-existe")
    assert r.status_code == 200 and "fora do recorte" in r.text


def test_gravar_persiste_a_folha_inteira(cli):
    ref = _ref_sistema()
    eventos = len(main.ESTADO.eventos)
    r = cli.post(f"/talentos/ficha/{ref}", data={
        "ano": "2026", "risco_perda": "alto", "impacto_perda": "alto",
        "prontidao": "1ano", "acao": "promocao", "idade": "31",
        "trajetoria": "Entrou júnior, cresceu rápido.",
        "val_teamwork": "Puxa a equipe.", "ferramentas": "Power BI",
        "trilha_posicao": "Coordenação em 1 ano."})
    assert r.status_code == 200
    reg = talentos.registro_de(ref, 2026, main.ESTADO.config.mapa_talentos)
    assert reg["risco_perda"] == "alto" and reg["acao"] == "promocao"
    c = reg["conteudo"]
    assert c["idade"] == "31" and c["trajetoria"].startswith("Entrou júnior")
    assert c["valores"]["teamwork"] == "Puxa a equipe."
    assert len(main.ESTADO.eventos) == eventos + 1
    assert "Avaliação de" in main.ESTADO.eventos[-1]["motivo"]


def test_gravar_entra_no_desfazer(cli):
    ref = _ref_sistema()
    cli.post(f"/talentos/ficha/{ref}", data={
        "ano": "2026", "risco_perda": "alto", "impacto_perda": "alto"})
    cli.post("/desfazer")
    reg = talentos.registro_de(ref, 2026, main.ESTADO.config.mapa_talentos)
    assert reg["risco_perda"] == ""       # voltou ao não-classificado


def test_visualizador_nao_grava(cli):
    ref = _ref_sistema()
    main.ESTADO.config.perfil = VIEWER
    r = cli.post(f"/talentos/ficha/{ref}", data={
        "ano": "2026", "risco_perda": "alto", "impacto_perda": "alto"})
    assert r.status_code == 200
    assert main.ESTADO.config.mapa_talentos == []


def test_pessoa_muda_de_celula_no_9box_apos_gravar(cli):
    ref = _ref_sistema()
    cli.post(f"/talentos/ficha/{ref}", data={
        "ano": "2026", "risco_perda": "alto", "impacto_perda": "alto"})
    linhas = talentos.medir(main.ESTADO.unidades, main.mapa_cc())
    ag = talentos.agenda(linhas, main.registros_talentos(), 2026)
    nb = talentos.nine_box(ag)
    critica = next(c for l in nb["grade"] for c in l["celulas"] if c["critica"])
    assert ref in [p["ref"] for p in critica["pessoas"]]


def test_csv_tem_cabecalho_de_contrato(cli):
    r = cli.get("/talentos.csv")
    assert r.status_code == 200
    cabecalho = r.text.splitlines()[0]
    assert "ref;colaborador;cargo" in cabecalho
    assert "risco_perda;impacto_perda;prontidao;acao;ano" in cabecalho


def test_pdf_sai_no_formulario_controlado(cli):
    r = cli.get(f"/talentos/ficha/{_ref_sistema()}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_pdf_de_matricula_ausente_e_404(cli):
    assert cli.get("/talentos/ficha/nao-existe/pdf").status_code == 404


def test_filtrar_de_dentro_devolve_o_corpo_do_mapa(cli):
    r = cli.post("/filtros?vista=talentos", data={"texto": "a"})
    assert r.status_code == 200
