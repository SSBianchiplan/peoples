"""
GPlanSiS|Peoples — Skills: Descrição de Cargos e Responsabilidades.

O organograma sabe quem responde a quem. O que ele nunca soube dizer é **o que
cada cargo é** — e essa é a pergunta que o RH faz quando abre uma vaga, quando
compara duas propostas de promoção e quando alguém pergunta por que dois
"Analista de Projetos" em verticais diferentes fazem coisas distintas.

Este módulo responde isso a partir do que já está gravado, sem cadastro novo:

    função por setor        que cargos existem em cada departamento
    Business Unit x função  a matriz que diz onde cada função se concentra
    liderança por unidade   gerência, coordenação, liderança técnica e
                            especialista, contados por BU, vertical e setor
    correlação              o quanto duas variáveis categóricas andam juntas
    matriz de competência   competência declarada x função, e a cobertura
    ficha do cargo          o Skills propriamente dito, montado da estrutura

**Sem remuneração, e é decisão.** LGPD-01/02 mantém salário fora deste sistema,
e o Skills aqui é descrição de cargo e responsabilidade — não tabela de Cargos e
Salários. Faixa salarial é dado de outro sistema, com outra guarda de acesso;
trazê-la para cá por conveniência de relatório abriria remuneração individual
para quem hoje só pode ver o desenho da estrutura.

**Nada é gravado por este módulo.** Como `tempo.py` e `estrutura.py`, ele recebe
unidades e devolve dicionários. A única coisa que persiste é a camada que o RH
edita — missão, formação, experiência e requisitos por cargo —, e ela mora em
`Config.dcr_cargos`, passa por `commit` e entra no Desfazer como qualquer outra
alteração. Derivado e editado convivem: o sistema monta o que sabe deduzir, o
RH escreve o que só ele sabe, e a ficha diz qual metade é qual.

**Liderança técnica não é coordenação.** A regra de nível classifica "líder" e
"coordenador" no mesmo degrau (`cargos.REGRAS_PADRAO`), e isso está certo para
o desenho — os dois ocupam a mesma faixa. Para o Skills está errado: quem lidera
tecnicamente responde por profundidade, quem coordena responde por gente, e
misturá-los faz a contagem de gestores mentir. O papel é derivado do cargo, não
do nível, e é por isso que ele existe separado aqui.
"""
from __future__ import annotations

import math
import re

from .dominio import sem_acento

# O módulo é puro e não recebe request: o idioma vigente entra como estado de
# módulo, ajustado por `main.alinhar_idioma()` antes de emitir. Mesma convenção
# de `importador`, `dominio` e `centros`. Fora da tela vale o padrão.
IDIOMA = "pt-BR"


def _t(texto: str, **p) -> str:
    from . import idiomas
    return idiomas.traduzir(texto, IDIOMA, **p)

# ---------------------------------------------------------------------------
# PAPÉIS
# ---------------------------------------------------------------------------
# O papel é a leitura do Skills sobre o nível: mesma escada, um degrau a mais.
# `codigo, rótulo, ordem` — a ordem é a da hierarquia, nunca a da contagem, para
# que duas emissões da mesma tabela saiam iguais (RNF-02).
PAPEIS = (
    ("diretoria", "Diretoria", 10),
    ("gerencia", "Gerência", 20),
    ("coordenacao", "Coordenação", 30),
    ("lideranca", "Liderança técnica", 35),
    ("especialista", "Especialista", 40),
    ("execucao", "Execução", 50),
    ("apoio", "Apoio", 60),
)
ROTULO_PAPEL = {c: r for c, r, _o in PAPEIS}
ORDEM_PAPEL = {c: o for c, _r, o in PAPEIS}

# Quem responde por gente. Separado de `PAPEIS` porque é isto — e não o nível —
# que divide o denominador da amplitude de comando.
PAPEIS_GESTAO = ("diretoria", "gerencia", "coordenacao")

# "Líder", "Líder Técnico", "Team Leader". Vem depois de coordenação na regra de
# nível e por isso chega aqui como `coordenacao`; o cargo é que desempata.
# `\b` nas duas pontas para não casar "Deslizante" nem "Liderança de Mercado".
LIDER = re.compile(r"\b(lider|leader|lead)\b")
COORDENA = re.compile(r"\b(coordenador|coordenadora|coordenacao|supervisor|"
                      r"supervisora)\b")

# Abaixo disto um grupo não ganha correlação nem proporção publicada: com quatro
# pessoas, uma mudança de emprego move a matriz inteira, e um número que oscila
# assim convida a decidir sobre ruído. É o mesmo princípio de `tempo.PISO_GRUPO`,
# com piso mais alto porque tabela cruzada divide a amostra duas vezes.
PISO_GRUPO = 5

# Uma célula de tabela cruzada com esperado abaixo disto torna o qui-quadrado
# pouco confiável. Não bloqueia o número — sinaliza, e a tela mostra o aviso.
PISO_ESPERADO = 5.0

# A régua de leitura do V de Cramér. Os cortes são os de Cohen adaptados para
# tabela de contingência, e estão aqui — e não na tela — porque um relatório que
# diz "forte" precisa dizer forte segundo o quê.
FORCAS = (
    (0.60, "muito forte"),
    (0.40, "forte"),
    (0.20, "moderada"),
    (0.10, "fraca"),
    (0.00, "desprezível"),
)

VAZIO = "—"

