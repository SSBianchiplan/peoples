"""Cota de IA da MarIA (auditoria M5): custo com teto por pessoa.

Nenhum teste chama a Anthropic: `urlopen` é trocado por um falso que devolve o
`usage` que a API devolveria — ou falha alto se for chamado quando não devia.

    pytest testes/test_ia_cota.py -q
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import urllib.error
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import configuracao as cfgmod                                    # noqa: E402
from orga import ia_cota                                                  # noqa: E402
from orga import main                                                     # noqa: E402
from orga import maria                                                    # noqa: E402


@pytest.fixture()
def cli():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    """Ledger novo por teste, chave fictícia e limites zerados."""
    monkeypatch.setenv("ORG_IA_USO_ARQUIVO", str(tmp_path / "ia_uso.sqlite3"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-teste-ficticio")
    ia_cota.zerar_limites()
    conversa, assist = list(main.ESTADO.conversa), list(main.ESTADO.assistencias)
    cota = main.ESTADO.config.maria_cota_usd
    yield tmp_path / "ia_uso.sqlite3"
    main.ESTADO.conversa, main.ESTADO.assistencias = conversa, assist
    main.ESTADO.config.maria_cota_usd = cota
    ia_cota.zerar_limites()


def linhas(caminho):
    c = sqlite3.connect(caminho)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute("SELECT * FROM ia_uso ORDER BY id")]
    finally:
        c.close()


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def anthropic_falsa(monkeypatch, usage: dict, modelo="claude-haiku-4-5", texto="Resposta."):
    chamadas = []

    def urlopen(pedido, timeout=0):
        chamadas.append(json.loads(pedido.data))
        return _Resp(json.dumps({"model": modelo, "usage": usage,
                                 "content": [{"type": "text", "text": texto}]}).encode())
    monkeypatch.setattr(maria.urllib.request, "urlopen", urlopen)
    return chamadas


def proibida(monkeypatch):
    def urlopen(*a, **k):
        raise AssertionError("a Anthropic não podia ter sido chamada")
    monkeypatch.setattr(maria.urllib.request, "urlopen", urlopen)


def estoura(caminho_ledger, quem="anon", valor=999.0):
    ia_cota.registrar(quem, "teste", "claude-opus-5-5", {}, valor, True, None, 1)


# ---------------------------------------------------------------------------
# Estourou -> 402, sem chamar o modelo
# ---------------------------------------------------------------------------
def test_cota_estourada_da_402_na_pergunta(cli, monkeypatch, ledger):
    estoura(ledger)
    proibida(monkeypatch)
    r = cli.post("/maria/perguntar", data={"pergunta": "Quantas pessoas?",
                                           "capacidade": maria.DESCREVER})
    assert r.status_code == 402
    assert "Cota de IA do mês atingida" in r.text
    assert len(linhas(ledger)) == 1             # nada novo: o modelo não foi chamado


def test_cota_estourada_da_402_no_chat_e_nao_suja_o_fio(cli, monkeypatch, ledger):
    estoura(ledger)
    proibida(monkeypatch)
    antes = len(main.ESTADO.conversa)
    r = cli.post("/maria/chat", data={"pergunta": "Oi"})
    assert r.status_code == 402
    assert "Cota de IA" in r.text
    assert len(main.ESTADO.conversa) == antes


def test_cota_estourada_da_402_no_agente(cli, monkeypatch, ledger):
    estoura(ledger)
    proibida(monkeypatch)
    r = cli.post("/maria/agente", data={"pedido": "Crie um time de vendas com 2 analistas"})
    assert r.status_code == 402


def test_cota_propria_vale_mais_que_o_padrao(ledger):
    ia_cota.registrar("u1", "teste", "x", {}, 3.0, True, None, 1)
    assert ia_cota.cota_de("u1", 20.0) == 20.0
    ia_cota.define_cota("u1", 2)
    with pytest.raises(ia_cota.Recusa) as e:
        ia_cota.verificar("u1", 20.0)
    assert e.value.status == 402
    ia_cota.define_cota("u1", "")                # volta ao padrão
    ia_cota.verificar("u1", 20.0)


def test_ritmo_por_minuto_da_429(ledger):
    for _ in range(ia_cota.POR_MINUTO):
        with ia_cota.em_curso("u2"):
            pass
    with pytest.raises(ia_cota.Recusa) as e:
        ia_cota.verificar("u2", 20.0)
    assert e.value.status == 429


# ---------------------------------------------------------------------------
# Sem chave -> resposta graciosa
# ---------------------------------------------------------------------------
def test_sem_chave_e_gracioso(cli, monkeypatch, ledger):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    proibida(monkeypatch)
    r = cli.post("/maria/perguntar", data={"pergunta": "Quantas pessoas?",
                                           "capacidade": maria.DESCREVER})
    assert r.status_code == 200
    assert "ANTHROPIC_API_KEY" in r.text
    assert "Traceback" not in r.text
    assert linhas(ledger) == []
    r = cli.post("/maria/chat", data={"pergunta": "Oi"})
    assert r.status_code == 200 and "Traceback" not in r.text


# ---------------------------------------------------------------------------
# Corpo grande -> 413
# ---------------------------------------------------------------------------
def test_corpo_grande_da_413(cli, monkeypatch, ledger):
    proibida(monkeypatch)
    grande = "x" * (ia_cota.CORPO_MAXIMO + 10)
    for rota, campo in (("/maria/perguntar", "pergunta"), ("/maria/chat", "pergunta"),
                        ("/maria/agente", "pedido")):
        r = cli.post(rota, data={campo: grande})
        assert r.status_code == 413, rota
    assert linhas(ledger) == []


# ---------------------------------------------------------------------------
# Uso real gravado
# ---------------------------------------------------------------------------
def test_uso_real_e_gravado_com_custo(cli, monkeypatch, ledger):
    chamadas = anthropic_falsa(monkeypatch, {"input_tokens": 1000, "output_tokens": 500,
                                             "cache_read_input_tokens": 2000,
                                             "cache_creation_input_tokens": 0})
    r = cli.post("/maria/perguntar", data={"pergunta": "Quantas pessoas?",
                                           "capacidade": maria.DESCREVER})
    assert r.status_code == 200
    assert len(chamadas) == 1
    (l,) = linhas(ledger)
    assert (l["usuario_id"], l["recurso"], l["ok"]) == ("anon", "perguntar", 1)
    assert (l["input_tokens"], l["output_tokens"], l["cache_read"]) == (1000, 500, 2000)
    esperado = (1000 * 1 + 500 * 5 + 2000 * 1 * 0.1) / 1e6      # haiku-4-5: 1/5
    assert l["custo_usd"] == pytest.approx(esperado)
    assert ia_cota.gasto_do_mes("anon") == pytest.approx(esperado)


def test_modelo_fora_da_lista_nao_passa(cli, monkeypatch, ledger):
    chamadas = anthropic_falsa(monkeypatch, {"input_tokens": 1, "output_tokens": 1})
    cli.post("/maria/perguntar", data={"pergunta": "Oi", "modelo": "claude-caro-inventado",
                                       "capacidade": maria.DESCREVER})
    assert chamadas[0]["model"] in maria.modelos()


# ---------------------------------------------------------------------------
# Erro da Anthropic não vaza detalhe
# ---------------------------------------------------------------------------
def test_erro_da_anthropic_nao_vaza_detalhe(cli, monkeypatch, ledger):
    def urlopen(pedido, timeout=0):
        raise urllib.error.HTTPError(maria.API, 400, "Bad Request", {},
                                     io.BytesIO(b'{"error":"org-segredo-interno 123"}'))
    monkeypatch.setattr(maria.urllib.request, "urlopen", urlopen)
    r = cli.post("/maria/chat", data={"pergunta": "Oi"})
    assert r.status_code == 200
    assert "org-segredo-interno" not in r.text
    assert "não respondeu como esperado" in r.text
    (l,) = linhas(ledger)
    assert (l["ok"], l["erro"], l["custo_usd"]) == (0, "http_400", 0)


def test_falha_de_rede_nao_vaza_detalhe(monkeypatch, ledger):
    def urlopen(pedido, timeout=0):
        raise OSError("conexão recusada em 10.0.0.7:443")
    monkeypatch.setattr(maria.urllib.request, "urlopen", urlopen)
    r = maria.perguntar("Oi", {}, quem="u3")
    assert not r["ok"] and "10.0.0.7" not in r["mensagem"]


# ---------------------------------------------------------------------------
# Só administrador altera cota
# ---------------------------------------------------------------------------
def test_so_admin_altera_cota(cli, ledger):
    cfg = main.ESTADO.config
    perfil = cfg.perfil
    try:
        cfg.perfil = cfgmod.VIEWER
        r = cli.post("/maria/cota", data={"cota_usd": "999"})
        assert r.status_code == 403
        assert cfg.maria_cota_usd != 999
        r = cli.put("/maria/cota/u9", json={"cota_usd": 999})
        assert r.status_code == 403
        assert ia_cota.cota_propria("u9") is None
        uso = cli.get("/maria/cota/uso").json()           # leitor vê só o próprio
        assert all(p["usuario_id"] == "anon" for p in uso["pessoas"])
    finally:
        cfg.perfil = perfil
    r = cli.post("/maria/cota", data={"cota_usd": "7.5"})
    assert r.status_code == 200 and cfg.maria_cota_usd == 7.5
    r = cli.post("/maria/cota", data={"cota_usd": "-1"})
    assert r.status_code == 400 and cfg.maria_cota_usd == 7.5
    r = cli.put("/maria/cota/u9", json={"cota_usd": 3})
    assert r.status_code == 200 and ia_cota.cota_propria("u9") == 3
    r = cli.put("/maria/cota/u9", json={"cota_usd": None})
    assert r.status_code == 200 and ia_cota.cota_propria("u9") is None


def test_migracao_idempotente(ledger):
    for _ in range(3):
        assert ia_cota.gasto_do_mes("x") == 0
    c = sqlite3.connect(ledger)
    nomes = {r[0] for r in c.execute("SELECT name FROM sqlite_master")}
    c.close()
    assert {"ia_uso", "ia_cota", "ia_uso_usuario_ts"} <= nomes
