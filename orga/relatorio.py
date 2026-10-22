"""Relatório PDF da MarIA — A4 retrato, vetorial, determinístico.

Atende três requisitos, e cada um muda uma linha do código:

**RQ-808 — gerado no backend, layout determinístico e versionado.** Nada de
impressão de tela do navegador: o mesmo texto produz o mesmo arquivo, byte a
byte, em qualquer máquina. O número da versão do layout vai impresso no rodapé,
porque relatório sem versão não se compara com o de três meses atrás.

**RQ-809 — todo número rastreável.** Cada bloco de dado carrega a origem (a
função ou rota que o produziu), o `correlacao_id` da emissão e o `ts` da
extração. Relatório sem rastro é documentação aspiracional impressa.

**RQ-810 — validação antes da renderização.** `gerar()` chama o portão de
`gramatica.py` e **recusa** quando há achado. O bloqueio é da emissão, não da
resposta: o texto continua na tela e no histórico.

O Markdown que a MarIA devolve vira estrutura antes de virar página. Só o
subconjunto que ela usa de verdade — título, parágrafo, lista, tabela, ênfase e
código — porque interpretar o resto seria inventar formatação que ninguém pediu.
"""
from __future__ import annotations

import re
import uuid
import zlib
from datetime import datetime, timezone

from pathlib import Path

from . import idiomas
from . import pdf as pdfmod


VERSAO_LAYOUT = "1.0.0"
A4 = (595.28, 841.89)                    # 210 x 297 mm em pontos
MARGEM = 48.0
LARGURA_UTIL = A4[0] - 2 * MARGEM

# O logo PRETO da organização entra no cabeçalho de todo relatório (Skills, Conversa de Valor,
# Avaliação, MarIA). Papel não tem tema: a versão preta é a que lê bem
# sobre o branco. Sem Pillow, `_logo_pdf` devolve None e o relatório sai sem
# logo — degrada, não quebra.
LOGO_PRETO = Path(__file__).resolve().parent.parent / "web" / "marca" / "peoples-preto.png"

# (tamanho, entrelinha, espaço antes) por tipo de bloco
ESTILO = {
    "h1": (16.5, 21, 16), "h2": (13.5, 18, 14), "h3": (11.5, 15, 11),
    "p": (9.8, 13.6, 7), "li": (9.8, 13.6, 3), "code": (8.6, 12, 8),
    "td": (8.6, 12, 0), "th": (8.6, 12, 0),
}
CINZA, TINTA, LARANJA = "#7D8286", "#2D3336", "#EB6A20"


# ---------------------------------------------------------------------------
# Markdown -> blocos
# ---------------------------------------------------------------------------
def blocos(texto: str) -> list[dict]:
    """Subconjunto de Markdown que a MarIA usa de fato."""
    saida: list[dict] = []
    linhas = (texto or "").replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(linhas):
        linha = linhas[i].rstrip()
        if not linha.strip():
            i += 1
            continue

        cabecalho = re.match(r"^(#{1,3})\s+(.*)$", linha)
        if cabecalho:
            saida.append({"tipo": f"h{len(cabecalho.group(1))}",
                          "texto": cabecalho.group(2).strip()})
            i += 1
            continue

        if linha.lstrip().startswith("```"):
            corpo = []
            i += 1
            while i < len(linhas) and not linhas[i].lstrip().startswith("```"):
                corpo.append(linhas[i])
                i += 1
            i += 1
            saida.append({"tipo": "code", "texto": "\n".join(corpo)})
            continue

        # Tabela: linha com | seguida de separador |---|
        if "|" in linha and i + 1 < len(linhas) and re.match(
                r"^\s*\|?[\s:|-]+\|[\s:|-]*$", linhas[i + 1]):
            cabeca = [c.strip() for c in linha.strip().strip("|").split("|")]
            i += 2
            corpo = []
            while i < len(linhas) and "|" in linhas[i]:
                corpo.append([c.strip()
                              for c in linhas[i].strip().strip("|").split("|")])
                i += 1
            saida.append({"tipo": "tabela", "cabeca": cabeca, "linhas": corpo})
            continue

        item = re.match(r"^\s*(?:[-*•]|\d+\.)\s+(.*)$", linha)
        if item:
            saida.append({"tipo": "li", "texto": item.group(1).strip()})
            i += 1
            continue

        # Parágrafo: junta até a linha em branco.
        corpo = [linha.strip()]
        i += 1
        while i < len(linhas) and linhas[i].strip() and not re.match(
                r"^\s*(#{1,3}\s|[-*•]\s|\d+\.\s|```)", linhas[i]) \
                and "|" not in linhas[i]:
            corpo.append(linhas[i].strip())
            i += 1
        saida.append({"tipo": "p", "texto": " ".join(corpo)})
    return saida


