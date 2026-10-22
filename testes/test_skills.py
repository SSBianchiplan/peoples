"""
Skills por colaborador: a matriz de competências, o .md individual e o pacote.

    pytest testes/test_skills.py -q
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import dcr                                                      # noqa: E402
from orga import main                                                     # noqa: E402

sys.path.insert(0, str(RAIZ_PROJETO / "ferramentas"))
import gerar_skills                                                       # noqa: E402


@pytest.fixture()
def cli():
    with TestClient(main.app) as c:
        yield c


def _pessoa():
    return next(u for u in main.ESTADO.unidades.values() if u.parent_id and u.cargo)


# ---------------------------------------------------------------------------
# A matriz
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cargo,tipo,familia,sen", [
    ("Analista de Automação Pleno", "celula", "automacao", "pleno"),
    ("Técnico em Automação", "celula", "automacao", "junior"),
    ("Especialista em Engenharia Elétrica", "especialista", "eletrica", "especialista"),
    ("Gerente de Planejamento Financeiro e Tesouraria", "gerencia", "financeiro", "gerencia"),
    ("Coordenador de Adm. Pessoal", "coordenacao", "rh", "coordenacao"),
    ("Montador Líder", "coordenacao", "producao", "lideranca"),
    ("Diretor Executivo / CEO", "diretoria", "exec", "diretoria"),
    ("Estagiário", "apoio", "administrativo", "aprendiz"),
    ("Tech Lead", "coordenacao", "digital", "lideranca"),
    ("SDR", "celula", "comercial", "junior"),
    ("Coordenador de Manutenção Elétrica", "coordenacao", "manutencao", "coordenacao"),
    ("Analista de Planejamento Financeiro Sênior", "celula", "financeiro", "senior"),
])
def test_classificacao_por_familia_senioridade(cargo, tipo, familia, sen):
    f = gerar_skills.ficha_de(cargo, tipo)
    assert (f["_familia"], f["_senioridade"]) == (familia, sen)


def test_ficha_gerada_e_completa_e_cabe_no_formulario():
    f = gerar_skills.ficha_de("Analista de Automação Pleno", "celula")
    for campo in dcr.CAMPOS_OVERLAY:
        assert f[campo].strip(), campo
        assert len(f[campo]) <= dcr.LIMITE_OVERLAY
    comps = dcr.itens(f["competencias"])
    assert any(c.startswith("[Técnica]") and "3/5" in c for c in comps)      # pleno = nível 3
    assert any(c.startswith("[Trilha]") for c in comps)
    assert any(r.startswith("[Formação]") for r in dcr.itens(f["requisitos"]))


def test_senioridade_sobe_o_nivel_esperado():
    jr = gerar_skills.ficha_de("Analista de Automação", "celula")["competencias"]
    sr = gerar_skills.ficha_de("Analista de Automação Sênior", "celula")["competencias"]
    assert "2/5" in jr and "4/5" in sr


@pytest.mark.parametrize("arquivo", ["estado.json", "estado-teste-5-niveis.json"])
def test_toda_funcao_da_base_recebe_ficha(arquivo):
    """Nenhum cargo da base de demonstração pode ficar sem Skills — é o que o RH
    precisa para abrir vaga, promover e comparar. Lê o ARQUIVO versionado, e não
    o ESTADO em memória: outros testes criam cargos de prova no processo."""
    import json
    caminho = RAIZ_PROJETO / "dados" / arquivo
    if not caminho.exists():
        pytest.skip(f"dados/{arquivo} ausente (base não versionada)")
    d = json.loads(caminho.read_text(encoding="utf-8"))
    if not d.get("config", {}).get("dcr_cargos"):
        pytest.skip(f"dados/{arquivo} sem fichas geradas (rode ferramentas/gerar_skills.py)")
    fichas = {dcr.chave_funcao(o["cargo"]) for o in d["config"]["dcr_cargos"]}
    cargos = {dcr.chave_funcao(u["cargo"]) for u in d["unidades"].values()
              if u["parent_id"] and u["cargo"]}
    assert cargos and cargos <= fichas, sorted(cargos - fichas)[:5]


# ---------------------------------------------------------------------------
# O .md por colaborador
# ---------------------------------------------------------------------------
def test_md_do_colaborador(cli):
    u = _pessoa()
    r = cli.get(f"/unidades/{u.id}/skills.md")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert "attachment" in r.headers.get("content-disposition", "")
    assert u.nome in r.text and u.cargo in r.text
    assert "# Skills" in r.text and "## Missão do Cargo" in r.text
    assert "Aderência" in r.text                       # a comparação declarado × desejável


def test_md_de_unidade_inexistente_e_404(cli):
    assert cli.get("/unidades/nao-existe/skills.md").status_code == 404


def test_md_da_raiz_sintetica_nao_explode(cli):
    from orga.dominio import raiz
    r = cli.get(f"/unidades/{raiz(main.ESTADO.unidades).id}/skills.md")
    assert r.status_code == 200


def test_pacote_zip_com_todos(cli):
    r = cli.get("/skills/todos.zip")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    nomes = z.namelist()
    pessoas = sum(1 for u in main.ESTADO.unidades.values() if u.parent_id)
    assert len([n for n in nomes if n.endswith(".md") and n != "INDICE.md"]) == pessoas
    assert "INDICE.md" in nomes


# ---------------------------------------------------------------------------
# Onde aparece na tela
# ---------------------------------------------------------------------------
def test_ficha_do_colaborador_mostra_skills_do_cargo(cli):
    u = _pessoa()
    html = cli.get(f"/unidades/{u.id}/ficha").text
    assert "Skills do cargo" in html
    assert f"/unidades/{u.id}/skills.md" in html


def test_gaveta_tem_o_botao_do_md(cli):
    u = _pessoa()
    html = cli.get(f"/fragmentos/painel/{u.id}").text
    assert f"/unidades/{u.id}/skills.md" in html
