"""
Criterios de onda executaveis: W9 (canvas editavel), W2-C2 (guarda de ciclo),
W4 (auditoria), W5-C3/C6 (proibicoes de render), A11Y e contrato de API.

    pytest -q
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import main                                                    # noqa: E402
from orga.dominio import mapa_filhos, raiz                           # noqa: E402


@pytest.fixture(autouse=True)
def estado_isolado(tmp_path):
    """Redireciona a persistencia e parte do seed da SPEC — arvore pequena e fixa."""
    main.ARQUIVO_ESTADO = tmp_path / "estado.json"
    main.semear(spec=True)
    main.ESTADO.historico.clear()
    yield


@pytest.fixture
def cli():
    return TestClient(main.app)


def unidades():
    return main.ESTADO.unidades


def por_codigo(codigo: str):
    return next(u for u in unidades().values() if u.codigo == codigo)


# ---------------------------------------------------------------------------
# W9 — canvas editavel
# ---------------------------------------------------------------------------
def test_W9C1_adicionar_subordinado_abre_o_painel_por_oob(cli):
    alvo = por_codigo("ORG-0002")
    antes = len(unidades())
    r = cli.post(f"/unidades/{alvo.id}/filho")
    assert r.status_code == 200 and len(unidades()) == antes + 1
    assert 'hx-swap-oob="true"' in r.text                        # INT-02
    assert '<aside id="painel"' in r.text
    novo = next(u for u in unidades().values() if u.parent_id == alvo.id)
    assert main.ESTADO.selecionado == novo.id


def test_ficha_completa_abre_com_todos_os_campos_e_vinculos(cli):
    """O botão "Editar ficha" abre o modal com todos os campos do colaborador +
    os vínculos no sistema, e salva pela mesma rota do painel."""
    u = por_codigo("ORG-0002")
    r = cli.get(f"/unidades/{u.id}/ficha?vista=canvas")
    assert r.status_code == 200
    for campo in ('name="nome"', 'name="tipo"', 'name="cargo"', 'name="area"',
                  'name="vertical"', 'name="centro_custo"', 'name="vinculo"',
                  'name="email"', 'name="data_inicio"', 'name="status"',
                  'name="responsabilidades"', 'name="competencias"',
                  # planilha completa (bd_completo_org) — campos organizacionais
                  'name="tipo_mo"', 'name="n2"', 'name="n4"', 'name="n5"',
                  'name="cc_equipe"', 'name="bu"', 'name="tipo_class"',
                  'name="mo_classe"', 'name="categoria_nivel"', 'name="genero"',
                  'name="data_nascimento"'):
        assert campo in r.text, campo
    # nada de remuneração na ficha (LGPD) — o dinheiro fica na view, só Admin
    for proibido in ('name="salario"', 'name="custo', 'name="venda'):
        assert proibido not in r.text, proibido
    assert f"/unidades/{u.id}/salvar" in r.text        # salva pela rota do painel
    assert 'id="ff-nome"' in r.text                    # ids próprios, sem colidir
    assert ("Vínculos" in r.text) or ("Links across" in r.text)   # seção de vínculos


def test_W9C2_prefixo_maior_grava_delegada(cli):
    u = por_codigo("ORG-0002")
    cli.post(f"/unidades/{u.id}/salvar", data={
        "nome": u.nome, "tipo": u.tipo,
        "responsabilidades": "Remuneração\n> Benefícios\n  \n> L.G.R.",
        "competencias": "Excel, Power BI , ,"})
    assert [(r["descricao"], r["origem"]) for r in u.responsabilidades] == [
        ("Remuneração", "propria"), ("Benefícios", "delegada"), ("L.G.R.", "delegada")]
    assert u.competencias == ["Excel", "Power BI"]


def test_W9C3_rebaixar_vira_filho_do_irmao_anterior(cli):
    primeiro, segundo = por_codigo("ORG-0002"), por_codigo("ORG-0003")
    cli.post(f"/unidades/{segundo.id}/rebaixar")
    assert segundo.parent_id == primeiro.id


def test_W9C4_profundidade_cresce_gera_faixa_e_barramento(cli):
    a, b = por_codigo("ORG-0002"), por_codigo("ORG-0003")
    antes = main.layout_atual()["profundidade_max"]
    cli.post(f"/unidades/{b.id}/rebaixar")
    cli.post(f"/unidades/{a.id}/filho")
    depois = main.layout_atual()
    assert depois["profundidade_max"] == antes + 1
    assert len(depois["cotas"]) == antes + 2


def test_W9C5_promover_volta_a_responder_ao_avo(cli):
    pai, filho = por_codigo("ORG-0002"), por_codigo("ORG-0003")
    cli.post(f"/unidades/{filho.id}/rebaixar")
    assert filho.parent_id == pai.id
    cli.post(f"/unidades/{filho.id}/promover")
    assert filho.parent_id == pai.parent_id


def test_W9C6_reordenar_renumera_em_multiplos_de_dez(cli):
    u = por_codigo("ORG-0002")
    cli.post(f"/unidades/{u.id}/reordenar?direcao=direita")
    irmaos = mapa_filhos(unidades())[u.parent_id]
    assert [f.ordem for f in irmaos] == [10, 20, 30, 40, 50]
    assert [f.codigo for f in irmaos][:2] == ["ORG-0003", "ORG-0002"]


def test_W9C7_duplicar_gera_codigo_novo_sem_pessoa(cli):
    o = por_codigo("ORG-0002")
    o.responsavel = "Beatriz Nogueira Pinto"
    cli.post(f"/unidades/{o.id}/duplicar")
    copia = next(u for u in unidades().values() if u.nome.endswith("(cópia)"))
    assert copia.codigo != o.codigo
    assert copia.responsavel == ""
    assert copia.responsabilidades == o.responsabilidades
    assert copia.responsabilidades is not o.responsabilidades      # copia profunda


def test_W9C8_excluir_sobe_os_filhos_ao_avo(cli):
    pai, filho = por_codigo("ORG-0002"), por_codigo("ORG-0003")
    cli.post(f"/unidades/{filho.id}/rebaixar")                     # filho de ORG-0002
    avo = pai.parent_id
    r = cli.delete(f"/unidades/{pai.id}")
    assert pai.id not in unidades()
    assert filho.parent_id == avo
    assert '<aside id="painel"' in r.text                           # painel limpo


def test_W9C9_excluir_raiz_e_recusado(cli):
    r = cli.delete(f"/unidades/{raiz(unidades()).id}")
    assert r.status_code == 200
    assert len(unidades()) == 6
    assert "recusada" in r.text


def test_W9C10_desfazer_restaura_o_snapshot(cli):
    alvo = por_codigo("ORG-0002")
    cli.post(f"/unidades/{alvo.id}/filho")
    assert len(unidades()) == 7
    cli.post("/desfazer")
    assert len(unidades()) == 6


def test_desfazer_sem_historico_avisa(cli):
    assert "Nada a desfazer" in cli.post("/desfazer").text


# ---------------------------------------------------------------------------
# W2-C2 — guarda de ciclo (RF-02 / INV-02)
# ---------------------------------------------------------------------------
def test_W2C2_mover_para_descendente_e_recusado(cli):
    pai, filho = por_codigo("ORG-0002"), por_codigo("ORG-0003")
    cli.post(f"/unidades/{filho.id}/rebaixar")
    r = cli.post(f"/unidades/{pai.id}/mover", data={"destino": filho.id})
    assert r.status_code == 200                                    # INT-06, nao 4xx
    assert "ciclo detectado" in r.text
    assert pai.parent_id != filho.id                               # estrutura intacta


def test_mover_para_si_mesmo_e_recusado(cli):
    u = por_codigo("ORG-0002")
    r = cli.post(f"/unidades/{u.id}/mover", data={"destino": u.id})
    assert "recusado" in r.text and u.parent_id != u.id


def test_painel_nao_oferece_descendente_como_destino(cli):
    pai = por_codigo("ORG-0002")
    filho = por_codigo("ORG-0003")
    cli.post(f"/unidades/{filho.id}/rebaixar")
    corpo = cli.get(f"/fragmentos/painel/{pai.id}").text
    opcoes = re.findall(r'<option value="([0-9a-f]+)"', corpo)
    assert filho.id not in opcoes and pai.id not in opcoes


# ---------------------------------------------------------------------------
# W4 — auditoria
# ---------------------------------------------------------------------------
def test_W4C2_cadeia_integra_apos_sequencia_de_mutacoes(cli):
    u = por_codigo("ORG-0002")
    for _ in range(5):
        cli.post(f"/unidades/{u.id}/filho")
        cli.post(f"/unidades/{u.id}/reordenar?direcao=direita")
    assert main.verificar_cadeia() == {"integro": True, "seq_falha": None,
                                       "total": len(main.ESTADO.eventos)}
    assert cli.get("/api/v1/auditoria/verificar").json()["integro"] is True


def test_W4C3_adulteracao_aponta_o_evento_certo(cli):
    u = por_codigo("ORG-0002")
    for _ in range(3):
        cli.post(f"/unidades/{u.id}/filho")
    main.ESTADO.eventos[2]["payload"]["parent_id"] = "forjado"
    verificacao = main.verificar_cadeia()
    assert verificacao["integro"] is False
    assert verificacao["seq_falha"] == main.ESTADO.eventos[2]["seq"]


def test_ledger_encadeia_cada_elo_ao_anterior(cli):
    u = por_codigo("ORG-0002")
    cli.post(f"/unidades/{u.id}/filho")
    evs = main.ESTADO.eventos
    assert evs[0]["hash_anterior"] == "GENESIS"
    assert all(b["hash_anterior"] == a["hash"] for a, b in zip(evs, evs[1:]))


def test_exportacao_entra_no_ledger(cli):
    """LGPD-05: toda exportacao e registrada."""
    antes = len(main.ESTADO.eventos)
    cli.get("/export.svg")
    cli.get("/export.csv")
    cli.get("/export.json")
    motivos = [e["motivo"] for e in main.ESTADO.eventos[antes:]]
    assert motivos == ["exportação SVG", "exportação CSV", "exportação JSON"]


def test_comandos_de_vista_nao_sujam_o_ledger(cli):
    antes = len(main.ESTADO.eventos)
    cli.post("/orientacao")
    cli.post("/arvore/expandir")
    cli.post("/busca", data={"termo": "beatriz"})
    cli.post(f"/unidades/{por_codigo('ORG-0002').id}/colapsar")
    assert len(main.ESTADO.eventos) == antes


# ---------------------------------------------------------------------------
# W5 — proibicoes de render
# ---------------------------------------------------------------------------
ARQUIVOS_ENTREGUES = [p for p in (list((RAIZ_PROJETO / "web" / "templates").glob("*.html"))
                                  + [RAIZ_PROJETO / "orga" / "main.py",
                                     RAIZ_PROJETO / "orga" / "dominio.py"])]


def test_javascript_da_pagina_compila():
    """Um `const` colidindo com um `let` mata o script inteiro em silêncio:
    a página continua desenhando (é servidor) e só a interação morre. Este
    teste existe porque isso aconteceu."""
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    # Renderizado, nao o fonte: o servidor injeta valores no script (o piso de
    # leitura), e o que precisa compilar e o que chega ao navegador.
    fonte = main.render("base.html", vista="canvas", corpo="", painel=None)
    corpo = fonte.split("<script>")[-1].split("</script>")[0]

    declarados = re.findall(r"^(?:const|let|function)\s+([A-Za-z_$][\w$]*)",
                            corpo, re.M)
    repetidos = {n for n in declarados if declarados.count(n) > 1}
    assert not repetidos, f"identificador declarado duas vezes: {repetidos}"

    if node:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as arq:
            arq.write(corpo)
            caminho = arq.name
        r = subprocess.run([node, "--check", caminho], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_desenho_gigante_nao_ganha_camada_permanente():
    """O navegador fechava sozinho ao abrir com a árvore expandida.

    Com 267 unidades o SVG mede 59 038 x 1 369 px — 80 M px, contra um teto de
    16 384 px por eixo na GPU. `will-change:transform` fixo no #lente e
    `filter:` no #canvas obrigavam o renderer a materializar isso em textura, e
    ele morria. A promoção agora dura só o gesto (classe .gesto)."""
    pagina = main.render("base.html", vista="canvas", corpo="", painel=None)
    css = "\n".join(re.findall(r"<style>(.*?)</style>", pagina, re.S))

    regras = dict(re.findall(r"(#lente|#canvas)\s*\{([^}]*)\}", css))
    assert "#lente" in regras, "a regra base do #lente sumiu — o teste ficaria vazio"
    assert "will-change" not in regras.get("#lente", ""), \
        "#lente promovido em repouso: a textura da árvore inteira volta a ser alocada"
    assert "filter" not in regras.get("#canvas", ""), \
        "filter no #canvas força um buffer do desenho inteiro"
    assert re.search(r"#lente\.gesto\s*\{[^}]*will-change", css), \
        "a promoção durante o gesto sumiu: arrastar volta a repintar por quadro"


def test_W5C3_nenhum_espelhamento_no_codigo():
    """LAY-02: scaleY(-1) e parentes espelhariam glifos, setas e sombreamento."""
    proibido = re.compile(r"scaleY|scale\s*\(\s*1\s*,\s*-1|column-reverse|"
                          r"transform\s*:\s*scale\s*\(\s*-", re.I)
    for arq in ARQUIVOS_ENTREGUES:
        assert not proibido.search(arq.read_text(encoding="utf-8")), arq.name


def test_W5C6_todo_conector_declara_fill_none(cli):
    """LAY-08."""
    svg = cli.get("/export.svg").text
    caminhos = re.findall(r"<path[^>]*>", svg)
    assert caminhos
    assert all('fill="none"' in p for p in caminhos)


def test_W5C4_seed_invertido_poe_a_lideranca_na_base(cli):
    L = main.layout_atual()
    ys = {n["id"]: n["y"] for n in L["nos"]}
    r = raiz(unidades())
    assert ys[r.id] == max(ys.values())
    for f in mapa_filhos(unidades())[r.id]:
        assert ys[r.id] > ys[f.id]


def test_RNF02_duas_renderizacoes_sao_identicas(cli):
    assert cli.get("/export.svg").text == cli.get("/export.svg").text


def test_export_svg_e_autocontido_e_sem_htmx(cli):
    """INT-07: a mesma serializacao serve a tela e ao arquivo."""
    svg = cli.get("/export.svg").text
    assert svg.startswith('<?xml version="1.0"')
    assert "<style>" in svg and "hx-" not in svg
    assert "<image" not in svg                                    # A11Y-07
    assert "Marina Albuquerque Sá" in svg                            # texto selecionavel


# ---------------------------------------------------------------------------
# Acessibilidade
# ---------------------------------------------------------------------------
def test_A11Y02_raiz_e_nivel_1_na_invertida(cli):
    svg = cli.get("/vistas/canvas").text
    primeiro = re.search(r'role="treeitem"[^>]*aria-level="(\d+)"', svg)
    assert primeiro.group(1) == "1"


def test_A11Y03_raiz_e_o_primeiro_no_tabulavel(cli):
    corpo = cli.get("/vistas/canvas").text
    rotulos = re.findall(r'aria-label="([^"]+)"[^>]*hx-get="/fragmentos/painel', corpo)
    assert rotulos[0].startswith("Recursos Humanos")


def test_A11Y04_desc_declara_a_orientacao(cli):
    """A `<desc>` diz em qual orientação o desenho está — em qualquer idioma.

    Cravar a frase em português amarrava um requisito de acessibilidade ao
    idioma vigente: bastava alguém deixar a interface em inglês para o teste
    acusar falha de A11Y onde não havia nenhuma. O que A11Y-04 exige é que a
    descrição exista e **mude** com a orientação.
    """
    def desc(html: str) -> str:
        achado = re.search(r"<desc>(.*?)</desc>", html, re.S)
        assert achado, "o desenho saiu sem <desc>"
        return achado.group(1).strip()

    invertida = desc(cli.get("/vistas/canvas").text)
    cli.post("/orientacao")
    vertical = desc(cli.get("/vistas/canvas").text)
    cli.post("/orientacao")

    assert len(invertida) > 20 and len(vertical) > 20
    assert invertida != vertical, "a descrição não distingue as orientações"


def test_trilho_de_cota_e_invisivel_ao_leitor_de_tela(cli):
    """SIG-03: reforco visual do que ja esta em aria-level."""
    svg = cli.get("/vistas/canvas").text
    assert '<g class="cota" aria-hidden="true">' in svg


def test_contexto_traz_acoes_ja_habilitadas_pelo_servidor(cli):
    """INT-03: o cliente nao decide habilitacao."""
    r = raiz(unidades())
    menu = cli.get(f"/fragmentos/menu/{r.id}").text
    duplicar = re.search(r"duplicar[^>]*>", menu, re.S)
    assert "disabled" in duplicar.group(0)
    assert 'hx-confirm' in menu                                   # INT-04


def test_INT01_fragmentos_do_canvas_so_alvejam_canvas_ou_painel():
    """A navegacao entre vistas alveja #area; o contrato INT-01 rege o canvas."""
    for nome in ("_canvas.html", "_menu.html", "_vista_canvas.html"):
        texto = (RAIZ_PROJETO / "web" / "templates" / nome).read_text(encoding="utf-8")
        assert set(re.findall(r'hx-target="([^"]+)"', texto)) <= {"#canvas", "#painel"}


