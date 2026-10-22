"""
Idiomas da interface — pt-BR, en-US, es.

O risco desta funcionalidade não é traduzir errado: é a chave usada no template
não existir no catálogo. Como a chave é o próprio texto em português e a falta
cai no português, isso **não quebra a tela** — some silenciosamente, e o
operador em inglês vê uma frase em português no meio da interface sem que nada
acuse. Estes testes existem para que a chave órfã falhe no CI, não no uso.

    pytest testes/test_idiomas.py -q
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import idiomas                                                  # noqa: E402
from orga import main                                                     # noqa: E402

PACOTE = RAIZ_PROJETO / "orga"
TEMPLATES = sorted((RAIZ_PROJETO / "web" / "templates").glob("*.html"))

# Nos templates, `t('...')` — Jinja não concatena literais, então regex basta.
# `th(` é o `t(` com parâmetros escapados (marcação do catálogo + valor seguro).
USO_TEMPLATE = re.compile(r"""\bth?\(\s*(['"])(.+?)\1""", re.S)
# `t('a' if x else 'b', …)`: o segundo literal também é chave. Sem limitar o
# miolo, o `.+?` atravessa a expressão e casa aspas de outro lugar do arquivo.
USO_TERNARIO = re.compile(
    r"""\bt\(\s*(['"])[^'"]*?\1\s+if\s+[^()]{1,120}?\s+else\s+"""
    r"""(['"])([^'"]*?)\2\s*[,)]""")

# Módulos que chamam `t(...)`/`T(...)` com literal — varridos pela AST.
SERVIDOR = ("main.py", "estrutura.py", "importador.py", "pdf.py",
            "centros.py", "dominio.py", "correio.py", "relatorio.py",
            "m365.py", "equipes.py", "dcr.py", "cgv.py", "talentos.py",
            "gptw.py", "onebyone.py")


def chaves_do_python(caminho: Path) -> list[str]:
    """`T(...)` extraído pela AST, não por regex.

    Regex erra em dois pontos que aparecem de verdade neste código: literal
    partido em várias linhas por concatenação implícita (só o primeiro pedaço
    casaria) e escape `\\u201c` no fonte, que a regex lê cru e o catálogo tem
    como aspa curva. A AST devolve a string final, já montada e decodificada —
    exatamente o que chega em `traduzir`.
    """
    import ast

    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    achadas = []
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                and no.func.id in ("T", "t", "_t") and no.args
                and isinstance(no.args[0], ast.Constant)
                and isinstance(no.args[0].value, str)):
            achadas.append(no.args[0].value)
    return achadas


def chaves_usadas() -> dict[str, list[str]]:
    """chave -> arquivos onde aparece."""
    achadas: dict[str, list[str]] = {}
    for arq in TEMPLATES:
        texto = arq.read_text(encoding="utf-8")
        for _, chave in USO_TEMPLATE.findall(texto):
            achadas.setdefault(chave, []).append(arq.name)
        for _, _, chave in USO_TERNARIO.findall(texto):
            achadas.setdefault(chave, []).append(arq.name)
    for nome in SERVIDOR:
        for chave in chaves_do_python(PACOTE / nome):
            achadas.setdefault(chave, []).append(nome)
    for chave, origem in chaves_indiretas().items():
        achadas.setdefault(chave, []).append(origem)
    return achadas


def chaves_pelo_funil(caminho: Path) -> list[str]:
    """Literais entregues a `alerta(...)` e `recusar(...)`.

    `alerta` traduz o que recebe, então a mensagem literal já sai traduzida sem
    `T()` na chamada. Ela é usada de verdade — o extrator precisa enxergá-la,
    senão o teste de chave morta acusa 60 mensagens que funcionam.
    """
    import ast

    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    achadas = []
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                and no.func.id in ("alerta", "recusar")):
            for arg in no.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    achadas.append(arg.value)
                # recusar(req, "…") e alerta("a" if x else "b")
                elif isinstance(arg, ast.IfExp):
                    for lado in (arg.body, arg.orelse):
                        if isinstance(lado, ast.Constant) and isinstance(lado.value, str):
                            achadas.append(lado.value)
    return achadas


def chaves_indiretas() -> dict[str, str]:
    """Rótulos que chegam ao template como variável, em `t(rotulo)`.

    São dados em Python — `PERFIS`, `TEMAS`, `CORES_NIVEL`, `BANDAS`,
    `CAMPOS_CARD`, `COLUNAS` — que o template traduz sem citar o texto. Estão
    em uso, mas nenhuma varredura de `t('…')` os encontraria. Listar as fontes
    aqui é o preço de traduzir dado no ponto de exibição, e é um preço que se
    paga uma vez: fonte nova sem entrada nesta lista aparece como chave morta.
    """
    from orga import ajuda
    from orga import banco
    from orga import cargos
    from orga import centros
    from orga import cgv
    from orga import configuracao
    from orga import dcr
    from orga import dominio
    from orga import estrutura
    from orga import maria
    from orga import gptw
    from orga import social
    from orga import talentos

    saida: dict[str, str] = {}

    def por(itens, origem):
        for x in itens:
            # `N2`, `N3`, `N5` são códigos de coluna, não texto: iguais nos três
            # idiomas e sem entrada no catálogo, por decisão.
            if isinstance(x, str) and re.search(r"[A-Za-zÀ-ÿ]{2}", x):
                saida.setdefault(x, origem)

    por((p["rotulo"] for p in configuracao.PERFIS.values()), "configuracao.PERFIS")
    por((p["descricao"] for p in configuracao.PERFIS.values()), "configuracao.PERFIS")
    por(configuracao.TEMAS.values(), "configuracao.TEMAS")
    por((r for r, _ in configuracao.CAMPOS_CARD.values()), "configuracao.CAMPOS_CARD")
    por((c["rotulo"] for c in cargos.CORES_NIVEL.values()), "cargos.CORES_NIVEL")
    por((n[1] for n in cargos.NIVEIS_PADRAO), "cargos.NIVEIS_PADRAO")
    por((c[1] for c in centros.COLUNAS), "centros.COLUNAS")
    por((b.rotulo for b in estrutura.BANDAS), "estrutura.BANDAS")
    por((b.legenda for b in estrutura.BANDAS), "estrutura.BANDAS")
    # Título e texto de cada passo da visita: chegam ao template pelo laço, sem
    # que nenhum arquivo cite o texto.
    por((p[1] for p in ajuda.PASSOS), "ajuda.PASSOS")
    por((p[2] for p in ajuda.PASSOS), "ajuda.PASSOS")
    # Valores gravados no dado que a tela exibe crus: origem do cargo no
    # catálogo e como o CC foi casado. São vocabulário, não identificador.
    por(("regra", "manual"), "origem do cargo no catálogo")
    # Como o CC casou (`centros.resolver`) e a orientação do desenho: os dois
    # chegam ao template como variável, em `t(valor)`.
    por(("exato", "departamento", "sem correspondência"), "centros.resolver")
    por(("invertida", "vertical", "lateral"), "orientação do desenho")
    # Motivo do evento de gênese: gravado pelo importador e exibido em Auditoria.
    por(("carga inicial a partir de Organograma.xlsx",
         "carga do seed de referência da SPEC §13"), "importador (gênese)")
    por((d for _, _, d in banco.TABELAS), "banco.TABELAS")
    por(social.VALORES.values(), "social.VALORES")
    # As sete capacidades: rótulo, verbo, efeito e autoridade chegam ao template
    # pelo laço, sem citar o texto.
    for coluna in (1, 2, 3, 4):
        por((c[coluna] for c in maria.CAPACIDADES), "maria.CAPACIDADES")
    # Vínculo e sugestões do chat: chegam ao template pelo laço, sem citar texto.
    por((r for r, _cor in dominio.VINCULOS.values()), "dominio.VINCULOS")
    por(dominio.STATUS.values(), "dominio.STATUS")
    # As faixas de tempo de casa chegam ao template por `t(f.rotulo)`, e os
    # dois rótulos extras — "A começar" e "Sem data" — saem de `tempo.py`,
    # que os acrescenta à escala na hora de montar a distribuição.
    por((r for _c, r, _p in dominio.FAIXAS_CASA), "dominio.FAIXAS_CASA")
    por(("A começar", "Sem data"), "tempo.por_faixa")
    # Skills: papel, força da correlação, seção do GEP-FOR-003, par de variáveis e
    # os valores da casa chegam ao template por variável, em `t(valor)`.
    por(dcr.ROTULO_PAPEL.values(), "dcr.PAPEIS")
    por((rot for _corte, rot in dcr.FORCAS), "dcr.FORCAS")
    por(dcr.ROTULO_SECAO.values(), "dcr.ROTULO_SECAO")
    por((rotulo for _l, _c, rotulo in dcr.PARES), "dcr.PARES")
    por((frase for _c, _r, frase in dcr.VALORES), "dcr.VALORES")
    # Conversa de Valor: ciclos, status, valores GPlanSiS, competências da liderança, elementos,
    # régua 70/20/10, princípios, CNV e dinâmica chegam ao template por variável.
    por(cgv.ROTULO_CICLO.values(), "cgv.CICLOS")
    por((q for _c, _r, q, _m in cgv.CICLOS), "cgv.CICLOS.quando")
    por(cgv.ROTULO_STATUS.values(), "cgv.STATUS")
    for i in (2, 3):    # rótulo e frase de cada valor GPlanSiS
        por((v[i] for v in cgv.VALORES_TRIO), "cgv.VALORES_TRIO")
    por((rot for _c, rot, _it in cgv.COMPETENCIAS_LIDERANCA), "cgv.COMPETENCIAS")
    por((i for _c, _r, itens in cgv.COMPETENCIAS_LIDERANCA for i in itens),
        "cgv.COMPETENCIAS.itens")
    for i in (1, 2):    # rótulo e o-que-fazer de cada elemento
        por((e[i] for e in cgv.ELEMENTOS), "cgv.ELEMENTOS")
    for i in (1, 2):    # rótulo e descrição de cada faixa da régua
        por((r[i] for r in cgv.REGRA_70_20_10), "cgv.REGRA")
    por(cgv.PRINCIPIOS_FEEDBACK, "cgv.PRINCIPIOS")
    for i in (0, 1, 2):    # componente, o-que e exemplo da CNV
        por((c[i] for c in cgv.CNV), "cgv.CNV")
    for i in (1, 2):    # rótulo e descrição de cada etapa da dinâmica
        por((d[i] for d in cgv.DINAMICA), "cgv.DINAMICA")
    # Avaliação: as escalas do 9-box (risco, impacto), a prontidão de
    # sucessão e a ação imediata chegam ao template por variável, em `t(rotulo)`.
    por((r for _c, r in talentos.RISCOS), "talentos.RISCOS")
    por((r for _c, r in talentos.IMPACTOS), "talentos.IMPACTOS")
    por((r for _c, r in talentos.PRONTIDOES), "talentos.PRONTIDOES")
    por((r for _c, r in talentos.ACOES), "talentos.ACOES")
    # Avaliação Mestre: pilares, escala, modelos, ciclos, maturidade, dimensões e — o grosso —
    # as 60 afirmações e as 10 abertas chegam ao template por variável, em `t(x)`.
    por((r for _c, r, _d in gptw.PILARES), "gptw.PILARES")
    por((d for _c, _r, d in gptw.PILARES), "gptw.PILARES.desc")
    por((r for _v, r in gptw.LIKERT), "gptw.LIKERT")
    por((r for _c, r in gptw.MODELOS_TRABALHO), "gptw.MODELOS_TRABALHO")
    por((r for _c, r, _q in gptw.CICLOS), "gptw.CICLOS")
    por((q for _c, _r, q in gptw.CICLOS), "gptw.CICLOS.quando")
    por((r for _p, _c, r, _d in gptw.MATURIDADE), "gptw.MATURIDADE")
    por((d for _p, _c, _r, d in gptw.MATURIDADE), "gptw.MATURIDADE.desc")
    por((r for _c, r in gptw.DIMENSOES), "gptw.DIMENSOES")
    por((texto for _i, _p, texto, _pu in gptw.AFIRMACOES), "gptw.AFIRMACOES")
    por((texto for _i, texto in gptw.ABERTAS), "gptw.ABERTAS")
    por(main.SUGESTOES, "main.SUGESTOES")
    # Painel RH: os títulos dos modais de lista chegam por variável, em `T(titulo)`.
    por(main._RH_DIM_ROT.values(), "main._RH_DIM_ROT")
    # One-on-One: cadências, status (rock/issue/objetivo/missão), estágios de vida e
    # rótulos de tipo chegam ao template por variável, em `t(rotulo)`.
    from orga import onebyone
    for tupla, origem in ((onebyone.CADENCIAS, "CADENCIAS"),
                          (onebyone.STATUS_ROCK, "STATUS_ROCK"),
                          (onebyone.STATUS_ISSUE, "STATUS_ISSUE"),
                          (onebyone.STATUS_OBJ, "STATUS_OBJ"),
                          (onebyone.STATUS_MISSAO, "STATUS_MISSAO"),
                          (onebyone.ESTAGIOS, "ESTAGIOS")):
        por((r for _c, r in tupla), "onebyone." + origem)
    por(onebyone.ROTULO_TIPO.values(), "onebyone.ROTULO_TIPO")
    por(onebyone.SINAIS_BURNOUT, "onebyone.SINAIS_BURNOUT")
    por(main.SUGESTOES_CALCULADAS.values(), "main.SUGESTOES_CALCULADAS")
    for chave in chaves_pelo_funil(PACOTE / "main.py"):
        saida.setdefault(chave, "main.py (alerta/recusar)")
    for chave in chaves_do_ledger(PACOTE / "main.py"):
        saida.setdefault(chave, "main.py (ledger)")
    return saida


def chaves_do_ledger(caminho: Path) -> list[str]:
    """Ação e motivo dos eventos de auditoria.

    O ledger é histórico imutável e grava sempre em pt-BR — traduzir na escrita
    faria o mesmo evento ter texto diferente conforme a língua de quem o criou.
    A tradução acontece na exibição (`_auditoria.html`), então estas strings
    estão em uso mesmo sem `T()` na chamada.
    """
    import ast

    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    achadas = []
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                and no.func.id in ("commit", "registrar")):
            # commit(acao, uid, motivo, payload) — o uid do meio não é texto
            for pos in (0, 2):
                if len(no.args) <= pos:
                    continue
                arg = no.args[pos]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    achadas.append(arg.value)
    return achadas


