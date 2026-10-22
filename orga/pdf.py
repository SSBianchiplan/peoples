"""
GPlanSiS|Peoples - exportacao em PDF A3 paisagem.

O SVG que o motor emite e um subconjunto controlado - retangulos, linhas,
paths so com M/L, circulos e texto em cinco estilos. Isso torna viavel
escrever o PDF direto, sem Chromium headless (ADR-007 ficou obsoleto com o
ADR-011) e sem biblioteca de PDF.

O ganho nao e evitar dependencia: e que o **texto continua texto**. O PDF sai
vetorial e pesquisavel - `pdftotext` extrai os nomes (W7-C3) - porque usa as
14 fontes base do PDF com WinAnsiEncoding, que cobre o portugues sem embutir
arquivo de fonte.

O desenho sai sempre em **uma folha**: a escala e derivada do proprio desenho
para enquadra-lo inteiro na area util, centrado nos dois eixos. Desenho
pequeno e ampliado ate ocupar a folha; desenho largo e reduzido. A escala
resultante vai impressa no rodape - quem ve 8 % sabe que precisa filtrar ou
colapsar antes de mandar para a grafica.
"""
from __future__ import annotations

import zlib
from datetime import date
from pathlib import Path

A3_PAISAGEM = (1190.55, 841.89)          # 420 x 297 mm em pontos
MARGEM = 26.0
ALTURA_CABECALHO = 52.0
ALTURA_RODAPE = 30.0
ESCALA_MAX = 2.2                         # teto ao ampliar desenho pequeno
# Piso de leitura: abaixo disso o texto nao sobrevive a impressao. E o MESMO
# numero que o canvas usa para parar de encolher no ajuste a tela — o servidor
# injeta este valor no JS da pagina para os dois nao derivarem.
PISO_LEITURA = 0.38

# --- fontes base 14 --------------------------------------------------------
F_NORMAL, F_FORTE, F_ITALICO, F_MONO, F_MONO_FORTE = "F1", "F2", "F3", "F4", "F5"
FONTES = {
    F_NORMAL: "Helvetica", F_FORTE: "Helvetica-Bold", F_ITALICO: "Helvetica-Oblique",
    F_MONO: "Courier", F_MONO_FORTE: "Courier-Bold",
}

# Estilo por classe do SVG: (fonte, corpo, cor, cor quando o card e escuro)
ESTILOS = {
    "t-cod":   (F_MONO, 9.5, "#4A5053", "#9AA0A3"),
    "t-nome":  (F_FORTE, 13, "#2D3336", "#FFFFFF"),
    "t-pes":   (F_FORTE, 11.5, "#2D3336", "#F6A709"),
    "t-cargo": (F_NORMAL, 11, "#4A5053", "#C9CDCF"),
    "t-area":  (F_NORMAL, 10, "#4A5053", "#9AA0A3"),
    "t-mail":  (F_MONO, 9, "#4A5053", "#9AA0A3"),
    "t-item":  (F_NORMAL, 11, "#2D3336", "#C9CDCF"),
    "t-item-del": (F_ITALICO, 11, "#4A5053", "#C9CDCF"),
    "t-skill": (F_NORMAL, 10, "#4A5053", "#C9CDCF"),
    "t-cota":  (F_MONO, 9.5, "#4A5053", "#4A5053"),
    "t-cota-base": (F_MONO_FORTE, 9.5, "#EB6A20", "#EB6A20"),
}

# Preenchida pelo chamador a partir do cadastro de niveis; este e o padrao.
LEGENDA = [("Diretoria", "#2D3336"), ("Gerência", "#EB6A20"),
           ("Coordenação", "#F6A709"), ("Célula / área", "#7D8286"),
           ("Apoio", "#B9BDBF")]

