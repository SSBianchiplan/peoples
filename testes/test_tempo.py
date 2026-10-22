"""
Tempo de empresa: a única leitura do sistema que fala do passado.

Puro como `estrutura.py` — recebe unidades, devolve dicionários —, então roda
sem servidor e sem estado. `hoje` entra por parâmetro em todo teste: um
indicador de tempo que depende do relógio da máquina passa hoje e falha em
janeiro.

    pytest testes/test_tempo.py -q
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import dominio                                                  # noqa: E402
from orga import tempo                                                    # noqa: E402
from orga.dominio import Unidade                                          # noqa: E402

HOJE = date(2026, 8, 13)


def _p(uid, nome, pai, inicio, vinculo="clt", tipo="celula", area="Eng"):
    return Unidade(id=uid, codigo=uid, nome=nome, tipo=tipo, parent_id=pai,
                   ordem=0, area=area, vinculo=vinculo, data_inicio=inicio,
                   cargo="Analista")


def _base():
    """Raiz + cinco pessoas cobrindo as cinco faixas."""
    return {u.id: u for u in [
        Unidade(id="R", codigo="ORG-RAIZ", nome="Diretoria", tipo="diretoria",
                parent_id=None, ordem=0),
        _p("a", "Ana", "R", "2026-05-01"),                    # ~0,3 ano
        _p("b", "Bia", "R", "2024-08-13"),                    # 2,0
        _p("c", "Caio", "R", "2022-08-13", vinculo="pj"),     # 4,0
        _p("d", "Davi", "R", "2019-08-13", vinculo="pj"),     # 7,0
        _p("e", "Eva", "R", "2010-08-13", vinculo="estagio"),  # 16,0
    ]}


# ---------------------------------------------------------------------------
# A conta
# ---------------------------------------------------------------------------
def test_a_regua_e_a_do_rh():
    """Dias corridos sobre 365, sem bissexto. É o número que o RH publica, e
    duas contas diferentes para «tempo de empresa» na mesma casa é pior que uma
    aproximada."""
    assert dominio.tempo_de_casa("2013-05-21", HOJE) == pytest.approx(13.238, abs=1e-3)
    assert dominio.tempo_de_casa("2011-05-20", HOJE) == pytest.approx(15.244, abs=1e-3)


def test_sem_data_e_none_e_nunca_zero():
    """Quem entrou hoje tem zero ano de casa; quem não tem data cadastrada não
    tem tempo de casa nenhum. Somar os dois inventaria um recém-contratado."""
    assert dominio.tempo_de_casa("", HOJE) is None
    assert dominio.tempo_de_casa("data ruim", HOJE) is None
    assert dominio.tempo_de_casa(HOJE.isoformat(), HOJE) == 0.0


def test_faixa_e_fechada_embaixo_e_aberta_em_cima():
    """Um ano exato cai em «1 a 3», não em «até 1 ano»."""
    assert dominio.faixa_de_casa(0.99) == "ate1"
    assert dominio.faixa_de_casa(1.0) == "de1a3"
    assert dominio.faixa_de_casa(10.0) == "mais10"
    assert dominio.faixa_de_casa(None) == ""


# ---------------------------------------------------------------------------
# Os indicadores
# ---------------------------------------------------------------------------
def test_a_raiz_nao_entra_na_conta():
    """Ela é nó sintético, não empregado: contá-la como pessoa sem data
    estragaria a contagem de «sem data», que é justamente o número que avisa
    que falta cadastro."""
    linhas = tempo.medir(_base(), HOJE)
    assert len(linhas) == 5
    assert "Diretoria" not in {l["nome"] for l in linhas}
    assert tempo.resumo(linhas)["sem_data"] == 0


def test_media_e_mediana_saem_as_duas():
    """A distância entre elas é a informação: onde divergem muito, há alguém
    sozinho no topo puxando a média."""
    r = tempo.resumo(tempo.medir(_base(), HOJE))
    assert r["pessoas"] == 5 and r["com_data"] == 5
    assert r["mediana"] == pytest.approx(4.0, abs=0.02)
    assert r["media"] > r["mediana"], "a veterana de 16 anos puxa a média"
    assert r["anos_somados"] == pytest.approx(29.3, abs=0.2)


def test_sem_data_fica_de_fora_da_media_e_aparece_contado():
    us = _base()
    us["f"] = _p("f", "Fabi", "R", "")
    r = tempo.resumo(tempo.medir(us, HOJE))
    assert r["pessoas"] == 6 and r["com_data"] == 5 and r["sem_data"] == 1
    assert r["media"] == pytest.approx(
        tempo.resumo(tempo.medir(_base(), HOJE))["media"])


def test_admissao_futura_nao_e_faixa_nem_media():
    """Contratação assinada que ainda não começou é dado, não faixa: misturá-la
    com quem já trabalha responderia outra pergunta."""
    us = _base()
    us["g"] = _p("g", "Gui", "R", "2026-12-01")
    linhas = tempo.medir(us, HOJE)
    assert next(l for l in linhas if l["nome"] == "Gui")["faixa"] == tempo.FUTURO
    r = tempo.resumo(linhas)
    assert r["futuros"] == 1 and r["com_data"] == 5


def test_faixas_saem_na_ordem_da_escala_e_nao_da_contagem():
    """Ordenar por tamanho faria a barra maior mudar de lugar entre dois
    renders, e o desenho deixaria de ser comparável com o do mês passado."""
    faixas = tempo.por_faixa(tempo.medir(_base(), HOJE))
    assert [f["chave"] for f in faixas[:5]] == [c for c, _r, _p in dominio.FAIXAS_CASA]
    assert sum(f["n"] for f in faixas) == 5


def test_grupo_pequeno_nao_ganha_mediana():
    """Com duas pessoas a mediana é a média das duas, e publicá-la como
    indicador convida a decidir sobre ruído."""
    grupos = {g["chave"]: g for g in tempo.por(tempo.medir(_base(), HOJE), "vinculo")}
    assert grupos["pj"]["n"] == 2 and grupos["pj"]["mediana"] is None
    assert grupos["pj"]["media"] is not None, "a média continua saindo"
    assert grupos["estagio"]["n"] == 1 and grupos["estagio"]["mediana"] is None


def test_grupos_empatados_nao_trocam_de_lugar():
    """RNF-02: duas execuções desenham igual. Só a contagem desempataria dois
    grupos do mesmo tamanho pela ordem do dicionário."""
    linhas = tempo.medir(_base(), HOJE)
    uma = [g["chave"] for g in tempo.por(linhas, "vinculo")]
    for _ in range(8):
        assert [g["chave"] for g in tempo.por(linhas, "vinculo")] == uma


def test_ano_sem_ninguem_entra_com_zero():
    """O buraco é informação: um ano sem admissão que sobreviveu até hoje diz
    algo sobre aquele período."""
    anos = {a["ano"]: a["n"] for a in
            tempo.admissoes_por_ano(tempo.medir(_base(), HOJE))}
    assert anos["2010"] == 1 and anos["2026"] == 1
    assert anos["2015"] == 0, "o ano vazio tem de aparecer"
    assert len(anos) == 2026 - 2010 + 1


def test_retencao_por_gestor_pede_equipe_minima():
    us = _base()
    for i in range(3):
        us[f"z{i}"] = _p(f"z{i}", f"Zé {i}", "a", "2026-06-01")
    linhas = tempo.medir(us, HOJE)
    gestores = {g["id"]: g for g in tempo.retencao_por_gestor(us, linhas)}
    # A raiz tem cinco reportes diretos; "Ana" ganhou três. Os dois entram.
    assert set(gestores) == {"R", "a"}
    assert gestores["a"]["n"] == 3
    assert gestores["a"]["media"] < gestores["R"]["media"]
    # Do mais novo para o mais antigo: a vista existe para achar o topo da lista.
    ordem = [g["id"] for g in tempo.retencao_por_gestor(us, linhas)]
    assert ordem[0] == "a"


# ---------------------------------------------------------------------------
# A vista
# ---------------------------------------------------------------------------
def test_a_vista_responde_e_respeita_o_filtro():
    from fastapi.testclient import TestClient
    from orga import main
    cli = TestClient(main.app)

    inteiro = cli.get("/vistas/tempo")
    assert inteiro.status_code == 200
    assert "Tempo de empresa" in inteiro.text

    total = len(main.ESTADO.unidades)
    cli.post("/filtros", data={"vinculo": "estagio"})
    try:
        recortado = cli.get("/vistas/tempo").text
        ctx = main.contexto_tempo()
        assert ctx["resumo"]["pessoas"] < total, \
            "o indicador tem de falar do recorte, não da base inteira"
        assert "filtro ativo" in recortado
    finally:
        cli.post("/filtros/limpar")


# ---------------------------------------------------------------------------
# Gaveta e grade
# ---------------------------------------------------------------------------
def test_a_gaveta_edita_admissao_e_situacao_e_calcula_o_tempo():
    """A data e a situação se editam; o tempo de casa NÃO — ele é a data menos
    hoje, e um campo editável para ele seria um número que discorda de si."""
    from fastapi.testclient import TestClient
    from orga import main
    cli = TestClient(main.app)
    alvo = next(u for u in main.ESTADO.unidades.values() if u.parent_id)
    guardado = (alvo.data_inicio, alvo.status)
    try:
        cli.post(f"/unidades/{alvo.id}/salvar", data={
            "nome": alvo.nome, "tipo": alvo.tipo, "cargo": alvo.cargo,
            "data_inicio": "2020-03-15", "status": "inativo", "vista": "canvas"})
        assert alvo.data_inicio == "2020-03-15" and alvo.status == "inativo"

        painel = cli.get(f"/fragmentos/painel/{alvo.id}?canvas=0").text
        assert 'name="data_inicio"' in painel and 'type="date"' in painel
        assert 'name="status"' in painel
        assert "ano(s) de casa" in painel, "o tempo aparece calculado"
        assert 'name="tempo' not in painel, "e nunca como campo"

        # Data impossível não entra: ela envenenaria o indicador inteiro, e o
        # estrago só apareceria num número que ninguém confere.
        cli.post(f"/unidades/{alvo.id}/salvar", data={
            "nome": alvo.nome, "tipo": alvo.tipo, "data_inicio": "31/02/lixo",
            "status": "ativo", "vista": "canvas"})
        assert alvo.data_inicio == ""
    finally:
        alvo.data_inicio, alvo.status = guardado


def test_o_email_da_gaveta_tem_link_de_escrever():
    """Monta o próprio caso em vez de procurar alguém com e-mail no estado: a
    suíte inteira compartilha `main.ESTADO`, e o seed que outro arquivo deixa
    não tem e-mail nenhum — o teste passava sozinho e quebrava em conjunto."""
    from fastapi.testclient import TestClient
    from orga import main
    cli = TestClient(main.app)
    alvo = next(u for u in main.ESTADO.unidades.values() if u.parent_id)
    guardado = alvo.email
    try:
        alvo.email = "fulano.de.tal@gplansis.com"
        painel = cli.get(f"/fragmentos/painel/{alvo.id}?canvas=0").text
        assert f"mailto:{alvo.email}" in painel
        alvo.email = ""
        assert "mailto:" not in cli.get(f"/fragmentos/painel/{alvo.id}?canvas=0").text,             "sem endereço não há para onde escrever, e o link não aparece"
    finally:
        alvo.email = guardado


def test_a_grade_mostra_so_as_colunas_marcadas():
    """Cabeçalho e corpo leem o mesmo conjunto: duas listas divergiriam na
    primeira coluna nova, e a tabela sairia com dez títulos sobre catorze
    colunas — erro que só aparece ao imprimir."""
    from fastapi.testclient import TestClient
    from orga import main
    cli = TestClient(main.app)
    guardado = list(main.ESTADO.config.colunas_tabela)
    try:
        r = cli.post("/tabela/colunas", data={"col": ["codigo", "nome", "status"]})
        # Só o cabeçalho: o menu de seleção continua listando as dezessete, e
        # procurar o rótulo na página inteira acharia a caixa, não a coluna.
        import re
        cabec = re.findall(r'role="columnheader"[^>]*>([^<]*)<', r.text)
        assert [c for c in cabec if c.strip()] == ["Código", "Unidade / pessoa",
                                                   "Situação"]
        assert len(cabec) == 3 + 1                       # + a coluna da alça

        # Desmarcar tudo volta ao padrão: grade sem coluna nenhuma não é um
        # estado que alguém queira, é o resultado de um engano.
        r = cli.post("/tabela/colunas", data={})
        assert main.ESTADO.config.colunas_tabela == list(main.COLUNAS_TABELA_PADRAO)
    finally:
        main.ESTADO.config.colunas_tabela = guardado


# ---------------------------------------------------------------------------
# O filtro vale de dentro da própria vista
# ---------------------------------------------------------------------------
def test_filtrar_de_dentro_do_tempo_devolve_o_relatorio_e_nao_o_desenho():
    """O htmx resolve `hx-target` antes de despachar, então apontar para
    `#canvas` a partir de uma tela que não tem canvas não dava erro nenhum —
    gravava o recorte no servidor e não trocava nada na tela."""
    from fastapi.testclient import TestClient
    from orga import main
    cli = TestClient(main.app)
    guardado = dict(main.ESTADO.filtros)
    try:
        r = cli.post("/filtros?vista=tempo", data={"vinculo": "clt"})
        assert r.status_code == 200
        assert 'id="canvas"' not in r.text, "devolveu o desenho, não o relatório"
        assert "painel-numeros" in r.text
        # A barra volta como chips fora de banda, e não inteira: trocá-la a
        # cada tecla roubaria o foco de quem está digitando na busca.
        assert 'hx-swap-oob' in r.text
    finally:
        main.ESTADO.filtros = guardado


def test_o_recorte_do_relatorio_nao_arrasta_os_ancestrais():
    """Canvas e tabela precisam do caminho até a raiz para desenhar e indentar.
    Um relatório não — e pagava caro por isso: filtrando Vínculo = CLT, os
    ancestrais traziam prestadores para dentro da média de CLT."""
    from orga import dominio, main

    guardado = dict(main.ESTADO.filtros)
    try:
        alvo = "clt"
        main.ESTADO.filtros = {**main.filtros_vazios(), "vinculo": [alvo]}
        ctx = main.contexto_tempo()
        vinculos = {g["chave"] for g in ctx["por_vinculo"] if g["n"]}
        assert vinculos <= {alvo}, (
            f"o relatório de CLT trouxe {vinculos - {alvo}} junto")
        # E o contrário continua valendo: sem filtro, a base inteira.
        main.ESTADO.filtros = main.filtros_vazios()
        assert main.contexto_tempo()["r"]["pessoas"] == sum(
            1 for u in main.ESTADO.unidades.values() if u.parent_id)
    finally:
        main.ESTADO.filtros = guardado
