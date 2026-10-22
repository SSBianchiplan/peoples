"""
Skills — Descrição de Cargo e Responsabilidades (GEP-FOR-003).

O motor é puro como `tempo.py` e `estrutura.py`: recebe unidades, devolve
dicionários, roda sem servidor e sem estado. Por isso a maior parte destes
testes não sobe o app — sobem só as rotas, no fim.

    pytest testes/test_dcr.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import dcr                                                      # noqa: E402
from orga import main                                                     # noqa: E402
from orga.configuracao import ADMIN, VIEWER                               # noqa: E402
from orga.dominio import Unidade                                          # noqa: E402


def _p(uid, nome, pai, cargo, tipo="celula", area="Eng", cc="80.31",
       competencias=(), responsabilidades=()):
    return Unidade(id=uid, codigo=uid, nome=nome, tipo=tipo, parent_id=pai,
                   ordem=0, cargo=cargo, area=area, centro_custo=cc,
                   competencias=list(competencias),
                   responsabilidades=list(responsabilidades))


def _base():
    """Raiz + oito pessoas cobrindo os sete papéis."""
    return {u.id: u for u in [
        Unidade(id="R", codigo="ORG-RAIZ", nome="Board", tipo="diretoria",
                parent_id=None, ordem=0),
        _p("g", "Gina", "R", "Gerente de Engenharia", tipo="gerencia"),
        _p("c", "Caio", "g", "Coordenador de Projetos", tipo="coordenacao"),
        _p("l", "Lia", "g", "Líder Técnico", tipo="coordenacao"),
        _p("e", "Edu", "g", "Especialista em Automação", tipo="especialista"),
        _p("a", "Ana", "c", "Analista de Projetos",
           competencias=["Automação", "  automação  ", "Excel"]),
        _p("b", "Bia", "c", "Analista de Projetos", competencias=["Excel"]),
        _p("s", "Sam", "l", "Estagiário", tipo="apoio"),
    ]}


def _linhas(unidades=None):
    return dcr.medir(unidades or _base())


# ---------------------------------------------------------------------------
# O papel — liderança técnica não é coordenação
# ---------------------------------------------------------------------------
def test_lider_no_cargo_vira_lideranca_tecnica():
    """A regra de nível junta líder e coordenador no mesmo degrau, e para o
    desenho isso está certo. Para o Skills está errado: quem lidera tecnicamente
    responde por profundidade, quem coordena responde por gente, e misturá-los
    faz a contagem de gestores mentir."""
    assert dcr.papel("coordenacao", "Líder Técnico") == "lideranca"
    assert dcr.papel("coordenacao", "Team Leader") == "lideranca"
    assert dcr.papel("coordenacao", "Coordenador de Projetos") == "coordenacao"


def test_quem_e_as_duas_coisas_conta_como_coordenacao():
    """Mesma escolha que `cargos.REGRAS_PADRAO` já fez: a responsabilidade sobre
    gente é a que muda o desenho da árvore, e é ela que a amplitude mede."""
    assert dcr.papel("coordenacao", "Coordenador e Líder de Squad") == "coordenacao"
    assert dcr.papel("coordenacao", "Supervisor Líder") == "coordenacao"


def test_lider_abaixo_da_coordenacao_ainda_e_lideranca():
    """Cargo fora do catálogo, ou catálogo editado à mão, chega aqui como
    célula — e continua sendo liderança técnica."""
    assert dcr.papel("celula", "Líder de Turno") == "lideranca"
    assert dcr.papel("celula", "Analista") == "execucao"


def test_palavra_dentro_de_outra_nao_conta():
    """`\\b` nas duas pontas: sem isso «Deslizante» viraria liderança."""
    assert dcr.papel("celula", "Operador de Ponte Deslizante") == "execucao"


def test_a_raiz_nao_e_gente():
    """Nó sintético não é empregado, e contá-lo inflaria toda proporção."""
    assert all(l["id"] != "R" for l in _linhas())
    assert len(_linhas()) == 7


# ---------------------------------------------------------------------------
# Tabela cruzada
# ---------------------------------------------------------------------------
def test_marginais_fecham_com_o_total():
    t = dcr.cruzar(_linhas(), "setor", "papel")
    assert sum(t["total_linha"].values()) == t["total"] == 7
    assert sum(t["total_coluna"].values()) == t["total"]
    assert sum(sum(g["celulas"]) for g in t["grade"]) == t["total"]


def test_linha_rara_e_agregada_e_o_total_continua_fechando():
    """Jogar fora o que é raro faria o total parar de fechar, e um total que não
    fecha destrói a confiança na tabela inteira."""
    t = dcr.cruzar(_linhas(), "funcao", "papel", minimo=2)
    assert t["total"] == 7
    assert sum(t["total_linha"].values()) == 7
    assert any(r.startswith("outras") for r in t["linhas"])


def test_ordem_nao_depende_da_ordem_do_dicionario():
    """RNF-02: duas emissões da mesma tabela têm que sair iguais."""
    a = dcr.cruzar(_linhas(), "setor", "papel")
    b = dcr.cruzar(dcr.medir(dict(reversed(list(_base().items())))),
                   "setor", "papel")
    assert a["linhas"] == b["linhas"] and a["colunas"] == b["colunas"]


# ---------------------------------------------------------------------------
# Correlação
# ---------------------------------------------------------------------------
def _grade(celulas: dict) -> dict:
    """Monta o que `cruzar` devolveria, direto das células."""
    linhas = sorted({a for a, _b in celulas})
    colunas = sorted({b for _a, b in celulas})
    return {
        "linhas": linhas, "colunas": colunas, "celulas": celulas,
        "total_linha": {a: sum(v for (x, _y), v in celulas.items() if x == a)
                        for a in linhas},
        "total_coluna": {b: sum(v for (_x, y), v in celulas.items() if y == b)
                         for b in colunas},
        "total": sum(celulas.values()),
    }


def test_independencia_perfeita_da_zero():
    """Tabela em que a proporção de cada coluna é idêntica em toda linha."""
    t = _grade({("a", "x"): 25, ("a", "y"): 25,
                ("b", "x"): 25, ("b", "y"): 25})
    assert dcr.cramer_v(t)["v"] == pytest.approx(0.0, abs=1e-9)


def test_associacao_perfeita_chega_perto_de_um():
    t = _grade({("a", "x"): 50, ("a", "y"): 0,
                ("b", "x"): 0, ("b", "y"): 50})
    m = dcr.cramer_v(t)
    assert m["v"] > 0.95 and m["forca"] == "muito forte"


def test_correcao_de_vies_derruba_a_tabela_esparsa():
    """Com muitas categorias e amostra pequena o V bruto sai perto de 1 por
    esparsidade, não por associação. Sem a correção este relatório mentiria."""
    celulas = {(f"f{i}", "x" if i % 2 else "y"): 1 for i in range(40)}
    m = dcr.cramer_v(_grade(celulas))
    assert m["v_bruto"] > 0.95
    assert m["v"] < m["v_bruto"]


def test_correcao_quase_nao_mexe_na_tabela_densa():
    """Onde a tabela é densa a correção desconta quase nada — é ruído que ela
    tira, e numa tabela cheia quase não há ruído a tirar."""
    t = _grade({("a", "x"): 400, ("a", "y"): 100,
                ("b", "x"): 100, ("b", "y"): 400})
    m = dcr.cramer_v(t)
    assert abs(m["v"] - m["v_bruto"]) < 0.01


def test_celula_rala_marca_a_ressalva():
    """Regra de Cochran: o número sai, com a ressalva colada nele."""
    t = _grade({("a", "x"): 1, ("a", "y"): 1, ("b", "x"): 1, ("b", "y"): 1})
    assert dcr.cramer_v(t)["confiavel"] is False


def test_tabela_degenerada_nao_devolve_numero():
    """Uma coluna só não tem associação a medir, e devolver 0 afirmaria que as
    variáveis são independentes — o que é diferente de não haver o que medir."""
    assert dcr.cramer_v(_grade({("a", "x"): 5, ("b", "x"): 5}))["v"] is None


# ---------------------------------------------------------------------------
# Liderança e amplitude
# ---------------------------------------------------------------------------
def test_lideranca_separa_os_quatro_papeis():
    g = dcr.lideranca(_linhas(), "setor")[0]
    assert (g["gerencia"], g["coordenacao"], g["lideranca"],
            g["especialista"]) == (1, 1, 1, 1)


def test_amplitude_nao_conta_lider_tecnico_como_gestor():
    """Especialista e liderança técnica respondem por profundidade, não por
    gente: entrar no denominador faria a amplitude parecer melhor do que é."""
    g = dcr.lideranca(_linhas(), "setor")[0]
    assert g["gestores"] == 2                      # gerência + coordenação
    assert g["amplitude"] == pytest.approx(7 / 2, abs=0.05)


def test_grupo_sem_gestor_nao_tem_amplitude():
    """Não é zero nem infinito: é grupo sem gestão própria, e o travessão da
    tela diz isso melhor que qualquer número."""
    us = {u.id: u for u in [
        Unidade(id="R", codigo="R", nome="Board", tipo="diretoria",
                parent_id=None, ordem=0),
        _p("a", "Ana", "R", "Analista"),
    ]}
    assert dcr.lideranca(dcr.medir(us), "setor")[0]["amplitude"] is None


def test_amplitude_direta_e_medida_na_arvore():
    """O contraponto da contagem por cadastro."""
    a = {g["id"]: g["diretos"] for g in dcr.amplitude_direta(_base(), _linhas())}
    assert a["g"] == 3 and a["c"] == 2 and a["l"] == 1


# ---------------------------------------------------------------------------
# Matriz de competência
# ---------------------------------------------------------------------------
def test_competencia_repetida_na_mesma_pessoa_conta_uma_vez():
    """«Automação» e «  automação  » são a mesma coisa na cabeça de quem
    digitou, e duas linhas na matriz se ninguém normalizar."""
    m = dcr.matriz_competencias(_linhas())
    automacao = next(c for c in m["competencias"]
                     if c["rotulo"].lower() == "automação")
    assert automacao["n"] == 1


def test_cobertura_vem_antes_de_qualquer_celula():
    """Numa área onde 2 de 7 preencheram, a matriz descreve os 2 — e não a
    área. Sem esse número ao lado, «Excel: 2» seria lido como «só 2 sabem»."""
    m = dcr.matriz_competencias(_linhas())
    assert m["pessoas"] == 7 and m["declararam"] == 2
    assert m["cobertura"] == pytest.approx(28.6, abs=0.1)


def test_corte_do_teto_e_declarado():
    """Tabela que some com dado sem avisar é a mesma coisa que dado errado."""
    m = dcr.matriz_competencias(_linhas(), teto=1)
    assert m["ocultas"] == m["distintas"] - 1 > 0


# ---------------------------------------------------------------------------
# A ficha
# ---------------------------------------------------------------------------
def test_ficha_consolida_as_duas_ocupacoes():
    f = dcr.ficha(dcr.chave_funcao("Analista de Projetos"), _linhas(), _base())
    assert f["n"] == 2
    assert [o["nome"] for o in f["ocupantes"]] == ["Ana", "Bia"]
    assert f["reporta_a"][0]["rotulo"] == "Coordenador de Projetos"


def test_ficha_de_cargo_extinto_e_none_e_nao_erro():
    """Cargo some da base a cada carga da planilha; um link guardado para a
    ficha de um cargo extinto é caso normal, não erro."""
    assert dcr.ficha("cargo que nao existe", _linhas(), _base()) is None


def test_responde_por_sai_da_arvore():
    f = dcr.ficha(dcr.chave_funcao("Coordenador de Projetos"), _linhas(), _base())
    assert f["diretos"] == 2
    assert f["responde_por"][0]["rotulo"] == "Analista de Projetos"


def test_frequencia_distingue_a_pessoa_do_cargo():
    """Um item que aparece em 1 de 12 não é a descrição do cargo — é a descrição
    de uma pessoa —, e a contagem é o que permite ver a diferença."""
    us = _base()
    us["a"].responsabilidades = [{"descricao": "Cronograma", "origem": "propria"}]
    us["b"].responsabilidades = [{"descricao": "Cronograma", "origem": "propria"},
                                 {"descricao": "Só da Bia", "origem": "propria"}]
    f = dcr.ficha(dcr.chave_funcao("Analista de Projetos"), dcr.medir(us), us)
    assert f["proprias"][0] == {"rotulo": "Cronograma", "n": 2}
    assert {"rotulo": "Só da Bia", "n": 1} in f["proprias"]


def test_area_nao_repete_o_mnemonico():
    """O cadastro já carrega a sigla dentro do nome em boa parte das linhas, e
    «PPC – PPC (Production Planning and Control)» é o mnemônico impresso duas
    vezes."""
    gente = [{"n5": "PPC", "setor": "PPC (Production Planning and Control)"}]
    assert dcr._area(gente) == "PPC (Production Planning and Control)"
    assert dcr._area([{"n5": "PRO", "setor": "Engenharia"}]) == "PRO – Engenharia"


def test_area_avisa_quando_a_funcao_existe_em_varios_setores():
    """O formulário tem uma linha só; escolher em silêncio faria a ficha de seis
    áreas parecer a ficha de uma."""
    gente = [{"n5": "", "setor": "Eng"}, {"n5": "", "setor": "Eng"},
             {"n5": "", "setor": "F&B"}]
    assert dcr._area(gente) == "Eng (+1)"


# ---------------------------------------------------------------------------
# O documento e a camada editável
# ---------------------------------------------------------------------------
def test_secoes_saem_na_ordem_do_formulario():
    f = dcr.ficha(dcr.chave_funcao("Analista de Projetos"), _linhas(), _base())
    assert [s["chave"] for s in dcr.documento(f)] == list(dcr.SECOES)


def test_requisito_nunca_e_deduzido():
    """Escolaridade, tempo de experiência e disponibilidade não estão em lugar
    nenhum da estrutura; inventá-los a partir do nível seria o sistema afirmando
    o que não sabe."""
    f = dcr.ficha(dcr.chave_funcao("Analista de Projetos"), _linhas(), _base())
    req = next(s for s in dcr.documento(f) if s["chave"] == "requisitos")
    assert req["origem"] == "vazio" and req["conteudo"] == []


def test_competencia_declarada_vira_sugestao_derivada():
    f = dcr.ficha(dcr.chave_funcao("Analista de Projetos"), _linhas(), _base())
    comp = next(s for s in dcr.documento(f) if s["chave"] == "competencias")
    assert comp["origem"] == "derivado" and "Excel" in comp["conteudo"]


def test_escrito_vence_o_derivado_e_o_derivado_nao_some():
    """O documento imprime um só; a tela mantém o outro ao lado, como sugestão."""
    overlay = [{"cargo": "Analista de Projetos",
                "competencias": "Negociação\nInglês"}]
    f = dcr.ficha(dcr.chave_funcao("Analista de Projetos"), _linhas(), _base(),
                  overlay)
    comp = next(s for s in dcr.documento(f) if s["chave"] == "competencias")
    assert comp["origem"] == "escrito"
    assert comp["conteudo"] == ["Negociação", "Inglês"]
    assert "Excel" in comp["sugestao"]


def test_marcador_digitado_a_mao_nao_vira_texto_do_item():
    """O traço reapareceria dentro do próprio marcador, e a ficha sairia com
    dois bullets na mesma linha."""
    assert dcr.itens("- Um\n* Dois\n• Três\n\n   \n– Quatro") == [
        "Um", "Dois", "Três", "Quatro"]


def test_linha_em_branco_nao_ocupa_lugar_no_overlay():
    """Gravá-la faria o índice marcar como «descrita» uma ficha que ninguém
    escreveu."""
    assert dcr.normalizar_overlay([{"cargo": "X", "missao": "   "}]) == []


def test_overlay_e_indexado_por_cargo_sem_caixa():
    saida = dcr.normalizar_overlay([{"cargo": "Analista", "missao": "a"},
                                    {"cargo": "ANALISTA", "missao": "b"}])
    assert len(saida) == 1 and saida[0]["missao"] == "b"


def test_overlay_trunca_texto_gigante():
    """Entrada de formulário não é dado confiável."""
    saida = dcr.normalizar_overlay([{"cargo": "X", "missao": "a" * 99999}])
    assert len(saida[0]["missao"]) == dcr.LIMITE_OVERLAY


def test_indice_marca_a_funcao_ja_descrita():
    overlay = [{"cargo": "Analista de Projetos", "missao": "Escrita."}]
    ix = {f["chave"]: f["descrita"] for f in dcr.funcoes(_linhas(), overlay)}
    assert ix[dcr.chave_funcao("Analista de Projetos")] is True
    assert ix[dcr.chave_funcao("Estagiário")] is False


# ---------------------------------------------------------------------------
# Markdown do PDF
# ---------------------------------------------------------------------------
def test_markdown_traz_as_quatro_secoes_e_os_valores():
    """Seção sem conteúdo sai com travessão em vez de sumir: formulário
    controlado sem uma seção parece outra versão do documento."""
    f = dcr.ficha(dcr.chave_funcao("Analista de Projetos"), _linhas(), _base())
    md = dcr.markdown(f)
    for rotulo in dcr.ROTULO_SECAO.values():
        assert f"## {rotulo}" in md
    assert "## Valores" in md
    assert "TeamWork" in md and "Analista de Projetos" in md


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def estado_isolado(tmp_path):
    """Parte do seed da SPEC — árvore pequena e fixa — e nunca toca o estado
    real de quem está usando o sistema."""
    main.ARQUIVO_ESTADO = tmp_path / "estado.json"
    main.semear(spec=True)
    main.ESTADO.config.dcr_cargos = []
    main.ESTADO.config.perfil = ADMIN
    main.ESTADO.historico.clear()
    yield


@pytest.fixture
def cli():
    return TestClient(main.app)


def _uma_chave() -> str:
    linhas = dcr.medir(main.ESTADO.unidades, main.mapa_cc())
    return dcr.funcoes(linhas, [])[0]["chave"]


def test_a_vista_esta_na_barra_do_topo(cli):
    r = cli.get("/?vista=dcr")
    assert r.status_code == 200
    assert 'hx-get="/vistas/dcr"' in r.text
    assert "GEP-FOR-003" in r.text


def test_cada_secao_do_modulo_responde(cli):
    for secao in main.SECOES_DCR:
        r = cli.get(f"/vistas/dcr?aba={secao}")
        assert r.status_code == 200, secao


def test_aba_invalida_cai_na_primeira_e_nao_em_erro(cli):
    r = cli.get("/vistas/dcr?aba=inventada")
    assert r.status_code == 200 and "GEP-FOR-003" in r.text


def test_ficha_abre_e_traz_o_formulario(cli):
    r = cli.get(f"/dcr/ficha/{_uma_chave()}")
    assert r.status_code == 200
    assert "GEP-FOR-003" in r.text and "Valores" in r.text


def test_ficha_de_cargo_extinto_responde_200_com_aviso(cli):
    """Link guardado para cargo que saiu da base não pode virar 500."""
    r = cli.get("/dcr/ficha/cargo-que-nao-existe")
    assert r.status_code == 200 and "Cargo fora do recorte" in r.text


def test_gravar_a_ficha_persiste_e_entra_no_ledger(cli):
    chave = _uma_chave()
    eventos = len(main.ESTADO.eventos)
    r = cli.post(f"/dcr/ficha/{chave}",
                 data={"missao": "Sustentar a operação.",
                       "responsabilidades": "- Planejar\n- Medir",
                       "requisitos": "", "competencias": ""})
    assert r.status_code == 200
    gravado = dcr.overlay_de(chave, main.ESTADO.config.dcr_cargos)
    assert gravado["missao"] == "Sustentar a operação."
    assert len(main.ESTADO.eventos) == eventos + 1
    assert "Skills do cargo" in main.ESTADO.eventos[-1]["motivo"]


def test_gravar_entra_no_desfazer(cli):
    """Uma ficha reescrita por engano volta pelo mesmo botão que qualquer outro
    erro."""
    chave = _uma_chave()
    cli.post(f"/dcr/ficha/{chave}", data={"missao": "Primeira.",
                                          "responsabilidades": "",
                                          "requisitos": "", "competencias": ""})
    cli.post("/desfazer")
    assert dcr.overlay_de(chave, main.ESTADO.config.dcr_cargos)["missao"] == ""


def test_visualizador_nao_reescreve_a_descricao_do_cargo(cli):
    """Quem não pode mexer na estrutura não pode reescrever a descrição dela."""
    main.ESTADO.config.perfil = VIEWER
    chave = _uma_chave()
    r = cli.post(f"/dcr/ficha/{chave}", data={"missao": "Não deveria entrar.",
                                              "responsabilidades": "",
                                              "requisitos": "",
                                              "competencias": ""})
    assert r.status_code == 200 and "Ação negada" in r.text
    assert main.ESTADO.config.dcr_cargos == []


def test_pdf_sai_no_formulario_controlado(cli):
    r = cli.get(f"/dcr/ficha/{_uma_chave()}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-1.7")
    assert "attachment" in r.headers["content-disposition"]


def test_pdf_de_cargo_extinto_e_404(cli):
    assert cli.get("/dcr/ficha/nao-existe/pdf").status_code == 404


def test_csv_tem_cabecalho_de_contrato(cli):
    r = cli.get("/dcr.csv")
    assert r.status_code == 200
    assert r.text.lstrip("﻿").splitlines()[0] == (
        "cargo;papel;pessoas;setores;business_units;"
        "competencias_distintas;descrita")


def test_filtrar_de_dentro_do_dcr_devolve_o_corpo_do_dcr(cli):
    """Filtrando de dentro de uma vista que não tem `#canvas`, o htmx não
    reclama de alvo ausente: a filtragem simplesmente não apareceria."""
    r = cli.post("/filtros?vista=dcr", data={"texto": "RH"})
    assert r.status_code == 200 and "GEP-FOR-003" in r.text


def test_a_barra_de_filtros_alveja_o_corpo_do_dcr(cli):
    """O servidor devolver o corpo certo não basta: se a barra não declarar o
    alvo, o htmx troca `#canvas` — que não existe nesta vista — e a filtragem
    não aparece na tela. O teste anterior passava com esta metade quebrada."""
    r = cli.get("/vistas/dcr")
    assert 'hx-post="/filtros?vista=dcr"' in r.text
    assert 'hx-target="#dcrCorpo"' in r.text
    assert 'hx-swap="innerHTML"' in r.text