# Larguras de avanco da Helvetica, em milesimos de em, direto do AFM.
#
# A versao anterior aproximava por classe de glifo e dava 500 para minusculas —
# que e Times, nao Helvetica. Para rotulo curto alinhado a direita a diferenca
# passava; em texto corrido ela some com um espaco inteiro a cada palavra, e as
# palavras encostam umas nas outras no PDF.
_LARG = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667,
    "'": 191, "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333,
    ".": 278, "/": 278,
    **{c: 556 for c in "0123456789"},
    ":": 278, ";": 278, "<": 584, "=": 584, ">": 584, "?": 556, "@": 1015,
    "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778,
    "H": 722, "I": 278, "J": 500, "K": 667, "L": 556, "M": 833, "N": 722,
    "O": 778, "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722,
    "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611,
    "[": 278, "\\": 278, "]": 278, "^": 469, "_": 556, "`": 333,
    "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556,
    "h": 556, "i": 222, "j": 222, "k": 500, "l": 222, "m": 833, "n": 556,
    "o": 556, "p": 556, "q": 556, "r": 333, "s": 500, "t": 278, "u": 556,
    "v": 500, "w": 722, "x": 500, "y": 500, "z": 500,
    "{": 334, "|": 260, "}": 334, "~": 584,
    # Acentuadas do WinAnsi que aparecem em portugues e espanhol: o avanco e o
    # da letra base, porque o acento nao ocupa largura propria.
    **{c: 556 for c in "áàâãäéêëíîïóôõöúûüçÁÀÂÃÄÉÊËÍÎÏÓÔÕÖÚÛÜÇñÑ"},
    "–": 556, "—": 1000, "“": 333, "”": 333, "‘": 222, "’": 222, "…": 1000,
    "·": 278, "×": 584, "°": 400, "€": 556, "ª": 370, "º": 365,
}


# Helvetica-Bold avanca ~7% a mais que a Helvetica na media dos glifos. Sem
# esse fator o texto depois de um trecho em negrito e desenhado por cima do
# anterior — o avanco calculado fica menor que o desenhado.
FATOR_FORTE = 1.07


def largura(txt: str, corpo: float, mono: bool = False,
            forte: bool = False) -> float:
    if mono:
        return len(txt) * corpo * 0.6
    bruta = sum(_LARG.get(c, 556) for c in txt) * corpo / 1000.0
    return bruta * FATOR_FORTE if forte else bruta


# ---------------------------------------------------------------------------
# PRIMITIVAS DE CONTEUDO
# ---------------------------------------------------------------------------
def _cor(hexa: str, traco: bool = False) -> str:
    h = hexa.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return f"{r:.3f} {g:.3f} {b:.3f} {'RG' if traco else 'rg'}"


def _esc(txt: str) -> str:
    saida = []
    for ch in str(txt):
        cod = ch.encode("cp1252", "replace")
        for b in cod:
            if b in (0x28, 0x29, 0x5C):
                saida.append("\\" + chr(b))
            elif b < 32:
                saida.append(" ")
            else:
                saida.append(chr(b))
    return "".join(saida)