# ---------------------------------------------------------------------------
# O FORMULÁRIO INSTITUCIONAL
# ---------------------------------------------------------------------------
# GEP-FOR-003 é um formulário controlado: o código e a revisão vão impressos no
# cabeçalho porque é por eles que a qualidade rastreia qual versão do modelo
# gerou o documento. Ficha sem código de formulário não passa em auditoria de
# processo — e é auditoria de processo que pede a descrição de cargo.
FORMULARIO = {
    "codigo": "GEP-FOR-003",
    "revisao": "02",
    "titulo": "Descrição de Cargo e Responsabilidades",
}

# As quatro seções do formulário, na ordem em que ele as imprime. A ordem não é
# estética: a missão enquadra as responsabilidades, e requisito lido antes da
# responsabilidade vira lista de desejos sem âncora.
SECOES = ("missao", "responsabilidades", "requisitos", "competencias")

# Os valores da casa, como o formulário os imprime. O código casa com
# `social.VALORES`, que é o mesmo vocabulário usado no reconhecimento entre
# pessoas — dois textos diferentes para o mesmo valor institucional seria a
# empresa discordando de si mesma em duas telas do mesmo sistema.
VALORES = (
    ("teamwork", "TeamWork", "Acreditamos que só crescemos juntos."),
    ("respect", "Respect", "Somos abertos e acolhemos as diferenças."),
    ("innovation", "Innovation", "Superamos nossos desafios."),
    ("ownership", "Ownership", "Somos conscientes e protagonistas."),
)


# ---------------------------------------------------------------------------
# LEITURA DA ESTRUTURA
# ---------------------------------------------------------------------------
def papel(tipo: str, cargo: str) -> str:
    """O papel do Skills, derivado do nível e desempatado pelo cargo.

    Só o degrau de coordenação é ambíguo: é lá que a regra de nível junta quem
    coordena gente e quem lidera tecnicamente. Quem for as duas coisas —
    "Coordenador e Líder de Squad" — conta como coordenação, pela mesma razão
    que `cargos.REGRAS_PADRAO` já usa: a responsabilidade sobre gente é a que
    muda o desenho da árvore, e é ela que a amplitude de comando mede.
    """
    if tipo in ("diretoria", "gerencia", "especialista", "apoio"):
        return tipo
    c = sem_acento(cargo)
    if tipo == "coordenacao":
        if LIDER.search(c) and not COORDENA.search(c):
            return "lideranca"
        return "coordenacao"
    # Nível abaixo da coordenação com "líder" no cargo é liderança técnica que a
    # regra não pegou — cargo fora do catálogo, ou catálogo editado à mão.
    if LIDER.search(c) and not COORDENA.search(c):
        return "lideranca"
    return "execucao"


def chave_funcao(cargo: str) -> str:
    """A função é o cargo sem acento e sem caixa — a mesma chave de `cargos`."""
    return sem_acento(cargo).strip()


def _pessoas(unidades):
    """As unidades que são gente. A raiz é nó sintético, não empregado."""
    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    return [u for u in us if u.parent_id is not None]


def medir(unidades, mapa_cc: dict | None = None) -> list[dict]:
    """Uma linha por pessoa, com função, setor, BU e papel já resolvidos.

    É a base de todo o resto — as matrizes, as correlações e as fichas consomem
    esta lista e não o dicionário de unidades. Uma régua só, aplicada uma vez:
    duas leituras de "qual é a BU desta pessoa" no mesmo módulo divergiriam no
    primeiro ajuste, e a errada seria a que ninguém conferiu.

    `mapa_cc` é o que `centros.mapear` devolve. Sem ele o módulo ainda funciona
    e cai no `vertical` gravado na própria unidade — é o que acontece nos testes
    e em qualquer base carregada antes do cadastro de centros de custo existir.
    """
    mapa_cc = mapa_cc or {}
    linhas = []
    for u in _pessoas(unidades):
        cc = mapa_cc.get(u.id) or {}
        linhas.append({
            "id": u.id,
            "codigo": u.codigo,
            "nome": u.nome,
            "cargo": (u.cargo or "").strip(),
            "funcao": chave_funcao(u.cargo),
            "setor": (u.area or "").strip(),
            # A BU é a natureza do centro de custo — "Bussines Unit", "Suport
            # Team", "Diretoria" —, que é o corte que separa quem entrega ao
            # cliente de quem sustenta a casa. Sai como está no cadastro,
            # inclusive a grafia: é valor de negócio que casa com outro sistema.
            "bu": (cc.get("tipo_cc") or "").strip(),
            "vertical": (cc.get("vertical_negocio") or u.vertical or "").strip(),
            # O mnemônico da equipe. O formulário escreve a área como
            # "PCO – Planejamento e Controle Operacional", e é este campo que
            # dá a primeira metade — sem ele a linha sairia só com o nome longo.
            "n5": (cc.get("n5") or "").strip(),
            "centro_custo": u.centro_custo,
            "nivel": u.tipo,
            "papel": papel(u.tipo, u.cargo),
            # O código serve à contagem e à correlação; o rótulo serve à matriz,
            # que imprime o eixo. Cruzar pelo código faria a tabela sair com
            # "coordenacao" sem acento no cabeçalho de uma tela em espanhol.
            "papel_rotulo": ROTULO_PAPEL[papel(u.tipo, u.cargo)],
            "vinculo": u.vinculo,
            "parent_id": u.parent_id,
            "competencias": [c for c in (u.competencias or []) if str(c).strip()],
            "responsabilidades": list(u.responsabilidades or []),
        })
    return linhas


def _rotulo(valor: str) -> str:
    return valor or VAZIO


