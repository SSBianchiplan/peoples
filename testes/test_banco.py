"""
Banco de dados: mapeamento, DDL e a carga gerada a partir do estado.

O que este módulo produz é **SQL que alguém vai executar**. Um nome com
apóstrofo mal escapado não é um defeito cosmético: é uma instrução a mais no
script. Por isso o escape tem teste próprio, com o dado real da base — que tem
"D'Avila" nele.

    pytest testes/test_banco.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import banco                                                    # noqa: E402
from orga import main                                                     # noqa: E402


@pytest.fixture()
def cli():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


# ---------------------------------------------------------------------------
# Escape — o que separa um script de uma injeção
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("entrada,esperado", [
    ("simples", "'simples'"),
    ("D'Avila", "'D''Avila'"),
    ("'; DROP TABLE org.unidade; --", "'''; DROP TABLE org.unidade; --'"),
    ("", "NULL"),
    (None, "NULL"),
    (7, "7"),
    (True, "true"),
])
def test_literal_sql_escapa_aspas(entrada, esperado):
    assert banco._lit(entrada) == esperado


def test_nome_com_apostrofo_sai_escapado_na_carga():
    """A base tem 'D’Avila'. Se o escape falhar, o script quebra no cliente —
    ou pior, executa o que veio depois da aspa."""
    sql = banco.sql_carga(main.ESTADO.unidades, main.ESTADO.config)
    for u in main.ESTADO.unidades.values():
        if "'" in u.nome:
            assert u.nome.replace("'", "''") in sql
            assert f"'{u.nome}'" not in sql


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
def test_carga_e_transacional():
    """Metade de um organograma no banco é pior do que nenhum."""
    sql = banco.sql_carga(main.ESTADO.unidades, main.ESTADO.config)
    assert sql.count("BEGIN;") == 1
    assert sql.rstrip().endswith("COMMIT;")


def test_pai_sempre_antes_do_filho():
    """A FK de `parent_id` recusa filho antes do pai — a ordem é requisito,
    não estética."""
    sql = banco.sql_carga(main.ESTADO.unidades, main.ESTADO.config)
    posicao = {}
    for u in main.ESTADO.unidades.values():
        marca = f"INSERT INTO org.unidade (organograma_id, codigo"
        alvo = sql.find(f"'{u.codigo}'", sql.find(marca))
        posicao[u.id] = sql.find(f"o.id, '{u.codigo}'")
    for u in main.ESTADO.unidades.values():
        if u.parent_id and posicao[u.id] >= 0 and posicao[u.parent_id] >= 0:
            assert posicao[u.parent_id] < posicao[u.id], \
                f"{u.codigo} entra antes do pai"


def test_contagem_bate_com_o_estado():
    c = banco.contagem_prevista(main.ESTADO.unidades)
    us = list(main.ESTADO.unidades.values())
    assert c["org.unidade"] == len(us)
    # Pessoa e quem tem e-mail OU matricula, menos a raiz, que e no e nao gente.
    assert c["org.pessoa"] == sum(1 for u in us
                                  if u.parent_id is not None and (u.email or u.codigo))
    assert c["org.responsabilidade"] == sum(len(u.responsabilidades or []) for u in us)


def test_carga_e_reexecutavel():
    """Rodar duas vezes não pode duplicar nada.

    Onde há chave natural, `ON CONFLICT` resolve. Accountability não tem —
    duas linhas iguais na mesma unidade são legítimas —, então lá a
    idempotência vem de apagar antes de escrever, na mesma transação.
    """
    sql = banco.sql_carga(main.ESTADO.unidades, main.ESTADO.config)
    # Duas tabelas apagam antes de escrever, e por motivos diferentes.
    # Accountability nao tem chave natural: duas linhas iguais na mesma unidade
    # sao legitimas. Alocacao tem, mas usava `ON CONFLICT DO NOTHING` sem alvo,
    # o que deixava a linha antiga de pe — cargo e vinculo alterados nunca
    # chegavam, e a segunda carga parecia nao ter aplicado.
    sem_conflito = ("org.responsabilidade", "org.alocacao")
    for tabela in sem_conflito:
        assert f"DELETE FROM {tabela}" in sql
    for bloco in sql.split("INSERT INTO")[1:]:
        cabeca = bloco.split(";")[0]
        if any(t in cabeca.split("\n")[0] for t in sem_conflito):
            continue
        assert "ON CONFLICT" in cabeca, f"inserção sem guarda: {cabeca[:70]}"


def test_apagar_accountability_vem_antes_de_inserir():
    """Apagar depois de inserir zeraria a carga — a ordem é o mecanismo."""
    sql = banco.sql_carga(main.ESTADO.unidades, main.ESTADO.config)
    assert sql.index("DELETE FROM org.responsabilidade") < \
        sql.index("INSERT INTO org.responsabilidade")


# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------
def test_senha_nunca_aparece():
    """A URL vai para a tela; a senha vaza em print, em suporte e em vídeo."""
    mascarada = banco.mascarar("postgresql://org:segredo123@db.interno:5432/org")
    assert "segredo123" not in mascarada
    assert "org" in mascarada and "db.interno" in mascarada


def test_mascarar_aguenta_url_sem_credencial():
    assert banco.mascarar("") == ""
    assert banco.mascarar("postgresql:///org") == "postgresql:///org"


def test_sem_dsn_nao_esta_pronto(monkeypatch):
    monkeypatch.delenv("ORG_DATABASE_URL", raising=False)
    s = banco.situacao()
    assert s["tem_dsn"] is False and s["pronto"] is False
    ok, msg = banco.testar()
    assert ok is False and "ORG_DATABASE_URL" in msg


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------
def test_aba_banco_responde(cli):
    r = cli.get("/vistas/configuracoes?aba=banco")
    assert r.status_code == 200
    for tabela, _, _ in banco.TABELAS:
        assert tabela in r.text


def test_downloads_entregam_sql(cli):
    ddl = cli.get("/banco/schema.sql")
    assert ddl.status_code == 200 and "CREATE TABLE org.unidade" in ddl.text
    carga = cli.get("/banco/carga.sql")
    assert carga.status_code == 200 and "INSERT INTO org.unidade" in carga.text
    assert "attachment" in carga.headers["content-disposition"]


def test_escrever_sem_banco_e_recusado_com_motivo(cli, monkeypatch):
    """Sem driver ou sem DSN a ação falha — e diz por quê, em vez de sumir."""
    monkeypatch.setattr(banco, "driver", lambda: None)
    r = cli.post("/config/banco/carga")
    assert r.status_code == 200
    assert "recusada" in r.text or "driver" in r.text


def test_a_closure_e_preenchida_e_contada_certo():
    """A tabela existe para subárvore custar um índice em vez de recursão. Ela
    ficava VAZIA: ninguém a preenchia, e o comentário dizia "calculado no
    banco" sem nada no banco calculando — toda consulta que a usasse devolvia
    zero linhas, sem erro nenhum."""
    from orga import banco, main

    sql = banco.sql_carga(main.ESTADO.unidades, main.ESTADO.config)
    assert "org.unidade_closure" in sql, "a carga não preenche a closure"
    assert "WITH RECURSIVE" in sql
    # O par (n, n) precisa entrar: sem ele, "a subárvore de X" excluiria o
    # próprio X e toda contagem sairia um a menos.
    assert "0::smallint" in sql

    # E a previsão conta PARES, não nós: antes devolvia `len(us)`, o que só
    # acertava numa árvore de um nível.
    us = list(main.ESTADO.unidades.values())
    previsto = banco.contagem_prevista(main.ESTADO.unidades)["org.unidade_closure"]
    prof = main.profundidades(main.ESTADO.unidades)
    assert previsto == sum(prof[u.id] + 1 for u in us)
    if len(us) > 1 and max(prof.values()) > 0:
        assert previsto > len(us), "com mais de um nível há mais pares que nós"


def test_delegada_sem_destino_e_estado_valido_no_schema():
    """O organograma delega para as ÁREAS dos reportes diretos, que são várias
    e podem ter vários donos cada. Eleger um filho para receber a delegação
    inventaria uma precisão que o dado não tem."""
    from orga import banco

    ddl = banco.ddl()
    i = ddl.index("ck_resp_delegacao_coerente")
    trecho = ddl[i:i + 200]
    # Destino nomeado implica delegação; delegação NÃO implica destino.
    assert "delegada_para_unidade_id IS NULL OR origem = 'delegada'" in trecho