def test_INT01_a_gaveta_alveja_o_que_existe_na_tela_de_origem(cli):
    """O painel escolhe o alvo em tempo de render, entao o fonte nao serve.

    O htmx resolve `hx-target` ANTES de despachar: apontar para `#canvas` a
    partir da tabela nao falhava com erro, fazia a edicao nao sair do
    navegador. Este teste existe por causa disso.
    """
    uid = por_codigo("ORG-0002").id
    esperado = {"canvas": "#canvas", "tabela": "#painel", "estrutura": "#painel"}
    for origem, alvo in esperado.items():
        url = (f"/fragmentos/painel/{uid}?canvas={1 if origem == 'canvas' else 0}"
               f"&vista={origem}")
        html = cli.get(url).text
        alvos = set(re.findall(r'hx-target="([^"]+)"', html))
        # `#unidadeFicha` é um alvo GLOBAL (mora no base.html, existe em toda
        # vista): o botão "Editar ficha" o alveja sem o risco que o contrato
        # cobre — o de um alvo que só existe na tela de origem. As MUTAÇÕES
        # (salvar/mover), essas sim, seguem presas a #canvas/#painel abaixo.
        assert alvos <= {"#canvas", "#painel", "#unidadeFicha"}, \
            f"{origem}: alvo fora do contrato"
        mutacoes = re.findall(
            r'hx-post="[^"]*/(?:salvar|mover)" hx-target="([^"]+)"', html)
        assert mutacoes and set(mutacoes) == {alvo}, (
            f"{origem}: salvar/mover apontam para {set(mutacoes)}, nao {alvo}")