class Tela:
    """Acumula operadores de conteudo PDF."""

    def __init__(self) -> None:
        self.ops: list[str] = []

    def __str__(self) -> str:
        return "\n".join(self.ops)

    def salvar(self) -> None:
        self.ops.append("q")

    def restaurar(self) -> None:
        self.ops.append("Q")

    def matriz(self, a, b, c, d, e, f) -> None:
        # 6 casas: com escala na casa dos milesimos (arvore inteira aberta),
        # 5 casas ja deixariam so 2 digitos significativos.
        self.ops.append(f"{a:.6f} {b:.6f} {c:.6f} {d:.6f} {e:.3f} {f:.3f} cm")

    def recorte(self, x, y, w, h) -> None:
        self.ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re W n")

    def retangulo(self, x, y, w, h, preenche=None, traco=None, espessura=1.0) -> None:
        if preenche:
            self.ops.append(_cor(preenche))
        if traco:
            self.ops.append(_cor(traco, True))
            self.ops.append(f"{espessura:.2f} w")
        self.ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        self.ops.append("B" if (preenche and traco) else "f" if preenche else "S")

    def linha(self, x1, y1, x2, y2, cor="#7D8286", espessura=1.0) -> None:
        self.ops.append(_cor(cor, True))
        self.ops.append(f"{espessura:.2f} w")
        self.ops.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def caminho(self, d: str, cor="#7D8286", espessura=1.2) -> None:
        """Path do conector: so 'M x y L x y' repetido (LAY-05/06/08)."""
        self.ops.append(_cor(cor, True))
        self.ops.append(f"{espessura:.2f} w")
        t = d.split()
        for i in range(0, len(t) - 5, 6):
            self.ops.append(f"{float(t[i+1]):.2f} {float(t[i+2]):.2f} m "
                            f"{float(t[i+4]):.2f} {float(t[i+5]):.2f} l")
        self.ops.append("S")

    def circulo(self, cx, cy, r, preenche=None, traco=None, espessura=1.2) -> None:
        k = r * 0.5523
        if preenche:
            self.ops.append(_cor(preenche))
        if traco:
            self.ops.append(_cor(traco, True))
            self.ops.append(f"{espessura:.2f} w")
        self.ops.append(f"{cx - r:.2f} {cy:.2f} m")
        self.ops.append(f"{cx - r:.2f} {cy + k:.2f} {cx - k:.2f} {cy + r:.2f} {cx:.2f} {cy + r:.2f} c")
        self.ops.append(f"{cx + k:.2f} {cy + r:.2f} {cx + r:.2f} {cy + k:.2f} {cx + r:.2f} {cy:.2f} c")
        self.ops.append(f"{cx + r:.2f} {cy - k:.2f} {cx + k:.2f} {cy - r:.2f} {cx:.2f} {cy - r:.2f} c")
        self.ops.append(f"{cx - k:.2f} {cy - r:.2f} {cx - r:.2f} {cy - k:.2f} {cx - r:.2f} {cy:.2f} c")
        self.ops.append("B" if (preenche and traco) else "f" if preenche else "S")

    def texto(self, x, y, txt, fonte=F_NORMAL, corpo=10, cor="#2D3336",
              invertido=False) -> None:
        """`invertido` desfaz o espelho do CTM do desenho — glifo sai de pé."""
        if not str(txt):
            return
        self.ops.append("BT")
        self.ops.append(_cor(cor))
        self.ops.append(f"/{fonte} {corpo:.2f} Tf")
        if invertido:
            self.ops.append(f"1 0 0 -1 {x:.2f} {y:.2f} Tm")
        else:
            self.ops.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
        self.ops.append(f"({_esc(txt)}) Tj")
        self.ops.append("ET")

    def imagem(self, nome, x, y, w, h) -> None:
        self.salvar()
        self.matriz(w, 0, 0, h, x, y)
        self.ops.append(f"/{nome} Do")
        self.restaurar()