# ---------------------------------------------------------------------------
# TABELA CRUZADA
# ---------------------------------------------------------------------------
def cruzar(linhas: list[dict], eixo_l: str, eixo_c: str,
           minimo: int = 0) -> dict:
    """Contagem de `eixo_l` x `eixo_c`, com marginais.

    `minimo` recolhe as linhas raras num agregado em vez de descartá-las: numa
    matriz de 119 cargos x 8 BUs, as 60 funções de uma pessoa só produzem 60
    linhas de ruído que empurram o que interessa para fora da tela — mas somem
    do total se forem jogadas fora, e um total que não fecha destrói a confiança
    na tabela inteira. Elas viram uma linha agregada e o total continua fechando.
    """
    celulas: dict[tuple[str, str], int] = {}
    tot_l: dict[str, int] = {}
    tot_c: dict[str, int] = {}
    for l in linhas:
        a, b = _rotulo(str(l.get(eixo_l) or "")), _rotulo(str(l.get(eixo_c) or ""))
        celulas[(a, b)] = celulas.get((a, b), 0) + 1
        tot_l[a] = tot_l.get(a, 0) + 1
        tot_c[b] = tot_c.get(b, 0) + 1

    raras = {a for a, n in tot_l.items() if n < minimo} if minimo else set()
    if raras:
        agregado = _t("outras ({n})", n=len(raras))
        for (a, b), n in list(celulas.items()):
            if a in raras:
                celulas[(agregado, b)] = celulas.get((agregado, b), 0) + n
                del celulas[(a, b)]
        tot_l = {a: n for a, n in tot_l.items() if a not in raras}
        tot_l[agregado] = sum(v for k, v in celulas.items() if k[0] == agregado)

    # Do maior para o menor, com o nome desempatando: dois grupos do mesmo
    # tamanho não podem trocar de lugar entre dois renders (RNF-02).
    ordem_l = sorted(tot_l, key=lambda a: (-tot_l[a], sem_acento(a)))
    ordem_c = sorted(tot_c, key=lambda b: (-tot_c[b], sem_acento(b)))
    total = sum(tot_l.values())
    return {
        "eixo_l": eixo_l, "eixo_c": eixo_c,
        "linhas": ordem_l, "colunas": ordem_c,
        "celulas": celulas,
        "total_linha": tot_l, "total_coluna": tot_c, "total": total,
        "grade": [{"rotulo": a, "total": tot_l[a],
                   "celulas": [celulas.get((a, b), 0) for b in ordem_c]}
                  for a in ordem_l],
    }


def concentracao(tabela: dict) -> list[dict]:
    """Onde cada linha se concentra: a coluna dominante e o quanto ela pesa.

    Uma matriz de 8 x 12 tem 96 números e ninguém lê 96 números. Esta é a
    leitura que sobra depois de olhar a matriz por trinta segundos — "Software
    Team é 71 % F&B" — e é ela que vai para a tela primeiro.
    """
    saida = []
    for a in tabela["linhas"]:
        total = tabela["total_linha"][a] or 1
        pares = [(b, tabela["celulas"].get((a, b), 0)) for b in tabela["colunas"]]
        # Maior contagem; empate resolvido pelo nome, nunca pela ordem do dict —
        # duas emissões da mesma tabela têm que eleger a mesma dominante.
        alvo, n = sorted(pares, key=lambda p: (-p[1], sem_acento(p[0])))[0]
        saida.append({
            "rotulo": a, "total": tabela["total_linha"][a],
            "dominante": alvo, "n": n,
            "pct": round(100 * n / total, 1),
            "espalhada": sum(1 for _b, v in pares if v),
        })
    return sorted(saida, key=lambda d: (-d["total"], sem_acento(d["rotulo"])))


# ---------------------------------------------------------------------------
# CORRELAÇÃO ENTRE VARIÁVEIS CATEGÓRICAS
# ---------------------------------------------------------------------------
def cramer_v(tabela: dict) -> dict:
    """Qui-quadrado e V de Cramér da tabela cruzada.

    Pearson não serve aqui: BU, função e nível são categóricas, não ordenáveis,
    e um coeficiente que exige ordem inventaria que "Gerência" é maior que
    "F&B". O V de Cramér mede associação entre categóricas, vai de 0 a 1, e não
    depende do tamanho da amostra — o que permite comparar o par BU x função com
    o par setor x nível na mesma tabela.

    **V alto não é causa.** Diz que saber a BU reduz a incerteza sobre a função;
    não diz que a BU determina a função, e muito menos qual das duas veio antes.
    O relatório publica a força junto do número justamente para que ninguém leia
    0,62 como "62 % de explicação", que é o erro clássico.

    `confiavel` fica falso quando mais de 20 % das células têm esperado abaixo de
    `PISO_ESPERADO` — a regra de Cochran. O número continua saindo, com a
    ressalva colada nele: esconder o resultado faria a pessoa procurá-lo noutro
    lugar, sem a ressalva.
    """
    n = tabela["total"]
    r, c = len(tabela["linhas"]), len(tabela["colunas"])
    if n < 2 or r < 2 or c < 2:
        return {"v": None, "qui2": None, "gl": 0, "n": n, "confiavel": False,
                "forca": "", "celulas_ralas": 0}

    qui2 = 0.0
    ralas = 0
    for a in tabela["linhas"]:
        for b in tabela["colunas"]:
            esperado = tabela["total_linha"][a] * tabela["total_coluna"][b] / n
            if esperado < PISO_ESPERADO:
                ralas += 1
            if esperado > 0:
                observado = tabela["celulas"].get((a, b), 0)
                qui2 += (observado - esperado) ** 2 / esperado

    # Ruído numérico do somatório pode passar de 1 por frações de 1e-12, e um
    # "V = 1,0000000002" na tela é o tipo de detalhe que faz alguém desconfiar
    # do relatório inteiro.
    bruto = min(1.0, math.sqrt(qui2 / (n * min(r - 1, c - 1))))

    # CORREÇÃO DE VIÉS (Bergsma, 2013). Sem ela este relatório mentiria: o par
    # Business Unit x função tem 120 categorias de um lado e 3 do outro sobre
    # 271 pessoas, e o V bruto sai 0,99 — que é esparsidade, não associação. Com
    # muitas categorias e amostra pequena, o qui-quadrado acumula erro em cada
    # célula vazia e o V herda tudo. A correção desconta o valor esperado do
    # próprio ruído; onde a tabela é densa ela quase não muda nada, e onde é
    # rala ela derruba o número para onde ele deveria estar.
    phi2 = qui2 / n
    phi2_c = max(0.0, phi2 - (r - 1) * (c - 1) / (n - 1))
    r_c = r - (r - 1) ** 2 / (n - 1)
    c_c = c - (c - 1) ** 2 / (n - 1)
    denominador = min(r_c - 1, c_c - 1)
    v = min(1.0, math.sqrt(phi2_c / denominador)) if denominador > 0 else 0.0

    return {
        "v": v, "v_bruto": bruto, "qui2": qui2, "gl": (r - 1) * (c - 1), "n": n,
        "celulas_ralas": ralas,
        "confiavel": ralas <= 0.2 * r * c,
        "forca": next(rot for corte, rot in FORCAS if v >= corte),
    }