# ---------------------------------------------------------------------------
# API  (SPEC 8)
# ---------------------------------------------------------------------------
def test_API01_etag_e_304(cli):
    r = cli.get("/api/v1/organograma")
    etag = r.headers["etag"]
    assert cli.get("/api/v1/organograma",
                   headers={"If-None-Match": etag}).status_code == 304


def test_API03_orientacao_nao_altera_a_estrutura(cli):
    a = cli.get("/api/v1/organograma?orientacao=invertida").json()
    b = cli.get("/api/v1/organograma?orientacao=vertical").json()
    assert a["raiz"] == b["raiz"]
    assert a["meta"]["orientacao"] != b["meta"]["orientacao"]


def test_API02_arvore_vem_aninhada_em_ordem_logica(cli):
    corpo = cli.get("/api/v1/organograma").json()
    assert corpo["raiz"]["codigo"] == "ORG-0001"
    assert corpo["raiz"]["profundidade"] == 0
    assert [f["codigo"] for f in corpo["raiz"]["filhos"]] == [
        "ORG-0002", "ORG-0003", "ORG-0004", "ORG-0005", "ORG-0006"]


def test_csv_traz_a_arvore_inteira(cli):
    linhas = cli.get("/export.csv").text.strip().splitlines()
    assert len(linhas) == len(unidades()) + 1
    assert linhas[0].startswith("﻿codigo;nivel;nome")


