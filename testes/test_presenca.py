"""Presença — quem está ativo agora.

Registro efêmero em memória: cada requisição COM sessão carimba o instante; a
lista mostra quem foi visto na janela, resolvido contra o organograma. Sem login
não há identidade, então quem não entrou não aparece.

    pytest testes/test_presenca.py -q
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import acesso                                                   # noqa: E402
from orga import main                                                     # noqa: E402


@pytest.fixture(autouse=True)
def presenca_limpa():
    """A presença é global em memória: limpa antes e depois para um teste não
    herdar os ativos de outro."""
    main.PRESENCA.clear()
    yield
    main.PRESENCA.clear()


@pytest.fixture()
def cli():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


def _duas_unidades():
    us = list(main.ESTADO.unidades.values())
    assert len(us) >= 2, "a base de teste precisa de ao menos duas unidades"
    return us[0], us[1]


def test_recente_aparece_e_antigo_some():
    a, b = _duas_unidades()
    main.PRESENCA[a.id] = time.time()                                   # agora
    main.PRESENCA[b.id] = time.time() - main.PRESENCA_JANELA - 5        # velho
    ids = [x["id"] for x in main.usuarios_ativos()]
    assert a.id in ids and b.id not in ids


def test_marca_o_proprio_e_o_poe_primeiro():
    a, b = _duas_unidades()
    main.PRESENCA[a.id] = time.time()
    main.PRESENCA[b.id] = time.time()
    ativos = main.usuarios_ativos(eu=b.id)
    assert ativos[0]["id"] == b.id and ativos[0]["eu"] is True
    assert any(x["id"] == a.id and x["eu"] is False for x in ativos)


def test_id_fora_do_organograma_e_ignorado():
    """Quem está no registro mas não é nó do ativo (ex.: desvinculado, ou nó
    removido) não tem card a mostrar — não entra na lista."""
    main.PRESENCA["nao-existe-xyz"] = time.time()
    assert main.usuarios_ativos() == []


def test_marcar_presenca_ignora_vazio():
    main._marcar_presenca(None)
    main._marcar_presenca("")
    assert main.PRESENCA == {}


def test_rota_presenca_lista_e_craxa(cli):
    a, _ = _duas_unidades()
    main.PRESENCA[a.id] = time.time()
    r = cli.get("/presenca")
    assert r.status_code == 200
    assert a.nome in r.text
    # o crachá de contagem volta por OOB para o botão
    assert 'id="presencaN"' in r.text and 'hx-swap-oob="true"' in r.text


def test_rota_presenca_vazia_diz_ninguem(cli):
    r = cli.get("/presenca")
    assert r.status_code == 200
    assert main.T("Ninguém por aqui agora.") in r.text or "Ninguém" in r.text


def test_requisicao_com_cookie_carimba_a_presenca(cli):
    """O batimento: qualquer requisição com sessão válida marca a pessoa como
    ativa (é o resolver_sessao que carimba) — é isso que o poll de 25s renova."""
    a, _ = _duas_unidades()
    cookie = acesso.assinar({"sub": a.email or "a@gplansis.com", "uid": a.id})
    cli.get("/api/v1/configuracao", headers={"Cookie": f"{acesso.COOKIE}={cookie}"})
    assert a.id in main.PRESENCA


def test_sem_cookie_nao_carimba_ninguem(cli):
    """Sem login não há identidade: uma requisição anônima não cria presença."""
    cli.get("/api/v1/configuracao")
    assert main.PRESENCA == {}
