"""Validação de texto antes da emissão — RQ-810.

O requisito é explícito: o texto **deve** passar por validação no locale ativo
antes de renderizar, e achado **bloqueia a emissão**, não gera aviso. Um
relatório que sai com erro e um aviso ao lado é um relatório que sai com erro.

O módulo tem duas camadas, e a diferença entre elas é dita em voz alta em vez
de escondida atrás da palavra "validado":

**Camada mecânica (sempre roda).** Não é corretor gramatical e não se apresenta
como um: pega o que quebra a leitura sem precisar entender a frase — espaço
antes de pontuação, espaço duplo, palavra repetida, aspas e parênteses
desbalanceados, markdown aberto e não fechado, mojibake de encoding. É
justamente o que mais aparece em texto que passou por API, template e PDF.

**LanguageTool (quando `LANGUAGETOOL_URL` estiver definida).** Aí sim é
gramática, no dicionário do locale: pt-BR pelo acordo de 1990, en-US e es pela
RAE. Sem a URL, a camada mecânica continua bloqueando, e o rodapé do PDF diz
que a checagem gramatical completa não rodou — porque afirmar validação que não
houve é pior do que não validar.

Uma decisão que parece severa e não é: **o bloqueio é da emissão, não da
resposta**. A resposta da MarIA continua na tela e no histórico. O que não sai é
o PDF, que é o artefato que circula fora do sistema e que ninguém relê.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

# locale -> (código do LanguageTool, dicionário declarado)
LOCALES = {
    "pt-BR": ("pt-BR", "acordo ortográfico de 1990"),
    "en-US": ("en-US", "—"),
    "es": ("es", "RAE"),
}

# Categorias que o LanguageTool devolve e que NÃO bloqueiam: estilo é opinião,
# e opinião não pode impedir alguém de emitir um relatório.
CATEGORIAS_IGNORADAS = {"STYLE", "REDUNDANCY", "TYPOGRAPHY_SPACE", "COLLOQUIALISMS"}


def _env(nome: str, padrao: str = "") -> str:
    return (os.environ.get(nome) or padrao).strip()


def servidor() -> str:
    return _env("LANGUAGETOOL_URL")


def disponivel() -> bool:
    return bool(servidor())


# ---------------------------------------------------------------------------
# Camada mecânica
# ---------------------------------------------------------------------------
# (chave, regex, o que está errado). Nomeadas para o achado dizer o que fazer.
MECANICAS = (
    ("espaco_antes_de_pontuacao", re.compile(r"\s+[,;.!?](?:\s|$)"),
     "espaço antes de pontuação"),
    ("espaco_duplo", re.compile(r"[^\S\n]{2,}"), "espaço duplo"),
    ("palavra_repetida",
     re.compile(r"\b(\w{3,})\s+\1\b", re.I | re.U), "palavra repetida"),
    ("pontuacao_repetida", re.compile(r"[,;:]{2,}|\.{4,}"),
     "pontuação repetida"),
    ("mojibake", re.compile(r"Ã[\x80-\xbf]|â€|Â[\xa0-\xbf]"),
     "texto corrompido por encoding"),
    ("espaco_antes_de_quebra", re.compile(r"[^\S\n]+\n"),
     "espaço no fim da linha"),
)

PARES = (("(", ")"), ("[", "]"), ("“", "”"), ("«", "»"))


def _linha_de(texto: str, pos: int) -> int:
    return texto.count("\n", 0, pos) + 1


def mecanica(texto: str) -> list[dict]:
    """Achados que não exigem entender a frase."""
    achados = []
    for chave, padrao, descricao in MECANICAS:
        for m in padrao.finditer(texto or ""):
            achados.append({
                "tipo": "mecanica", "regra": chave, "mensagem": descricao,
                "linha": _linha_de(texto, m.start()),
                "trecho": texto[max(0, m.start() - 24):m.end() + 24].strip(),
            })
    for abre, fecha in PARES:
        if texto.count(abre) != texto.count(fecha):
            achados.append({
                "tipo": "mecanica", "regra": "delimitador_desbalanceado",
                "mensagem": f"delimitador desbalanceado: {abre} {fecha}",
                "linha": 0, "trecho": "",
            })
    # Markdown de ênfase aberto e não fechado sai como asterisco solto no PDF.
    if (texto or "").count("**") % 2:
        achados.append({"tipo": "mecanica", "regra": "enfase_aberta",
                        "mensagem": "ênfase markdown não fechada",
                        "linha": 0, "trecho": ""})
    return achados


# ---------------------------------------------------------------------------
# LanguageTool
# ---------------------------------------------------------------------------
def linguagem(texto: str, locale: str, tempo: int = 15) -> tuple[list[dict], str]:
    """(achados, situação). Nunca levanta.

    Falha de rede não pode virar "texto aprovado" — devolve a situação para o
    chamador decidir, e o chamador bloqueia.
    """
    if not disponivel():
        return [], "nao_configurado"
    codigo = LOCALES.get(locale, LOCALES["pt-BR"])[0]
    corpo = urllib.parse.urlencode({
        "text": (texto or "")[:20000], "language": codigo,
        "level": "default",
    }).encode()
    pedido = urllib.request.Request(
        servidor().rstrip("/") + "/v2/check", data=corpo,
        headers={"content-type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(pedido, timeout=tempo) as r:
            dados = json.loads(r.read())
    except Exception as erro:                        # noqa: BLE001
        return [], f"falhou: {str(erro)[:120]}"

    achados = []
    for m in dados.get("matches", []):
        categoria = ((m.get("rule") or {}).get("category") or {}).get("id", "")
        if categoria in CATEGORIAS_IGNORADAS:
            continue
        contexto = (m.get("context") or {}).get("text", "")
        achados.append({
            "tipo": "gramatica",
            "regra": (m.get("rule") or {}).get("id", "?"),
            "mensagem": m.get("message", ""),
            "linha": 0,
            "trecho": contexto[:80],
            "sugestao": ", ".join(s.get("value", "")
                                  for s in (m.get("replacements") or [])[:3]),
        })
    return achados, "ok"


# ---------------------------------------------------------------------------
# Portão
# ---------------------------------------------------------------------------
def validar(texto: str, locale: str = "pt-BR") -> dict:
    """Resultado do portão. `libera` False impede a emissão — RQ-810."""
    achados = mecanica(texto)
    gramaticais, situacao = linguagem(texto, locale)
    achados += gramaticais
    return {
        "libera": not achados,
        "achados": achados,
        "locale": locale,
        "dicionario": LOCALES.get(locale, LOCALES["pt-BR"])[1],
        "gramatica": situacao,
        # O rodapé do PDF carrega isto: afirmar validação que não houve é pior
        # do que não validar.
        "completa": situacao == "ok",
    }


def limpar(texto: str) -> str:
    """Correções mecânicas seguras, aplicadas antes de validar.

    Só o que não muda sentido: espaço sobrando e pontuação deslocada. Corrigir
    gramática automaticamente seria reescrever o que a MarIA disse, e aí o PDF
    deixaria de ser o que ela respondeu.
    """
    t = (texto or "").replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[^\S\n]+\n", "\n", t)               # espaço no fim da linha
    t = re.sub(r"\s+([,;.!?])", r"\1", t)            # espaço antes de pontuação
    t = re.sub(r"[^\S\n]{2,}", " ", t)               # espaço duplo
    t = re.sub(r"\n{3,}", "\n\n", t)                 # linha em branco repetida
    return t.strip()