# Os pares que o relatório publica. Cada um responde uma pergunta que alguém
# faz de verdade, e é por isso que são estes seis e não todas as 21 combinações
# possíveis — uma matriz de correlação cheia é onde a leitura se perde.
PARES = (
    ("bu", "papel", "Business Unit × papel"),
    ("bu", "funcao", "Business Unit × função"),
    ("vertical", "papel", "Vertical × papel"),
    ("vertical", "funcao", "Vertical × função"),
    ("setor", "papel", "Setor × papel"),
    ("vinculo", "papel", "Vínculo × papel"),
)


def correlacoes(linhas: list[dict], pares=PARES) -> list[dict]:
    """O V de Cramér de cada par, do mais associado ao menos."""
    saida = []
    for eixo_l, eixo_c, rotulo in pares:
        tabela = cruzar(linhas, eixo_l, eixo_c)
        medida = cramer_v(tabela)
        if medida["v"] is None:
            continue
        saida.append({**medida, "rotulo": rotulo,
                      "eixo_l": eixo_l, "eixo_c": eixo_c,
                      "categorias_l": len(tabela["linhas"]),
                      "categorias_c": len(tabela["colunas"])})
    return sorted(saida, key=lambda d: (-d["v"], d["rotulo"]))


# ---------------------------------------------------------------------------
# LIDERANÇA POR UNIDADE
# ---------------------------------------------------------------------------
def lideranca(linhas: list[dict], por: str = "bu") -> list[dict]:
    """Gerência, coordenação, liderança técnica e especialista por unidade.

    `por` aceita `bu`, `vertical` ou `setor` — a mesma pergunta em três recortes,
    e um agrupador em vez de três funções que divergem na terceira edição.

    **A amplitude é declarada, não medida na árvore.** `pessoas / gestores` é a
    razão do grupo, e não a média de subordinados diretos: uma coordenadora cuja
    equipe inteira está em outro centro de custo apareceria com amplitude zero
    numa contagem por árvore, o que diria mais sobre o cadastro de CC do que
    sobre ela. `amplitude_direta` existe ao lado, medida na árvore, exatamente
    para que a distância entre as duas seja visível.
    """
    grupos: dict[str, list[dict]] = {}
    for l in linhas:
        grupos.setdefault(_rotulo(str(l.get(por) or "")), []).append(l)

    saida = []
    for chave, gente in grupos.items():
        contagem = {c: sum(1 for l in gente if l["papel"] == c)
                    for c, _r, _o in PAPEIS}
        gestores = sum(contagem[c] for c in PAPEIS_GESTAO)
        saida.append({
            "chave": chave, "rotulo": chave, "n": len(gente),
            **contagem,
            "gestores": gestores,
            "tecnicos": contagem["lideranca"] + contagem["especialista"],
            # Sem gestor não é amplitude infinita: é um grupo sem gestão própria,
            # e o travessão da tela diz isso melhor que qualquer número.
            "amplitude": round(len(gente) / gestores, 1) if gestores else None,
            "funcoes": len({l["funcao"] for l in gente if l["funcao"]}),
        })
    return sorted(saida, key=lambda g: (-g["n"], sem_acento(g["rotulo"])))


def amplitude_direta(unidades, linhas: list[dict],
                     minimo: int = 1) -> list[dict]:
    """Quantos subordinados diretos cada gestor tem, medido na árvore.

    O contraponto de `lideranca`: aqui a conta é de estrutura, não de cadastro.
    Onde os dois números divergem muito, há gente pendurada num centro de custo
    que não é o de quem a lidera — e isso é achado de dado, não de organização.
    """
    us = unidades if isinstance(unidades, dict) else {u.id: u for u in unidades}
    por_id = {l["id"]: l for l in linhas}
    equipes: dict[str, int] = {}
    for l in linhas:
        if l["parent_id"] in us:
            equipes[l["parent_id"]] = equipes.get(l["parent_id"], 0) + 1

    saida = []
    for gid, n in equipes.items():
        chefe = por_id.get(gid)
        if chefe is None or n < minimo:
            continue
        saida.append({
            "id": gid, "codigo": chefe["codigo"], "nome": chefe["nome"],
            "cargo": chefe["cargo"], "papel": chefe["papel"],
            "setor": chefe["setor"], "bu": chefe["bu"],
            "diretos": n,
        })
    return sorted(saida, key=lambda g: (-g["diretos"], sem_acento(g["nome"])))


