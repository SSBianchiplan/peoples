"""Funil institucional — a leitura de negócio do organograma.

Transcreve a estrutura da apresentação *Estrutura GPlanSiS|Peoples 2026* (960x540,
20 lâminas) e a reconcilia com os dados vivos. A apresentação declara quatro
faixas empilhadas em estádio, centradas e alargando para cima:

    Cliente                       823 px de 960   (o topo, o mais largo)
    Business Units                702 px
    Serviços Compartilhados       572 px
    Diretoria Executiva           451 px          (a base, sustentando)

É a mesma tese do organograma invertido (LAY-01): quem atende o cliente fica
em cima, a diretoria sustenta embaixo. As faixas vêm da apresentação; **os
membros de cada faixa vêm do cadastro de centros de custo**, não daqui — um
slide desatualizado não pode inventar uma vertical que não existe.
"""
from dataclasses import dataclass

from . import centros  # Larguras medidas nos retângulos da lâmina, como fração da largura útil.
LARGURAS = (0.857, 0.731, 0.596, 0.470)


@dataclass(frozen=True)
class Banda:
    chave: str
    rotulo: str
    largura: float
    tipo_cc: str      # o `tipo` do cadastro de CC que alimenta a faixa
    legenda: str


BANDAS = (
    Banda("cliente", "Cliente", LARGURAS[0], "",
          "A razão da estrutura: tudo abaixo existe para atendê-lo."),
    Banda("negocio", "Business Units", LARGURAS[1], "Bussines Unit",
          "Verticais que entregam ao cliente."),
    Banda("apoio", "Serviços Compartilhados", LARGURAS[2], "Suport Team",
          "Áreas administrativas que sustentam as verticais."),
    Banda("diretoria", "Diretoria Executiva", LARGURAS[3], "Diretoria",
          "A base que sustenta o conjunto."),
)

# O que a estrutura declara em cada faixa, na ordem em que as lâminas as
# apresentam — que é a ordem de tamanho, da maior para a menor.
#
# Atualizado a partir do estado do sistema, e não da lâmina de 2026: **P&M
# virou PFD**, e **OTC passou a ser vertical própria**. Enquanto o
# deck dizia P&M, a tela acusava quatro divergências que não eram erro de
# ninguém — eram a apresentação falando de uma empresa que já tinha mudado.
#
# Esta lista continua sendo a estrutura PRETENDIDA, e é isso que dá sentido à
# comparação: quando o cadastro ganhar uma vertical que ninguém declarou, a
# tela volta a acusar. Deixá-la seguir o cadastro sozinha seria trocar um
# alarme por um espelho.
DECK = {
    "negocio": ("ENG", "PFD", "F&B", "P&P", "OTC", "NVT"),
    "apoio": ("CON", "RH", "SPC", "SUP", "ALM", "FIN", "SGQ", "MKT"),
    "diretoria": ("DIR",),
}

# Sigla do cadastro -> como a apresentação chama a mesma coisa. PFD e OTC saem
# daqui: eram apelidos de quando não tinham faixa própria, e agora a estrutura
# as chama pela sigla — o selo "Painéis" ao lado de PFD passou a repetir, com
# outra palavra, o que o chip já diz.
APELIDO_DECK = {"PMO": "PCO", "SUP": "Suprimentos",
                "ALM": "Almoxarifado", "CON": "Controladoria e Fiscal",
                "FIN": "Financeiro", "RH": "Recursos Humanos", "MKT": "Marketing",
                "SGQ": "Qualidade e SST"}

NOMES = {"ENG": "Engenharia", "P&P": "Pulp & Paper", "F&B": "Food & Beverage",
         "NVT": "New Ventures", "OTC": "Gestão de TIC's",
         "PFD": "Painéis e Field Devices", "PMO": "Planejamento e Controle",
         "DIR": "Diretoria", "RH": "Recursos Humanos", "MKT": "Marketing",
         "SUP": "Suprimentos", "SGQ": "Qualidade, Saúde e Segurança",
         "CON": "Controladoria e Fiscal", "ALM": "Almoxarifado",
         "FIN": "Financeiro",
         "SPC": "Planej. e Controle de Serviços",
         "PPC": "Planej. e Controle da Produção",
         "FAT": "Qualidade Técnica"}

