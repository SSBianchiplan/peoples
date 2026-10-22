"""Portão de gramática e relatório PDF da MarIA — RQ-808, RQ-809, RQ-810.

O que estes testes protegem é a diferença entre "o PDF saiu" e "o PDF saiu
legível e rastreável". Um relatório é o artefato que circula fora do sistema:
ninguém relê, ninguém corrige, e o erro que passar vira o registro oficial.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orga import gramatica
from orga import maria as mariamod
from orga import pdf as pdfmod
from orga import relatorio
from orga import main


@pytest.fixture()
def cliente():
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


META = {
    "titulo": "MarIA · Descrever",
    "subtitulo": "GPlanSiS|Peoples · Tudo · 2026-08-11",
    "rodape": "GPlanSiS|Peoples · MarIA · GPlanSiS|Peoples",
    "idioma": "pt-BR",
    "procedencia": [("origem", "teste"), ("correlacao_id", "abc123")],
}
LIBERADO = {"libera": True, "achados": [], "locale": "pt-BR",
            "dicionario": "acordo ortográfico de 1990",
            "gramatica": "ok", "completa": True}


# ---------------------------------------------------------------------------
# Portão
# ---------------------------------------------------------------------------
def test_texto_limpo_libera():
    assert gramatica.validar("A vertical ENG concentra 58 pessoas.")["libera"]


def test_achado_mecanico_bloqueia():
    """Bloqueio, não aviso. Relatório que sai com erro e um aviso ao lado é
    relatório que sai com erro."""
    r = gramatica.validar("Isso está está errado .")
    assert not r["libera"]
    regras = {a["regra"] for a in r["achados"]}
    assert "palavra_repetida" in regras
    assert "espaco_antes_de_pontuacao" in regras


def test_enfase_aberta_bloqueia():
    """`**` sem par vira asterisco solto no PDF."""
    assert not gramatica.validar("Total de **58 pessoas na vertical")["libera"]


def test_mojibake_bloqueia():
    assert not gramatica.validar("A engenharia tem 58 pessoas Ã© o maior")["libera"]


def test_sem_languagetool_nao_afirma_validacao_completa(monkeypatch):
    """Afirmar validação que não houve é pior do que não validar."""
    monkeypatch.delenv("LANGUAGETOOL_URL", raising=False)
    r = gramatica.validar("Texto correto.")
    assert r["libera"] and not r["completa"]
    assert r["gramatica"] == "nao_configurado"


def test_falha_de_rede_nao_vira_aprovacao(monkeypatch):
    monkeypatch.setenv("LANGUAGETOOL_URL", "http://127.0.0.1:9/nao-existe")
    r = gramatica.validar("Texto correto.")
    assert not r["completa"]
    assert r["gramatica"].startswith("falhou")


def test_locale_leva_o_dicionario_declarado():
    assert gramatica.validar("Ok.", "es")["dicionario"] == "RAE"
    assert "1990" in gramatica.validar("Ok.", "pt-BR")["dicionario"]


def test_limpar_nao_reescreve_conteudo():
    """Corrigir gramática automaticamente seria reescrever o que a MarIA
    disse — e aí o PDF deixa de ser o que ela respondeu."""
    original = "A vertical ENG  concentra 58 pessoas ."
    limpo = gramatica.limpar(original)
    assert limpo == "A vertical ENG concentra 58 pessoas."
    assert gramatica.validar(limpo)["libera"]
    # nenhuma palavra sumiu nem apareceu
    assert re.findall(r"\w+", original) == re.findall(r"\w+", limpo)


# ---------------------------------------------------------------------------
# Emissão
# ---------------------------------------------------------------------------
def test_pdf_valido_e_multipagina():
    texto = "\n\n".join(f"## Seção {i}\n\nParágrafo com **negrito** e `código`."
                        for i in range(1, 30))
    dados = relatorio.gerar({"resposta": texto}, META, LIBERADO)
    assert dados.startswith(b"%PDF-1.7") and dados.rstrip().endswith(b"%%EOF")
    assert dados.count(b"/Type /Page /Parent") > 1


def test_pdf_e_deterministico():
    """Mesmo texto, mesmos bytes: dois relatórios do mesmo registro têm que
    ser o mesmo arquivo, senão comparar versões é impossível."""
    a = {"resposta": "Parágrafo único.", "quando": "2026-08-11T10:00:00"}
    meta = dict(META, procedencia=[("origem", "teste"), ("ts_emissao", "fixo")])
    assert relatorio.gerar(a, meta, LIBERADO) == relatorio.gerar(a, meta, LIBERADO)


def test_nada_ultrapassa_a_margem():
    """Texto que vaza a margem é texto cortado na impressão."""
    texto = ("Palavralonguíssimaqueprecisaquebrar " * 12 + "\n\n"
             "| Vertical | Pessoas |\n|---|---|\n| Engenharia | 58 |\n")
    dados = relatorio.gerar({"resposta": texto}, META, LIBERADO)
    limite = relatorio.A4[0] - relatorio.MARGEM
    for x, corpo, conteudo in _textos(dados):
        assert x + pdfmod.largura(conteudo, corpo) <= limite + 0.5, conteudo


def test_rodape_declara_o_que_foi_validado():
    parcial = dict(LIBERADO, completa=False, gramatica="nao_configurado")
    assert b"checagem mec" in _bruto(relatorio.gerar({"resposta": "Ok."},
                                                    META, parcial))
    assert b"gram" in _bruto(relatorio.gerar({"resposta": "Ok."}, META, LIBERADO))


def test_rodape_no_idioma_do_relatorio():
    """Quem lê um PDF em inglês não decifra o selo em português."""
    ingles = dict(META, idioma="en-US")
    bruto = _bruto(relatorio.gerar({"resposta": "Ok."}, ingles,
                                   dict(LIBERADO, locale="en-US")))
    assert b"grammar" in bruto and b"gram\xe1tica" not in bruto


def test_procedencia_traz_o_recorte():
    """RQ-809: sem o recorte não dá para auditar se a resposta era compatível
    com o que a pessoa podia ver."""
    campos = dict(relatorio.procedencia(
        {"escopo": "Engenharia", "modelo": "claude-opus-4-8",
         "quando": "2026-08-11T10:00:00", "entrada": 8952, "saida": 300},
        "GET /maria/assistencia/x/pdf", "corr123"))
    assert campos["recorte"] == "Engenharia"
    assert campos["correlacao_id"] == "corr123"
    assert campos["tokens"] == "8952/300"
    assert campos["ts_extracao"] != campos["ts_emissao"]


# ---------------------------------------------------------------------------
# Formatação na tela
# ---------------------------------------------------------------------------
def test_formatar_neutraliza_injecao():
    """O texto vem de um modelo. Nada que ele escreva pode virar tag."""
    saida = mariamod.formatar("<script>alert(1)</script> e <img src=x onerror=y>")
    # O que importa não é a ausência da palavra — é que nada dela virou tag.
    assert "<script>" not in saida and "<img" not in saida
    assert "&lt;script&gt;" in saida and "&lt;img src=x onerror=y&gt;" in saida
    # As únicas tags do resultado são as que formatar() emitiu.
    import re as _re
    assert set(_re.findall(r"</?([a-z0-9]+)", saida)) <= {"p", "b", "code"}


def test_formatar_estrutura_markdown():
    # Os títulos do modelo começam em h3: h1 e h2 já pertencem à página.
    saida = mariamod.formatar("# Um\n\n## Dois\n\n- a\n- b\n\nTexto **forte**.")
    assert "<h3>Um</h3>" in saida and "<h4>Dois</h4>" in saida
    assert saida.count("<li>") == 2 and "<b>forte</b>" in saida


def test_largura_helvetica_bate_com_a_afm():
    """A tabela errada (Times) tirava ~2,7pt por palavra — exatamente um
    espaço — e as palavras colavam no PDF."""
    assert round(pdfmod.largura("quebra", 10), 2) == 31.13


# ---------------------------------------------------------------------------
def _bruto(dados: bytes) -> bytes:
    import zlib
    saida = b""
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", dados, re.S):
        try:
            saida += zlib.decompress(m.group(1))
        except zlib.error:
            saida += m.group(1)
    return saida


def _textos(dados: bytes):
    """(x, corpo, texto) de cada Tj do documento."""
    padrao = re.compile(
        rb"/F\d+ ([\d.]+) Tf.*?1 0 0 1 ([\d.]+) [\d.]+ Tm.*?\((.*?)\) Tj", re.S)
    for m in padrao.finditer(_bruto(dados)):
        conteudo = (m.group(3).replace(rb"\(", b"(").replace(rb"\)", b")")
                    .replace(rb"\\", b"\\"))
        yield float(m.group(2)), float(m.group(1)), conteudo.decode("latin-1")


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
def _com_assistencia(resposta: str) -> str:
    """Grava uma assistência e devolve o id."""
    registro = mariamod.assistencia(
        "Quantas pessoas há na engenharia?",
        {"ok": True, "texto": resposta, "modelo": "claude-opus-4-8",
         "entrada": 100, "saida": 40, "custo_usd": 0.001},
        {"nome": "Ana Exemplo", "id": "ORG-0001"},
        mariamod.DESCREVER, "pt-BR", "Tudo")
    main.ESTADO.assistencias.append(registro)
    return registro["id"]


def test_rota_detalhe_mostra_a_resposta_formatada(cliente):
    aid = _com_assistencia("## Resumo\n\nA vertical **ENG** tem 58 pessoas.")
    r = cliente.get(f"/maria/assistencia/{aid}")
    assert r.status_code == 200
    assert "<b>ENG</b>" in r.text and "<h4>Resumo</h4>" in r.text


def test_rota_detalhe_inexistente_nao_explode(cliente):
    assert cliente.get("/maria/assistencia/naoexiste").status_code == 404


def test_rota_pdf_emite(cliente):
    aid = _com_assistencia("A vertical ENG concentra 58 pessoas.")
    r = cliente.get(f"/maria/assistencia/{aid}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-1.7")
    assert aid in r.headers["content-disposition"]


def test_rota_pdf_recusa_texto_com_achado(cliente):
    """RQ-810: o portão bloqueia a emissão e explica — não entrega um PDF
    quebrado nem finge que está tudo bem."""
    aid = _com_assistencia("A vertical ENG tem **58 pessoas na engenharia")
    r = cliente.get(f"/maria/assistencia/{aid}/pdf")
    assert r.status_code == 422
    assert "pdf" not in r.headers["content-type"].lower()
    assert "58 pessoas" in r.text          # a resposta continua legível


def test_pdf_bloqueado_fica_no_ledger(cliente):
    antes = len(main.ESTADO.eventos)
    aid = _com_assistencia("erro erro no texto")
    cliente.get(f"/maria/assistencia/{aid}/pdf")
    assert len(main.ESTADO.eventos) > antes
    assert "bloquead" in main.ESTADO.eventos[-1]["motivo"]