# ---------------------------------------------------------------------------
# MATRIZ DE COMPETÊNCIA
# ---------------------------------------------------------------------------
def matriz_competencias(linhas: list[dict], por: str = "funcao",
                        teto: int = 40) -> dict:
    """Competência declarada x grupo, com a cobertura de cada grupo.

    `cobertura` é a fração de pessoas do grupo que declararam ao menos uma
    competência, e ela vem antes de qualquer célula: numa área onde 8 de 30
    preencheram, a matriz descreve os 8 e não a área. Sem esse número ao lado, a
    linha "Automação: 3" seria lida como "só 3 sabem automação", quando o que
    ela diz é "3 dos 8 que responderam".

    `teto` corta a lista de competências pelas mais frequentes. O corte é
    declarado no retorno (`ocultas`), porque tabela que some com dado sem avisar
    é a mesma coisa que dado errado.
    """
    freq: dict[str, int] = {}
    for l in linhas:
        for c in set(_norm_comp(x) for x in l["competencias"]):
            if c:
                freq[c] = freq.get(c, 0) + 1

    ordenadas = sorted(freq, key=lambda c: (-freq[c], c))
    visiveis = ordenadas[:teto]

    grupos: dict[str, list[dict]] = {}
    for l in linhas:
        grupos.setdefault(_rotulo(str(l.get(por) or "")), []).append(l)

    corpo = []
    for chave, gente in sorted(grupos.items(),
                               key=lambda kv: (-len(kv[1]), sem_acento(kv[0]))):
        declararam = sum(1 for l in gente if l["competencias"])
        conta = {c: 0 for c in visiveis}
        for l in gente:
            for c in set(_norm_comp(x) for x in l["competencias"]):
                if c in conta:
                    conta[c] += 1
        corpo.append({
            "rotulo": chave, "n": len(gente), "declararam": declararam,
            "cobertura": round(100 * declararam / len(gente), 1) if gente else 0.0,
            "celulas": [conta[c] for c in visiveis],
            "distintas": len({_norm_comp(x) for l in gente
                              for x in l["competencias"] if _norm_comp(x)}),
        })

    total_declarou = sum(1 for l in linhas if l["competencias"])
    return {
        "competencias": [{"rotulo": c, "n": freq[c]} for c in visiveis],
        "grupos": corpo,
        "ocultas": max(0, len(ordenadas) - len(visiveis)),
        "distintas": len(ordenadas),
        "declararam": total_declarou,
        "pessoas": len(linhas),
        "cobertura": (round(100 * total_declarou / len(linhas), 1)
                      if linhas else 0.0),
    }


def _norm_comp(texto) -> str:
    """Competência sem caixa e sem espaço de sobra, mantendo o acento.

    Sem normalizar, "Automação" e "automação " são duas competências na matriz e
    a mesma coisa na cabeça de quem digitou. O acento fica: é rótulo que vai
    para a tela, e `sem_acento` só entra na ordenação e na comparação.
    """
    return " ".join(str(texto or "").split()).strip()


# ---------------------------------------------------------------------------
# A FICHA — o Skills de um cargo
# ---------------------------------------------------------------------------
def _consolidar(itens, chave_de, rotulo_de) -> list[dict]:
    """Frequência de um atributo repetido entre as pessoas do mesmo cargo."""
    conta: dict[str, int] = {}
    rotulos: dict[str, str] = {}
    for x in itens:
        k = chave_de(x)
        if not k:
            continue
        conta[k] = conta.get(k, 0) + 1
        rotulos.setdefault(k, rotulo_de(x))
    return [{"rotulo": rotulos[k], "n": conta[k]}
            for k in sorted(conta, key=lambda k: (-conta[k], k))]


def funcoes(linhas: list[dict], overlay: list[dict] | None = None) -> list[dict]:
    """O índice de fichas: uma linha por função, com o que a lista precisa."""
    por_chave: dict[str, list[dict]] = {}
    for l in linhas:
        if l["funcao"]:
            por_chave.setdefault(l["funcao"], []).append(l)

    escrito = {chave_funcao(o.get("cargo", "")) for o in (overlay or [])
               if _tem_texto(o)}
    saida = []
    for chave, gente in por_chave.items():
        papeis = _consolidar(gente, lambda l: l["papel"],
                             lambda l: ROTULO_PAPEL.get(l["papel"], l["papel"]))
        saida.append({
            "chave": chave,
            "cargo": gente[0]["cargo"],
            "n": len(gente),
            "papel": papeis[0]["rotulo"] if papeis else VAZIO,
            "papel_codigo": gente[0]["papel"],
            "setores": len({l["setor"] for l in gente if l["setor"]}),
            "bus": len({l["bu"] for l in gente if l["bu"]}),
            "competencias": len({_norm_comp(c) for l in gente
                                 for c in l["competencias"] if _norm_comp(c)}),
            "descrita": chave in escrito,
        })
    return sorted(saida, key=lambda f: (-f["n"], sem_acento(f["cargo"])))


def _tem_texto(o: dict) -> bool:
    return any(str(o.get(c) or "").strip() for c in CAMPOS_OVERLAY)