# ---------------------------------------------------------------------------
# W8-C6 — varredura LGPD
# ---------------------------------------------------------------------------
def test_W8C6_nenhum_campo_de_remuneracao_ou_dado_sensivel():
    """NOBJ-01, LGPD-01/02. 'Remuneração Estratégica' e nome de area, nao dado."""
    proibidos = re.compile(r"salario|salário|remuneracao_|faixa_salarial|cpf|"
                           r"\brg\b|endereco|telefone|biometri|saude|custo_pessoal", re.I)
    from dataclasses import fields
    from orga.dominio import Unidade
    assert not [f.name for f in fields(Unidade) if proibidos.search(f.name)]

    def chaves(no):                       # varre o estado gravado, nao so o modelo
        if isinstance(no, dict):
            return set(no) | {c for v in no.values() for c in chaves(v)}
        if isinstance(no, list):
            return {c for v in no for c in chaves(v)}
        return set()

    assert not [k for k in chaves(json.loads(main.serializar())) if proibidos.search(k)]
    schema = (RAIZ_PROJETO / "orga" / "schema.sql").read_text(encoding="utf-8")
    colunas = re.findall(r"^\s{4}(\w+)\s+\w", schema, re.M)
    assert not [c for c in colunas if proibidos.search(c)]


# ---------------------------------------------------------------------------
# Busca e vistas
# ---------------------------------------------------------------------------
def test_busca_destaca_e_abre_o_caminho(cli):
    alvo = por_codigo("ORG-0004")
    main.ESTADO.colapsados = {raiz(unidades()).id}
    assert len(main.layout_atual()["nos"]) == 1
    cli.post("/filtros", data={"texto": "daniela"})
    L = main.layout_atual()
    assert {n["id"] for n in L["nos"] if n["achou"]} == {alvo.id}
    assert {n["id"] for n in L["nos"]} == {alvo.id, raiz(unidades()).id}
    assert [n["passagem"] for n in L["nos"] if n["id"] != alvo.id] == [True]


