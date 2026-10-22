"""
GPlanSiS|Peoples - cargos e niveis hierarquicos.

O `tipo` da unidade (diretoria, gerencia, coordenacao, celula, area, apoio) e o
nivel hierarquico. Ele nasce do cargo por regra de palavra-chave: "Gerente de
Operacoes" vira gerencia, "Estagiario" vira apoio. Enquanto essa regra viveu
dentro do importador, ela era codigo — mudar a leitura de um cargo exigia
editar Python e recarregar a base.

Aqui ela e dado, em tres camadas, da mais especifica para a mais geral:

    1. catalogo   cargo exato -> nivel        "Montador Lider" -> coordenacao
    2. regras     padrao -> nivel             "supervisor"     -> coordenacao
    3. piso       nivel padrao                                    celula

O catalogo nasce da aplicacao das regras sobre os cargos que existem na base, e
a partir da primeira edicao passa a mandar. Sao 119 cargos distintos na carga
atual — por isso a tela filtra.

A cor do nivel e um TOKEN, nao um valor: o tema escuro precisa de contrapartida
para cada cor, e deixar o operador digitar um hexadecimal furaria tanto a
paleta institucional quanto o contraste. Cada token ja vem com o par verificado.
"""
from __future__ import annotations

import re

from .dominio import sem_acento

# ---------------------------------------------------------------------------
# CORES DE NIVEL  (token -> par claro/escuro, ambos dentro da paleta)
# ---------------------------------------------------------------------------
# O valor escuro nao e o claro clareado: e a leitura invertida. Num fundo
# escuro o tom mais senior tem que ser o mais claro, senao o grafite da
# diretoria some dentro do card (1,1:1).
CORES_NIVEL = {
    "grafite":     {"rotulo": "Grafite", "claro": "#2D3336", "escuro": "#E8EAEB"},
    "laranja":     {"rotulo": "Laranja", "claro": "#EB6A20", "escuro": "#EB6A20"},
    "ambar":       {"rotulo": "Âmbar", "claro": "#F6A709", "escuro": "#F6A709"},
    "cinza":       {"rotulo": "Cinza", "claro": "#7D8286", "escuro": "#9AA0A3"},
    "cinza-claro": {"rotulo": "Cinza claro", "claro": "#B9BDBF", "escuro": "#6E7679"},
}

# codigo, rotulo, cor, ordem — o codigo casa com org.tipo_unidade (schema.sql)
NIVEIS_PADRAO = [
    ("diretoria", "Diretoria", "grafite", 10),
    ("gerencia", "Gerência", "laranja", 20),
    ("coordenacao", "Coordenação", "ambar", 30),
    # A trilha técnica, ao lado da de gestão e não abaixo dela: um especialista
    # responde por profundidade, não por gente. Fica em 35 — acima de célula,
    # porque é senioridade — e em `ambar`, a mesma faixa de coordenação, porque
    # é o degrau equivalente do outro lado. A paleta tem cinco tons para sete
    # níveis; repetir onde a senioridade é a mesma diz mais que inventar tom.
    ("especialista", "Especialista", "ambar", 35),
    ("celula", "Célula", "cinza", 40),
    ("area", "Área", "cinza", 50),
    ("apoio", "Apoio", "cinza-claro", 60),
]

NIVEL_PISO = "celula"

# Primeira regra que casa vence — por isso a ordem importa e e editavel.
REGRAS_PADRAO = [
    ("diretor|ceo|cto|cfo|clo|conselho|presidente", "diretoria", 10),
    ("gerente|gerencia", "gerencia", 20),
    ("coordenador|coordenadora|supervisor|lider", "coordenacao", 30),
    # Depois de coordenação, e não antes: quem for as duas coisas — "Supervisor
    # especialista" — é classificado pela responsabilidade sobre gente, que é a
    # que muda o desenho da árvore.
    ("especialista", "especialista", 35),
    ("estagi|aprendiz|assistente|auxiliar", "apoio", 40),
]


def nivel(codigo="", rotulo="", cor="cinza", ordem=99, ativo=True) -> dict:
    return {"codigo": codigo, "rotulo": rotulo, "cor": cor,
            "ordem": int(ordem), "ativo": bool(ativo)}


def regra(padrao="", nivel="", ordem=99, ativo=True) -> dict:
    return {"padrao": padrao, "nivel": nivel, "ordem": int(ordem),
            "ativo": bool(ativo)}


def niveis_padrao() -> list[dict]:
    return [nivel(c, r, cor, o) for c, r, cor, o in NIVEIS_PADRAO]


def regras_padrao() -> list[dict]:
    return [regra(p, n, o) for p, n, o in REGRAS_PADRAO]


