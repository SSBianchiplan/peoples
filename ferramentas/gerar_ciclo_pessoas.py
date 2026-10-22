"""Ciclo de gente 2026, gerado a partir dos Skills — para TODOS os organogramas.

A regra é a hierarquia: cada liderado conversa com o seu líder direto (o pai na
árvore), e é o líder que registra. A partir da ficha Skills do cargo de cada
pessoa (família, senioridade, papel, competências com nível esperado), o
gerador produz, de forma determinística e reproduzível:

  1. **Accountabilities** — exatamente 5 PRÓPRIAS por pessoa, extraídas das
     responsabilidades do Skills do cargo (as delegadas, que o sistema deriva
     das equipes, são preservadas).
  2. **Conversas de Valor** (GEP-FOR-006) — três ciclos de 2026 por pessoa:
     Completa (mar/abr, realizada), Check-in 1 (jul, realizada) e Check-in 2
     (nov, agendada). Entregas, aderência aos quatro valores, PDI (três
     competências-gap do Skills, regra 70/20/10), expectativa de carreira (a
     trilha do Skills) e o feedback do liderado à liderança (GEP-FOR-005).
  3. **Avaliação** (GEP-FOR-004, 9-box) — risco × impacto de perda, prontidão
     de sucessão e ação para o Comitê, com o texto rico (trajetória, formações,
     perfil, performance, bem-estar, ferramentas, inglês, trilha, valores).
  4. **Avaliação Mestre** (pesquisa de clima) — 100% de participação: uma
     resposta ANÔNIMA por pessoa na pesquisa anual (60 afirmações) e no pulso
     (15), com estratos derivados da estrutura (nunca a identidade), modelo de
     trabalho e abertas; e a programação do ciclo.

Nada aqui é opinião sobre pessoas reais: a base é fictícia, e o conteúdo é
função do CARGO (Skills), do tempo de casa e de um sorteio com semente fixa.

    python ferramentas/gerar_ciclo_pessoas.py            # só o que falta
    python ferramentas/gerar_ciclo_pessoas.py --forcar   # regrava tudo

Roda também no servidor, com o serviço parado, sobre `dados/`.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from orga import cgv as cgvmod                   # noqa: E402
from orga import dcr as dcrmod                   # noqa: E402
from orga import dominio                         # noqa: E402
from orga import gptw as gptwmod                 # noqa: E402
from orga import organogramas                    # noqa: E402
from orga import talentos as talmod              # noqa: E402
import gerar_skills as gs                        # noqa: E402

ANO = 2026
HOJE = date(2026, 9, 6)
SEMENTE = 20260906


def h(*partes) -> int:
    return int(hashlib.sha256("|".join(str(p) for p in partes).encode()).hexdigest()[:12], 16)


def escolha(seq, *chave):
    return seq[h(*chave) % len(seq)]


def _corpo_evento(anterior: str, ev: dict) -> str:
    return "|".join([anterior, ev["quando"], ev["ator"], ev["acao"], ev["entidade_id"],
                     ev["motivo"], json.dumps(ev["payload"], sort_keys=True, ensure_ascii=False)])


def primeiro_nome(nome: str) -> str:
    return (nome or "").split()[0] if nome else ""


# =============================================================================
# 1. ACCOUNTABILITIES — 5 próprias por pessoa, do Skills do cargo
# =============================================================================
def accountabilities(u: dict, ficha: dict, n_liderados: int) -> list[dict]:
    base = [r for r in dcrmod.itens(ficha["responsabilidades"])
            if not r.startswith(("Cumprir as normas", "Registrar o trabalho"))]
    if n_liderados:
        base.insert(0, f"Conduzir Conversas de Valor e PDI com {n_liderados} liderado(s) direto(s)")
    # Rotação determinística por pessoa: pares do mesmo cargo não ficam idênticos.
    k = h(u["id"], "acc") % max(1, len(base))
    girado = base[k:] + base[:k]
    proprias = girado[:5]
    kpis = [c[len("[KPI] "):] for c in dcrmod.itens(ficha["competencias"]) if c.startswith("[KPI]")]
    i = 0
    while len(proprias) < 5 and kpis:
        proprias.append(f"Responder pelo indicador «{kpis[i % len(kpis)]}» no seu escopo")
        i += 1
    while len(proprias) < 5:
        proprias.append("Sustentar a qualidade, a segurança e o registro das próprias entregas")
    delegadas = [r for r in (u.get("responsabilidades") or []) if r.get("origem") == "delegada"]
    return ([{"descricao": d, "origem": "propria", "delegada_para": None} for d in proprias]
            + delegadas)


# =============================================================================
# 2. CONVERSAS DE VALOR
# =============================================================================
VALORES_TXT = {
    "teamwork": ["Compartilha o que sabe e puxa o time junto nas entregas difíceis.",
                 "Colabora com outras áreas sem esperar ser chamado; é ponte, não muro.",
                 "Apoia colegas em pico de demanda e pede ajuda no tempo certo."],
    "respect": ["Escuta antes de responder e trata divergência como informação.",
                "Cumpre combinados e respeita o tempo dos outros.",
                "Acolhe quem chega e dá feedback com cuidado e clareza."],
    "innovation": ["Trouxe melhoria de processo que reduziu retrabalho no período.",
                   "Questiona o padrão quando ele não serve mais e propõe alternativa testável.",
                   "Aprende ferramenta nova e a coloca em uso rápido."],
    "ownership": ["Assume o resultado, inclusive quando o erro não foi dele.",
                  "Antecipa riscos e comunica antes de virar problema.",
                  "Fecha o que abre: entrega completa, documentada e sem pendência escondida."],
}
ATENCAO_TXT = {
    "teamwork": "Ponto de atenção: envolver os pares mais cedo nas decisões técnicas.",
    "respect": "Ponto de atenção: dosar o tom nas revisões — o conteúdo está certo, a forma pode acolher mais.",
    "innovation": "Ponto de atenção: transformar ideias em experimento com dono e prazo.",
    "ownership": "Ponto de atenção: pedir apoio antes de o prazo apertar.",
}
LIDERANCA_TXT = {
    "liderar": ["Inspira pelo exemplo e constrói confiança; poderia dar feedback com mais frequência.",
                "Cria ambiente positivo e apoia o desenvolvimento; é referência de conduta.",
                "É claro sobre valores e contrata pessoas alinhadas; às vezes falta tempo para o um a um."],
    "gerenciar": ["Estabelece expectativas claras e acompanha; delega conforme a maturidade de cada um.",
                  "Simplifica processos e remove obstáculos; o acompanhamento poderia ser mais regular.",
                  "Delega bem, mas concentra decisões em pico de projeto."],
    "responsabilizar": ["Define metas e responde pelos resultados; toma decisões difíceis quando precisa.",
                        "Assume riscos calculados e lidera as mudanças; explica o porquê das mudanças de rota.",
                        "Protege o time e responde pelo resultado; poderia envolver mais o time na estratégia."],
}
ENTREGAS_TXT = ["Entregou {a} e {b} dentro do prazo, com qualidade reconhecida pelo cliente interno.",
                "Principais contribuições: {a}; {b}. Reduziu retrabalho e melhorou o registro das entregas.",
                "Avançou em {a} e assumiu {b}; ponto forte em organização e follow-up."]
CARREIRA_TXT = ["Deseja evoluir para {p}. Combinado: consolidar as competências-gap do PDI até o fim do ano.",
                "Interesse declarado em {p}; a liderança vê aderência e vai expor a projetos de maior complexidade.",
                "Trajetória desejada: {p}. Próximo marco: liderar uma entrega ponta a ponta com autonomia."]
CHECKIN_TXT = ["Check-in: PDI em andamento — {a} concluído; {b} em curso. Nenhum desvio de prazo.",
               "Check-in: entregas do trimestre no prazo; competência «{a}» já aplicada em projeto.",
               "Check-in: ajustado o foco do PDI para «{a}»; apoio da liderança combinado."]


def gaps(ficha: dict, u: dict) -> list[str]:
    """Competências técnicas desejáveis que a pessoa não declara — o insumo do PDI."""
    declaradas = [dominio.sem_acento(c).lower() for c in (u.get("competencias") or [])]
    saida = []
    for c in dcrmod.itens(ficha["competencias"]):
        if not c.startswith("[Técnica]"):
            continue
        nome = c[len("[Técnica] "):].split(" — nível")[0]
        chave = dominio.sem_acento(nome).lower()
        if not any(d and (d in chave or chave in d) for d in declaradas):
            saida.append(nome)
    return saida or ["Aprofundamento na disciplina do cargo"]


def cgv_de(u: dict, pai: dict | None, ficha: dict, proprias: list[str]) -> list[dict]:
    ref = (u.get("codigo") or "").strip() or f"u:{u['id']}"
    nome, cargo, lider = u["nome"], u["cargo"], (pai or {}).get("nome", "")
    g = gaps(ficha, u)
    trilha = next((c for c in dcrmod.itens(ficha["competencias"]) if c.startswith("[Trilha] Próximo passo")),
                  "[Trilha] Próximo passo: próximo nível da carreira")
    proximo = trilha.split("Próximo passo: ", 1)[-1]
    a, b = proprias[0].lower(), proprias[1].lower() if len(proprias) > 1 else proprias[0].lower()
    rnd = random.Random(h(u["id"], "cgv"))
    valores = {}
    fraco = escolha(list(VALORES_TXT), u["id"], "fraco")
    for cod in VALORES_TXT:
        valores[cod] = ATENCAO_TXT[cod] if cod == fraco else escolha(VALORES_TXT[cod], u["id"], cod)
    prazos = ["até jun/2026", "até set/2026", "até dez/2026"]
    pdi = [{"comp": g[i % len(g)],
            "acao": f"70% prática em projeto real · 20% par/mentoria com referência técnica · 10% curso/certificação ({g[i % len(g)][:40]})",
            "prazo": prazos[i]} for i in range(3)]
    lideranca = {c: escolha(LIDERANCA_TXT[c], u["id"], c) for c in LIDERANCA_TXT} if pai and pai.get("parent_id") else \
                {c: "" for c in LIDERANCA_TXT}
    completa = {
        "ref": ref, "ano": ANO, "ciclo": "completa", "status": "realizada",
        "data": f"2026-0{3 + rnd.randint(0, 1)}-{rnd.randint(2, 28):02d}", "nota": "",
        "conteudo": {"entregas": escolha(ENTREGAS_TXT, u["id"], "e").format(a=a, b=b),
                     "valores": valores, "pdi": pdi,
                     "carreira": escolha(CARREIRA_TXT, u["id"], "c").format(p=proximo),
                     "lideranca": lideranca},
        "nome": nome, "cargo": cargo, "lider": lider}
    checkin1 = {
        "ref": ref, "ano": ANO, "ciclo": "checkin1", "status": "realizada",
        "data": f"2026-07-{rnd.randint(1, 31):02d}", "nota": "Check-in realizado com o líder direto.",
        "conteudo": {"entregas": escolha(CHECKIN_TXT, u["id"], "k").format(a=g[0], b=g[1 % len(g)]),
                     "valores": {c: "" for c in VALORES_TXT}, "pdi": pdi, "carreira": "",
                     "lideranca": {c: "" for c in LIDERANCA_TXT}},
        "nome": nome, "cargo": cargo, "lider": lider}
    checkin2 = {
        "ref": ref, "ano": ANO, "ciclo": "checkin2", "status": "agendada",
        "data": f"2026-11-{rnd.randint(3, 27):02d}", "nota": "Agendado pela liderança direta.",
        "conteudo": cgvmod.conteudo_vazio() if hasattr(cgvmod, "conteudo_vazio") else {},
        "nome": nome, "cargo": cargo, "lider": lider}
    return [completa, checkin1, checkin2]


# =============================================================================
# 3. AVALIAÇÃO (9-box)
# =============================================================================
PERFIL_TXT = ["Perfil analítico e organizado; comunica com clareza e entrega com consistência.",
              "Perfil colaborativo, orientado a resultado; assume responsabilidade e busca aprender.",
              "Perfil técnico, detalhista e confiável; ganha influência quando expõe mais o raciocínio.",
              "Perfil de iniciativa, resolve com autonomia e puxa o time nas entregas críticas."]
BEM_ESTAR_TXT = ["Sem sinais de sobrecarga; equilíbrio vida-trabalho preservado.",
                 "Atenção a picos de projeto: combinado revezamento em viagens.",
                 "Engajado; pediu previsibilidade de agenda para estudos."]


def talento_de(u: dict, pai: dict | None, ficha: dict, sen: str, papel: str, anos: float | None,
               proprias: list[str], cgv: dict) -> dict:
    ref = (u.get("codigo") or "").strip() or f"u:{u['id']}"
    r = h(u["id"], "tal")
    # Impacto: quem lidera ou é referência pesa mais; risco: pouco tempo de casa e
    # juniores giram mais. Um dado do sorteio evita que o cargo decida sozinho.
    impacto = "alto" if papel in ("diretoria", "gerencia", "coordenacao", "lideranca") or sen in ("especialista", "senior") \
        else ("medio" if sen == "pleno" else escolha(["medio", "baixo", "baixo"], u["id"], "imp"))
    risco = "alto" if (anos is not None and anos < 1.5 and r % 3 == 0) else \
        ("medio" if (anos is None or anos < 4 or r % 4 == 0) else "baixo")
    prontidao = {"especialista": "agora", "senior": escolha(["agora", "1ano"], u["id"], "pr"),
                 "pleno": escolha(["1ano", "2anos"], u["id"], "pr"), "junior": escolha(["2anos", "3mais"], u["id"], "pr"),
                 "aprendiz": "3mais", "apoio": "3mais", "lideranca": "1ano", "coordenacao": "1ano",
                 "gerencia": escolha(["agora", "1ano"], u["id"], "pr"), "diretoria": "agora"}[sen]
    if impacto == "alto" and risco == "alto":
        acao = "meritocracia"
    elif prontidao == "agora" and sen not in ("diretoria",):
        acao = "promocao"
    elif risco == "alto":
        acao = "rotativo"
    else:
        acao = escolha(["meritocracia", "outros", "outros"], u["id"], "ac")
    F = gs.FAMILIAS[gs.familia_de(u["cargo"])]
    tempo = f"{anos:.1f} anos de casa" if anos is not None else "tempo de casa não informado"
    ct = cgv["conteudo"]
    conteudo = {
        "idade": "",
        "trajetoria": f"{tempo}; atua como {u['cargo']} em {u.get('area') or F['nome']}. "
                      f"Principais frentes: {proprias[0].lower()}; {proprias[1].lower() if len(proprias) > 1 else ''}",
        "formacoes": "; ".join(F["formacao"]) + ". Certificações: " + "; ".join(F["certificacoes"]),
        "perfil": escolha(PERFIL_TXT, u["id"], "perfil"),
        "performance": ct["entregas"],
        "bem_estar": escolha(BEM_ESTAR_TXT, u["id"], "bem"),
        "ferramentas": ", ".join(F["ferramentas"]),
        "ingles": gs.IDIOMA[sen],
        "trilha_posicao": ct["carreira"],
        "acao_nota": {"meritocracia": "Levar ao Comitê de Meritocracia: impacto alto e risco de perda alto.",
                      "promocao": "Pronto para o próximo passo; validar vaga/orçamento com a liderança.",
                      "rotativo": "Plano de retenção e rotação de projetos para ampliar repertório.",
                      "outros": "Manter desenvolvimento pelo PDI; reavaliar no próximo ciclo."}[acao],
        "valores": ct["valores"],
    }
    return {"ref": ref, "ano": ANO, "risco_perda": risco, "impacto_perda": impacto,
            "prontidao": prontidao, "acao": acao, "conteudo": conteudo,
            "nome": u["nome"], "cargo": u["cargo"], "lider": (pai or {}).get("nome", "")}


# =============================================================================
# 4. AVALIAÇÃO MESTRE — clima, anônima, 100%
# =============================================================================
ABERTAS_POOL = {
    1: ["Do que entregamos aos clientes e da competência técnica do time.", "Da forma como resolvemos problemas difíceis juntos.",
        "De ver o organograma e os Skills claros: sei onde estou e para onde posso ir."],
    2: ["Picos de projeto que viram horas extras sem previsibilidade.", "Decisões que demoram quando envolvem mais de uma área.",
        "Ferramentas antigas em algumas rotinas administrativas."],
    3: ["Dar feedback mais frequente, não só na Conversa de Valor.", "Explicar o porquê das mudanças de rota nos projetos.",
        "Estar mais presente no dia a dia do time."],
    5: ["Recomendo: ambiente técnico forte e gente que se ajuda.", "Recomendaria com ressalva: melhorar previsibilidade de viagens."],
    6: ["Trilha de certificações com tempo reservado para estudo.", "Mentoria com uma referência técnica sênior."],
    7: ["Planejar viagens com mais antecedência.", "Blocos de foco sem reunião."],
    9: ["Padronizar a passagem de bastão entre engenharia e campo.", "Um ritual mensal de lições aprendidas por projeto."],
}


def resposta_clima(u: dict, sen: str, papel: str, ciclo: str, anos: float | None) -> dict:
    rnd = random.Random(h(u["id"], "gptw", ciclo))
    # Latente de satisfação: base 4,0; líderes e sêniores um pouco acima; pouco
    # tempo de casa um pouco abaixo. Cada afirmação sorteia em volta do latente.
    base = 4.0 + (0.3 if papel in ("gerencia", "diretoria") else 0) + (0.15 if sen in ("senior", "especialista") else 0) \
        - (0.25 if anos is not None and anos < 1 else 0) + rnd.uniform(-0.45, 0.35)
    ids = gptwmod.IDS_PULSO if ciclo == "pulso" else [a[0] for a in gptwmod.AFIRMACOES]
    respostas = {}
    for aid in ids:
        pilar = gptwmod.PILAR_DE[aid]
        ajuste = {"credibilidade": 0.0, "respeito": -0.15, "imparcialidade": -0.3, "orgulho": 0.25, "camaradagem": 0.2}[pilar]
        v = round(base + ajuste + rnd.gauss(0, 0.7))
        respostas[aid] = max(1, min(5, v))
    abertas = {}
    if ciclo == "anual":
        for qid in rnd.sample(sorted(ABERTAS_POOL), 3):
            abertas[qid] = rnd.choice(ABERTAS_POOL[qid])
    fam = gs.familia_de(u["cargo"])
    modelo = {"automacao": "campo", "servicos": "campo", "eletrica": "presencial", "producao": "presencial",
              "manutencao": "presencial", "digital": "hibrido", "marketing": "hibrido", "comercial": "hibrido",
              "exec": "hibrido", "cto": "hibrido"}.get(fam, escolha(["presencial", "hibrido"], u["id"], "mod"))
    faixa = dominio.faixa_de_casa(anos) if anos is not None and anos >= 0 else ""
    return {"id": hashlib.sha256(f"{u['id']}|{ciclo}|{ANO}".encode()).hexdigest()[:20],
            "ciclo": ciclo, "ano": ANO, "respostas": respostas, "abertas": abertas,
            "nivel": u.get("tipo", ""), "area": u.get("area", ""), "vinculo": u.get("vinculo", ""),
            "faixa": faixa, "modelo": modelo}


# =============================================================================
# APLICAÇÃO
# =============================================================================
def aplicar(caminho: Path, forcar: bool) -> dict:
    d = json.loads(caminho.read_text(encoding="utf-8"))
    us = d["unidades"]
    cfg = d.setdefault("config", {})
    fichas = {dcrmod.chave_funcao(o["cargo"]): o for o in (cfg.get("dcr_cargos") or [])}
    filhos: dict[str, int] = {}
    for u in us.values():
        if u.get("parent_id"):
            filhos[u["parent_id"]] = filhos.get(u["parent_id"], 0) + 1
    pessoas = [u for u in us.values() if u.get("parent_id") and u.get("cargo")]

    cgv_idx = {(r["ref"], r["ano"], r["ciclo"]): r for r in cgvmod.normalizar_overlay(cfg.get("cgv_registros"))}
    tal_idx = {(r["ref"], r["ano"]): r for r in talmod.normalizar_overlay(cfg.get("mapa_talentos"))}
    gptw = gptwmod.normalizar_overlay(cfg.get("gptw_respostas")) if not forcar else []
    gptw_ids = {r["id"] for r in gptw}
    n_acc = n_cgv = n_tal = n_clima = 0

    for u in pessoas:
        pai = us.get(u["parent_id"])
        ficha = fichas.get(dcrmod.chave_funcao(u["cargo"]))
        if ficha is None:                              # cargo sem Skills: gera na hora
            f = gs.ficha_de(u["cargo"], u["tipo"])
            ficha = {k: f[k] for k in ("cargo", "missao", "responsabilidades", "requisitos", "competencias")}
        papel = dcrmod.papel(u["tipo"], u["cargo"])
        sen = gs.senioridade_de(u["cargo"], papel)
        anos = dominio.tempo_de_casa(u.get("data_inicio") or None, HOJE)

        # 1. accountabilities
        proprias_atuais = [r for r in (u.get("responsabilidades") or []) if r.get("origem") != "delegada"]
        if forcar or len(proprias_atuais) != 5:
            u["responsabilidades"] = accountabilities(u, ficha, filhos.get(u["id"], 0))
            n_acc += 1
        proprias = [r["descricao"] for r in u["responsabilidades"] if r.get("origem") != "delegada"]

        # 2. Conversas de Valor (3 ciclos)
        ref = (u.get("codigo") or "").strip() or f"u:{u['id']}"
        regs = cgv_de(u, pai, ficha, proprias)
        for reg in regs:
            k = (reg["ref"], reg["ano"], reg["ciclo"])
            # Registro legado sem líder (ou só pendente) não é conversa: cede o lugar.
            legado = k in cgv_idx and (not cgv_idx[k].get("lider") or cgv_idx[k]["status"] == "pendente")
            if forcar or k not in cgv_idx or legado:
                cgv_idx[k] = reg
                n_cgv += 1
        completa = cgv_idx[(ref, ANO, "completa")]

        # 3. Avaliação
        if forcar or (ref, ANO) not in tal_idx:
            tal_idx[(ref, ANO)] = talento_de(u, pai, ficha, sen, papel, anos, proprias, completa)
            n_tal += 1

        # 4. Avaliação Mestre — anual + pulso
        for ciclo in ("anual", "pulso"):
            r = resposta_clima(u, sen, papel, ciclo, anos)
            if r["id"] not in gptw_ids:
                gptw.append(r)
                gptw_ids.add(r["id"])
                n_clima += 1

    cfg["cgv_registros"] = cgvmod.normalizar_overlay(list(cgv_idx.values()))
    cfg["mapa_talentos"] = talmod.normalizar_overlay(list(tal_idx.values()))
    cfg["gptw_respostas"] = gptwmod.normalizar_overlay(gptw)
    cfg["gptw_programacao"] = gptwmod.normalizar_programacao({
        "ciclo": "anual", "abertura": "2026-03-02", "fechamento": "2026-04-15", "notificar": False,
        "status": "programada", "agendado_em": "2026-02-20T12:00:00+00:00",
        "agendado_por": "RH · GPlanSiS|Peoples"})

    # Ledger: um evento de carga, encadeado ao último hash.
    if n_acc or n_cgv or n_tal or n_clima:
        evs = d.setdefault("eventos", [])
        anterior = evs[-1]["hash"] if evs else "GENESIS"
        ev = {"seq": len(evs) + 1, "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "ator": "ferramentas/gerar_ciclo_pessoas.py (Administrador)", "acao": "alterar",
              "entidade_id": "-", "motivo": "carga do ciclo de gente 2026 a partir dos Skills",
              "payload": {"accountabilities": n_acc, "conversas_de_valor": n_cgv,
                          "avaliacoes": n_tal, "respostas_clima": n_clima},
              "hash_anterior": anterior}
        ev["hash"] = hashlib.sha256(_corpo_evento(anterior, ev).encode()).hexdigest()
        evs.append(ev)

    caminho.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"pessoas": len(pessoas), "accountabilities": n_acc, "cgv": n_cgv, "avaliacoes": n_tal,
            "clima": n_clima, "cgv_total": len(cfg["cgv_registros"]),
            "clima_total": len(cfg["gptw_respostas"])}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    forcar = "--forcar" in sys.argv
    for org in organogramas.listar():
        p = organogramas.caminho_estado(org["slug"])
        if not p.exists():
            continue
        r = aplicar(p, forcar)
        print(f"{org['slug']:22s} pessoas={r['pessoas']:3d} · accountabilities={r['accountabilities']:3d} · "
              f"CdV novas={r['cgv']:3d} (total {r['cgv_total']}) · avaliações={r['avaliacoes']:3d} · "
              f"clima novas={r['clima']:3d} (total {r['clima_total']})")