def test_busca_curta_nao_filtra(cli):
    cli.post("/filtros", data={"texto": "a"})
    assert main.achados() is None
    assert main.layout_atual()["filtrando"] is False


def test_foco_reduz_o_desenho_a_subarvore(cli):
    alvo = por_codigo("ORG-0002")
    cli.post(f"/unidades/{alvo.id}/focar")
    L = main.layout_atual()
    assert {n["id"] for n in L["nos"]} == {alvo.id}
    assert L["cabecalho"]["escopo"] == alvo.nome
    cli.post("/foco/limpar")
    assert main.layout_atual()["cabecalho"]["escopo"] is None


def test_vistas_respondem(cli):
    for rota in ("/", "/vistas/canvas", "/vistas/tabela", "/vistas/auditoria"):
        assert cli.get(rota).status_code == 200
    assert "Cadeia íntegra" in cli.get("/vistas/auditoria").text


# ---------------------------------------------------------------------------
# Importador
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cargo,esperado", [
    ("Diretor Executivo / CEO", "diretoria"),
    ("Gerente de Operações", "gerencia"),
    ("Coordenador de Engenharia Elétrica", "coordenacao"),
    ("Supervisor de Automação", "coordenacao"),
    ("Montador Líder", "coordenacao"),
    ("Analista de Automação Pleno", "celula"),
    ("Especialista em Automação", "celula"),
    ("Estagiário", "apoio"),
    ("Aprendiz Administrativo", "apoio"),
])
def test_classificacao_de_cargo(cargo, esperado):
    from orga import importador
    assert importador.classificar(cargo) == esperado