def normalizar_niveis(niveis: list[dict]) -> list[dict]:
    """Sem nivel nao ha card. Lista vazia ou sem o piso volta ao padrao."""
    saida, vistos = [], set()
    for n in niveis or []:
        codigo = sem_acento(n.get("codigo", "")).strip().replace(" ", "_")[:24]
        if not codigo or codigo in vistos:
            continue
        vistos.add(codigo)
        cor = n.get("cor") if n.get("cor") in CORES_NIVEL else "cinza"
        saida.append(nivel(codigo, str(n.get("rotulo") or codigo).strip()[:40],
                           cor, n.get("ordem", 99), n.get("ativo", True)))
    if not saida or NIVEL_PISO not in vistos:
        padrao = {n["codigo"]: n for n in niveis_padrao()}
        for codigo, n in padrao.items():
            if codigo not in vistos:
                saida.append(n)
    return sorted(saida, key=lambda n: (n["ordem"], n["codigo"]))


def normalizar_regras(regras: list[dict], codigos: set[str]) -> list[dict]:
    saida = []
    for r in regras or []:
        padrao = str(r.get("padrao") or "").strip()[:120]
        if not padrao or r.get("nivel") not in codigos:
            continue
        try:
            re.compile(padrao)
        except re.error:                    # padrao invalido nao derruba a tela
            continue
        saida.append(regra(padrao, r["nivel"], r.get("ordem", 99),
                           r.get("ativo", True)))
    return sorted(saida, key=lambda r: (r["ordem"], r["padrao"]))


# ---------------------------------------------------------------------------
# CLASSIFICACAO
# ---------------------------------------------------------------------------
def por_regra(cargo: str, regras: list[dict] | None = None) -> str:
    """Nivel derivado so das regras — sem consultar o catalogo."""
    c = sem_acento(cargo)
    for r in (regras if regras is not None else regras_padrao()):
        if not r.get("ativo", True):
            continue
        try:
            if re.search(r["padrao"], c):
                return r["nivel"]
        except re.error:
            continue
    return NIVEL_PISO


def classificar(cargo: str, catalogo: dict | None = None,
                regras: list[dict] | None = None) -> str:
    """Catalogo primeiro, regra depois, piso por ultimo."""
    if catalogo:
        achado = catalogo.get(chave(cargo))
        if achado:
            return achado
    return por_regra(cargo, regras)


def chave(cargo: str) -> str:
    return sem_acento(cargo).strip()


def indexar(catalogo: list[dict]) -> dict[str, str]:
    return {chave(c["cargo"]): c["nivel"] for c in catalogo
            if c.get("cargo") and c.get("nivel")}


# ---------------------------------------------------------------------------
# CATALOGO
# ---------------------------------------------------------------------------
def descobrir(unidades, catalogo: list[dict], regras: list[dict],
              codigos: set[str]) -> list[dict]:
    """Acrescenta os cargos que a estrutura usa e o catalogo ainda nao tem.

    Nao sobrescreve mapeamento existente: o que o operador decidiu vale mais
    que a regra de palavra-chave que gerou a primeira versao.
    """
    atual = {chave(c["cargo"]): c for c in catalogo or []
             if c.get("cargo") and c.get("nivel") in codigos}
    for u in unidades.values():
        if not u.cargo:
            continue
        k = chave(u.cargo)
        if k in atual:
            continue
        atual[k] = {"cargo": u.cargo.strip(), "nivel": por_regra(u.cargo, regras),
                    "origem": "regra"}
    return sorted(atual.values(), key=lambda c: sem_acento(c["cargo"]))


def uso(unidades) -> dict[str, int]:
    contagem: dict[str, int] = {}
    for u in unidades.values():
        if u.cargo:
            contagem[chave(u.cargo)] = contagem.get(chave(u.cargo), 0) + 1
    return contagem


def aplicar(unidades, catalogo: list[dict], regras: list[dict]) -> dict:
    """Reescreve o `tipo` das unidades conforme o catalogo. Devolve o que mudou.

    E acao explicita, nao efeito colateral de salvar: reclassificar 267 pessoas
    muda a cor de todo card e a altura de faixa do desenho — quem manda isso
    precisa ter pedido.
    """
    ix = indexar(catalogo)
    mudancas = []
    for u in unidades.values():
        if not u.cargo:
            continue
        novo = classificar(u.cargo, ix, regras)
        if novo != u.tipo:
            mudancas.append({"id": u.id, "nome": u.nome, "cargo": u.cargo,
                             "de": u.tipo, "para": novo})
            u.tipo = novo
    return {"alteradas": len(mudancas), "detalhe": mudancas[:40]}


def divergencias(unidades, catalogo: list[dict], regras: list[dict]) -> list[dict]:
    """Cargos cujo nivel no catalogo nao bate com o `tipo` gravado na unidade.

    Aparece quando alguem editou o nivel de uma unidade direto no painel, ou
    quando o catalogo mudou e ninguem aplicou.
    """
    ix = indexar(catalogo)
    por_cargo: dict[str, dict] = {}
    for u in unidades.values():
        if not u.cargo:
            continue
        esperado = classificar(u.cargo, ix, regras)
        if esperado == u.tipo:
            continue
        d = por_cargo.setdefault(chave(u.cargo), {
            "cargo": u.cargo, "esperado": esperado, "atual": {}, "total": 0})
        d["atual"][u.tipo] = d["atual"].get(u.tipo, 0) + 1
        d["total"] += 1
    return sorted(por_cargo.values(), key=lambda d: -d["total"])