NEGRITO = re.compile(r"\*\*(.+?)\*\*")
CODIGO = re.compile(r"`([^`]+)`")


def pedacos(texto: str) -> list[tuple[str, str]]:
    """(texto, fonte) — o negrito e o código viram fonte, não marcação."""
    saida, resto = [], texto or ""
    padrao = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`")
    pos = 0
    for m in padrao.finditer(resto):
        if m.start() > pos:
            saida.append((resto[pos:m.start()], pdfmod.F_NORMAL))
        if m.group(1):
            saida.append((m.group(1), pdfmod.F_FORTE))
        else:
            saida.append((m.group(2), pdfmod.F_MONO))
        pos = m.end()
    if pos < len(resto):
        saida.append((resto[pos:], pdfmod.F_NORMAL))
    return saida or [(resto, pdfmod.F_NORMAL)]


def quebrar(pares: list[tuple[str, str]], corpo: float,
            largura_max: float) -> list[list[tuple[str, str]]]:
    """Quebra em linhas medindo a largura real de cada trecho."""
    linhas: list[list[tuple[str, str]]] = [[]]
    largura = 0.0
    for texto, fonte in pares:
        for palavra in re.split(r"(\s+)", texto):
            if not palavra:
                continue
            mono = fonte in (pdfmod.F_MONO, pdfmod.F_MONO_FORTE)
            w = pdfmod.largura(palavra, corpo, mono,
                               fonte in (pdfmod.F_FORTE, pdfmod.F_MONO_FORTE))
            if largura + w > largura_max and linhas[-1] and palavra.strip():
                linhas.append([])
                largura = 0.0
            if not palavra.strip() and not linhas[-1]:
                continue
            linhas[-1].append((palavra, fonte))
            largura += w
    return [l for l in linhas if l]


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------
class Folha:
    """Fluxo de texto com quebra de página. Uma `Tela` por página."""

    def __init__(self, meta: dict, imagem: tuple | None = None):
        self.meta = meta
        self.imagem = imagem            # (dados, w, h) do logo, ou None
        self.paginas: list[pdfmod.Tela] = []
        self.tela = None
        self.y = 0.0
        self.nova()

    def nova(self) -> None:
        self.tela = pdfmod.Tela()
        self.paginas.append(self.tela)
        self.y = A4[1] - MARGEM
        if len(self.paginas) == 1:
            self._capa()

    def _capa(self) -> None:
        # O logo preto no alto, à direita — como papel timbrado. Fica acima da
        # linha do título, então não disputa espaço com ele.
        if self.imagem:
            _dados, w, h = self.imagem
            alt = 20.0
            larg = alt * w / max(1, h)
            self.tela.imagem("Im1", MARGEM + LARGURA_UTIL - larg, self.y - alt,
                             larg, alt)
            self.y -= alt + 8
        self.tela.texto(MARGEM, self.y - 14, self.meta["titulo"],
                        pdfmod.F_FORTE, 19, TINTA)
        self.y -= 30
        self.tela.texto(MARGEM, self.y - 10, self.meta["subtitulo"],
                        pdfmod.F_NORMAL, 9.5, CINZA)
        self.y -= 18
        self.tela.retangulo(MARGEM, self.y, LARGURA_UTIL, 2, preenche=LARANJA)
        self.y -= 16

    def espaco(self, altura: float) -> None:
        if self.y - altura < MARGEM + 42:            # 42 = faixa do rodapé
            self.nova()

    def escrever(self, bloco: dict) -> None:
        tipo = bloco["tipo"]
        if tipo == "tabela":
            return self._tabela(bloco)
        corpo, entrelinha, antes = ESTILO.get(tipo, ESTILO["p"])
        self.y -= antes
        recuo = 12 if tipo == "li" else 0
        fonte_base = pdfmod.F_FORTE if tipo.startswith("h") else pdfmod.F_NORMAL
        cor = TINTA if tipo != "code" else "#4A5053"

        if tipo == "code":
            linhas = [[(l, pdfmod.F_MONO)] for l in bloco["texto"].split("\n")]
        else:
            partes = pedacos(bloco["texto"])
            if fonte_base == pdfmod.F_FORTE:
                partes = [(t, pdfmod.F_FORTE) for t, _ in partes]
            linhas = quebrar(partes, corpo, LARGURA_UTIL - recuo)

        for n, linha in enumerate(linhas):
            self.espaco(entrelinha)
            x = MARGEM + recuo
            if tipo == "li" and n == 0:
                self.tela.texto(MARGEM + 2, self.y - corpo, "•",
                                pdfmod.F_NORMAL, corpo, LARANJA)
            for texto, fonte in linha:
                self.tela.texto(x, self.y - corpo, texto, fonte, corpo, cor)
                x += pdfmod.largura(
                    texto, corpo,
                    fonte in (pdfmod.F_MONO, pdfmod.F_MONO_FORTE),
                    fonte in (pdfmod.F_FORTE, pdfmod.F_MONO_FORTE))
            self.y -= entrelinha

    def _tabela(self, bloco: dict) -> None:
        colunas = max(1, len(bloco["cabeca"]))
        largura_col = LARGURA_UTIL / colunas
        self.y -= 10
        self.espaco(30)
        # Cabeçalho
        self.tela.retangulo(MARGEM, self.y - 14, LARGURA_UTIL, 14,
                            preenche="#F4F5F6")
        for i, titulo in enumerate(bloco["cabeca"]):
            self.tela.texto(MARGEM + 4 + i * largura_col, self.y - 10.5,
                            _cortar(titulo, largura_col - 8, 8.6),
                            pdfmod.F_FORTE, 8.6, TINTA)
        self.y -= 16
        for linha in bloco["linhas"]:
            self.espaco(13)
            for i, celula in enumerate(linha[:colunas]):
                self.tela.texto(MARGEM + 4 + i * largura_col, self.y - 9,
                                _cortar(re.sub(r"\*\*", "", celula),
                                        largura_col - 8, 8.6),
                                pdfmod.F_NORMAL, 8.6, TINTA)
            self.tela.linha(MARGEM, self.y - 12.5, MARGEM + LARGURA_UTIL,
                            self.y - 12.5, "#E7E9EA", 0.5)
            self.y -= 13
        self.y -= 6


def _cortar(texto: str, largura_max: float, corpo: float) -> str:
    if pdfmod.largura(texto, corpo) <= largura_max:
        return texto
    while texto and pdfmod.largura(texto + "…", corpo) > largura_max:
        texto = texto[:-1]
    return texto + "…"


# ---------------------------------------------------------------------------
# Emissão
# ---------------------------------------------------------------------------
def gerar(assistencia: dict, meta: dict, validacao: dict) -> bytes:
    """Bytes do PDF. Só chega aqui depois do portão liberar — RQ-810."""
    imagem = pdfmod._logo_pdf(LOGO_PRETO)        # logo preto no cabeçalho
    folha = Folha(meta, imagem)
    for bloco in blocos(assistencia.get("resposta", "")):
        folha.escrever(bloco)

    # RQ-809: a procedência vai no documento, não num e-mail à parte.
    folha.espaco(90)
    folha.y -= 14
    folha.tela.linha(MARGEM, folha.y, MARGEM + LARGURA_UTIL, folha.y,
                     "#D9DBDC", 0.6)
    folha.y -= 12
    for rotulo, valor in meta["procedencia"]:
        folha.tela.texto(MARGEM, folha.y - 8, f"{rotulo}:", pdfmod.F_MONO_FORTE,
                         7.4, CINZA)
        folha.tela.texto(MARGEM + 96, folha.y - 8, str(valor), pdfmod.F_MONO,
                         7.4, CINZA)
        folha.y -= 11

    fluxo = _paginas(folha, meta, validacao)
    return _montar(fluxo, imagem)


def _paginas(folha: Folha, meta: dict, validacao: dict) -> list[bytes]:
    # O rodapé sai no idioma do relatório: quem lê um PDF em inglês não deve
    # ter que decifrar o selo de validação em português.
    def t(texto, **p):
        return idiomas.traduzir(texto, meta.get("idioma", idiomas.PADRAO), **p)

    saida = []
    total = len(folha.paginas)
    for n, tela in enumerate(folha.paginas, start=1):
        y = MARGEM - 12
        tela.linha(MARGEM, MARGEM - 2, MARGEM + LARGURA_UTIL, MARGEM - 2,
                   "#E7E9EA", 0.5)
        esquerda = meta["rodape"]
        # RQ-810: o rodapé declara o que foi validado. Dizer "validado" quando
        # só a camada mecânica rodou seria afirmar o que não houve.
        # O rodapé sai no idioma do relatório: quem lê um PDF em inglês não
        # deve ter que decifrar o selo de validação em português.
        # Documento que não passou pelo portão de gramática declara o que ele é,
        # e não um selo de validação que ninguém rodou. O Skills é o primeiro caso:
        # o texto vem da estrutura e do RH, não de um modelo de linguagem, e
        # imprimir "checagem mecânica" nele afirmaria uma verificação inexistente.
        selo = meta.get("selo") or (
            t("gramática {locale} · {dicionario}",
              locale=validacao["locale"], dicionario=validacao["dicionario"])
            if validacao.get("completa")
            else t("checagem mecânica · {locale}", locale=validacao["locale"]))
        tela.texto(MARGEM, y, esquerda, pdfmod.F_MONO, 6.8, CINZA)
        tela.texto(MARGEM, y - 9, selo, pdfmod.F_MONO, 6.8, CINZA)
        direita = t("{n}/{total} · layout v{versao}",
                    n=n, total=total, versao=VERSAO_LAYOUT)
        tela.texto(MARGEM + LARGURA_UTIL - pdfmod.largura(direita, 6.8, True), y,
                   direita, pdfmod.F_MONO, 6.8, CINZA)
        saida.append(str(tela).encode("latin-1", "replace"))
    return saida


def _montar(fluxos: list[bytes], imagem: tuple | None = None) -> bytes:
    """Monta o arquivo. Multipágina; a única imagem é o logo do cabeçalho."""
    objetos: list[bytes] = []

    def obj(corpo: bytes) -> int:
        objetos.append(corpo)
        return len(objetos)

    fontes = {}
    for apelido, nome in pdfmod.FONTES.items():
        fontes[apelido] = obj(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /" + nome.encode()
            + b" /Encoding /WinAnsiEncoding >>")

    # O logo (XObject de imagem) entra nos recursos como /Im1, disponível a todas
    # as páginas — só a capa o desenha, mas tê-lo no recurso comum é inofensivo.
    id_imagem = 0
    if imagem:
        dados, w, h = imagem
        id_imagem = obj(
            b"<< /Type /XObject /Subtype /Image /Width " + str(w).encode()
            + b" /Height " + str(h).encode()
            + b" /ColorSpace /DeviceRGB /BitsPerComponent 8"
            + b" /Filter /FlateDecode /Length " + str(len(dados)).encode()
            + b" >>\nstream\n" + dados + b"\nendstream")

    recursos_txt = "<< /Font << " + " ".join(
        f"/{a} {n} 0 R" for a, n in fontes.items()) + " >>"
    if id_imagem:
        recursos_txt += f" /XObject << /Im1 {id_imagem} 0 R >>"
    recursos = (recursos_txt + " >>").encode()

    conteudos = []
    for fluxo in fluxos:
        comprimido = zlib.compress(fluxo, 9)
        conteudos.append(obj(
            b"<< /Length " + str(len(comprimido)).encode()
            + b" /Filter /FlateDecode >>\nstream\n" + comprimido + b"\nendstream"))

    paginas_id = len(objetos) + len(conteudos) + 1
    pagina_ids = []
    for cid in conteudos:
        pagina_ids.append(obj(
            f"<< /Type /Page /Parent {paginas_id} 0 R /MediaBox "
            f"[0 0 {A4[0]:.2f} {A4[1]:.2f}] /Resources ".encode() + recursos
            + f" /Contents {cid} 0 R >>".encode()))
    arvore = obj(
        b"<< /Type /Pages /Count " + str(len(pagina_ids)).encode()
        + b" /Kids [" + b" ".join(f"{i} 0 R".encode() for i in pagina_ids)
        + b"] >>")
    raiz = obj(f"<< /Type /Catalog /Pages {arvore} 0 R >>".encode())

    saida = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    posicoes = [0]
    for i, corpo in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f"{i} 0 obj\n".encode() + corpo + b"\nendobj\n"
    xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n".encode()
    saida += b"0000000000 65535 f \n"
    for pos in posicoes[1:]:
        saida += f"{pos:010d} 00000 n \n".encode()
    saida += (f"trailer\n<< /Size {len(objetos) + 1} /Root {raiz} 0 R >>\n"
              f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(saida)


def procedencia(assistencia: dict, origem: str, correlacao: str = "") -> list:
    """RQ-809: de onde veio cada coisa que está impressa."""
    return [
        ("origem", origem),
        ("correlacao_id", correlacao or uuid.uuid4().hex[:16]),
        ("ts_extracao", assistencia.get("quando", "")),
        ("ts_emissao", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        ("recorte", assistencia.get("escopo", "—")),
        ("modelo", assistencia.get("modelo", "—")),
        ("capacidade", assistencia.get("capacidade", "—")),
        ("tokens", f"{assistencia.get('entrada', 0)}/{assistencia.get('saida', 0)}"),
        ("custo_usd", f"{assistencia.get('custo_usd', 0):.6f}"),
    ]
