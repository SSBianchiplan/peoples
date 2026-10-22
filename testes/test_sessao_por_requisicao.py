"""Sessão POR REQUISIÇÃO — o teste que faltava.

O bug: o login gravava a identidade e o RBAC da pessoa no `ESTADO.config` GLOBAL
(e ainda persistia). Como todos os leitores liam desse global, o ÚLTIMO login
virava "o usuário atual" de todo mundo: Bruno logava e a tela do Ana
passava a mostrar o Bruno.

A correção resolve a sessão por requisição, a partir do cookie assinado
(`resolver_sessao` → ContextVar → `acesso_vigente()`), e o login não toca mais o
global. Estes testes provam o isolamento — inclusive sob concorrência, que é onde
um estado global compartilhado vaza de verdade — e que o login não muta/persiste
nada. Sem eles, a regressão voltaria silenciosa e sem alarme.

    pytest testes/test_sessao_por_requisicao.py -q
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import acesso                                                   # noqa: E402
from orga import configuracao as cfgmod                                   # noqa: E402
from orga import main                                                     # noqa: E402


@pytest.fixture()
def cli():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def duas_pessoas(monkeypatch):
    """Duas unidades reais com papéis DISTINTOS em `Config.acessos`: A=Admin,
    B=Visualizador. Devolve (A, B, cookieA, cookieB). Restaura `acessos` ao fim —
    o estado é isolado por sessão, não por teste. Sem superadmin (que daria Admin
    a todos e mascararia o vazamento)."""
    monkeypatch.setenv("ORG_SUPERADMINS", "")     # nenhum override de superadmin
    us = list(main.ESTADO.unidades.values())
    assert len(us) >= 2, "a base de teste precisa de ao menos duas unidades"
    a, b = us[0], us[1]
    acessos_antes = main.ESTADO.config.acessos
    main.ESTADO.config.acessos = {
        a.id: {"papel": cfgmod.ADMIN,
               "escopo": {"tipo": "tudo", "valor": ""}, "modulos": []},
        b.id: {"papel": cfgmod.VIEWER,
               "escopo": {"tipo": "proprio", "valor": ""}, "modulos": []},
    }
    ck_a = acesso.assinar({"sub": a.email or "a@gplansis.com", "uid": a.id})
    ck_b = acesso.assinar({"sub": b.email or "b@gplansis.com", "uid": b.id})
    try:
        yield a, b, ck_a, ck_b
    finally:
        main.ESTADO.config.acessos = acessos_antes


def _cabecalho(cookie):
    # Cookie explícito por requisição (o JWT não tem ';' nem ','): é o que
    # precisamos para alternar identidades sem um jar persistente ambíguo.
    return {"Cookie": f"{acesso.COOKIE}={cookie}"}


def _quem(cli, cookie):
    """O que /api/v1/configuracao devolve para ESTE cookie: (usuario_id, perfil)."""
    r = cli.get("/api/v1/configuracao", headers=_cabecalho(cookie))
    assert r.status_code == 200
    c = r.json()
    return c["usuario_id"], c["perfil"]


# ---------------------------------------------------------------------------
# O cerne: Bruno não vira Ana
# ---------------------------------------------------------------------------
def test_cada_cookie_ve_a_propria_identidade(cli, duas_pessoas):
    a, b, ck_a, ck_b = duas_pessoas
    assert _quem(cli, ck_a) == (a.id, cfgmod.ADMIN)
    assert _quem(cli, ck_b) == (b.id, cfgmod.VIEWER)


def test_login_de_um_nao_muda_a_sessao_do_outro(cli, duas_pessoas):
    """A reprodução exata do bug relatado: B 'loga' (bate uma rota com o cookie
    dele) e A, logo depois, continua sendo A — não herda a identidade de B."""
    a, b, ck_a, ck_b = duas_pessoas
    assert _quem(cli, ck_a) == (a.id, cfgmod.ADMIN)      # A antes
    assert _quem(cli, ck_b) == (b.id, cfgmod.VIEWER)     # B entra
    assert _quem(cli, ck_a) == (a.id, cfgmod.ADMIN)      # A DEPOIS — intacto


def test_intercalado_sem_carry_over(cli, duas_pessoas):
    """A,B,A,B,… cada resposta reflete só o próprio cookie — prova o reset do
    ContextVar entre requisições que reusam o worker."""
    a, b, ck_a, ck_b = duas_pessoas
    esperado = [(a.id, cfgmod.ADMIN), (b.id, cfgmod.VIEWER)]
    for i in range(8):
        ck = ck_a if i % 2 == 0 else ck_b
        assert _quem(cli, ck) == esperado[i % 2]


def test_sem_cookie_cai_no_global(cli, duas_pessoas):
    """Sem cookie (dev/testes), `acesso_vigente()` devolve o Config global — o
    modo aberto de hoje, preservado. Não deve refletir nenhuma das duas pessoas."""
    r = cli.get("/api/v1/configuracao")
    assert r.status_code == 200
    assert r.json()["perfil"] == main.ESTADO.config.perfil


# ---------------------------------------------------------------------------
# Concorrência real: onde um global compartilhado vaza de verdade
# ---------------------------------------------------------------------------
def test_isolamento_sob_concorrencia(duas_pessoas):
    """N requisições SIMULTÂNEAS alternando os dois cookies, contra o endpoint
    sync (threadpool). Se a sessão ainda morasse num global, as requisições
    concorrentes se sobrescreveriam e A veria o perfil de B. Usa httpx.AsyncClient
    para sobrepor de fato os endpoints sync no threadpool."""
    import httpx
    a, b, ck_a, ck_b = duas_pessoas
    pares = [(ck_a, (a.id, cfgmod.ADMIN)), (ck_b, (b.id, cfgmod.VIEWER))]

    async def corridas():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://teste") as ac:
            async def bate(cookie):
                r = await ac.get("/api/v1/configuracao", headers=_cabecalho(cookie))
                c = r.json()
                return c["usuario_id"], c["perfil"]
            tarefas = [bate(pares[i % 2][0]) for i in range(40)]
            return await asyncio.gather(*tarefas)

    vistos = asyncio.run(corridas())
    vazamentos = [(i, v) for i, v in enumerate(vistos) if v != pares[i % 2][1]]
    assert not vazamentos, f"vazou entre sessões concorrentes: {vazamentos[:5]}"


# ---------------------------------------------------------------------------
# O login não escreve sessão em lugar nenhum durável
# ---------------------------------------------------------------------------
def test_login_nao_muta_a_sessao_do_global(cli, monkeypatch, conta):
    conta("alguem@gplansis.com")
    """POST /entrar não pode tocar os campos de SESSÃO do Config global. (Persistir
    o log de acesso via gravar() é OK — não é campo de sessão, e para_persistir()
    já exclui a sessão; ver test_serializar_nao_grava_os_campos_de_sessao.)"""
    monkeypatch.setattr(main, "gravar", lambda *a, **k: None)   # sem tocar o disco
    antes = (main.ESTADO.config.usuario_id, main.ESTADO.config.perfil,
             main.ESTADO.config.escopo_tipo, main.ESTADO.config.escopo_valor,
             list(main.ESTADO.config.modulos_visiveis))
    r = cli.post("/entrar", data={"email": "alguem@gplansis.com", "senha": "senha-de-teste-123"},
                 follow_redirects=False)
    assert r.status_code == 303 and acesso.COOKIE in r.cookies
    depois = (main.ESTADO.config.usuario_id, main.ESTADO.config.perfil,
              main.ESTADO.config.escopo_tipo, main.ESTADO.config.escopo_valor,
              list(main.ESTADO.config.modulos_visiveis))
    assert depois == antes, "o login não deve tocar a sessão no Config global"


# ---------------------------------------------------------------------------
# Sessão é EFÊMERA: nunca chega ao estado.json compartilhado
# ---------------------------------------------------------------------------
def test_serializar_nao_grava_os_campos_de_sessao():
    """O que `gravar()` escreve no estado.json (via serializar) não pode conter
    identidade/perfil de sessão — senão um preview de dev ou um login viraria
    estado durável e compartilhado. `acessos` (atribuição) continua persistindo."""
    import json
    cfg_persistido = json.loads(main.serializar())["config"]
    for campo in cfgmod.CAMPOS_SESSAO:
        assert campo not in cfg_persistido, f"{campo} vazou para o estado durável"
    assert "acessos" in cfg_persistido


def test_estado_poluido_antigo_nao_recarrega_a_sessao():
    """Um estado.json de ANTES do fix pode ter perfil/usuario_id gravados (o bug).
    Ao carregar, esses campos são ignorados — a sessão nasce dos defaults, sem
    trancar a instância nem herdar a identidade de ninguém."""
    poluido = {"titulo": "Acme", "perfil": cfgmod.VIEWER, "usuario_id": "alguem",
               "escopo_tipo": "proprio", "escopo_valor": "x",
               "modulos_visiveis": ["dcr"]}
    cfg = cfgmod.Config.de_dict(poluido)
    assert cfg.perfil == cfgmod.ADMIN            # default, não o viewer poluído
    assert cfg.usuario_id is None
    assert cfg.escopo_tipo == "" and cfg.escopo_valor == ""
    assert cfg.modulos_visiveis == []
    assert cfg.titulo == "Acme"                  # config real (não-sessão) carrega
