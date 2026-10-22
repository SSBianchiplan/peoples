"""
MarIA — as sete capacidades e o recorte de quem pergunta.

Um assistente de IA não se testa pelo que responde: pelo que ele **não faz**.
Os dois riscos concretos são ver mais que quem perguntou e mutar sem alguém
autorizar. Cada um tem teste aqui, e nenhum depende da API estar configurada.

    pytest testes/test_maria.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import main                                                     # noqa: E402
from orga import maria                                                    # noqa: E402


@pytest.fixture()
def cli():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def estado_limpo():
    """Devolve a tela como estava.

    O recorte do canvas lê foco, colapso e filtro do ESTADO — três coisas que
    qualquer outro teste pode ter mexido. Sem restaurar, a ordem dos testes
    decide o resultado.
    """
    guarda = (main.ESTADO.foco, set(main.ESTADO.colapsados),
              dict(main.ESTADO.filtros))
    main.ESTADO.foco = None
    main.ESTADO.filtros = main.filtros_vazios()
    # O colapso também: um teste anterior que expande tudo faria o canvas
    # desenhar as 267 unidades, e "o recorte estreita" passaria a ser falso
    # por ordem de execução, não por defeito.
    main.ESTADO.colapsados = main.colapso_por_nivel(
        main.ESTADO.config.profundidade_aberta)
    yield
    main.ESTADO.foco, main.ESTADO.colapsados, main.ESTADO.filtros = (
        guarda[0], guarda[1], guarda[2])


# ---------------------------------------------------------------------------
# As sete capacidades
# ---------------------------------------------------------------------------
def test_a_tabela_tem_as_sete():
    assert len(maria.CAPACIDADES) == 7
    chaves = [c[0] for c in maria.CAPACIDADES]
    assert chaves == [maria.LER, maria.DESCREVER, maria.RELATAR, maria.ANALISAR,
                      maria.PLANEJAR, maria.EXECUTAR, maria.AUTONOMA]


@pytest.mark.parametrize("capacidade", [maria.LER, maria.DESCREVER,
                                        maria.RELATAR, maria.ANALISAR,
                                        maria.PLANEJAR])
def test_capacidades_1_a_5_estao_disponiveis(capacidade):
    assert maria.permitida(capacidade) is True


def test_agir_sozinha_continua_recusada():
    """Recusada no código, não desencorajada no prompt. Encadear ações sem
    parada humana entre elas é outra coisa, e não é esta."""
    assert maria.permitida(maria.AUTONOMA) is False
    r = maria.perguntar("faça isso", {}, capacidade=maria.AUTONOMA)
    assert r["ok"] is False and r["motivo"] == "capacidade_indisponivel"


def test_executar_existe_mas_so_pela_aprovacao():
    """A 6 passou a existir com o agente Organograma — e existe COM a autoridade
    que a tabela sempre exigiu. O que este teste garante é que não há atalho:
    criar unidade exige um POST separado que cita uma proposta já revisada."""
    assert maria.permitida(maria.EXECUTAR) is True
    rotas = {r.path for r in main.app.routes if hasattr(r, "path")}
    aplicar = [r for r in rotas if "agente" in r and "aplicar" in r]
    assert aplicar == ["/maria/agente/{pid}/aplicar"]
    # e a rota exige o identificador de uma proposta guardada
    assert "{pid}" in aplicar[0]


def test_capacidade_recusada_nem_chama_o_modelo(monkeypatch):
    """A recusa acontece antes da chamada — senão a API seria paga para
    devolver uma resposta que o sistema vai descartar."""
    chamou = []
    monkeypatch.setattr(maria, "configurada", lambda: True)
    monkeypatch.setattr(maria.urllib.request, "urlopen",
                        lambda *a, **k: chamou.append(1))
    maria.perguntar("x", {}, capacidade=maria.AUTONOMA)
    assert chamou == []


def test_aprovar_nao_chama_o_modelo_de_novo(monkeypatch):
    """A pessoa aprova a lista que leu.

    Se a aprovação gerasse a estrutura outra vez, ela estaria aprovando um
    texto e o sistema criando outro — que é o modo mais silencioso de o
    consentimento não valer nada.
    """
    chamou = []
    monkeypatch.setattr(maria, "configurada", lambda: True)
    monkeypatch.setattr(maria.urllib.request, "urlopen",
                        lambda *a, **k: chamou.append(1))

    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        antes = dict(main.ESTADO.propostas)
        nivel = next(iter(main.ESTADO.config.rotulos_nivel))
        pai = next(iter(main.ESTADO.unidades.values()))
        try:
            main.ESTADO.propostas["p1"] = {
                "id": "p1", "time": "Growth", "departamento": "Growth",
                "sob": pai.nome, "observacoes": "", "problemas": [],
                "unidades": [{"cargo": "Analista de Growth", "nivel": nivel,
                              "quantidade": 2}], "total": 2, "pedido": "x"}
            quantas = len(main.ESTADO.unidades)
            c.post("/maria/agente/p1/aplicar")
            assert len(main.ESTADO.unidades) == quantas + 2
            assert chamou == [], "a aprovação chamou o modelo de novo"
            assert "p1" not in main.ESTADO.propostas
        finally:
            main.ESTADO.propostas = antes


def test_aplicar_proposta_inexistente_nao_cria_nada(cli):
    quantas = len(main.ESTADO.unidades)
    r = cli.post("/maria/agente/nao-existe/aplicar")
    assert r.status_code == 200
    assert len(main.ESTADO.unidades) == quantas


def test_criacao_inteira_cabe_num_desfazer(cli):
    """Meia estrutura nova num organograma de 267 pessoas é pior do que
    nenhuma: um ponto de desfazer cobre a criação toda."""
    antes = dict(main.ESTADO.propostas)
    nivel = next(iter(main.ESTADO.config.rotulos_nivel))
    pai = next(iter(main.ESTADO.unidades.values()))
    try:
        main.ESTADO.propostas["p2"] = {
            "id": "p2", "time": "T", "departamento": "T", "sob": pai.nome,
            "observacoes": "", "problemas": [], "total": 3, "pedido": "x",
            "unidades": [{"cargo": "Analista", "nivel": nivel, "quantidade": 3}]}
        quantas = len(main.ESTADO.unidades)
        cli.post("/maria/agente/p2/aplicar")
        assert len(main.ESTADO.unidades) == quantas + 3
        cli.post("/desfazer")
        assert len(main.ESTADO.unidades) == quantas
    finally:
        main.ESTADO.propostas = antes


# ---------------------------------------------------------------------------
# Agente Organograma — o que a proposta recusa
# ---------------------------------------------------------------------------
def test_json_e_extraido_de_texto_com_ruido():
    cercado = "```json\n" + '{"a": 1}' + "\n```"
    assert maria.extrair_json(cercado) == {"a": 1}
    assert maria.extrair_json('claro! {"b": 2} espero ter ajudado') == {"b": 2}
    assert maria.extrair_json("sem json nenhum") is None
    assert maria.extrair_json('{"quebrado": ') is None


def test_proposta_recusa_nivel_inventado():
    """O que o modelo devolve é entrada não confiável como qualquer outra."""
    p, problemas = maria.validar_proposta(
        {"unidades": [{"cargo": "X", "nivel": "imperador", "quantidade": 1}]},
        {"diretoria"}, set())
    assert p["unidades"] == []
    assert any("imperador" in x for x in problemas)


@pytest.mark.parametrize("quantidade", [0, -3, 31, 9999, "muitos"])
def test_proposta_recusa_quantidade_fora_da_faixa(quantidade):
    p, problemas = maria.validar_proposta(
        {"unidades": [{"cargo": "X", "nivel": "d", "quantidade": quantidade}]},
        {"d"}, set())
    assert p["unidades"] == [] and problemas


def test_gestor_inventado_cai_para_a_raiz():
    """Criar sob alguém que não existe no recorte seria pendurar um time
    inteiro num galho imaginário."""
    p, problemas = maria.validar_proposta(
        {"sob": "Pessoa Que Não Existe",
         "unidades": [{"cargo": "X", "nivel": "d", "quantidade": 1}]},
        {"d"}, {"Alguém Real"})
    assert p["sob"] == ""
    assert any("não está no seu recorte" in x for x in problemas)


def test_proposta_sem_unidades_nao_vira_proposta(monkeypatch):
    monkeypatch.setattr(maria, "configurada", lambda: True)
    monkeypatch.setattr(maria, "perguntar", lambda *a, **k: {
        "ok": True, "texto": '{"unidades": [], "observacoes": "pedido ambíguo"}',
        "modelo": "m", "entrada": 1, "saida": 1, "custo_usd": 0})
    r = maria.propor_estrutura("faça algo", {}, {"d"}, set())
    assert r["ok"] is False and r["motivo"] == "sem_proposta"


def test_sem_efeito_nao_inclui_quem_muta():
    assert maria.muta(maria.LER) is False
    assert maria.muta(maria.DESCREVER) is False
    assert maria.muta(maria.ANALISAR) is False
    assert maria.muta(maria.PLANEJAR) is True


# ---------------------------------------------------------------------------
# Recorte — a MarIA nunca vê mais que quem pergunta
# ---------------------------------------------------------------------------
def test_contexto_respeita_o_escopo():
    """O recorte vem da mesma guarda que rege a edição (SEC-03). Regra paralela
    para a IA divergiria da regra real no primeiro ajuste."""
    us = main.ESTADO.unidades
    alvo = next(iter(us.values()))
    ctx = maria.contexto(us, main.mapa_cc(), main.ESTADO.config, {alvo.id})
    assert ctx["total_no_recorte"] == 1
    assert [p["nome"] for p in ctx["pessoas_amostra"]] == [alvo.nome]


def test_escopo_vazio_nao_vaza_nada():
    ctx = maria.contexto(main.ESTADO.unidades, main.mapa_cc(),
                         main.ESTADO.config, set())
    assert ctx["total_no_recorte"] == 0 and ctx["pessoas_amostra"] == []


def test_sem_escopo_le_tudo():
    ctx = maria.contexto(main.ESTADO.unidades, main.mapa_cc(),
                         main.ESTADO.config, None)
    assert ctx["total_no_recorte"] == len(main.ESTADO.unidades)


def test_contexto_declara_quando_trunca():
    """Truncar em silêncio faria a MarIA responder sobre uma amostra achando
    que viu o todo."""
    ctx = maria.contexto(main.ESTADO.unidades, main.mapa_cc(),
                         main.ESTADO.config, None, limite=3)
    assert len(ctx["pessoas_amostra"]) == 3
    assert ctx["amostra_truncada_em"] == 3
    assert ctx["total_no_recorte"] > 3


def test_contagens_cobrem_o_recorte_inteiro_e_nao_a_amostra():
    """Mandar 220 fichas custava 27 mil tokens por pergunta. As contagens
    cobrem todo mundo; a amostra é que encolhe — e a distinção precisa estar
    no dado, senão a MarIA conta a amostra achando que é o todo."""
    us = main.ESTADO.unidades
    ctx = maria.contexto(us, main.mapa_cc(), main.ESTADO.config, None, limite=5)
    contagens = ctx["contagens_do_recorte_inteiro"]
    assert sum(contagens["por_nivel"].values()) == len(us)
    assert len(ctx["pessoas_amostra"]) == 5


def test_contexto_agregado_e_muito_menor_que_a_ficha_completa():
    import json

    us = main.ESTADO.unidades
    if len(us) < 50:
        pytest.skip("semente pequena demais para comparar")
    curto = len(json.dumps(maria.contexto(us, main.mapa_cc(),
                                          main.ESTADO.config, None), ensure_ascii=False))
    longo = len(json.dumps(maria.contexto(us, main.mapa_cc(), main.ESTADO.config,
                                          None, limite=260), ensure_ascii=False))
    assert curto < longo * 0.6


def test_editor_com_escopo_recebe_so_a_subarvore():
    cfg = main.ESTADO.config
    antes = (cfg.perfil, cfg.escopo_id)
    try:
        alvo = next(u for u in main.ESTADO.unidades.values() if u.parent_id)
        cfg.perfil, cfg.escopo_id = "org.editor", alvo.id
        ids, rotulo = main.escopo_visivel()
        assert ids is not None and alvo.id in ids
        assert len(ids) < len(main.ESTADO.unidades)
        assert rotulo == alvo.nome
    finally:
        cfg.perfil, cfg.escopo_id = antes


def test_admin_le_o_organograma_inteiro():
    cfg = main.ESTADO.config
    antes = (cfg.perfil, cfg.escopo_id)
    try:
        cfg.perfil, cfg.escopo_id = "org.admin", None
        ids, _ = main.escopo_visivel()
        assert ids is None
    finally:
        cfg.perfil, cfg.escopo_id = antes


# ---------------------------------------------------------------------------
# Chamada e custo
# ---------------------------------------------------------------------------
def test_sem_chave_avisa_em_vez_de_falhar(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = maria.perguntar("oi", {})
    assert r["ok"] is False and r["motivo"] == "sem_chave"


def test_pergunta_vazia_nao_chama(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k" * 20)
    assert maria.perguntar("   ", {})["motivo"] == "vazio"


def test_erro_de_rede_nao_derruba_a_tela(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k" * 20)

    def explode(*a, **k):
        raise OSError("sem rota para o host")

    monkeypatch.setattr(maria.urllib.request, "urlopen", explode)
    r = maria.perguntar("oi", {})
    assert r["ok"] is False and r["motivo"] == "rede"


def test_custo_usa_a_tabela_do_modelo():
    assert maria.custo("claude-opus-4-8", 1_000_000, 0) == 15
    assert maria.custo("claude-haiku-4-5", 0, 1_000_000) == 5
    # modelo desconhecido cai no padrão em vez de custar zero
    assert maria.custo("modelo-que-nao-existe", 1_000_000, 0) == 15


def test_prompt_marca_o_rascunho():
    p = maria.prompt(maria.PLANEJAR, "reorganize", {}, "pt-BR")
    assert "RASCUNHO" in p
    assert "aprovação humana" in p


# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------
def test_assistencia_guarda_o_recorte():
    """Sem o recorte não dá para auditar depois se a resposta era compatível
    com o que a pessoa podia ver."""
    r = {"ok": True, "texto": "resposta", "modelo": "m", "entrada": 10,
         "saida": 20, "custo_usd": 0.001}
    a = maria.assistencia("pergunta", r, {"id": "u1", "nome": "Alguém"},
                          maria.DESCREVER, "pt-BR", "Engenharia")
    assert a["escopo"] == "Engenharia"
    assert a["quem"] == "Alguém" and a["quem_id"] == "u1"
    assert a["pergunta"] == "pergunta" and a["resposta"] == "resposta"


def test_assistencia_registra_ate_a_falha():
    """Falha que não fica registrada vira 'a MarIA não respondeu' sem rastro."""
    r = {"ok": False, "mensagem": "sem chave"}
    a = maria.assistencia("p", r, None, maria.LER, "pt-BR")
    assert a["ok"] is False and a["resposta"] == "sem chave"


def test_resumo_soma_so_o_que_respondeu():
    h = [
        {"ok": True, "entrada": 10, "saida": 5, "custo_usd": 0.1,
         "capacidade": maria.LER},
        {"ok": False, "entrada": 99, "saida": 99, "custo_usd": 9.9,
         "capacidade": maria.LER},
    ]
    r = maria.resumo(h)
    assert r["total"] == 2 and r["com_resposta"] == 1
    assert r["entrada"] == 10 and r["saida"] == 5
    assert r["usd"] == 0.1 and r["brl"] == round(0.1 * maria.USD_BRL, 2)


def test_pergunta_pela_rota_grava_no_historico(cli):
    antes = list(main.ESTADO.assistencias)
    try:
        r = cli.post("/maria/perguntar",
                     data={"pergunta": "quantas pessoas?", "capacidade": "descrever"})
        assert r.status_code == 200
        assert len(main.ESTADO.assistencias) == len(antes) + 1
        registro = main.ESTADO.assistencias[-1]
        assert registro["pergunta"] == "quantas pessoas?"
        assert registro["capacidade"] == "descrever"
    finally:
        main.ESTADO.assistencias = antes


def test_capacidade_recusada_tambem_vira_registro(cli):
    """A recusa é informação: sem registro, ninguém descobre que alguém tentou."""
    antes = list(main.ESTADO.assistencias)
    try:
        cli.post("/maria/perguntar",
                 data={"pergunta": "reorganize tudo", "capacidade": "autonoma"})
        registro = main.ESTADO.assistencias[-1]
        assert registro["ok"] is False
        assert registro["capacidade"] == "autonoma"
    finally:
        main.ESTADO.assistencias = antes


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------
def test_modulo_abre_sem_chave(cli, monkeypatch):
    """Tela que some quando não configurada esconde o que existe."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = cli.get("/vistas/maria")
    assert r.status_code == 200
    assert "ANTHROPIC_API_KEY" in r.text
    for _, rotulo, *_ in maria.CAPACIDADES:
        assert rotulo in r.text or rotulo.lower() in r.text.lower()


