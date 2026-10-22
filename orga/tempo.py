"""
GPlanSiS|Peoples — tempo de empresa: quanto tempo de casa a estrutura carrega.

A planilha do RH traz a data de admissão de cada pessoa, e é o primeiro dado
que este organograma tem sobre o **tempo**. Tudo o mais aqui descreve como a
empresa está agora; a admissão é a única coluna que diz como ela chegou aqui.

**Nada é gravado.** Como `estrutura.py`, este módulo recebe unidades e devolve
dicionários — as contas são refeitas a cada render, sobre o recorte vigente.
Guardar um tempo de casa seria guardar um número que nasce velho: gravado hoje,
mente amanhã. A data de admissão é o fato; o resto é aritmética.

Três decisões que estão no código, e não neste texto:

**Sem data não é zero.** Quem não tem admissão cadastrada fica de fora das
médias e aparece contado à parte. Somá-lo como zero inventaria um recém-
contratado e puxaria a média para baixo — justamente o número que alguém usaria
para decidir sobre retenção.

**Mediana, e não só média.** Numa área com um fundador de 15 anos e quatro
recém-chegados, a média diz 3,4 anos e nenhuma das cinco pessoas está perto
disso. A mediana diz 0,6 e descreve a área. As duas aparecem, porque a
distância entre elas é a informação: onde média e mediana divergem muito, há
alguém sozinho no topo.

**Grupo pequeno não ganha estatística.** Abaixo de `PISO_GRUPO` pessoas, um
recorte mostra a contagem e recusa a mediana: com duas pessoas ela é a média
das duas, e publicar isso como indicador convida a decidir sobre ruído.
"""
from __future__ import annotations

from datetime import date

from . import dominio
from .dominio import faixa_de_casa, sem_acento, tempo_de_casa

# Abaixo disto o grupo é pequeno demais para uma mediana significar algo.
PISO_GRUPO = 3

# Admissão adiante de hoje não é erro nem faixa: é contratação assinada que
# ainda não começou. Fica visível e fora das médias — misturá-la com quem já
# está trabalhando responderia outra pergunta.
FUTURO = "futuro"


def _pessoas(unidades, incluir_raiz: bool = False) -> list:
    """As unidades que são gente. A raiz é nó sintético, não empregado."""
    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    return [u for u in us if incluir_raiz or u.parent_id is not None]


def medir(unidades, hoje: date | None = None) -> list[dict]:
    """Uma linha por pessoa, com os anos de casa e a faixa já resolvidos.

    É a base de todo o resto: os agrupamentos abaixo consomem esta lista, e não
    o dicionário de unidades, para que a régua do tempo seja aplicada uma vez
    só. Duas contas de "anos de casa" no mesmo módulo divergiriam no primeiro
    ajuste, e a que estivesse errada seria a que ninguém conferiu.
    """
    hoje = hoje or date.today()
    linhas = []
    for u in _pessoas(unidades):
        anos = tempo_de_casa(u.data_inicio, hoje)
        futura = anos is not None and anos < 0
        linhas.append({
            "id": u.id, "codigo": u.codigo, "nome": u.nome, "cargo": u.cargo,
            "area": u.area, "tipo": u.tipo, "vinculo": u.vinculo,
            "centro_custo": u.centro_custo, "vertical": u.vertical,
            "data_inicio": u.data_inicio, "status": u.status,
            "anos": anos,
            "faixa": FUTURO if futura else faixa_de_casa(anos),
        })
    return linhas


def _mediana(valores: list[float]) -> float | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    if len(ordenados) % 2:
        return ordenados[meio]
    return (ordenados[meio - 1] + ordenados[meio]) / 2


def resumo(linhas: list[dict]) -> dict:
    """Os números do topo: quantos, há quanto tempo, e quantos ficaram de fora."""
    com_data = [l["anos"] for l in linhas
                if l["anos"] is not None and l["faixa"] != FUTURO]
    return {
        "pessoas": len(linhas),
        "com_data": len(com_data),
        "sem_data": sum(1 for l in linhas if l["anos"] is None),
        "futuros": sum(1 for l in linhas if l["faixa"] == FUTURO),
        "media": (sum(com_data) / len(com_data)) if com_data else None,
        "mediana": _mediana(com_data),
        "minimo": min(com_data) if com_data else None,
        "maximo": max(com_data) if com_data else None,
        # A soma dos anos de casa é o "capital de experiência" da estrutura: o
        # que a empresa perde de uma vez se todos saírem no mesmo dia.
        "anos_somados": sum(com_data) if com_data else 0.0,
    }


def por_faixa(linhas: list[dict]) -> list[dict]:
    """A distribuição, na ordem das faixas — nunca na ordem da contagem.

    Ordenar por tamanho faria a barra maior mudar de lugar entre dois renders e
    o desenho deixaria de ser comparável com o do mês passado. A faixa é uma
    escala; escala não se reordena.
    """
    total = len(linhas) or 1
    saida = []
    for chave, rotulo, _piso in dominio.FAIXAS_CASA:
        n = sum(1 for l in linhas if l["faixa"] == chave)
        saida.append({"chave": chave, "rotulo": rotulo, "n": n,
                      "pct": round(100 * n / total, 1)})
    for chave, rotulo in ((FUTURO, "A começar"), ("", "Sem data")):
        n = sum(1 for l in linhas if l["faixa"] == chave)
        if n:
            saida.append({"chave": chave, "rotulo": rotulo, "n": n,
                          "pct": round(100 * n / total, 1)})
    return saida


