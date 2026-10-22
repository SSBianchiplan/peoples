"""
GPlanSiS|Peoples - cadastro de centros de custo.

O organograma so conhecia o CC de nivel 4 que vem na planilha de pessoas
(80.31, 87.32...). Esse numero identifica a equipe, mas nao diz a que vertical
de negocio ela pertence nem que natureza ela tem. Essa informacao vive em um
cadastro proprio, com sete colunas:

    LogicalCC   tronco de dois digitos          80
    N2          centro de custo da vertical     80.0
    N3          centro de custo do grupo        80.30
    Departamento  equipe                        Process Engineering
    N5          mnemonico da equipe             PRO
    Vertical    vertical de negocio             ENG
    Tipo        natureza                        Bussines Unit

A chave e o par (N3, Departamento): "Managers Team" existe em 80.20, 81.20,
82.20 e 89.20, e "Hardware Design Team" em quatro verticais diferentes — nem o
codigo nem o nome sozinhos identificam a linha.

O N4 da planilha nao aparece aqui: ele e derivavel (N3 e o N4 com o ultimo
digito zerado), e e por essa relacao que uma pessoa alcanca a sua vertical.

Os rotulos saem como estao no cadastro de origem, inclusive "Bussines Unit" e
"Suport Team". Sao valores de negocio que podem precisar casar com outros
sistemas; corrigir a grafia e decisao do dono do dado, e a tela permite.
"""
from __future__ import annotations

from .dominio import sem_acento

# O idioma vigente, como no importador: `centros` é módulo puro e não recebe
# request, então quem o chama ajusta antes. Fora da tela vale o padrão.
IDIOMA = "pt-BR"


def _t(texto: str, **p) -> str:
    from . import idiomas
    return idiomas.traduzir(texto, IDIOMA, **p)

