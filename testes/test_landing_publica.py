"""A apresentação pública em peoples.gplansis.com, e a porta que ela abre.

A raiz do Peoples atende dois públicos e decide pela sessão: sem sessão serve a
landing (`web/publico/landing.html`), com sessão serve o aplicativo. O que estes
testes guardam, em ordem de importância:

  **Liberar a raiz não pode liberar o resto.** `LIVRES` é testado com
  `startswith`, e um `"/"` acrescentado ali abriria o sistema INTEIRO sem que
  nada acusasse — a tela continuaria bonita e qualquer pessoa veria o
  organograma. Por isso a raiz é liberada por igualdade exata, e o teste
  `test_liberar_a_raiz_nao_abriu_mais_nada` percorre um punhado de rotas
  protegidas para provar que continuam fechadas.

  **A landing não vaza dado do organograma.** Ela é um arquivo estático de
  marketing; se algum dia alguém a fizer renderizar contexto do sistema, é aqui
  que aparece.

  **A entrada existe e leva ao login.** Uma apresentação sem porta obriga quem
  já é usuário a saber o endereço de cor.

  **Todo link interno resolve.** Âncora quebrada em página de apresentação é o
  tipo de defeito que ninguém reporta e todo mundo percebe.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orga import acesso, main

RAIZ = Path(__file__).resolve().parents[1]
LANDING = RAIZ / "web" / "publico" / "landing.html"


@pytest.fixture
def fechado(monkeypatch):
    """O sistema com login exigido, que é o estado de produção."""
    monkeypatch.setenv("ORG_EXIGIR_LOGIN", "1")
    monkeypatch.setenv("JWT_SECRET", "segredo-de-teste-com-mais-de-32-caracteres-ok")
    return TestClient(main.app, follow_redirects=False)


def _com_sessao(cli):
    cli.cookies.set(acesso.COOKIE, acesso.assinar({"sub": "tic@gplansis.com",
                                                   "uid": ""}))
    return cli


# --------------------------------------------------------------------- A RAIZ
def test_a_raiz_sem_sessao_serve_a_apresentacao(fechado):
    r = fechado.get("/")
    assert r.status_code == 200, f"esperava a landing, veio {r.status_code}"
    assert "GPlanSiS" in r.text and "Peoples" in r.text
    # É a landing, e não o aplicativo: o marcador é o título dela.
    assert "A estrutura da sua empresa" in r.text


def test_a_raiz_com_sessao_serve_o_aplicativo(fechado):
    r = _com_sessao(fechado).get("/")
    assert r.status_code == 200
    # O aplicativo tem o cabeçalho de vistas; a landing, não.
    assert 'id="btAvatar"' in r.text
    assert "A estrutura da sua empresa" not in r.text


def test_liberar_a_raiz_nao_abriu_mais_nada(fechado):
    """O teste que importa.

    `LIVRES` é comparado com `startswith`. Um `"/"` acrescentado ali liberaria
    todas as rotas do sistema de uma vez, e o sintoma seria o organograma
    aberto na internet — sem erro, sem log, sem nada. A raiz é liberada por
    igualdade exata, e aqui se prova que a guarda continua fechando o resto.
    """
    protegidas = ["/vistas/canvas", "/vistas/estrutura", "/vistas/tabela",
                  "/vistas/configuracoes", "/panorama", "/boas-vindas",
                  "/greyos", "/senha", "/config/idioma"]
    for caminho in protegidas:
        r = fechado.get(caminho)
        assert r.status_code in (303, 401, 405), \
            f"{caminho} respondeu {r.status_code} sem sessão — a guarda abriu"
        if r.status_code == 303:
            assert r.headers["location"] == "/login", caminho


def test_com_senha_temporaria_a_raiz_ainda_leva_para_a_troca(fechado, monkeypatch):
    """O defeito que a primeira versão desta mudança criou.

    Liberei `/` no TOPO da guarda, antes da verificação de sessão. Com isso quem
    recebe senha do administrador — e deve ser levado a `/senha` em qualquer
    rota até escolher a própria — abriria o aplicativo direto pela raiz. A
    liberação vale só para quem NÃO tem sessão; com sessão, a raiz segue a
    guarda normal.
    """
    monkeypatch.setattr(main.usuariosmod, "precisa_trocar", lambda email: True)
    r = _com_sessao(fechado).get("/")
    assert r.status_code == 303 and r.headers["location"] == "/senha", \
        "a raiz passou por cima da troca obrigatória de senha"


def test_a_raiz_nao_serve_a_landing_para_fragmento_htmx(fechado):
    """Um `hx-get` que caísse na landing colaria a página de marketing inteira
    dentro do canvas. Sem sessão, fragmento continua recebendo o 401 com
    HX-Redirect."""
    r = fechado.get("/", headers={"HX-Request": "true"})
    assert r.status_code == 401
    assert r.headers.get("HX-Redirect") == "/login"


def test_a_lista_de_livres_nao_contem_a_raiz():
    """Guarda estrutural, para a próxima pessoa não «simplificar» juntando as
    duas listas."""
    assert "/" not in main.LIVRES, \
        "«/» dentro de LIVRES libera tudo, porque LIVRES é usado com startswith"
    assert main.LIVRE_EXATO == ("/",)
    fonte = (RAIZ / "orga" / "main.py").read_text(encoding="utf-8")
    assert "req.url.path in LIVRE_EXATO" in fonte, \
        "a raiz tem de ser liberada por igualdade, não por prefixo"


# --------------------------------------------------------------------- A LANDING
def test_a_landing_existe_e_e_estatica():
    assert LANDING.exists(), "web/publico/landing.html não está no lugar"
    t = LANDING.read_text(encoding="utf-8")
    assert t.lstrip().startswith("<!"), "a landing precisa ser um documento HTML"
    # Nada de Jinja: ela é servida como arquivo, sem contexto do sistema. Um
    # `{{ }}` aqui chegaria ao navegador como texto cru.
    assert "{{" not in t and "{%" not in t


def test_a_landing_nao_carrega_nada_do_organograma(fechado):
    """Ela é marketing servido sem sessão. Se algum dia passar a renderizar
    contexto do sistema, aparece aqui — e nome de pessoa numa página pública é
    o pior tipo de vazamento, porque ninguém vai procurá-lo."""
    r = fechado.get("/")
    for vestigio in ("hx-get", "hx-post", "/vistas/", "conta-item",
                     "btAvatar", "organograma-dados"):
        assert vestigio not in r.text, f"a landing traz «{vestigio}» do aplicativo"


def test_a_landing_tem_entrada_para_o_sistema(fechado):
    """Sem porta, quem já é usuário precisa saber o endereço de cor."""
    r = fechado.get("/")
    assert r.text.count('href="/login"') >= 1
    assert "Entrar" in r.text
    # E o destino responde de verdade.
    assert fechado.get("/login").status_code == 200


def test_a_entrada_sobrevive_ao_colapso_do_menu_no_celular():
    """A landing esconde os links de navegação em tela estreita:

        @media(max-width:880px){.topo nav a:not(.bt){display:none}}

    A entrada no sistema entrou como link simples na primeira versão e, medido
    no navegador a 390px, ficava invisível — num celular só se chegaria ao login
    rolando até o herói. Por isso ela carrega a classe `bt`, que a regra
    preserva. Confirmado depois: visível a 390px, e a página continua sem
    rolagem lateral.
    """
    t = LANDING.read_text(encoding="utf-8")
    cabecalho = t[t.index("<header"):t.index("</header>")]
    entrada = re.search(r'<a([^>]*)href="/login"', cabecalho)
    assert entrada, "a entrada saiu do cabeçalho"
    assert "bt" in entrada.group(1), \
        "a entrada do cabeçalho precisa da classe `bt`, senão o media query a esconde"
    # E a regra que motiva isso continua no arquivo — se ela sair, este teste
    # deixa de fazer sentido e alguém precisa saber.
    assert ".topo nav a:not(.bt){display:none}" in t


def test_toda_ancora_da_landing_resolve():
    t = LANDING.read_text(encoding="utf-8")
    ancoras = {m[1:] for m in re.findall(r'href="(#[^"]+)"', t)}
    ids = set(re.findall(r'id="([^"]+)"', t))
    assert ancoras, "a landing perdeu a navegação interna"
    assert not (ancoras - ids), f"âncoras sem destino: {sorted(ancoras - ids)}"


def test_os_links_externos_da_landing_sao_os_esperados():
    """Nenhum link para fora além das fontes do Google e do e-mail de contato.
    Um domínio de terceiro numa página pública nossa é coisa que se descobre
    de propósito, não por acidente."""
    t = LANDING.read_text(encoding="utf-8")
    externos = set(re.findall(r'(?:href|src)="(https?://[^"]+)"', t))
    hosts = {re.match(r"https?://([^/]+)", u).group(1) for u in externos}
    assert hosts <= {"fonts.googleapis.com", "fonts.gstatic.com"}, \
        f"host externo inesperado: {sorted(hosts)}"
    for m in re.findall(r'href="mailto:([^"?]+)', t):
        assert m == "contato@gplansis.com", f"e-mail inesperado: {m}"


def test_sem_o_arquivo_a_raiz_cai_no_login(fechado, monkeypatch):
    """Instalação sem a landing não pode virar erro 500 na porta de entrada."""
    monkeypatch.setattr(main, "LANDING", RAIZ / "web" / "publico" / "nao-existe.html")
    r = fechado.get("/")
    assert r.status_code == 303 and r.headers["location"] == "/login"