def por(linhas: list[dict], campo: str, rotulos: dict | None = None) -> list[dict]:
    """Agrupa por um campo da pessoa e mede cada grupo.

    Serve a `area`, `vinculo`, `tipo` e `vertical` com o mesmo código: a
    pergunta "quem tem mais tempo de casa" é a mesma, muda só o corte. Um
    agrupador por campo evita quatro funções que divergem na terceira edição.
    """
    grupos: dict[str, list[dict]] = {}
    for l in linhas:
        chave = str(l.get(campo) or "")
        grupos.setdefault(chave, []).append(l)

    saida = []
    for chave, gente in grupos.items():
        r = resumo(gente)
        saida.append({
            "chave": chave,
            "rotulo": (rotulos or {}).get(chave, chave) or "—",
            "n": r["pessoas"],
            "media": r["media"],
            # Mediana só com gente suficiente. Com duas pessoas ela é a média
            # das duas, e publicá-la como indicador convida a decidir sobre ruído.
            "mediana": r["mediana"] if r["com_data"] >= PISO_GRUPO else None,
            "minimo": r["minimo"],
            "maximo": r["maximo"],
            "novatos": sum(1 for l in gente if l["faixa"] == "ate1"),
            "veteranos": sum(1 for l in gente if l["faixa"] == "mais10"),
        })
    # Do mais numeroso para o menor, e o nome desempata: dois grupos do mesmo
    # tamanho não podem trocar de lugar entre dois renders (RNF-02).
    return sorted(saida, key=lambda g: (-g["n"], sem_acento(g["rotulo"])))


def admissoes_por_ano(linhas: list[dict]) -> list[dict]:
    """Quantas pessoas entraram em cada ano, e quantas delas ainda estão.

    Só quem está na estrutura hoje aparece: o organograma não guarda quem saiu,
    então isto NÃO é histórico de contratação — é a idade da equipe atual, vista
    pelo ano de entrada. Ler como "contratamos 40 em 2024" seria errado se
    quinze saíram no caminho; o que a linha diz é "40 dos que estão hoje
    entraram em 2024".
    """
    contagem: dict[str, int] = {}
    for l in linhas:
        if l["data_inicio"]:
            contagem[l["data_inicio"][:4]] = contagem.get(l["data_inicio"][:4], 0) + 1
    if not contagem:
        return []
    # Anos sem ninguém entram com zero: o buraco é informação — um ano sem
    # admissão que sobreviveu até hoje diz algo sobre aquele período.
    anos = range(int(min(contagem)), int(max(contagem)) + 1)
    pico = max(contagem.values())
    return [{"ano": str(a), "n": contagem.get(str(a), 0),
             "pct": round(100 * contagem.get(str(a), 0) / pico, 1)}
            for a in anos]


def retencao_por_gestor(unidades, linhas: list[dict], minimo: int = PISO_GRUPO
                        ) -> list[dict]:
    """Tempo de casa médio da equipe direta de cada gestor.

    Responde uma pergunta que nenhuma outra vista responde: onde a casa é nova.
    Uma gerência inteira abaixo de um ano é um time sem memória — pode ser
    crescimento, pode ser rotatividade, e as duas leituras pedem ação diferente.
    O indicador não decide qual é; ele diz onde olhar.
    """
    us = unidades if isinstance(unidades, dict) else {u.id: u for u in unidades}
    por_id = {l["id"]: l for l in linhas}
    equipes: dict[str, list[dict]] = {}
    for u in us.values():
        if u.parent_id and u.parent_id in us and u.id in por_id:
            equipes.setdefault(u.parent_id, []).append(por_id[u.id])

    saida = []
    for gid, gente in equipes.items():
        if len(gente) < minimo:
            continue
        r = resumo(gente)
        if r["media"] is None:
            continue
        gestor = us[gid]
        saida.append({
            "id": gid, "codigo": gestor.codigo, "nome": gestor.nome,
            "cargo": gestor.cargo, "area": gestor.area,
            "n": len(gente), "media": r["media"], "mediana": r["mediana"],
            "novatos": sum(1 for l in gente if l["faixa"] == "ate1"),
        })
    return sorted(saida, key=lambda g: (g["media"], sem_acento(g["nome"])))


def panorama(unidades, hoje: date | None = None, rotulos_nivel: dict | None = None
             ) -> dict:
    """Tudo o que a vista precisa, numa passada só sobre as unidades."""
    linhas = medir(unidades, hoje)
    vinculos = {k: r for k, (r, _cor) in dominio.VINCULOS.items()}
    return {
        "linhas": linhas,
        "resumo": resumo(linhas),
        "faixas": por_faixa(linhas),
        "por_area": por(linhas, "area"),
        "por_vinculo": por(linhas, "vinculo", vinculos),
        "por_nivel": por(linhas, "tipo", rotulos_nivel or dominio.TIPOS),
        "admissoes": admissoes_por_ano(linhas),
        "gestores": retencao_por_gestor(unidades, linhas),
    }