# (logico, n2, n3, departamento, n5, vertical, tipo)
# Cadastro de EXEMPLO, fictício: serve de ponto de partida e de base para os
# testes. Cada empresa troca pelo próprio em Configurações › Centros de custo.
REFERENCIA: list[tuple[str, ...]] = [
    ("80", "80.0", "80.00", "Engineering", "ENG", "ENG", "Bussines Unit"),
    ("80", "80.0", "80.20", "Documentation Team", "DOC", "ENG", "Bussines Unit"),
    ("80", "80.0", "80.20", "Managers Team", "ENG", "ENG", "Bussines Unit"),
    ("80", "80.0", "80.20", "Planning Team", "ENG", "ENG", "Bussines Unit"),
    ("80", "80.0", "80.30", "Automation and Instrumentation Engineering", "INS", "ENG", "Bussines Unit"),
    ("80", "80.0", "80.30", "Electrical Engineering", "EFC", "ENG", "Bussines Unit"),
    ("80", "80.0", "80.30", "Mechanical Engineering", "MEC", "ENG", "Bussines Unit"),
    ("80", "80.0", "80.30", "Process Engineering", "PRO", "ENG", "Bussines Unit"),

    ("81", "81.0", "81.00", "Pulp & Paper", "P&P", "P&P", "Bussines Unit"),
    ("81", "81.0", "81.10", "Account Managers", "COM", "P&P", "Bussines Unit"),
    ("81", "81.0", "81.20", "Managers Team", "P&P", "P&P", "Bussines Unit"),
    ("81", "81.0", "81.30", "Hardware Design Team", "HDT", "P&P", "Bussines Unit"),
    ("81", "81.0", "81.40", "Software Team", "SCA", "P&P", "Bussines Unit"),

    ("82", "82.0", "82.00", "Food & Beverage", "F&B", "F&B", "Bussines Unit"),
    ("82", "82.0", "82.10", "Account Managers", "COM", "F&B", "Bussines Unit"),
    ("82", "82.0", "82.20", "Managers Team", "F&B", "F&B", "Bussines Unit"),
    ("82", "82.0", "82.30", "Hardware Design Team", "HDT", "F&B", "Bussines Unit"),
    ("82", "82.0", "82.40", "Software Team", "SCA", "F&B", "Bussines Unit"),

    ("83", "83.0", "83.00", "Gestão de TIC's", "OTC", "OTC", "Bussines Unit"),
    ("83", "83.0", "83.30", "Cybersecurity", "OTC", "OTC", "Bussines Unit"),
    ("83", "83.0", "83.30", "Infrastructure", "OTC", "OTC", "Bussines Unit"),
    ("83", "83.0", "83.40", "Software Team", "OTC", "OTC", "Bussines Unit"),

    ("87", "87.0", "87.30", "PPC (Production Planning and Control)", "PPC", "PMO", "Bussines Unit"),
    ("87", "87.0", "87.40", "SPC (Service Planning and Control)", "SPC", "PMO", "Bussines Unit"),

    ("88", "88.0", "88.20", "Management Team", "PFD", "PFD", "Bussines Unit"),
    ("88", "88.0", "88.30", "Electrical Control Team", "PFD", "PFD", "Bussines Unit"),
    ("88", "88.0", "88.30", "Hardware Design Team", "HDT", "PFD", "Bussines Unit"),
    ("88", "88.0", "88.50", "Field Services", "SRV", "PFD", "Bussines Unit"),

    ("89", "89.0", "89.00", "New Ventures", "NVT", "NVT", "Bussines Unit"),
    ("89", "89.0", "89.20", "Managers Team", "NVT", "NVT", "Bussines Unit"),
    ("89", "89.0", "89.30", "Hardware Design Team", "NVT", "NVT", "Bussines Unit"),

    ("90", "90.0", "90.00", "Board Staff", "DIR", "DIR", "Diretoria"),
    ("90", "90.0", "90.10", "Board", "DIR", "DIR", "Diretoria"),

    ("91", "91.0", "91.00", "Human Resources", "RH", "RH", "Suport Team"),
    ("92", "92.0", "92.00", "Marketing", "MKT", "MKT", "Suport Team"),

    ("94", "94.0", "94.00", "Procurement", "SUP", "SUP", "Suport Team"),
    ("94", "94.0", "94.10", "Purchasing", "SUP", "SUP", "Suport Team"),
    ("94", "94.0", "94.20", "Logistics", "SUP", "SUP", "Suport Team"),

    ("95", "95.0", "95.00", "Quality, Health, Safety, Environment", "SGQ", "SGQ", "Suport Team"),
    ("95", "95.0", "95.20", "Safety", "SGQ", "SGQ", "Suport Team"),

    ("96", "96.0", "96.10", "Controlling", "CON", "CON", "Suport Team"),
    ("96", "96.0", "96.30", "Warehouse", "ALM", "ALM", "Suport Team"),
    ("96", "96.0", "96.40", "Billing", "CON", "CON", "Suport Team"),

    ("97", "97.0", "97.00", "Finance", "FIN", "FIN", "Suport Team"),
]

CAMPOS = ("logico", "n2", "n3", "departamento", "n5", "vertical", "tipo")
COLUNAS = [
    ("logico", "LogicalCC", 74), ("n2", "N2", 74), ("n3", "N3", 78),
    ("departamento", "Departamento", 0), ("n5", "N5", 66),
    ("vertical", "Vertical", 78), ("tipo", "Tipo", 130),
]
TIPOS_CC = ("Bussines Unit", "Diretoria", "Suport Team")

# Erros de digitação da coluna Departamento da planilha de pessoas. Corrigir na
# leitura, e não na exibição, é o que impede o nome errado de continuar viajando
# para o card, a tabela, o filtro, o CSV e o PDF — e de voltar na próxima carga.
# A grafia certa vem do cadastro de CC, que é a autoridade sobre o vocabulário;
# `Environment` é a única que o cadastro não tem linha própria (o CC 95.30 não
# existe lá), mas é o E de "Quality, Health, Safety, Environment".
CORRECOES_DEPARTAMENTO = {
    "Enviroment": "Environment",
    "Pulp & Papper": "Pulp & Paper",
}


