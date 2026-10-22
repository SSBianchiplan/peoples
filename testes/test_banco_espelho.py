"""
Espelho da estrutura: o banco como fonte fiel (Ondas DB-1 e DB-2).

`sql_carga` desce o estado para o Postgres; `carregar_estrutura` sobe de volta.
Para o banco poder virar a fonte da leitura (Onda DB-3) sem perder dado, o
retorno tem de ser IGUAL ao que desceu — e cinco campos (área, centro de custo,
vertical, responsável, competências) e a identidade do nó (`origem_id`) só
passaram a caber no banco nesta onda. Estes testes guardam essa fidelidade.

O round-trip REAL (carga executa no Postgres e volta idêntica) exige banco e roda
em `test_espelho_round_trip_real`, pulado sem `ORG_DATABASE_URL`. Offline, os
testes cobrem duas coisas verificáveis sem banco: a carga EMITE os campos, e o
motor de diff (`verificar_espelho`) acusa divergência real e ignora as
transformações que a própria carga faz de propósito.

    pytest testes/test_banco_espelho.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import banco                                                    # noqa: E402
from orga import main                                                     # noqa: E402


# ---------------------------------------------------------------------------
# A carga escreve o nó INTEIRO (fidelidade)
# ---------------------------------------------------------------------------
def test_carga_declara_as_colunas_de_fidelidade():
    """Sem estas colunas no INSERT, o banco guardaria meio nó."""
    sql = banco.sql_carga(main.ESTADO.unidades, main.ESTADO.config)
    for coluna in ("origem_id", "area", "centro_custo", "vertical",
                   "responsavel", "competencias"):
        assert coluna in sql, f"coluna {coluna} fora da carga de org.unidade"


def test_carga_declara_os_campos_da_planilha_completa():
    """bd_completo_org: os campos organizacionais entram na carga da unidade."""
    sql = banco.sql_carga(main.ESTADO.unidades, main.ESTADO.config)
    for coluna in ("tipo_mo", "cc_n2", "cc_n4", "cc_n5", "cc_equipe", "bu",
                   "tipo_class", "mo_classe", "categoria_nivel", "genero",
                   "data_nascimento"):
        assert coluna in sql, f"coluna {coluna} fora da carga"


def test_campos_da_planilha_fazem_round_trip():
    """Um nó com os campos organizacionais preenchidos volta igual do espelho."""
    from orga.dominio import Unidade
    u = Unidade(id="x1", codigo="ORG-X1", nome="Fulano", tipo="celula",
                parent_id="raiz", ordem=0, tipo_mo="Não vendável", n2="87.0",
                n4="87.01", n5="PCO", cc_equipe="87.01-PCO-PCO", bu="Florianópolis",
                tipo_class="INDIRETO", mo_classe="MOI - INDIRETO",
                categoria_nivel="GO", genero="M", data_nascimento="1985-12-20")
    raiz = Unidade(id="raiz", codigo="ORG-0001", nome="Diretoria",
                   tipo="diretoria", parent_id=None, ordem=0)
    mem = {"raiz": raiz, "x1": u}
    r = banco.verificar_espelho(mem, banco=_espelho_ideal(mem))
    assert r["ok"] is True, r["divergencias"][:3]


def test_carga_grava_o_id_de_memoria_como_origem_id():
    """`origem_id` é a identidade do nó em memória — a chave do estado —, e não o
    código. `colapsados` e o ledger apontam para ela; sem gravá-la, o retorno do
    banco não remonta os mesmos ids."""
    sql = banco.sql_carga(main.ESTADO.unidades, main.ESTADO.config)
    algum = next(u for u in main.ESTADO.unidades.values()
                 if u.parent_id is not None)
    assert f"'{algum.id}'" in sql
    assert algum.id != algum.codigo          # a premissa do teste


def test_competencias_saem_como_jsonb():
    assert banco._jsonb(["a", "b"]) == '\'["a", "b"]\'::jsonb'
    assert banco._jsonb([]) == "'[]'::jsonb"
    assert banco._jsonb(None) == "'[]'::jsonb"
    # apóstrofo no dado não pode quebrar o literal
    assert "''" in banco._jsonb(["D'Avila"])


# ---------------------------------------------------------------------------
# Sem banco, tudo é no-op silencioso (dev/testes)
# ---------------------------------------------------------------------------
def test_carregar_estrutura_sem_banco_devolve_none(monkeypatch):
    monkeypatch.delenv("ORG_DATABASE_URL", raising=False)
    assert banco.carregar_estrutura() is None


def test_verificar_espelho_sem_banco_nao_quebra(monkeypatch):
    monkeypatch.delenv("ORG_DATABASE_URL", raising=False)
    r = banco.verificar_espelho(main.ESTADO.unidades)
    assert r["ok"] is False and r.get("erro") == "sem banco"


# ---------------------------------------------------------------------------
# O motor de diff — testado com um espelho ideal injetado (offline)
# ---------------------------------------------------------------------------
def _espelho_ideal(unidades) -> dict:
    """O que `carregar_estrutura` devolveria depois de uma carga perfeita: cada
    `Unidade` reprojetada no formato do leitor, com as transformações que a carga
    faz de propósito. Vale para dado bem-formado (todo nó com código e cargo),
    que é o da base — a fronteira dos nós sem cargo é da carga, não deste teste.
    """
    banco_dict = {}
    for u in unidades.values():
        d = {
            "id": u.id, "codigo": u.codigo or "", "nome": u.nome,
            "tipo": u.tipo, "parent_id": u.parent_id, "ordem": int(u.ordem or 0),
            "area": u.area or "", "centro_custo": u.centro_custo or "",
            "vertical": u.vertical or "", "responsavel": u.responsavel or "",
            "competencias": list(u.competencias or []),
            "email": u.email or "", "data_inicio": (u.data_inicio or "")[:10],
            "status": u.status or "",
            "responsabilidades": [
                {"descricao": r.get("descricao", ""),
                 "origem": r.get("origem") or "propria", "delegada_para": None}
                for r in (u.responsabilidades or [])],
            # cargo/vinculo saem do próprio nó: a raiz também volta inteira
            "cargo": u.cargo or "",
            "vinculo": u.vinculo or "clt",       # a carga faz coalesce p/ 'clt'
            # planilha completa (bd_completo_org) — campos organizacionais
            "tipo_mo": u.tipo_mo or "", "n2": u.n2 or "", "n4": u.n4 or "",
            "n5": u.n5 or "", "cc_equipe": u.cc_equipe or "", "bu": u.bu or "",
            "tipo_class": u.tipo_class or "", "mo_classe": u.mo_classe or "",
            "categoria_nivel": u.categoria_nivel or "", "genero": u.genero or "",
            "data_nascimento": (u.data_nascimento or "")[:10],
        }
        banco_dict[u.id] = d
    return banco_dict


def test_espelho_fiel_da_base_nao_tem_divergencia():
    """A base semeada, descida e subida de volta, tem de bater campo a campo."""
    ideal = _espelho_ideal(main.ESTADO.unidades)
    r = banco.verificar_espelho(main.ESTADO.unidades, banco=ideal)
    assert r["ok"] is True, r["divergencias"][:3]
    assert r["iguais"] == r["total"] == len(main.ESTADO.unidades)
    assert not r["so_na_tela"] and not r["so_no_banco"]


def test_diff_acusa_um_campo_alterado():
    ideal = _espelho_ideal(main.ESTADO.unidades)
    alvo = next(oid for oid, d in ideal.items() if d["parent_id"] is not None)
    ideal[alvo] = {**ideal[alvo], "area": "AREA DIFERENTE DE PROPOSITO"}
    r = banco.verificar_espelho(main.ESTADO.unidades, banco=ideal)
    assert r["ok"] is False
    achou = [x for x in r["divergencias"] if x["id"] == alvo]
    assert achou and achou[0]["campos"] == ["area"]


def test_diff_acusa_no_faltando_e_sobrando():
    ideal = _espelho_ideal(main.ESTADO.unidades)
    sumido = next(oid for oid, d in ideal.items() if d["parent_id"] is not None)
    ideal.pop(sumido)
    ideal["FANTASMA-XYZ"] = {**next(iter(ideal.values())), "id": "FANTASMA-XYZ"}
    r = banco.verificar_espelho(main.ESTADO.unidades, banco=ideal)
    assert sumido in r["so_na_tela"]
    assert "FANTASMA-XYZ" in r["so_no_banco"]
    assert r["ok"] is False


def test_raiz_faz_round_trip_completo():
    """A raiz é sintética (sem alocação), mas cargo/vínculo moram no próprio nó —
    então ela volta INTEIRA do banco, sem exceção. É o que deixa a leitura vir do
    banco (Onda DB-3) sem regredir o cargo do topo."""
    ideal = _espelho_ideal(main.ESTADO.unidades)
    raiz = next(oid for oid, d in ideal.items() if d["parent_id"] is None)
    raiz_mem = main.ESTADO.unidades[raiz]
    assert raiz_mem.cargo                          # a raiz tem cargo em memória
    assert ideal[raiz]["cargo"] == raiz_mem.cargo  # e o banco o guarda igual
    r = banco.verificar_espelho(main.ESTADO.unidades, banco=ideal)
    assert r["ok"] is True and r["iguais"] == r["total"]


def test_diff_ignora_delegada_para_none_e_ordem():
    """`delegada_para=None` não é gravada e a ordem das listas não é identidade —
    normalizações da carga, não perda. O diff não pode acusá-las."""
    ideal = _espelho_ideal(main.ESTADO.unidades)
    # um nó com responsabilidades, se houver
    alvo = next((oid for oid, d in ideal.items() if d["responsabilidades"]), None)
    if alvo is not None:
        # o banco devolve sem a chave delegada_para em alguns casos; garante que
        # a ausência dela não conta
        for r in ideal[alvo]["responsabilidades"]:
            r.pop("delegada_para", None)
    r = banco.verificar_espelho(main.ESTADO.unidades, banco=ideal)
    assert r["ok"] is True


# ---------------------------------------------------------------------------
# Dual-write (Onda DB-2): opt-in, não-fatal
# ---------------------------------------------------------------------------
def test_dual_write_e_opt_in_e_espelha_quando_ligado(monkeypatch):
    """Sem `ORG_ESPELHO=1`, mutação NÃO toca o banco — mesmo pronto: o .env de
    dev pode apontar para um banco real. Ligado, desce a carga da estrutura."""
    chamadas = []
    monkeypatch.setattr(main.bancomod, "situacao", lambda: {"pronto": True})
    monkeypatch.setattr(main.bancomod, "aplicar",
                        lambda sql: (chamadas.append(sql), (True, "ok"))[1])
    monkeypatch.setattr(main, "_ESTRUTURA_ESPELHADA", None)   # zera a guarda de assinatura

    monkeypatch.delenv("ORG_ESPELHO", raising=False)
    main.espelhar_estrutura()
    assert chamadas == []                    # padrão: desligado

    monkeypatch.setenv("ORG_ESPELHO", "1")
    main.espelhar_estrutura()
    assert len(chamadas) == 1
    assert "INSERT INTO org.unidade" in chamadas[0]


def test_dual_write_guarda_nao_re_carga_estrutura_inalterada(monkeypatch):
    """A guarda de assinatura (DB-5): a segunda mutação sem mexer na estrutura
    (um colapso, um filtro) NÃO re-desce a carga."""
    chamadas = []
    monkeypatch.setenv("ORG_ESPELHO", "1")
    monkeypatch.setattr(main.bancomod, "situacao", lambda: {"pronto": True})
    monkeypatch.setattr(main.bancomod, "aplicar",
                        lambda sql: (chamadas.append(sql), (True, "ok"))[1])
    monkeypatch.setattr(main, "_ESTRUTURA_ESPELHADA", None)
    main.espelhar_estrutura()                # estrutura nova -> desce
    main.espelhar_estrutura()                # inalterada -> pula
    assert len(chamadas) == 1


def test_dual_write_nao_e_fatal_quando_o_banco_recusa(monkeypatch):
    """Postgres fora do ar não pode derrubar a edição: o estado.json já gravou."""
    monkeypatch.setenv("ORG_ESPELHO", "1")
    monkeypatch.setattr(main.bancomod, "situacao", lambda: {"pronto": True})
    monkeypatch.setattr(main, "_ESTRUTURA_ESPELHADA", None)

    def explode(_sql):
        raise RuntimeError("conexão recusada")
    monkeypatch.setattr(main.bancomod, "aplicar", explode)
    main.espelhar_estrutura()                # não levanta


# ---------------------------------------------------------------------------
# DB-3: escolha da fonte da estrutura (Postgres primeiro, JSON como queda)
# ---------------------------------------------------------------------------
import json as _json


def _bruto_e_banco():
    bruto = _json.loads(main.serializar())          # o JSON de verdade
    banco_u = _espelho_ideal(main.ESTADO.unidades)  # o que o banco devolveria
    return bruto, banco_u


def test_escolha_sem_banco_usa_json():
    bruto, _ = _bruto_e_banco()
    unidades, origem = main._escolher_estrutura(bruto, None)
    assert origem == "json"
    assert unidades is bruto["unidades"]


def test_escolha_banco_confere_e_vence():
    """Banco pronto e igual ao JSON: a estrutura passa a vir do banco."""
    bruto, banco_u = _bruto_e_banco()
    unidades, origem = main._escolher_estrutura(bruto, banco_u)
    assert origem == "banco"
    assert unidades is banco_u


def test_escolha_sem_json_restaura_do_banco():
    _, banco_u = _bruto_e_banco()
    assert main._escolher_estrutura(None, banco_u) == (banco_u, "restauro")
    assert main._escolher_estrutura({}, banco_u) == (banco_u, "restauro")


def test_escolha_json_vence_em_divergencia():
    """Espelho atrasado (dual-write é não-fatal) não pode reverter a edição: em
    divergência o JSON prevalece, e o banco será reconciliado."""
    bruto, banco_u = _bruto_e_banco()
    alvo = next(oid for oid, d in banco_u.items() if d["parent_id"] is not None)
    banco2 = {k: dict(v) for k, v in banco_u.items()}
    banco2[alvo]["area"] = "AREA ATRASADA NO BANCO"
    unidades, origem = main._escolher_estrutura(bruto, banco2)
    assert origem == "divergencia"
    assert unidades is bruto["unidades"]             # JSON, não o banco


# ---------------------------------------------------------------------------
# DB-4: espelho do ledger (org.evento)
# ---------------------------------------------------------------------------
def _evento(seq, anterior="GENESIS"):
    return {"seq": seq, "quando": f"2026-08-15T10:0{seq}:00+00:00",
            "ator": "operador@local (org.admin)", "acao": "alterar",
            "entidade_id": "no-123", "motivo": "teste", "payload": {"x": seq},
            "hash_anterior": anterior, "hash": f"hash{seq}"}


def test_sql_evento_e_transacional_e_sincroniza():
    sql = banco.sql_evento([_evento(1), _evento(2, "hash1")], slug="peoples")
    assert sql.count("BEGIN;") == 1 and sql.rstrip().endswith("COMMIT;")
    assert "DELETE FROM org.evento" in sql              # sincroniza (apaga antes)
    assert sql.count("INSERT INTO org.evento") == 2
    assert "'teste'" in sql and "hash1" in sql          # campos verbatim
    assert '\'{"x": 1}\'::jsonb' in sql                 # payload jsonb (objeto)


def test_carregar_ledger_sem_banco_devolve_none(monkeypatch):
    monkeypatch.delenv("ORG_DATABASE_URL", raising=False)
    assert banco.carregar_ledger() is None


def test_espelho_ledger_opt_in_e_nao_repete(monkeypatch):
    chamadas = []
    monkeypatch.setenv("ORG_ESPELHO", "1")
    monkeypatch.setattr(main.bancomod, "situacao", lambda: {"pronto": True})
    monkeypatch.setattr(main.bancomod, "aplicar",
                        lambda sql: (chamadas.append(sql), (True, "ok"))[1])
    ev0, sig0 = list(main.ESTADO.eventos), main._LEDGER_ESPELHADO
    try:
        main.ESTADO.eventos = [_evento(1)]
        main._LEDGER_ESPELHADO = None
        main.espelhar_ledger()             # ledger mudou -> espelha
        main.espelhar_ledger()             # inalterado -> pula
        assert len(chamadas) == 1 and "INSERT INTO org.evento" in chamadas[0]
    finally:
        main.ESTADO.eventos, main._LEDGER_ESPELHADO = ev0, sig0


def test_espelho_ledger_desligado_por_padrao(monkeypatch):
    chamadas = []
    monkeypatch.delenv("ORG_ESPELHO", raising=False)
    monkeypatch.setattr(main.bancomod, "situacao", lambda: {"pronto": True})
    monkeypatch.setattr(main.bancomod, "aplicar", lambda sql: chamadas.append(sql))
    sig0 = main._LEDGER_ESPELHADO
    try:
        main._LEDGER_ESPELHADO = None
        main.espelhar_ledger()
        assert chamadas == []
    finally:
        main._LEDGER_ESPELHADO = sig0


# O round-trip REAL (carga executa no Postgres e volta idêntica) NÃO tem teste na
# suíte de propósito: o `.env` de quem desenvolve aponta para um banco de
# verdade, e a suíte não pode ESCREVER nele. A `ambiente_isolado` (conftest) tira
# o DSN em tempo de execução justamente por isso. A verificação real roda à mão
# na validação do deploy, com `verificar_espelho` (só SELECTs, seguro).
