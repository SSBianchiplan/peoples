"""Monitoramento de acessos: login e logout de cada usuário.

Trilha SEPARADA do ledger de mutações. Registra entrada (nas duas portas de
login) e saída, persiste no estado.json (sem reintroduzir campos de sessão), e
não registra logout sem sessão.

    pytest testes/test_acessos_log.py -q
"""
from __future__ import annotations

import json
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


def test_login_por_email_registra_entrada(cli, conta):
    conta("alguem@gplansis.com")
    n0 = len(main.ESTADO.acessos_log)
    r = cli.post("/entrar", data={"email": "alguem@gplansis.com", "senha": "senha-de-teste-123"},
                 follow_redirects=False)
    assert r.status_code == 303
    assert len(main.ESTADO.acessos_log) == n0 + 1
    ev = main.ESTADO.acessos_log[-1]
    assert ev["evento"] == "entrar"
    assert ev["email"] == "alguem@gplansis.com"
    assert ev["quando"]                                    # carimbo de tempo


def test_logout_registra_saida(cli):
    u = next(iter(main.ESTADO.unidades.values()))
    cookie = acesso.assinar({"sub": u.email or "x@gplansis.com", "uid": u.id})
    n0 = len(main.ESTADO.acessos_log)
    r = cli.post("/sair", headers={"Cookie": f"{acesso.COOKIE}={cookie}"},
                 follow_redirects=False)
    assert r.status_code == 303
    assert len(main.ESTADO.acessos_log) == n0 + 1
    ev = main.ESTADO.acessos_log[-1]
    assert ev["evento"] == "sair" and ev["usuario_id"] == u.id


def test_logout_sem_sessao_nao_registra(cli):
    n0 = len(main.ESTADO.acessos_log)
    cli.post("/sair", follow_redirects=False)             # sem cookie
    assert len(main.ESTADO.acessos_log) == n0


def test_acessos_log_persiste_no_estado(cli):
    """serializar() inclui o log — a trilha sobrevive ao restart."""
    d = json.loads(main.serializar())
    assert "acessos_log" in d


def test_acessos_log_nao_reintroduz_a_sessao_no_persistido(cli, conta):
    conta("alguem@gplansis.com")
    """Persistir o log de acesso não pode trazer de volta os campos de sessão que
    o fix CAMPOS_SESSAO tirou do estado.json."""
    cli.post("/entrar", data={"email": "alguem@gplansis.com", "senha": "senha-de-teste-123"},
             follow_redirects=False)
    cfg_persistido = json.loads(main.serializar())["config"]
    for campo in cfgmod.CAMPOS_SESSAO:
        assert campo not in cfg_persistido