def corrigir_departamento(nome: str) -> str:
    return CORRECOES_DEPARTAMENTO.get(str(nome or "").strip(), str(nome or "").strip())


def registro(logico="", n2="", n3="", departamento="", n5="", vertical="",
             tipo="", ativo=True) -> dict:
    return {"logico": logico, "n2": n2, "n3": n3, "departamento": departamento,
            "n5": n5, "vertical": vertical, "tipo": tipo, "ativo": bool(ativo)}


def referencia() -> list[dict]:
    return [registro(*linha) for linha in REFERENCIA]


def chave(n3: str, departamento: str) -> str:
    """(N3, Departamento) — nem o codigo nem o nome identificam sozinhos."""
    return f"{str(n3).strip()}|{sem_acento(departamento)}"


def n3_de(n4: str) -> str:
    """80.31 -> 80.30. O N4 identifica a equipe dentro do grupo N3."""
    n4 = str(n4 or "").strip()
    if len(n4) >= 2 and n4[-1].isdigit():
        return n4[:-1] + "0"
    return n4


def normalizar(centros: list[dict]) -> list[dict]:
    """Preenche o que e derivavel, remove linha sem chave e ordena."""
    saida, vistos = [], set()
    for c in centros:
        r = registro(**{k: c.get(k, "") for k in CAMPOS},
                     ativo=c.get("ativo", True))
        r["n3"] = str(r["n3"]).strip()
        # Toda lista de CC passa por aqui — carga, edição e descoberta. É o
        # ponto que repara também o que já foi gravado com a grafia errada.
        r["departamento"] = corrigir_departamento(r["departamento"])
        if not r["n3"] and not r["departamento"]:
            continue
        if not r["n2"] and r["n3"]:
            r["n2"] = r["n3"][:-2] + "0" if len(r["n3"]) > 2 else r["n3"]
        if not r["logico"] and r["n2"]:
            r["logico"] = r["n2"].split(".")[0]
        k = chave(r["n3"], r["departamento"])
        if k in vistos:
            continue
        vistos.add(k)
        saida.append(r)
    return sorted(saida, key=lambda c: (c["n3"], sem_acento(c["departamento"])))


# ---------------------------------------------------------------------------
# RESOLUCAO  unidade -> centro de custo
# ---------------------------------------------------------------------------
def indices(centros: list[dict]) -> dict:
    """Tres indices, do mais especifico ao mais tolerante."""
    por_chave, por_depto, por_n3 = {}, {}, {}
    for c in centros:
        if not c.get("ativo", True):
            continue
        por_chave.setdefault(chave(c["n3"], c["departamento"]), c)
        por_depto.setdefault(sem_acento(c["departamento"]), c)
        por_n3.setdefault(c["n3"], c)
    return {"chave": por_chave, "depto": por_depto, "n3": por_n3}


def resolver(centro_custo: str, area: str, ix: dict) -> tuple[dict | None, str]:
    """Devolve (registro, como_casou).

    A planilha de pessoas e o cadastro de CC sao mantidos por gente diferente:
    "Pulp & Papper" na primeira e "Pulp & Paper" no segundo. Por isso a
    resolucao tem degraus, e o degrau usado e devolvido — a tela mostra quantas
    unidades cairam em cada um, que e o unico jeito de a divergencia aparecer.
    """
    n3 = n3_de(centro_custo)
    exato = ix["chave"].get(chave(n3, area))
    if exato:
        return exato, "exato"
    por_depto = ix["depto"].get(sem_acento(area))
    if por_depto:
        return por_depto, "departamento"
    por_n3 = ix["n3"].get(n3)
    if por_n3:
        return por_n3, "n3"
    return None, "sem correspondência"