# ---------------------------------------------------------------------------
# DESENHO DO ORGANOGRAMA
# ---------------------------------------------------------------------------
def _desenhar_layout(tela: Tela, layout: dict) -> None:
    """Emite o mesmo desenho do SVG. Coordenadas em espaco SVG; o CTM cuida."""
    # Cota de nivel. As coordenadas vem prontas do motor — inclusive a ancora
    # do texto, que muda de eixo entre a piramide e a lateral. O PDF nao tem
    # `text-anchor`: recuar pela largura da string e como se centraliza aqui.
    t = layout["trilho"]
    tela.linha(t["x1"], t["y1"], t["x2"], t["y2"], "#B9BDBF", 1)
    for c in layout["cotas"]:
        for tick in (c["t1"], c["t2"]):
            tela.linha(tick["x1"], tick["y1"], tick["x2"], tick["y2"], "#B9BDBF", 1)
        if c["marco"]:
            tela.retangulo(c["marco"]["x"], c["marco"]["y"], 6, 6, preenche="#EB6A20")
        fonte, corpo, cor, _ = ESTILOS["t-cota-base" if c["base"] else "t-cota"]
        larg = largura(c["rotulo"], corpo, True)
        recuo = larg if c["texto"]["ancora"] == "end" else larg / 2
        tela.texto(c["texto"]["x"] - recuo, c["texto"]["y"], c["rotulo"],
                   fonte, corpo, cor, invertido=True)

    # LAY-09: conectores antes dos cards
    for con in layout["conectores"]:
        tela.caminho(con["d"], "#7D8286", 1.2)

    for n in layout["nos"]:
        escuro = n["raiz"]
        tela.retangulo(n["x"], n["y"], n["w"], n["h"],
                       preenche="#2D3336" if escuro else "#FFFFFF",
                       traco="#2D3336" if escuro else "#D9DBDC", espessura=1)
        tela.retangulo(n["x"], n["y"], n["w"], 3, preenche=n["cor"])
        for regua in (n["regua"], n["regua2"]):
            if regua:
                tela.linha(n["x"] + 12, regua, n["x"] + n["w"] - 12, regua,
                           "#4A5053" if escuro else "#E7E9EA", 1)
        for t in n["textos"]:
            fonte, corpo, claro, sombrio = ESTILOS.get(t["cls"], ESTILOS["t-cargo"])
            tela.texto(t["x"], t["y"], t["txt"], fonte, corpo,
                       sombrio if escuro else claro, invertido=True)
        for i in n["itens"]:
            if i["mx"] is not None:
                if i["delegada"]:
                    tela.circulo(i["mx"], i["my"], 2.2, traco="#EB6A20", espessura=1.2)
                else:
                    tela.circulo(i["mx"], i["my"], 2.2,
                                 preenche="#7D8286" if escuro else "#7D8286")
            chave = "t-item-del" if i["delegada"] else "t-item"
            fonte, corpo, claro, sombrio = ESTILOS[chave]
            tela.texto(i["x"], i["y"], i["txt"], fonte, corpo,
                       sombrio if escuro else claro, invertido=True)
        for s in n["skills"]:
            fonte, corpo, claro, sombrio = ESTILOS["t-skill"]
            tela.texto(s["x"], s["y"], s["txt"], fonte, corpo,
                       sombrio if escuro else claro, invertido=True)


def _cabecalho(tela: Tela, meta: dict, logo: tuple | None) -> None:
    lg, ag = A3_PAISAGEM
    topo = ag - MARGEM
    x = MARGEM

    if logo:
        _, lw, lh = logo
        altura_logo = 15.0
        largura_logo = altura_logo * lw / lh
        tela.imagem("Im1", x, topo - altura_logo - 1, largura_logo, altura_logo)
        x += largura_logo + 14
        tela.linha(x - 7, topo - 17, x - 7, topo + 1, "#D9DBDC", 1)

    tela.texto(x, topo - 11, meta["titulo"], F_FORTE, 14, "#2D3336")
    tela.texto(x, topo - 26, meta["subtitulo"], F_NORMAL, 9, "#4A5053")

    direita = lg - MARGEM
    tela.texto(direita - largura(meta["data"], 9), topo - 11, meta["data"],
               F_NORMAL, 9, "#4A5053")
    tela.texto(direita - largura(meta["tenant"], 9), topo - 26, meta["tenant"],
               F_NORMAL, 9, "#7D8286")
    tela.linha(MARGEM, ag - MARGEM - ALTURA_CABECALHO + 12, lg - MARGEM,
               ag - MARGEM - ALTURA_CABECALHO + 12, "#EB6A20", 1.4)


def _t(texto: str, idioma: str | None = None, **p) -> str:
    """O PDF é levado para reunião: sai na língua de quem exportou."""
    from . import idiomas
    return idiomas.traduzir(texto, idioma or idiomas.PADRAO, **p)


