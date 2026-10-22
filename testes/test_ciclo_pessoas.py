"""
O ciclo de gente 2026 gerado a partir dos Skills — a regra é a hierarquia.

    pytest testes/test_ciclo_pessoas.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import gptw                                                     # noqa: E402


def _estado(arquivo: str) -> dict:
    # A base de dados não é versionada (LGPD): sem o arquivo gerado localmente
    # (ferramentas/organograma_teste.py + gerar_ciclo_pessoas.py), o teste é pulado.
    caminho = RAIZ_PROJETO / "dados" / arquivo
    if not caminho.exists():
        pytest.skip(f"dados/{arquivo} ausente (base não versionada)")
    d = json.loads(caminho.read_text(encoding="utf-8"))
    if not d.get("config", {}).get("cgv_registros"):
        pytest.skip(f"dados/{arquivo} sem o ciclo gerado (rode ferramentas/gerar_ciclo_pessoas.py)")
    return d


def _pessoas(d: dict) -> list[dict]:
    return [u for u in d["unidades"].values() if u["parent_id"] and u["cargo"]]


def _ref(u: dict) -> str:
    return (u.get("codigo") or "").strip() or f"u:{u['id']}"


@pytest.mark.parametrize("arquivo", ["estado.json", "estado-teste-5-niveis.json"])
def test_cinco_accountabilities_proprias_por_pessoa(arquivo):
    d = _estado(arquivo)
    for u in _pessoas(d):
        proprias = [r for r in u["responsabilidades"] if r.get("origem") != "delegada"]
        assert len(proprias) == 5, u["cargo"]
        assert all(r["descricao"].strip() for r in proprias)


@pytest.mark.parametrize("arquivo", ["estado.json", "estado-teste-5-niveis.json"])
def test_conversa_de_valor_de_todo_liderado_com_o_lider_direto(arquivo):
    """Cada pessoa tem a Completa realizada e os dois check-ins; o líder da
    conversa é o pai na árvore — essa é a regra."""
    d = _estado(arquivo)
    regs = {(r["ref"], r["ciclo"]): r for r in d["config"]["cgv_registros"] if r["ano"] == 2026}
    for u in _pessoas(d):
        ref = _ref(u)
        pai = d["unidades"][u["parent_id"]]
        completa = regs[(ref, "completa")]
        assert completa["status"] == "realizada" and completa["lider"] == pai["nome"]
        c = completa["conteudo"]
        assert c["entregas"] and c["carreira"]
        assert all(c["valores"][v] for v in ("teamwork", "respect", "innovation", "ownership"))
        assert sum(1 for i in c["pdi"] if i["comp"]) == 3
        assert regs[(ref, "checkin1")]["status"] == "realizada"
        assert regs[(ref, "checkin2")]["status"] == "agendada"


def test_feedback_a_lideranca_so_quando_o_lider_e_pessoa():
    d = _estado("estado.json")
    regs = {(r["ref"], r["ciclo"]): r for r in d["config"]["cgv_registros"]}
    for u in _pessoas(d):
        pai = d["unidades"][u["parent_id"]]
        lid = regs[(_ref(u), "completa")]["conteudo"]["lideranca"]
        if pai["parent_id"]:                 # líder é gente: o liderado avalia (LMA)
            assert all(lid.values())
        else:                                # líder é a raiz sintética: não há quem avaliar
            assert not any(lid.values())


@pytest.mark.parametrize("arquivo", ["estado.json", "estado-teste-5-niveis.json"])
def test_avaliacao_9box_para_todos(arquivo):
    d = _estado(arquivo)
    mapa = {r["ref"]: r for r in d["config"]["mapa_talentos"] if r["ano"] == 2026}
    for u in _pessoas(d):
        r = mapa[_ref(u)]
        assert r["risco_perda"] in ("alto", "medio", "baixo")
        assert r["impacto_perda"] in ("alto", "medio", "baixo")
        assert r["prontidao"] and r["acao"]
        assert r["conteudo"]["trajetoria"] and r["conteudo"]["trilha_posicao"]


@pytest.mark.parametrize("arquivo", ["estado.json", "estado-teste-5-niveis.json"])
def test_avaliacao_mestre_cem_por_cento_anonima(arquivo):
    """Uma resposta anual (60 afirmações) e uma de pulso (15) por pessoa — 100%
    de participação —, sem nenhuma identidade gravada."""
    d = _estado(arquivo)
    pessoas = _pessoas(d)
    resp = d["config"]["gptw_respostas"]
    anual = [r for r in resp if r["ciclo"] == "anual" and r["ano"] == 2026]
    pulso = [r for r in resp if r["ciclo"] == "pulso" and r["ano"] == 2026]
    assert len(anual) == len(pessoas) and len(pulso) == len(pessoas)
    assert all(len(r["respostas"]) == len(gptw.AFIRMACOES) for r in anual)
    assert all(len(r["respostas"]) == len(gptw.IDS_PULSO) for r in pulso)
    assert all(set(r.keys()) <= {"id", "ciclo", "ano", "respostas", "abertas", "nivel", "area",
                                 "vinculo", "faixa", "modelo"} for r in resp)
    assert d["config"]["gptw_programacao"]["status"] == "programada"
    # O PTI sai numa faixa plausível (nem 100% nem colapsado) — a distribuição é
    # real, não um carimbo.
    pti = gptw.gti(anual)["gti"]
    assert 55 <= pti <= 95, pti