# A camada que o RH escreve — uma entrada por seção do formulário. `missao` é
# prosa; as outras três são listas, uma por linha, e viram marcadores na ficha.
#
# `responsabilidades` e `competencias` também são DEDUZIDAS da estrutura, e as
# duas versões convivem de propósito: o sistema mostra o que consegue extrair do
# que está gravado, o RH escreve o texto que vai para o documento assinado, e a
# ficha diz de onde veio cada bloco. Sem essa distinção, um texto redigido pelo
# RH seria sobrescrito na próxima carga da planilha — e ninguém saberia dizer
# qual das duas versões estava valendo.
CAMPOS_OVERLAY = SECOES
LIMITE_OVERLAY = 6000

# Seções que o formulário imprime como lista de marcadores.
CAMPOS_LISTA = ("responsabilidades", "requisitos", "competencias")


def itens(texto: str) -> list[str]:
    """Texto de várias linhas -> marcadores, como o formulário imprime.

    Uma linha é um marcador. O traço, o asterisco e o ponto que muita gente
    digita por hábito de lista são removidos: eles reapareceriam como texto
    dentro do próprio marcador, e a ficha sairia com dois bullets na mesma
    linha. Linha em branco separa parágrafos ao digitar e não vira item vazio.
    """
    saida = []
    for linha in str(texto or "").replace("\r\n", "\n").split("\n"):
        limpa = re.sub(r"^\s*[-*•·–—]\s*", "", linha).strip()
        if limpa:
            saida.append(limpa)
    return saida


def normalizar_overlay(bruto: list[dict] | None) -> list[dict]:
    """Saneia a camada editável. Entrada de formulário não é dado confiável."""
    saida: dict[str, dict] = {}
    for o in bruto or []:
        cargo = str((o or {}).get("cargo") or "").strip()[:120]
        if not cargo:
            continue
        linha = {"cargo": cargo}
        for campo in CAMPOS_OVERLAY:
            linha[campo] = str(o.get(campo) or "").strip()[:LIMITE_OVERLAY]
        # Linha em branco não ocupa lugar: gravá-la faria o índice marcar como
        # "descrita" uma ficha que ninguém escreveu.
        if _tem_texto(linha):
            saida[chave_funcao(cargo)] = linha
    return sorted(saida.values(), key=lambda o: sem_acento(o["cargo"]))


def overlay_de(chave: str, overlay: list[dict] | None) -> dict:
    for o in overlay or []:
        if chave_funcao(o.get("cargo", "")) == chave:
            return o
    return {"cargo": "", **{c: "" for c in CAMPOS_OVERLAY}}


def ficha(chave: str, linhas: list[dict], unidades,
          overlay: list[dict] | None = None,
          rotulos_nivel: dict | None = None) -> dict | None:
    """O Skills de uma função: o que o sistema deduz + o que o RH escreveu.

    `None` quando a função não existe no recorte — a rota transforma isso em
    aviso, e não em 500. Cargo some da base a cada carga da planilha; um link
    guardado para a ficha de um cargo extinto é caso normal, não erro.

    Tudo o que sai daqui é rastreável a uma pessoa da estrutura: quem reporta a
    quem sai da árvore, as responsabilidades saem do que está gravado em cada
    unidade, e a frequência ao lado de cada item diz em quantas das N ocupações
    aquilo aparece. Um item que aparece em 1 de 12 não é a descrição do cargo —
    é a descrição de uma pessoa —, e a contagem é o que permite ver a diferença.
    """
    gente = [l for l in linhas if l["funcao"] == chave]
    if not gente:
        return None

    us = unidades if isinstance(unidades, dict) else {u.id: u for u in unidades}
    por_id = {l["id"]: l for l in linhas}
    rotulos_nivel = rotulos_nivel or {}

    # Reporte: o cargo de cada pai distinto. É o "responde a" do Skills, e sai da
    # árvore — não de campo declarado, que envelheceria na primeira mudança.
    chefes = []
    for l in gente:
        pai = por_id.get(l["parent_id"])
        if pai:
            chefes.append(pai)
        elif l["parent_id"] in us:
            # O pai é a raiz: nó sintético, sem cargo, e fora de `linhas`.
            chefes.append({"cargo": us[l["parent_id"]].nome, "funcao": "raiz"})

    diretos = [x for x in linhas if x["parent_id"] in {l["id"] for l in gente}]

    responsabilidades = [r for l in gente for r in l["responsabilidades"]]
    ocupantes = sorted(gente, key=lambda l: sem_acento(l["nome"]))

    return {
        "chave": chave,
        "cargo": gente[0]["cargo"],
        "n": len(gente),
        "papel": ROTULO_PAPEL.get(gente[0]["papel"], gente[0]["papel"]),
        "papel_codigo": gente[0]["papel"],
        "niveis": _consolidar(
            gente, lambda l: l["nivel"],
            lambda l: rotulos_nivel.get(l["nivel"], l["nivel"])),
        "setores": _consolidar(gente, lambda l: l["setor"], lambda l: l["setor"]),
        "bus": _consolidar(gente, lambda l: l["bu"], lambda l: l["bu"]),
        "verticais": _consolidar(gente, lambda l: l["vertical"],
                                 lambda l: l["vertical"]),
        "vinculos": _consolidar(gente, lambda l: l["vinculo"],
                                lambda l: l["vinculo"]),
        "reporta_a": _consolidar(chefes, lambda c: chave_funcao(c["cargo"]),
                                 lambda c: c["cargo"]),
        "responde_por": _consolidar(diretos, lambda l: l["funcao"],
                                    lambda l: l["cargo"]),
        "diretos": len(diretos),
        "proprias": _consolidar(
            [r for r in responsabilidades if r.get("origem") != "delegada"],
            lambda r: sem_acento(r.get("descricao", "")),
            lambda r: r.get("descricao", "")),
        "delegadas": _consolidar(
            [r for r in responsabilidades if r.get("origem") == "delegada"],
            lambda r: sem_acento(r.get("descricao", "")),
            lambda r: r.get("descricao", "")),
        "competencias": _consolidar(
            [c for l in gente for c in set(_norm_comp(x)
                                           for x in l["competencias"])],
            lambda c: sem_acento(c), lambda c: c),
        "ocupantes": [{"id": l["id"], "codigo": l["codigo"], "nome": l["nome"],
                       "setor": l["setor"], "bu": l["bu"]} for l in ocupantes],
        "area": _area(gente),
        "escrito": overlay_de(chave, overlay),
    }


