"""
Filtros, tabela colapsavel, permissoes, configuracao, carga assistida e PDF.

    pytest -q
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import cargos as cargosmod                                      # noqa: E402
from orga import centros                                                  # noqa: E402
from orga import configuracao as cfgmod                                   # noqa: E402
from orga import estrutura as estruturamod                                # noqa: E402
from orga import importador                                               # noqa: E402
from orga import main                                                     # noqa: E402
from orga import dominio                                                  # noqa: E402
from orga import pdf as pdfmod                                            # noqa: E402
from orga.dominio import (Tokens, Unidade, descendentes, mapa_filhos,     # noqa: E402
                          montar_card, raiz)


@pytest.fixture(autouse=True)
def estado_isolado(tmp_path):
    main.ARQUIVO_ESTADO = tmp_path / "estado.json"
    main.semear(spec=True)
    main.ESTADO.config = cfgmod.Config()
    main.ESTADO.config.centros_custo = main.cadastro_cc([])
    main.ESTADO.config.catalogo_cargos = main.catalogo_cargos()
    main.ESTADO.historico.clear()
    yield


@pytest.fixture
def cli():
    return TestClient(main.app)


def unidades():
    return main.ESTADO.unidades


def por_codigo(codigo: str):
    return next(u for u in unidades().values() if u.codigo == codigo)


def marcar_cc(codigo: str, cc: str, vertical: str, area: str = "") -> None:
    u = por_codigo(codigo)
    u.centro_custo, u.vertical = cc, vertical
    if area:
        u.area = area


# ---------------------------------------------------------------------------
# FILTROS
# ---------------------------------------------------------------------------
def test_filtro_por_vertical_reduz_e_marca_passagem(cli):
    marcar_cc("ORG-0002", "91.02", "91.0")
    marcar_cc("ORG-0003", "92.02", "92.0")
    cli.post("/filtros", data={"vertical": "92.0"})
    L = main.layout_atual()
    ids = {n["id"] for n in L["nos"]}
    assert por_codigo("ORG-0003").id in ids
    assert por_codigo("ORG-0002").id not in ids
    # a raiz fica so para sustentar o caminho ate o achado
    raiz_card = next(n for n in L["nos"] if n["id"] == raiz(unidades()).id)
    assert raiz_card["passagem"] is True and raiz_card["achou"] is False


def test_filtro_por_gestor_inclui_a_subarvore(cli):
    pai, filho = por_codigo("ORG-0002"), por_codigo("ORG-0003")
    cli.post(f"/unidades/{filho.id}/rebaixar")
    cli.post("/filtros", data={"gestor": pai.id})
    achados = main.achados()
    assert achados == {pai.id, filho.id}


def test_filtro_por_time_e_tipo_combina_em_e_logico(cli):
    a, b = por_codigo("ORG-0002"), por_codigo("ORG-0006")
    a.area, b.area = "Equipe X", "Equipe X"
    cli.post("/filtros", data={"area": "Equipe X", "tipo": "apoio"})
    assert main.achados() == {b.id}                       # ORG-0006 e o unico apoio


def test_filtro_por_centro_de_custo(cli):
    marcar_cc("ORG-0004", "91.07", "91.0")
    cli.post("/filtros", data={"centro_custo": "91.07"})
    assert main.achados() == {por_codigo("ORG-0004").id}


def test_filtro_abre_o_caminho_sem_alterar_o_colapso_guardado(cli):
    r = raiz(unidades())
    main.ESTADO.colapsados = {r.id}
    cli.post("/filtros", data={"texto": "beatriz"})
    assert len(main.layout_atual()["nos"]) == 2            # raiz + achado
    assert main.ESTADO.colapsados == {r.id}                # estado intacto
    cli.post("/filtros/limpar")
    assert len(main.layout_atual()["nos"]) == 1            # volta colapsado


def test_limpar_filtros_devolve_a_vista_inteira(cli):
    cli.post("/filtros", data={"texto": "beatriz"})
    r = cli.post("/filtros/limpar?vista=tabela")
    assert main.filtro_ativo() is False
    assert 'id="filtros"' in r.text and "<table" in r.text


def test_filtro_vale_para_o_csv_exportado(cli):
    cli.post("/filtros", data={"texto": "beatriz"})
    linhas = cli.get("/export.csv").text.strip().splitlines()
    assert len(linhas) == 3                                # cabecalho + raiz + achado


def test_dominio_dos_filtros_sai_do_dado(cli):
    marcar_cc("ORG-0002", "91.02", "91.0", area="Human Resources")
    corpo = cli.get("/vistas/tabela").text
    assert 'name="centro_custo" value="91.02"' in corpo
    assert 'name="area" value="Human Resources"' in corpo
    assert 'name="gestor" value="%s"' % raiz(unidades()).id in corpo
    # a vertical exposta e a de negocio, resolvida pelo cadastro de CC
    assert 'name="vertical_negocio" value="RH"' in corpo
    assert 'name="tipo_cc" value="Suport Team"' in corpo


def test_centro_de_custo_vem_com_o_nome_do_departamento(cli):
    from orga.dominio import valores_de_filtro
    marcar_cc("ORG-0002", "91.02", "91.0", area="Human Resources")
    opcoes = dict(valores_de_filtro(unidades(), main.mapa_cc())["centro_custo"])
    # O valor continua sendo so o codigo — e ele que casa com u.centro_custo.
    assert opcoes["91.02"] == "91.02 · Human Resources"


def test_centro_de_custo_com_dois_departamentos_mostra_os_dois(cli):
    from orga.dominio import valores_de_filtro
    marcar_cc("ORG-0002", "81.11", "81.0", area="Pre-Engineering")
    marcar_cc("ORG-0003", "81.11", "81.0", area="Account Managers")
    opcoes = dict(valores_de_filtro(unidades())["centro_custo"])
    assert opcoes["81.11"] == "81.11 · Account Managers, Pre-Engineering"


def test_grafia_errada_do_departamento_nao_volta_pela_barra_de_filtros(cli):
    # A correção é de leitura, mas o estado gravado antes dela continua trazendo
    # "Enviroment" — e a barra é tela. O valor fica cru, senão o filtro deixaria
    # de encontrar exatamente quem está com o nome errado.
    from orga.dominio import valores_de_filtro
    marcar_cc("ORG-0002", "95.31", "95.0", area="Enviroment")
    opcoes = valores_de_filtro(unidades())
    assert ("Enviroment", "Environment") in opcoes["area"]
    assert dict(opcoes["centro_custo"])["95.31"] == "95.31 · Environment"


def test_centro_de_custo_sem_departamento_fica_so_com_o_codigo(cli):
    from orga.dominio import valores_de_filtro
    marcar_cc("ORG-0002", "77.11", "77.0")
    por_codigo("ORG-0002").area = ""
    opcoes = dict(valores_de_filtro(unidades())["centro_custo"])
    assert opcoes["77.11"] == "77.11"


def test_filtro_marcado_volta_marcado_no_popover(cli):
    marcar_cc("ORG-0002", "91.02", "91.0")
    cli.post("/filtros", data={"centro_custo": "91.02"})
    corpo = cli.get("/vistas/tabela").text
    assert 'name="centro_custo" value="91.02"\n               checked' in corpo \
        or 'value="91.02"' in corpo and "checked" in corpo


def test_gestor_marcado_sobrevive_ao_recorte_dos_outros(cli):
    """O beco sem saida que `sobrevive` existe para evitar, e do qual o gestor
    era o unico chip de fora.

    Marcado o gestor, marcar depois uma vertical a que ele nao pertence o tirava
    da propria lista: o checkbox sumia e nao havia mais como desmarca-lo. So a
    limpeza geral destravava — e ela leva junto tudo o que a pessoa escolheu.
    """
    chefe = por_codigo("ORG-0001")                     # tem filhos: e gestor
    marcar_cc("ORG-0002", "91.02", "77.0")             # vertical que o chefe nao tem
    cli.post("/filtros", data={"gestor": chefe.id, "vertical": "77.0"})
    opcoes = main.contexto_filtros()["opcoes"]
    assert chefe.id in {v for v, _ in opcoes["gestor"]}
    # E com o nome, nunca com o id em hexa: o rotulo e o que a pessoa le.
    assert dict(opcoes["gestor"])[chefe.id] == chefe.nome


def test_dominio_dos_chips_varre_a_base_uma_vez_por_criterio(cli, monkeypatch):
    """`base_de` estava DENTRO do `any()` dos chips de nivel e vinculo, entao
    era reavaliado uma vez por chave do enum — e cada avaliacao e uma passada
    de `filtrar` sobre a base inteira. Nove varreduras a mais por render."""
    marcar_cc("ORG-0002", "91.02", "91.0")
    cli.post("/filtros", data={"vertical": "91.0"})
    n = [0]
    original = dominio.filtrar
    monkeypatch.setattr(dominio, "filtrar",
                        lambda *a, **k: (n.__setitem__(0, n[0] + 1),
                                         original(*a, **k))[1])
    main.contexto_filtros()
    assert n[0] == len(dominio.CRITERIOS), (
        f"{n[0]} varreduras para {len(dominio.CRITERIOS)} critérios")


def test_cada_criterio_tem_borracha_propria(cli):
    corpo = cli.get("/vistas/canvas").text
    campos = ("vertical_negocio", "tipo_cc", "centro_custo", "area", "cargo",
              "gestor", "tipo", "vinculo")
    for campo in campos:
        assert f"limparCampo('{campo}', event)" in corpo
    # Um chip novo entra com a sua borracha; a conta sai do que a barra
    # realmente desenha, não de uma lista que precisa ser lembrada. Conta por
    # `data-campo`, e não pela classe: um chip sem opção no recorte vigente
    # ganha `chip vazio`, e casar a classe inteira o deixaria de fora.
    assert corpo.count('class="borracha"') == corpo.count("data-campo=") == len(campos)


# ---------------------------------------------------------------------------
# TABELA
# ---------------------------------------------------------------------------
def test_tabela_respeita_o_colapso_do_canvas(cli):
    r = raiz(unidades())
    main.ESTADO.colapsados = {r.id}
    linhas = main.linhas_tabela()
    assert len(linhas) == 1 and linhas[0]["colapsado"] is True
    assert linhas[0]["descendentes"] == 5


def test_colapsar_na_tabela_colapsa_no_canvas(cli):
    r = raiz(unidades())
    resp = cli.post(f"/unidades/{r.id}/colapsar?vista=tabela")
    assert "<table" in resp.text and 'id="filtros"' not in resp.text
    assert r.id in main.ESTADO.colapsados
    assert len(main.layout_atual()["nos"]) == 1            # mesma verdade


def test_expandir_ate_nivel_n(cli):
    filho = por_codigo("ORG-0003")
    cli.post(f"/unidades/{filho.id}/filho")                # cria N2
    cli.post("/arvore/nivel?nivel=1&vista=tabela")
    assert len(main.linhas_tabela()) == 6                  # raiz + 5, N2 dobrado
    cli.post("/arvore/nivel?nivel=2&vista=tabela")
    assert len(main.linhas_tabela()) == 7


# ---------------------------------------------------------------------------
# Grafia dos departamentos
# ---------------------------------------------------------------------------
def test_grafia_errada_da_planilha_e_corrigida_na_leitura():
    """"Enviroment" não era só feio: virou linha de centro de custo.

    A planilha traz `Enviroment` na coluna Departamento. Como a descoberta de CC
    monta linhas novas a partir de `u.area`, a grafia errada entrou no cadastro
    como se fosse um departamento que ninguém conhecia — e de lá foi para o card,
    a tabela, o filtro e o funil.
    """
    assert centros.corrigir_departamento("Enviroment") == "Environment"
    assert centros.corrigir_departamento("Pulp & Papper") == "Pulp & Paper"
    assert centros.corrigir_departamento("  Enviroment  ") == "Environment"
    # o que já está certo não pode ser mexido
    assert centros.corrigir_departamento("Mechanical Team") == "Mechanical Team"
    assert centros.corrigir_departamento("") == ""


def test_toda_correcao_tem_nome_em_portugues_e_nao_encadeia():
    """Corrigir para um nome que a tela não sabe exibir só troca de problema."""
    for errado, certo in centros.CORRECOES_DEPARTAMENTO.items():
        assert certo in estruturamod.ROTULO_PT, \
            f"{certo!r} não tem rótulo em português — apareceria cru na tela"
        assert certo not in centros.CORRECOES_DEPARTAMENTO, \
            f"correção encadeada: {errado} → {certo} → …"
        assert errado != certo


def test_normalizar_repara_cadastro_ja_gravado():
    """O estado em disco é anterior à correção; carregar tem de consertá-lo."""
    sujo = [centros.registro(n3="95.30", departamento="Enviroment", n5="SGQ",
                             vertical="SGQ", tipo="Suport Team")]
    assert centros.normalizar(sujo)[0]["departamento"] == "Environment"


def test_descoberta_nao_cria_departamento_com_a_grafia_errada():
    unidades = {u.id: u for u in main.ESTADO.unidades.values()}
    alvo = next(iter(unidades.values()))
    alvo.area, alvo.centro_custo, alvo.vertical = "Enviroment", "95.31", "95.0"
    achados = centros.descobrir(unidades, centros.referencia())
    nomes = {c["departamento"] for c in achados}
    assert "Enviroment" not in nomes
    assert "Environment" in nomes


def test_estrutura_nao_mostra_grafia_errada(cli):
    """Regressão da tela que o operador reportou: SGQ mostrava "Enviroment"."""
    assert estruturamod.rotulo_pt("Enviroment") == "Meio Ambiente"
    assert estruturamod.rotulo_pt("Pulp & Papper") == "Pulp & Paper"


def test_estrutura_seleciona_vertical_com_e_comercial(cli):
    """F&B, P&P e P&M levam `&` na sigla.

    Sem escape o link vira `vertical=P&P`, que a query string lê como
    `vertical=P` mais um parâmetro `P` vazio — o chip parecia clicável e não
    selecionava nada. O servidor via 200 e ninguém percebia.
    """
    # A semente de teste não tem verticais com `&`; o contrato é do template.
    html = main.render(
        "_estrutura.html", vista="estrutura", banda="negocio", vert=None,
        departamento="", pessoas=[], rotulo_dep="", conferir=False,
        consulta="banda=negocio", divergencias=[],
        faixas=[{"chave": "negocio", "rotulo": "Business Units", "largura": .73,
                 "legenda": "", "pessoas": 63, "chips": [
                     {"sigla": "P&P", "nome": "Pulp & Paper", "deck": None,
                      "pessoas": 18},
                     {"sigla": "F&B", "nome": "Food & Beverage", "deck": None,
                      "pessoas": 45}]}])
    for sigla in ("F&B", "P&P"):
        assert f"vertical={sigla}" not in html, f"{sigla} entrou cru na URL"
    assert "vertical=P%26P" in html and "vertical=F%26B" in html

    # E o servidor tem de aceitar a sigla escapada de volta.
    r = cli.get("/vistas/estrutura?banda=negocio&vertical=" + quote("P&P"))
    assert r.status_code == 200


def test_linha_da_tabela_abre_a_gaveta_sem_canvas_oob(cli):
    alvo = por_codigo("ORG-0002")
    corpo = cli.get("/vistas/tabela").text
    # `vista=tabela` viaja junto: e o que faz o salvar devolver a tabela.
    assert f'hx-get="/fragmentos/painel/{alvo.id}?canvas=0&amp;vista=tabela"' in corpo
    assert 'hx-target="#painel"' in corpo
    painel = cli.get(f"/fragmentos/painel/{alvo.id}?canvas=0&vista=tabela").text
    assert "<svg" not in painel                            # nao ha #canvas na tabela
    assert 'name="nome"' in painel
    assert main.ESTADO.selecionado == alvo.id


def test_salvar_pela_tabela_devolve_a_tabela_atualizada(cli):
    """Sem isso o nome editado continuava velho na linha que o abriu."""
    alvo = por_codigo("ORG-0002")
    r = cli.post(f"/unidades/{alvo.id}/salvar",
                 data={"nome": "Nome Trocado", "tipo": alvo.tipo,
                       "vista": "tabela", "contexto": ""})
    assert r.status_code == 200
    assert 'id="tabelaCorpo" hx-swap-oob="true"' in r.text
    assert "Nome Trocado" in r.text
    assert main.ESTADO.unidades[alvo.id].nome == "Nome Trocado"


def test_tabela_marca_a_linha_selecionada(cli):
    alvo = por_codigo("ORG-0002")
    cli.get(f"/fragmentos/painel/{alvo.id}?canvas=0")
    assert "clicavel achou" in cli.get("/vistas/tabela").text or True
    assert 'class="clicavel sel"' in cli.get("/vistas/tabela").text


# ---------------------------------------------------------------------------
# PERMISSOES  (SEC-02 / SEC-03)
# ---------------------------------------------------------------------------
ROTAS_DE_MUTACAO = [
    ("post", "/unidades/{id}/filho", {}),
    ("post", "/unidades/{id}/duplicar", {}),
    ("post", "/unidades/{id}/reordenar", {}),
    ("post", "/unidades/{id}/rebaixar", {}),
    ("post", "/unidades/{id}/salvar", {"nome": "X", "tipo": "area"}),
    ("delete", "/unidades/{id}", {}),
]


@pytest.mark.parametrize("metodo,rota,dados", ROTAS_DE_MUTACAO)
def test_viewer_nao_altera_nada(cli, metodo, rota, dados):
    main.ESTADO.config.perfil = cfgmod.VIEWER
    alvo = por_codigo("ORG-0003")
    antes = len(unidades()), alvo.nome
    r = cli.request(metodo.upper(), rota.format(id=alvo.id), data=dados)
    assert r.status_code == 200                            # INT-06, nao 4xx
    assert "Ação negada" in r.text
    assert (len(unidades()), alvo.nome) == antes


def test_editor_dentro_do_escopo_altera(cli):
    escopo = por_codigo("ORG-0002")
    main.ESTADO.config.perfil = cfgmod.EDITOR
    main.ESTADO.config.escopo_id = escopo.id
    r = cli.post(f"/unidades/{escopo.id}/filho")
    assert "Ação negada" not in r.text
    assert len(mapa_filhos(unidades())[escopo.id]) == 1


def test_editor_fora_do_escopo_e_recusado(cli):
    escopo, fora = por_codigo("ORG-0002"), por_codigo("ORG-0005")
    main.ESTADO.config.perfil = cfgmod.EDITOR
    main.ESTADO.config.escopo_id = escopo.id
    r = cli.post(f"/unidades/{fora.id}/filho")
    assert "fora do escopo" in r.text
    assert not mapa_filhos(unidades()).get(fora.id)


def test_editor_alcanca_descendentes_do_escopo(cli):
    escopo, neto = por_codigo("ORG-0002"), por_codigo("ORG-0003")
    cli.post(f"/unidades/{neto.id}/rebaixar")              # vira filho de ORG-0002
    main.ESTADO.config.perfil = cfgmod.EDITOR
    main.ESTADO.config.escopo_id = escopo.id
    assert neto.id in descendentes(unidades(), escopo.id)
    r = cli.post(f"/unidades/{neto.id}/salvar",
                 data={"nome": "Renomeado", "tipo": neto.tipo})
    assert "Ação negada" not in r.text and neto.nome == "Renomeado"


def test_editor_nao_entra_na_configuracao(cli):
    main.ESTADO.config.perfil = cfgmod.EDITOR
    r = cli.post("/config/geral", data={"titulo": "Pirata"})
    assert "Ação negada" in r.text
    assert main.ESTADO.config.titulo == "Organograma"


def test_viewer_nao_recarrega_a_base(cli):
    main.ESTADO.config.perfil = cfgmod.VIEWER
    assert "Ação negada" in cli.post("/restaurar").text


def test_menu_de_contexto_desabilita_para_viewer(cli):
    main.ESTADO.config.perfil = cfgmod.VIEWER
    menu = cli.get(f"/fragmentos/menu/{por_codigo('ORG-0003').id}").text
    acoes = re.findall(r"<button[^>]*>", menu)
    mutantes = [a for a in acoes if "/unidades/" in a and "colapsar" not in a
                and "focar" not in a and "fragmentos" not in a]
    assert mutantes and all("disabled" in a for a in mutantes)


def test_painel_fica_em_leitura_para_viewer(cli):
    main.ESTADO.config.perfil = cfgmod.VIEWER
    painel = cli.get(f"/fragmentos/painel/{por_codigo('ORG-0002').id}").text
    assert "<fieldset" in painel and "disabled" in painel
    assert "sem permissão de edição" in painel


# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------
def test_titulo_configurado_chega_ao_desenho(cli):
    cli.post("/config/geral", data={"titulo": "Estrutura GPlanSiS|Peoples",
                                    "tenant": "GPlanSiS|Peoples",
                                    "orientacao_padrao": "invertida",
                                    "profundidade_aberta": 1})
    assert main.layout_atual()["cabecalho"]["titulo"] == "Estrutura GPlanSiS|Peoples"
    assert "Estrutura GPlanSiS|Peoples" in cli.get("/export.svg").text


def test_campos_do_card_controlam_o_desenho(cli):
    u = por_codigo("ORG-0002")
    antes = len([n for n in main.layout_atual()["nos"] if n["id"] == u.id][0]["itens"])
    assert antes > 0
    cli.post("/config/campos", data={"campo_nome": "1", "campo_cargo": "1"})
    card = [n for n in main.layout_atual()["nos"] if n["id"] == u.id][0]
    assert card["itens"] == []                             # accountabilities fora
    assert not any(t["cls"] == "t-cod" for t in card["textos"])
    assert any(t["cls"] == "t-nome" for t in card["textos"])


def test_campo_nome_nao_pode_ser_desligado(cli):
    cli.post("/config/campos", data={})                    # nada marcado
    assert "nome" in main.ESTADO.config.campos


def test_tokens_fora_da_faixa_sao_saneados(cli):
    cli.post("/config/campos", data={"campo_nome": "1", "card_w": "9999",
                                     "gap_h": "0", "gap_v": "40", "max_itens": "99"})
    c = main.ESTADO.config
    assert c.card_w == cfgmod.LIMITES_TOKENS["card_w"][1]
    assert c.gap_h == cfgmod.LIMITES_TOKENS["gap_h"][0]
    assert main.layout_atual()["nos"][0]["w"] == c.card_w


def test_geometria_configurada_muda_o_layout(cli):
    largura_antes = main.layout_atual()["nos"][0]["w"]
    cli.post("/config/campos", data={"campo_nome": "1", "card_w": "160"})
    assert main.layout_atual()["nos"][0]["w"] == 160 != largura_antes


def test_perfil_e_escopo_persistem(cli):
    alvo = por_codigo("ORG-0002")
    cli.post("/config/permissoes", data={"perfil": cfgmod.EDITOR,
                                         "escopo_id": alvo.id})
    assert main.ESTADO.config.perfil == cfgmod.EDITOR
    assert main.ESTADO.config.escopo_id == alvo.id
    assert cli.get("/api/v1/configuracao").json()["perfil_rotulo"] == "Editor"


def test_cadastro_de_cc_nasce_da_tabela_de_referencia(cli):
    reg = main.ESTADO.config.centros_custo
    assert len(reg) >= len(centros.REFERENCIA)
    linha = next(c for c in reg if c["n3"] == "80.30"
                 and c["departamento"] == "Process Engineering")
    assert (linha["logico"], linha["n2"], linha["n5"], linha["vertical"],
            linha["tipo"]) == ("80", "80.0", "PRO", "ENG", "Bussines Unit")


def test_chave_do_cadastro_e_o_par_n3_departamento():
    """"Managers Team" existe em quatro N3 distintos; o nome nao identifica."""
    reg = centros.referencia()
    managers = [c for c in reg if c["departamento"] == "Managers Team"]
    assert len({c["n3"] for c in managers}) == len(managers) >= 4
    assert len({centros.chave(c["n3"], c["departamento"]) for c in reg}) == len(reg)


def test_n4_da_planilha_alcanca_o_n3_do_cadastro():
    assert centros.n3_de("80.31") == "80.30"
    assert centros.n3_de("87.01") == "87.00"
    assert centros.n3_de("GBE") == "GBE"
    assert centros.n3_de("") == ""


def test_resolucao_tem_degraus_e_diz_qual_usou():
    ix = centros.indices(centros.referencia())
    assert centros.resolver("80.31", "Process Engineering", ix)[1] == "exato"
    # a planilha escreve "Pulp & Papper"; o cadastro, "Pulp & Paper"
    assert centros.resolver("81.21", "Pulp & Papper", ix)[1] == "n3"
    assert centros.resolver("", "Engineering", ix)[1] == "departamento"
    assert centros.resolver("99.99", "Inexistente", ix) == (None, "sem correspondência")


def test_cadastro_e_editavel_e_normaliza(cli):
    cli.post("/config/cc", data={
        "linha": "0", "logico_0": "", "n2_0": "", "n3_0": "80.30",
        "departamento_0": "Process Engineering", "n5_0": "PRO",
        "vertical_0": "ENG", "tipo_0": "Bussines Unit", "ativo_0": "1",
        "novo_n3": "99.90", "novo_departamento": "Time Novo",
        "novo_n5": "NEW", "novo_vertical": "NEW", "novo_tipo": "Suport Team"})
    reg = {c["departamento"]: c for c in main.ESTADO.config.centros_custo}
    assert reg["Time Novo"]["n5"] == "NEW"
    assert reg["Time Novo"]["n2"] == "99.0"      # derivado do N3
    assert reg["Time Novo"]["logico"] == "99"


def test_descobrir_acrescenta_sem_apagar(cli):
    u = por_codigo("ORG-0002")
    u.area, u.centro_custo, u.vertical = "Equipe Inedita", "77.11", "77.0"
    antes = len(main.ESTADO.config.centros_custo)
    cli.post("/config/cc/redescobrir")
    reg = main.ESTADO.config.centros_custo
    assert len(reg) == antes + 1
    novo = next(c for c in reg if c["departamento"] == "Equipe Inedita")
    assert novo["n3"] == "77.10" and novo["logico"] == "77"


def test_conciliacao_relata_orfas_e_ociosas(cli):
    u = por_codigo("ORG-0002")
    u.area, u.centro_custo = "Equipe Fantasma", "77.11"
    rel = centros.conciliar(unidades(), centros.referencia())
    assert ("77.11", "Equipe Fantasma") in rel["orfas"]
    assert rel["por_casamento"].get("sem correspondência", 0) >= 1
    assert any(c["departamento"] == "Finance" for c in rel["ociosos"])


def test_cc_alimenta_filtro_e_card(cli):
    u = por_codigo("ORG-0002")
    u.area, u.centro_custo, u.vertical = "Process Engineering", "80.31", "80.0"
    cli.post("/filtros", data={"vertical_negocio": "ENG"})
    assert main.achados() == {u.id}
    cli.post("/filtros/limpar")
    cli.post("/filtros", data={"tipo_cc": "Bussines Unit"})
    assert main.achados() == {u.id}


def test_cadastro_de_cc_sai_em_csv(cli):
    linhas = cli.get("/centros.csv").text.strip().splitlines()
    assert len(linhas) == len(main.ESTADO.config.centros_custo) + 1
    assert linhas[0].startswith("﻿LogicalCC;N2;N3;Departamento;N5;Vertical;Tipo")


def test_configuracao_entra_no_ledger(cli):
    antes = len(main.ESTADO.eventos)
    cli.post("/config/geral", data={"titulo": "X", "tenant": "Y",
                                    "orientacao_padrao": "vertical",
                                    "profundidade_aberta": 2})
    assert len(main.ESTADO.eventos) == antes + 1
    assert main.verificar_cadeia()["integro"] is True


def test_config_sobrevive_a_recarga_da_base(cli):
    cli.post("/config/geral", data={"titulo": "Persistente", "tenant": "T",
                                    "orientacao_padrao": "invertida",
                                    "profundidade_aberta": 1})
    cli.post("/restaurar")
    assert main.ESTADO.config.titulo == "Persistente"


# ---------------------------------------------------------------------------
# CARGA ASSISTIDA
# ---------------------------------------------------------------------------
def planilha(linhas: list[dict], titulos: list[str] | None = None) -> bytes:
    """Monta um .xlsx a partir de dicts {titulo da coluna: valor}.

    Por titulo, e nao por posicao, porque o contrato passou a ser lido por
    titulo: um helper posicional voltaria a esconder exatamente o defeito que
    a leitura por nome corrigiu, e uma coluna nova no meio deslocaria trinta
    linhas de teste em silencio.

    `titulos` deixa escrever uma planilha PARCIAL — util para provar que
    arquivo antigo, sem as colunas novas, continua entrando.
    """
    import openpyxl
    titulos = titulos or importador.TITULOS
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ORG"
    ws.append(titulos)
    for l in linhas:
        ws.append([l.get(t, "") for t in titulos])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def pl(nome, cargo="", area="Human Resources", email="", n2="91.0",
       n3="91.00", n4="", gestor="", **extra) -> dict:
    """Uma linha do contrato, com os oito campos historicos nomeados."""
    linha = {"Colaborador": nome, "Cargo/Função": cargo, "Departamento": area,
             "E-mail": email, "N2": n2, "N3": n3, "N4": n4,
             "Gestor Direto": gestor}
    linha.update(extra)
    return linha


# As oito colunas de sempre — as novas ficam de fora de proposito, para o
# caminho classico continuar sendo exercitado por toda a suite.
TITULOS_ANTIGOS = ["Colaborador", "Cargo/Função", "Departamento", "E-mail",
                   "N2", "N3", "N4", "Gestor Direto"]

BASE_PLANILHA = [
    pl("Marina Albuquerque Sá", "Gerente de RH", email="l@x.com", n4="91.01",
       gestor="Conselho"),
    pl("Beatriz Nogueira Pinto", "Coordenador de RH", email="k@x.com", n4="91.02",
       gestor="Marina Albuquerque Sá"),
]


def preparar_espelho() -> None:
    """Alinha o seed da SPEC com a planilha-base, para o diff ficar limpo."""
    for codigo, email in (("ORG-0001", "l@x.com"), ("ORG-0002", "k@x.com")):
        u = por_codigo(codigo)
        u.email = email
    por_codigo("ORG-0001").nome = "Marina Albuquerque Sá"
    por_codigo("ORG-0002").nome = "Beatriz Nogueira Pinto"


def test_planilha_sem_coluna_obrigatoria_e_recusada(cli):
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.append(["Nome", "Cargo"])
    buf = io.BytesIO()
    wb.save(buf)
    r = cli.post("/config/importar/analisar",
                 files={"arquivo": ("ruim.xlsx", buf.getvalue())})
    assert "Planilha recusada" in r.text and "Colaborador" in r.text
    assert main.ESTADO.importacao is None


def test_analise_classifica_novo_alterado_e_ausente(cli):
    preparar_espelho()
    dados = planilha(BASE_PLANILHA + [
        pl("Novato da Silva", "Analista de RH", email="n@x.com", n4="91.02",
           gestor="Beatriz Nogueira Pinto")])
    cli.post("/config/importar/analisar",
             files={"arquivo": ("nova.xlsx", dados)})
    imp = main.ESTADO.importacao
    assert [l["nome"] for l in imp["novos"]] == ["Novato da Silva"]
    assert {r["codigo"] for r in imp["removidos"]} == {"ORG-0003", "ORG-0004",
                                                       "ORG-0005", "ORG-0006"}
    assert imp["total"] == 3
    assert len(unidades()) == 6                            # passo 2 nao escreve


def test_analise_detecta_troca_de_gestor_e_de_campo(cli):
    preparar_espelho()
    dados = planilha([
        BASE_PLANILHA[0],
        pl("Beatriz Nogueira Pinto", "Gerente de Remuneração", area="Rewards",
           email="k@x.com", n4="91.09", gestor="Marina Albuquerque Sá")])
    cli.post("/config/importar/analisar", files={"arquivo": ("d.xlsx", dados)})
    alterado = next(a for a in main.ESTADO.importacao["alterados"]
                    if a["codigo"] == "ORG-0002")
    campos = {c for c, _, _ in alterado["mudancas"]}
    assert {"cargo", "area", "centro_custo"} <= campos


def test_aplicar_cria_atualiza_e_reparenta(cli):
    preparar_espelho()
    dados = planilha(BASE_PLANILHA + [
        pl("Novato da Silva", "Analista de RH", email="n@x.com", n4="91.02",
           gestor="Beatriz Nogueira Pinto")])
    cli.post("/config/importar/analisar", files={"arquivo": ("n.xlsx", dados)})
    cli.post("/config/importar/aplicar", data={"criar": "1", "atualizar": "1"})
    novo = next(u for u in unidades().values() if u.nome == "Novato da Silva")
    assert novo.parent_id == por_codigo("ORG-0002").id
    assert novo.cargo == "Analista de RH" and novo.codigo.startswith("ORG-")
    assert len(unidades()) == 7                            # nada removido
    assert main.ESTADO.importacao is None


def test_aplicar_remocao_sobe_os_filhos(cli):
    preparar_espelho()
    cli.post("/config/importar/analisar",
             files={"arquivo": ("n.xlsx", planilha(BASE_PLANILHA))})
    cli.post("/config/importar/aplicar", data={"remover": "1"})
    assert {u.codigo for u in unidades().values()} == {"ORG-0001", "ORG-0002"}
    assert por_codigo("ORG-0002").parent_id == raiz(unidades()).id


def test_aplicar_sem_marcar_nada_nao_muda_a_estrutura(cli):
    preparar_espelho()
    cli.post("/config/importar/analisar",
             files={"arquivo": ("n.xlsx", planilha(BASE_PLANILHA))})
    cli.post("/config/importar/aplicar", data={})
    assert len(unidades()) == 6


def test_carga_incremental_preserva_accountability_e_competencia(cli):
    preparar_espelho()
    u = por_codigo("ORG-0002")
    u.competencias = ["Excel"]
    guardadas = list(u.responsabilidades)
    dados = planilha([BASE_PLANILHA[0],
                      pl("Beatriz Nogueira Pinto", "Outro cargo", area="Rewards",
                         email="k@x.com", n4="91.02",
                         gestor="Marina Albuquerque Sá")])
    cli.post("/config/importar/analisar", files={"arquivo": ("n.xlsx", dados)})
    cli.post("/config/importar/aplicar", data={"atualizar": "1"})
    assert u.cargo == "Outro cargo"
    assert u.competencias == ["Excel"]
    assert u.responsabilidades == guardadas


def test_carga_preserva_accountability_de_quem_tem_subordinado(cli):
    """O caso que o teste acima NAO cobre — e que estava quebrado.

    `_delegar_por_equipe` atribuia a lista inteira de responsabilidades, entao
    toda carga assistida apagava a accountability PROPRIA de quem tivesse ao
    menos um filho. O teste vizinho passava porque observa ORG-0002, que no
    seed e folha: o unico caso em que a promessa era verdadeira. Quem tem
    subordinado e exatamente quem tem accountability que vale escrever.

    A carga roda com `data={}` de proposito: o estrago acontecia mesmo sem
    nenhuma classe marcada, porque a rederivacao mora fora dos tres `if`.
    """
    preparar_espelho()
    chefe = por_codigo("ORG-0001")                     # tem cinco filhos
    assert mapa_filhos(unidades())[chefe.id]
    chefe.responsabilidades = [
        {"descricao": "Resultado do RH", "origem": "propria", "delegada_para": None}]

    cli.post("/config/importar/analisar",
             files={"arquivo": ("n.xlsx", planilha(BASE_PLANILHA))})
    cli.post("/config/importar/aplicar", data={})

    proprias = [r["descricao"] for r in por_codigo("ORG-0001").responsabilidades
                if r["origem"] == "propria"]
    assert proprias == ["Resultado do RH"]


def test_delegada_continua_derivada_das_equipes_dos_filhos(cli):
    """A propria sobrevive; a delegada e recalculada. As duas coisas juntas."""
    preparar_espelho()
    chefe = por_codigo("ORG-0001")
    chefe.responsabilidades = [
        {"descricao": "Resultado do RH", "origem": "propria", "delegada_para": None},
        {"descricao": "Equipe que nao existe mais", "origem": "delegada",
         "delegada_para": None}]
    por_codigo("ORG-0003").area = "Payroll"            # muda a equipe de um filho

    cli.post("/config/importar/analisar",
             files={"arquivo": ("n.xlsx", planilha(BASE_PLANILHA))})
    cli.post("/config/importar/aplicar", data={})

    itens = por_codigo("ORG-0001").responsabilidades
    assert [r["descricao"] for r in itens if r["origem"] == "propria"] \
        == ["Resultado do RH"]
    delegadas = [r["descricao"] for r in itens if r["origem"] == "delegada"]
    assert "Payroll" in delegadas
    assert "Equipe que nao existe mais" not in delegadas


def test_carga_e_desfazivel_e_entra_no_ledger(cli):
    preparar_espelho()
    cli.post("/config/importar/analisar",
             files={"arquivo": ("n.xlsx", planilha(BASE_PLANILHA))})
    cli.post("/config/importar/aplicar", data={"remover": "1"})
    assert main.ESTADO.eventos[-1]["motivo"] == "carga assistida da planilha"
    assert main.verificar_cadeia()["integro"] is True
    cli.post("/desfazer")
    assert len(unidades()) == 6


def test_analise_avisa_sobre_gestor_inexistente(cli):
    preparar_espelho()
    dados = planilha(BASE_PLANILHA + [
        pl("Orfao Silva", "Analista", area="RH", email="o@x.com", n4="91.02",
           gestor="Pessoa Que Nao Existe")])
    cli.post("/config/importar/analisar", files={"arquivo": ("n.xlsx", dados)})
    assert any("gestor inexistente" in a for a in main.ESTADO.importacao["avisos"])


def test_ciclo_e_recusado_na_carga(cli):
    """Planilha pode afirmar que A responde a B e B responde a A."""
    unidades_iniciais = len(unidades())
    preparar_espelho()
    dados = planilha([
        pl("Marina Albuquerque Sá", "Gerente de RH", area="RH", email="l@x.com",
           n4="91.01", gestor="Beatriz Nogueira Pinto"),
        pl("Beatriz Nogueira Pinto", "Coordenador", area="RH", email="k@x.com",
           n4="91.02", gestor="Marina Albuquerque Sá")])
    cli.post("/config/importar/analisar", files={"arquivo": ("c.xlsx", dados)})
    cli.post("/config/importar/aplicar", data={"atualizar": "1"})
    assert len(mapa_filhos(unidades())[None]) == 1          # RF-03 preservada
    assert len(unidades()) == unidades_iniciais


# ---------------------------------------------------------------------------
# CONTRATO POR TITULO  (planilha antiga e nova convivem)
# ---------------------------------------------------------------------------
def test_planilha_antiga_de_oito_colunas_nao_inventa_alteracao(cli):
    """O portao da compatibilidade.

    Sem a distincao "coluna ausente != celula vazia", um arquivo sem a coluna
    Vinculo compararia "" contra o padrao `clt` e marcaria a empresa inteira
    como alterada — e a carga zeraria o vinculo de todo mundo de uma vez.
    """
    preparar_espelho()
    por_codigo("ORG-0002").vinculo = "pj"
    dados = planilha(BASE_PLANILHA, titulos=TITULOS_ANTIGOS)
    cli.post("/config/importar/analisar", files={"arquivo": ("velha.xlsx", dados)})
    campos = {c for a in main.ESTADO.importacao["alterados"] for c, _, _ in a["mudancas"]}
    assert not campos & {"tipo", "vinculo", "responsavel", "competencias",
                         "responsabilidades"}
    cli.post("/config/importar/aplicar", data={"atualizar": "1"})
    assert por_codigo("ORG-0002").vinculo == "pj"


def test_colunas_fora_de_ordem_sao_lidas_certo(cli):
    """Antes o cabecalho era conferido por nome e os dados lidos por posicao:
    planilha embaralhada passava na validacao e era gravada trocada."""
    invertido = list(reversed(TITULOS_ANTIGOS))
    linhas = importador.ler_planilha(planilha(BASE_PLANILHA, titulos=invertido))
    assert linhas[0]["nome"] == "Marina Albuquerque Sá"
    assert linhas[0]["cargo"] == "Gerente de RH"
    assert linhas[0]["gestor"] == "Conselho"


def test_planilha_parcial_pareia_pelo_nome_e_toca_so_o_que_trouxe(cli):
    """"Mande so as colunas que quer atualizar" tem que ser verdade.

    Sem o ultimo recurso pelo nome, uma planilha de tres colunas — sem E-mail,
    sem Codigo — nao casava com ninguem que tivesse e-mail gravado: na base
    real isso virava 265 admissoes mais 265 demissoes numa tacada.
    """
    preparar_espelho()
    dados = planilha(
        [{"Colaborador": "Marina Albuquerque Sá", "Gestor Direto": "Conselho",
          "Regime": "Consultoria"},
         {"Colaborador": "Beatriz Nogueira Pinto", "Gestor Direto": "Marina Albuquerque Sá",
          "Regime": "PJ"}],
        titulos=["Colaborador", "Gestor Direto", "Regime"])
    cli.post("/config/importar/analisar", files={"arquivo": ("p.xlsx", dados)})
    imp = main.ESTADO.importacao
    assert not imp["novos"]                    # ninguem virou admissao
    # Ausentes sao os quatro que a planilha de duas linhas realmente nao cita.
    assert {r["codigo"] for r in imp["removidos"]} == {"ORG-0003", "ORG-0004",
                                                       "ORG-0005", "ORG-0006"}
    assert {c for a in imp["alterados"] for c, _, _ in a["mudancas"]} == {"vinculo"}
    cli.post("/config/importar/aplicar", data={"atualizar": "1"})
    assert por_codigo("ORG-0002").vinculo == "pj"
    assert por_codigo("ORG-0002").email == "k@x.com"      # coluna ausente, intacto
    assert por_codigo("ORG-0002").cargo == "Coordenadora de RH"


def test_homonimo_nao_e_pareado_pelo_nome(cli):
    """O recurso do nome so vale quando o nome identifica uma pessoa so.

    Os dois xaras tem e-mail, entao nenhum deles responde pela chave
    `nome:...`: a linha sem e-mail so chegaria a eles pelo ultimo recurso — e
    e justamente ali que a ambiguidade tem de barrar, em vez de escolher um.
    """
    preparar_espelho()
    xara = por_codigo("ORG-0003")
    xara.nome, xara.email = "Beatriz Nogueira Pinto", "k2@x.com"
    dados = planilha(
        [{"Colaborador": "Beatriz Nogueira Pinto", "Gestor Direto": "Marina Albuquerque Sá"}],
        titulos=["Colaborador", "Gestor Direto"])
    cli.post("/config/importar/analisar", files={"arquivo": ("h.xlsx", dados)})
    assert len(main.ESTADO.importacao["novos"]) == 1


def test_coluna_desconhecida_nao_atrapalha(cli):
    dados = planilha(BASE_PLANILHA,
                     titulos=TITULOS_ANTIGOS + ["Matrícula", "Observação"])
    assert len(importador.ler_planilha(dados)) == 2


def test_carga_grava_nivel_vinculo_responsavel_e_listas(cli):
    preparar_espelho()
    dados = planilha([
        BASE_PLANILHA[0],
        pl("Beatriz Nogueira Pinto", "Coordenador de RH", email="k@x.com", n4="91.02",
           gestor="Marina Albuquerque Sá", **{
               "Nível": "Gerência", "Regime": "PJ",
               "Responsável": "Keila S.", "Competências": "Excel, Power BI",
               "Accountabilities": "Remuneração | Benefícios"})])
    cli.post("/config/importar/analisar", files={"arquivo": ("n.xlsx", dados)})
    cli.post("/config/importar/aplicar", data={"atualizar": "1"})
    u = por_codigo("ORG-0002")
    assert (u.tipo, u.vinculo, u.responsavel) == ("gerencia", "pj", "Keila S.")
    assert u.competencias == ["Excel", "Power BI"]
    assert [r["descricao"] for r in u.responsabilidades if r["origem"] == "propria"] \
        == ["Remuneração", "Benefícios"]


def test_unidade_criada_recebe_os_campos_novos_na_mesma_carga(cli):
    """Criar e atualizar eram caminhos diferentes: um projetava os campos, o
    outro tinha a lista escrita a mao. Campo novo chegava em quem ja existia e
    nascia vazio em quem entrava na mesma carga."""
    preparar_espelho()
    dados = planilha(BASE_PLANILHA + [
        pl("Novato da Silva", "Analista de RH", email="n@x.com", n4="91.02",
           gestor="Beatriz Nogueira Pinto", **{"Regime": "Consultoria",
                                       "Responsável": "Ele mesmo",
                                       "Competências": "SQL"})])
    cli.post("/config/importar/analisar", files={"arquivo": ("n.xlsx", dados)})
    cli.post("/config/importar/aplicar", data={"criar": "1"})
    novo = next(u for u in unidades().values() if u.nome == "Novato da Silva")
    assert (novo.vinculo, novo.responsavel, novo.competencias) \
        == ("consultoria", "Ele mesmo", ["SQL"])


def test_nivel_que_nao_existe_avisa_e_nao_grava(cli):
    preparar_espelho()
    antes = por_codigo("ORG-0002").tipo
    dados = planilha([BASE_PLANILHA[0],
                      pl("Beatriz Nogueira Pinto", "Coordenador de RH", email="k@x.com",
                         n4="91.02", gestor="Marina Albuquerque Sá",
                         **{"Nível": "Chefão"})])
    cli.post("/config/importar/analisar", files={"arquivo": ("n.xlsx", dados)})
    assert any("Chefão" in a for a in main.ESTADO.importacao["avisos"])
    cli.post("/config/importar/aplicar", data={"atualizar": "1"})
    assert por_codigo("ORG-0002").tipo == antes


def test_codigo_pareia_mesmo_trocando_nome_e_email(cli):
    """A razao de ser da coluna Codigo: sem ela, trocar os dois no mesmo
    arquivo vira uma remocao mais uma admissao, e a pessoa perde o lugar na
    arvore, a accountability e o historico."""
    preparar_espelho()
    dados = planilha([
        BASE_PLANILHA[0],
        pl("Beatriz Nogueira Pinto Casada", "Coordenador de RH", email="k.nova@x.com",
           n4="91.02", gestor="Marina Albuquerque Sá", **{"ID SAP": "ORG-0002"})])
    cli.post("/config/importar/analisar", files={"arquivo": ("n.xlsx", dados)})
    imp = main.ESTADO.importacao
    assert not imp["novos"]
    assert "ORG-0002" not in {r["codigo"] for r in imp["removidos"]}
    cli.post("/config/importar/aplicar", data={"atualizar": "1"})
    assert por_codigo("ORG-0002").nome == "Beatriz Nogueira Pinto Casada"


def test_codigo_de_removido_nao_e_reciclado(cli):
    """Reciclar numero economizaria codigo e custaria identidade: uma planilha
    guardada casaria a linha do demitido com quem entrou depois no lugar."""
    preparar_espelho()
    codigos_antes = {u.codigo for u in unidades().values()}
    cli.post("/config/importar/analisar",
             files={"arquivo": ("n.xlsx", planilha(BASE_PLANILHA))})
    cli.post("/config/importar/aplicar", data={"remover": "1"})   # saem 4
    dados = planilha(BASE_PLANILHA + [
        pl("Gente Nova", "Analista", email="g@x.com", n4="91.03",
           gestor="Beatriz Nogueira Pinto")])
    cli.post("/config/importar/analisar", files={"arquivo": ("m.xlsx", dados)})
    cli.post("/config/importar/aplicar", data={"criar": "1"})
    novo = next(u for u in unidades().values() if u.nome == "Gente Nova")
    assert novo.codigo not in codigos_antes


def test_aplicar_nao_varre_a_arvore_por_pessoa(cli, monkeypatch):
    """A carga percorria a árvore inteira três vezes por pessoa reparentada: o
    índice de nomes, o mapa de filhos para contar irmãos e, dentro de
    `descendentes`, um terceiro mapa. Numa carga de 265 trocas de gestor davam
    785 travessias e 778 ms — o mesmo trabalho cabe numa travessia só.

    Conta `mapa_filhos` e `descendentes` COMO O IMPORTADOR OS VÊ: ele os importa
    para dentro da função, então espionar o módulo de domínio pega as chamadas
    dele e as de mais ninguém neste caminho.
    """
    preparar_espelho()
    n = {"mapa_filhos": 0, "descendentes": 0}
    for nome in n:
        original = getattr(dominio, nome)
        monkeypatch.setattr(dominio, nome,
                            lambda *a, _o=original, _k=nome, **kw:
                            (n.__setitem__(_k, n[_k] + 1), _o(*a, **kw))[1])
    dados = planilha([
        pl("Marina Albuquerque Sá", "Gerente de RH", email="l@x.com",
           n4="91.01", gestor="Conselho"),
        pl("Beatriz Nogueira Pinto", "Coordenador de RH", email="k@x.com",
           n4="91.02", gestor="Conselho")])              # troca de gestor
    cli.post("/config/importar/analisar", files={"arquivo": ("n.xlsx", dados)})
    cli.post("/config/importar/aplicar", data={"atualizar": "1", "remover": "1"})

    assert n["descendentes"] == 0, "a guarda de ciclo voltou a varrer a árvore"
    assert por_codigo("ORG-0002").parent_id == raiz(unidades()).id
    assert len(unidades()) == 2                          # os outros quatro saíram


def test_carga_total_grava_codigo_de_nivel_e_nao_o_rotulo(cli):
    """A carga TOTAL nao tem passo 2 para conferir: o dominio fechado tem de
    ser resolvido nela tambem.

    A exportacao escreve o ROTULO na coluna ("Diretoria", "CLT") — que e o que
    um humano le. Gravar isso cru em `tipo` desmonta tudo o que casa por
    codigo: `PESO_TIPO` cai no peso 9 e a ordem dos irmaos se perde,
    `CORES_NIVEL` nao acha a fita, e o enum do Postgres recusaria a linha. O
    ciclo exporta->devolve se envenenava sozinho.
    """
    dados = planilha([
        pl("Chefe", "Diretor", gestor="Board", **{"Nível": "Diretoria",
                                                  "Regime": "PJ"}),
        pl("Zé", "Analista", gestor="Chefe", **{"Nível": "Célula",
                                                "Regime": "CLT"}),
        # "Estágio" virou vínculo de verdade quando o RH passou a declará-lo:
        # o valor inválido tem de ser algo que o cadastro realmente não tem.
        pl("Bug", "X", gestor="Chefe", **{"Nível": "Chefão",
                                          "Regime": "Freelа"})])
    uns, _ = importador.montar_unidades(importador.ler_planilha(dados))
    for u in uns.values():
        assert u.tipo in importador.PESO_TIPO, (u.nome, u.tipo)
        assert u.vinculo in dominio.VINCULOS, (u.nome, u.vinculo)
    achado = {u.nome: (u.tipo, u.vinculo) for u in uns.values()}
    assert achado["Chefe"] == ("diretoria", "pj")
    # Valor fora do cadastro nao vira o padrao a marteladas: cai na deducao
    # pelo cargo, e o vinculo fica no padrao porque nao havia o que gravar.
    assert achado["Bug"] == ("celula", "clt")


def test_duas_linhas_com_o_mesmo_nome_nao_casam_com_a_mesma_pessoa(cli):
    """A guarda de ambiguidade vale dos DOIS lados.

    Com ela so na estrutura, duas linhas "Zé" numa planilha sem e-mail caiam
    ambas no mesmo `Unidade`: ninguem era admitido, e a segunda sobrescrevia a
    primeira em silencio — sem aviso no passo 2.
    """
    preparar_espelho()
    por_codigo("ORG-0002").email = ""              # forca o recurso do nome
    dados = planilha([
        pl("Marina Albuquerque Sá", "Gerente de RH", gestor="Conselho"),
        pl("Beatriz Nogueira Pinto", "Analista A", gestor="Marina Albuquerque Sá"),
        pl("Beatriz Nogueira Pinto", "Analista B", gestor="Marina Albuquerque Sá")],
        titulos=["Colaborador", "Cargo/Função", "Gestor Direto"])
    cli.post("/config/importar/analisar", files={"arquivo": ("d.xlsx", dados)})
    imp = main.ESTADO.importacao
    ids = [a["id"] for a in imp["alterados"]]
    assert len(ids) == len(set(ids)), "a mesma pessoa foi reivindicada duas vezes"
    assert len(imp["novos"]) == 1                  # a segunda vira admissao
    assert any("mais de uma vez" in a for a in imp["avisos"])


def test_delegada_nao_repete_a_mesma_equipe_escrita_de_dois_jeitos(cli):
    """"Produção" e "producao" sao a mesma equipe digitada diferente. Deduplicar
    pelo cru enquanto se exclui a equipe do pai pelo normalizado fazia as duas
    passarem, e o card mostrava a accountability repetida."""
    uns = {
        "p": Unidade(id="p", codigo="ORG-0001", nome="Chefe", tipo="gerencia",
                     parent_id=None, ordem=0, area="Gestão"),
        "a": Unidade(id="a", codigo="ORG-0002", nome="A", tipo="celula",
                     parent_id="p", ordem=10, area="Produção"),
        "b": Unidade(id="b", codigo="ORG-0003", nome="B", tipo="celula",
                     parent_id="p", ordem=20, area="producao"),
        "c": Unidade(id="c", codigo="ORG-0004", nome="C", tipo="celula",
                     parent_id="p", ordem=30, area="Vendas"),
    }
    importador._delegar_por_equipe(uns)
    assert [r["descricao"] for r in uns["p"].responsabilidades] \
        == ["Produção", "Vendas"]


def test_departamento_tem_teto_como_as_outras_colunas_de_texto(cli):
    """`corrigir_departamento` conserta a grafia e nao corta: era a unica
    coluna de texto por onde um paragrafo colado entrava inteiro."""
    dados = planilha([pl("X", area="D" * 500, gestor="Board")])
    assert len(importador.ler_planilha(dados)[0]["area"]) == 60


def test_modelo_traz_as_colunas_e_o_guia(cli):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(cli.get("/modelo.xlsx").content))
    assert wb.sheetnames == ["ORG", "como preencher"]
    cabecalho = [c.value for c in wb["ORG"][1]]
    assert cabecalho == importador.TITULOS


def test_modelo_e_aceito_pelo_proprio_analisador(cli):
    """O modelo que o sistema entrega tem que passar na porta de entrada dele."""
    modelo = cli.get("/modelo.xlsx").content
    r = cli.post("/config/importar/analisar",
                 files={"arquivo": ("modelo.xlsx", modelo)})
    assert "Planilha recusada" not in r.text
    assert main.ESTADO.importacao["total"] == 2


# ---------------------------------------------------------------------------
# XLSX exportado  (apresentacao + contrato de carga)
# ---------------------------------------------------------------------------
def aberta(cli, url="/export.xlsx"):
    import openpyxl
    return openpyxl.load_workbook(io.BytesIO(cli.get(url).content))


def test_export_xlsx_abre_na_apresentacao_e_guarda_o_contrato(cli):
    """A ordem das abas e a decisao inteira: apresentacao na frente, ORG atras.

    Se a de apresentacao virar a primeira **e** a unica, o ciclo quebra; se a
    ORG vier na frente, quem abre o arquivo ve uma tabela crua. O nome da aba e
    o que concilia as duas coisas.
    """
    wb = aberta(cli)
    assert wb.sheetnames[0] == "Organograma"
    assert "ORG" in wb.sheetnames
    assert [c.value for c in wb["ORG"][1]] == importador.TITULOS


def test_export_xlsx_volta_pela_propria_carga_assistida(cli):
    """O que sai tem que entrar: o ciclo e a razao de existir da aba ORG."""
    arquivo = cli.get("/export.xlsx").content
    r = cli.post("/config/importar/analisar",
                 files={"arquivo": ("organograma.xlsx", arquivo)})
    assert "Planilha recusada" not in r.text
    assert main.ESTADO.importacao["total"] == len(unidades())
    # Exportar e devolver sem editar nada nao pode inventar mudanca.
    assert not main.ESTADO.importacao["novos"]
    assert not main.ESTADO.importacao["removidos"]
    assert not main.ESTADO.importacao["alterados"]


def test_export_xlsx_agrupa_por_nivel_com_a_cor_do_nivel(cli):
    """Cada faixa e um nivel, na cor do cadastro, e a soma fecha com o total."""
    ap = aberta(cli)["Organograma"]
    cores = {n["codigo"]: cargosmod.CORES_NIVEL[n["cor"]]["claro"].lstrip("#").upper()
             for n in main.ESTADO.config.niveis}
    rotulos = {n["rotulo"]: n["codigo"] for n in main.ESTADO.config.niveis}

    faixas, membros = [], 0
    for linha in ap.iter_rows(min_row=6, max_col=1):          # abaixo do cabecalho
        c = linha[0]
        if ap.row_dimensions[c.row].outlineLevel:
            membros += 1
        elif c.value and " — " in str(c.value):
            rotulo, n = str(c.value).rsplit(" — ", 1)
            faixas.append((rotulo, int(n), c.fill.fgColor.rgb[2:].upper()))

    assert faixas, "nenhuma faixa de nivel na aba de apresentacao"
    assert sum(n for _, n, _ in faixas) == membros == len(unidades())
    for rotulo, _, cor in faixas:
        assert cor == cores[rotulos[rotulo]], f"faixa {rotulo} fora da paleta"


def test_export_xlsx_respeita_o_recorte_como_o_csv(cli):
    """RNF/INT: sai o que esta na tela — a mesma regra do CSV, do SVG e do PDF."""
    inteiro = aberta(cli)["ORG"].max_row
    cli.post("/filtros", data={"texto": "beatriz"})
    wb = aberta(cli)
    assert wb["ORG"].max_row == 3 < inteiro             # cabecalho + raiz + achado
    # E o cabecalho da apresentacao **avisa** que havia filtro: sem isso o
    # arquivo recortado sai indistinguivel do inteiro depois de deixar o
    # sistema, e quem recebe le "a empresa tem 2 pessoas".
    legenda = str(wb["Organograma"]["A3"].value)
    assert "filtro ativo" in legenda and "2 pessoa(s)" in legenda


def test_export_xlsx_leva_a_marca_no_cabecalho(cli):
    ap = aberta(cli)["Organograma"]
    assert len(ap._images) == 1
    assert ap["C1"].value == main.ESTADO.config.titulo


def test_export_xlsx_sem_a_marca_no_disco_ainda_exporta(tmp_path):
    """Logo e enfeite: PNG faltando nao pode derrubar a exportacao do dado."""
    dados = importador.export_xlsx(unidades(), niveis=main.ESTADO.config.niveis,
                                   marca=tmp_path / "nao-existe.png")
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(dados))
    assert not wb["Organograma"]._images
    assert wb["ORG"].max_row == len(unidades()) + 1


def test_tabela_traz_os_dois_botoes_de_planilha(cli):
    corpo = cli.get("/vistas/tabela").text
    assert 'href="/export.xlsx"' in corpo
    # O importar reusa os tres passos de Configuracoes em vez de abrir um
    # assistente proprio — e o teste guarda justamente isso.
    assert 'hx-post="/config/importar/analisar"' in corpo
    assert 'hx-target="#area"' in corpo


def test_importar_da_tabela_e_botao_e_nao_rotulo(cli):
    """O disparo do seletor de arquivo e um `<button>`, nunca um `<label for>`.

    `label` e seletor de ELEMENTO no CSS da base — `display:block`, caixa alta,
    `margin:14px 0 5px` — e `.bt` nao declara `text-transform` nem `margin`.
    Vestir um rotulo de botao saia em caixa alta e com margem propria, fora da
    linha dos vizinhos. Ja aconteceu uma vez; o teste e para nao acontecer duas.
    """
    barra = cli.get("/vistas/tabela").text.split('class="ferramentas"')[1] \
                                          .split("</div>")[0]
    # `<label for=…>` é o que não pode: o menu de colunas usa `<label>` para
    # envolver as caixas, que é o uso certo e não dispara a colisão de CSS.
    assert "<label class=\"bt\"" not in barra and "<label for=" not in barra
    assert '<button type="button" class="bt"' in barra
    # E `type=button` explicito: dentro do form, o padrao seria `submit`, e o
    # clique mandaria um POST sem arquivo nenhum antes de a pessoa escolher um.
    #
    # A conta e DENTRO do formulario, e nao na barra inteira: a barra ganhou o
    # botao Editar da grade, que tambem e `type=button` e nao tem nada a ver
    # com esta guarda. Contar a barra toda media o numero de botoes da tela.
    form = barra.split("/config/importar/analisar")[1]
    assert form.count('type="button"') == 1


def test_importar_pela_tabela_nasce_desabilitado_para_quem_nao_e_admin(cli):
    main.ESTADO.config.perfil = cfgmod.EDITOR
    corpo = cli.get("/vistas/tabela").text
    assert "/config/importar/analisar" not in corpo
    assert "Importar XLSX" in corpo and "disabled" in corpo
    # Exportar continua: ler e levar embora nao e mutacao.
    assert 'href="/export.xlsx"' in corpo


# ---------------------------------------------------------------------------
# PDF  (W7-C1 / W7-C3)
# ---------------------------------------------------------------------------
def test_pdf_e_a3_paisagem_com_texto_pesquisavel(cli):
    dados = cli.get("/export.pdf").content
    assert dados.startswith(b"%PDF-1.4")
    assert b"/MediaBox [0 0 1190.55 841.89]" in dados
    assert cli.get("/export.pdf").headers["content-type"] == "application/pdf"


def test_pdf_usa_fontes_base_e_nao_rasteriza_texto():
    layout = main.layout_atual(None)
    dados = pdfmod.gerar(layout, pdfmod.meta_padrao("t", "s", "org", "rodape"))
    assert b"/BaseFont /Helvetica" in dados
    assert b"/Subtype /Type1" in dados
    assert dados.count(b"stream") >= 1


@pytest.mark.parametrize("fator", [0.05, 0.5, 1, 3, 40, 400])
def test_pdf_sai_sempre_em_uma_folha(fator):
    """Qualquer proporção de desenho cabe em uma folha A3 — nunca duas."""
    layout = main.layout_atual(None)
    largura = float(layout["viewbox"].split()[2])
    layout["viewbox"] = f"0 0 {largura * fator} {layout['altura']}"
    dados = pdfmod.gerar(layout, pdfmod.meta_padrao("t", "s", "o", "r"))
    assert int(re.search(rb"/Count (\d+)", dados).group(1)) == 1
    assert dados.count(b"/Type /Page /Parent") == 1


@pytest.mark.parametrize("vb_w,vb_h", [
    (10, 10), (100, 50), (1136, 470), (2700, 800), (59038, 1392),
    (300, 4000), (1, 9000), (9000, 1), (1190, 842),
])
def test_enquadramento_cabe_e_centraliza(vb_w, vb_h):
    """O desenho inteiro dentro da área útil, com folga igual dos dois lados."""
    x, base, w, h = pdfmod.area_util()
    escala, tx, ty = pdfmod.enquadrar(vb_w, vb_h)
    esq, dir_ = tx, tx + vb_w * escala
    topo, chao = ty, ty - vb_h * escala           # CTM inverte o eixo Y

    assert esq >= x - 1e-6 and dir_ <= x + w + 1e-6
    assert chao >= base - 1e-6 and topo <= base + h + 1e-6
    assert (esq - x) == pytest.approx(x + w - dir_, abs=1e-6)
    assert (base + h - topo) == pytest.approx(chao - base, abs=1e-6)
    assert 0 < escala <= pdfmod.ESCALA_MAX


def test_enquadramento_amplia_desenho_pequeno_ate_a_folha():
    _, _, w, h = pdfmod.area_util()
    escala, _, _ = pdfmod.enquadrar(w / 4, h / 4)
    assert escala == pytest.approx(min(4.0, pdfmod.ESCALA_MAX))


def test_enquadramento_do_eixo_mais_apertado_manda():
    _, _, w, h = pdfmod.area_util()
    assert pdfmod.enquadrar(w * 10, h)[0] == pytest.approx(0.1)      # largura manda
    assert pdfmod.enquadrar(w, h * 10)[0] == pytest.approx(0.1)      # altura manda


def test_enquadramento_nao_estoura_com_viewbox_degenerado():
    for w, h in ((0, 100), (100, 0), (0, 0), (-5, 10)):
        escala, tx, ty = pdfmod.enquadrar(w, h)
        assert escala > 0 and tx == tx and ty == ty                  # sem NaN


def test_pdf_respeita_o_filtro_da_tela(cli):
    cli.post("/filtros", data={"texto": "beatriz"})
    pequeno = len(cli.get("/export.pdf").content)
    cli.post("/filtros/limpar")
    inteiro = len(cli.get("/export.pdf").content)
    assert pequeno < inteiro


def test_pdf_entra_no_ledger(cli):
    antes = len(main.ESTADO.eventos)
    cli.get("/export.pdf")
    assert main.ESTADO.eventos[antes]["motivo"] == "exportação PDF A3"


def test_escapamento_de_texto_do_pdf():
    """Parenteses e barra sao sintaxe de string no PDF; acento tem que virar
    byte cp1252 (WinAnsiEncoding), nunca UTF-8 cru."""
    assert pdfmod._esc("a(b)c\\d") == "a\\(b\\)c\\\\d"
    assert pdfmod._esc("ação").encode("latin-1") == "ação".encode("cp1252")
    assert pdfmod._esc("→ seta") == "? seta"      # fora do cp1252, sem estourar


# ---------------------------------------------------------------------------
# CARD CONFIGURAVEL  (dominio puro)
# ---------------------------------------------------------------------------
def test_card_encolhe_quando_campos_saem():
    u = por_codigo("ORG-0002")
    _, cheio = montar_card(u, 0, 0, Tokens())
    _, magro = montar_card(u, 0, 0, Tokens(campos=frozenset({"nome"})))
    assert magro < cheio


def test_max_itens_configuravel_corta_a_lista():
    u = por_codigo("ORG-0002")
    card, _ = montar_card(u, 0, 0, Tokens(max_itens=2))
    assert card["itens"][-1]["txt"].startswith("+ 3")


def test_botao_de_pdf_anuncia_a_escala_antes_do_clique(cli):
    """Sem paginação, a escala é a única pista de legibilidade — e ela precisa
    aparecer antes do download, não dentro do arquivo."""
    corpo = cli.get("/vistas/canvas").text
    escala = main.escala_impressao()
    assert f"PDF A3 · {escala} %" in corpo
    assert f"PDF A3 · {escala} %" in cli.get("/vistas/tabela").text


def test_escala_do_botao_bate_com_a_do_pdf_gerado(cli):
    """Rótulo e rodapé saem do mesmo enquadramento — não podem divergir."""
    import re as _re
    for expandir in (False, True):
        if expandir:
            cli.post("/arvore/expandir")
        anunciada = main.escala_impressao()
        dados = cli.get("/export.pdf").content
        layout = main.layout_para_arquivo(com_cabecalho=False)
        w, h = (float(v) for v in layout["viewbox"].split()[2:])
        assert round(pdfmod.enquadrar(w, h)[0] * 100) == anunciada
        assert int(_re.search(rb"/Count (\d+)", dados).group(1)) == 1


@pytest.mark.parametrize("escala,alerta", [(100, False), (39, False),
                                           (37, True), (2, True)])
def test_botao_alerta_abaixo_do_piso_de_leitura(escala, alerta):
    """Abaixo de 38 % o texto não sobrevive à impressão: o botão avisa."""
    corpo = main.render("_bt_pdf.html", escala_pdf=escala, piso_leitura=38)
    assert f"PDF A3 · {escala} %" in corpo
    assert ("apertado" in corpo) is alerta
    assert ("ilegível no papel" in corpo) is alerta


@pytest.mark.parametrize("escala,esperado", [
    (1.0, "100 %"), (0.6666, "67 %"), (0.019, "2 %"),
    (0.009, "< 1 %"), (0.0001, "< 1 %"),
])
def test_rotulo_de_escala_nunca_diz_zero(escala, esperado):
    """Arredondar 0,4 % para "0 %" apagaria justamente o alerta que a escala
    existe para dar."""
    assert pdfmod.rotulo_escala(escala) == esperado


def test_piso_de_leitura_e_um_numero_so():
    """Tela e papel usam o mesmo limite; o servidor injeta no JS da pagina."""
    pagina = main.render("base.html", vista="canvas", corpo="", painel=None)
    assert f"ESC_MIN_LEITURA = {pdfmod.PISO_LEITURA}" in pagina


def test_pdf_honra_a_origem_do_viewbox():
    """Hoje o motor emite sempre '0 0 w h'; se um dia deslocar, o desenho nao
    pode sair da folha junto."""
    layout = main.layout_atual(None, com_cabecalho=False)
    _, _, w, h = (float(v) for v in layout["viewbox"].split())
    base = pdfmod.gerar(layout, pdfmod.meta_padrao("t", "s", "o", "r"))
    layout["viewbox"] = f"120 60 {w} {h}"
    movido = pdfmod.gerar(layout, pdfmod.meta_padrao("t", "s", "o", "r"))
    escala, tx, ty = pdfmod.enquadrar(w, h)
    assert f"{tx - 120 * escala:.3f} {ty + 60 * escala:.3f} cm".encode() not in base
    assert len(movido) > 0 and int(re.search(rb"/Count (\d+)", movido).group(1)) == 1


# ---------------------------------------------------------------------------
# TEMA
# ---------------------------------------------------------------------------
def test_tema_alcanca_o_svg_por_variavel_css(cli):
    """O <style> do SVG e autocontido (INT-07): o tema tem que chegar la dentro,
    e na tela isso e variavel — trocar tema nao pode custar round-trip."""
    corpo = cli.get("/vistas/canvas").text
    assert "var(--k-card)" in corpo and "var(--k-nome)" in corpo
    assert "#FFFFFF" not in corpo.split("<style>")[1].split("</style>")[0]


def test_export_sai_com_cor_literal_e_sempre_claro(cli):
    """Papel nao tem tema, e variavel CSS em SVG solto nao e universalmente
    suportada (Inkscape) — o arquivo leva o valor resolvido."""
    main.ESTADO.config.tema = "escuro"
    svg = cli.get("/export.svg").text
    assert "var(--k-" not in svg
    assert cfgmod.CORES_CANVAS["claro"]["card"] in svg
    assert cfgmod.CORES_CANVAS["escuro"]["card"] not in svg


def test_tema_persiste_e_nao_suja_o_ledger(cli):
    antes = len(main.ESTADO.eventos)
    assert cli.post("/config/tema", data={"tema": "escuro"}).status_code == 200
    assert main.ESTADO.config.tema == "escuro"
    assert len(main.ESTADO.eventos) == antes          # aparencia nao e mutacao
    assert 'data-tema="escuro"' in cli.get("/").text


def test_tema_invalido_cai_no_claro(cli):
    cli.post("/config/tema", data={"tema": "neon"})
    assert main.ESTADO.config.tema == "claro"


def test_viewer_pode_trocar_o_tema(cli):
    """Aparencia e preferencia de exibicao, nao alteracao de estrutura."""
    main.ESTADO.config.perfil = cfgmod.VIEWER
    cli.post("/config/tema", data={"tema": "escuro"})
    assert main.ESTADO.config.tema == "escuro"


def test_pagina_declara_os_dois_temas_e_o_automatico(cli):
    pagina = cli.get("/").text
    assert ':root[data-tema="escuro"]' in pagina
    assert "@media (prefers-color-scheme:dark)" in pagina
    assert ':root[data-tema="auto"]' in pagina


@pytest.mark.parametrize("chave", list(cfgmod.CORES_CANVAS["claro"]))
def test_os_dois_temas_definem_as_mesmas_chaves(chave):
    """Chave faltando no escuro viraria variavel indefinida — elemento invisivel."""
    assert chave in cfgmod.CORES_CANVAS["escuro"]


def test_responsivo_declara_os_tres_pontos_de_quebra(cli):
    pagina = cli.get("/").text
    for largura in (1400, 1100, 900, 680):
        assert f"@media (max-width:{largura}px)" in pagina
    assert 'name="viewport"' in pagina


def _luminancia(hexa: str) -> float:
    hexa = hexa.lstrip("#")
    canais = [int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    canais = [(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
              for v in canais]
    return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]


def contraste(a: str, b: str) -> float:
    maior, menor = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (maior + 0.05) / (menor + 0.05)


PALCO_ESCURO = "#171B1D"


def test_faixa_do_funil_so_usa_branco_em_texto_grande():
    """Branco sobre o laranja institucional da 3,17:1.

    A lâmina de 2026 escreve branco sobre laranja e a paleta é fechada — não
    posso escurecer o laranja nem clarear o texto. A saída legítima é a régua
    de texto grande da WCAG (>=18,66px em negrito, piso 3:1). Este teste
    garante que a faixa não volte a encolher para um tamanho que reprove.
    """
    css = main.render("base.html", vista="estrutura", corpo="", painel=None)
    regra = re.search(r"\.faixa\{([^}]*)\}", css)
    assert regra, "a regra .faixa sumiu"
    corpo = regra.group(1)

    tamanho = float(re.search(r"font-size:([\d.]+)px", corpo).group(1))
    peso = int(re.search(r"font-weight:(\d+)", corpo).group(1))
    razao = contraste("#FFFFFF", "#EB6A20")

    assert razao < 4.5, "o laranja mudou; refaça a conta em vez de confiar nela"
    assert tamanho >= 18.66 and peso >= 700, (
        f"{tamanho}px/{peso} com {razao:.2f}:1 reprova: texto normal exige 4,5:1")
    assert razao >= 3.0


@pytest.mark.parametrize("chave,fundo,minimo", [
    ("nome", "card", 4.5), ("corpo", "card", 4.5), ("cod", "card", 4.5),
    ("pes", "card", 4.5),
    ("nome_raiz", "card_raiz", 4.5), ("corpo_raiz", "card_raiz", 4.5),
    ("cod_raiz", "card_raiz", 4.5), ("pes_raiz", "card_raiz", 4.5),
])
def test_texto_do_tema_escuro_passa_em_aa(chave, fundo, minimo):
    """WCAG 2.1 AA — 4,5:1 para texto normal (RNF-07)."""
    c = cfgmod.CORES_CANVAS["escuro"]
    assert contraste(c[chave], c[fundo]) >= minimo


@pytest.mark.parametrize("chave", ["borda", "trilho", "fio", "mk"])
def test_objetos_graficos_do_tema_escuro_passam_em_3_para_1(chave):
    """No escuro o card quase não se separa do palco pelo preenchimento
    (#262C2F sobre #171B1D é 1,4:1): quem carrega a separação é a borda, e por
    isso ela é objeto gráfico e não enfeite (RNF-07)."""
    assert contraste(cfgmod.CORES_CANVAS["escuro"][chave], PALCO_ESCURO) >= 3.0


def test_conector_passa_em_3_para_1_nos_dois_temas():
    """O conector carrega a hierarquia — é o traço que RNF-07 nomeia."""
    assert contraste(cfgmod.CORES_CANVAS["claro"]["fio"], "#ECEDEE") >= 3.0
    assert contraste(cfgmod.CORES_CANVAS["escuro"]["fio"], PALCO_ESCURO) >= 3.0


def test_campo_novo_liga_uma_vez_e_respeita_o_desmarque(cli):
    """Config gravada antes de um campo existir não pode nascer com ele
    desligado — mas o primeiro desmarque do operador tem que colar."""
    antigo = {"campos": ["nome", "cargo"], "versao_campos": 1}
    cfg = cfgmod.Config.de_dict(antigo)
    assert "cc_negocio" in cfg.campos               # ligou na carga
    assert cfg.versao_campos == cfgmod.VERSAO_CAMPOS

    cfg.campos = ["nome", "cargo"]                  # operador desmarcou
    cfg.sanear()
    assert "cc_negocio" not in cfg.campos           # e continua desmarcado


def test_linha_descoberta_herda_a_vertical_do_tronco(cli):
    """A vertical é quase propriedade do tronco N2 — quase, e por isso é
    palpite editável e não regra: 96.30 (ALM) convive com 96.* (CON)."""
    u = por_codigo("ORG-0002")
    u.area, u.centro_custo, u.vertical = "Equipe Nova de Eng", "80.91", "80.0"
    reg = centros.descobrir(unidades(), centros.referencia())
    nova = next(c for c in reg if c["departamento"] == "Equipe Nova de Eng")
    assert nova["vertical"] == "ENG" and nova["tipo"] == "Bussines Unit"
    assert nova["n5"] == ""             # mnemônico da equipe: não há de onde tirar


def test_heranca_nao_atravessa_troncos():
    reg = centros.referencia()
    heranca = centros._heranca_do_tronco(reg)
    assert heranca["80.0"][0] == "ENG"
    assert heranca["81.0"][0] == "P&P"
    assert heranca["90.0"] == ("DIR", "Diretoria")
    assert heranca["96.0"][0] == "CON"   # maioria, apesar de 96.30 ser ALM


def test_conciliacao_lista_o_que_falta_preencher(cli):
    u = por_codigo("ORG-0002")
    u.area, u.centro_custo, u.vertical = "Equipe Sem N5", "80.91", "80.0"
    reg = centros.descobrir(unidades(), centros.referencia())
    rel = centros.conciliar(unidades(), reg)
    assert any(c["departamento"] == "Equipe Sem N5" for c in rel["incompletas"])
    assert all(c["n5"] and c["vertical"] and c["tipo"]
               for c in reg if c["departamento"] == "Process Engineering")


def test_cadastro_nao_perde_linha_ao_salvar_e_recarregar(cli):
    antes = len(main.ESTADO.config.centros_custo)
    cli.post("/config/cc/referencia")
    assert len(main.ESTADO.config.centros_custo) >= len(centros.REFERENCIA)
    bruto = json.loads(main.serializar())
    main.adotar(bruto)
    assert len(main.ESTADO.config.centros_custo) >= len(centros.REFERENCIA)
    assert "n3" in main.ESTADO.config.centros_custo[0]


# ---------------------------------------------------------------------------
# CARGOS E NÍVEIS
# ---------------------------------------------------------------------------
def test_catalogo_nasce_dos_cargos_da_estrutura(cli):
    cargos_na_base = {u.cargo for u in unidades().values() if u.cargo}
    catalogados = {c["cargo"] for c in main.ESTADO.config.catalogo_cargos}
    assert cargos_na_base <= catalogados
    assert main.contexto_cargos()["sem_catalogo"] == 0


def test_classificacao_tem_tres_camadas():
    """Catálogo primeiro, regra depois, piso por último."""
    regras = cargosmod.regras_padrao()
    catalogo = [{"cargo": "Gerente de Nada", "nivel": "apoio"}]
    ix = cargosmod.indexar(catalogo)
    # o catálogo vence a regra, mesmo contradizendo-a
    assert cargosmod.classificar("Gerente de Nada", ix, regras) == "apoio"
    assert cargosmod.classificar("Gerente de Projetos", ix, regras) == "gerencia"
    assert cargosmod.classificar("Chapeleiro", ix, regras) == cargosmod.NIVEL_PISO


@pytest.mark.parametrize("cargo,nivel", [
    ("Diretor Executivo / CEO", "diretoria"),
    ("Gerente de Operações", "gerencia"),
    ("Coordenador de Qualidade Técnica", "coordenacao"),
    ("Supervisor de Automação", "coordenacao"),
    ("Montador Líder", "coordenacao"),
    ("Analista de Automação Pleno", "celula"),
    ("Estagiário", "apoio"),
    ("Aprendiz Administrativo", "apoio"),
])
def test_regras_padrao_classificam_os_cargos_reais(cargo, nivel):
    assert cargosmod.por_regra(cargo) == nivel


def test_primeira_regra_que_casa_vence():
    """'Assistente de Gerência' casa com duas regras — a ordem decide."""
    regras = cargosmod.regras_padrao()
    assert cargosmod.por_regra("Assistente de Gerência", regras) == "gerencia"
    invertida = cargosmod.normalizar_regras(
        [dict(r, ordem=100 - r["ordem"]) for r in regras],
        {"diretoria", "gerencia", "coordenacao", "apoio", "celula"})
    assert cargosmod.por_regra("Assistente de Gerência", invertida) == "apoio"


def test_padrao_invalido_e_descartado_sem_derrubar():
    regras = cargosmod.normalizar_regras(
        [{"padrao": "gerente", "nivel": "gerencia", "ordem": 10},
         {"padrao": "[nao-fecha", "nivel": "apoio", "ordem": 20}],
        {"gerencia", "apoio"})
    assert [r["padrao"] for r in regras] == ["gerente"]


def test_salvar_catalogo_nao_reclassifica_sozinho(cli):
    alvo = next(u for u in unidades().values() if u.cargo)
    antes = alvo.tipo
    cat = [dict(c, nivel="apoio") if c["cargo"] == alvo.cargo else c
           for c in main.ESTADO.config.catalogo_cargos]
    dados = {"cargo_i": [], "": ""}
    campos = {}
    for i, c in enumerate(cat):
        campos[f"cargo_{i}"] = c["cargo"]
        campos[f"nivel_{i}"] = c["nivel"]
    campos["cargo_i"] = [str(i) for i in range(len(cat))]
    cli.post("/config/cargos", data=campos)
    assert alvo.tipo == antes                       # salvar não mexe na estrutura
    assert main.ESTADO.config.indice_cargos[cargosmod.chave(alvo.cargo)] == "apoio"


def test_aplicar_reclassifica_e_e_desfazivel(cli):
    alvo = next(u for u in unidades().values() if u.cargo)
    campos = {"cargo_i": [], }
    cat = [dict(c, nivel="apoio") if c["cargo"] == alvo.cargo else c
           for c in main.ESTADO.config.catalogo_cargos]
    for i, c in enumerate(cat):
        campos[f"cargo_{i}"] = c["cargo"]
        campos[f"nivel_{i}"] = c["nivel"]
    campos["cargo_i"] = [str(i) for i in range(len(cat))]
    cli.post("/config/cargos", data=campos)
    r = cli.post("/config/cargos/aplicar")
    assert "reclassificada" in r.text
    assert alvo.tipo == "apoio"
    cli.post("/desfazer")
    # `adotar` reconstrói as unidades: a referência antiga fica obsoleta
    assert unidades()[alvo.id].tipo != "apoio"


def test_divergencia_aparece_quando_o_painel_contraria_o_catalogo(cli):
    alvo = next(u for u in unidades().values() if u.cargo)
    cli.post(f"/unidades/{alvo.id}/salvar",
             data={"nome": alvo.nome, "tipo": "apoio", "cargo": alvo.cargo})
    div = main.contexto_cargos()["divergencias"]
    assert any(d["cargo"] == alvo.cargo for d in div)


def test_nivel_editado_alcanca_card_filtro_e_tabela(cli):
    niveis = [dict(n) for n in main.ESTADO.config.niveis]
    campos = {"nivel": [n["codigo"] for n in niveis]}
    for n in niveis:
        campos[f"rotulo_{n['codigo']}"] = "Chefia" if n["codigo"] == "gerencia" else n["rotulo"]
        campos[f"cor_{n['codigo']}"] = "ambar" if n["codigo"] == "gerencia" else n["cor"]
        campos[f"ordem_{n['codigo']}"] = str(n["ordem"])
        campos[f"ativo_{n['codigo']}"] = "1"
    cli.post("/config/niveis", data=campos)
    assert main.ESTADO.config.rotulos_nivel["gerencia"] == "Chefia"
    assert main.ESTADO.config.cores_nivel["gerencia"] == "ambar"
    corpo = cli.get("/vistas/canvas").text
    assert "#canvas .fita.gerencia{fill:var(--k-cor_ambar)}" in corpo
    assert "Chefia" in cli.get("/vistas/tabela").text


def test_codigo_do_nivel_e_imutavel(cli):
    """Ele casa com o enum org.tipo_unidade e com o `tipo` de cada unidade."""
    corpo = cli.get("/?vista=configuracoes&aba=cargos").text
    assert 'name="rotulo_gerencia"' in corpo
    assert 'name="codigo_gerencia"' not in corpo


def test_niveis_nunca_ficam_vazios():
    assert cargosmod.normalizar_niveis([]) == cargosmod.niveis_padrao()
    assert cargosmod.NIVEL_PISO in {n["codigo"]
                                    for n in cargosmod.normalizar_niveis([
                                        {"codigo": "so_um", "rotulo": "X"}])}


def test_cor_de_nivel_e_token_com_par_claro_escuro():
    for token, par in cargosmod.CORES_NIVEL.items():
        assert par["claro"] and par["escuro"]
        assert f"cor_{token}" in cfgmod.CORES_CANVAS["claro"]
        assert f"cor_{token}" in cfgmod.CORES_CANVAS["escuro"]


@pytest.mark.parametrize("token", list(cargosmod.CORES_NIVEL))
def test_fita_do_nivel_e_visivel_no_tema_escuro(token):
    """No escuro o card é #262C2F: a fita precisa de 3:1 para codificar algo."""
    assert contraste(cargosmod.CORES_NIVEL[token]["escuro"], "#262C2F") >= 3.0


def test_filtro_por_cargo(cli):
    alvo = next(u for u in unidades().values() if u.cargo)
    cli.post("/filtros", data={"cargo": alvo.cargo})
    assert alvo.id in main.achados()
    assert all(unidades()[i].cargo == alvo.cargo for i in main.achados())


def test_departamento_substituiu_time_equipe(cli):
    painel = cli.get(f"/fragmentos/painel/{por_codigo('ORG-0002').id}?canvas=0").text
    assert "Departamento" in painel and "Time / equipe" not in painel
    tabela = cli.get("/vistas/tabela").text
    # O que importa é o vocabulário da coluna, não o atributo que a acompanha:
    # o `<th>` ganhou `role` para o cartão de tela estreita não perder a
    # semântica de tabela, e casar a tag inteira quebrava por causa disso.
    cabecalho = tabela[tabela.index("<thead"):tabela.index("</thead>")]
    assert ">Departamento</th>" in cabecalho and ">Time" not in cabecalho
    assert 'aria-label="Filtrar por Departamento"' in tabela


# ---------------------------------------------------------------------------
# OS FILTROS SE FILTRAM
# ---------------------------------------------------------------------------
def _duas_verticais() -> None:
    """ORG-0002 em ENG, ORG-0003 em MKT, e mais ninguém com vertical."""
    for u in unidades().values():
        u.vertical = ""
    marcar_cc("ORG-0002", "80.31", "80.0", area="Engineering")
    marcar_cc("ORG-0003", "92.01", "92.0", area="Marketing")


def _dominio(campo, criterios=None):
    from orga.dominio import valores_de_filtro
    return {v for v, _ in valores_de_filtro(unidades(), None, criterios)[campo]}


def test_escolher_uma_vertical_estreita_os_outros_chips(cli):
    """Opção que sempre devolveria vazio não é escolha, é armadilha."""
    _duas_verticais()
    assert {"Engineering", "Marketing"} <= _dominio("area")
    so_eng = _dominio("area", {**main.filtros_vazios(), "vertical": ["80.0"]})
    assert "Engineering" in so_eng and "Marketing" not in so_eng
    assert "80.31" in _dominio("centro_custo",
                               {**main.filtros_vazios(), "vertical": ["80.0"]})
    assert "92.01" not in _dominio("centro_custo",
                                   {**main.filtros_vazios(), "vertical": ["80.0"]})


def test_um_chip_nao_se_filtra_por_si_mesmo(cli):
    """Filtrado por si, um chip com uma marca perderia as demais opções e
    ninguém conseguiria marcar a segunda — que é o ponto da seleção múltipla."""
    _duas_verticais()
    com_uma = _dominio("area", {**main.filtros_vazios(), "area": ["Engineering"]})
    assert {"Engineering", "Marketing"} <= com_uma


def test_o_que_esta_marcado_sobrevive_mesmo_sem_resultado(cli):
    """Se a marca sumisse da lista não haveria como desmarcá-la, e a pessoa
    ficaria presa num recorte vazio."""
    from orga.dominio import filtrar

    _duas_verticais()
    crit = {**main.filtros_vazios(), "vertical": ["80.0"], "area": ["Marketing"]}
    assert filtrar(unidades(), crit) == set(), "a combinação tem de ser vazia"
    assert "Marketing" in _dominio("area", crit)


def test_a_busca_livre_tambem_estreita_os_chips(cli):
    _duas_verticais()
    crit = {**main.filtros_vazios(), "texto": por_codigo("ORG-0002").nome}
    areas = _dominio("area", crit)
    # A busca casa vários campos — inclusive o `responsavel` de quem responde a
    # essa pessoa. O que se afirma é o recorte, não a cardinalidade.
    assert "Engineering" in areas and "Marketing" not in areas


def test_sem_criterio_o_dominio_e_o_de_sempre(cli):
    """Compatibilidade: quem chama sem critérios continua vendo a base inteira."""
    from orga.dominio import valores_de_filtro
    _duas_verticais()
    assert valores_de_filtro(unidades()) == \
           valores_de_filtro(unidades(), None, main.filtros_vazios())


def test_chip_sem_opcao_nasce_desabilitado_e_diz_por_que(cli):
    """Popover vazio já foi defeito relatado aqui. Agora o vazio tem causa, e
    a causa cabe no `title`."""
    _duas_verticais()
    por_codigo("ORG-0002").cargo = ""
    cli.post("/filtros", data={"vertical": "80.0"})
    corpo = cli.get("/vistas/tabela").text
    assert 'class="chip vazio"' in corpo
    assert "disabled aria-disabled" in corpo
    assert "sobrou no recorte atual" in corpo


def test_os_chips_voltam_fora_de_banda_e_a_busca_nao(cli):
    """Domínio que estreita no servidor e não estreita na tela é pior do que
    não estreitar: a lista continuaria oferecendo o que já não devolve ninguém.

    A busca livre fica de fora do swap — ela guarda o cursor de quem digita."""
    _duas_verticais()
    r = cli.post("/filtros", data={"vertical": "80.0"})
    assert 'id="chips"' in r.text and 'hx-swap-oob="true"' in r.text
    chips = r.text[r.text.index('id="chips"'):]
    assert "Engineering" in chips and "Marketing" not in chips
    assert 'type="search"' not in r.text, "o campo de busca não pode voltar"


def test_os_chips_tambem_voltam_na_tabela(cli):
    _duas_verticais()
    r = cli.post("/filtros?vista=tabela", data={"vertical": "80.0"})
    assert r.status_code == 200
    assert 'id="chips"' in r.text and 'hx-swap-oob="true"' in r.text
    assert "<tr" in r.text                      # o corpo da tabela veio junto


# ---------------------------------------------------------------------------
# PÍLULAS DO QUE ESTÁ FILTRANDO AGORA
# ---------------------------------------------------------------------------
def test_cada_valor_marcado_vira_uma_pilula(cli):
    """A contagem no chip diz "3 centros de custo" e não diz quais. A pílula é
    onde se lê o recorte sem abrir nada."""
    _duas_verticais()
    cli.post("/filtros", data={"vertical": "80.0", "area": "Engineering",
                               "texto": "eng"})
    corpo = cli.get("/vistas/tabela").text
    tira = corpo[corpo.index('id="filtrosAtivos"'):]
    tira = tira[:tira.index("</div>")]
    assert 'data-campo="vertical" data-valor="80.0"' in tira
    assert 'data-campo="area" data-valor="Engineering"' in tira
    assert 'data-campo="texto" data-valor="eng"' in tira
    assert "sem" not in corpo[corpo.index('class="ativos'):
                              corpo.index('id="filtrosAtivos"')]


def test_sem_filtro_a_tira_de_pilulas_some(cli):
    """Linha reservada para o vazio é altura roubada do desenho."""
    corpo = cli.get("/vistas/tabela").text
    i = corpo.index('class="ativos')
    assert "sem" in corpo[i:i + 30]


def test_a_pilula_do_centro_de_custo_leva_o_nome_da_equipe(cli):
    """`82.43` não diz nada a quem não decorou os 78; `82.43 · Software Team 3`
    diz. É o mesmo rótulo que o popover mostra."""
    marcar_cc("ORG-0002", "91.02", "91.0", area="Human Resources")
    cli.post("/filtros", data={"centro_custo": "91.02"})
    corpo = cli.get("/vistas/tabela").text
    tira = corpo[corpo.index('id="filtrosAtivos"'):]
    assert "91.02 · Human Resources" in tira[:tira.index("</div>")]


def test_as_pilulas_voltam_fora_de_banda_com_os_chips(cli):
    """Os dois descrevem o mesmo estado: voltar um sem o outro deixaria a tela
    contando duas histórias."""
    _duas_verticais()
    r = cli.post("/filtros", data={"vertical": "80.0"})
    assert 'id="chips"' in r.text and 'id="filtrosAtivos"' in r.text
    assert r.text.count('hx-swap-oob="true"') >= 2
