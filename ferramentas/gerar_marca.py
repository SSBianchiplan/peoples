"""Gera os ativos de marca do GPlanSiS|Peoples (substituem os da organização
anterior, que foram removidos): wordmark branco e preto, lockup da tela de
entrada e dois fundos abstratos para a tela de login.

Só Pillow — sem design tool, reproduzível em qualquer máquina.

    python ferramentas/gerar_marca.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
MARCA = RAIZ / "web" / "marca"

LARANJA = (235, 106, 32)
AMBAR = (246, 167, 9)
GRAFITE = (45, 51, 54)
BRANCO = (255, 255, 255)
CINZA = (125, 130, 134)

FONTES = [
    "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    for f in FONTES:
        if Path(f).exists():
            return ImageFont.truetype(f, tamanho)
    return ImageFont.load_default()


def wordmark(cor_texto, nome: str) -> None:
    """`GPlanSiS|Peoples` — a barra em laranja, o resto na cor pedida. Fundo
    transparente, 240 px de altura: o cabeçalho usa 17 px, o PDF 15 mm."""
    f = fonte(180)
    partes = [("GPlanSiS", cor_texto), ("|", LARANJA), ("Peoples", cor_texto)]
    larguras = [f.getlength(t) for t, _ in partes]
    w = int(sum(larguras) + 80)
    img = Image.new("RGBA", (w, 240), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 40
    for (t, cor), lw in zip(partes, larguras):
        d.text((x, 20), t, font=f, fill=cor + (255,))
        x += lw
    img.save(MARCA / nome, optimize=True)


def lockup() -> None:
    """A lâmina direita do login: PEO/PLES empilhado em laranja, contorno
    arredondado e a pastilha com o nome do hub. Fundo preto de propósito — o
    template usa `mix-blend-mode:screen`, e o preto some sobre a lâmina."""
    W, H = 651, 540
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((60, 40, 590, 500), radius=42, outline=BRANCO, width=6)
    d.rounded_rectangle((110, 0, 300, 150), radius=42, fill=BRANCO)
    f = fonte(150)
    d.text((95, 140), "PEO", font=f, fill=LARANJA)
    d.text((95, 330), "PLES", font=f, fill=LARANJA)
    # pastilha
    d.rounded_rectangle((330, 290, 600, 380), radius=45, fill=LARANJA)
    fp = fonte(56)
    tw = fp.getlength("GPlanSiS")
    d.text((465 - tw / 2, 302), "GPlanSiS", font=fp, fill=BRANCO)
    img.save(MARCA / "lockup-peoples.png", optimize=True)


def _gradiente(W: int, H: int, a, b) -> Image.Image:
    base = Image.new("RGB", (W, H), a)
    px = base.load()
    for y in range(H):
        t = y / (H - 1)
        cor = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = cor
    return base


def fundo_rede(nome: str, semente: int) -> None:
    """Rede de nós — a estrutura vista de longe. Baixa opacidade: é fundo de um
    cartão de login, não ilustração."""
    rnd = random.Random(semente)
    W, H = 2000, 1125
    img = _gradiente(W, H, (14, 17, 18), (31, 36, 38))
    cam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    pontos = [(rnd.randint(0, W), rnd.randint(0, H)) for _ in range(70)]
    for i, (x1, y1) in enumerate(pontos):
        for x2, y2 in pontos[i + 1:]:
            if math.hypot(x2 - x1, y2 - y1) < 260:
                d.line((x1, y1, x2, y2), fill=CINZA + (60,), width=2)
    for x, y in pontos:
        r = rnd.choice((6, 8, 11))
        cor = LARANJA if rnd.random() < 0.3 else CINZA
        d.ellipse((x - r, y - r, x + r, y + r), fill=cor + (170,))
    cam = cam.filter(ImageFilter.GaussianBlur(0.6))
    img.paste(cam, (0, 0), cam)
    img.save(MARCA / nome, quality=86)


def fundo_piramide(nome: str) -> None:
    """A pirâmide invertida — a liderança na base, os times acima — como faixas
    de cartões esmaecidos."""
    W, H = 2000, 1125
    img = _gradiente(W, H, (20, 24, 26), (10, 12, 13))
    cam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    niveis = [(16, 90), (10, 250), (6, 420), (3, 600), (1, 800)]
    for n, y in niveis:
        cw, gap = 96, 30
        total = n * cw + (n - 1) * gap
        x0 = (W - total) / 2
        for i in range(n):
            x = x0 + i * (cw + gap)
            d.rounded_rectangle((x, y, x + cw, y + 120), radius=10,
                                fill=GRAFITE + (150,), outline=CINZA + (90,), width=2)
            d.rectangle((x, y, x + cw, y + 12), fill=(LARANJA if y >= 600 else AMBAR) + (200,))
    img.paste(cam, (0, 0), cam)
    img.save(MARCA / nome, quality=86)


if __name__ == "__main__":
    MARCA.mkdir(parents=True, exist_ok=True)
    for velho in ("lockup-organograma.png", "paleta.png"):
        (MARCA / velho).unlink(missing_ok=True)
    (RAIZ / "docs" / "trio_comunicado.png").unlink(missing_ok=True)
    wordmark(BRANCO, "peoples-branco.png")
    wordmark(GRAFITE, "peoples-preto.png")
    lockup()
    fundo_rede("cultura.jpg", 7)
    fundo_piramide("fundo-organograma.jpg")
    for p in sorted(MARCA.iterdir()):
        print(f"{p.name:28s} {p.stat().st_size // 1024:5d} KB")