# Departamento como está no cadastro (inglês) -> nome usado na apresentação.
# A apresentação é o vocabulário oficial em português; o cadastro é o dado.
ROTULO_PT = {
    "Managers Team": "Gestão", "Management Team": "Gestão",
    "Specialists": "Especialistas", "Digital Industries": "Indústrias Digitais",
    "Process Engineering": "Engenharia de Processos",
    "Engenharia de Processos": "Engenharia de Processos",
    "Mechanical Engineering": "Engenharia Mecânica",
    "Electrical Engineering": "Engenharia Elétrica",
    "Civil Engineering": "Engenharia Civil",
    "Automation and Instrumentation Engineering": "Engenharia EIA",
    "Documentation Team": "Gestão e Documentação",
    "Planning Team": "Planejamento",
    "Account Managers": "Técnico Comercial",
    "Hardware Design Team": "Projetos de Painéis",
    "Software Team": "Automação", "Software Team 1": "Automação 1",
    "Software Team 2": "Automação 2", "Software Team 3": "Automação 3",
    "Solution Analysts": "Analistas de Solução",
    "Pre-Engineering": "Pré-Engenharia", "Estimating Team": "Orçamentos",
    "Field Services": "Serviços de Campo", "Mechanical Team": "Montagem Mecânica",
    "Electrical Control Team": "Montagem Elétrica — Controle",
    "Electrical Power Team": "Montagem Elétrica — Potência",
    "Small Panels": "Gavetas e Pequenos Painéis",
    "Mechanical Protection": "Proteção Mecânica", "Devices Team": "Dispositivos",
    "Tools & Kanban": "Ferramentaria e Kanban",
    "New Ventures": "P&D", "Cybersecurity": "Cibersegurança",
    "Infrastructure": "Infraestrutura", "Gestão de TIC's": "Gestão de TIC's",
    "PPC (Production Planning and Control)": "PCP — Planej. e controle da produção",
    "SPC (Service Planning and Control)": "PCS — Planej. e controle de serviços",
    "FAT (Factory Acceptance Test)": "QTC — Qualidade técnica",
    "Warehouse": "Almoxarifado",
    "Purchasing": "Compras", "Procurement": "Suprimentos",
    "Logistics": "Logística", "Expediting": "Expedição",
    "Human Resources": "Recursos Humanos", "Finance": "Financeiro",
    "Controlling": "Controladoria", "Tax & Accounting": "Fiscal e Contábil",
    "Tax validation": "Validação Fiscal", "Billing": "Faturamento",
    "Marketing": "Marketing", "Safety": "Segurança do Trabalho",
    "Quality, Health, Safety, Environment": "Qualidade e SST",
    "Board": "Diretoria", "Board Staff": "Assessoria da Diretoria",
    "Engineering": "Engenharia", "Food & Beverage": "Food & Beverage",
    "Pulp & Paper": "Pulp & Paper",
    # Departamentos que a apresentação não nomeia, mas que existem na base.
    "Environment": "Meio Ambiente",
    "PFD": "Painéis e Field Devices",
    # Três pessoas têm como departamento a própria sigla da vertical — é assim
    # que o RH cadastra quem responde pela vertical inteira e não por uma
    # equipe dentro dela. Sem estas linhas a tela acusava "departamento sem
    # nome em português" apontando para uma sigla que já É o nome.
    "P&P": "Pulp & Paper",
    "OTC": "Gestão de TIC's",
    "Governança corporativa": "Governança corporativa",
}