@pytest.mark.skipif(not (RAIZ_PROJETO / "planilhas" / "Organograma.xlsx").exists(),
                    reason="planilha ausente")
def test_carga_da_planilha_produz_arvore_unica_e_integra():
    from orga import importador
    from orga.dominio import Unidade, profundidades
    estado = importador.gerar()
    us = {k: Unidade.de_dict(v) for k, v in estado["unidades"].items()}
    assert len(mapa_filhos(us)[None]) == 1                        # RF-03
    prof = profundidades(us)
    assert len(prof) == len(us)                                   # ninguem orfao
    assert raiz(us).nome == "Board"
    assert len({u.codigo for u in us.values()}) == len(us)        # codigo unico
    lideres = [u for u in us.values() if mapa_filhos(us).get(u.id)]
    assert all(all(r["origem"] == "delegada" for r in u.responsabilidades)
               for u in lideres)


def test_invariantes_do_canvas_ficam_no_js():
    """Dois defeitos achados por revisão adversarial, ambos invisíveis em teste
    de servidor. Ficam travados aqui porque o custo de re-introduzi-los é alto:
    quebram o zoom e os atalhos sem erro de console."""
    corpo = main.render("base.html", vista="canvas", corpo="", painel=None)
    js = corpo.split("<script>")[-1].split("</script>")[0]

    # `overflow:hidden` não impede rolagem programática: focar um card fora da
    # vista (seta, Tab, focus()) rola o palco e desloca a âncora do zoom.
    assert "document.addEventListener('scroll'" in js
    assert "p.scrollLeft = p.scrollTop = 0" in js
    assert "tx -= p.scrollLeft" in js

    # preventDefault no mousedown cancela a troca de foco: sem o blur, as teclas
    # de atalho passam a digitar no campo de filtro.
    assert "foco.blur()" in js
    assert js.index("foco.blur()") < js.index("e.preventDefault();\n    puxando")

    # roda: deltaMode precisa ser normalizado nos DOIS ramos, não só no zoom.
    assert "const emPixels" in js
    assert "const k = emPixels(e);" in js

    # popover em camada fixa — a barra de filtros recorta os dois eixos.
    assert ".pop{position:fixed" in corpo


