"""
GPlanSiS|Peoples — o contrato da grade editável (AG Grid Community).

A tabela sempre foi desenhada no servidor. A grade não substitui esse desenho:
ela se monta **por cima** dele. Sem JavaScript, ou com a biblioteca fora do ar,
o `<table>` renderizado continua ali e a vista funciona como antes — é a mesma
escada de melhoria progressiva que o resto do sistema usa.

Três decisões que estão no código, e não neste texto:

**A grade é vista, não fonte.** Toda edição vai ao servidor por rota própria,
passa pelas mesmas guardas do painel (permissão, ciclo, renumeração, ledger,
ponto de desfazer) e a grade recarrega os dados. Nada é resolvido no cliente e
depois "sincronizado": um estado paralelo no navegador seria uma segunda
verdade, e a primeira briga entre as duas ninguém saberia arbitrar (ADR-011).

**Suspensa onde o vocabulário é do sistema.** Nível, vínculo, situação, centro
de custo e vertical não são texto livre — são listas que alguém cadastrou. Um
campo de texto ali convida a digitar "Gerencia" ao lado de "Gerência" e a
descobrir a divergência três meses depois, num relatório. Cargo e departamento
ganham suspensa **com digitação livre**: o vocabulário existe, mas cresce.

**Derivado não se edita.** Profundidade, número de subordinados, tempo de casa,
N5 e natureza são resultado — de árvore, de admissão, do cadastro de centros de
custo. Deixá-los editáveis ofereceria à pessoa mudar um número que o próximo
render recalcula por cima. A grade os mostra e explica, na dica da célula, de
onde vêm e onde se muda de verdade.

A licença da AG Grid Community é MIT e o arquivo vive em `web/vendor/`, como o
htmx: nada é buscado de CDN em tempo de execução.
"""
from __future__ import annotations

from . import dominio

# Editores que a grade conhece. O nome é do domínio, e não da AG Grid: se a
# biblioteca trocar de API, o mapa muda num lugar só.
TEXTO, SUSPENSA, ABERTA, DATA, LONGO = "texto", "suspensa", "aberta", "data", "longo"

# (chave, editor, domínio da suspensa, largura, dica de por que não se edita)
#
# A ordem e os rótulos NÃO moram aqui: vêm de `main.COLUNAS_TABELA`, que é o que
# o seletor de colunas e o CSV já leem. Duas listas de colunas divergiriam na
# primeira coluna nova, e a grade sairia com um título a menos que a tabela.
CAMPOS = {
    "codigo": (TEXTO, "", 96, ""),
    "nivel_n": (None, "", 56,
                "A profundidade é a posição na árvore: mude o pai da linha e "
                "ela muda sozinha."),
    "nome": (TEXTO, "", 230, ""),
    "cargo": (ABERTA, "cargo", 210, ""),
    "tipo": (SUSPENSA, "tipo", 130, ""),
    "area": (ABERTA, "area", 170, ""),
    "centro_custo": (SUSPENSA, "centro_custo", 92, ""),
    "n5": (None, "", 70,
           "N5 vem do cadastro de centros de custo, pela chave N3 + "
           "Departamento. Edite em Configurações › Centros de custo."),
    # A coluna Vertical mostra `cc.vertical_negocio` — a vertical RESOLVIDA
    # pelo cadastro —, e não o campo `vertical` da unidade. São coisas
    # diferentes com o mesmo nome, e deixar a coluna editável gravaria num
    # campo que a coluna não estava mostrando.
    "vertical": (None, "", 92,
                 "A vertical vem do cadastro de centros de custo, pela chave "
                 "N3 + Departamento. Edite em Configurações › Centros de custo."),
    "tipo_cc": (None, "", 130,
                "A natureza vem do cadastro de centros de custo. Edite em "
                "Configurações › Centros de custo."),
    "vinculo": (SUSPENSA, "vinculo", 120, ""),
    "sub": (None, "", 64,
            "Subordinados diretos é uma contagem: crie, mova ou remova linhas "
            "e ela acompanha."),
    "accountabilities": (LONGO, "", 280, ""),
    "email": (TEXTO, "", 210, ""),
    "data_inicio": (DATA, "", 120, ""),
    "tempo_casa": (None, "", 110,
                   "O tempo de casa é calculado da admissão, em dias corridos "
                   "sobre 365. Corrija a data e ele acompanha."),
    "status": (SUSPENSA, "status", 110, ""),
}