def mapear(unidades, centros: list[dict]) -> dict[str, dict]:
    """uid -> {vertical_negocio, n5, tipo_cc, n3, departamento_cc, casamento}."""
    ix = indices(centros)
    saida: dict[str, dict] = {}
    for uid, u in unidades.items():
        if not (u.centro_custo or u.area):
            continue
        c, como = resolver(u.centro_custo, u.area, ix)
        saida[uid] = {
            "vertical_negocio": c["vertical"] if c else "",
            "n5": c["n5"] if c else "",
            "tipo_cc": c["tipo"] if c else "",
            "n3": c["n3"] if c else n3_de(u.centro_custo),
            "departamento_cc": c["departamento"] if c else "",
            "casamento": como,
        }
    return saida


def conciliar(unidades, centros: list[dict]) -> dict:
    """Relatorio de cobertura: o que casou, como, e o que ficou de fora."""
    mapa = mapear(unidades, centros)
    por_como: dict[str, int] = {}
    for m in mapa.values():
        por_como[m["casamento"]] = por_como.get(m["casamento"], 0) + 1

    ix = indices(centros)
    orfas = sorted({(u.centro_custo, u.area) for uid, u in unidades.items()
                    if uid in mapa and mapa[uid]["casamento"] == "sem correspondência"})
    usados = {chave(m["n3"], m["departamento_cc"]) for m in mapa.values()
              if m["departamento_cc"]}
    ociosos = [c for c in centros
               if chave(c["n3"], c["departamento"]) not in usados]
    # Linha em uso mas sem N5 / vertical / tipo: nao e erro, e pendencia — e
    # so a tela mostrando isso o operador descobre que falta preencher.
    incompletas = [c for c in centros
                   if chave(c["n3"], c["departamento"]) in usados
                   and not all(c[k] for k in ("n5", "vertical", "tipo"))]
    return {"total": len(mapa), "por_casamento": por_como, "orfas": orfas,
            "ociosos": ociosos, "incompletas": incompletas,
            "cobertura": len(mapa) - len(
                [1 for m in mapa.values() if m["casamento"] == "sem correspondência"])}


def _heranca_do_tronco(centros: list[dict]) -> dict[str, tuple[str, str]]:
    """N2 -> (vertical, tipo) mais frequentes no tronco.

    A vertical e quase uma propriedade do tronco: todo 80.* e ENG, todo 81.* e
    P&P. Quase — 96.30 (Warehouse/ALM) convive com 96.* (CON). Por isso e
    palpite de preenchimento, editavel, e nao regra de derivacao.
    """
    contagem: dict[str, dict] = {}
    for c in centros:
        if not c["n2"]:
            continue
        alvo = contagem.setdefault(c["n2"], {"vertical": {}, "tipo": {}})
        for campo in ("vertical", "tipo"):
            if c[campo]:
                alvo[campo][c[campo]] = alvo[campo].get(c[campo], 0) + 1
    return {n2: (max(v["vertical"], key=v["vertical"].get, default=""),
                 max(v["tipo"], key=v["tipo"].get, default=""))
            for n2, v in contagem.items()}


def descobrir(unidades, centros: list[dict]) -> list[dict]:
    """Acrescenta ao cadastro os pares (N3, Departamento) que a estrutura usa
    e o cadastro ainda nao conhece. Nao apaga nem sobrescreve o que existe.

    A linha nova herda vertical e tipo do tronco N2, quando ha maioria clara.
    O N5 fica em branco de proposito: e mnemonico da equipe, nao ha de onde
    tirar, e branco e o unico jeito honesto de dizer "falta preencher".
    """
    atuais = normalizar(centros)
    vistos = {chave(c["n3"], c["departamento"]) for c in atuais}
    heranca = _heranca_do_tronco(atuais)
    for u in unidades.values():
        if not u.area:
            continue
        # Sem isto a grafia errada da planilha entra no cadastro como se fosse
        # um departamento novo — foi assim que "Enviroment" virou linha de CC.
        area = corrigir_departamento(u.area)
        n3 = n3_de(u.centro_custo)
        if not n3 or chave(n3, area) in vistos:
            continue
        vistos.add(chave(n3, area))
        vertical, tipo = heranca.get(u.vertical, ("", ""))
        atuais.append(registro(n2=u.vertical, n3=n3, departamento=area,
                               logico=(u.vertical or "").split(".")[0],
                               vertical=vertical, tipo=tipo))
    return normalizar(atuais)


