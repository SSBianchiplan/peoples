"""A grade editável da Tabela: contrato, guardas e melhoria progressiva.

A grade é a única parte do sistema desenhada no cliente, e por isso é a única
onde vale a pena repetir aqui o que o painel já garante: que o servidor recusa
o que não deve gravar. Um teste que só exercitasse a tela deixaria passar
exatamente o caso que importa — o POST forjado, que não vem da tela.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orga import configuracao as cfgmod
from orga import dominio, grade
from orga import main


@pytest.fixture
def cli():
    return TestClient(main.app)


@pytest.fixture
def folha():
    """Uma unidade nova, filha da raiz, devolvida ao fim do teste.

    Criada e removida aqui de propósito: a suíte compartilha `main.ESTADO`, e
    um teste que edita alguém da base deixa o rastro para o próximo — o que já
    aconteceu, e o próximo a rodar acusa falha onde não há defeito.
    """
    raiz = main.raiz(main.ESTADO.unidades)
    nova = dominio.Unidade(id=main.novo_id(), codigo="ZZ-TESTE",
                           nome="Unidade de teste", tipo="celula",
                           parent_id=raiz.id, ordem=9990)
    main.ESTADO.unidades[nova.id] = nova
    yield nova
    main.ESTADO.unidades.pop(nova.id, None)


# ---------------------------------------------------------------------------
# O contrato das colunas
# ---------------------------------------------------------------------------
def test_toda_coluna_da_tabela_tem_contrato_na_grade():
    """Duas listas de colunas divergiriam na primeira coluna nova, e a grade
    sairia com um título a menos que a tabela — ou com um campo editável que
    ninguém decidiu que seria editável."""
    da_tabela = {c for c, _r, _p in main.COLUNAS_TABELA}
    assert da_tabela == set(grade.CAMPOS), (
        f"sem contrato: {da_tabela - set(grade.CAMPOS)} · "
        f"contrato sem coluna: {set(grade.CAMPOS) - da_tabela}")


def test_derivado_nao_e_editavel_e_diz_por_que():
    """Profundidade, subordinados, tempo de casa, N5, vertical e natureza são
    resultado. Deixá-los editáveis ofereceria mudar um número que o próximo
    render recalcula por cima — e recusar em silêncio, numa grade editável,
    lê-se como defeito."""
    derivadas = {"nivel_n", "sub", "tempo_casa", "n5", "vertical", "tipo_cc"}
    for chave in derivadas:
        editor, _dom, _larg, porque = grade.CAMPOS[chave]
        assert editor is None, f"{chave} não devia ser editável"
        assert porque, f"{chave} recusa a edição sem dizer por quê"
    assert not (derivadas & grade.EDITAVEIS)


def test_dados_trazem_linhas_colunas_e_dominios(cli):
    d = cli.get("/grade/dados").json()
    assert len(d["linhas"]) == len(main.linhas_tabela()), (
        "a grade e a tabela leem a MESMA travessia: duas dariam duas ordens")
    assert len(d["colunas"]) == len(main.COLUNAS_TABELA)
    # As suspensas do sistema saem do cadastro, não de lista fixa no cliente.
    assert {n["codigo"] for n in main.ESTADO.config.niveis} == \
           {o["v"] for o in d["dominios"]["tipo"]}
    assert set(dominio.STATUS) == {o["v"] for o in d["dominios"]["status"]}
    assert d["dominios"]["area"], "departamento sai do dado observado"


# ---------------------------------------------------------------------------
# Editar célula
# ---------------------------------------------------------------------------
def test_grava_texto_e_devolve_a_grade_inteira(cli, folha):
    r = cli.post("/grade/celula", data={"uid": folha.id, "campo": "cargo",
                                        "valor": "Analista de Prova"}).json()
    assert r["ok"] and folha.cargo == "Analista de Prova"
    # A grade inteira volta porque uma célula não basta: mudar o centro de
    # custo troca N5, vertical e natureza na mesma linha.
    assert "linhas" in r and "colunas" in r


def test_campo_fora_da_lista_branca_e_recusado(cli, folha):
    """`campo` chega por POST, e formulário é coisa que se forja."""
    for campo in ("tempo_casa", "parent_id", "id", "ordem", "__class__"):
        r = cli.post("/grade/celula", data={"uid": folha.id, "campo": campo,
                                            "valor": "x"}).json()
        assert r["ok"] is False, f"{campo} não podia ter sido aceito"
        assert r["aviso"]
    assert folha.parent_id is not None and folha.id


def test_suspensa_recusa_valor_fora_do_dominio(cli, folha):
    """Vocabulário do sistema é fechado: gravar 'Gerencia' ao lado de
    'Gerência' cria a divergência que só aparece três meses depois."""
    cli.post("/grade/celula", data={"uid": folha.id, "campo": "tipo",
                                    "valor": "gerencia"})
    assert folha.tipo == "gerencia"
    cli.post("/grade/celula", data={"uid": folha.id, "campo": "tipo",
                                    "valor": "nivel-inventado"})
    assert folha.tipo == "gerencia", "o valor inventado passou"

    cli.post("/grade/celula", data={"uid": folha.id, "campo": "vinculo",
                                    "valor": "nao-existe"})
    assert folha.vinculo in dominio.VINCULOS


def test_data_invalida_nao_envenena_o_tempo_de_casa(cli, folha):
    """O POST não vem só da tela. Lixo aqui estragaria a média de tempo de
    empresa, e o estrago só apareceria num indicador que ninguém confere."""
    cli.post("/grade/celula", data={"uid": folha.id, "campo": "data_inicio",
                                    "valor": "31/02/2020 ou coisa que o valha"})
    assert folha.data_inicio == ""
    cli.post("/grade/celula", data={"uid": folha.id, "campo": "data_inicio",
                                    "valor": "2020-03-01"})
    assert folha.data_inicio == "2020-03-01"


def test_nome_vazio_nao_apaga_a_linha_da_tela(cli, folha):
    """O nome é o que a árvore mostra: uma linha em branco não é editável de
    volta, e a unidade continuaria lá, invisível."""
    cli.post("/grade/celula", data={"uid": folha.id, "campo": "nome",
                                    "valor": "   "})
    assert folha.nome == "Unidade de teste"


def test_accountability_delegada_sobrevive_ao_editor_longo(cli, folha):
    """O editor longo devolve o mesmo texto da gaveta — uma por linha, com `>`
    marcando a delegada. Um segundo formato divergiria do primeiro."""
    cli.post("/grade/celula", data={
        "uid": folha.id, "campo": "accountabilities",
        "valor": "Própria daqui\n> Delegada de baixo\n\n  "})
    assert [(r["descricao"], r["origem"]) for r in folha.responsabilidades] == [
        ("Própria daqui", "propria"), ("Delegada de baixo", "delegada")]


# ---------------------------------------------------------------------------
# Hierarquia
# ---------------------------------------------------------------------------
def test_ciclo_e_recusado_com_a_grade_de_pe(cli, folha):
    """RF-02 / INV-02. E a recusa vem 200 com o motivo (INT-06): a grade
    continua na tela e a pessoa lê por que não deu."""
    r = cli.post("/grade/mover", data={"uid": folha.parent_id,
                                       "destino": folha.id})
    assert r.status_code == 200
    assert r.json()["ok"] is False and "ciclo" in r.json()["aviso"].lower()


def test_indentar_vira_filho_do_irmao_anterior(cli, folha):
    raiz = main.raiz(main.ESTADO.unidades)
    irmaos = [x.id for x in main.mapa_filhos(main.ESTADO.unidades).get(raiz.id, [])]
    assert irmaos[-1] == folha.id, "a fixture entra por último"
    anterior = irmaos[-2]
    assert cli.post("/grade/mover",
                    data={"uid": folha.id, "acao": "indentar"}).json()["ok"]
    assert folha.parent_id == anterior
    assert cli.post("/grade/mover",
                    data={"uid": folha.id, "acao": "promover"}).json()["ok"]
    assert folha.parent_id == raiz.id


def test_o_primeiro_irmao_nao_tem_para_onde_indentar(cli):
    """Recusa explicada, e não movimento silencioso para lugar nenhum."""
    raiz = main.raiz(main.ESTADO.unidades)
    primeiro = main.mapa_filhos(main.ESTADO.unidades)[raiz.id][0]
    r = cli.post("/grade/mover",
                 data={"uid": primeiro.id, "acao": "indentar"}).json()
    assert r["ok"] is False and r["aviso"]


def test_mover_para_destino_inexistente_nao_orfana_a_unidade(cli, folha):
    pai = folha.parent_id
    r = cli.post("/grade/mover",
                 data={"uid": folha.id, "destino": "id-que-nao-existe"}).json()
    assert r["ok"] is False
    assert folha.parent_id == pai


# ---------------------------------------------------------------------------
# Nó: dobrar, criar, duplicar, excluir
# ---------------------------------------------------------------------------
def test_dobrar_e_o_mesmo_estado_do_canvas(cli, folha):
    """Dobrar na grade dobra no canvas: duas representações da mesma verdade,
    não duas verdades."""
    cli.post("/grade/no", data={"uid": folha.id, "acao": "dobrar"})
    assert folha.id in main.ESTADO.colapsados
    cli.post("/grade/no", data={"uid": folha.id, "acao": "alternar"})
    assert folha.id not in main.ESTADO.colapsados


def test_filho_novo_nasce_com_codigo_proprio(cli, folha):
    """Dois nós com o mesmo código romperiam a chave que a carga usa para
    reconhecer quem já existe."""
    antes = set(main.ESTADO.unidades)
    assert cli.post("/grade/no",
                    data={"uid": folha.id, "acao": "filho"}).json()["ok"]
    novo = main.ESTADO.unidades[(set(main.ESTADO.unidades) - antes).pop()]
    try:
        assert novo.parent_id == folha.id
        assert novo.codigo and novo.codigo != folha.codigo
        codigos = [u.codigo for u in main.ESTADO.unidades.values() if u.codigo]
        assert len(codigos) == len(set(codigos)), "código repetido"
    finally:
        main.ESTADO.unidades.pop(novo.id, None)


def test_duplicar_nao_leva_a_pessoa_junto(cli, folha):
    """W9-C7: a cópia é do cargo, não de quem o ocupa. Duas pessoas com o mesmo
    e-mail em nós diferentes viram dois provisionamentos para o mesmo login."""
    folha.responsavel = "Fulano de Tal"
    folha.email = "fulano@gplansis.com"
    antes = set(main.ESTADO.unidades)
    assert cli.post("/grade/no",
                    data={"uid": folha.id, "acao": "duplicar"}).json()["ok"]
    copia = main.ESTADO.unidades[(set(main.ESTADO.unidades) - antes).pop()]
    try:
        assert copia.responsavel == "" and copia.email == ""
        assert copia.codigo != folha.codigo
    finally:
        main.ESTADO.unidades.pop(copia.id, None)


def test_a_raiz_nao_se_exclui_nem_se_duplica(cli):
    """W9-C9 / RF-03: sem raiz não há árvore, e com duas não há uma."""
    raiz = main.raiz(main.ESTADO.unidades)
    for acao in ("excluir", "duplicar"):
        r = cli.post("/grade/no", data={"uid": raiz.id, "acao": acao}).json()
        assert r["ok"] is False and r["aviso"]
    assert main.raiz(main.ESTADO.unidades).id == raiz.id


def test_excluir_sobe_os_filhos_em_vez_de_perde_los(cli, folha):
    filho = dominio.Unidade(id=main.novo_id(), codigo="ZZ-FILHO", nome="Abaixo",
                            tipo="celula", parent_id=folha.id, ordem=10)
    main.ESTADO.unidades[filho.id] = filho
    try:
        avo = folha.parent_id
        assert cli.post("/grade/no",
                        data={"uid": folha.id, "acao": "excluir"}).json()["ok"]
        assert filho.parent_id == avo, "o filho ficou pendurado em nada"
    finally:
        main.ESTADO.unidades.pop(filho.id, None)


# ---------------------------------------------------------------------------
# Ledger, desfazer e permissão
# ---------------------------------------------------------------------------
def test_toda_mutacao_da_grade_entra_no_ledger_e_da_ponto_de_desfazer(cli, folha):
    """A grade não é uma porta lateral: o que entra por ela é auditável e
    reversível como o que entra pela gaveta."""
    eventos = len(main.ESTADO.eventos)
    pontos = len(main.ESTADO.historico)
    cli.post("/grade/celula", data={"uid": folha.id, "campo": "cargo",
                                    "valor": "Auditado"})
    assert len(main.ESTADO.eventos) == eventos + 1
    assert len(main.ESTADO.historico) == pontos + 1
    assert "grade" in main.ESTADO.eventos[-1]["motivo"]

    cli.post("/desfazer")
    assert main.ESTADO.unidades[folha.id].cargo != "Auditado"


def test_quem_so_le_recebe_a_grade_sem_edicao(cli, folha):
    """INT-03: a decisão chega pronta do servidor, e a recusa não depende de o
    cliente ter escondido o botão."""
    anterior = main.ESTADO.config.perfil
    try:
        main.ESTADO.config.perfil = cfgmod.VIEWER
        d = cli.get("/grade/dados").json()
        assert d["podeEditar"] is False and d["motivo"]

        cargo = folha.cargo
        for rota, dados in (("/grade/celula", {"uid": folha.id, "campo": "cargo",
                                               "valor": "Forjado"}),
                            ("/grade/mover", {"uid": folha.id,
                                              "acao": "promover"}),
                            ("/grade/no", {"uid": folha.id, "acao": "excluir"})):
            r = cli.post(rota, data=dados).json()
            assert r["ok"] is False and r["aviso"], rota
        assert folha.cargo == cargo and folha.id in main.ESTADO.unidades
    finally:
        main.ESTADO.config.perfil = anterior


# ---------------------------------------------------------------------------
# Melhoria progressiva
# ---------------------------------------------------------------------------
def test_a_tabela_do_servidor_continua_no_html(cli):
    """Sem JavaScript, com a biblioteca fora do ar ou com a rota em erro, a
    vista precisa ser a de sempre — e não uma tela vazia."""
    html = cli.get("/vistas/tabela").text
    assert '<table class="arvore"' in html
    assert 'id="grade"' in html and "hidden" in html
    # O botão nasce escondido: sem grade montada ele prometeria uma edição que
    # a tabela do servidor não tem.
    assert 'id="btEditarGrade"' in html
    trecho = html.split('id="btEditarGrade"')[1][:120]
    assert "hidden" in trecho


def test_a_biblioteca_e_local_e_nao_de_cdn(cli):
    """Sem CDN e sem passo de build: a AG Grid Community mora em `web/vendor`,
    como o htmx."""
    html = cli.get("/").text
    assert "/vendor/ag-grid-community.min.js" in html
    assert "cdn." not in html and "unpkg" not in html
    assert cli.get("/vendor/ag-grid-community.min.js").status_code == 200
    assert cli.get("/estatico/grade.js").status_code == 200