# ---------------------------------------------------------------------------
# ÍCONE DE APLICATIVO — o que o celular usa, e que falha calado
# ---------------------------------------------------------------------------
# Este conjunto quebra de um jeito difícil de notar: nada dá erro, o site abre,
# e só o atalho na tela inicial fica errado — no iPhone com um retrato reduzido
# da página de login, no Android com o ícone recortado. Ninguém percebe olhando
# o navegador, que é onde se olha.
ICONES = {
    "icone-180.png": "iOS, tela inicial — o iPhone só aceita PNG em apple-touch-icon",
    "icone-192.png": "Android/Chrome — o menor dos dois tamanhos que o manifest exige",
    "icone-512.png": "Android/Chrome — o maior; sem os dois o site não é instalável",
    "icone-512-maskable.png": "o recorte do aparelho come o desenho sem margem",
}


def test_os_arquivos_de_icone_existem_e_nao_estao_vazios():
    for nome, porque in ICONES.items():
        alvo = RAIZ_PROJETO / "web" / "marca" / nome
        assert alvo.exists(), f"{nome} não existe — {porque}"
        assert alvo.stat().st_size > 1000, f"{nome} está pequeno demais para ser um PNG válido"
        assert alvo.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", f"{nome} não é PNG"


def test_o_manifest_e_publico_e_aponta_para_icones_que_existem():
    """O celular busca o manifest ANTES de qualquer login. Protegê-lo faria o
    atalho nascer sem ícone, e o 303 para /login não aparece em lugar nenhum."""
    cli = TestClient(main.app)
    r = cli.get("/manifest.webmanifest")
    assert r.status_code == 200, "o manifest não pode exigir sessão"
    assert "manifest" in r.headers["content-type"]
    d = r.json()
    assert d["name"] == "GPlanSiS|Peoples"
    assert d["start_url"] == "/" and d["scope"] == "/", \
        "escopo fora da raiz faria o atalho abrir fora do app"
    tamanhos = {i["sizes"] for i in d["icons"] if i.get("purpose") == "any"}
    assert {"192x192", "512x512"} <= tamanhos, "o Chrome exige 192 e 512 para instalar"
    assert any(i.get("purpose") == "maskable" for i in d["icons"]), \
        "sem maskable o Android recorta o desenho"
    for icone in d["icons"]:
        caminho = RAIZ_PROJETO / "web" / icone["src"].lstrip("/")
        assert caminho.exists(), f"o manifest aponta para {icone['src']}, que não existe"


