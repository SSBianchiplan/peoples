"""
Acesso: sessão assinada, o login próprio (e-mail + senha) e a guarda que fecha
o sistema.

Módulo de segurança testa-se pelo que ele **recusa**. Assinatura adulterada,
token sem prazo, senha errada, e-mail de fora do domínio, força bruta e
primeiro acesso repetido são os jeitos de entrar sem credencial; cada um tem
um teste aqui. E pelo que ele permite: a porta continua abrindo para quem
deve entrar.

    pytest testes/test_acesso.py -q
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import acesso                                                   # noqa: E402
from orga import configuracao as cfgmod                                   # noqa: E402
from orga import main                                                     # noqa: E402
from orga import usuarios                                                 # noqa: E402

SENHA = "senha-de-teste-123"


@pytest.fixture()
def cli():
    from fastapi.testclient import TestClient
    usuarios._TENTATIVAS.clear()
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def com_email():
    """Uma unidade com e-mail — garantida, e não procurada. Num clone limpo o
    estado é o seed da SPEC, sem e-mail nenhum; a fixture ARRANJA um e devolve
    a unidade ao que era no fim."""
    alvo = next((u for u in main.ESTADO.unidades.values()
                 if u.email and acesso.dominio_valido(u.email)), None)
    if alvo is not None:
        yield alvo
        return
    alvo = next(iter(main.ESTADO.unidades.values()))
    anterior = alvo.email
    alvo.email = f"{alvo.id}@gplansis.com".lower()
    try:
        yield alvo
    finally:
        alvo.email = anterior


@pytest.fixture()
def sem_usuarios(tmp_path, monkeypatch):
    """Um arquivo de credenciais VAZIO só para este teste: o primeiro acesso é
    o único momento em que a ausência de usuário importa, e o arquivo isolado
    da suíte já acumulou contas de outros testes."""
    monkeypatch.setenv("ORG_USUARIOS_ARQUIVO", str(tmp_path / "usuarios.json"))
    usuarios._CACHE.clear()
    yield
    usuarios._CACHE.clear()


def _erro_da_tela(html: str) -> str:
    """Só o texto do balão de erro — a página inteira sempre contém as frases
    do formulário, então afirmar sobre ela não distingue guarda nenhuma."""
    m = re.search(r'<p class="erro"[^>]*>(.*?)</p>', html, re.S)
    return " ".join(m.group(1).split()) if m else ""


# ---------------------------------------------------------------------------
# Sessão assinada
# ---------------------------------------------------------------------------
def test_ida_e_volta_da_sessao():
    token = acesso.assinar({"sub": "a@b.com", "uid": "x1"})
    carga = acesso.verificar(token)
    assert carga and carga["sub"] == "a@b.com" and carga["uid"] == "x1"


def test_assinatura_adulterada_e_recusada():
    token = acesso.assinar({"sub": "a@b.com"})
    cab, corpo, ass = token.split(".")
    outra = ("A" if ass[0] != "A" else "B") + ass[1:]
    assert acesso.verificar(f"{cab}.{corpo}.{outra}") is None


def test_token_expirado_e_recusado():
    assert acesso.verificar(acesso.assinar({"sub": "a@b.com"}, ttl=-5)) is None


def test_token_sem_prazo_e_recusado():
    cab, corpo, _ = acesso.assinar({"sub": "a@b.com"}).split(".")
    import base64
    import json
    bruto = json.loads(base64.urlsafe_b64decode(corpo + "=="))
    bruto.pop("exp")
    corpo2 = base64.urlsafe_b64encode(json.dumps(bruto).encode()).decode().rstrip("=")
    dados = f"{cab}.{corpo2}"
    assert acesso.verificar(f"{dados}.{acesso._hmac(dados)}") is None


@pytest.mark.parametrize("lixo", ["", "a", "a.b", "a.b.c", None, "x" * 500])
def test_token_malformado_nao_explode(lixo):
    assert acesso.verificar(lixo) is None


# ---------------------------------------------------------------------------
# Domínio
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("email,ok", [
    ("a.b@gplansis.com", True),
    ("A.B@GPLANSIS.COM", True),
    ("alguem@gmail.com", False),
    ("sem-arroba", False),
    ("", False),
])
def test_dominio_da_organizacao(monkeypatch, email, ok):
    monkeypatch.setenv("ORG_DOMINIOS", "gplansis.com")
    assert acesso.dominio_valido(email) is ok


def test_sem_dominio_configurado_qualquer_email_bem_formado_vale(monkeypatch):
    monkeypatch.delenv("ORG_DOMINIOS", raising=False)
    assert acesso.dominio_valido("a@gmail.com") is True
    assert acesso.dominio_valido("sem-arroba") is False
    assert acesso.dominio_valido("@x.com") is False


# ---------------------------------------------------------------------------
# Login próprio: e-mail + senha
# ---------------------------------------------------------------------------
def test_login_exige_senha_correta(cli, conta):
    conta("alguem@gplansis.com")
    r = cli.post("/entrar", data={"email": "alguem@gplansis.com", "senha": "errada-errada"})
    assert r.status_code == 200 and acesso.COOKIE not in r.cookies
    assert "inválidos" in _erro_da_tela(r.text)


def test_email_inexistente_recebe_a_mesma_mensagem(cli, conta):
    """Sem enumeração: quem não existe e quem errou a senha veem o mesmo texto."""
    conta("alguem@gplansis.com")
    r1 = cli.post("/entrar", data={"email": "alguem@gplansis.com", "senha": "errada-errada"})
    r2 = cli.post("/entrar", data={"email": "ninguem@gplansis.com", "senha": "errada-errada"})
    assert _erro_da_tela(r1.text) == _erro_da_tela(r2.text)
    assert acesso.COOKIE not in r2.cookies


def test_login_sem_senha_cadastrada_nao_entra(cli):
    """Ter e-mail do domínio não basta mais — é a diferença para a identificação
    antiga, que aceitava qualquer endereço do domínio sem provar nada."""
    r = cli.post("/entrar", data={"email": "alguem@gplansis.com", "senha": ""})
    assert acesso.COOKIE not in r.cookies


def test_login_fora_do_organograma_entra_desvinculado(cli, conta):
    """Com senha, um e-mail que não é nó do organograma ATIVO entra desvinculado
    (uid vazio), com o acesso padrão. A identidade viaja no COOKIE, não no
    estado global."""
    conta("ninguem@gplansis.com")
    global_antes = main.ESTADO.config.usuario_id
    r = cli.post("/entrar", data={"email": "ninguem@gplansis.com", "senha": SENHA},
                 follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    carga = acesso.verificar(r.cookies[acesso.COOKIE])
    assert carga["uid"] == ""
    assert main.resolver_rbac(carga["uid"], carga["sub"]).usuario_id is None
    assert main.ESTADO.config.usuario_id == global_antes   # login não muta o global


def test_login_do_organograma_vincula_o_no(cli, conta, com_email):
    u = com_email
    conta(u.email)
    global_antes = main.ESTADO.config.usuario_id
    r = cli.post("/entrar", data={"email": u.email.upper(), "senha": SENHA},
                 follow_redirects=False)
    assert r.status_code == 303
    carga = acesso.verificar(r.cookies[acesso.COOKIE])
    assert carga["sub"] == u.email.lower() and carga["uid"] == u.id
    assert main.resolver_rbac(carga["uid"], carga["sub"]).usuario_id == u.id
    assert main.ESTADO.config.usuario_id == global_antes


def test_cookie_de_sessao_e_httponly(cli, conta, com_email):
    """A sessão não pode ser legível por JavaScript: um XSS a roubaria inteira."""
    u = com_email
    conta(u.email)
    r = cli.post("/entrar", data={"email": u.email, "senha": SENHA}, follow_redirects=False)
    bruto = r.headers["set-cookie"].lower()
    assert "httponly" in bruto and "samesite=lax" in bruto


def test_dominio_e_a_primeira_porta(cli, conta, monkeypatch):
    monkeypatch.setenv("ORG_DOMINIOS", "gplansis.com")
    conta("fora@gmail.com")                          # tem senha, mas é de fora
    r = cli.post("/entrar", data={"email": "fora@gmail.com", "senha": SENHA})
    assert acesso.COOKIE not in r.cookies
    assert "e-mail da organização" in _erro_da_tela(r.text)


def test_forca_bruta_trava_a_conta(cli, conta):
    conta("alvo@gplansis.com")
    for _ in range(usuarios.TENTATIVAS_MAX):
        cli.post("/entrar", data={"email": "alvo@gplansis.com", "senha": "errada-errada"})
    r = cli.post("/entrar", data={"email": "alvo@gplansis.com", "senha": SENHA})
    assert acesso.COOKIE not in r.cookies
    assert "Muitas tentativas" in _erro_da_tela(r.text)


def test_superadmin_entra_como_admin_total(cli, conta, monkeypatch):
    """O operador (superadmin) entra SEMPRE como Administrador total, mesmo fora
    do organograma ativo — com senha, como todo mundo. Resolvido POR REQUISIÇÃO
    a partir do cookie, sem mutar o Config global."""
    monkeypatch.setenv("ORG_SUPERADMINS", "chefe@gplansis.com")
    conta("chefe@gplansis.com")
    cfg = main.ESTADO.config
    antes = (cfg.usuario_id, cfg.perfil, cfg.escopo_tipo, list(cfg.modulos_visiveis))
    r = cli.post("/entrar", data={"email": "chefe@gplansis.com", "senha": SENHA},
                 follow_redirects=False)
    assert r.status_code == 303 and acesso.COOKIE in r.cookies
    carga = acesso.verificar(r.cookies[acesso.COOKIE])
    sess = main.resolver_rbac(carga["uid"], carga["sub"])
    assert sess.perfil == cfgmod.ADMIN
    assert sess.escopo_tipo == "tudo" and sess.modulos_visiveis == []
    assert (cfg.usuario_id, cfg.perfil, cfg.escopo_tipo, list(cfg.modulos_visiveis)) == antes


# ---------------------------------------------------------------------------
# Primeiro acesso
# ---------------------------------------------------------------------------
def test_primeiro_acesso_cria_o_admin_uma_vez_so(cli, sem_usuarios):
    assert usuarios.total() == 0
    assert "Criar administrador inicial" in cli.get("/login").text
    r = cli.post("/entrar/primeiro", data={"email": "op@gplansis.com", "senha": SENHA,
                                            "repetir": SENHA}, follow_redirects=False)
    assert r.status_code == 303 and acesso.COOKIE in r.cookies
    assert usuarios.existe("op@gplansis.com")
    # A partir daqui a tela deixa de oferecer, e a rota recusa.
    cli.cookies.clear()
    assert "Criar administrador inicial" not in cli.get("/login").text
    r = cli.post("/entrar/primeiro", data={"email": "outro@gplansis.com", "senha": SENHA,
                                            "repetir": SENHA})
    assert acesso.COOKIE not in r.cookies and not usuarios.existe("outro@gplansis.com")


def test_primeiro_acesso_exige_senhas_iguais_e_fortes(cli, sem_usuarios):
    r = cli.post("/entrar/primeiro", data={"email": "op@gplansis.com", "senha": SENHA,
                                            "repetir": "outra-coisa-123"})
    assert "não conferem" in _erro_da_tela(r.text) and usuarios.total() == 0
    r = cli.post("/entrar/primeiro", data={"email": "op@gplansis.com", "senha": "curta",
                                            "repetir": "curta"})
    assert "pelo menos" in _erro_da_tela(r.text) and usuarios.total() == 0


# ---------------------------------------------------------------------------
# Troca de senha
# ---------------------------------------------------------------------------
def test_senha_temporaria_leva_para_a_troca(cli, conta, monkeypatch):
    monkeypatch.setattr(acesso, "exigir_login", lambda: True)
    conta("nova@gplansis.com", precisa_trocar=True)
    r = cli.post("/entrar", data={"email": "nova@gplansis.com", "senha": SENHA},
                 follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/senha"
    # Com a senha temporária, toda rota leva a /senha — até ela ser trocada.
    r = cli.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/senha"
    r = cli.get("/vistas/tabela", headers={"HX-Request": "true"})
    assert r.status_code == 401 and r.headers.get("HX-Redirect") == "/senha"


def test_trocar_senha_prova_a_atual(cli, conta):
    conta("eu@gplansis.com")
    cli.post("/entrar", data={"email": "eu@gplansis.com", "senha": SENHA}, follow_redirects=False)
    r = cli.post("/senha", data={"atual": "errada-errada", "nova": "nova-senha-456",
                                 "repetir": "nova-senha-456"})
    assert "incorreta" in _erro_da_tela(r.text)
    assert usuarios.conferir("eu@gplansis.com", SENHA)
    r = cli.post("/senha", data={"atual": SENHA, "nova": "nova-senha-456",
                                 "repetir": "nova-senha-456"})
    assert "alterada" in r.text.lower()
    assert usuarios.conferir("eu@gplansis.com", "nova-senha-456")
    assert not usuarios.precisa_trocar("eu@gplansis.com")
    assert main.ESTADO.acessos_log[-1]["evento"] == "senha"


def test_senha_sem_sessao_vai_para_o_login(cli):
    cli.cookies.clear()
    r = cli.get("/senha", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


# ---------------------------------------------------------------------------
# Administração das contas (Config › Permissões)
# ---------------------------------------------------------------------------
def test_admin_define_e_remove_senha_de_um_colaborador(cli, com_email):
    u = com_email
    r = cli.post("/config/acessos/senha", data={"ref": u.id, "senha": SENHA, "temporaria": "1"})
    assert r.status_code == 200 and "Senha definida" in r.text
    assert usuarios.existe(u.email) and usuarios.precisa_trocar(u.email)
    r = cli.post("/config/acessos/senha/remover", data={"ref": u.id})
    assert "Senha removida" in r.text and not usuarios.existe(u.email)


def test_admin_cria_conta_fora_do_organograma(cli):
    r = cli.post("/config/acessos/senha", data={"email": "operador@gplansis.com", "senha": SENHA})
    assert "Senha definida" in r.text and usuarios.existe("operador@gplansis.com")
    assert "operador@gplansis.com" in cli.get("/vistas/configuracoes?aba=permissoes").text


def test_admin_nao_remove_a_propria_senha(cli, conta):
    conta("eu@gplansis.com")
    cli.post("/entrar", data={"email": "eu@gplansis.com", "senha": SENHA}, follow_redirects=False)
    r = cli.post("/config/acessos/senha/remover", data={"email": "eu@gplansis.com"})
    assert "própria senha" in r.text and usuarios.existe("eu@gplansis.com")


def test_senha_curta_e_recusada_pelo_admin(cli, com_email):
    r = cli.post("/config/acessos/senha", data={"ref": com_email.id, "senha": "curta"})
    assert "pelo menos" in r.text and not usuarios.existe(com_email.email)


# ---------------------------------------------------------------------------
# Guarda
# ---------------------------------------------------------------------------
def test_sistema_aberto_por_padrao(cli):
    """Ligar a exigência por conta própria trancaria quem já está usando."""
    assert acesso.exigir_login() is False
    assert cli.get("/").status_code == 200


def test_exigencia_fecha_tudo_menos_o_login_e_a_apresentacao(cli, monkeypatch):
    """A raiz deixou de redirecionar: sem sessão ela serve a apresentação
    pública, com o botão «Entrar» levando a /login (ver
    testes/test_landing_publica.py). O que este teste continua guardando é o
    resto — nenhuma outra rota abre sem sessão."""
    monkeypatch.setattr(acesso, "exigir_login", lambda: True)
    cli.cookies.clear()
    raiz = cli.get("/", follow_redirects=False)
    assert raiz.status_code == 200 and "A estrutura da sua empresa" in raiz.text
    for caminho in ("/vistas/canvas", "/vistas/configuracoes", "/panorama"):
        r = cli.get(caminho, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login", caminho
    assert cli.get("/login").status_code == 200


def test_fragmento_htmx_recebe_redirect_proprio(cli, monkeypatch):
    """Devolver a página de login inteira para um fragmento htmx colaria o
    formulário de login dentro do canvas."""
    monkeypatch.setattr(acesso, "exigir_login", lambda: True)
    cli.cookies.clear()
    r = cli.get("/vistas/tabela", headers={"HX-Request": "true"})
    assert r.status_code == 401
    assert r.headers.get("HX-Redirect") == "/login"


def test_sair_apaga_a_sessao(cli, conta, com_email):
    u = com_email
    conta(u.email)
    antes = main.ESTADO.config.usuario_id
    try:
        cli.post("/entrar", data={"email": u.email, "senha": SENHA}, follow_redirects=False)
        r = cli.post("/sair", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"
        assert acesso.verificar(cli.cookies.get(acesso.COOKIE)) is None
    finally:
        main.ESTADO.config.usuario_id = antes


def test_segredo_fraco_e_erro_quando_a_porta_esta_fechada(monkeypatch):
    """Segredo curto com login exigido é sessão forjável — tem de falhar alto,
    no arranque, e não silenciosamente em produção."""
    monkeypatch.setattr(acesso, "exigir_login", lambda: True)
    monkeypatch.setenv("JWT_SECRET", "curto")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        acesso.segredo()


def test_nao_ha_mais_sso_corporativo(cli):
    """O Entra saiu: as rotas antigas não existem e o módulo não as expõe."""
    assert cli.post("/entrar/microsoft", follow_redirects=False).status_code == 404
    assert cli.get("/entrar/microsoft/callback", follow_redirects=False).status_code == 404
    assert not hasattr(acesso, "entra_configurado")
    assert "Microsoft" not in cli.get("/login").text