def _area(gente: list[dict]) -> str:
    """A linha «Área» do formulário: `N5 – Departamento`.

    Uma função pode existir em vários departamentos — "Analista de Projetos"
    aparece em seis. O formulário tem uma linha só, então ela leva o
    departamento onde a função mais aparece e o sufixo diz quantos outros
    existem. Escolher em silêncio faria a ficha de seis áreas parecer a ficha
    de uma.
    """
    contagem: dict[tuple[str, str], int] = {}
    for l in gente:
        if l["setor"]:
            par = (l["n5"], l["setor"])
            contagem[par] = contagem.get(par, 0) + 1
    if not contagem:
        return ""
    (n5, setor), _n = sorted(contagem.items(),
                             key=lambda kv: (-kv[1], sem_acento(kv[0][1])))[0]
    # "PPC – PPC (Production Planning and Control)" é o mnemônico impresso duas
    # vezes: o cadastro já carrega a sigla dentro do nome do departamento em
    # boa parte das linhas. Prefixa só quando o nome não a traz.
    prefixa = n5 and not sem_acento(setor).startswith(sem_acento(n5))
    principal = f"{n5} – {setor}" if prefixa else setor
    outras = len(contagem) - 1
    return f"{principal} (+{outras})" if outras else principal


def documento(f: dict) -> list[dict]:
    """As quatro seções do GEP-FOR-003, na ordem do formulário.

    Cada seção declara a `origem` do que está nela — `escrito` quando o RH
    redigiu, `derivado` quando o sistema extraiu da estrutura, `vazio` quando
    não há nem um nem outro. A tela e o PDF pintam essa diferença, e é ela que
    impede o documento de ser lido como se tudo tivesse sido revisado por
    alguém: uma responsabilidade deduzida de seis cadastros é ponto de partida
    para o RH escrever, não texto aprovado.

    O texto escrito VENCE o derivado quando existe. O derivado não desaparece —
    a tela o mantém ao lado, como sugestão —, mas o documento imprime um só.
    """
    escrito = f.get("escrito") or {}
    derivado = {
        "responsabilidades": [r["rotulo"] for r in f["proprias"]]
                             + [r["rotulo"] for r in f["delegadas"]],
        "competencias": [c["rotulo"] for c in f["competencias"]],
        # Requisito não se deduz de organograma: escolaridade, tempo de
        # experiência e disponibilidade para viagem não estão em lugar nenhum
        # da estrutura, e inventá-los a partir do nível seria o sistema
        # afirmando o que não sabe.
        "requisitos": [],
        "missao": [],
    }
    saida = []
    for chave in SECOES:
        texto = str(escrito.get(chave) or "").strip()
        lista = chave in CAMPOS_LISTA
        if texto:
            conteudo = itens(texto) if lista else [texto]
            origem = "escrito"
        else:
            conteudo = derivado[chave]
            origem = "derivado" if conteudo else "vazio"
        saida.append({"chave": chave, "tipo": "lista" if lista else "prosa",
                      "conteudo": conteudo, "origem": origem,
                      "sugestao": derivado[chave] if origem == "escrito" else []})
    return saida


ROTULO_SECAO = {
    "missao": "Missão do Cargo",
    "responsabilidades": "Principais Responsabilidades",
    "requisitos": "Requisitos Desejáveis",
    "competencias": "Competências Desejáveis",
}


def markdown(f: dict) -> str:
    """A ficha em Markdown, na ordem do GEP-FOR-003.

    Markdown e não PDF direto: `relatorio.py` já sabe paginar, quebrar linha
    medindo largura real e desenhar tabela, e o subconjunto que ele interpreta
    — título, parágrafo, lista — é exatamente o que este formulário usa. Um
    segundo montador de PDF neste repositório divergiria do primeiro na terceira
    correção de entrelinha.

    Seção sem conteúdo sai com o travessão em vez de sumir: o formulário é
    controlado, e uma ficha impressa sem a seção "Requisitos Desejáveis" não é a
    mesma ficha com o campo vazio — a primeira parece outra versão do
    documento, a segunda mostra o que falta preencher.
    """
    linhas = [f"# {_t('Descrição de Cargo')}", ""]
    linhas.append(f"**{_t('Cargo')}:** {f['cargo']}")
    linhas.append("")
    linhas.append(f"**{_t('Área')}:** {f['area'] or VAZIO}")
    linhas.append("")
    for secao in documento(f):
        linhas.append(f"## {_t(ROTULO_SECAO[secao['chave']])}")
        linhas.append("")
        if not secao["conteudo"]:
            linhas.append(VAZIO)
        elif secao["tipo"] == "lista":
            linhas.extend(f"- {item}" for item in secao["conteudo"])
        else:
            linhas.extend(secao["conteudo"])
        linhas.append("")
    linhas.append(f"## {_t('Valores')}")
    linhas.append("")
    linhas.extend(f"- **{rotulo}:** {_t(frase)}" for _c, rotulo, frase in VALORES)
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# PANORAMA
# ---------------------------------------------------------------------------
def resumo(linhas: list[dict]) -> dict:
    papeis = {c: sum(1 for l in linhas if l["papel"] == c) for c, _r, _o in PAPEIS}
    gestores = sum(papeis[c] for c in PAPEIS_GESTAO)
    return {
        "pessoas": len(linhas),
        "funcoes": len({l["funcao"] for l in linhas if l["funcao"]}),
        "setores": len({l["setor"] for l in linhas if l["setor"]}),
        "bus": len({l["bu"] for l in linhas if l["bu"]}),
        "verticais": len({l["vertical"] for l in linhas if l["vertical"]}),
        "sem_cargo": sum(1 for l in linhas if not l["funcao"]),
        "sem_bu": sum(1 for l in linhas if not l["bu"]),
        **papeis,
        "gestores": gestores,
        "amplitude": round(len(linhas) / gestores, 1) if gestores else None,
    }


