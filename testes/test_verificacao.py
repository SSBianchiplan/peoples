"""As correções que a verificação completa de 13/08/2026 pediu.

Cada teste aqui nasceu de um defeito REPRODUZIDO, e não de uma suspeita. O
comentário de cada um guarda o que acontecia antes — sem isso, o próximo a ler
vê uma guarda sem entender o que ela evita, e a primeira refatoração a remove.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orga import dominio, importador
from orga import main
from testes.test_gerenciador import planilha


def _xlsx(linhas: list[dict]) -> bytes:
    """Dicts com os nomes INTERNOS dos campos viram planilha com os TÍTULOS.

    Passa pelo `ler_planilha` de verdade: `analisar` recebe bytes, e um teste
    que chamasse a lógica por dentro não provaria que a coluna chega lá.
    """
    titulo = {c.campo: c.titulo for c in importador.COLUNAS}
    return planilha([{titulo[k]: v for k, v in l.items()} for l in linhas])


@pytest.fixture
def cli():
    return TestClient(main.app)


@pytest.fixture
def folha():
    """Uma unidade descartável, filha da raiz."""
    raiz = main.raiz(main.ESTADO.unidades)
    nova = dominio.Unidade(id=main.novo_id(), codigo="ZZ-VERIF",
                           nome="Unidade de verificação", tipo="celula",
                           parent_id=raiz.id, ordem=9990)
    main.ESTADO.unidades[nova.id] = nova
    yield nova
    main.ESTADO.unidades.pop(nova.id, None)


# ---------------------------------------------------------------------------
# O ledger é append-only, inclusive contra o desfazer
# ---------------------------------------------------------------------------
def test_desfazer_nao_rebobina_o_ledger(cli, folha):
    """`marcar_ponto` guarda `serializar()`, que inclui os eventos, e `adotar`
    trocava a lista inteira: desfazer restaurava o ledger de ANTES da edição, e
    a edição sumia da trilha. Pior, `verificar_cadeia` recalcula os hashes
    sobre a lista que existe — a cadeia continuava fechando, e a Auditoria
    dizia "íntegra" sobre um histórico do qual um trecho tinha sido removido.
    """
    antes = len(main.ESTADO.eventos)
    cli.post(f"/unidades/{folha.id}/salvar",
             data={"nome": "Nome que precisa ficar na trilha", "tipo": "celula"})
    assert len(main.ESTADO.eventos) == antes + 1
    marca = main.ESTADO.eventos[-1]["motivo"]

    cli.post("/desfazer")
    motivos = [e["motivo"] for e in main.ESTADO.eventos]
    assert marca in motivos, "a edição desapareceu da trilha ao desfazer"
    # E o desfazer é ele próprio um fato: entra na trilha em vez de apagá-la.
    assert motivos[-1] == "desfazer"
    assert len(main.ESTADO.eventos) == antes + 2
    assert main.verificar_cadeia()["integro"], "a cadeia deixou de fechar"


def test_refazer_tambem_so_acrescenta(cli, folha):
    antes = len(main.ESTADO.eventos)
    cli.post(f"/unidades/{folha.id}/salvar",
             data={"nome": "Editado", "tipo": "celula"})
    cli.post("/desfazer")
    cli.post("/refazer")
    assert len(main.ESTADO.eventos) == antes + 3
    assert main.ESTADO.eventos[-1]["motivo"] == "refazer"
    assert main.verificar_cadeia()["integro"]


# ---------------------------------------------------------------------------
# O mural entra na pilha de desfazer
# ---------------------------------------------------------------------------
def test_mural_marca_ponto_e_nao_e_engolido_pelo_desfazer(cli, folha):
    """As duas rotas gravavam sem `marcar_ponto()`. O Desfazer seguinte — de
    uma edição QUALQUER, feita antes — restaurava um instantâneo anterior à
    mensagem e a engolia: quem publicou via a mensagem sumir por causa de um
    botão que nada tinha a ver com ela."""
    antes_mural = len(main.ESTADO.mural)
    guardado = main.ESTADO.config.usuario_id
    try:
        alvo = next(u for u in main.ESTADO.unidades.values() if u.parent_id)
        main.ESTADO.config.usuario_id = alvo.id
        pontos = len(main.ESTADO.historico)
        r = cli.post(f"/mural/{folha.id}",
                     data={"texto": "Obrigado pelo apoio na virada!"})
        assert r.status_code == 200
        assert len(main.ESTADO.mural) == antes_mural + 1
        assert len(main.ESTADO.historico) == pontos + 1, "não marcou ponto"

        # E o desfazer agora desfaz a MENSAGEM, que é a última mutação.
        cli.post("/desfazer")
        assert len(main.ESTADO.mural) == antes_mural
    finally:
        main.ESTADO.config.usuario_id = guardado
        del main.ESTADO.mural[antes_mural:]


def test_remocao_recusada_no_mural_nao_consome_o_desfazer(cli, folha):
    """O ponto é marcado antes de remover, porque depois o "agora" já não tem a
    mensagem. Recusando, o ponto tem de sair: um Desfazer que não desfaz nada é
    pior que nenhum — ele consome a vez."""
    pontos = len(main.ESTADO.historico)
    r = cli.delete(f"/mural/{folha.id}/nao-existe")
    assert r.status_code == 200
    assert len(main.ESTADO.historico) == pontos


# ---------------------------------------------------------------------------
# Código repetido deixa de identificar
# ---------------------------------------------------------------------------
def test_codigo_repetido_na_planilha_nao_casa_duas_linhas_com_a_mesma_pessoa():
    """Duas linhas com o mesmo ID SAP casavam com a MESMA unidade: a segunda
    sobrescrevia a primeira, uma das duas pessoas sumia da carga sem aparecer
    em "removidos", e o passo 2 não dizia nada — havia aviso para nome
    repetido e nenhum para código repetido, que é a identidade mais forte."""
    us = {u.id: u for u in list(main.ESTADO.unidades.values())[:6]}
    alvo = next(u for u in us.values() if u.parent_id)
    linhas = [
        {"codigo": "999999", "nome": "Pessoa Um da Prova",
         "email": "um@exemplo.com", "gestor": alvo.nome},
        {"codigo": "999999", "nome": "Pessoa Dois da Prova",
         "email": "dois@exemplo.com", "gestor": alvo.nome},
    ]
    r = importador.analisar(_xlsx(linhas), us, "prova.xlsx")
    # As duas entram como pessoas novas, e nenhuma sobrescreve a outra.
    nomes = {n["nome"] for n in r["novos"]}
    assert {"Pessoa Um da Prova", "Pessoa Dois da Prova"} <= nomes
    assert any("digo" in a and "mais de uma vez" in a for a in r["avisos"]), \
        f"o passo 2 não avisou: {r['avisos']}"


def test_codigo_repetido_na_base_grava_na_pessoa_certa():
    """Dois cadastros já gravados com o mesmo código faziam o `dict` ficar com
    o ÚLTIMO em silêncio, e a carga seguinte escrevia na pessoa errada.

    Este é o teste que distingue: a linha traz `Xara Um` com o e-mail de `x1`.
    Desqualificado o código, ela cai para nome+e-mail e acerta `x1`. Valendo o
    código, `por_codigo["777"]` devolve `x2` — e o cargo novo iria para a
    outra pessoa, sem que nada na tela apontasse para o engano.
    """
    us = {"r1": dominio.Unidade(id="r1", codigo="R", nome="Raiz",
                                tipo="diretoria", parent_id=None, ordem=10)}
    for i, nome in enumerate(("Xara Um", "Xara Dois"), start=1):
        us[f"x{i}"] = dominio.Unidade(
            id=f"x{i}", codigo="777", nome=nome, tipo="celula",
            parent_id="r1", ordem=i * 10, email=f"x{i}@exemplo.com",
            cargo="Antigo")
    r = importador.analisar(_xlsx(
        [{"codigo": "777", "nome": "Xara Um", "email": "x1@exemplo.com",
          "gestor": "Raiz", "cargo": "Cargo Novo"}]), us, "prova.xlsx")
    assert not r["novos"], "criou gente nova onde havia identificação por nome"
    assert [a["id"] for a in r["alterados"]] == ["x1"],         f"gravou na pessoa errada: {r['alterados']}"
    assert any("digo" in a for a in r["avisos"])


# ---------------------------------------------------------------------------
# O arquivo sai com o recorte que a tela declara
# ---------------------------------------------------------------------------
def test_foco_recorta_o_csv_como_recorta_o_desenho(cli):
    """O botão promete, no título, que o foco vale para o arquivo. Com foco
    numa subárvore, o desenho mostrava a subárvore e o CSV saía com a base
    inteira."""
    filhos = main.mapa_filhos(main.ESTADO.unidades)
    alvo = next((u for u in main.ESTADO.unidades.values()
                 if len(filhos.get(u.id, [])) >= 2 and u.parent_id), None)
    if alvo is None:
        pytest.skip("base sem galho para focar")
    guardado = main.ESTADO.foco
    try:
        main.ESTADO.foco = alvo.id
        esperado = {alvo.id} | main.descendentes(main.ESTADO.unidades, alvo.id)
        assert main.ids_para_arquivo() == esperado
        linhas = cli.get("/export.csv").text.strip().splitlines()
        assert len(linhas) - 1 == len(esperado), "o CSV ignorou o foco"
        assert len(esperado) < len(main.ESTADO.unidades)
    finally:
        main.ESTADO.foco = guardado


def test_colapso_nao_recorta_o_arquivo_de_carga(cli):
    """Decisão, não esquecimento: dobrar é gesto de LEITURA. A aba `ORG` é o
    contrato de carga e o ciclo é exportar, editar fora, devolver — saindo
    dobrada, ela volta com menos gente do que a estrutura tem, e a carga lê a
    ausência como remoção. Uma dobra na tela viraria demissão em massa."""
    alvo = next(u for u in main.ESTADO.unidades.values()
                if main.mapa_filhos(main.ESTADO.unidades).get(u.id))
    guardado = set(main.ESTADO.colapsados)
    try:
        main.ESTADO.colapsados.add(alvo.id)
        assert main.ids_para_arquivo() == set(main.ESTADO.unidades)
    finally:
        main.ESTADO.colapsados = guardado


# ---------------------------------------------------------------------------
# A proposta do agente respeita o escopo de quem aprova
# ---------------------------------------------------------------------------
def test_proposta_do_agente_nao_cria_fora_do_escopo_do_editor(cli):
    """`negado(NIVEL_EDITOR)` sem `uid` confere o perfil e passa direto pelo
    escopo. Um editor restrito a um galho aprovava a proposta e as unidades
    nasciam sob a RAIZ, fora do que ele pode editar — era a única rota de
    criação que escapava do funil."""
    from orga import configuracao as cfgmod

    cfg = main.ESTADO.config
    guardado = (cfg.perfil, cfg.escopo_id, dict(main.ESTADO.propostas))
    antes = set(main.ESTADO.unidades)
    try:
        # O galho é criado AQUI. Depender do formato da base deixava o teste
        # verde sozinho e vermelho na suíte, onde outro teste já tinha trocado
        # a estrutura — e a falha então não fala do defeito, fala da ordem.
        galho = dominio.Unidade(
            id=main.novo_id(), codigo="ZZ-GALHO", nome="Galho do escopo",
            tipo="gerencia", parent_id=main.raiz(main.ESTADO.unidades).id,
            ordem=9980)
        main.ESTADO.unidades[galho.id] = galho
        antes = set(main.ESTADO.unidades)
        cfg.perfil, cfg.escopo_id = cfgmod.EDITOR, galho.id
        main.ESTADO.propostas["zz1"] = {
            "sob": "", "time": "Prova", "departamento": "Prova",
            "unidades": [{"cargo": "Analista", "nivel": "celula",
                          "quantidade": 2}]}
        r = cli.post("/maria/agente/zz1/aplicar")
        assert r.status_code == 200
        assert "fora do escopo" in r.text
        assert set(main.ESTADO.unidades) == antes, "criou unidades assim mesmo"
    finally:
        cfg.perfil, cfg.escopo_id, main.ESTADO.propostas = guardado
        for novo in set(main.ESTADO.unidades) - antes:
            del main.ESTADO.unidades[novo]
        main.ESTADO.unidades.pop(galho.id, None)


def test_proposta_sobre_unidade_que_sumiu_e_recusada(cli):
    """A proposta nomeia o pai por NOME, e não achando caía na raiz em
    silêncio: a pessoa aprovava "quatro vagas sob Engenharia" e as quatro
    nasciam no topo do organograma."""
    guardado = dict(main.ESTADO.propostas)
    antes = set(main.ESTADO.unidades)
    try:
        main.ESTADO.propostas["zz2"] = {
            "sob": "Unidade que não existe mais", "time": "Prova",
            "departamento": "Prova",
            "unidades": [{"cargo": "Analista", "nivel": "celula",
                          "quantidade": 1}]}
        r = cli.post("/maria/agente/zz2/aplicar")
        assert r.status_code == 200
        assert "não existe mais" in r.text
        assert set(main.ESTADO.unidades) == antes
    finally:
        main.ESTADO.propostas = guardado
        for novo in set(main.ESTADO.unidades) - antes:
            del main.ESTADO.unidades[novo]