# Campos que a rota de célula aceita gravar. Fora desta lista o pedido é
# recusado — o formulário é coisa que se forja, e "campo" chega por POST.
EDITAVEIS = frozenset(c for c, (e, *_) in CAMPOS.items() if e)


def colunas(colunas_tabela: list[dict]) -> list[dict]:
    """As colunas da grade, na ordem e com os rótulos que a tabela já usa."""
    saida = []
    for c in colunas_tabela:
        editor, dom, largura, porque = CAMPOS.get(c["chave"], (TEXTO, "", 140, ""))
        saida.append({
            "chave": c["chave"], "rotulo": c["rotulo"], "on": c["on"],
            "editor": editor or "", "dominio": dom, "largura": largura,
            "porque": porque,
        })
    return saida


def _accountabilities(u) -> str:
    """Uma por linha, com `>` marcando a delegada — o mesmo texto da gaveta.

    O editor longo devolve exatamente isto de volta, e `main.salvar` já sabe
    lê-lo: um segundo formato para a mesma coisa divergiria do primeiro.
    """
    return "\n".join(("> " if r.get("origem") == "delegada" else "")
                     + str(r.get("descricao", "")) for r in u.responsabilidades)


def linha(l: dict, rotulos_nivel: dict, anos) -> dict:
    """Uma linha da tabela achatada, no formato que a grade consome.

    Recebe o dicionário que `main.linhas_tabela()` já monta — a grade não
    reconstrói a árvore nem reaplica filtro e colapso. Uma segunda travessia
    daria uma segunda ordem, e a grade mostraria uma árvore que a tabela não
    mostra.
    """
    u, cc = l["u"], l["cc"]
    return {
        "id": u.id,
        "pai": u.parent_id,
        "d": l["d"],
        "filhos": l["n"],
        "descendentes": l["descendentes"],
        "colapsado": l["colapsado"],
        "achou": l["achou"],
        "passagem": l["passagem"],
        "codigo": u.codigo,
        "nivel_n": f"N{l['d']}",
        "nome": u.nome,
        "cargo": u.cargo,
        "tipo": u.tipo,
        "tipo_rotulo": rotulos_nivel.get(u.tipo, u.tipo),
        "area": u.area,
        "centro_custo": u.centro_custo,
        "n5": cc.get("n5", ""),
        "vertical": cc.get("vertical_negocio", ""),
        "tipo_cc": cc.get("tipo_cc", ""),
        "vinculo": u.vinculo,
        "sub": l["n"] or "",
        "accountabilities": _accountabilities(u),
        "email": u.email,
        "data_inicio": u.data_inicio,
        "tempo_casa": anos(l["anos"]),
        "status": u.status,
    }


def dominios(config, opcoes: dict, traduzir) -> dict[str, list[dict]]:
    """As listas das suspensas, como pares valor/rótulo.

    Nível, vínculo e situação saem da configuração e do domínio — são o
    vocabulário fechado do sistema. Departamento, cargo e centro de custo saem
    do **dado observado**, o mesmo que alimenta os chips de filtro: lista fixa
    não conhece o departamento que nasceu ontem.
    """
    def pares(campo):
        return [{"v": v, "r": r} for v, r in opcoes.get(campo, []) if v]

    return {
        "tipo": [{"v": n["codigo"], "r": traduzir(n["rotulo"])}
                 for n in config.niveis],
        "vinculo": [{"v": v, "r": traduzir(rot[0])}
                    for v, rot in dominio.VINCULOS.items()],
        "status": [{"v": v, "r": traduzir(r)} for v, r in dominio.STATUS.items()],
        "area": pares("area"),
        "cargo": pares("cargo"),
        "centro_custo": pares("centro_custo"),
    }