# ---------------------------------------------------------------------------
# Mecanismo
# ---------------------------------------------------------------------------
def test_faltando_traducao_cai_no_portugues():
    """A garantia central: nunca vazio, nunca a chave crua."""
    assert idiomas.traduzir("frase que nunca foi traduzida", "en-US") == \
        "frase que nunca foi traduzida"
    assert idiomas.traduzir("", "es") == ""


def test_sufixo_de_contexto_nao_aparece_na_tela():
    assert idiomas.sem_contexto("Nível [do cargo]") == "Nível"
    assert idiomas.traduzir("Nível [do cargo]", "pt-BR") == "Nível"
    # e continua sumindo quando o idioma não tem a entrada
    assert idiomas.traduzir("Zzz [contexto]", "es") == "Zzz"


def test_idioma_invalido_cai_no_padrao():
    assert idiomas.valido("klingon") == idiomas.PADRAO
    assert idiomas.valido(None) == idiomas.PADRAO
    assert idiomas.valido("es") == "es"


def test_interpolacao_sobrevive_a_traducao_quebrada():
    """Tradutor que troca {n} por {N} não pode derrubar a página."""
    idiomas.CATALOGO["__teste {n} unidades__"] = {"en-US": "__test {WRONG} units__"}
    try:
        saida = idiomas.traduzir("__teste {n} unidades__", "en-US", n=7)
        assert saida == "__teste 7 unidades__"      # caiu no português, formatado
    finally:
        idiomas.CATALOGO.pop("__teste {n} unidades__", None)