def pivotar(linhas: list[dict], cadastro: list[dict]) -> tuple[list[dict], list[str]]:
    """Atualiza o cadastro com o que a planilha do RH declara, e conta o que mudou.

    A planilha traz N2, N3, N4, N5 e Departamento por PESSOA; o cadastro guarda
    isso por (N3, Departamento). Pivotar é fazer a volta: cada combinação que
    aparece na planilha vira — ou completa — uma linha do cadastro.

    Duas regras, e as duas existem para o cadastro não virar lixo:

    **N5 em branco é preenchido; N5 divergente NÃO é sobrescrito.** Preencher o
    que falta é ganho puro — era `descobrir` que deixava em branco por não ter
    de onde tirar, e agora tem. Já sobrescrever silenciosamente o que alguém
    editou na tela de Centros de custo tiraria da pessoa a decisão que a tela
    existe para dar. A divergência vira aviso.

    **Uma combinação com mais de um N5 na planilha não preenche nada.** Nesta
    base, `83.40/Software Team` pode ter gente marcada SCA e gente marcada OTC:
    escolher uma delas seria inventar, e o cadastro é por (N3, Departamento) —
    ele não tem onde guardar as duas. Vira aviso, para alguém decidir.
    """
    atuais = normalizar(cadastro)
    por_chave = {chave(c["n3"], c["departamento"]): c for c in atuais}

    # Que N5 a planilha declara para cada (N3, Departamento).
    declarados: dict[str, set[str]] = {}
    for l in linhas:
        n5 = str(l.get("n5") or "").strip()
        area = corrigir_departamento(l.get("area"))
        n3 = str(l.get("n3") or "").strip() or n3_de(l.get("centro_custo") or "")
        if n5 and n3 and area:
            declarados.setdefault(chave(n3, area), set()).add(n5)

    preenchidos, divergentes, ambiguos = [], [], []
    for k, n5s in declarados.items():
        c = por_chave.get(k)
        if c is None:
            continue                      # `descobrir` cria a linha; aqui só preenche
        if len(n5s) > 1:
            ambiguos.append(f"{c['n3']}/{c['departamento']}: {', '.join(sorted(n5s))}")
            continue
        n5 = next(iter(n5s))
        atual = str(c.get("n5") or "").strip()
        if not atual:
            c["n5"] = n5
            preenchidos.append(f"{c['n3']}/{c['departamento']} → {n5}")
        elif atual != n5:
            divergentes.append(f"{c['n3']}/{c['departamento']}: cadastro {atual}, "
                               f"planilha {n5}")

    avisos = []
    if preenchidos:
        avisos.append(_t("{n} centro(s) de custo ganharam o N5 que faltava: {quais}",
                         n=len(preenchidos), quais="; ".join(preenchidos[:5]))
                      + ("…" if len(preenchidos) > 5 else ""))
    if divergentes:
        avisos.append(_t("{n} centro(s) de custo têm N5 diferente do que a planilha "
                         "declara — o cadastro foi mantido: {quais}",
                         n=len(divergentes), quais="; ".join(divergentes[:5]))
                      + ("…" if len(divergentes) > 5 else ""))
    if ambiguos:
        avisos.append(_t("{n} combinação(ões) de N3 e departamento aparecem com mais "
                         "de um N5 na planilha, e por isso não foram preenchidas: "
                         "{quais}", n=len(ambiguos), quais="; ".join(ambiguos[:5]))
                      + ("…" if len(ambiguos) > 5 else ""))
    return normalizar(atuais), avisos


def verticais(centros: list[dict]) -> list[tuple[str, str]]:
    """(codigo, rotulo) de cada vertical de negocio, com os N2 que a compoem."""
    grupos: dict[str, set] = {}
    for c in centros:
        if c["vertical"]:
            grupos.setdefault(c["vertical"], set()).add(c["n2"])
    return [(v, f"{v} · {', '.join(sorted(n2s))}")
            for v, n2s in sorted(grupos.items())]