def _rodape(tela: Tela, meta: dict, escala: float) -> None:
    legenda = meta.get("legenda") or LEGENDA
    lg = A3_PAISAGEM[0]
    y = MARGEM + 8
    tela.linha(MARGEM, y + 13, lg - MARGEM, y + 13, "#D9DBDC", 0.8)

    x = MARGEM
    for rotulo, cor in legenda:
        tela.retangulo(x, y + 1, 14, 4, preenche=cor)
        tela.texto(x + 19, y, rotulo, F_NORMAL, 8, "#4A5053")
        x += 19 + largura(rotulo, 8) + 16
    tela.circulo(x + 3, y + 2.5, 2.4, traco="#EB6A20", espessura=1)
    tela.texto(x + 10, y, _t("accountability delegada", meta.get("idioma")),
               F_ITALICO, 8, "#4A5053")

    # A escala e informacao de engenharia, nao enfeite: e ela que diz se o
    # desenho ainda e legivel no papel ou se falta filtrar antes de imprimir.
    rodape = (_t("escala {escala}", meta.get("idioma"),
                 escala=rotulo_escala(escala)) + "   ·   " + meta["rodape"])
    tela.texto(lg - MARGEM - largura(rodape, 8), y, rodape, F_NORMAL, 8, "#7D8286")


def rotulo_escala(escala: float) -> str:
    """Nunca "0 %": num organograma de 59 000 px a escala e pequena, nao nula,
    e arredondar para zero apagaria justamente o alerta que ela existe para dar."""
    pct = escala * 100
    if pct < 1:
        return "< 1 %"
    return f"{pct:.0f} %"


# ---------------------------------------------------------------------------
# MONTAGEM DO ARQUIVO
# ---------------------------------------------------------------------------
def _logo_pdf(caminho: Path) -> tuple[bytes, int, int] | None:
    """PNG -> XObject RGB comprimido. Sem Pillow, o cabecalho vai sem logo."""
    try:
        from PIL import Image
    except ImportError:
        return None
    if not caminho.exists():
        return None
    im = Image.open(caminho).convert("RGBA")
    fundo = Image.new("RGB", im.size, (255, 255, 255))
    fundo.paste(im, mask=im.split()[3])
    if fundo.width > 720:
        fundo = fundo.resize((720, max(1, round(720 * fundo.height / fundo.width))))
    return zlib.compress(fundo.tobytes(), 9), fundo.width, fundo.height


def area_util() -> tuple[float, float, float, float]:
    """(x, base, largura, altura) da regiao entre cabecalho e rodape."""
    lg, ag = A3_PAISAGEM
    topo = ag - MARGEM - ALTURA_CABECALHO
    base = MARGEM + ALTURA_RODAPE
    return MARGEM, base, lg - 2 * MARGEM, topo - base


def enquadrar(vb_w: float, vb_h: float) -> tuple[float, float, float]:
    """Caixa (largura, altura) -> (escala, tx, ty) que a poe inteira na folha.

    Centra a CAIXA publicada pelo motor como bbox real (LAY-14), que e o mesmo
    criterio de `preserveAspectRatio="xMidYMid meet"` — nao a tinta. As duas
    coisas diferem por poucos pontos, porque o trilho de cota fica a esquerda
    do primeiro card, e e o viewBox que o botao anuncia e o SVG exporta.

    Funcao pura, e o coracao do "cabe em uma pagina": o eixo mais apertado
    manda na escala, e a folga sobrando vira margem igual dos dois lados.
    O CTM correspondente e [escala 0 0 -escala tx ty] - o Y negativo converte
    o eixo do SVG (cresce para baixo) no do PDF (cresce para cima).
    """
    caixa_x, caixa_base, caixa_w, caixa_h = area_util()
    if vb_w <= 0 or vb_h <= 0:
        return 1.0, caixa_x, caixa_base + caixa_h
    escala = min(caixa_w / vb_w, caixa_h / vb_h, ESCALA_MAX)
    tx = caixa_x + (caixa_w - vb_w * escala) / 2
    ty = caixa_base + caixa_h - (caixa_h - vb_h * escala) / 2
    return escala, tx, ty