def test_traducao_boa_interpola():
    idiomas.CATALOGO["__teste {n} unidades__"] = {"en-US": "__{n} units__"}
    try:
        assert idiomas.traduzir("__teste {n} unidades__", "en-US", n=7) == "__7 units__"
    finally:
        idiomas.CATALOGO.pop("__teste {n} unidades__", None)


# ---------------------------------------------------------------------------
# Integridade do catálogo
# ---------------------------------------------------------------------------
def test_toda_chave_usada_existe_no_catalogo():
    """Chave órfã não quebra a tela — some em português. Por isso o teste."""
    usadas = chaves_usadas()
    orfas = {c: locais for c, locais in usadas.items() if c not in idiomas.CATALOGO}
    assert not orfas, (
        f"{len(orfas)} chave(s) sem entrada no catálogo — apareceriam em "
        f"português para quem usa outro idioma:\n"
        + "\n".join(f"  {c!r} em {sorted(set(v))}" for c, v in
                    sorted(orfas.items())[:15]))


def test_catalogo_nao_guarda_chave_que_ninguem_usa():
    """Chave morta é tradução paga e não entregue — ou um template que mudou."""
    usadas = set(chaves_usadas())
    mortas = sorted(set(idiomas.CATALOGO) - usadas)
    assert not mortas, (
        f"{len(mortas)} chave(s) no catálogo que nenhum template usa:\n"
        + "\n".join(f"  {c!r}" for c in mortas[:15]))


