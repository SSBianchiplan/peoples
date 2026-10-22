"""
One-on-One — fundação (Onda 1B-1): modelo, persistência e SIGILO por pessoa.

A parte crítica é a ACL (LGPD, nível pessoa): um 1:1 é de duas pessoas — o
liderado (`ref`) e o líder que o escreveu (`lider_ref`), por matrícula. Ninguém
mais lê, exceto RH/compliance. Estes testes vêm primeiro e são adversariais: o
não-participante NÃO pode ver, o fail-closed vale, e o funil `visiveis()` nunca
vaza um registro de quem não é participante.

    pytest testes/test_onebyone.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

import pytest                                                            # noqa: E402
from fastapi.testclient import TestClient                                # noqa: E402

from orga import main                                                     # noqa: E402
from orga import onebyone as o                                           # noqa: E402
from orga.configuracao import ADMIN, VIEWER, Config                      # noqa: E402


def _conv(rid, ref, lider_ref, **c):
    return {"id": rid, "tipo": "conversa", "ref": ref, "lider_ref": lider_ref,
            "data": "2026-08-01", "conteudo": {"pauta": "pauta", **c}}


# --- SIGILO (a ACL, primeiro) -----------------------------------------------
def test_participante_ve_o_proprio_1a1():
    reg = _conv("a1", "M-LIDERADO", "M-LIDER")
    assert o.pode_ver(reg, "M-LIDERADO") is True
    assert o.pode_ver(reg, "M-LIDER") is True


def test_nao_participante_nao_ve():
    reg = _conv("a1", "M-LIDERADO", "M-LIDER")
    assert o.pode_ver(reg, "M-ESTRANHO") is False
    # nem um gestor de gestor (skip-level) — a matrícula dele não é participante
    assert o.pode_ver(reg, "M-SKIP") is False


def test_rh_compliance_ve_tudo():
    reg = _conv("a1", "M-LIDERADO", "M-LIDER")
    assert o.pode_ver(reg, "M-ESTRANHO", rh=True) is True


def test_fail_closed_sem_matricula_e_sem_rh():
    reg = _conv("a1", "M-LIDERADO", "M-LIDER")
    assert o.pode_ver(reg, "") is False
    assert o.pode_ver(reg, None or "") is False


def test_visiveis_nunca_vaza_registro_de_terceiro():
    overlay = [
        _conv("a1", "ANA", "GINA"),
        _conv("a2", "BIA", "GINA"),
        _conv("a3", "CAIO", "DIRETOR"),
    ]
    # A Ana só enxerga o dela; nada da Bia nem do Caio.
    so_ana = o.visiveis(overlay, "ANA")
    assert {r["id"] for r in so_ana} == {"a1"}
    # A Gina (líder de Ana e Bia) vê os dois 1:1 que conduziu, não o do Caio.
    gina = o.visiveis(overlay, "GINA")
    assert {r["id"] for r in gina} == {"a1", "a2"}
    # RH vê os três.
    assert len(o.visiveis(overlay, "QUALQUER", rh=True)) == 3


def test_participantes_sao_as_duas_matriculas():
    assert o.participantes(_conv("a", "X", "Y")) == {"X", "Y"}
    # líder ausente (externo/desligado): só o liderado é participante
    assert o.participantes(_conv("a", "X", "")) == {"X"}


# --- Normalização -----------------------------------------------------------
def test_overlay_dropa_tipo_invalido_e_sem_ref():
    n = o.normalizar_overlay([
        _conv("ok", "M1", "M2"),
        {"id": "x", "tipo": "inexistente", "ref": "M1"},
        {"id": "y", "tipo": "rock", "ref": "", "conteudo": {"titulo": "sem ref"}},
    ])
    assert {r["id"] for r in n} == {"ok"}


def test_overlay_dropa_registro_sem_sinal():
    # conversa sem data e sem conteúdo preenchido não persiste
    vazio = {"id": "v", "tipo": "conversa", "ref": "M1", "lider_ref": "M2",
             "conteudo": {}}
    assert o.normalizar_overlay([vazio]) == []


def test_conteudo_valida_enum_int_e_texto():
    n = o.normalizar_overlay([{
        "id": "r", "tipo": "rock", "ref": "M1", "ano": 2026, "trimestre": 3,
        "conteudo": {"titulo": "x" * 9000, "status": "invalido", "progresso": 500}}])
    c = n[0]["conteudo"]
    assert len(c["titulo"]) == o.LIMITE_CAMPO      # cortado no limite
    assert c["status"] == ""                       # enum inválido zera
    assert c["progresso"] == 100                   # inteiro preso à faixa


def test_trimestre_e_ano_saneados():
    n = o.normalizar_overlay([
        {"id": "a", "tipo": "rock", "ref": "M1", "ano": 1999, "conteudo": {"titulo": "t"}},
        {"id": "b", "tipo": "rock", "ref": "M1", "ano": 2026, "trimestre": 9,
         "conteudo": {"titulo": "t"}}])
    porid = {r["id"]: r for r in n}
    assert "a" not in porid                         # ano fora de 2000..2100 cai
    assert porid["b"]["trimestre"] == 0             # trimestre fora de 1..4 vira 0


# --- Config overlay ---------------------------------------------------------
def test_config_sanea_o_overlay_no_carregamento():
    c = Config()
    c.onebyone = [_conv("a1", "M1", "M2"), {"id": "x", "tipo": "lixo", "ref": "M9"}]
    recarregado = Config.de_dict(c.para_dict())
    assert {r["id"] for r in recarregado.onebyone} == {"a1"}


def test_campos_de_sessao_nao_persistem():
    from orga.configuracao import CAMPOS_SESSAO
    assert "ver_1a1_rh" in CAMPOS_SESSAO            # é efêmero, resolvido por login
    c = Config()
    c.ver_1a1_rh = True
    assert "ver_1a1_rh" not in c.para_persistir()   # não vaza para o estado durável


# --- Fusão overlay + banco --------------------------------------------------
def test_fundir_overlay_vence_no_conflito():
    banco = [_conv("a1", "M1", "M2", pauta="do banco")]
    overlay = [_conv("a1", "M1", "M2", pauta="editado agora")]
    fundido = o.fundir(overlay, banco)
    assert len(fundido) == 1
    assert fundido[0]["conteudo"]["pauta"] == "editado agora"


def test_fundir_banco_preenche_o_que_o_overlay_nao_tem():
    banco = [_conv("velho", "M1", "M2", pauta="ano passado")]
    overlay = [_conv("novo", "M1", "M2", pauta="agora")]
    assert {r["id"] for r in o.fundir(overlay, banco)} == {"velho", "novo"}


# --- Cadência (FUP) ---------------------------------------------------------
def test_proxima_data_soma_a_cadencia():
    assert o.proxima_data("2026-08-01", "semanal") == "2026-08-08"
    assert o.proxima_data("2026-08-01", "quinzenal") == "2026-08-15"
    assert o.proxima_data("", "semanal") == ""


def test_status_1a1_marca_atrasada():
    from datetime import date
    overlay = [{"id": "c", "tipo": "conversa", "ref": "M1", "lider_ref": "M2",
                "data": "2026-01-01", "conteudo": {"cadencia": "semanal"}}]
    st = o.status_1a1(overlay, "M1", date(2026, 8, 15))
    assert st["n"] == 1 and st["atrasada"] is True


# --- Rotas (app, estado isolado) --------------------------------------------
def test_onebyone_e_uma_aba(cli):
    r = cli.get("/?vista=onebyone")
    assert r.status_code == 200
    assert 'hx-get="/vistas/onebyone"' in r.text


def test_corpo_responde_e_traz_sigilo(cli):
    r = cli.get("/vistas/onebyone")
    assert r.status_code == 200
    assert "ob-sigilo" in r.text          # o aviso de sigilo aparece


def test_registrar_e_apagar_1a1_pela_rota(cli):
    # o admin (sou_rh) pode abrir a ficha de qualquer pessoa e registrar
    ref = _um_ref()
    r = cli.post(f"/onebyone/conversa/{ref}",
                 data={"data": "2026-08-10", "cadencia": "quinzenal",
                       "pauta": "Alinhamento", "notas": "ok",
                       "proximos_passos": "seguir", "sentimento": "4"})
    assert r.status_code == 200
    convs = [x for x in main.ESTADO.config.onebyone if x["tipo"] == "conversa"]
    assert len(convs) == 1 and convs[0]["ref"] == ref
    item_id = convs[0]["id"]
    # apagar
    a = cli.post(f"/onebyone/conversa/{ref}/apagar/{item_id}")
    assert a.status_code == 200
    assert not [x for x in main.ESTADO.config.onebyone if x["id"] == item_id]


def test_ficha_fora_do_sigilo_nao_vaza(cli):
    # rebaixa para um viewer sem vínculo: não é participante de ninguém
    main.ESTADO.config.perfil = VIEWER
    main.ESTADO.config.ver_1a1_rh = False
    main.ESTADO.config.usuario_id = "quem-nao-existe"
    r = cli.get(f"/onebyone/ficha/{_um_ref()}")
    assert r.status_code == 200
    assert "1:1 indispon" in r.text       # aviso, sem conteúdo


@pytest.fixture(autouse=True)
def _estado_onebyone(tmp_path):
    """Seed da SPEC, admin (superadmin vê tudo). Restaura perfil ao sair — um teste
    que rebaixa a VIEWER não pode deixar a sessão travada para o próximo arquivo."""
    perfil_antes = main.ESTADO.config.perfil
    rh_antes = main.ESTADO.config.ver_1a1_rh
    uid_antes = main.ESTADO.config.usuario_id
    main.ARQUIVO_ESTADO = tmp_path / "estado.json"
    main.semear(spec=True)
    main.ESTADO.config.perfil = ADMIN
    main.ESTADO.config.ver_1a1_rh = True
    main.ESTADO.config.onebyone = []
    main.ESTADO.historico.clear()
    yield
    main.ESTADO.config.perfil = perfil_antes
    main.ESTADO.config.ver_1a1_rh = rh_antes
    main.ESTADO.config.usuario_id = uid_antes


@pytest.fixture
def cli():
    return TestClient(main.app)


def _um_ref() -> str:
    linhas = o.base(main.ESTADO.unidades, main.mapa_cc())
    return o.ref_de(linhas[0])


# --- Rocks / Issues / Objetivo / Carreira (1B-3) ----------------------------
def test_trimestre_atual():
    from datetime import date
    assert o.trimestre_atual(date(2026, 2, 1)) == 1
    assert o.trimestre_atual(date(2026, 8, 15)) == 3
    assert o.trimestre_atual(date(2026, 12, 31)) == 4


def test_rocks_issues_objetivo_por_trimestre():
    overlay = [
        {"id": "r1", "tipo": "rock", "ref": "M1", "lider_ref": "M2", "ano": 2026,
         "trimestre": 3, "conteudo": {"titulo": "Rock A", "status": "on", "progresso": 50}},
        {"id": "r2", "tipo": "rock", "ref": "M1", "lider_ref": "M2", "ano": 2026,
         "trimestre": 2, "conteudo": {"titulo": "Rock velho", "status": "feito"}},
        {"id": "i1", "tipo": "issue", "ref": "M1", "lider_ref": "M2",
         "conteudo": {"titulo": "Issue X", "status": "aberto"}},
        {"id": "o1", "tipo": "objetivo", "ref": "M1", "lider_ref": "M2", "ano": 2026,
         "trimestre": 3, "conteudo": {"titulo": "Meta Q3", "status": "on"}},
    ]
    n = o.normalizar_overlay(overlay)
    assert [r["id"] for r in o.rocks(n, "M1", 2026, 3)] == ["r1"]     # só o do Q3
    assert o.objetivo(n, "M1", 2026, 3)["conteudo"]["titulo"] == "Meta Q3"
    assert len(o.issues(n, "M1")) == 1


def test_carreira_longo_prazo_e_trimestre_zero():
    overlay = o.normalizar_overlay([
        {"id": "c", "tipo": "objetivo", "ref": "M1", "lider_ref": "M2", "ano": 0,
         "trimestre": 0, "conteudo": {"titulo": "Ser diretor", "descricao": "plano"}}])
    car = o.carreira_longo_prazo(overlay, "M1")
    assert car and car["conteudo"]["titulo"] == "Ser diretor"


def test_campos_do_tipo_cobre_texto_int_enum():
    campos = o.campos_do_tipo("rock")
    assert "titulo" in campos and "progresso" in campos and "status" in campos


def test_salvar_rock_e_objetivo_pela_rota(cli):
    ref = _um_ref()
    r = cli.post(f"/onebyone/item/{ref}/rock",
                 data={"titulo": "Entregar X", "status": "on", "progresso": "30",
                       "ano": "2026", "trimestre": "3"})
    assert r.status_code == 200
    rocks = [x for x in main.ESTADO.config.onebyone if x["tipo"] == "rock"]
    assert len(rocks) == 1 and rocks[0]["conteudo"]["titulo"] == "Entregar X"
    # objetivo de carreira (trimestre 0)
    c = cli.post(f"/onebyone/item/{ref}/objetivo",
                 data={"titulo": "Ser líder", "descricao": "plano", "ano": "0", "trimestre": "0"})
    assert c.status_code == 200
    car = [x for x in main.ESTADO.config.onebyone
           if x["tipo"] == "objetivo" and x["trimestre"] == 0]
    assert len(car) == 1


def test_tipo_de_item_invalido_e_404(cli):
    r = cli.post(f"/onebyone/item/{_um_ref()}/inventado", data={"titulo": "x"})
    assert r.status_code == 404


# --- PRM: pulso, burnout, ciclo de vida (1B-4) ------------------------------
def test_ultimo_clima_prefere_pulso_recente():
    overlay = o.normalizar_overlay([
        {"id": "c", "tipo": "conversa", "ref": "M1", "lider_ref": "M2",
         "data": "2026-08-01", "conteudo": {"sentimento": 4}},
        {"id": "p", "tipo": "pulso", "ref": "M1", "lider_ref": "M2",
         "data": "2026-08-10", "conteudo": {"sentimento": 2, "energia": 3}}])
    assert o.ultimo_clima(overlay, "M1") == 2   # pulso mais recente vence


def test_burnout_span_alto_sozinho_nao_alerta():
    """Span alto NÃO é burnout por si: sem sinal de engajamento, não acende."""
    from datetime import date
    roster = [{"id": "n2", "codigo": "M2", "nome": "Beto", "cargo": "Gerente"}]
    filhos = {"n2": ["a", "b", "c", "d", "e", "f", "g", "h"]}   # span 8, sem pulso/1:1
    al = o.alertas_burnout(roster, filhos and [], filhos, date(2026, 8, 15))
    assert al == []


def test_burnout_clima_baixo_acende_e_span_agrava():
    from datetime import date
    # M1: clima baixo + span alto → dois sinais (clima baixo dispara, span agrava)
    roster = [{"id": "n1", "codigo": "M1", "nome": "Ana", "cargo": "Gerente"},
              {"id": "n2", "codigo": "M2", "nome": "Beto", "cargo": "Gerente"}]
    overlay = o.normalizar_overlay([
        {"id": "p", "tipo": "pulso", "ref": "M1", "lider_ref": "MX",
         "data": "2026-08-10", "conteudo": {"sentimento": 1}}])
    filhos = {"n1": list("abcdefgh"), "n2": list("abcdefgh")}   # ambos span 8
    al = o.alertas_burnout(roster, overlay, filhos, date(2026, 8, 15))
    porref = {a["ref"]: a for a in al}
    assert set(porref) == {"M1"}                    # só M1 (tem clima baixo)
    assert "clima baixo" in porref["M1"]["sinais"]
    assert "span alto" in porref["M1"]["sinais"]    # agravante, com o sinal de clima
    assert porref["M1"]["n"] == 2


def test_panorama_prm_agrega_clima_e_estagios():
    from datetime import date
    roster = [{"id": "n1", "codigo": "M1", "nome": "Ana", "cargo": "A"}]
    overlay = o.normalizar_overlay([
        {"id": "p", "tipo": "pulso", "ref": "M1", "lider_ref": "MX",
         "data": "2026-08-10", "conteudo": {"sentimento": 4}},
        {"id": "cv", "tipo": "ciclo", "ref": "M1", "lider_ref": "MX",
         "conteudo": {"estagio": "onboarding"}}])
    p = o.panorama_prm(roster, overlay, {}, date(2026, 8, 15))
    assert p["clima_medio"] == 4.0 and p["com_pulso"] == 1
    assert p["estagios"][0]["cod"] == "onboarding"
    assert p["span_alto"] == 0 and "limiar_span" in p   # contexto estrutural à parte


def test_secao_prm_responde(cli):
    r = cli.get("/vistas/onebyone?aba=prm")
    assert r.status_code == 200
    assert "Alertas de burnout" in r.text or "burnout" in r.text.lower()


def test_registrar_pulso_e_ciclo(cli):
    ref = _um_ref()
    p = cli.post(f"/onebyone/item/{ref}/pulso",
                 data={"data": "2026-08-12", "sentimento": "4", "energia": "3",
                       "comentario": "tranquilo"})
    assert p.status_code == 200
    assert [x for x in main.ESTADO.config.onebyone if x["tipo"] == "pulso"]
    c = cli.post(f"/onebyone/item/{ref}/ciclo", data={"estagio": "onboarding"})
    assert c.status_code == 200
    ciclos = [x for x in main.ESTADO.config.onebyone if x["tipo"] == "ciclo"]
    assert len(ciclos) == 1 and ciclos[0]["conteudo"]["estagio"] == "onboarding"


# --- Missões + ponte Conversa de Valor + GPlanSiS|OS (1B-5) ------------------------------------
def test_missoes_do_cgv_viram_rascunhos():
    cgv = [{"ref": "M1", "ano": 2026, "conteudo": {"pdi": [
        {"comp": "Liderança", "acao": "Mentoria", "prazo": "Q4"},
        {"comp": "", "acao": "", "prazo": ""}]}}]
    drafts = o.missoes_do_cgv("M1", cgv)
    assert len(drafts) == 1                          # o vazio não entra
    assert drafts[0]["titulo"] == "Liderança"
    assert drafts[0]["origem"] == o.ORIGEM_CGV and drafts[0]["status"] == "proposta"


def test_missoes_ordena_abertas_primeiro():
    overlay = o.normalizar_overlay([
        {"id": "m1", "tipo": "missao", "ref": "M1", "lider_ref": "M2",
         "conteudo": {"titulo": "Feita", "status": "concluida"}},
        {"id": "m2", "tipo": "missao", "ref": "M1", "lider_ref": "M2",
         "conteudo": {"titulo": "Nova", "status": "proposta"}}])
    assert [m["id"] for m in o.missoes(overlay, "M1")] == ["m2", "m1"]


def test_greyos_exporta_payload():
    from orga import greyos
    overlay = o.normalizar_overlay([
        {"id": "m1", "tipo": "missao", "ref": "M1", "lider_ref": "M2", "nome": "Ana",
         "conteudo": {"titulo": "Mentoria", "acao": "1h/sem", "status": "andamento",
                      "origem": "Conversa de Valor · PDI"}}])
    payload = greyos.exportar(overlay)
    assert payload["schema"] == "greyos.task" and payload["count"] == 1
    t0 = payload["tasks"][0]
    assert t0["external_id"] == "m1" and t0["title"] == "Mentoria"
    assert t0["owner_ref"] == "M1" and t0["source"] == "Conversa de Valor · PDI"
    assert greyos.configurado() is False            # integração viva ainda não existe


def test_gerar_missoes_do_cgv_pela_rota_nao_duplica(cli):
    ref = _um_ref()
    # planta um PDI na Conversa de Valor desta pessoa
    main.ESTADO.config.cgv_registros = [{
        "ref": ref, "ano": 2026, "ciclo": "completa", "status": "realizada",
        "conteudo": {"pdi": [{"comp": "Comunicação", "acao": "Curso", "prazo": "Q3"}]}}]
    r = cli.post(f"/onebyone/missoes-do-cgv/{ref}")
    assert r.status_code == 200
    miss = [x for x in main.ESTADO.config.onebyone if x["tipo"] == "missao"]
    assert len(miss) == 1 and miss[0]["conteudo"]["titulo"] == "Comunicação"
    # rodar de novo não duplica
    cli.post(f"/onebyone/missoes-do-cgv/{ref}")
    assert len([x for x in main.ESTADO.config.onebyone if x["tipo"] == "missao"]) == 1


def test_export_json_respeita_sigilo(cli):
    r = cli.get("/onebyone/export.json")
    assert r.status_code == 200
    body = r.json()
    assert body["schema"] == "greyos.task" and "tasks" in body