def gerar(layout: dict, meta: dict, logo: Path | None = None) -> bytes:
    """Devolve os bytes do PDF A3 paisagem, em uma unica folha."""
    caixa_x, caixa_base, caixa_w, caixa_h = area_util()
    vb_x, vb_y, vb_w, vb_h = (float(v) for v in layout["viewbox"].split())
    escala, tx, ty = enquadrar(vb_w, vb_h)

    imagem = _logo_pdf(logo) if logo else None
    tela = Tela()
    _cabecalho(tela, meta, imagem)
    _rodape(tela, meta, escala)
    tela.salvar()
    tela.recorte(caixa_x, caixa_base, caixa_w, caixa_h)   # rede de seguranca
    # A origem do viewBox entra na translacao: hoje `calcular_layout` sempre
    # emite "0 0 w h", mas assumir isso em silencio deslocaria o desenho inteiro
    # se um dia deixar de ser verdade.
    tela.matriz(escala, 0, 0, -escala, tx - vb_x * escala, ty + vb_y * escala)
    _desenhar_layout(tela, layout)
    tela.restaurar()
    return _montar(zlib.compress(str(tela).encode("latin-1", "replace"), 9), imagem)


def _montar(fluxo: bytes, imagem: tuple | None) -> bytes:
    lg, ag = A3_PAISAGEM
    objetos: list[bytes] = []

    def add(corpo: bytes) -> int:
        objetos.append(corpo)
        return len(objetos)

    fontes = " ".join(f"/{k} {5 + i} 0 R" for i, k in enumerate(FONTES))
    id_catalogo, id_pages = 1, 2
    objetos.append(b"")                                   # 1 catalogo
    objetos.append(b"")                                   # 2 pages
    objetos.append(b"")                                   # 3 recursos
    objetos.append(b"")                                   # 4 (reserva/imagem)
    for nome in FONTES.values():                          # 5..9 fontes
        add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{nome} "
            f"/Encoding /WinAnsiEncoding >>".encode())

    id_imagem = 0
    if imagem:
        dados, w, h = imagem
        id_imagem = add(b"<< /Type /XObject /Subtype /Image /Width " + str(w).encode()
                        + b" /Height " + str(h).encode()
                        + b" /ColorSpace /DeviceRGB /BitsPerComponent 8"
                        + b" /Filter /FlateDecode /Length " + str(len(dados)).encode()
                        + b" >>\nstream\n" + dados + b"\nendstream")

    id_fluxo = add(b"<< /Filter /FlateDecode /Length "
                   + str(len(fluxo)).encode() + b" >>\nstream\n"
                   + fluxo + b"\nendstream")
    id_pagina = add(
        f"<< /Type /Page /Parent {id_pages} 0 R /MediaBox [0 0 {lg:.2f} {ag:.2f}] "
        f"/Resources 3 0 R /Contents {id_fluxo} 0 R >>".encode())

    recursos = f"<< /Font << {fontes} >>"
    if id_imagem:
        recursos += f" /XObject << /Im1 {id_imagem} 0 R >>"
    recursos += " >>"
    objetos[2] = recursos.encode()
    objetos[3] = b"<< >>"
    objetos[1] = (f"<< /Type /Pages /Count 1 /Kids [{id_pagina} 0 R] >>").encode()
    objetos[0] = f"<< /Type /Catalog /Pages {id_pages} 0 R >>".encode()

    saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    posicoes = []
    for i, corpo in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f"{i} 0 obj\n".encode() + corpo + b"\nendobj\n"
    inicio_xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n".encode()
    saida += b"0000000000 65535 f \n"
    for pos in posicoes:
        saida += f"{pos:010d} 00000 n \n".encode()
    saida += (f"trailer\n<< /Size {len(objetos) + 1} /Root {id_catalogo} 0 R >>\n"
              f"startxref\n{inicio_xref}\n%%EOF\n").encode()
    return bytes(saida)


def meta_padrao(titulo: str, subtitulo: str, tenant: str, rodape: str) -> dict:
    return {"titulo": titulo, "subtitulo": subtitulo, "tenant": tenant,
            "rodape": rodape, "data": date.today().strftime("%d/%m/%Y")}