# Espanhol dos mesmos departamentos. Falta aqui cai no português, e não no nome
# cru: entre "Gestão" e "Managers Team", quem lê espanhol entende o primeiro.
ROTULO_ES = {
    "Managers Team": "Gestión", "Management Team": "Gestión",
    "Specialists": "Especialistas",
    "Digital Industries": "Industrias Digitales",
    "Process Engineering": "Ingeniería de Procesos",
    "Engenharia de Processos": "Ingeniería de Procesos",
    "Mechanical Engineering": "Ingeniería Mecánica",
    "Electrical Engineering": "Ingeniería Eléctrica",
    "Civil Engineering": "Ingeniería Civil",
    "Automation and Instrumentation Engineering": "Ingeniería EIA",
    "Documentation Team": "Gestión y Documentación",
    "Planning Team": "Planificación",
    "Account Managers": "Técnico Comercial",
    "Hardware Design Team": "Proyectos de Tableros",
    "Software Team": "Automatización", "Software Team 1": "Automatización 1",
    "Software Team 2": "Automatización 2", "Software Team 3": "Automatización 3",
    "Solution Analysts": "Analistas de Soluciones",
    "Pre-Engineering": "Preingeniería", "Estimating Team": "Presupuestos",
    "Field Services": "Servicios de Campo",
    "Mechanical Team": "Montaje Mecánico",
    "Electrical Control Team": "Montaje Eléctrico — Control",
    "Electrical Power Team": "Montaje Eléctrico — Potencia",
    "Small Panels": "Gavetas y Tableros Pequeños",
    "Mechanical Protection": "Protección Mecánica",
    "Devices Team": "Dispositivos",
    "Tools & Kanban": "Herramental y Kanban",
    "New Ventures": "I+D",
    "Cybersecurity": "Ciberseguridad", "Infrastructure": "Infraestructura",
    "OTC": "Gestión de TIC", "P&P": "Pulp & Paper",
    "Gestão de TIC's": "Gestión de TIC",
    "PPC (Production Planning and Control)":
        "PCP — Planif. y control de la producción",
    "SPC (Service Planning and Control)":
        "PCS — Planif. y control de servicios",
    "FAT (Factory Acceptance Test)": "QTC — Calidad técnica",
    "Warehouse": "Almacén",
    "Purchasing": "Compras", "Procurement": "Abastecimiento",
    "Logistics": "Logística", "Expediting": "Expedición",
    "Human Resources": "Recursos Humanos", "Finance": "Finanzas",
    "Controlling": "Contraloría", "Tax & Accounting": "Fiscal y Contable",
    "Tax validation": "Validación Fiscal", "Billing": "Facturación",
    "Marketing": "Marketing", "Safety": "Seguridad Laboral",
    "Quality, Health, Safety, Environment": "Calidad y SST",
    "Board": "Directorio", "Board Staff": "Asesoría del Directorio",
    "Engineering": "Ingeniería", "Environment": "Medio Ambiente",
    "PFD": "Tableros y Field Devices",
    "Governança corporativa": "Gobernanza corporativa",
}

# Inglês só onde o cadastro está em português — o resto já é o próprio nome.
ROTULO_EN = {
    "Engenharia de Processos": "Process Engineering",
    "Gestão de TIC's": "IT Management",
    "Governança corporativa": "Corporate Governance",
    "PFD": "Panels and Field Devices",
}


def rotulo_pt(departamento: str) -> str:
    """O nome em português, já com a grafia corrigida.

    A correção entra aqui também — e não só na carga — porque um estado gravado
    antes da correção continua trazendo a grafia velha, e ela não pode
    reaparecer na tela só porque o dado é antigo.
    """
    nome = centros.corrigir_departamento(departamento)
    return ROTULO_PT.get(nome, nome)


def rotulo(departamento: str, idioma: str = "pt-BR") -> str:
    """O nome do departamento no idioma da interface.

    Departamento é **dado do cliente**, não interface — por isso não passa pelo
    catálogo de strings. Mas o cadastro está em inglês e a apresentação
    institucional deu nome em português a cada um; exibir "Managers Team" para
    quem escolheu português seria descartar esse trabalho. A regra:

        en-US  → o nome do cadastro, que já é inglês (salvo os que não são)
        pt-BR  → o nome da apresentação
        es     → o espanhol, caindo no português antes de cair no nome cru
    """
    nome = centros.corrigir_departamento(departamento)
    if idioma == "en-US":
        return ROTULO_EN.get(nome) or nome
    if idioma == "es":
        return ROTULO_ES.get(nome) or ROTULO_PT.get(nome) or nome
    return ROTULO_PT.get(nome, nome)


def _vertical_de(u, mapa: dict) -> str:
    return ((mapa.get(u.id) or {}).get("vertical_negocio") or u.vertical or "")


def _tipo_de(u, mapa: dict) -> str:
    return (mapa.get(u.id) or {}).get("tipo_cc") or ""


def funil(unidades, mapa: dict) -> list[dict]:
    """As quatro faixas, com os membros que o cadastro de fato tem."""
    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    faixas = []
    for b in BANDAS:
        membros: dict[str, int] = {}
        for u in us:
            if b.tipo_cc and _tipo_de(u, mapa) == b.tipo_cc:
                membros[_vertical_de(u, mapa)] = membros.get(_vertical_de(u, mapa), 0) + 1
        chips = [{"sigla": s, "nome": NOMES.get(s, s), "deck": APELIDO_DECK.get(s),
                  "pessoas": n} for s, n in sorted(membros.items(),
                                                   key=lambda kv: (-kv[1], kv[0]))]
        faixas.append({"chave": b.chave, "rotulo": b.rotulo, "largura": b.largura,
                       "legenda": b.legenda, "chips": chips,
                       "pessoas": sum(c["pessoas"] for c in chips)})
    faixas[0]["pessoas"] = sum(f["pessoas"] for f in faixas[1:])
    return faixas


