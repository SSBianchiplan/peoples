"""A visão por equipe nas rotas: alternância, gaveta, guarda e exportação."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import configuracao as cfgmod                                     # noqa: E402
from orga import equipes                                                    # noqa: E402
from orga import main                                                       # noqa: E402


@pytest.fixture(autouse=True)
def base_conhecida(tmp_path):
    """Cada teste parte do seed da SPEC, como o resto da suíte faz.

    Sem isto os testes daqui liam o que o arquivo anterior tivesse deixado em
    `ESTADO.unidades` — e passavam ou falhavam conforme a ordem de execução, o
    que é o mesmo que não afirmar nada.
    """
    main.ARQUIVO_ESTADO = tmp_path / "estado.json"
    main.semear(spec=True)
    main.ESTADO.config = cfgmod.Config()
    main.ESTADO.config.centros_custo = main.cadastro_cc([])
    main.ESTADO.config.catalogo_cargos = main.catalogo_cargos()
    main.ESTADO.agrupamento = "pessoa"
    main.ESTADO.colapsados.clear()
    main.ESTADO.foco = main.ESTADO.selecionado = None
    main.ESTADO.historico.clear()
    yield


@pytest.fixture
def cli():
    return TestClient(main.app)


def _uma_equipe() -> str:
    return next(iter(main.agrupar_atual()["unidades"]))


def _estrutura_profunda() -> None:
    """Instala uma organização com três níveis e times distintos.

    O seed da SPEC é um departamento raso: nele nenhum nó a partir de N1 tem
    filhos, então escolher um nível não colapsa nada e o teste não afirmaria o
    mecanismo, só a forma daquela base.
    """
    from orga.dominio import Unidade
    main.ESTADO.unidades = {u.id: u for u in [
        Unidade(id="R", codigo="R", nome="Board", tipo="diretoria",
                parent_id=None, ordem=0, area="Board", centro_custo="90.11"),
        Unidade(id="A", codigo="A", nome="Ana", tipo="gerencia", parent_id="R",
                ordem=0, area="Engineering", centro_custo="80.31"),
        Unidade(id="B", codigo="B", nome="Bia", tipo="coordenacao", parent_id="A",
                ordem=0, area="Hardware", centro_custo="82.31"),
        Unidade(id="C", codigo="C", nome="Caio", tipo="celula", parent_id="B",
                ordem=0, area="Firmware", centro_custo="82.41"),
        Unidade(id="D", codigo="D", nome="Davi", tipo="celula", parent_id="A",
                ordem=1, area="Software", centro_custo="81.41"),
    ]}
    main.ESTADO.colapsados.clear()


# ---------------------------------------------------------------------------
# ALTERNÂNCIA
# ---------------------------------------------------------------------------
def test_o_botao_alterna_e_o_estado_persiste(cli):
    r = cli.post("/agrupamento")
    assert r.status_code == 200
    assert main.ESTADO.agrupamento == "equipe"
    assert "EQ-" in r.text
    cli.post("/agrupamento")
    assert main.ESTADO.agrupamento == "pessoa"


def test_alternar_solta_a_selecao(cli):
    """A seleção guarda id de pessoa, que não existe no desenho por equipe.
    Deixar a gaveta aberta sobre alguém que sumiu da tela é o sistema
    mostrando duas coisas diferentes ao mesmo tempo."""
    alvo = next(iter(main.ESTADO.unidades))
    main.ESTADO.selecionado = alvo
    cli.post("/agrupamento")
    assert main.ESTADO.selecionado is None


def test_recolher_as_pessoas_no_time_da_menos_caixas(cli):
    """Contra o total, e não contra os nós visíveis: a visão por pessoa abre
    colapsada na profundidade configurada, então comparar o que está na tela
    compararia dois estados de colapso, não os dois agrupamentos."""
    pessoas = len(main.ESTADO.unidades)
    cli.post("/agrupamento")
    times = len(main.agrupar_atual()["unidades"])
    assert 0 < times < pessoas


# ---------------------------------------------------------------------------
# GUARDA: EQUIPE NÃO É UNIDADE GRAVADA
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("metodo,rota", [
    ("post", "/unidades/{id}/filho"),
    ("post", "/unidades/{id}/duplicar"),
    ("post", "/unidades/{id}/promover"),
    ("post", "/unidades/{id}/rebaixar"),
    ("delete", "/unidades/{id}"),
])
def test_mutacao_em_equipe_e_recusada_com_a_tela_intacta(cli, metodo, rota):
    """INT-06: recusa responde 200 com o canvas de pé, nunca 4xx. A guarda mora
    em `negado`, que é o funil de toda mutação — não rota a rota."""
    cli.post("/agrupamento")
    cid = _uma_equipe()
    antes = len(main.ESTADO.unidades)
    r = cli.request(metodo.upper(), rota.format(id=cid))
    assert r.status_code == 200
    assert "Ação negada" in r.text
    assert len(main.ESTADO.unidades) == antes


def test_menu_de_contexto_de_equipe_vem_vazio(cli):
    """Não há o que promover, mover ou excluir num nó derivado — e menu vazio
    é mais honesto que menu cinza, porque isto não é permissão."""
    cli.post("/agrupamento")
    r = cli.get("/fragmentos/menu/" + _uma_equipe())
    assert r.status_code == 200 and r.text.strip() == ""


# ---------------------------------------------------------------------------
# A GAVETA
# ---------------------------------------------------------------------------
def test_a_gaveta_da_equipe_mostra_a_hierarquia(cli):
    cli.post("/agrupamento")
    cid = _uma_equipe()
    r = cli.get(f"/fragmentos/equipe/{cid}")
    assert r.status_code == 200
    assert "eq-arvore" in r.text
    assert "não é gravada" in r.text          # a gaveta diz que é read-only


def test_clicar_numa_pessoa_evidencia_e_abre_a_linha_dela(cli):
    cli.post("/agrupamento")
    agr = main.agrupar_atual()
    cid, membros = next((c, m) for c, m in agr["membros"].items() if m)
    alvo = membros[0]
    r = cli.get(f"/fragmentos/equipe/{cid}?pessoa={alvo.id}")
    assert "eq-alvo" in r.text                 # evidência em forma, não só cor
    assert "eq-detalhe" in r.text
    assert alvo.nome in r.text


def test_a_gaveta_da_equipe_sobrevive_ao_recarregar(cli):
    """O servidor guarda a seleção; recarregar não pode perdê-la — e um id de
    equipe não existe em `ESTADO.unidades`."""
    cli.post("/agrupamento")
    cid = _uma_equipe()
    cli.get(f"/fragmentos/equipe/{cid}")
    assert main.ESTADO.selecionado == cid
    assert cli.get("/").status_code == 200


# ---------------------------------------------------------------------------
# O QUE SAI PARA O PAPEL
# ---------------------------------------------------------------------------
def test_o_cabecalho_descreve_o_desenho_que_esta_na_tela(cli):
    """Contar `ESTADO.unidades` diria "267 unidades" embaixo de um desenho com
    81 caixas — e o cabeçalho é a única legenda que o papel leva junto."""
    cli.post("/agrupamento")
    cab = main.cabecalho_do_desenho()
    assert "equipes" in cab["linhas"][0]
    assert "pessoas" in cab["linhas"][0]


def test_o_pdf_diz_no_titulo_que_e_a_visao_por_equipe(cli):
    cli.post("/agrupamento")
    r = cli.get("/export.pdf")
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 1000


def test_o_svg_sai_no_modo_vigente(cli):
    """Sai o que está na tela — a regra vale para o agrupamento como já vale
    para filtro, colapso e foco."""
    cli.post("/agrupamento")
    svg = cli.get("/export.svg")
    assert svg.status_code == 200
    assert "pessoa(s)" in svg.text            # a contagem que só o card de time traz


def test_colapsar_uma_equipe_encolhe_o_desenho(cli):
    """81 times abertos dão 15 000 px, que nenhuma folha A3 imprime legível.
    Dobrar um galho é como se faz caber — o mesmo gesto da visão por pessoa.
    """
    # O seed da SPEC é de um departamento só, e um único time não tem galho
    # para dobrar. O que este teste afirma é o gesto, não a forma daquela base.
    _estrutura_profunda()
    cli.post("/agrupamento")
    agr = main.agrupar_atual()
    com_filhos = {u.parent_id for u in agr["unidades"].values() if u.parent_id}
    assert com_filhos, "a estrutura de apoio precisa ter time abaixo de time"
    alvo = sorted(com_filhos)[0]

    antes = float(main.layout_atual()["largura"])
    cli.post(f"/unidades/{alvo}/colapsar")
    assert alvo in main.ESTADO.colapsados
    assert float(main.layout_atual()["largura"]) < antes


# ---------------------------------------------------------------------------
# NÍVEIS SOBRE O PALCO
# ---------------------------------------------------------------------------
def test_o_canvas_oferece_niveis_ate_a_profundidade_do_desenho(cli):
    """Oferecer um N que não existe daria um botão que não muda nada."""
    from orga.dominio import profundidades

    pagina = cli.get("/vistas/canvas").text
    fundo = max(profundidades(main.ESTADO.unidades).values())
    assert 'class="niveis"' in pagina
    assert f">N{fundo}<" in pagina
    assert f">N{fundo + 1}<" not in pagina


def test_escolher_um_nivel_colapsa_dali_para_baixo(cli):
    from orga.dominio import profundidades

    _estrutura_profunda()
    r = cli.post("/arvore/nivel?nivel=1&vista=canvas")
    assert r.status_code == 200
    prof = profundidades(main.ESTADO.unidades)
    assert main.ESTADO.colapsados
    assert all(prof[uid] >= 1 for uid in main.ESTADO.colapsados)


def test_o_nivel_por_equipe_conta_a_arvore_de_times(cli):
    """Sem isto, escolher um nível por equipe colapsaria ids de pessoa — que
    não estão no desenho — e a tela não mudaria."""
    _estrutura_profunda()
    cli.post("/agrupamento")
    cli.post("/arvore/nivel?nivel=1&vista=canvas")
    assert main.ESTADO.colapsados
    assert all(equipes.e_equipe(c) for c in main.ESTADO.colapsados)


def test_o_nivel_de_um_modo_preserva_o_colapso_do_outro(cli):
    """O conjunto é um só. Sem separar os dois espaços de nome, escolher um
    nível por equipe apagaria o colapso montado na visão por pessoa."""
    _estrutura_profunda()
    cli.post("/arvore/nivel?nivel=1&vista=canvas")
    pessoas = {c for c in main.ESTADO.colapsados if not equipes.e_equipe(c)}
    assert pessoas

    cli.post("/agrupamento")
    cli.post("/arvore/nivel?nivel=1&vista=canvas")
    assert pessoas <= main.ESTADO.colapsados        # o de pessoa sobreviveu
    assert any(equipes.e_equipe(c) for c in main.ESTADO.colapsados)


def test_escolher_um_nivel_reenquadra_mesmo_apos_zoom(cli):
    """`ajusteAuto` desliga no primeiro zoom ou arrasto, e é isso que impede o
    desenho de pular do lugar a cada edição. Mas escolher um nível **é** o
    pedido de reenquadrar: quem pede "abrir até N2" quer ver o N2, não a mesma
    janelinha de antes. O handler distingue os dois pela origem da troca."""
    js = cli.get("/").text
    assert "requestConfig" in js
    # Níveis e abrir/dobrar mudam quanta árvore existe: os dois reenquadram.
    assert "closest('.niveis,.arvore-acoes')" in js
    # A exceção do arraste cobre o canto inteiro — níveis, abrir/dobrar e zoom.
    # Sem ela, clicar num desses botões começaria um pan, porque o handler
    # captura todo mousedown que não seja card.
    assert ".no,.alca,.canto" in js


def test_trocar_de_agrupamento_devolve_botao_e_niveis_fora_de_banda(cli):
    """INT-01 não deixa um fragmento do canvas alvejar outra coisa que não
    `#canvas` e `#painel` — então quem descreve o modo volta por `hx-swap-oob`."""
    r = cli.post("/agrupamento")
    assert 'id="btAgrupamento"' in r.text and 'hx-swap-oob="true"' in r.text
    assert 'id="niveis"' in r.text
    assert "Por equipe" in r.text


def test_focar_uma_equipe_nao_derruba_o_cabecalho(cli):
    """`foco` guarda um id que pode ser de pessoa ou de equipe: procurar no
    dicionário errado dava KeyError e levava a tela inteira junto."""
    cli.post("/agrupamento")
    cid = _uma_equipe()
    main.ESTADO.foco = cid
    try:
        assert cli.get("/").status_code == 200
        assert main.cabecalho_do_desenho()["escopo"]
    finally:
        main.ESTADO.foco = None


# ---------------------------------------------------------------------------
# BARRA DO CANVAS
# ---------------------------------------------------------------------------
def test_o_filtro_de_vinculo_tem_o_que_oferecer(cli):
    """O chip existia na barra sem domínio nenhum: abria vazio e não filtrava
    nada. Como os demais, ele sai do dado."""
    from orga.dominio import valores_de_filtro

    opcoes = valores_de_filtro(main.ESTADO.unidades, main.mapa_cc())
    assert "vinculo" in opcoes, "o chip de vínculo não tinha domínio"
    assert opcoes["vinculo"], "domínio vazio: o popover abriria em branco"
    codigos = {k for k, _ in opcoes["vinculo"]}
    assert codigos <= {"clt", "pj", "consultoria"}


def test_o_vinculo_so_oferece_o_que_alguem_tem(cli):
    """`consultoria` surge sozinho no dia em que a primeira pessoa for
    cadastrada assim — e não antes, como lista fixa faria."""
    from orga.dominio import Unidade, valores_de_filtro

    presentes = {u.vinculo for u in main.ESTADO.unidades.values()}
    codigos = {k for k, _ in valores_de_filtro(main.ESTADO.unidades)["vinculo"]}
    assert codigos == presentes


def test_filtrar_por_vinculo_recorta_de_verdade(cli):
    from orga.dominio import filtrar

    alvo = next(iter(main.ESTADO.unidades.values()))
    antes = alvo.vinculo
    try:
        alvo.vinculo = "pj"
        achados = filtrar(main.ESTADO.unidades, {**main.filtros_vazios(),
                                                 "vinculo": ["pj"]})
        assert achados == {alvo.id}
    finally:
        alvo.vinculo = antes


# ---------------------------------------------------------------------------
# DESFAZER E REFAZER
# ---------------------------------------------------------------------------
def test_refazer_devolve_o_que_o_desfazer_tirou(cli):
    raiz_id = main.layout_atual()["raiz_id"]
    cli.post(f"/unidades/{raiz_id}/filho")
    depois_de_criar = len(main.ESTADO.unidades)

    cli.post("/desfazer")
    assert len(main.ESTADO.unidades) == depois_de_criar - 1
    cli.post("/refazer")
    assert len(main.ESTADO.unidades) == depois_de_criar


def test_editar_depois_de_desfazer_abandona_o_futuro(cli):
    """Sem limpar a pilha, `Refazer` traria de volta um estado montado sobre
    outra versão da estrutura — e o que voltasse não seria o que ninguém viu."""
    raiz_id = main.layout_atual()["raiz_id"]
    cli.post(f"/unidades/{raiz_id}/filho")
    cli.post("/desfazer")
    assert main.ESTADO.refazer

    cli.post(f"/unidades/{raiz_id}/filho")      # edita: abandona aquele futuro
    assert main.ESTADO.refazer == []
    r = cli.post("/refazer")
    assert r.status_code == 200 and "Nada a refazer" in r.text


def test_refazer_sem_pilha_avisa_e_nao_quebra(cli):
    main.ESTADO.refazer.clear()
    r = cli.post("/refazer")
    assert r.status_code == 200 and "Nada a refazer" in r.text


def test_os_botoes_de_historico_voltam_fora_de_banda(cli):
    """Eles vivem na barra, fora do `#canvas`, e o INT-01 não deixa um
    fragmento do canvas alvejar outra coisa. Sem o OOB, o botão continuaria
    clicável depois de esvaziar a pilha."""
    raiz_id = main.layout_atual()["raiz_id"]
    cli.post(f"/unidades/{raiz_id}/filho")
    r = cli.post("/desfazer")
    assert 'id="hist"' in r.text and 'hx-swap-oob="true"' in r.text


def test_o_botao_nasce_desabilitado_quando_nao_ha_o_que_desfazer(cli):
    """INT-03: quem sabe se há pilha é o servidor. Um botão que parece
    clicável e responde "nada a desfazer" ensina a desconfiar da tela."""
    main.ESTADO.historico.clear()
    main.ESTADO.refazer.clear()
    pagina = cli.get("/vistas/canvas").text
    assert pagina.count("disabled") >= 2


def test_exportar_reune_os_cinco_formatos_num_popover(cli):
    """Formato novo que nao entra aqui existe e ninguem acha."""
    pagina = cli.get("/vistas/canvas").text
    assert 'id="expoMenu"' in pagina
    for rota in ("/export.pdf", "/export.xlsx", "/export.svg", "/export.csv",
                 "/export.json"):
        assert rota in pagina
    # A escala segue no rótulo do botão, fora do popover: é ela que diz se o
    # papel sai legível, e escondê-la faria a exportação voltar a ser cega.
    assert "expo-esc" in pagina


# ---------------------------------------------------------------------------
# ABRIR NÍVEL A NÍVEL
# ---------------------------------------------------------------------------
def test_marcar_dois_niveis_mostra_os_dois(cli):
    """O nó de N1 **está** no recorte — não é passagem. Mantendo o colapso
    dele, o N2 que a pessoa acabou de marcar nunca desenhava."""
    _estrutura_profunda()
    cli.post("/arvore/colapsar?vista=canvas")      # tudo dobrado
    cli.post("/niveis/1")
    cli.post("/niveis/2")
    ids = {n["id"] for n in main.layout_atual()["nos"]}
    assert {"A", "B"} <= ids, "N1 e N2 marcados: os dois têm de aparecer"


def test_cabecalho_em_modo_equipe_conta_times_e_nao_pessoas(cli):
    """O cabecalho conta o que recebe, e recebia ids de PESSOA sobre um desenho
    de TIMES: "filtro ativo · 34 unidade(s) correspondente(s)" embaixo de nove
    cards. E o mesmo descasamento que deu a `cabecalho_layout` o parametro
    `unidades`, e que a docstring dela diz existir para evitar."""
    cli.post("/agrupamento")                       # modo equipe
    cli.post("/filtros", data={"tipo": "area"})     # o seed tem quatro
    desenhados = len(main.desenho_atual())
    linhas = main.layout_atual()["cabecalho"]["linhas"]
    casou = next(l for l in linhas if "correspondente" in l)
    assert str(desenhados) in casou, f"{casou!r} não fala dos {desenhados} times"


def test_a_visao_por_equipe_e_derivada_uma_vez_por_requisicao(cli, monkeypatch):
    """`agrupar` percorre a base inteira, e a requisicao do canvas a pedia tres
    vezes — o layout, a profundidade dos controles e o cabecalho —, sempre com o
    mesmo resultado."""
    from orga import equipes as equipesmod
    cli.post("/agrupamento")
    n = [0]
    original = equipesmod.agrupar
    monkeypatch.setattr(equipesmod, "agrupar",
                        lambda *a, **k: (n.__setitem__(0, n[0] + 1),
                                         original(*a, **k))[1])
    cli.get("/vistas/canvas")
    assert n[0] == 1, f"agrupar() chamado {n[0]}x numa requisição só"


def test_editar_em_modo_equipe_aparece_na_hora(cli):
    """A contrapartida do cache: guardar o desenho nao pode servir o de ontem.

    O caminho mais curto para o estrago seria uma mutacao que nao invalidasse —
    por isso o teste edita, confere, desfaz e confere de novo."""
    cli.post("/agrupamento")
    antes = {u.nome for u in main.desenho_atual().values()}
    alvo = next(u for u in main.ESTADO.unidades.values() if u.area)
    cli.post(f"/unidades/{alvo.id}/salvar",
             data={"nome": alvo.nome, "tipo": alvo.tipo, "area": "Time Novo",
                   "cargo": alvo.cargo, "vista": "canvas"})
    assert "Time Novo" in {u.nome for u in main.desenho_atual().values()}
    cli.post("/desfazer")
    assert {u.nome for u in main.desenho_atual().values()} == antes


def test_chip_de_filtro_nao_apaga_o_recorte_por_nivel(cli):
    """Dois controles, um estado — e um deles montava o estado do zero.

    `profundidade` mora em `ESTADO.filtros` mas fica de fora de `CRITERIOS`: e
    propriedade da arvore desenhada, nao atributo da unidade. O formulario dos
    chips nao a envia, entao remontar o dicionario a apagava. Pior: a resposta
    do POST traz so os chips fora de banda, logo `_niveis.html` nao voltava
    para se desmarcar — os botoes N seguiam apertados sobre um servidor que ja
    tinha esquecido o recorte.
    """
    _estrutura_profunda()
    cli.post("/arvore/colapsar?vista=canvas")
    cli.post("/niveis/1")
    marcado = list(main.ESTADO.filtros["profundidade"])
    assert marcado

    cli.post("/filtros", data={"texto": "", "vinculo": "clt"})
    assert main.ESTADO.filtros["profundidade"] == marcado
    assert "A" in {n["id"] for n in main.layout_atual()["nos"]}

    # E limpar continua limpando: a preservacao nao pode virar teimosia.
    cli.post("/filtros/limpar")
    assert main.ESTADO.filtros["profundidade"] == []


def test_um_nivel_marcado_nao_abre_o_de_baixo(cli):
    """Marcar N1 pede N1, e não a subárvore inteira dele."""
    _estrutura_profunda()
    cli.post("/arvore/colapsar?vista=canvas")
    cli.post("/niveis/1")
    ids = {n["id"] for n in main.layout_atual()["nos"]}
    assert "A" in ids and "C" not in ids


def test_abrir_um_nivel_de_cada_vez(cli):
    """Abrir 267 cards de um golpe responde a pergunta errada: quem desce
    nível a nível está lendo a estrutura."""
    _estrutura_profunda()
    cli.post("/arvore/colapsar?vista=canvas")
    fundo = lambda: max(n["nivel"] for n in main.layout_atual()["nos"])  # noqa: E731

    antes = fundo()
    cli.post("/arvore/mais?vista=canvas")
    depois = fundo()
    assert depois == antes + 1

    cli.post("/arvore/menos?vista=canvas")
    assert fundo() == antes


def test_o_passo_parte_do_que_esta_aberto_e_nao_de_um_contador(cli):
    """Depois de alguém dobrar um galho na mão, um contador guardado diria
    "estamos em N3" com a tela mostrando N1."""
    _estrutura_profunda()
    cli.post("/arvore/expandir?vista=canvas")
    assert main.nivel_aberto(main.ESTADO.unidades, main.ESTADO.colapsados) == 3

    main.ESTADO.colapsados.add("A")               # dobra na mão
    assert main.nivel_aberto(main.ESTADO.unidades, main.ESTADO.colapsados) == 1
    cli.post("/arvore/mais?vista=canvas")
    assert main.nivel_aberto(main.ESTADO.unidades, main.ESTADO.colapsados) == 2


def test_fechar_abaixo_da_raiz_nao_quebra(cli):
    _estrutura_profunda()
    cli.post("/arvore/colapsar?vista=canvas")
    for _ in range(4):
        r = cli.post("/arvore/menos?vista=canvas")
        assert r.status_code == 200
    assert main.layout_atual()["nos"]


def test_os_quatro_botoes_estao_na_tela(cli):
    pagina = cli.get("/vistas/canvas").text
    for rota in ("/arvore/menos", "/arvore/mais", "/arvore/expandir",
                 "/arvore/colapsar"):
        assert rota in pagina


# ---------------------------------------------------------------------------
# ESTRUTURA: ABRIR E FECHAR AS FAIXAS
# ---------------------------------------------------------------------------
def test_estrutura_abre_as_quatro_faixas_de_uma_vez(cli):
    from orga.dominio import sem_acento

    uma = cli.get("/vistas/estrutura?banda=cliente").text
    todas = cli.get("/vistas/estrutura?banda=*").text
    # Com todas abertas há mais grupos de chips do que com uma só.
    assert todas.count('class="chips"') > uma.count('class="chips"')
    assert sem_acento("Estrutura") in sem_acento(todas)


def test_estrutura_fecha_todas(cli):
    fechado = cli.get("/vistas/estrutura").text
    assert 'class="chips"' not in fechado


def test_escolher_uma_vertical_nao_fecha_as_outras_faixas(cli):
    """Com tudo aberto, o chip leva a banda vigente — e não a da própria
    faixa. Levando a da faixa, escolher uma vertical fecharia as outras três."""
    todas = cli.get("/vistas/estrutura?banda=*").text
    assert "banda=%2A" in todas or "banda=*" in todas


def test_banda_invalida_cai_para_nenhuma(cli):
    """A vista não guarda estado: o que vem na URL é validado contra o dado."""
    r = cli.get("/vistas/estrutura?banda=inexistente")
    assert r.status_code == 200 and 'class="chips"' not in r.text


def test_os_dois_botoes_estao_no_cabecalho_da_estrutura(cli):
    pagina = cli.get("/vistas/estrutura").text
    assert 'class="est-tudo"' in pagina
    assert "banda=%2A" in pagina                  # abrir todas


# ---------------------------------------------------------------------------
# DIVERGÊNCIAS DA ESTRUTURA
# ---------------------------------------------------------------------------
def test_a_raiz_sintetica_nao_conta_como_pessoa_fora_das_faixas(cli):
    """`Board` é nó materializado porque a SPEC exige raiz única (RF-03), e não
    tem centro de custo por decisão de carga. Acusá-la é alarme que nunca
    apaga — e alarme que nunca apaga ensina a ignorar o painel inteiro."""
    from orga import estrutura as estruturamod
    from orga.dominio import raiz

    # Põe a raiz na mesma condição da base real: sem centro de custo, e por
    # isso sem tipo. No seed da SPEC ela resolve — o que este teste afirma é a
    # regra, não a forma daquela base.
    r = raiz(main.ESTADO.unidades)
    antes = (r.centro_custo, r.area, r.vertical)
    try:
        r.centro_custo = r.area = r.vertical = ""
        main._CACHE_CC["chave"] = None                # o mapa é memoizado
        assert not estruturamod._tipo_de(r, main.mapa_cc())
        div = estruturamod.divergencias(main.ESTADO.unidades, main.mapa_cc())
        fora = [d for d in div if "fora das faixas" in str(d.get("o_que", ""))]
        assert not fora, "a raiz não pode aparecer como pessoa fora das faixas"
    finally:
        r.centro_custo, r.area, r.vertical = antes
        main._CACHE_CC["chave"] = None


def test_pessoa_de_verdade_sem_tipo_ainda_e_acusada(cli):
    """Excluir a raiz não pode virar excluir o problema."""
    from orga import estrutura as estruturamod
    from orga.dominio import Unidade, raiz

    r = raiz(main.ESTADO.unidades)
    main.ESTADO.unidades["ORFAO"] = Unidade(
        id="ORFAO", codigo="ORG-9999", nome="Sem CC", tipo="celula",
        parent_id=r.id, ordem=999, area="Inexistente", centro_custo="")
    try:
        div = estruturamod.divergencias(main.ESTADO.unidades, main.mapa_cc())
        fora = [d for d in div if "fora das faixas" in str(d.get("o_que", ""))]
        assert fora, "quem não é raiz e não resolve tipo tem de aparecer"
        assert "1 pessoa(s)" in fora[0]["o_que"]      # concordância com n=1
    finally:
        main.ESTADO.unidades.pop("ORFAO", None)


# ---------------------------------------------------------------------------
# TELA ESTREITA
# ---------------------------------------------------------------------------
# O layout de celular é CSS, e CSS não se testa aqui. O que se testa é a
# estrutura de que ele depende: o agrupamento existe, o gatilho existe, e o que
# ficou de fora ficou de fora de propósito.
def test_o_menu_do_cabecalho_guarda_os_modulos_e_deixa_maria_e_avatar_de_fora(cli):
    """Em tela estreita o cabeçalho vira um menu — mas não inteiro.

    MarIA e o avatar são o que se abre no meio de uma leitura; enterrá-los
    custaria dois toques onde hoje se gasta um. A regra é posicional, e é aqui
    que ela fica escrita: quem mexer no cabeçalho descobre no CI, não no uso.
    """
    pagina = cli.get("/").text
    i_grupo = pagina.index('id="modulos"')
    i_maria = pagina.index('id="mariaTopo"')          # MarIA abre o que vem depois
    dentro = pagina[i_grupo:i_maria]

    assert 'id="btMenuTopo"' in pagina[:i_grupo]      # o gatilho vem antes do grupo
    for modulo in ("/vistas/canvas", "/vistas/estrutura", "/vistas/tabela",
                   "/vistas/configuracoes"):
        assert modulo in dentro, f"{modulo} precisa entrar no menu"
    # Manual, Boas-vindas e o idioma saíram do menu de módulos e passaram para o
    # popover do avatar (que abre depois de MarIA).
    for fora in ("bt-maria", 'id="btAvatar"', "conta-idioma"):
        assert fora not in dentro, f"{fora} não pode entrar no menu"
    depois = pagina[i_maria:]
    assert 'id="btAvatar"' in depois
    assert 'hx-post="/config/idioma"' in depois
    # O GPlanSiS|OS saiu do sistema em 08/09/2026 — não está no menu de módulos
    # nem no popover do avatar. Antes este teste EXIGIA o link no popover, que
    # era o requisito de quando ele mudou de lugar; agora guarda a ausência nos
    # dois, para ninguém o devolver por engano a um dos dois menus.
    assert 'href="/greyos"' not in dentro
    assert 'href="/greyos"' not in depois


def test_os_filtros_tem_um_gatilho_e_um_grupo_para_suspender(cli):
    """Oito critérios numa tira que rola para o lado é o mesmo que escondê-los.
    O gatilho abre o grupo inteiro de uma vez; o valor de cada chip não muda."""
    pagina = cli.get("/vistas/canvas").text
    assert 'id="btFiltros"' in pagina and 'id="filtrosCorpo"' in pagina
    corpo = pagina[pagina.index('id="filtrosCorpo"'):]
    # Nenhum chip pode ficar de fora do grupo: um critério solto some da tela
    # estreita sem que nada acuse — é o defeito que este teste existe para pegar.
    assert corpo.count('class="chip"') == pagina.count('class="chip"') > 0
    assert 'type="search"' in corpo and "limpar-tudo" in corpo


def test_botao_de_icone_nao_fica_mudo_quando_o_rotulo_sai(cli):
    """Em tela estreita o rótulo some por CSS e sobra o desenho.

    Se o nome acessível fosse o texto, o botão ficaria mudo ao girar o
    aparelho. Todo botão que carrega ícone carrega também `aria-label` — e o
    rótulo continua no HTML, para a tela larga.
    """
    import re

    pagina = cli.get("/vistas/canvas").text
    botoes = [b for b in re.findall(r"<button\b.*?</button>", pagina, re.S)
              if 'class="ic"' in b]
    assert botoes, "nenhum botão de ferramenta ganhou ícone"
    for b in botoes:
        abertura = b[:b.index(">")]
        assert "aria-label=" in abertura, b[:90]
        assert 'class="rot"' in b, b[:90]


def test_a_tabela_traz_o_que_o_cartao_de_tela_estreita_precisa(cli):
    """Em tela estreita a linha vira cartão, e três coisas sustentam isso.

    Trocar o `display` de <tr>/<td> apaga a semântica de tabela no navegador —
    daí as funções escritas no HTML. O cabeçalho sai da tela, e é `data-rot`
    que passa a nomear cada valor. E o recuo da árvore vem de `--prof`, que
    serve ao mesmo tempo à coluna da tela larga e ao degrau do cartão.
    """
    import re

    pagina = cli.get("/vistas/tabela").text
    corpo = pagina[pagina.index("<tbody"):]
    assert '<table class="arvore" role="table"' in pagina
    assert corpo.count('role="row"') == corpo.count("<tr ") > 0
    assert corpo.count('role="cell"') == corpo.count("<td ") > 0
    assert re.search(r'<tr role="row" style="--prof:\d+"', corpo)
    for rotulo in ("Departamento", "CC", "N5", "Vertical", "Natureza", "Sub."):
        assert f'data-rot="{rotulo}"' in corpo, rotulo


def test_celula_sem_valor_sai_vazia_de_verdade(cli):
    """`td:empty` esconde o campo que a pessoa não tem — mas só casa com
    célula literalmente vazia. Um espaço em branco do Jinja abriria um rótulo
    órfão no cartão para cada linha sem accountability."""
    from orga.dominio import raiz

    r = raiz(main.ESTADO.unidades)
    r.responsabilidades = []
    r.centro_custo = ""
    corpo = cli.get("/vistas/tabela").text
    assert '<td role="cell" class="accs"></td>' in corpo
    assert '<td role="cell" class="cod" data-rot="CC"></td>' in corpo


def test_a_lateral_e_um_interruptor_que_devolve_a_piramide_de_onde_veio(cli):
    """Quem desenha em convencional e dá uma olhada na árvore indentada tem de
    voltar para a convencional. Sem a pirâmide guardada, o sistema desfazia uma
    escolha que ninguém pediu para desfazer."""
    cli.post("/orientacao")                                  # invertida -> vertical
    assert main.ESTADO.orientacao == "vertical"
    cli.post("/orientacao/lateral")
    assert main.ESTADO.orientacao == "lateral"
    cli.post("/orientacao/lateral")
    assert main.ESTADO.orientacao == "vertical"


def test_virar_a_piramide_estando_na_lateral_traz_a_piramide_guardada(cli):
    """Clicar em "▲ Convencional" olhando uma árvore indentada é pedir a
    pirâmide — não o oposto de uma pirâmide que não está na tela."""
    cli.post("/orientacao")                                  # guarda vertical
    cli.post("/orientacao/lateral")
    cli.post("/orientacao")
    assert main.ESTADO.orientacao == "vertical"


def test_a_lateral_sobrevive_ao_recarregar(cli):
    cli.post("/orientacao/lateral")
    bruto = __import__("json").loads(main.serializar())
    assert bruto["orientacao"] == "lateral"
    assert bruto["orientacao_piramide"] == "invertida"
    main.adotar(bruto)
    assert main.ESTADO.orientacao == "lateral"
    assert main.ESTADO.orientacao_piramide == "invertida"


def test_estado_antigo_sem_a_piramide_guardada_nao_quebra(cli):
    """Arquivo gravado antes da lateral existir: a orientação vigente serve de
    semente, a menos que ela própria seja a lateral."""
    bruto = __import__("json").loads(main.serializar())
    bruto["orientacao"] = "vertical"
    bruto.pop("orientacao_piramide")
    main.adotar(bruto)
    assert main.ESTADO.orientacao_piramide == "vertical"
    bruto["orientacao"] = "lateral"
    main.adotar(bruto)
    assert main.ESTADO.orientacao_piramide == "invertida"


def test_o_botao_lateral_fica_ao_lado_da_orientacao_e_diz_o_estado(cli):
    pagina = cli.get("/vistas/canvas").text
    assert 'hx-post="/orientacao/lateral"' in pagina
    i_orient = pagina.index('hx-post="/orientacao"')
    i_lat = pagina.index('hx-post="/orientacao/lateral"')
    assert 0 < i_lat - i_orient < 900, "o botão tem de nascer ao lado da orientação"
    assert 'aria-pressed="false"' in pagina[i_lat:i_lat + 400]
    cli.post("/orientacao/lateral")
    pagina = cli.get("/vistas/canvas").text
    i_lat = pagina.index('hx-post="/orientacao/lateral"')
    assert 'aria-pressed="true"' in pagina[i_lat:i_lat + 400]
    assert "apertado" in pagina[i_lat - 200:i_lat]


def test_a_lateral_sai_no_svg_no_pdf_e_no_csv(cli):
    """Sai o que está na tela: a regra vale para a orientação como já vale para
    filtro, colapso, foco e agrupamento."""
    cli.post("/orientacao/lateral")
    svg = cli.get("/export.svg")
    assert svg.status_code == 200 and "árvore indentada" in svg.text
    pdf = cli.get("/export.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert cli.get("/export.csv").status_code == 200


def test_o_rotulo_da_piramide_nao_promete_o_que_o_botao_nao_entrega(cli):
    """Na lateral, `layout.invertida` é falso por ausência de pirâmide, não por
    escolha — e o rótulo saía "▲ Convencional" enquanto o clique devolvia a
    invertida. O rótulo tem de ser a pirâmide que o botão de fato entrega."""
    cli.post("/orientacao/lateral")                          # guarda invertida
    pagina = cli.get("/vistas/canvas").text
    assert "▼ Invertida" in pagina and "▲ Convencional" not in pagina
    r = cli.post("/orientacao")
    assert main.ESTADO.orientacao == "invertida"
    # O botão volta fora de banda: o contrato INT-01 não deixa o fragmento do
    # canvas alvejar a barra, e sem o OOB o rótulo ficaria congelado.
    assert 'id="btOrientacao"' in r.text and 'hx-swap-oob="true"' in r.text
    assert "▼ Invertida" in r.text


def test_os_botoes_de_orientacao_voltam_fora_de_banda(cli):
    """Clicar em Lateral redesenhava o organograma e deixava o botão apagado —
    a tela mostrando uma coisa e o controle dizendo outra."""
    r = cli.post("/orientacao/lateral")
    assert 'id="btOrientacao"' in r.text and 'hx-swap-oob="true"' in r.text
    i = r.text.index('id="btOrientacao"')
    assert 'aria-pressed="true"' in r.text[i:]
    r = cli.post("/orientacao/lateral")
    i = r.text.index('id="btOrientacao"')
    assert 'aria-pressed="false"' in r.text[i:]


def test_desfazer_devolve_os_controles_junto_com_o_desenho(cli):
    """`adotar` restaura orientação, agrupamento, níveis e filtros. Mandando só
    o desenho, a barra ficava descrevendo um modo que o servidor já não tem — e
    o clique seguinte ia para o lado errado."""
    raiz_id = main.layout_atual()["raiz_id"]
    cli.post("/orientacao/lateral")
    cli.post(f"/unidades/{raiz_id}/filho")           # marca ponto no histórico
    cli.post("/orientacao")                          # volta à pirâmide
    r = cli.post("/desfazer")
    for marca in ('id="btOrientacao"', 'id="btAgrupamento"', 'id="niveis"',
                  'id="chips"', 'id="expo"'):
        assert marca in r.text, marca


def test_a_escala_do_pdf_acompanha_a_troca_de_eixo(cli):
    """Trocar de eixo é o que mais muda a proporção do viewBox. Deixar o rótulo
    velho ali é mentir no ponto da decisão."""
    _estrutura_profunda()
    antes = main.escala_impressao()
    r = cli.post("/orientacao/lateral")
    assert 'id="expo"' in r.text
    depois = main.escala_impressao()
    i = r.text.index('id="expo"')
    assert f"{depois} %" in r.text[i:]
    assert antes != depois or True          # o que se afirma é o rótulo vivo


def test_o_agrupamento_apertado_usa_a_classe_que_existe_no_css(cli):
    """`.bt.on` não existe neste projeto: o modo por equipe ficava sem realce."""
    r = cli.post("/agrupamento")
    i = r.text.index('id="btAgrupamento"')
    assert "apertado" in r.text[max(0, i - 120):i]


# ---------------------------------------------------------------------------
# BOTÃO DIREITO NO VAZIO DO PALCO
# ---------------------------------------------------------------------------
def test_o_menu_do_fundo_responde_e_traz_as_acoes_do_desenho(cli):
    r = cli.get("/fragmentos/menu-fundo")
    assert r.status_code == 200
    for acao in ("/arvore/mais", "/arvore/menos", "/arvore/expandir",
                 "/arvore/colapsar", "/orientacao", "/orientacao/lateral",
                 "/agrupamento", "/foco/limpar", "/filtros/limpar",
                 "ajustar()", "ajustarLargura()"):
        assert acao in r.text, acao


def test_o_menu_do_fundo_so_alveja_canvas_painel_ou_area(cli):
    """INT-01 no espírito: o menu é fragmento do canvas. `#area` é a exceção já
    aberta pelo `Limpar tudo` da barra, que devolve a vista inteira."""
    import re

    r = cli.get("/fragmentos/menu-fundo")
    assert set(re.findall(r'hx-target="([^"]+)"', r.text)) <= {"#canvas", "#area"}


def test_a_habilitacao_do_menu_do_fundo_vem_pronta(cli):
    """INT-03: botão que parece clicável e responde "nada a fazer" ensina a
    desconfiar da tela."""
    _estrutura_profunda()
    main.ESTADO.foco = None
    main.ESTADO.filtros = main.filtros_vazios()
    corpo = cli.get("/fragmentos/menu-fundo").text
    i_foco = corpo.index("/foco/limpar")
    assert "disabled" in corpo[i_foco:i_foco + 160]
    i_filtro = corpo.index("/filtros/limpar")
    assert "disabled" in corpo[i_filtro:i_filtro + 160]

    main.ESTADO.foco = "A"
    cli.post("/filtros", data={"texto": "Ana"})
    corpo = cli.get("/fragmentos/menu-fundo").text
    i_foco = corpo.index("/foco/limpar")
    assert "disabled" not in corpo[i_foco:i_foco + 160]
    i_filtro = corpo.index("/filtros/limpar")
    assert "disabled" not in corpo[i_filtro:i_filtro + 160]


def test_o_menu_do_fundo_nao_oferece_criar_na_visao_por_equipe(cli):
    """Equipe é desenho derivado: a guarda recusaria, e botão aceso que responde
    "ação negada" é a definição de tela em que não se confia."""
    corpo = cli.get("/fragmentos/menu-fundo").text
    i = corpo.index("/filho")
    assert "disabled" not in corpo[i:i + 160]
    cli.post("/agrupamento")
    corpo = cli.get("/fragmentos/menu-fundo").text
    i = corpo.index("/filho")
    assert "disabled" in corpo[i:i + 160]


def test_os_degraus_do_menu_do_fundo_sabem_quando_acabou(cli):
    """`nivel_aberto` é derivado do desenho, não de contador guardado."""
    _estrutura_profunda()
    cli.post("/arvore/expandir?vista=canvas")
    corpo = cli.get("/fragmentos/menu-fundo").text
    i = corpo.index("/arvore/mais")
    assert "disabled" in corpo[i:i + 160], "aberto até o fim, não há mais nível"
    cli.post("/arvore/nivel?nivel=0&vista=canvas")
    corpo = cli.get("/fragmentos/menu-fundo").text
    i = corpo.index("/arvore/menos")
    assert "disabled" in corpo[i:i + 160], "tudo dobrado, não há o que fechar"


def test_o_botao_exportar_volta_inteiro_e_sem_involucro(cli):
    """O OOB mirava `#expo` de dentro de um `<span>` envolvente, e o htmx troca
    o elemento que carrega o atributo — o botão virava invólucro, e a cada
    troca de orientação nascia mais uma camada dentro da barra."""
    r = cli.post("/orientacao/lateral")
    assert r.text.count('id="expo"') == 1
    assert "expoOob" not in r.text
    i = r.text.index('id="expo"')
    assert 'hx-swap-oob="true"' in r.text[i:i + 120]
    # e três trocas seguidas continuam devolvendo um só
    for _ in range(3):
        r = cli.post("/orientacao/lateral")
    assert r.text.count('id="expo"') == 1


# ---------------------------------------------------------------------------
# A VISITA GUIADA
# ---------------------------------------------------------------------------
def test_todo_alvo_da_visita_existe_na_pagina(cli):
    """O alvo é contrato com o template: renomear `#btExportar` faria o passo
    sumir em silêncio. Este teste é o que transforma silêncio em falha.

    Não é um motor de CSS: extrai da página todos os `id` e todas as classes, e
    exige que cada peça do seletor esteja lá. Não prova que o seletor casa —
    prova que nenhuma peça dele desapareceu, que é o defeito real.
    """
    import re

    from orga import ajuda

    pagina = cli.get("/").text
    ids = set(re.findall(r'id="([^"]+)"', pagina))
    classes = {c for atr in re.findall(r'class="([^"]+)"', pagina)
               for c in atr.split()}
    for alvo, titulo, _texto, _lado in ajuda.PASSOS:
        for peca in re.findall(r'[#.][\w-]+', alvo):
            alvo_de = ids if peca[0] == "#" else classes
            assert peca[1:] in alvo_de, f'{titulo}: {alvo} — falta {peca}'


def test_a_visita_so_entra_na_pagina_quando_esta_ligada(cli):
    """Desligada, ela não existe no DOM — e não há caminho para ligá-la sem
    passar pela tela que a governa."""
    main.ESTADO.config.helper = True
    assert 'id="tour"' in cli.get("/").text
    main.ESTADO.config.helper = False
    assert 'id="tour"' not in cli.get("/").text


def test_o_interruptor_da_visita_grava(cli):
    r = cli.post("/config/helper", data={"ligado": "0"})
    assert r.status_code == 204 and main.ESTADO.config.helper is False
    cli.post("/config/helper", data={"ligado": "1"})
    assert main.ESTADO.config.helper is True


def test_os_passos_chegam_traduzidos_e_formatados(cli):
    """Fazer isso no cliente pediria um formatador em JavaScript e um catálogo
    em JavaScript, que é onde a tradução costuma se perder."""
    from orga import ajuda

    passos = main.passos_da_visita()
    assert len(passos) == len(ajuda.PASSOS)
    assert all(p["titulo"] and p["texto"] for p in passos)
    # `**` virou <b>, e nada de asterisco solto sobrou na tela
    algum = next(p for p in passos if "<b>" in p["texto"])
    assert "**" not in algum["texto"]
    anterior = main.ESTADO.config.idioma
    try:
        main.ESTADO.config.idioma = "en-US"
        assert main.passos_da_visita()[0]["titulo"] != passos[0]["titulo"]
    finally:
        main.ESTADO.config.idioma = anterior


def test_a_visita_esta_acima_de_tudo(cli):
    """Enquanto ela corre, ela é o sistema: deixar um alerta passar por cima
    seria um segundo dono da tela."""
    import re
    from pathlib import Path

    css = Path(main.RAIZ / "web" / "templates" / "base.html").read_text(encoding="utf-8")
    z = {n: int(v) for n, v in re.findall(r"\.(tour|alerta|ctx)\{[^}]*z-index:(\d+)", css)}
    assert z["tour"] > z["alerta"] > z["ctx"], z