@pytest.mark.parametrize("idioma", idiomas.TRADUZIDOS)
def test_catalogo_completo_no_idioma(idioma):
    faltam = idiomas.faltando(idioma)
    assert not faltam, (
        f"{len(faltam)} sem tradução em {idioma}:\n"
        + "\n".join(f"  {c!r}" for c in faltam[:15]))


@pytest.mark.parametrize("idioma", idiomas.TRADUZIDOS)
def test_marcadores_de_interpolacao_sobrevivem(idioma):
    """`{n}` perdido na tradução vira texto sem o número, ou KeyError."""
    marcador = re.compile(r"\{(\w+)\}")
    ruins = []
    for pt, trads in idiomas.CATALOGO.items():
        alvo = trads.get(idioma)
        if not alvo:
            continue
        if set(marcador.findall(idiomas.sem_contexto(pt))) != set(marcador.findall(alvo)):
            ruins.append((pt, alvo))
    assert not ruins, (
        f"{len(ruins)} tradução(ões) em {idioma} com marcador diferente do "
        f"português:\n" + "\n".join(f"  {p!r}\n    -> {a!r}" for p, a in ruins[:10]))


@pytest.mark.parametrize("idioma", idiomas.TRADUZIDOS)
def test_markup_inline_sobrevive(idioma):
    """<b>, <code> e <i> fazem parte do texto; perder a tag quebra o parágrafo."""
    tags = re.compile(r"</?(b|i|code|strong|em)>")
    ruins = []
    for pt, trads in idiomas.CATALOGO.items():
        alvo = trads.get(idioma)
        if not alvo:
            continue
        if sorted(tags.findall(pt)) != sorted(tags.findall(alvo)):
            ruins.append((pt, alvo))
    assert not ruins, (
        f"{len(ruins)} tradução(ões) em {idioma} com markup diferente:\n"
        + "\n".join(f"  {p!r}\n    -> {a!r}" for p, a in ruins[:10]))


