"""
Multi-organograma: o registro, os caminhos de estado e o ciclo de vida (criar,
trocar, excluir) do organograma ativo.

O sistema nasceu com UM organograma. Estes testes guardam que passar a ter
vários não quebra o que existia (o `peoples` segue no `estado.json` de sempre),
que os estados não se misturam ao trocar, e que o slug gerado é sempre válido
para o banco (o CHECK de `org.organograma.slug`).

    pytest testes/test_organogramas.py -q
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import organogramas as orgs                                     # noqa: E402
from orga import main                                                     # noqa: E402
from orga.dominio import Unidade                                          # noqa: E402

# O mesmo CHECK do schema: 3–50 chars, começa e termina em alfanumérico.
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")


# ---------------------------------------------------------------------------
# Registro e slug — puros
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nome", [
    "GPlanSiS|Peoples Brasil", "Água & Café Ltda.", "X", "  ", "Açaí S.A.",
    "----", "Filial 2027!!!", "café"])
def test_slug_sempre_valido_para_o_banco(nome):
    assert SLUG_RE.match(orgs.slugificar(nome)), nome


def test_slug_e_unico_entre_os_existentes():
    ex = {"peoples", "acme", "acme-2"}
    for nome in ["GPlanSiS|Peoples", "Acme", "Acme"]:
        s = orgs.slugificar(nome, ex)
        assert s not in ex and SLUG_RE.match(s)
        ex.add(s)


def test_caminho_legado_para_o_padrao_e_novo_para_os_demais(tmp_path, monkeypatch):
    monkeypatch.setattr(orgs, "_DADOS", tmp_path)
    assert orgs.caminho_estado(orgs.SLUG_PADRAO).name == "estado.json"
    assert orgs.caminho_estado("acme").name == "estado-acme.json"


def test_ler_sem_arquivo_devolve_o_padrao_sem_escrever(tmp_path, monkeypatch):
    monkeypatch.setattr(orgs, "_DADOS", tmp_path)
    monkeypatch.setattr(orgs, "REGISTRO", tmp_path / "organogramas.json")
    reg = orgs.ler()
    assert reg["ativo"] == orgs.SLUG_PADRAO
    assert [o["slug"] for o in reg["lista"]] == [orgs.SLUG_PADRAO]
    assert not (tmp_path / "organogramas.json").exists()   # não materializa à toa


def test_adicionar_renomear_definir_ativo_remover(tmp_path, monkeypatch):
    monkeypatch.setattr(orgs, "_DADOS", tmp_path)
    monkeypatch.setattr(orgs, "REGISTRO", tmp_path / "organogramas.json")
    reg = orgs.ler()
    reg, slug = orgs.adicionar(reg, "Acme Corp")
    assert slug != orgs.SLUG_PADRAO and orgs.existe(reg, slug)
    reg = orgs.renomear(reg, slug, "Acme S.A.")
    assert orgs.nome_de(reg, slug) == "Acme S.A."
    reg = orgs.definir_ativo(reg, slug)
    assert orgs.ativo(reg) == slug
    reg = orgs.remover(reg, slug)
    assert not orgs.existe(reg, slug)
    assert orgs.ativo(reg) == orgs.SLUG_PADRAO      # ativo apagado -> reelege


def test_remover_nunca_esvazia_a_lista(tmp_path, monkeypatch):
    monkeypatch.setattr(orgs, "_DADOS", tmp_path)
    monkeypatch.setattr(orgs, "REGISTRO", tmp_path / "organogramas.json")
    reg = orgs.remover(orgs.ler(), orgs.SLUG_PADRAO)
    assert orgs.listar(reg) and orgs.existe(reg, orgs.SLUG_PADRAO)


# ---------------------------------------------------------------------------
# Ciclo de vida no `main` — mexe no ESTADO global; isolado e restaurado
# ---------------------------------------------------------------------------
@pytest.fixture()
def multi_org(tmp_path, monkeypatch):
    monkeypatch.setattr(orgs, "_DADOS", tmp_path)
    monkeypatch.setattr(orgs, "REGISTRO", tmp_path / "organogramas.json")
    snap = main.serializar()
    slug0, arq0 = main.SLUG_ATIVO, main.ARQUIVO_ESTADO
    main.SLUG_ATIVO = orgs.SLUG_PADRAO
    main.ARQUIVO_ESTADO = orgs.caminho_estado(orgs.SLUG_PADRAO)   # tmp/estado.json
    main.ARQUIVO_ESTADO.write_text(snap, encoding="utf-8")        # semente = estado atual
    yield main
    main.SLUG_ATIVO, main.ARQUIVO_ESTADO = slug0, arq0
    main.adotar(json.loads(snap))


def _raizes(m):
    return [u for u in m.ESTADO.unidades.values() if u.parent_id is None]


def test_criar_troca_e_nasce_com_uma_raiz(multi_org):
    m = multi_org
    antes = len(orgs.listar())
    slug = m.criar_organograma("Filial Sul")
    assert m.SLUG_ATIVO == slug                     # já mostra o novo
    assert len(orgs.listar()) == antes + 1
    assert orgs.caminho_estado(slug).exists()
    assert len(m.ESTADO.unidades) == 1 and len(_raizes(m)) == 1
    assert m.ESTADO.config.titulo == "Filial Sul"


def test_trocar_nao_mistura_os_organogramas(multi_org):
    m = multi_org
    a = m.criar_organograma("Alpha")               # ativo=a, só raiz
    raiz = _raizes(m)[0]
    novo = m.novo_id()
    m.ESTADO.unidades[novo] = Unidade(
        id=novo, codigo="ORG-0002", nome="Pessoa A", tipo="celula",
        parent_id=raiz.id, ordem=0)
    m.gravar()                                      # Alpha agora tem 2 nós
    b = m.criar_organograma("Beta")                # Beta nasce vazio (só raiz)
    assert len(m.ESTADO.unidades) == 1
    assert m.trocar_organograma(a) is True
    assert len(m.ESTADO.unidades) == 2             # Alpha preservado
    assert m.trocar_organograma(b) is True
    assert len(m.ESTADO.unidades) == 1             # Beta preservado


def test_excluir_o_ativo_troca_para_outro(multi_org):
    m = multi_org
    a = m.criar_organograma("Alpha")
    assert m.SLUG_ATIVO == a
    assert m.excluir_organograma(a) is True
    assert m.SLUG_ATIVO != a
    assert not orgs.existe(orgs.ler(), a)
    assert not orgs.caminho_estado(a).exists()
    assert m.ESTADO.unidades                        # o ativo novo carregou


def test_nao_exclui_o_ultimo(multi_org):
    m = multi_org
    assert m.excluir_organograma(orgs.SLUG_PADRAO) is False


# ---------------------------------------------------------------------------
# Rotas + seletor no cabeçalho (HTTP de verdade)
# ---------------------------------------------------------------------------
def _cli():
    from fastapi.testclient import TestClient
    return TestClient(main.app)


def test_rota_criar_troca_e_aparece_no_cabecalho(multi_org):
    with _cli() as c:
        r = c.post("/organogramas/criar", data={"nome": "Filial Norte"})
        assert r.status_code == 204 and r.headers.get("HX-Redirect") == "/"
        assert any(o["nome"] == "Filial Norte" for o in orgs.listar())
        home = c.get("/")
        assert home.status_code == 200
        assert "org-topo" in home.text            # o seletor está no cabeçalho
        assert "Filial Norte" in home.text        # e mostra o ativo recém-criado


def test_rota_criar_sem_nome_reclama(multi_org):
    with _cli() as c:
        r = c.post("/organogramas/criar", data={"nome": "   "})
        assert r.status_code == 200                # re-renderiza a aba com aviso
        assert "HX-Redirect" not in r.headers


def test_rota_trocar_e_excluir(multi_org):
    m = multi_org
    a = m.criar_organograma("Alpha")              # ativo = Alpha
    with _cli() as c:
        r = c.post("/organogramas/trocar", data={"slug": orgs.SLUG_PADRAO})
        assert r.status_code == 204 and r.headers["HX-Redirect"] == "/"
        assert m.SLUG_ATIVO == orgs.SLUG_PADRAO
        r = c.post("/organogramas/excluir", data={"slug": a})   # Alpha não-ativo
        assert r.status_code == 204
        assert not orgs.existe(orgs.ler(), a)


def test_aba_organogramas_responde(multi_org):
    with _cli() as c:
        r = c.get("/vistas/configuracoes?aba=organogramas")
        assert r.status_code == 200 and "Organogramas" in r.text


def test_criar_colaborador_num_organograma_novo(multi_org):
    """No organograma vazio (só raiz), o botão cria a pessoa sob a raiz e abre a
    ficha — sem precisar clicar num card antes."""
    m = multi_org
    m.criar_organograma("Zero")
    assert len(m.ESTADO.unidades) == 1                 # nasce só com a raiz
    with _cli() as c:
        r = c.post("/colaborador/novo")
        assert r.status_code == 200
    assert len(m.ESTADO.unidades) == 2                 # criou sob a raiz
    novos = [u for u in m.ESTADO.unidades.values() if u.parent_id]
    assert len(novos) == 1 and novos[0].nome           # com nome preenchido


def test_trocar_limpa_a_selecao(multi_org):
    """Trocar de organograma não pode deixar selecionado um id do anterior."""
    m = multi_org
    a = m.criar_organograma("Alpha")
    m.ESTADO.selecionado = next(iter(m.ESTADO.unidades))
    m.trocar_organograma(orgs.SLUG_PADRAO)
    assert m.ESTADO.selecionado is None