def test_botao_no_cabecalho(cli):
    html = cli.get("/").text
    assert 'id="btMaria"' in html
    # O chat virou gaveta lateral; o módulo continua sendo uma vista.
    assert "/maria/chat" in html
    assert "/vistas/maria" in html
    assert 'id="mariaChat"' in html


def test_modelo_so_aceita_da_lista(cli):
    antes = main.ESTADO.config.maria_modelo
    try:
        cli.post("/maria/modelo", data={"modelo": "modelo-inventado"})
        assert main.ESTADO.config.maria_modelo == ""
        cli.post("/maria/modelo", data={"modelo": "claude-sonnet-5"})
        assert main.ESTADO.config.maria_modelo == "claude-sonnet-5"
    finally:
        main.ESTADO.config.maria_modelo = antes


def test_chave_da_api_nunca_vai_para_a_tela(cli, monkeypatch):
    """Credencial em HTML vaza em print, em cache e em view-source."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-segredo-do-cliente")
    html = cli.get("/vistas/maria").text
    assert "sk-ant-segredo-do-cliente" not in html


# ---------------------------------------------------------------------------
# O modelo padrão do sistema
# ---------------------------------------------------------------------------
def test_padrao_do_sistema_e_o_haiku():
    """Padrão de verdade, não override em runtime.

    Com o padrão em opus, qualquer instalação nova, estado limpo ou campo
    resetado voltava a um modelo ~15x mais caro por token — e a tela continuava
    mostrando haiku para quem já tinha salvo.
    """
    assert maria.MODELO_PADRAO == "claude-haiku-4-5"
    assert maria.MODELO_PADRAO in maria.modelos()
    # .env.exemplo é o que toda instalação nova copia: divergir dele é entregar
    # o padrão errado sem ninguém perceber.
    exemplo = (RAIZ_PROJETO / ".env.exemplo").read_text(encoding="utf-8")
    assert f"MARIA_MODEL={maria.MODELO_PADRAO}" in exemplo


def test_padrao_tem_preco_declarado():
    """Sem entrada em PRECOS o custo cai no genérico e a conta sai errada."""
    assert maria.MODELO_PADRAO in maria.PRECOS


# ---------------------------------------------------------------------------
# Recorte pelo canvas — só estreita
# ---------------------------------------------------------------------------
def test_canvas_nunca_devolve_none(estado_limpo):
    """None significa 'organograma inteiro' lá dentro (maria.contexto).

    Qualquer `ids or None` no caminho do canvas transformaria 'nada visível'
    em 'tudo' — e o erro passaria despercebido, porque o recorte do editor
    continuaria funcionando.
    """
    ids, rotulo = main.escopo_visivel(main.RECORTE_CANVAS)
    assert ids is not None and isinstance(ids, set)
    assert "canvas" in rotulo.lower()


def test_canvas_segue_o_que_esta_desenhado(estado_limpo):
    desenhados = {n["id"] for n in
                  main.layout_atual(None, com_cabecalho=False)["nos"]}
    ids, _ = main.escopo_visivel(main.RECORTE_CANVAS)
    assert ids == desenhados


def test_canvas_nunca_amplia_o_que_a_pessoa_ja_via(estado_limpo):
    """SEC-03: escolher o recorte pode estreitar, nunca abrir."""
    cfg = main.ESTADO.config
    antes = (cfg.perfil, cfg.escopo_id)
    try:
        alvo = next(u for u in main.ESTADO.unidades.values() if u.parent_id)
        cfg.perfil, cfg.escopo_id = "org.editor", alvo.id
        permitidos, _ = main.escopo_visivel()
        main.ESTADO.foco = None                  # canvas mostra a raiz inteira
        ids, _ = main.escopo_visivel(main.RECORTE_CANVAS)
        assert ids <= permitidos
    finally:
        cfg.perfil, cfg.escopo_id = antes


def test_canvas_com_foco_diz_de_onde(estado_limpo):
    alvo = next(u for u in main.ESTADO.unidades.values() if u.parent_id)
    anterior = main.ESTADO.foco
    try:
        main.ESTADO.foco = alvo.id
        _, rotulo = main.escopo_visivel(main.RECORTE_CANVAS)
        assert alvo.nome in rotulo
    finally:
        main.ESTADO.foco = anterior


def test_recorte_desconhecido_cai_no_padrao(estado_limpo):
    """Parâmetro inventado não pode virar recorte novo por engano."""
    assert main.escopo_visivel("qualquer-coisa") == main.escopo_visivel()


# ---------------------------------------------------------------------------
# As cinco sugestões
# ---------------------------------------------------------------------------
def test_sao_sempre_cinco(estado_limpo):
    assert len(main.sugestoes(None)) == 5
    assert len(main.sugestoes(set())) == 5          # recorte vazio
    um = next(iter(main.ESTADO.unidades))
    assert len(main.sugestoes({um})) == 5


def test_sugestao_ja_vem_formatada(estado_limpo):
    """Marcador sobrando vira `{n}` literal no botão — e a pergunta segue
    assim para a API."""
    for s in main.sugestoes(None) + main.sugestoes(set()):
        assert "{" not in s and "}" not in s
        assert s.strip() == s


def test_sugestao_nao_cita_numero_maior_que_o_recorte(estado_limpo):
    """Contagem de fora do recorte na sugestão é vazamento pela porta da
    frente: a pessoa lê o número sem nunca ter feito a pergunta."""
    import re
    ids = {next(iter(main.ESTADO.unidades))}
    for s in main.sugestoes(ids):
        # `N5`, `N2`, `N0` são códigos de coluna e de nível, não contagens — a
        # mesma distinção que o extrator de idiomas já faz. A regra aqui é
        # sobre quantidade: "78 centros de custo" precisa caber no recorte,
        # "mnemônico N5" é o nome de um campo.
        for numero in re.findall(r"(?<![A-Za-z])\d+", s):
            assert int(numero) <= len(ids), s


def test_sugestao_sai_do_poco_declarado(estado_limpo):
    """O poço é o que o extrator de i18n lê. Frase fora dele não é traduzida."""
    import re
    # Os dois poços: as 45 sem parâmetro e as 5 calculadas. Ambos são lidos
    # pelo extrator de idiomas; frase fora deles não seria traduzida.
    todos = list(main.SUGESTOES) + list(main.SUGESTOES_CALCULADAS.values())
    moldes = [re.escape(m).replace(r"\{n\}", r"\d+")
              .replace(r"\{total\}", r"\d+")
              .replace(r"\{dep\}", ".+").replace(r"\{nivel\}", ".+")
              .replace(r"\{vertical\}", ".+") for m in todos]
    for s in main.sugestoes(None):
        assert any(re.fullmatch(m, s) for m in moldes), s


def test_conversa_em_curso_nao_recalcula_sugestao(estado_limpo):
    """O template só mostra sugestão com a conversa vazia; calcular a cada
    turno pagaria uma varredura das unidades por mensagem trocada."""
    anterior = main.ESTADO.conversa
    try:
        main.ESTADO.conversa = [{"papel": "eu", "texto": "oi", "ok": True}]
        assert main.contexto_chat()["sugestoes"] == ()
    finally:
        main.ESTADO.conversa = anterior


# ---------------------------------------------------------------------------
# O recorte escolhido chega até o registro
# ---------------------------------------------------------------------------
def test_gaveta_mantem_a_escolha(cli):
    html = cli.get("/maria/chat", params={"recorte": "canvas"}).text
    assert 'value="canvas" selected' in html.replace("  ", " ")
    assert "canvas" in html.lower()


def test_gaveta_abre_no_recorte_de_permissao(cli):
    html = cli.get("/maria/chat").text
    assert 'value="" selected' in html.replace("  ", " ")


def test_sugestao_nunca_diz_um_no_plural(estado_limpo):
    """"1 pessoas" nos três idiomas custaria dez moldes a mais para dizer o
    que a reserva já diz sem número nenhum — então o piso é dois."""
    import re
    for ids in (None, set(), {next(iter(main.ESTADO.unidades))}):
        for s in main.sugestoes(ids):
            assert not re.search(r"\b1 \w+s\b", s), s


def test_rotulo_de_nivel_na_sugestao_e_traduzido():
    """O nível é interface (o admin edita a régua, o catálogo traduz); só
    departamento e vertical é que são dado do cliente e ficam como estão."""
    from orga import idiomas
    anterior = main.ESTADO.config.idioma
    try:
        main.ESTADO.config.idioma = "en-US"
        main.alinhar_idioma()
        texto = " ".join(main.sugestoes(None))
        if "Level" in texto or "level" in texto:
            assert "Célula" not in texto and "Diretoria" not in texto
    finally:
        main.ESTADO.config.idioma = anterior
        main.alinhar_idioma()


def test_recorte_escolhido_fica_gravado_na_assistencia(cli, monkeypatch,
                                                       estado_limpo):
    """Sem o recorte no registro não dá para auditar depois se a contagem que
    a MarIA deu batia com o que a pessoa estava vendo."""
    monkeypatch.setattr(main.mariamod, "perguntar", lambda *a, **k: {
        "ok": True, "texto": "Resposta.", "modelo": "claude-haiku-4-5",
        "entrada": 10, "saida": 5, "custo_usd": 0.0})
    cli.post("/maria/perguntar", data={"capacidade": "descrever",
                                       "pergunta": "quantos?",
                                       "recorte": "canvas"})
    assert "canvas" in main.ESTADO.assistencias[-1]["escopo"].lower()


def test_pergunta_no_canvas_so_ve_o_desenhado(cli, monkeypatch, estado_limpo):
    """O que chega ao modelo é o recorte, não o organograma inteiro."""
    visto = {}
    monkeypatch.setattr(main.mariamod, "perguntar",
                        lambda pergunta, ctx, **k: visto.update(ctx) or {
                            "ok": True, "texto": "ok", "modelo": "x",
                            "entrada": 1, "saida": 1, "custo_usd": 0.0})
    # A condição é montada aqui: colapsar alguém com filhos é o que faz o
    # canvas mostrar menos que o todo. Depender do colapso que já estava no
    # ESTADO deixaria o teste passar ou falhar conforme a ordem da suíte.
    filhos = main.mapa_filhos(main.ESTADO.unidades)
    pai = next(uid for uid, fs in filhos.items() if uid and fs)
    main.ESTADO.colapsados = {pai}

    cli.post("/maria/perguntar", data={"capacidade": "descrever",
                                       "pergunta": "quantos?",
                                       "recorte": "canvas"})
    desenhados = len(main.layout_atual(None, com_cabecalho=False)["nos"])
    assert visto["total_no_recorte"] == desenhados
    assert visto["total_no_recorte"] < len(main.ESTADO.unidades)


# ---------------------------------------------------------------------------
# CAPACIDADES NA GAVETA
# ---------------------------------------------------------------------------
def test_a_gaveta_oferece_as_capacidades_que_nao_mutam(cli):
    """Elas são a carta da MarIA, e escolher qual está em jogo muda o prompt.
    Antes a gaveta mandava sempre `descrever` e as outras só existiam na tabela
    do módulo."""
    from orga import maria as mariamod

    corpo = cli.get("/maria/chat").text
    for codigo, rotulo, _verbo in mariamod.DE_CONVERSA:
        assert f'value="{codigo}"' in corpo, codigo
    assert 'checked' in corpo
    # descrever vem escolhida por padrão
    i = corpo.index('id="cap-descrever"')
    assert "checked" in corpo[i:i + 120]


def test_executar_e_agir_sozinha_ficam_de_fora_da_gaveta(cli):
    """`Executar` exige aprovação humana por ação, num POST próprio com a
    proposta à vista. Oferecê-la num campo de texto contradiria o rodapé que
    promete somente leitura."""
    from orga import maria as mariamod

    corpo = cli.get("/maria/chat").text
    assert 'id="cap-executar"' not in corpo
    assert 'id="cap-autonoma"' not in corpo
    assert {c[0] for c in mariamod.DE_CONVERSA} == \
           mariamod.DISPONIVEIS - {mariamod.EXECUTAR}


def test_capacidade_forjada_no_formulario_cai_para_descrever(cli):
    """Filtro de entrada, e não de exibição: formulário é coisa que se forja."""
    assert main.capacidade_de_conversa("executar") == "descrever"
    assert main.capacidade_de_conversa("autonoma") == "descrever"
    assert main.capacidade_de_conversa("qualquer") == "descrever"
    assert main.capacidade_de_conversa("analisar") == "analisar"


def test_a_capacidade_escolhida_sobrevive_ao_turno(cli):
    """Volta marcada porque o POST a carregou — sem estado novo no servidor."""
    r = cli.get("/maria/chat?capacidade=analisar")
    i = r.text.index('id="cap-analisar"')
    assert "checked" in r.text[i:i + 120]


def test_o_indicador_de_pensando_e_um_giro_e_nao_um_retrato(cli):
    """22 px de ilustração empurravam o rodapé a cada pergunta, e a gaveta
    pulava. O que a pessoa precisa saber é que a máquina está ocupada."""
    corpo = cli.get("/maria/chat").text
    i = corpo.index('id="mcPensando"')
    trecho = corpo[i:i + 260]
    assert 'class="giro"' in trecho
    assert "MarIA_pensativa" not in trecho


def test_o_poco_de_sugestoes_e_grande_e_sorteado(estado_limpo):
    """Com cinco fixas, quem abre a gaveta todo dia vê sempre as mesmas cinco e
    para de ler. O sorteio é o que faz a vitrine convidar em vez de repetir."""
    assert len(main.SUGESTOES) >= 45
    assert len(set(main.SUGESTOES)) == len(main.SUGESTOES), "pergunta repetida"
    # Recorte vazio de propósito: ali nenhuma calculada sobrevive e as cinco
    # saem inteiras do poço, que é o que este teste quer observar. Numa base
    # rica as calculadas podem ocupar as cinco vagas, e o sorteio não
    # apareceria — o teste passaria a medir a base, não o mecanismo.
    vistas = set()
    for _ in range(30):
        vistas.update(main.sugestoes(set()))
    assert len(vistas) > main.QUANTAS_SUGESTOES, "a reserva não está variando"



def _casa(molde: str, frase: str) -> bool:
    """A frase saiu deste molde? Os marcadores já foram substituídos."""
    import re
    padrao = re.escape(molde)
    for marcador, conteudo in ((r"\{n\}", r"\d+"), (r"\{total\}", r"\d+"),
                               (r"\{dep\}", ".+"), (r"\{nivel\}", ".+"),
                               (r"\{vertical\}", ".+")):
        padrao = padrao.replace(marcador, conteudo)
    return bool(re.fullmatch(padrao, frase))

def test_a_calculada_tem_vaga_reservada_mas_nao_toma_a_vitrine(estado_limpo):
    """Sugestão que cita o número certo mostra que a MarIA já leu o recorte, e
    por isso tem vaga garantida. Mas só duas: as cinco eram determinísticas, e
    quem abria a gaveta todo dia via sempre a mesma tela."""
    saida = main.sugestoes(None)
    assert len(saida) == main.QUANTAS_SUGESTOES

    calculadas = {main.T(m) for m in main.SUGESTOES_CALCULADAS.values()}
    def e_calculada(frase):
        return any(_casa(molde, frase) for molde in calculadas)

    quantas = sum(1 for s in saida if e_calculada(s))
    assert 1 <= quantas <= main.TETO_CALCULADAS, (
        f"{quantas} calculadas na vitrine — o teto é {main.TETO_CALCULADAS}")
    # E o resto veio do poço, que é o que faz a vitrine mudar.
    assert sum(1 for s in saida if not e_calculada(s)) >= 3


def test_a_vitrine_muda_a_cada_abertura(estado_limpo):
    """A gaveta refaz a chamada a cada abertura — não há cache nem `once`. Se o
    sorteio não variasse, refazer a chamada não adiantaria nada."""
    vitrines = {tuple(main.sugestoes(None)) for _ in range(20)}
    assert len(vitrines) >= 15, (
        f"20 aberturas deram só {len(vitrines)} vitrines distintas")
    # Inclusive as calculadas rodam entre si, e não ficam presas nas duas
    # maiores: em vinte aberturas mais de duas chaves diferentes aparecem.
    vistas = {s for v in vitrines for s in v}
    assert len(vistas) > main.QUANTAS_SUGESTOES


def test_toda_sugestao_e_uma_pergunta_so_nos_tres_idiomas(estado_limpo):
    """A vitrine é um convite a perguntar. Escrita como "afirmação. pergunta?",
    metade do botão contava algo que a pessoa já vê na tabela, e a pergunta
    chegava no fim, pequena — o número serve de gancho, não de aviso."""
    from orga import idiomas

    moldes = list(main.SUGESTOES) + list(main.SUGESTOES_CALCULADAS.values())
    for molde in moldes:
        versoes = {"pt-BR": molde, **idiomas.CATALOGO.get(molde, {})}
        assert set(versoes) == {"pt-BR", "en-US", "es"}, molde
        for idioma, texto in versoes.items():
            assert texto.endswith("?"), f"[{idioma}] não termina em ?: {texto}"
            assert "." not in texto[:-1], (
                f"[{idioma}] afirmação antes da pergunta: {texto}")
            if idioma == "es":
                assert "¿" in texto, f"[es] sem ¿ de abertura: {texto}"
