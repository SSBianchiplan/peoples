"""
GPlanSiS|Peoples - dominio e motor de layout.
SPEC-GPLANSIS-ORG-001 secoes 5 (modelo), 9 (contrato de layout) e ADR-011.

Este modulo NAO importa FastAPI, nao toca disco e nao le estado global.
`calcular_layout` e pura e sincrona (FE-01), o que a torna testavel em
Python puro e garante o determinismo exigido pela RNF-02.

A inversao e projecao de indice de nivel (LAY-01). Nao existe, e nao pode
existir, transformacao de matriz sobre o SVG (LAY-02).
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict
from datetime import date
from dataclasses import dataclass, field, replace

# ---------------------------------------------------------------------------
# TOKENS DE LAYOUT  (SPEC 9.6)
# ---------------------------------------------------------------------------
CARD_W = 236          # largura fixa do card
CARD_PAD = 13         # respiro interno
GAP_H = 26            # espaco entre irmaos
GAP_V = 76            # folga vertical entre faixas; define a altura do barramento
GAP_LATERAL = 14      # respiro entre linhas da arvore indentada (orientacao lateral)
MARGEM = 40           # margem do desenho, todos os lados
TRILHO_X = 34         # faixa reservada a cota de nivel (elemento-assinatura)
ALTURA_MIN = 98       # piso do card
ALTURA_CABECALHO = 56  # faixa de titulo dentro do proprio SVG
MAX_ITENS = 6         # accountabilities visiveis antes do resumo "+ n"

# O layout é puro e síncrono (ADR-011) e não recebe request: o idioma vigente
# entra como estado de módulo, ajustado por `main` antes de calcular.
IDIOMA = "pt-BR"


def _t(texto: str, **p) -> str:
    from . import idiomas
    return idiomas.traduzir(texto, IDIOMA, **p)
MAX_SKILLS = 2        # linhas de competencias

# Campos que o motor sabe desenhar no card, e quais vem ligados. A tela de
# configuracao (configuracao.CAMPOS_CARD) rotula estes mesmos codigos — um
# teste garante que as duas listas nao derivem. O dominio nao importa a
# configuracao: ele e a camada de baixo.
# Natureza do vinculo. CLT e o padrao porque e a maioria; o que precisa
# aparecer e a excecao — quem nao e empregado tem acesso, contrato e prazo
# diferentes, e nao distinguir isso no organograma e como o acesso de um
# prestador sobrevive ao fim do contrato.
VINCULOS = {
    "clt": ("CLT", "cinza"),
    "pj": ("Prestador (PJ)", "ambar"),
    "estagio": ("Estágio", "cinza-claro"),
    "rpa": ("RPA", "laranja"),
    "consultoria": ("Consultoria externa", "laranja"),
    # A raiz e os nós que não são gente. O RH escreve "Não Aplicável" na coluna
    # de regime deles, e é melhor ter a chave do que deixar cair no padrão CLT.
    "nao_aplicavel": ("Não aplicável", "cinza-claro"),
}
VINCULO_PADRAO = "clt"

# Situação declarada pelo RH. Chave interna e rótulo, como o vínculo: o que a
# planilha traz é o rótulo ("Ativo"), o que se grava é a chave — senão a mesma
# pessoa fica "Ativo" numa carga e "ativo" na outra, e o filtro passa a ter
# duas entradas para a mesma coisa.
#
# Inativo NÃO some do organograma. Quem saiu é removido pela carga; quem está
# inativo e continua na estrutura é afastamento, licença ou desligamento em
# curso — e some do desenho seria justamente esconder o que alguém precisa ver.
STATUS = {
    "ativo": "Ativo",
    "inativo": "Inativo",
}
STATUS_PADRAO = "ativo"

CAMPOS_CARD = ("codigo", "centro_custo", "nome", "responsavel", "cargo",
               "area", "email", "vertical", "cc_negocio",
               "accountabilities", "competencias")
CAMPOS_PADRAO = frozenset(CAMPOS_CARD) - {"email", "vertical"}

# Marca do cliente no card da raiz (`marca/peoples-*.png`). O motor precisa
# da proporcao para reservar altura; o template usa a mesma conta para desenhar.
LARGURA_MARCA, ALTURA_MARCA = 2203, 397

# tipografia: largura media do glifo em px, por estilo
LARG_NOME = 7.4
LARG_CORPO = 5.6
LARG_MIUDO = 5.2


@dataclass(frozen=True)
class Tokens:
    """Geometria e conteudo do card. Configuravel sem tocar no motor."""
    card_w: int = CARD_W
    card_pad: int = CARD_PAD
    gap_h: int = GAP_H
    gap_v: int = GAP_V
    margem: int = MARGEM
    trilho_x: int = TRILHO_X
    altura_min: int = ALTURA_MIN
    max_itens: int = MAX_ITENS
    campos: frozenset = CAMPOS_PADRAO
    # Empilhamento de irmaos-folha. Uma equipe de 17 pessoas numa fileira so
    # empurra o desenho para 17 larguras de card; em pilhas de 5 ela ocupa 4.
    # `pilha_cards=0` desliga e o desenho volta a ser uma fileira.
    pilha_cards: int = 5
    pilha_minimo: int = 6          # so empilha a partir daqui: 5 em fila cabem
    pilha_gap: int = 10            # respiro entre cards da mesma pilha
    gap_lateral: int = GAP_LATERAL  # respiro entre linhas na orientacao lateral
    # A marca do cliente no card da raiz. Desligada na exportacao: o SVG solto
    # viraria quadrado vazio no Inkscape e o PDF nao desenha imagem — reservar
    # altura para o que nao vai ser desenhado deixa um bloco branco no papel.
    marca: bool = True
    # codigo do nivel -> rotulo. Vazio usa TIPOS.
    niveis: tuple = ()

    def com(self, **mudancas) -> "Tokens":
        return replace(self, **mudancas)

    def tem(self, campo: str) -> bool:
        return campo in self.campos

    def rotulo(self, nivel: str) -> str:
        return dict(self.niveis).get(nivel) or TIPOS.get(nivel, nivel)


PADRAO = Tokens()

# Rotulo e cor de nivel sao configuraveis (cargos.py / modulo Cargos e niveis).
# Estes sao os padroes, usados quando ninguem passa tokens — testes e chamada
# direta ao motor. Os codigos casam com org.tipo_unidade (schema.sql).
TIPOS = {
    "diretoria": "Diretoria",
    "gerencia": "Gerência",
    "coordenacao": "Coordenação",
    "especialista": "Especialista",
    "area": "Área",
    "celula": "Célula",
    "apoio": "Apoio",
}

# Paleta institucional (marca/paleta.png). Nenhum tom fora dela.
COR_TIPO = {
    "diretoria": "#2D3336",
    "gerencia": "#EB6A20",
    "coordenacao": "#F6A709",
    "especialista": "#F6A709",
    "area": "#7D8286",
    "celula": "#7D8286",
    "apoio": "#B9BDBF",
}


# ---------------------------------------------------------------------------
# MODELO
# ---------------------------------------------------------------------------
@dataclass
class Unidade:
    """No da estrutura.

    Na carga a partir da planilha cada no e uma posicao ocupada por uma
    pessoa: `nome` e a pessoa e `cargo` e a funcao. Na carga do seed da SPEC
    cada no e uma unidade organizacional e `responsavel` nomeia quem responde
    por ela. O card acomoda as duas leituras sem ramificar o layout.
    """
    id: str
    codigo: str
    nome: str
    tipo: str
    parent_id: str | None
    ordem: int
    responsavel: str = ""
    cargo: str = ""
    area: str = ""                 # departamento / equipe
    email: str = ""
    centro_custo: str = ""         # CC de nivel 4
    vertical: str = ""             # CC de nivel 2 (agrupador de negocio)
    vinculo: str = VINCULO_PADRAO      # clt | pj | estagio | rpa | consultoria
    # Data de admissao, ISO (AAAA-MM-DD). Texto e nao `date` porque o estado vai
    # e volta de JSON, e uma data que vira string na gravacao e objeto na leitura
    # e uma classe de bug que nao paga o que promete.
    #
    # O TEMPO DE EMPRESA NAO E GRAVADO. A planilha do RH traz a coluna, e ela
    # confere exatamente com (hoje - inicio)/365 — o que significa que e
    # derivada, e que ja nasce velha: gravada hoje, mente amanha. O sistema
    # calcula (`tempo_de_casa`) a partir desta data, que e o unico fato.
    data_inicio: str = ""
    status: str = ""               # "Ativo" e afins, como o RH declara
    responsabilidades: list[dict] = field(default_factory=list)
    competencias: list[str] = field(default_factory=list)
    # Campos organizacionais da planilha completa (bd_completo_org). Nenhum é
    # remuneração — o dinheiro (salário, custo, venda) fica FORA daqui, numa
    # tabela à parte só de Admin (LGPD-01/02). `data_nascimento` é ISO texto,
    # como `data_inicio`; a idade é derivada, não gravada.
    tipo_mo: str = ""              # Tipo M.O — vendável / não vendável
    n2: str = ""                   # nível 2 do CC (numérico)
    n4: str = ""                   # nível 4 do CC
    n5: str = ""                   # nível 5 do CC
    cc_equipe: str = ""            # código composto CC_Equipe
    bu: str = ""                   # unidade de negócio / localidade
    tipo_class: str = ""           # direto / indireto
    mo_classe: str = ""            # MO — MOI / MOD
    categoria_nivel: str = ""      # categoria de nível (GO etc.)
    genero: str = ""
    data_nascimento: str = ""      # ISO (AAAA-MM-DD); idade é derivada

    @classmethod
    def de_dict(cls, d: dict) -> "Unidade":
        """Tolerante a estados gravados por versoes anteriores."""
        campos = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in campos})


def tempo_de_casa(data_inicio: str, hoje=None) -> float | None:
    """Anos de casa, com uma casa de precisão que o RH reconhece.

    `None` quando não há data — e `None` não é zero: quem entrou hoje tem zero
    anos de casa, quem não tem data cadastrada não tem tempo de casa nenhum, e
    somar os dois na mesma média inventaria gente recém-contratada.

    A régua é a mesma que a planilha do RH usa: dias corridos sobre 365. Não é
    ano civil — 365 fixo, sem bissexto — porque é o número que o RH publica, e
    dois números diferentes para "tempo de empresa" na mesma casa é pior que um
    número aproximado.
    """
    if not data_inicio:
        return None
    try:
        inicio = date.fromisoformat(str(data_inicio)[:10])
    except ValueError:
        return None
    return ((hoje or date.today()) - inicio).days / 365.0


# As faixas do indicador. Cada uma é (chave, rótulo, piso em anos) e o piso é
# fechado embaixo e aberto em cima: quem tem 1,0 ano exato cai em "1 a 3", não
# em "até 1 ano". Os cortes são os do RH — experiência, ciclo de promoção e
# risco de saída mudam de patamar em 1, 3, 5 e 10 anos.
FAIXAS_CASA = (
    ("ate1", "Até 1 ano", 0.0),
    ("de1a3", "1 a 3 anos", 1.0),
    ("de3a5", "3 a 5 anos", 3.0),
    ("de5a10", "5 a 10 anos", 5.0),
    ("mais10", "Mais de 10 anos", 10.0),
)


def faixa_de_casa(anos: float | None) -> str:
    """A faixa de um tempo de casa. `""` quando não há data."""
    if anos is None:
        return ""
    escolhida = FAIXAS_CASA[0][0]
    for chave, _rotulo, piso in FAIXAS_CASA:
        if anos >= piso:
            escolhida = chave
    return escolhida


def sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in base if not unicodedata.combining(c)).lower()


# ---------------------------------------------------------------------------
# ARVORE
# ---------------------------------------------------------------------------
def mapa_filhos(unidades: dict[str, Unidade]) -> dict[str | None, list[Unidade]]:
    """Filhos por pai, ordenados por (ordem, nome, id) - LAY-12.

    O `id` e o desempate final: sem ele, dois irmaos com mesma ordem e mesmo
    nome trocariam de lugar entre execucoes e a RNF-02 cairia.
    """
    m: dict[str | None, list[Unidade]] = defaultdict(list)
    for u in unidades.values():
        m[u.parent_id].append(u)
    for k in m:
        m[k].sort(key=lambda x: (x.ordem, sem_acento(x.nome), x.id))
    return m


def raiz(unidades: dict[str, Unidade]) -> Unidade:
    """A unica unidade sem pai (RF-03)."""
    sem_pai = mapa_filhos(unidades)[None]
    if not sem_pai:
        raise ValueError(_t("ORG-RAIZ: organograma sem raiz"))
    return sem_pai[0]


def descendentes(unidades: dict[str, Unidade], uid: str) -> set[str]:
    m = mapa_filhos(unidades)
    acc: set[str] = set()
    pilha = [uid]
    while pilha:
        for f in m.get(pilha.pop(), []):
            if f.id not in acc:
                acc.add(f.id)
                pilha.append(f.id)
    return acc


def ancestrais(unidades: dict[str, Unidade], uid: str) -> list[Unidade]:
    """Da raiz ate o pai de `uid`, em ordem logica."""
    cadeia: list[Unidade] = []
    atual = unidades.get(uid)
    visto: set[str] = set()
    while atual is not None and atual.parent_id is not None:
        if atual.parent_id in visto:
            break
        visto.add(atual.parent_id)
        atual = unidades.get(atual.parent_id)
        if atual is not None:
            cadeia.append(atual)
    cadeia.reverse()
    return cadeia


def com_ancestrais(unidades: dict[str, Unidade], ids) -> set[str]:
    """Fecho ancestral: garante que todo achado tenha caminho ate a raiz."""
    saida = set(ids)
    for uid in list(ids):
        saida.update(a.id for a in ancestrais(unidades, uid))
    return saida


def profundidades(unidades: dict[str, Unidade]) -> dict[str, int]:
    """Profundidade logica absoluta, raiz = 0 (A11Y-02)."""
    filhos = mapa_filhos(unidades)
    prof: dict[str, int] = {}
    pilha = [(raiz(unidades), 0)]
    while pilha:
        u, d = pilha.pop()
        prof[u.id] = d
        for f in filhos.get(u.id, []):
            pilha.append((f, d + 1))
    return prof


def renumerar(unidades: dict[str, Unidade], parent_id: str | None) -> None:
    """Ordem em multiplos de 10, deixando espaco para insercao no meio."""
    for i, f in enumerate(mapa_filhos(unidades).get(parent_id, [])):
        f.ordem = (i + 1) * 10


# ---------------------------------------------------------------------------
# FILTROS
# ---------------------------------------------------------------------------
CRITERIOS = ("vertical", "vertical_negocio", "tipo_cc", "area", "tipo",
             "cargo", "centro_custo", "gestor", "vinculo")
# Vem do cadastro de centros de custo (centros.py), nao da propria unidade.
DERIVADOS = ("vertical_negocio", "tipo_cc", "n5")


def valor_de(u: Unidade, campo: str, extras: dict | None) -> str:
    """Atributo da unidade, ou dado resolvido pelo cadastro de CC."""
    if campo in DERIVADOS:
        return ((extras or {}).get(u.id) or {}).get(campo, "")
    return getattr(u, campo, "")


def valores_de_filtro(unidades: dict[str, Unidade],
                      extras: dict | None = None,
                      criterios: dict | None = None) -> dict[str, list[tuple]]:
    """Dominio de cada filtro como pares (valor, rotulo), tirado do dado.

    Nunca lista fixa: CC que nao existe nao aparece, CC novo aparece sozinho.

    Com `criterios`, os filtros se filtram: cada chip oferece so o que ainda
    existe **depois do recorte que os outros ja fizeram**. Escolhida a vertical
    ENG, `Departamento` deixa de listar os 61 departamentos da empresa e passa a
    listar os de ENG — as demais opcoes davam zero resultado, e opcao que sempre
    devolve vazio nao e escolha, e armadilha.

    Cada chip ve o recorte dos OUTROS, nunca o seu proprio: filtrado por si
    mesmo, um chip com uma marca perderia todas as demais opcoes e ninguem
    conseguiria marcar a segunda. E o que ja esta marcado sobrevive sempre, mesmo
    quando a combinacao nao devolve ninguem — senao a marca sumiria da lista e
    nao haveria como desmarca-la.
    """
    espelho = lambda vs: [(v, v) for v in vs]                    # noqa: E731

    ativos = {k: set(v) for k, v in (criterios or {}).items()
              if k in CRITERIOS and v}

    def base_de(campo: str):
        """As unidades que sobram quando todos os outros criterios valem.

        Devolve a vista do dicionario quando nao ha o que recortar, em vez de
        uma copia: quem chama so percorre, e sem filtro nenhum esta funcao e
        chamada nove vezes por render — nove listas de 267 itens montadas para
        serem lidas uma vez e jogadas fora.
        """
        if criterios is None:
            return unidades.values()
        achados = filtrar(unidades, {**criterios, campo: []}, extras)
        if achados is None:
            return unidades.values()
        return [unidades[i] for i in achados if i in unidades]

    def sobrevive(campo: str, valores: list[tuple], rotulo=None) -> list[tuple]:
        # `rotulo` existe por causa do gestor: nele o valor e um id em hexa, e
        # devolver `(id, id)` poria o hexa cru na tela onde devia estar o nome.
        marcados = ativos.get(campo, set())
        vistos = {v for v, _ in valores}
        faltando = [v for v in sorted(marcados - vistos) if v]
        nomear = rotulo or (lambda v: v)
        return valores + [(v, nomear(v)) for v in faltando]

    def derivado(campo):
        return espelho(sorted({valor_de(u, campo, extras)
                               for u in base_de(campo)
                               if valor_de(u, campo, extras)}))

    # Deferido pelo mesmo motivo de `_t`: `centros` importa daqui, e o ciclo so
    # nao se fecha porque o import acontece na chamada.
    from . import centros  # A grafia certa do departamento vale no rotulo, nunca no valor: o valor e
    # o que casa com `u.area`, e corrigi-lo faria o filtro deixar de achar
    # justamente quem tem o nome errado. Mesma regra de estrutura.rotulo_pt —
    # estado gravado antes da correcao nao pode trazer "Pulp & Papper" de volta
    # para a tela so porque o dado e antigo.
    limpo = lambda a: centros.corrigir_departamento(a)            # noqa: E731

    # "83.42" so diz alguma coisa a quem decorou os 78 codigos; o codigo e o
    # nome da equipe precisam viajar juntos. O nome sai da propria pessoa
    # (`area`) — o mesmo que o chip Departamento lista, e o unico jeito de os
    # dois chips concordarem. Nao vem de `extras`: ao casar so pelo N3, o
    # cadastro devolve o nome de uma equipe irma, e o rotulo mentiria.
    # O nome da equipe sai de toda a base, e nao do recorte: o rotulo de 83.42 e
    # "Software Team" independentemente de quem o filtro deixou de pe. Recortar
    # aqui faria o mesmo codigo trocar de nome conforme o filtro vigente.
    departamentos: dict[str, set[str]] = {}
    for u in unidades.values():
        if u.centro_custo:
            departamentos.setdefault(u.centro_custo, set()).add(limpo(u.area))

    def rotulo_cc(cc: str) -> str:
        # Um N4 pode abrigar mais de um departamento (81.11 tem dois). Aparecem
        # todos: mostrar so um seria prometer um recorte menor do que o filtro
        # de fato aplica.
        nomes = sorted((n for n in departamentos.get(cc, ()) if n), key=sem_acento)
        return f"{cc} · {', '.join(nomes)}" if nomes else cc

    filhos = mapa_filhos(unidades)
    gestores = sorted((u for u in base_de("gestor") if filhos.get(u.id)),
                      key=lambda u: sem_acento(u.nome))
    # Uma chamada, guardada — e nao uma por chave do enum. O `any()` abaixo
    # continua curto-circuitando na primeira pessoa que casa; o que se paga uma
    # vez e a montagem da base, que e uma passada de `filtrar` sobre tudo.
    base_tipo = base_de("tipo")
    base_vinculo = base_de("vinculo")

    return {
        "vertical": sobrevive("vertical", espelho(sorted(
            {u.vertical for u in base_de("vertical") if u.vertical}))),
        "vertical_negocio": sobrevive("vertical_negocio", derivado("vertical_negocio")),
        "tipo_cc": sobrevive("tipo_cc", derivado("tipo_cc")),
        "area": sobrevive("area", [
            (a, limpo(a)) for a in
            sorted({u.area for u in base_de("area") if u.area}, key=sem_acento)]),
        "centro_custo": sobrevive("centro_custo", [
            (cc, rotulo_cc(cc)) for cc in
            sorted({u.centro_custo for u in base_de("centro_custo")
                    if u.centro_custo})]),
        "cargo": sobrevive("cargo", espelho(sorted(
            {u.cargo for u in base_de("cargo") if u.cargo}, key=sem_acento))),
        # `base_de` sai de dentro do `any()`: la dentro ele era reavaliado uma
        # vez por chave do enum, e cada avaliacao e uma passada de `filtrar`
        # sobre a base inteira. Eram nove varreduras a mais por render — seis
        # aqui, tres no vinculo — em cima das sete que os criterios pedem.
        "tipo": sobrevive("tipo", [
            (k, r) for k, r in TIPOS.items()
            if any(u.tipo == k for u in base_tipo)]),
        # O chip de vinculo existia na barra sem dominio nenhum: abria vazio e
        # nao filtrava nada. Como os demais, ele sai do dado — so aparece o
        # vinculo que alguem de fato tem, e `consultoria` surge sozinho no dia
        # em que a primeira pessoa for cadastrada assim.
        "vinculo": sobrevive("vinculo", [
            (k, rotulo) for k, (rotulo, _cor) in VINCULOS.items()
            if any(u.vinculo == k for u in base_vinculo)]),
        # O gestor tambem sobrevive ao proprio recorte. Era o unico chip de
        # fora: marcado o gestor Fulano e depois uma vertical a que ele nao
        # pertence, ele sumia da propria lista e nao havia mais como desmarca-lo
        # — o beco sem saida que `sobrevive` foi escrito para evitar. So a
        # limpeza geral destravava.
        "gestor": sobrevive("gestor", [(u.id, u.nome) for u in gestores],
                            lambda i: unidades[i].nome if i in unidades else i),
    }


def casa_texto(u: Unidade, termo: str, extras: dict | None = None) -> bool:
    campos = [u.nome, u.cargo, u.area, u.email, u.codigo, u.centro_custo,
              u.vertical, u.responsavel, " ".join(u.competencias),
              " ".join(r.get("descricao", "") for r in u.responsabilidades),
              *(valor_de(u, c, extras) for c in DERIVADOS)]
    return termo in sem_acento(" ".join(campos))


def filtrar(unidades: dict[str, Unidade], criterios: dict,
            extras: dict | None = None) -> set[str] | None:
    """ids que satisfazem TODOS os critérios ativos. None = sem filtro.

    `gestor` é hierárquico: casa a própria unidade e toda a sua subárvore —
    é assim que se lê "quem responde ao fulano". Vertical de negócio e natureza
    vêm do cadastro de CC, por isso passam por `extras`.
    """
    ativos = {k: set(v) for k, v in criterios.items()
              if k in CRITERIOS and v}
    texto = sem_acento(str(criterios.get("texto", "")).strip())
    if len(texto) < 2:
        texto = ""
    if not ativos and not texto:
        return None

    sob_gestor: set[str] | None = None
    if "gestor" in ativos:
        sob_gestor = set()
        for gid in ativos.pop("gestor"):
            if gid in unidades:
                sob_gestor |= {gid} | descendentes(unidades, gid)

    saida = set()
    for uid, u in unidades.items():
        if sob_gestor is not None and uid not in sob_gestor:
            continue
        if any(valor_de(u, campo, extras) not in valores
               for campo, valores in ativos.items()):
            continue
        if texto and not casa_texto(u, texto, extras):
            continue
        saida.add(uid)
    return saida


# ---------------------------------------------------------------------------
# TEXTO
# ---------------------------------------------------------------------------
def quebrar(texto: str, largura_px: float, larg_glifo: float,
            max_linhas: int) -> list[str]:
    """Quebra por palavra dentro de `largura_px`; corte sinalizado por reticencia."""
    texto = " ".join(str(texto or "").split())
    if not texto:
        return []
    max_chars = max(4, int(largura_px / larg_glifo))
    palavras = texto.split(" ")
    linhas: list[str] = []
    atual = ""
    i = 0
    while i < len(palavras) and len(linhas) < max_linhas:
        tentativa = f"{atual} {palavras[i]}".strip()
        if len(tentativa) <= max_chars:
            atual = tentativa
            i += 1
        elif atual:
            linhas.append(atual)
            atual = ""
        else:                                   # palavra unica maior que a linha
            linhas.append(palavras[i][: max_chars - 1] + "…")
            i += 1
    if atual and len(linhas) < max_linhas:
        linhas.append(atual)
        i = len(palavras)
    if i < len(palavras) and linhas:            # sobrou texto: marca o corte
        ult = linhas[-1]
        linhas[-1] = (ult[: max_chars - 1].rstrip() if len(ult) >= max_chars - 1
                      else ult) + "…"
    return linhas


# ---------------------------------------------------------------------------
# CARD
# ---------------------------------------------------------------------------
def montar_card(u: Unidade, x: float, y: float, tk: Tokens = PADRAO,
                cc: dict | None = None) -> tuple[dict, float]:
    """Monta o card em coordenadas absolutas e devolve (card, altura).

    Chamado duas vezes por no: uma para medir (em 0,0) e outra para posicionar.
    A altura depende so do conteudo e dos tokens, nunca da orientacao - e por
    isso que alternar orientacao nao remonta o DOM (W5-C7).
    """
    util = tk.card_w - 2 * tk.card_pad
    px = x + tk.card_pad
    cur = y + 17
    textos: list[dict] = []

    def linha(txt: str, cls: str, larg: float, maximo: int, avanco: float,
              recuo: float = 0.0) -> None:
        nonlocal cur
        for ln in quebrar(txt, util - recuo, larg, maximo):
            textos.append({"x": px + recuo, "y": cur, "cls": cls, "txt": ln})
            cur += avanco

    cc = cc or {}
    # N5 igual a vertical (DIR/DIR, RH/RH) nao merece a repeticao.
    partes = dict.fromkeys(p for p in (cc.get("n5"), cc.get("vertical_negocio")) if p)
    negocio = "  ·  ".join(partes)
    cabecalho = " ".join(p for p in (
        u.codigo if tk.tem("codigo") else "",
        f"  {u.centro_custo}" if tk.tem("centro_custo") and u.centro_custo else "",
        f"  ·  {u.vertical}" if tk.tem("vertical") and u.vertical else "",
        f"  ·  {negocio}" if tk.tem("cc_negocio") and negocio else "") if p)
    if cabecalho:
        textos.append({"x": px, "y": cur, "cls": "t-cod", "txt": cabecalho})
        cur += 17

    linha(u.nome, "t-nome", LARG_NOME, 2, 16)
    if tk.tem("responsavel"):
        linha(u.responsavel, "t-pes", LARG_CORPO, 1, 14)
    if tk.tem("cargo"):
        linha(u.cargo, "t-cargo", LARG_CORPO, 2, 13.5)
    if tk.tem("area"):
        linha(u.area, "t-area", LARG_MIUDO, 1, 13)
    if tk.tem("email"):
        linha(u.email, "t-mail", LARG_MIUDO, 1, 13)

    regua = cur - 5
    cur += 11

    itens: list[dict] = []
    if tk.tem("accountabilities"):
        visiveis = u.responsabilidades[:tk.max_itens]
        for r in visiveis:
            delegada = r.get("origem") == "delegada"
            for k, ln in enumerate(quebrar(r.get("descricao", ""),
                                           util - 11, LARG_CORPO, 1)):
                itens.append({
                    "x": px + 11, "y": cur,
                    "mx": px + 3 if k == 0 else None, "my": cur - 3.4,
                    "txt": ln, "delegada": delegada,
                })
                cur += 15
        resto = len(u.responsabilidades) - len(visiveis)
        if resto > 0:
            itens.append({"x": px + 11, "y": cur, "mx": None, "my": None,
                          "txt": _t("+ {n} accountabilities", n=resto),
                          "delegada": False})
            cur += 15

    skills: list[dict] = []
    regua2 = None
    if tk.tem("competencias") and u.competencias:
        regua2 = cur - 6
        cur += 11
        for ln in quebrar("  ·  ".join(u.competencias), util, LARG_MIUDO, MAX_SKILLS):
            skills.append({"x": px, "y": cur, "txt": ln})
            cur += 13

    # A raiz leva a marca do cliente no pe do card (MRK-02): a altura precisa
    # abrir espaco para ela aqui, porque e este numero que o motor usa para
    # empilhar as faixas. Reservar no template faria a imagem vazar o card.
    #
    # O `y` sai daqui, do mesmo `cur` que reserva — e nao de `regua`, como saia
    # antes. Ancorado na regua, o desenho caia no topo do card enquanto o espaco
    # ficava sobrando no rodape: com a raiz vazia sobravam 29 px mortos, e uma
    # accountability na raiz bastava para a marca ser pintada por cima do texto.
    # Uma conta so para o mesmo retangulo.
    #
    # `tk.marca` desliga a reserva onde a imagem nao vai ser desenhada: o SVG
    # solto viraria quadrado vazio no Inkscape e o PDF nao tem imagem, e reservar
    # 55 px que ninguem preenche deixava o card mais visivel do papel com um
    # bloco branco no pe.
    e_raiz = u.parent_id is None and tk.marca
    marca = None
    if e_raiz:
        # Inteiro de proposito: altura fracionaria fazia `y + h` e `ancora_pai`
        # arredondarem para lados diferentes, e o conector da raiz descolava do
        # card por um centesimo.
        marca_w = tk.card_w - 40
        marca_h = round(marca_w * ALTURA_MARCA / LARGURA_MARCA)
        cur += 14
        marca = {"x": x + 20, "y": cur, "w": marca_w, "h": marca_h}
        cur += marca_h + 6

    altura = max(cur - y + tk.card_pad - 6, tk.altura_min)
    card = {
        "id": u.id, "codigo": u.codigo, "nome": u.nome, "tipo": u.tipo,
        "rotulo_tipo": tk.rotulo(u.tipo),
        "cor": COR_TIPO.get(u.tipo, "#7D8286"),      # literal, usado pelo PDF
        "x": x, "y": y, "w": tk.card_w, "h": altura, "cx": x + tk.card_w / 2,
        "regua": regua, "regua2": regua2,
        "textos": textos, "itens": itens, "skills": skills,
        # `raiz` continua sendo "este e o no de cima", e nao "este leva a
        # marca": e ele que pinta o card de grafite, na tela e no papel.
        "raiz": u.parent_id is None,
        # Geometria da marca: o template desenha exatamente o que o motor
        # reservou — duas contas para o mesmo retangulo divergiriam.
        "marca": marca,
        # dados para o tooltip do cliente — sem round-trip por hover
        "dica": {"nome": u.nome, "cargo": u.cargo, "area": u.area,
                 "email": u.email, "vertical": u.vertical,
                 "cc": "  ·  ".join(p for p in (u.centro_custo, negocio) if p),
                 "tipo": tk.rotulo(u.tipo), "codigo": u.codigo,
                 "responsavel": u.responsavel,
                 "itens": [(r.get("descricao", ""), r.get("origem") == "delegada")
                           for r in u.responsabilidades],
                 "skills": list(u.competencias)},
    }
    return card, altura


def _a2(v: float) -> float:
    """LAY-13 - toda coordenada emitida sai com 2 casas."""
    return round(v + 0.0, 2)


def _tick(trilho: float, marca: float, lateral: bool) -> dict:
    """O risquinho que fecha a faixa de um nivel, cruzando o trilho."""
    if lateral:
        return {"x1": _a2(marca), "y1": _a2(trilho - 4),
                "x2": _a2(marca), "y2": _a2(trilho + 4)}
    return {"x1": _a2(trilho - 4), "y1": _a2(marca),
            "x2": _a2(trilho + 4), "y2": _a2(marca)}


def _arredondar_card(card: dict) -> dict:
    for k in ("x", "y", "w", "h", "cx", "cy", "regua", "regua2"):
        if card.get(k) is not None:
            card[k] = _a2(card[k])
    # A marca sai do `x` ja arredondado, e nao do bruto: derivada do valor cheio,
    # ela emitia um `x` com mais casas do que o card e deixava de casar com a
    # borda que a contem (LAY-13).
    if card.get("marca"):
        card["marca"]["x"] = _a2(card["x"] + 20)
        card["marca"]["y"] = _a2(card["marca"]["y"])
    for t in card["textos"]:
        t["x"], t["y"] = _a2(t["x"]), _a2(t["y"])
    for i in card["itens"]:
        i["x"], i["y"] = _a2(i["x"]), _a2(i["y"])
        if i["mx"] is not None:
            i["mx"], i["my"] = _a2(i["mx"]), _a2(i["my"])
    for s in card["skills"]:
        s["x"], s["y"] = _a2(s["x"]), _a2(s["y"])
    return card


# ---------------------------------------------------------------------------
# MOTOR DE LAYOUT  (SPEC 9 - normativo)
# ---------------------------------------------------------------------------
def calcular_layout(unidades: dict[str, Unidade],
                    orientacao: str = "invertida",
                    selecionado: str | None = None,
                    colapsados: frozenset[str] | set[str] = frozenset(),
                    foco: str | None = None,
                    destaque: frozenset[str] | set[str] = frozenset(),
                    cabecalho: dict | None = None,
                    tokens: Tokens = PADRAO,
                    restritos: set[str] | None = None,
                    extras: dict[str, dict] | None = None,
                    chave_bloco=None) -> dict:
    """Arvore logica -> geometria. Unico produtor de coordenadas do sistema.

    Fase 1: espaco canonico, orientacao-agnostico (eixo transversal + profundidade).
    Fase 2: projecao do indice de nivel no eixo Y conforme a orientacao.

    A orientacao `lateral` troca os eixos: a profundidade anda para a direita e
    a leitura desce na ordem do documento — uma arvore indentada, como a de um
    explorador de arquivos. Ela nao distribui eixo transversal nenhum, entao
    nao passa pela fase 1b: a largura vira (D+1) colunas em vez das 32 000 px
    que 267 pessoas ocupam em piramide, e o desenho passa a caber num celular.

    `restritos` limita o desenho a um conjunto de nos (filtro); os que estao
    la so para sustentar o caminho ate um achado saem marcados como passagem.
    `extras` traz, por unidade, o que o cadastro de centros de custo resolveu
    (vertical de negocio, N5, natureza) — dado que nao mora na unidade.
    `cabecalho` reserva uma faixa no topo: ele pertence ao SVG, nao ao chrome
    da pagina, para que a mesma serializacao va a tela e ao arquivo (INT-07).

    `chave_bloco` diz o que faz duas folhas irmas pertencerem ao mesmo bloco
    empilhado. O padrao e o departamento, que e a resposta certa quando cada no
    e uma pessoa. Quem desenha nos DERIVADOS passa a sua — no modo por equipe
    cada no ja E um time, e `area` la carrega o efetivo ("12 pessoa(s)"), entao
    o padrao empilharia os times por numero de pessoas, que nao quer dizer nada.
    O motor continua sem saber que equipe existe (ADR-011): quem sabe e quem
    chama.
    """
    tk = tokens
    chave_bloco = chave_bloco or (lambda u: sem_acento(u.area))
    invertida = orientacao == "invertida"
    lateral = orientacao == "lateral"
    filhos = mapa_filhos(unidades)
    prof_abs = profundidades(unidades)
    base = unidades.get(foco) if foco else None
    if base is None:
        base = raiz(unidades)
    d0 = prof_abs.get(base.id, 0)

    def visiveis_de(u: Unidade) -> list[Unidade]:
        fs = filhos.get(u.id, [])
        if restritos is not None:
            fs = [f for f in fs if f.id in restritos]
        return fs

    # ---- fase 1a: profundidade relativa, altura e nos ocultos ---------------
    prof: dict[str, int] = {}
    alt: dict[str, float] = {}
    ocultos: dict[str, int] = {}
    ordem_dom: list[Unidade] = []

    ex = extras or {}

    def medir(u: Unidade, d: int) -> None:
        prof[u.id] = d
        _, h = montar_card(u, 0, 0, tk, ex.get(u.id))
        alt[u.id] = h
        ordem_dom.append(u)                       # pre-ordem = ordem logica (FE-03)
        netos = visiveis_de(u)
        if u.id in colapsados and netos:
            desc = descendentes(unidades, u.id)
            if restritos is not None:
                desc &= restritos
            ocultos[u.id] = len(desc)
            return
        for f in netos:
            medir(f, d + 1)

    medir(base, 0)
    D = max(prof.values())

    # ---- fase 1b: eixo transversal -----------------------------------------
    # Folhas ocupam posicoes sequenciais; pais sao centralizados sobre os filhos.
    # Subarvores ocupam intervalos disjuntos em X, logo nao ha colisao.
    px: dict[str, float] = {}
    cursor = 0.0
    # uid -> posicao na pilha (0 = mais perto do pai); e o pai de cada pilha.
    degrau: dict[str, int] = {}
    pais_com_pilha: set[str] = set()

    def e_folha(u: Unidade) -> bool:
        """Folha de verdade: nao chefia ninguem no recorte atual.

        Um no **dobrado** ocupa uma coluna e nada abaixo dela, mas nao entra
        aqui: ele e um gestor com equipe atras do `+n`, e a fileira e o que
        mostra a largura daquele nivel — quantas frentes a empresa tem ali.
        Empilhar gerencia esconde justamente a leitura que aquele nivel existe
        para dar. Quem empilha e o nivel de quem executa.
        """
        return not visiveis_de(u)

    def por_departamento(fs: list[Unidade]) -> list[tuple[str, list[Unidade]]]:
        """Irmaos agrupados por time, na ordem em que a arvore os apresenta.

        A ordem dos times e a da primeira aparicao, e nao a alfabetica: assim o
        bloco segue a hierarquia que `mapa_filhos` ja decidiu (ordem, nome, id),
        e o desenho nao se reorganiza sozinho quando alguem renomeia um time.
        Sem acento e sem caixa na chave padrao, como no resto do sistema —
        `Producao` e `Produção` sao o mesmo time. Quem desenha no derivado
        troca a chave por `chave_bloco`.
        """
        grupos: dict[str, list[Unidade]] = {}
        for f in fs:
            grupos.setdefault(chave_bloco(f), []).append(f)
        return list(grupos.items())

    def dispor_pilha(folhas: list[Unidade]) -> list[float]:
        """Posiciona as folhas em colunas por time. Devolve os x usados."""
        nonlocal cursor
        inicio = cursor
        passo = tk.card_w + tk.gap_h
        coluna = 0
        usados: list[float] = []
        for _, membros in por_departamento(folhas):
            # Cada time comeca coluna propria: uma coluna que mistura
            # Infrastructure com Cybersecurity nao responde "quem faz o que",
            # que e a pergunta que o empilhamento tinha acabado de tornar
            # legivel. Time maior que a pilha transborda para a coluna
            # seguinte, e continua sendo o mesmo bloco.
            for i, f in enumerate(membros):
                salto, linha = divmod(i, tk.pilha_cards)
                x = inicio + (coluna + salto) * passo
                px[f.id] = x
                degrau[f.id] = linha
                usados.append(x)
            coluna += -(-len(membros) // tk.pilha_cards)      # divisao p/ cima
        cursor = inicio + coluna * passo
        return usados

    def passo_x(u: Unidade) -> float:
        nonlocal cursor
        fs = [] if u.id in colapsados else visiveis_de(u)
        if not fs:
            x = cursor
            cursor += tk.card_w + tk.gap_h
            px[u.id] = x
            return x

        # Familia mista tambem empilha: contam as folhas, nao o total. Antes,
        # um unico irmao com equipe deixava outras oito folhas esticadas numa
        # fileira — a regra era "so grupos puros", e ela punia justamente o
        # caso mais comum de gerente que acumula time e reportes diretos.
        folhas = [f for f in fs if e_folha(f)]
        if tk.pilha_cards >= 2 and len(folhas) >= tk.pilha_minimo:
            xs: list[float] = []
            pilha_posta = False
            for f in fs:
                if e_folha(f):
                    # A pilha inteira ocupa o lugar da primeira folha: assim ela
                    # cai onde a ordem da arvore ja a colocaria, em vez de ser
                    # jogada para uma das pontas.
                    if not pilha_posta:
                        xs.extend(dispor_pilha(folhas))
                        pilha_posta = True
                else:
                    xs.append(passo_x(f))
            pais_com_pilha.add(u.id)
        else:
            xs = [passo_x(f) for f in fs]
        x = (min(xs) + max(xs)) / 2
        px[u.id] = x
        return x

    # A arvore indentada nao tem eixo transversal a distribuir: a ordem do
    # documento ja e a ordem da tela. `px`, `degrau` e `pais_com_pilha` ficam
    # vazios, e com eles todo o empilhamento — que existe para estreitar um
    # desenho que aqui ja nasce estreito.
    if not lateral:
        passo_x(base)

    # Recuo de cada card dentro da faixa do seu nivel: a pilha cresce para longe
    # do pai, e a faixa engorda para caber. Assim a cota continua sendo uma por
    # nivel — nenhum card muda de faixa por estar empilhado.
    recuo: dict[str, float] = {}
    for pai in pais_com_pilha:
        irmaos = visiveis_de(unidades[pai]) if pai in unidades else []
        # So a altura dos empilhados: numa familia mista o irmao que tem equipe
        # costuma ter card mais alto, e medir por ele abriria buracos entre os
        # degraus da pilha.
        na_pilha = [f for f in irmaos if f.id in degrau]
        if not na_pilha:
            continue
        h = max((alt[f.id] for f in na_pilha if f.id in alt), default=0.0)
        for f in na_pilha:
            recuo[f.id] = degrau[f.id] * (h + tk.pilha_gap)

    # ---- fase 2: projecao (SPEC 9.1) ---------------------------------------
    alt_prof: dict[int, float] = defaultdict(float)
    for uid, d in prof.items():
        alt_prof[d] = max(alt_prof[d], alt[uid] + recuo.get(uid, 0.0))

    # linha visual 0 = topo da tela. invertida: nivel logico D vira linha 0.
    alt_linha = {(D - d if invertida else d): h for d, h in alt_prof.items()}
    y_linha: dict[int, float] = {}
    topo = ALTURA_CABECALHO if cabecalho else 0
    acumulado = float(tk.margem + topo)
    for linha_i in range(D + 1):
        y_linha[linha_i] = acumulado
        acumulado += alt_linha[linha_i] + tk.gap_v
    altura_total = acumulado - tk.gap_v + tk.margem

    # Na lateral a cota deixa de ser trilho a esquerda e vira regua no topo:
    # os niveis viraram colunas. A reserva troca de eixo junto.
    coluna = tk.card_w + tk.gap_h
    esq = tk.margem + (0 if lateral else tk.trilho_x)
    alto = tk.margem + topo + (tk.trilho_x if lateral else 0)
    if lateral:
        y_fluxo: dict[str, float] = {}
        corrente = float(alto)
        for u in ordem_dom:
            y_fluxo[u.id] = corrente
            corrente += alt[u.id] + tk.gap_lateral
        altura_total = corrente - tk.gap_lateral + tk.margem

    # ---- cards --------------------------------------------------------------
    nos: list[dict] = []
    indice: dict[str, dict] = {}
    filtrando = restritos is not None
    for u in ordem_dom:
        d = prof[u.id]
        if lateral:
            x, y = esq + d * coluna, y_fluxo[u.id]
        else:
            linha_i = (D - d) if invertida else d
            # invertida encosta o card na base da faixa; vertical, no topo.
            # Assim a aresta que aponta para os filhos fica sempre alinhada.
            # O recuo afasta o card do pai dentro da propria faixa — e o que empilha.
            rec = recuo.get(u.id, 0.0)
            x = px[u.id] + esq
            y = y_linha[linha_i] + (alt_linha[linha_i] - rec - alt[u.id]
                                    if invertida else rec)
        card, _ = montar_card(u, x, y, tk, ex.get(u.id))
        card["nivel"] = d0 + d                       # nivel logico absoluto
        card["sel"] = u.id == selecionado
        card["achou"] = u.id in destaque
        card["passagem"] = filtrando and u.id not in destaque
        card["n_filhos"] = len(visiveis_de(u))
        card["ocultos"] = ocultos.get(u.id, 0)
        # As ancoras vivem no eixo da profundidade: Y nas piramides, X na
        # lateral. Sao a face por onde o fio sai do pai e entra no filho.
        card["cy"] = card["y"] + card["h"] / 2
        if lateral:
            card["ancora_pai"] = card["x"] + card["w"]
            card["ancora_filho"] = card["x"]
        else:
            card["ancora_pai"] = card["y"] if invertida else card["y"] + card["h"]
            card["ancora_filho"] = card["y"] + card["h"] if invertida else card["y"]
        nos.append(_arredondar_card(card))
        indice[u.id] = card

    # ---- conectores (SPEC 9.3) ---------------------------------------------
    sinal = -1 if invertida else 1
    conectores: list[dict] = []
    for u in ordem_dom:
        fs = [] if u.id in colapsados else visiveis_de(u)
        fs = [f for f in fs if f.id in indice]
        if not fs:
            continue
        p = indice[u.id]
        if lateral:
            # Cotovelo, e nao diagonal: o barramento desce pela calha entre a
            # coluna do pai e a dos filhos — uma faixa de `gap_h` de largura em
            # que nenhum card jamais cai, porque as colunas sao fixas. Por isso
            # ele pode ser um segmento unico (LAY-05) atravessando a subarvore
            # inteira sem cruzar caixa nenhuma.
            #
            # Filho unico tambem ganha cotovelo: numa arvore indentada o fio
            # inclinado seria a unica linha torta do desenho.
            calha = p["x"] + tk.card_w + tk.gap_h / 2
            d = (f"M {_a2(p['ancora_pai'])} {_a2(p['cy'])} "
                 f"L {_a2(calha)} {_a2(p['cy'])} "
                 f"M {_a2(calha)} {_a2(p['cy'])} "
                 f"L {_a2(calha)} {_a2(max(indice[f.id]['cy'] for f in fs))}")
            for f in fs:
                c = indice[f.id]
                d += (f" M {_a2(calha)} {_a2(c['cy'])} "
                      f"L {_a2(c['ancora_filho'])} {_a2(c['cy'])}")
            conectores.append({"pai": u.id, "d": d})
            continue
        if len(fs) == 1:                                          # LAY-06
            f = indice[fs[0].id]
            conectores.append({"pai": u.id, "d":
                f"M {_a2(p['cx'])} {_a2(p['ancora_pai'])} "
                f"L {_a2(f['cx'])} {_a2(f['ancora_filho'])}"})
            continue
        y_bus = p["ancora_pai"] + sinal * (tk.gap_v / 2)
        cxs = [indice[f.id]["cx"] for f in fs]
        d = (f"M {_a2(p['cx'])} {_a2(p['ancora_pai'])} "
             f"L {_a2(p['cx'])} {_a2(y_bus)} "
             f"M {_a2(min(cxs))} {_a2(y_bus)} L {_a2(max(cxs))} {_a2(y_bus)}")  # LAY-05
        if u.id in pais_com_pilha:
            # Uma coluna empilhada ganha um trilho so, do barramento ate o card
            # mais distante. Um fio por card cruzaria os de baixo; o trilho passa
            # atras deles, porque LAY-09 desenha conector antes de card — e o que
            # se ve entre um card e o seguinte e o segmento que sobra.
            for cx in sorted({indice[f.id]["cx"] for f in fs}):
                pontas = [indice[f.id]["ancora_filho"] for f in fs
                          if indice[f.id]["cx"] == cx]
                fim = min(pontas) if invertida else max(pontas)
                d += f" M {_a2(cx)} {_a2(y_bus)} L {_a2(cx)} {_a2(fim)}"
        else:
            for f in fs:
                c = indice[f.id]
                d += (f" M {_a2(c['cx'])} {_a2(y_bus)} "
                      f"L {_a2(c['cx'])} {_a2(c['ancora_filho'])}")
        conectores.append({"pai": u.id, "d": d})

    # ---- alcas de colapso ---------------------------------------------------
    # Ficam fora do <g> do card: aninhar dois alvos htmx no mesmo clique
    # dispararia as duas requisicoes.
    alcas: list[dict] = []
    for u in ordem_dom:
        c = indice[u.id]
        if not c["n_filhos"]:
            continue
        aberto = u.id not in colapsados
        # A alca fica sempre na face por onde o fio sai: no topo (ou na base)
        # do card nas piramides, na aresta direita na lateral. Assim ela cai
        # onde a pessoa ja esta olhando para seguir a linha.
        eixo_x, eixo_y = ((c["ancora_pai"], c["cy"]) if lateral
                          else (c["cx"], c["ancora_pai"]))
        alcas.append({
            "id": u.id, "x": _a2(eixo_x - 26), "y": _a2(eixo_y - 9),
            "tx": _a2(eixo_x), "ty": _a2(eixo_y + 4),
            "txt": ("−" if aberto else f"+{c['ocultos']}"),
            "aberto": aberto,
            "rotulo": _t("Colapsar subordinados de {nome}", nome=u.nome)
                      if aberto
                      else _t("Expandir subordinados de {nome}", nome=u.nome),
        })

    # ---- cota de nivel (elemento-assinatura, SIG-01..03) --------------------
    # A cota mede a faixa de cada nivel. Nas piramides a faixa e horizontal e o
    # trilho corre a esquerda; na lateral os niveis viraram colunas, a faixa e
    # vertical e o trilho corre no topo. `ini`/`fim`/`meio` sao a faixa no eixo
    # que for — e as coordenadas ja saem prontas daqui, porque quem produz
    # geometria neste sistema e o motor, nao o template nem o gerador de PDF
    # (ADR-011). Sem isso os dois teriam de repetir a mesma regra de eixo.
    cotas = []
    trilho = (alto - 20) if lateral else _a2(tk.margem + tk.trilho_x - 20)
    for d in range(D + 1):
        if lateral:
            ini = float(esq + d * coluna)
            fim = ini + tk.card_w
        else:
            linha_i = (D - d) if invertida else d
            ini = float(y_linha[linha_i])
            fim = ini + alt_linha[linha_i]
        meio = (ini + fim) / 2
        # `e_base`, e nao `base`: `base` ja e o no que ancora o desenho, e
        # reaproveitar o nome aqui o trocava por um booleano.
        e_base = (d0 + d) == 0
        cotas.append({
            "ini": _a2(ini), "fim": _a2(fim), "meio": _a2(meio),
            "rotulo": f"N{d0 + d}", "base": e_base,
            "t1": _tick(trilho, ini, lateral),
            "t2": _tick(trilho, fim, lateral),
            "marco": ({"x": _a2(meio - 3), "y": _a2(trilho - 3)} if lateral
                      else {"x": _a2(trilho - 3), "y": _a2(meio - 3)}) if e_base else None,
            "texto": ({"x": _a2(meio), "y": _a2(trilho - 8), "ancora": "middle"}
                      if lateral else
                      {"x": _a2(trilho - 9), "y": _a2(meio + 3), "ancora": "end"}),
        })
    ini_trilho = min(c["ini"] for c in cotas)
    fim_trilho = max(c["fim"] for c in cotas)
    trilho_linha = ({"x1": ini_trilho, "y1": trilho, "x2": fim_trilho, "y2": trilho}
                    if lateral else
                    {"x1": trilho, "y1": ini_trilho, "x2": trilho, "y2": fim_trilho})

    # ---- viewBox pelo bbox real (LAY-14) -----------------------------------
    largura_total = max((c["x"] + c["w"] for c in nos), default=esq) + tk.margem
    if cabecalho:
        # A pílula "◂ todo o organograma" fica na direita do cabeçalho, mas num
        # desenho estreito — a lateral é estreita por construção — ela aterrissa
        # em cima da legenda, que começa na margem. Aqui ela desce uma linha em
        # vez de cobrir: o motor decide, porque é ele quem sabe a largura.
        largo = largura_total - tk.margem >= 620
        cabecalho = dict(cabecalho, x=tk.margem, y_titulo=tk.margem + 4,
                         y_linhas=tk.margem + 24, y_regua=tk.margem + 38,
                         volta_x=_a2(largura_total - 200 if largo else tk.margem),
                         volta_y=_a2(tk.margem + (11 if largo else 45)))
    return {
        "cabecalho": cabecalho,
        "raiz_id": base.id,
        "nos": nos,
        "conectores": conectores,
        "alcas": alcas,
        "cotas": cotas,
        "trilho": trilho_linha,
        "viewbox": f"0 0 {_a2(largura_total)} {_a2(altura_total)}",
        "largura": _a2(largura_total),
        "altura": _a2(altura_total),
        "orientacao": orientacao,
        "invertida": invertida,
        "lateral": lateral,
        "profundidade_max": D,
        "total_visivel": len(nos),
        "total_oculto": sum(ocultos.values()),
        "filtrando": filtrando,
    }