def test_nenhuma_chave_e_so_pontuacao_ou_numero():
    """Traduzir "·" ou "%" é ruído no catálogo e convida a erro."""
    ruins = [c for c in idiomas.CATALOGO if not re.search(r"[A-Za-zÀ-ÿ]{2}", c)]
    assert not ruins, f"chaves sem palavra: {ruins[:10]}"


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------
@pytest.fixture()
def cli():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


# ---------------------------------------------------------------------------
# Departamento é dado, não interface — mas tem nome nos três idiomas
# ---------------------------------------------------------------------------
def test_departamento_tem_nome_nos_tres_idiomas():
    from orga import estrutura

    assert estrutura.rotulo("Mechanical Team", "pt-BR") == "Montagem Mecânica"
    assert estrutura.rotulo("Mechanical Team", "en-US") == "Mechanical Team"
    assert estrutura.rotulo("Mechanical Team", "es") == "Montaje Mecánico"
    # o cadastro tem departamentos escritos em português: em inglês eles não
    # podem ficar em português só porque a origem ficou
    assert estrutura.rotulo("Gestão de TIC's", "en-US") == "IT Management"
    # e a grafia errada continua corrigida em qualquer idioma
    assert estrutura.rotulo("Enviroment", "es") == "Medio Ambiente"
    assert estrutura.rotulo("Enviroment", "en-US") == "Environment"