def vertical(unidades, mapa: dict, sigla: str, idioma: str = "pt-BR") -> dict:
    """Departamentos de uma vertical, no vocabulário da apresentação."""
    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    dentro = [u for u in us if _vertical_de(u, mapa) == sigla]
    deps: dict[str, list] = {}
    for u in dentro:
        deps.setdefault(u.area or "—", []).append(u)
    lista = [{"departamento": d, "rotulo": rotulo(d, idioma), "pessoas": len(v),
              # a grafia corrigida é que decide, senão `Enviroment` continuaria
              # marcado como sem tradução mesmo já exibindo "Meio Ambiente"
              "traduzido": centros.corrigir_departamento(d) in ROTULO_PT}
             for d, v in sorted(deps.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    return {"sigla": sigla, "nome": NOMES.get(sigla, sigla),
            "deck": APELIDO_DECK.get(sigla), "pessoas": len(dentro),
            "departamentos": lista}


def pessoas(unidades, mapa: dict, sigla: str, departamento: str) -> list:
    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    dentro = [u for u in us
              if _vertical_de(u, mapa) == sigla and (u.area or "—") == departamento]
    return sorted(dentro, key=lambda u: (u.cargo or "zzz", u.nome))


def divergencias(unidades, mapa: dict, idioma: str = "pt-BR") -> list[dict]:
    """Onde a apresentação de 2026 e o cadastro vigente discordam.

    Não é erro de nenhum dos dois: a lâmina é a estrutura pretendida e o
    cadastro é a vigente. O que não pode é a diferença ficar invisível.

    Traduz aqui, e não no template, porque cada achado é uma frase montada com
    contagem e nome: o template receberia texto pronto e não teria como
    parametrizar.
    """
    from . import idiomas
    def t(texto, **p):
        return idiomas.traduzir(texto, idioma, **p)

    faixas = {f["chave"]: f for f in funil(unidades, mapa)}
    achados = []

    vivos = {c["sigla"] for c in faixas["negocio"]["chips"]}
    nomes_deck = {APELIDO_DECK.get(s, s) for s in vivos}
    for declarado in DECK["negocio"]:
        if declarado not in vivos and declarado not in nomes_deck:
            achados.append({"nivel": "falta", "onde": t("Business Units"),
                            "o_que": declarado,
                            "detalhe": t("declarada na apresentação, ausente no "
                                         "cadastro de centros de custo")})
    for c in faixas["negocio"]["chips"]:
        nome = c["deck"] or c["sigla"]
        if nome not in DECK["negocio"] and c["sigla"] not in DECK["negocio"]:
            achados.append({"nivel": "extra", "onde": t("Business Units"),
                            "o_que": f"{c['sigla']} · {c['nome']}",
                            "detalhe": t("{n} pessoa(s) no cadastro, sem faixa "
                                         "própria na apresentação",
                                         n=c["pessoas"])})

    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    # A raiz fica de fora: `Board` é nó sintético, materializado porque a SPEC
    # exige raiz única (RF-03), e não tem centro de custo por decisão de carga.
    # Acusá-la aqui é alarme que nunca apaga — e alarme que nunca apaga ensina
    # a ignorar o painel inteiro.
    sem = [u for u in us if u.parent_id is not None and not _tipo_de(u, mapa)]
    if sem:
        achados.append({"nivel": "atencao", "onde": t("Classificação"),
                        "o_que": t("{n} pessoa(s) fora das faixas", n=len(sem)),
                        "detalhe": t("centro de custo não resolve para um tipo "
                                     "(Business Unit, Suport Team ou Diretoria)")})

    # Grafias corrigidas: quem lê a tela precisa saber que o nome exibido não é
    # o que está na planilha, senão procura por "Environment" e não acha.
    corrigidos = sorted({u.area for u in us
                         if u.area in centros.CORRECOES_DEPARTAMENTO})
    if corrigidos:
        achados.append({
            "nivel": "corrigido", "onde": t("Grafia"),
            "o_que": t("{n} nome(s) corrigido(s) na leitura", n=len(corrigidos)),
            "detalhe": " · ".join(
                f"{c} → {centros.CORRECOES_DEPARTAMENTO[c]}" for c in corrigidos)
            + t(" — corrija também na planilha, senão a próxima carga repete")})

    crus = sorted({rotulo_pt(u.area) for u in us
                   if u.area and rotulo_pt(u.area) not in ROTULO_PT.values()})
    if crus:
        achados.append({"nivel": "atencao", "onde": t("Vocabulário"),
                        "o_que": t("{n} departamento(s) sem nome em português",
                                   n=len(crus)),
                        "detalhe": ", ".join(crus[:6])
                                   + ("…" if len(crus) > 6 else "")})
    return achados
