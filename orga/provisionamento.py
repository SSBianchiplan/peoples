"""Provisionamento de TI — o que muda no acesso quando alguém muda de área.

Trocar de departamento raramente é só uma linha no organograma: quem sai de
Engenharia para Suprimentos perde licença de CAD e ganha licença de compras. Na
prática isso vira um chamado escrito à mão, e o que sobra é gente com acesso a
sistema de uma área onde não trabalha mais — o risco real não é a licença
esquecida, é a permissão que ficou.

O organograma **já sabe** que a mudança aconteceu. Este módulo faz dela um
pedido de provisionamento: compara o software da área antiga com o da nova e
diz, item a item, o que revogar e o que conceder.

Duas decisões que valem explicar:

**A pendência nasce fechada em conteúdo, não em referência.** O ticket guarda os
nomes de software copiados no instante da mudança. Se o catálogo for editado
depois, o pedido continua dizendo o que era verdade quando foi aberto — um
chamado que muda sozinho não é auditável.

**Revogar vem antes de conceder.** A lista sai nessa ordem de propósito: acesso
a mais é problema de segurança, acesso a menos é problema de produtividade. Os
dois importam; só um deles piora com o tempo.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

# Departamento (como está no cadastro) -> software que a área usa.
# É ponto de partida editável, não verdade: sai da leitura do organograma da
# GPlanSiS|Peoples e existe para a tela não nascer vazia.
CATALOGO_PADRAO = {
    "Electrical Engineering": ["EPLAN Electric P8", "AutoCAD", "SolidWorks Electrical"],
    "Mechanical Engineering": ["SolidWorks", "AutoCAD", "Inventor"],
    "Process Engineering": ["Aspen HYSYS", "AutoCAD P&ID"],
    "Automation and Instrumentation Engineering":
        ["TIA Portal", "Studio 5000", "Unity Pro", "PDMS"],
    "Software Team": ["Visual Studio", "Git", "TIA Portal"],
    "Software Team 1": ["Visual Studio", "Git", "TIA Portal"],
    "Software Team 2": ["Visual Studio", "Git", "TIA Portal"],
    "Software Team 3": ["Visual Studio", "Git", "TIA Portal"],
    "Hardware Design Team": ["EPLAN Electric P8", "AutoCAD"],
    "Digital Industries": ["Power BI", "Azure DevOps", "Node-RED"],
    "Cybersecurity": ["Nessus", "Wireshark", "Microsoft Defender"],
    "Infrastructure": ["Windows Admin Center", "Veeam", "Zabbix"],
    "Gestão de TIC's": ["Windows Admin Center", "Zabbix", "Power BI"],
    "Procurement": ["ERP · Compras", "Portal do Fornecedor"],
    "Purchasing": ["ERP · Compras", "Portal do Fornecedor"],
    "Logistics": ["ERP · Logística", "Portal do Transportador"],
    "Warehouse": ["ERP · Estoque", "Coletor WMS"],
    "Finance": ["ERP · Financeiro", "Power BI"],
    "Controlling": ["ERP · Controladoria", "Power BI"],
    "Tax & Accounting": ["ERP · Fiscal", "SPED"],
    "Billing": ["ERP · Faturamento"],
    "Human Resources": ["ERP · RH", "Portal do Colaborador"],
    "Marketing": ["Adobe Creative Cloud", "Canva", "RD Station"],
    "Quality, Health, Safety, Environment": ["ERP · Qualidade", "Power BI"],
    "Safety": ["ERP · Qualidade"],
    "Field Services": ["ERP · Serviços", "App de Campo"],
    "Managers Team": ["Power BI", "ERP · Gestão"],
    "Management Team": ["Power BI", "ERP · Gestão"],
}

# Todo mundo tem, em qualquer área: não entra nem sai de pedido nenhum.
BASE_COMUM = ["Microsoft 365", "Teams", "GPlanSiS|Peoples"]

ABERTA, CONCLUIDA = "aberta", "concluída"


def catalogo_padrao() -> list[dict]:
    return [{"area": area, "softwares": lista}
            for area, lista in sorted(CATALOGO_PADRAO.items())]


def normalizar(catalogo: list[dict] | None) -> list[dict]:
    """Uma linha por área, sem duplicata e sem software em branco."""
    saida, vistas = [], set()
    for linha in catalogo or []:
        area = str(linha.get("area", "")).strip()
        if not area or area in vistas:
            continue
        vistas.add(area)
        itens = linha.get("softwares")
        if isinstance(itens, str):
            itens = [p.strip() for p in itens.split(",")]
        itens = [str(s).strip() for s in (itens or []) if str(s).strip()]
        saida.append({"area": area, "softwares": sorted(dict.fromkeys(itens))})
    return sorted(saida, key=lambda x: x["area"].lower())


def indexar(catalogo: list[dict]) -> dict[str, list[str]]:
    return {c["area"]: c["softwares"] for c in normalizar(catalogo)}


def diferenca(indice: dict, de: str, para: str) -> tuple[list[str], list[str]]:
    """(revogar, conceder). O que está nas duas áreas não se mexe.

    Software comum às duas pontas ficaria numa lista de revogar e noutra de
    conceder — TI tiraria e devolveria o mesmo acesso no mesmo chamado.
    """
    antes = set(indice.get(de, [])) - set(BASE_COMUM)
    depois = set(indice.get(para, [])) - set(BASE_COMUM)
    return sorted(antes - depois), sorted(depois - antes)


def abrir(u, de: str, para: str, indice: dict, por: str = "") -> dict | None:
    """Pedido de provisionamento, ou None quando não há o que pedir.

    Duas razões para não abrir, e a segunda é a que importa:

    1. Sem diferença de software não há pedido — chamado vazio ensina a
       ignorar a fila.
    2. **Destino sem catálogo não abre pedido.** Sem entrada para a área nova,
       a diferença seria "revogar tudo, conceder nada" — e TI cortaria o acesso
       de alguém porque ninguém mapeou o departamento de destino. A falta
       aparece como aviso na tela (`areas_sem_catalogo`), não como revogação.
    """
    if para not in indice:
        return None
    revogar, conceder = diferenca(indice, de, para)
    if not revogar and not conceder:
        return None
    return {
        "id": uuid.uuid4().hex[:12],
        "unidade_id": u.id,
        "codigo": u.codigo,
        "pessoa": u.nome,
        "email": u.email,
        "cargo": u.cargo,
        "de": de,
        "para": para,
        "revogar": revogar,
        "conceder": conceder,
        "situacao": ABERTA,
        "aberta_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "concluida_em": None,
        "por": por,
    }


def abertas(fila: list[dict]) -> list[dict]:
    return [p for p in fila or [] if p.get("situacao") == ABERTA]


def concluir(fila: list[dict], pid: str, por: str = "") -> bool:
    for p in fila or []:
        if p.get("id") == pid and p.get("situacao") == ABERTA:
            p["situacao"] = CONCLUIDA
            p["concluida_em"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds")
            p["concluida_por"] = por
            return True
    return False


def destinatarios(unidades, mapa: dict) -> list[str]:
    """A quem o pedido se destina: o e-mail de quem trabalha em TI.

    Sai do próprio organograma em vez de uma lista fixa — lista fixa
    desatualiza no dia em que alguém entra ou sai da equipe, e ninguém percebe
    até um chamado não chegar.
    """
    us = unidades.values() if isinstance(unidades, dict) else unidades
    alvo = []
    for u in us:
        vertical = (mapa.get(u.id) or {}).get("vertical_negocio", "")
        if u.email and (vertical == "OTC" or "TIC" in (u.area or "")):
            alvo.append(u.email)
    return sorted(set(alvo))


def areas_sem_catalogo(unidades, indice: dict) -> list[str]:
    """Áreas em uso que ninguém mapeou. Mudar para uma delas não gera pedido —
    e o silêncio pareceria "nada a fazer"."""
    us = unidades.values() if isinstance(unidades, dict) else unidades
    return sorted({u.area for u in us if u.area and u.area not in indice})
