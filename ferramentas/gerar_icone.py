"""Gera os ícones de aplicativo do GPlanSiS|Peoples a partir de UMA geometria.

O favicon do navegador é um SVG embutido no `<head>`, e resolve o desktop. O
celular não usa nenhum dos dois caminhos do desktop:

  **iOS** ignora o favicon e o manifest para o atalho na tela inicial: ele lê
  `apple-touch-icon`, e só aceita **PNG**. Sem esse arquivo, o iPhone gera o
  ícone tirando um retrato reduzido da página — que é o que dá aquele atalho
  ilegível com um pedaço do formulário de login dentro.

  **Android/Chrome** usa o `manifest`, e além do ícone comum quer um
  **maskable**: o sistema recorta o ícone na forma do tema do aparelho (círculo,
  losango, quadrado arredondado). Um ícone desenhado até a borda perde o "P" no
  recorte, então o maskable é o mesmo desenho com margem — o dobro de folga que
  a especificação pede como zona segura.

Uma geometria só, definida na grade de 16 do favicon, escalada para cada
tamanho: assim o ícone da aba, o do iPhone e o do Android são o mesmo desenho, e
mexer num lugar não deixa os outros para trás.

Pillow e nada mais — sem ferramenta de design, reproduzível em qualquer máquina,
como o `gerar_marca.py`.

    python ferramentas/gerar_icone.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parents[1]
MARCA = RAIZ / "web" / "marca"

GRAFITE = (45, 51, 54, 255)          # #2D3336 — o grafite institucional
LARANJA = (235, 106, 32, 255)        # #EB6A20 — a barra do wordmark
BRANCO = (255, 255, 255, 255)

# A grade de 16, igual à do favicon. Tudo abaixo é fração dela.
G = 16.0
ESCALA = 8                           # supersampling: bordas limpas na redução


def _desenhar(tela: int, conteudo: float, arredondar: float) -> Image.Image:
    """A marca: a barra laranja e o «P» de Peoples, o final do wordmark.

    `conteudo` é a fração do lado que o desenho ocupa — 1.0 desenha até a borda
    (o ícone comum), menos que isso deixa a margem que o recorte do Android come.
    `arredondar` é o raio do canto em frações do lado; 0 deixa o quadrado inteiro,
    que é o certo para o maskable (a máscara do aparelho é que arredonda).
    """
    lado = tela * ESCALA
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if arredondar:
        d.rounded_rectangle([0, 0, lado - 1, lado - 1],
                            radius=arredondar * lado, fill=GRAFITE)
    else:
        d.rectangle([0, 0, lado - 1, lado - 1], fill=GRAFITE)

    # A grade de 16 mapeada para dentro da área de conteúdo, centrada.
    u = lado * conteudo / G
    deslocar = lado * (1 - conteudo) / 2

    def x(v: float) -> float:
        return deslocar + v * u

    # A barra laranja: o «|» que separa GPlanSiS de Peoples.
    d.rounded_rectangle([x(3.1), x(3), x(5.0), x(13)], radius=0.8 * u, fill=LARANJA)

    # O «P», em geometria e não em fonte: texto dependeria da fonte instalada na
    # máquina de quem gera, e o mesmo comando produziria ícones diferentes.
    d.rectangle([x(6.6), x(3), x(8.5), x(13)], fill=BRANCO)          # haste
    d.rectangle([x(8.5), x(3), x(9.7), x(8.8)], fill=BRANCO)         # ombro da bojo
    d.ellipse([x(9.7 - 2.9), x(3), x(9.7 + 2.9), x(8.8)], fill=BRANCO)
    # A contraforma, por último: é ela que faz o «P» não virar um borrão.
    d.rectangle([x(8.5), x(4.7), x(9.7), x(7.1)], fill=GRAFITE)
    d.ellipse([x(9.7 - 1.2), x(4.7), x(9.7 + 1.2), x(7.1)], fill=GRAFITE)

    return img.resize((tela, tela), Image.LANCZOS)


# Cada arquivo com o motivo de existir, porque nenhum deles é opcional por acaso.
ARQUIVOS = [
    # iOS, tela inicial. 180 é o maior que o iPhone pede; ele reduz para o resto.
    ("icone-180.png", 180, 1.0, 0.0),
    # Android/Chrome: o par que o manifest exige. Sem os dois tamanhos o Chrome
    # não considera o site instalável e nem oferece o atalho.
    ("icone-192.png", 192, 1.0, 0.22),
    ("icone-512.png", 512, 1.0, 0.22),
    # Maskable: margem grande e canto reto — o recorte do aparelho é que decide
    # a forma, e o desenho tem de sobreviver ao pior deles (o círculo).
    ("icone-512-maskable.png", 512, 0.58, 0.0),
]


def main() -> int:
    MARCA.mkdir(parents=True, exist_ok=True)
    for nome, tamanho, conteudo, raio in ARQUIVOS:
        alvo = MARCA / nome
        _desenhar(tamanho, conteudo, raio).save(alvo, "PNG", optimize=True)
        print(f"{alvo.relative_to(RAIZ)}  {tamanho}px  "
              f"conteúdo {conteudo:.0%}  {alvo.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
