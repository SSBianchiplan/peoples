"""Organograma de TESTE: 5 níveis, 28 pessoas fictícias.

Um segundo organograma registrado ao lado do principal (o sistema é
multi-organograma; o ativo continua sendo o `peoples`). Serve para demonstrar,
treinar e testar sem tocar na base de 272.

    raiz sintética "Conselho de Administração" (como na base principal)
    1 Presidência (CEO)
    3 Diretorias
    6 Gerências
    8 Coordenações
   10 Analistas / especialistas
   -- 28 pessoas, profundidade 5

    python ferramentas/organograma_teste.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from dataclasses import asdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from orga.configuracao import Config          # noqa: E402
from orga.dominio import Unidade              # noqa: E402

SLUG = "teste-5-niveis"
NOME = "Organograma Teste — 5 níveis"
DOMINIO = "gplansis.com"

# (nome, cargo, área, competências, accountabilities, vínculo, admissão)
PRESIDENCIA = ("Helena Vasconcelos Prado", "Diretora-Presidente (CEO)", "Presidência",
               ["Estratégia", "Governança", "Liderança"],
               ["Direção geral", "Relação com o conselho"], "clt", "2015-03-02")

DIRETORIAS = [
    ("Ricardo Albuquerque Neto", "Diretor de Operações", "Operações",
     ["Gestão industrial", "Lean", "PCP"], ["Resultado operacional", "Segurança"], "clt", "2016-08-15"),
    ("Camila Ferraz Duarte", "Diretora Comercial", "Comercial",
     ["Vendas B2B", "Negociação", "CRM"], ["Receita", "Carteira de clientes"], "clt", "2017-02-06"),
    ("Anderson Luz Carvalho", "Diretor de Tecnologia", "Tecnologia",
     ["Arquitetura", "Dados", "Cibersegurança"], ["Roadmap de produto", "Plataforma"], "clt", "2018-05-21"),
]

GERENCIAS = [  # (índice da diretoria, ...)
    (0, "Patrícia Moraes Lins", "Gerente de Produção", "Produção",
     ["Programação", "OEE", "Kaizen"], ["Entrega no prazo"], "clt", "2018-11-05"),
    (0, "Marcelo Andrade Reis", "Gerente de Manutenção", "Manutenção",
     ["Manutenção preditiva", "Confiabilidade"], ["Disponibilidade dos ativos"], "clt", "2019-04-01"),
    (1, "Juliana Castro Bittencourt", "Gerente de Vendas", "Vendas",
     ["Prospecção", "Propostas"], ["Meta comercial"], "clt", "2019-09-16"),
    (1, "Fernando Sales Quintela", "Gerente de Marketing", "Marketing",
     ["Marca", "Conteúdo", "Eventos"], ["Geração de demanda"], "pj", "2020-01-13"),
    (2, "Luciana Pires Tavares", "Gerente de Engenharia de Software", "Engenharia",
     ["Python", "Cloud", "DevOps"], ["Qualidade do software"], "clt", "2020-07-06"),
    (2, "Rafael Nogueira Brandão", "Gerente de Dados e IA", "Dados",
     ["Machine Learning", "SQL", "Governança de dados"], ["Plataforma de dados"], "clt", "2021-02-22"),
]

COORDENACOES = [  # (índice da gerência, ...)
    (0, "Bruno Teixeira Amaral", "Coordenador de Turno", "Produção",
     ["Liderança de equipe", "5S"], ["Turno A"], "clt", "2021-06-14"),
    (0, "Aline Guimarães Souto", "Coordenadora de Qualidade", "Qualidade",
     ["ISO 9001", "Auditoria"], ["Não conformidades"], "clt", "2021-10-04"),
    (1, "Diego Farias Montenegro", "Coordenador de Manutenção Elétrica", "Manutenção",
     ["NR-10", "Automação"], ["Plano de manutenção"], "clt", "2022-01-17"),
    (2, "Renata Lopes Figueira", "Coordenadora de Contas-Chave", "Vendas",
     ["Key account", "Contratos"], ["Grandes contas"], "clt", "2022-03-07"),
    (2, "Thiago Barros Medina", "Coordenador de Inside Sales", "Vendas",
     ["Funil", "CRM"], ["Pipeline"], "pj", "2022-08-01"),
    (3, "Gabriela Rocha Valente", "Coordenadora de Comunicação", "Marketing",
     ["Redação", "Redes sociais"], ["Presença digital"], "pj", "2023-02-13"),
    (4, "Otávio Mendes Sarmento", "Tech Lead", "Engenharia",
     ["Arquitetura", "Revisão de código"], ["Squad Plataforma"], "clt", "2023-05-08"),
    (5, "Vitória Campos Leal", "Coordenadora de Analytics", "Dados",
     ["Power BI", "Estatística"], ["Indicadores executivos"], "clt", "2023-09-11"),
]

ANALISTAS = [  # (índice da coordenação, ...)
    (0, "Caio Ribeiro Lacerda", "Operador Líder", "Produção", ["Setup", "Segurança"], [], "clt", "2024-01-08"),
    (0, "Mariana Freitas Bento", "Analista de Processos", "Produção", ["Mapeamento", "Lean"], [], "clt", "2024-03-04"),
    (1, "Eduardo Pinheiro Costa", "Inspetor de Qualidade", "Qualidade", ["Metrologia"], [], "clt", "2024-04-15"),
    (2, "Larissa Monteiro Sá", "Técnica em Automação", "Manutenção", ["CLP", "Inversores"], [], "estagio", "2025-02-03"),
    (3, "Gustavo Lima Peçanha", "Executivo de Contas", "Vendas", ["Negociação"], [], "clt", "2024-06-10"),
    (3, "Isabela Nunes Aragão", "Analista de Pré-vendas", "Vendas", ["Propostas técnicas"], [], "clt", "2024-09-02"),
    (4, "Henrique Cardoso Viana", "SDR", "Vendas", ["Prospecção"], [], "pj", "2025-01-20"),
    (5, "Sofia Azevedo Marinho", "Designer", "Marketing", ["Figma", "Identidade visual"], [], "pj", "2025-03-17"),
    (6, "Leonardo Correia Dantas", "Desenvolvedor Pleno", "Engenharia", ["Python", "FastAPI"], [], "clt", "2024-11-04"),
    (7, "Yasmin Batista Fontes", "Analista de Dados", "Dados", ["SQL", "Python"], [], "estagio", "2025-04-07")
]

CC = {"Presidência": ("10.01", "PRE"), "Operações": ("20.01", "OPE"), "Produção": ("20.02", "OPE"),
      "Manutenção": ("20.03", "OPE"), "Qualidade": ("20.04", "OPE"), "Comercial": ("30.01", "COM"),
      "Vendas": ("30.02", "COM"), "Marketing": ("30.03", "COM"), "Tecnologia": ("40.01", "TEC"),
      "Engenharia": ("40.02", "TEC"), "Dados": ("40.03", "TEC")}


def sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def uid(nome: str) -> str:
    return hashlib.sha256(f"{SLUG}:{nome}".encode()).hexdigest()[:12]


def email(nome: str) -> str:
    p = sem_acento(nome).lower().split()
    return f"{p[0]}.{p[-1]}@{DOMINIO}"


def no(codigo: int, dados, tipo: str, parent: str | None, ordem: int) -> Unidade:
    nome, cargo, area, comps, accs, vinculo, adm = dados
    cc, vert = CC[area]
    return Unidade(
        id=uid(nome), codigo=f"TST-{codigo:03d}", nome=nome, tipo=tipo, parent_id=parent,
        ordem=ordem, cargo=cargo, area=area, email=email(nome), centro_custo=cc,
        vertical=vert, vinculo=vinculo, data_inicio=adm, status="ativo",
        responsabilidades=[{"descricao": a, "origem": "propria", "delegada_para": None}
                           for a in accs],
        competencias=list(comps))


def montar() -> dict:
    unidades: list[Unidade] = []
    # A raiz é SINTÉTICA, como na base principal ("Conselho de administração"):
    # o espelho no banco só cria `org.pessoa` para quem tem pai, então uma
    # pessoa na raiz divergiria do banco a cada arranque. Abaixo dela vêm os 5
    # níveis de gente: CEO → diretorias → gerências → coordenações → analistas.
    conselho = Unidade(id=uid("Conselho de Administração"), codigo="TST-000",
                       nome="Conselho de Administração", tipo="diretoria", parent_id=None,
                       ordem=0, cargo="Conselho de administração", area="Governança",
                       responsabilidades=[{"descricao": "Governança", "origem": "propria",
                                           "delegada_para": None}])
    unidades.append(conselho)
    seq = 1
    ceo = no(seq, PRESIDENCIA, "diretoria", conselho.id, 0); unidades.append(ceo)
    dirs = []
    for i, d in enumerate(DIRETORIAS):
        seq += 1
        u = no(seq, d, "diretoria", ceo.id, i); unidades.append(u); dirs.append(u)
    gers = []
    ordem = {}
    for g in GERENCIAS:
        seq += 1
        pai = dirs[g[0]]
        o = ordem.get(pai.id, 0); ordem[pai.id] = o + 1
        u = no(seq, g[1:], "gerencia", pai.id, o); unidades.append(u); gers.append(u)
    coords = []
    for c in COORDENACOES:
        seq += 1
        pai = gers[c[0]]
        o = ordem.get(pai.id, 0); ordem[pai.id] = o + 1
        u = no(seq, c[1:], "coordenacao", pai.id, o); unidades.append(u); coords.append(u)
    for a in ANALISTAS:
        seq += 1
        pai = coords[a[0]]
        o = ordem.get(pai.id, 0); ordem[pai.id] = o + 1
        tipo = "especialista" if "Analista" in a[2] or "Técnic" in a[2] else "celula"
        unidades.append(no(seq, a[1:], tipo, pai.id, o))
    assert len(unidades) == 29, len(unidades)          # 28 pessoas + a raiz sintética

    cfg = Config()
    cfg.titulo = NOME
    cfg.tenant = "GPlanSiS|Peoples"
    ev = {"seq": 1, "quando": "2026-09-05T12:00:00+00:00",
          "ator": "ferramentas/organograma_teste.py (Administrador)", "acao": "criar",
          "entidade_id": "-", "motivo": "carga inicial do organograma de teste (5 níveis, 28 pessoas)",
          "payload": {"pessoas": 28, "niveis": 5}, "hash_anterior": "GENESIS"}
    corpo = "|".join([ev["hash_anterior"], ev["quando"], ev["ator"], ev["acao"], ev["entidade_id"],
                      ev["motivo"], json.dumps(ev["payload"], sort_keys=True, ensure_ascii=False)])
    ev["hash"] = hashlib.sha256(corpo.encode()).hexdigest()
    return {"unidades": {u.id: asdict(u) for u in unidades}, "eventos": [ev],
            "config": cfg.para_persistir(), "orientacao": "invertida",
            "orientacao_piramide": "invertida", "agrupamento": "pessoa",
            "colapsados": [], "colapso_aplicado": True, "provisionamentos": [],
            "mural": [], "assistencias": [], "acessos_log": [], "conversa": [],
            "propostas": {}, "filtros": {}}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    dados = RAIZ / "dados"
    dados.mkdir(exist_ok=True)
    estado = montar()
    (dados / f"estado-{SLUG}.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    registro = {"ativo": "peoples",
                "lista": [{"slug": "peoples", "nome": "GPlanSiS|Peoples", "criado_em": None},
                          {"slug": SLUG, "nome": NOME, "criado_em": date(2026, 9, 5).isoformat()}]}
    (dados / "organogramas.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    prof = {}
    us = estado["unidades"]
    for k, v in us.items():
        d, p = 0, v["parent_id"]
        while p:
            d += 1; p = us[p]["parent_id"]
        prof[d] = prof.get(d, 0) + 1
    print(f"{len(us) - 1} pessoas + raiz · níveis: {dict(sorted(prof.items()))} -> dados/estado-{SLUG}.json")
