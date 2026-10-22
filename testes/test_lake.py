"""
Lakehouse — a base intermediária e a API somente-leitura.

O que estes testes protegem não é o SQL (isso o Postgres verifica): é o
CONTRATO. Nome de vista fora do catálogo não vira consulta; a API não tem rota
de escrita; o token de serviço é comparado em tempo constante; e sem lakehouse
configurado o sistema responde "indisponível" em vez de quebrar.

    pytest testes/test_lake.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import lake                                                     # noqa: E402
from orga import main                                                     # noqa: E402


@pytest.fixture()
def cli():
    with TestClient(main.app) as c:
        yield c


def test_catalogo_lista_as_vistas(cli):
    r = cli.get("/api/v1/lake")
    assert r.status_code == 200
    d = r.json()
    assert d["somente_leitura"] is True
    nomes = {v["nome"] for v in d["vistas"]}
    assert {"painel_executivo", "skills_cobertura", "clima_pti"} <= nomes
    assert all(v["fonte"].startswith(("gold.", "silver.")) for v in d["vistas"])


def test_vista_fora_do_catalogo_e_404(cli):
    """Nome vindo da URL nunca vira SQL: só o catálogo fechado vira consulta."""
    r = cli.get("/api/v1/lake/pg_authid")
    assert r.status_code == 404 and r.json()["erro"] == "vista desconhecida"
    for tentativa in ("gold.painel_executivo; drop table x", "../etc", "org.pessoa"):
        assert cli.get(f"/api/v1/lake/{tentativa}").status_code in (404, 200)
        assert lake.consultar(tentativa).get("erro") == "vista desconhecida"


def test_sem_lakehouse_configurado_responde_indisponivel(cli, monkeypatch):
    monkeypatch.delenv("LAKE_LEITOR_DSN", raising=False)
    r = cli.get("/api/v1/lake/painel_executivo")
    assert r.status_code == 200 and "indisponível" in r.json()["erro"]


def test_nao_existe_rota_de_escrita_no_lake(cli):
    caminhos = [getattr(r, "path", "") for r in main.app.routes]
    for r in main.app.routes:
        if getattr(r, "path", "").startswith("/api/v1/lake"):
            assert set(getattr(r, "methods", set())) <= {"GET", "HEAD"}
    assert "/api/v1/lake" in caminhos
    assert cli.post("/api/v1/lake/painel_executivo").status_code == 405


def test_token_de_servico(monkeypatch):
    monkeypatch.setenv("ORG_LAKE_TOKENS", "tok-um , tok-dois")
    assert lake.token_valido("tok-um") and lake.token_valido("tok-dois")
    assert not lake.token_valido("tok-tres")
    assert not lake.token_valido("") and not lake.token_valido(None)
    monkeypatch.delenv("ORG_LAKE_TOKENS")
    assert not lake.token_valido("tok-um")            # sem tokens, nada passa


def test_token_abre_a_api_do_lake_com_login_exigido(cli, monkeypatch):
    """Máquina-a-máquina não tem navegador: com token válido a API do lake
    responde mesmo com o sistema fechado; sem token, vai para o login."""
    from orga import acesso
    monkeypatch.setattr(acesso, "exigir_login", lambda: True)
    monkeypatch.setenv("ORG_LAKE_TOKENS", "tok-servico")
    cli.cookies.clear()
    r = cli.get("/api/v1/lake", headers={"Authorization": "Bearer tok-servico"})
    assert r.status_code == 200
    r = cli.get("/api/v1/lake", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    r = cli.get("/api/v1/lake", headers={"Authorization": "Bearer errado"},
                follow_redirects=False)
    assert r.status_code == 303


def test_limite_e_saneado():
    assert lake.LIMITE_PADRAO <= lake.LIMITE_MAX
    d = lake.consultar("painel_executivo", limite=10 ** 9)
    assert "erro" in d or d["total"] <= lake.LIMITE_MAX


def test_catalogo_so_expoe_gold_e_silver():
    """bronze tem nome de gente e retrato cru: não é publicável."""
    assert all(f.startswith(("gold.", "silver.")) for f, _d in lake.VISTAS.values())