def panorama(unidades, mapa_cc: dict | None = None,
             overlay: list[dict] | None = None,
             rotulos_nivel: dict | None = None) -> dict:
    """Tudo o que a vista precisa, numa passada só sobre as unidades."""
    linhas = medir(unidades, mapa_cc)
    bu_funcao = cruzar(linhas, "bu", "funcao", minimo=PISO_GRUPO)
    return {
        "linhas": linhas,
        "resumo": resumo(linhas),
        "papeis": PAPEIS,
        "funcoes": funcoes(linhas, overlay),
        "setor_papel": cruzar(linhas, "setor", "papel_rotulo"),
        "bu_papel": cruzar(linhas, "bu", "papel_rotulo"),
        "bu_funcao": bu_funcao,
        "concentracao": concentracao(cruzar(linhas, "funcao", "bu",
                                            minimo=PISO_GRUPO)),
        "correlacoes": correlacoes(linhas),
        "lideranca_bu": lideranca(linhas, "bu"),
        "lideranca_vertical": lideranca(linhas, "vertical"),
        "lideranca_setor": lideranca(linhas, "setor"),
        "amplitude": amplitude_direta(unidades, linhas),
        "competencias": matriz_competencias(linhas),
        "piso_grupo": PISO_GRUPO,
    }


# ---------------------------------------------------------------------------
# PERSISTÊNCIA EM POSTGRES — a descrição de cargo durável
# ---------------------------------------------------------------------------
# Mesmo desenho da Conversa de Valor, e pelos mesmos motivos: o banco é OPCIONAL (a suíte e o
# dev rodam sem ele), então `Config.dcr_cargos` segue a verdade viva — editável,
# no Desfazer, testável. O Postgres é o espelho durável, e é o que torna a
# descrição de cargo editável no banco e não presa a um arquivo local.
def banco_pronto() -> bool:
    from . import banco
    return banco.situacao().get("pronto", False)


def _conectar():
    from . import banco
    pg = banco.driver()
    return pg.connect(banco.dsn(), connect_timeout=8) if pg and banco.dsn() else None


def salvar_no_banco(reg: dict, slug: str = "peoples") -> tuple[bool, str]:
    """UPSERT de uma descrição no Postgres. Idempotente por (slug, ref): editar o
    mesmo cargo atualiza a linha. Silencioso sem banco — o overlay já guardou."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return False, "sem banco"
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO org.dcr_overlay (slug, ref, cargo, missao, "
                "responsabilidades, requisitos, competencias, registrado_por) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (slug, ref) DO UPDATE SET cargo=EXCLUDED.cargo, "
                "missao=EXCLUDED.missao, responsabilidades=EXCLUDED.responsabilidades, "
                "requisitos=EXCLUDED.requisitos, competencias=EXCLUDED.competencias, "
                "registrado_por=EXCLUDED.registrado_por, atualizado_em=now()",
                (slug, chave_funcao(reg.get("cargo", "")), reg.get("cargo", ""),
                 reg.get("missao", ""), reg.get("responsabilidades", ""),
                 reg.get("requisitos", ""), reg.get("competencias", ""),
                 reg.get("por", "")))
        con.commit()
        return True, "gravado no banco"
    except Exception as erro:                          # noqa: BLE001
        return False, str(erro).strip().splitlines()[0][:200]
    finally:
        if con is not None:
            con.close()


def carregar_do_banco(slug: str = "peoples") -> list[dict]:
    """Todas as descrições do banco, no formato do overlay. `[]` sem banco."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return []
        with con.cursor() as cur:
            cur.execute(
                "SELECT cargo, missao, responsabilidades, requisitos, competencias "
                "FROM org.dcr_overlay WHERE slug=%s", (slug,))
            return [{"cargo": r[0], "missao": r[1], "responsabilidades": r[2],
                     "requisitos": r[3], "competencias": r[4]}
                    for r in cur.fetchall()]
    except Exception:                                  # noqa: BLE001
        return []
    finally:
        if con is not None:
            con.close()


def fundir(overlay: list[dict] | None,
           do_banco: list[dict] | None) -> list[dict]:
    """Overlay vivo + banco, sem duplicar. O overlay vence no conflito de mesma
    função: é o que o operador acabou de editar, ainda não espelhado."""
    idx = {chave_funcao(r["cargo"]): r for r in normalizar_overlay(do_banco)}
    idx.update({chave_funcao(r["cargo"]): r for r in normalizar_overlay(overlay)})
    return sorted(idx.values(), key=lambda o: sem_acento(o["cargo"]))