def test_toda_tela_de_entrada_declara_o_icone_do_celular():
    """Login e troca de senha são as telas que alguém tem aberto quando decide
    "adicionar à tela inicial" — se elas não declaram o ícone, o atalho sai
    errado justamente no caminho mais provável."""
    for nome in ("base.html", "login.html", "senha.html"):
        html = (RAIZ_PROJETO / "web" / "templates" / nome).read_text(encoding="utf-8")
        assert 'rel="apple-touch-icon"' in html, f"{nome}: o iOS ignora o favicon no atalho"
        assert 'rel="manifest"' in html, f"{nome}: sem manifest o Android não usa o ícone"
        assert 'name="theme-color"' in html, f"{nome}: a barra do sistema fica fora da paleta"


def test_o_icone_do_navegador_e_o_mesmo_desenho_em_toda_tela():
    """Três telas, o mesmo favicon: se uma divergir, a aba muda de ícone ao
    navegar, que é o tipo de defeito que ninguém reporta e todos notam."""
    marcas = set()
    for nome in ("base.html", "login.html", "senha.html"):
        html = (RAIZ_PROJETO / "web" / "templates" / nome).read_text(encoding="utf-8")
        m = re.search(r'<link rel="icon" href="([^"]+)"', html)
        assert m, f"{nome} sem favicon"
        marcas.add(m.group(1))
    assert len(marcas) == 1, "o favicon divergiu entre as telas"
    href = marcas.pop()
    # O favicon é um arquivo da marca (/marca/favicon.svg), servido pelo próprio app.
    assert href.startswith("/marca/"), href
    caminho = RAIZ_PROJETO / "web" / href.lstrip("/")
    assert caminho.exists(), f"o favicon aponta para {href}, que não existe"
    svg = caminho.read_text(encoding="utf-8")
    # A marca é a paleta institucional, não uma cor qualquer que passou por ali.
    assert "#2D3336" in svg and "#EB6A20" in svg