def test_espanhol_faltando_cai_no_portugues_e_nao_no_nome_cru():
    """Entre "Gestão" e "Managers Team", quem lê espanhol entende o primeiro."""
    from orga import estrutura

    faltam = [k for k in estrutura.ROTULO_PT if k not in estrutura.ROTULO_ES]
    # O que sobra são nomes de marca, que não se traduzem — e `P&P`, que é a
    # sigla da mesma vertical: o português dela já é "Pulp & Paper", e é isso
    # que o espanhol deve mostrar.
    assert set(faltam) <= {"Food & Beverage", "Pulp & Paper"}, faltam
    for k in faltam:
        assert estrutura.rotulo(k, "es") == estrutura.ROTULO_PT[k]


def test_seletor_de_idioma_esta_no_menu_da_conta(cli):
    """O seletor mudou de lugar: saiu da barra e entrou no popover do avatar,
    junto do Manual e das Boas-vindas. O que se afirma aqui é que os três
    idiomas continuam ofertados e cada um manda o seu próprio POST."""
    html = cli.get("/").text
    assert "conta-idioma" in html          # o grupo de idioma no menu da conta
    assert html.count('hx-post="/config/idioma"') == len(idiomas.IDIOMAS)
    for codigo, nome in idiomas.IDIOMAS.items():
        assert f'"idioma": "{codigo}"' in html
        assert nome in html


def test_troca_de_idioma_manda_recarregar(cli):
    """A tela é montada no servidor: sem recarregar, sobraria fragmento antigo
    em outra língua no meio da página."""
    anterior = main.ESTADO.config.idioma
    try:
        r = cli.post("/config/idioma", data={"idioma": "en-US"})
        assert r.status_code == 204
        assert r.headers.get("hx-refresh") == "true"
        assert main.ESTADO.config.idioma == "en-US"
        assert '<html lang="en-US"' in cli.get("/").text
    finally:
        cli.post("/config/idioma", data={"idioma": anterior})


def test_idioma_invalido_nao_derruba_a_tela(cli):
    anterior = main.ESTADO.config.idioma
    try:
        cli.post("/config/idioma", data={"idioma": "../../etc/passwd"})
        assert main.ESTADO.config.idioma == idiomas.PADRAO
        assert cli.get("/").status_code == 200
    finally:
        cli.post("/config/idioma", data={"idioma": anterior})


@pytest.mark.parametrize("idioma", ["pt-BR", "en-US", "es"])
def test_todas_as_vistas_renderizam_em_cada_idioma(cli, idioma):
    anterior = main.ESTADO.config.idioma
    try:
        cli.post("/config/idioma", data={"idioma": idioma})
        for vista in ("canvas", "estrutura", "tabela", "tempo", "dcr", "cgv",
                      "talentos", "gptw", "onebyone", "auditoria", "configuracoes"):
            r = cli.get(f"/?vista={vista}")
            assert r.status_code == 200, f"{vista} em {idioma}"
            assert f'<html lang="{idioma}"' in r.text
    finally:
        cli.post("/config/idioma", data={"idioma": anterior})
