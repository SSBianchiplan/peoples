"""Correções da auditoria de segurança (out/2026) — cada teste prova um achado.

A5  /banco/carga.sql e /banco/schema.sql só para o superadmin.
A6  aviso do servidor escapado; `th` escapa parâmetros; CSP com script-src sem
    'unsafe-inline'; páginas sem manipulador inline; lake só com token ou Admin.
M5  (cota da MarIA) fica na entrega transversal — ver DEPLOY.md.
M21 revogação de sessão por versão; Origin em POST; padrões fechados (acessos
    vazios, primeiro acesso, superadmin sem e-mail no código).
Extra: /api/v1/configuracao sem os registros de RH; módulo oculto também nas
    rotas de dado.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from orga import acesso, main, usuarios
from orga import configuracao as cfgmod

SENHA = "senha-de-teste-123"


@pytest.fixture()
def fechado(monkeypatch, tmp_path):
    """Produção: login exigido, credenciais isoladas, sem superadmin implícito."""
    monkeypatch.setenv("ORG_EXIGIR_LOGIN", "1")
    monkeypatch.setenv("JWT_SECRET", "segredo-de-teste-com-mais-de-32-caracteres-ok")
    monkeypatch.setenv("ORG_USUARIOS_ARQUIVO", str(tmp_path / "usuarios.json"))
    monkeypatch.setenv("ORG_SUPERADMINS", "op@gplansis.com")
    monkeypatch.delenv("ORG_ACESSO_ABERTO", raising=False)
    usuarios._CACHE.clear()
    usuarios._TENTATIVAS.clear()
    yield TestClient(main.app, follow_redirects=False)
    usuarios._CACHE.clear()


def _entrar(cli, email):
    if not usuarios.existe(email):
        usuarios.definir_senha(email, SENHA)
    r = cli.post("/entrar", data={"email": email, "senha": SENHA})
    assert r.status_code == 303 and acesso.COOKIE in r.cookies, r.text[:300]
    cli.cookies.set(acesso.COOKIE, r.cookies[acesso.COOKIE])
    return cli


# ------------------------------------------------------------------- A5
def test_carga_sql_recusada_para_quem_nao_e_superadmin(fechado):
    _entrar(fechado, "leitor@gplansis.com")
    for rota in ("/banco/carga.sql", "/banco/schema.sql"):
        r = fechado.get(rota)
        assert r.status_code == 403, rota
        assert "INSERT" not in r.text and "CREATE" not in r.text


def test_carga_sql_recusada_mesmo_para_admin_do_rbac(fechado, monkeypatch):
    monkeypatch.setenv("ORG_ACESSO_ABERTO", "1")          # todos Admin no RBAC
    _entrar(fechado, "admin@gplansis.com")
    assert fechado.get("/banco/carga.sql").status_code == 403


def test_carga_sql_liberada_para_o_superadmin(fechado):
    _entrar(fechado, "op@gplansis.com")
    r = fechado.get("/banco/carga.sql")
    assert r.status_code == 200 and "INSERT" in r.text
    assert fechado.get("/banco/schema.sql").status_code == 200


def test_sem_sessao_carga_sql_nao_sai(fechado):
    r = fechado.get("/banco/carga.sql")
    assert r.status_code in (303, 401)


def test_api_configuracao_nao_entrega_registros_de_rh():
    cli = TestClient(main.app)
    c = cli.get("/api/v1/configuracao").json()
    for chave in ("acessos", "onebyone", "mapa_talentos", "cgv_registros",
                  "gptw_respostas"):
        assert chave not in c
    assert "perfil_rotulo" in c and "titulo" in c


# ------------------------------------------------------------------- A6
def test_alerta_escapa_o_que_interpola():
    html = main.alerta(main.T("Senha definida para {email}.",
                              email='<img src=x onerror=alert(1)>@x.com'))
    assert "<img" not in html and "&lt;img" in html
    assert html.startswith('<div id="alerta"')


def test_planilha_recusada_nao_injeta_html():
    html = main.alerta(main.T("Planilha recusada: {erro}",
                              erro="<script>alert(1)</script>"))
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_th_mantem_a_marcacao_do_catalogo_e_escapa_o_parametro():
    tpl = main.tpl.env.from_string(
        "{{ th('Sem regra que case, o cargo cai no piso <b>{nivel}</b>.', nivel=x) }}")
    saida = tpl.render(th=lambda texto, **p: main.Markup(texto).format(**p),
                       x="<script>1</script>")
    assert "<b>" in saida and "<script>" not in saida and "&lt;script&gt;" in saida


def test_csp_com_nonce_e_sem_unsafe_inline_em_script():
    cli = TestClient(main.app)
    r = cli.get("/")
    csp = r.headers["content-security-policy"]
    script = re.search(r"script-src ([^;]*)", csp).group(1)
    assert "'self'" in script and "'unsafe-inline'" not in script
    assert "'unsafe-eval'" not in script
    nonce = re.search(r"'nonce-([^']+)'", script).group(1)
    # Todo <script> inline da página carrega o nonce desta resposta.
    inline = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>", r.text)
    inline = [a for a in inline if "application/json" not in a]
    assert inline and all(f'nonce="{nonce}"' in a for a in inline)
    assert "object-src 'none'" in csp and "frame-ancestors" in csp


def test_nonce_muda_a_cada_resposta():
    cli = TestClient(main.app)
    a = cli.get("/").headers["content-security-policy"]
    b = cli.get("/").headers["content-security-policy"]
    assert a != b


def test_paginas_e_fragmentos_sem_manipulador_inline():
    """A CSP barra onclick=; se algum voltar a um template, a tela quebra em
    produção sem erro no servidor — por isso a varredura é dos fontes."""
    from pathlib import Path
    pasta = Path(main.RAIZ) / "web" / "templates"
    for arq in pasta.glob("*.html"):
        texto = arq.read_text(encoding="utf-8")
        assert not re.search(r"\son[a-z]+\s*=", texto), arq.name
        assert not re.search(r"\shx-on[:\w-]*=", texto), arq.name
        assert "'js:" not in texto and '"js:' not in texto, arq.name
        assert not re.search(r"hx-trigger=\"[^\"]*\[", texto), arq.name
        # <script> executável só no base.html, e com nonce.
        for attrs in re.findall(r"<script([^>]*)>", texto):
            assert "src=" in attrs or "nonce=" in attrs or "application/json" in attrs, arq.name


def test_csp_js_permite_toda_funcao_usada_nos_templates():
    from pathlib import Path
    raiz = Path(main.RAIZ) / "web"
    js = (raiz / "estatico" / "csp.js").read_text(encoding="utf-8")
    usados = set()
    for arq in (raiz / "templates").glob("*.html"):
        for expr in re.findall(r'data-on-[a-z-]+="([^"]*)"',
                               arq.read_text(encoding="utf-8")):
            usados |= set(re.findall(r"([A-Za-z_][\w.]*)\(", expr))
    bloco = js.split("var PERMITIDAS = {")[1].split("};")[0]
    for nome in usados:
        assert re.search(r"['\s{,]" + re.escape(nome) + r"'?\s*:", bloco), nome


def test_landing_tem_csp_propria(fechado):
    r = fechado.get("/")
    assert "fonts.googleapis.com" in r.headers["content-security-policy"]
    assert "'unsafe-eval'" not in r.headers["content-security-policy"]


def test_lake_recusa_cookie_de_quem_nao_e_admin(fechado):
    _entrar(fechado, "leitor@gplansis.com")
    r = fechado.get("/api/v1/lake/colaborador")
    assert r.status_code == 403


def test_lake_aceita_token_de_servico(fechado, monkeypatch):
    monkeypatch.setenv("ORG_LAKE_TOKENS", "tok-servico")
    r = fechado.get("/api/v1/lake/colaborador",
                    headers={"Authorization": "Bearer tok-servico"})
    assert r.status_code != 403


# ------------------------------------------------------------------- M21
def test_post_de_outra_origem_e_recusado():
    cli = TestClient(main.app)
    r = cli.post("/foco/limpar", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = cli.post("/foco/limpar", headers={"Referer": "https://evil.example/x"})
    assert r.status_code == 403


def test_post_da_propria_origem_passa():
    cli = TestClient(main.app)
    r = cli.post("/foco/limpar", headers={"Origin": "http://testserver"})
    assert r.status_code == 200


def test_trocar_a_senha_encerra_as_outras_sessoes(fechado):
    _entrar(fechado, "pessoa@gplansis.com")
    assert fechado.get("/api/v1/configuracao").status_code == 200
    usuarios.definir_senha("pessoa@gplansis.com", "outra-senha-forte-1")
    r = fechado.get("/api/v1/configuracao")
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_remover_a_conta_encerra_a_sessao(fechado):
    _entrar(fechado, "desligado@gplansis.com")
    assert fechado.get("/api/v1/configuracao").status_code == 200
    usuarios.remover("desligado@gplansis.com")
    assert fechado.get("/api/v1/configuracao").status_code == 303


def test_trocar_a_propria_senha_mantem_esta_sessao(fechado):
    _entrar(fechado, "troca@gplansis.com")
    r = fechado.post("/senha", data={"atual": SENHA, "nova": "nova-senha-123",
                                     "repetir": "nova-senha-123"})
    assert r.status_code == 200 and acesso.COOKIE in r.cookies
    fechado.cookies.set(acesso.COOKIE, r.cookies[acesso.COOKIE])
    assert fechado.get("/api/v1/configuracao").status_code == 200


def test_cookie_antigo_sem_versao_continua_valido_ate_trocar(fechado):
    """Compatibilidade do deploy: cookie emitido antes (sem `v`) vale para a
    conta que ainda não trocou a senha depois da atualização."""
    usuarios.definir_senha("antigo@gplansis.com", SENHA)
    d = usuarios.ler()
    d["usuarios"]["antigo@gplansis.com"].pop("sessao_v")
    usuarios.salvar(d)
    fechado.cookies.set(acesso.COOKIE, acesso.assinar({"sub": "antigo@gplansis.com",
                                                       "uid": ""}))
    assert fechado.get("/api/v1/configuracao").status_code == 200


def test_acessos_vazios_nao_dao_admin_a_todos_com_login(fechado, monkeypatch):
    monkeypatch.setattr(main.ESTADO.config, "acessos", {})
    sess = main.resolver_rbac(None, "qualquer@gplansis.com")
    assert sess.perfil == cfgmod.VIEWER
    monkeypatch.setenv("ORG_ACESSO_ABERTO", "1")
    assert main.resolver_rbac(None, "qualquer@gplansis.com").perfil == cfgmod.ADMIN


def test_superadmin_nao_tem_email_fixo_no_codigo(monkeypatch):
    monkeypatch.delenv("ORG_SUPERADMINS", raising=False)
    monkeypatch.delenv("ORG_ADMIN_EMAIL", raising=False)
    assert acesso.superadmins() == frozenset()
    monkeypatch.setenv("ORG_ADMIN_EMAIL", "Dono@Empresa.com")
    assert acesso.superadmins() == frozenset({"dono@empresa.com"})


def test_primeiro_acesso_fechado_em_producao(fechado):
    r = fechado.post("/entrar/primeiro", data={"email": "op2@gplansis.com",
                                               "senha": SENHA, "repetir": SENHA})
    assert acesso.COOKIE not in r.cookies
    assert usuarios.total() == 0


def test_primeiro_acesso_com_liberacao_cria_operador(fechado, monkeypatch):
    monkeypatch.setenv("ORG_PRIMEIRO_ACESSO", "1")
    monkeypatch.setenv("ORG_SUPERADMINS", "")
    r = fechado.post("/entrar/primeiro", data={"email": "op2@gplansis.com",
                                               "senha": SENHA, "repetir": SENHA})
    assert acesso.COOKIE in r.cookies
    assert acesso.e_superadmin("op2@gplansis.com")


def test_modulo_oculto_tambem_nas_rotas_de_dado(monkeypatch):
    cfg = main.ESTADO.config
    monkeypatch.setattr(cfg, "perfil", cfgmod.VIEWER)
    monkeypatch.setattr(cfg, "modulos_visiveis", ["canvas"])
    cli = TestClient(main.app)
    assert cli.get("/talentos.csv").status_code == 403
    assert cli.get("/onebyone/export.json").status_code == 403
    monkeypatch.setattr(cfg, "modulos_visiveis", [])
    assert cli.get("/talentos.csv").status_code == 200


def test_helper_global_exige_admin(monkeypatch):
    monkeypatch.setattr(main.ESTADO.config, "perfil", cfgmod.VIEWER)
    antes = main.ESTADO.config.helper
    r = TestClient(main.app).post("/config/helper", data={"ligado": "0" if antes else "1"})
    assert r.status_code == 403 and main.ESTADO.config.helper == antes
