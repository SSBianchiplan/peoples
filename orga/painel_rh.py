"""Painel de RH / Departamento Pessoal — indicadores e movimentação.

Módulo PURO (não toca ESTADO nem disco): recebe as unidades, o mapa de CC e o log
de acessos, e devolve os agregados que a vista e o export de Excel consomem. É a
fonte única dos números — a tela e a planilha nunca divergem.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from . import dominio

FAIXAS_CASA = [("< 1 ano", 0, 1), ("1 a 3 anos", 1, 3), ("3 a 5 anos", 3, 5),
               ("5 a 10 anos", 5, 10), ("10+ anos", 10, 999)]
TERCEIRIZADOS = ("pj", "estagio", "rpa", "consultoria")
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out",
         "nov", "dez"]


def _iso(v):
    """Divide 'AAAA-MM-DD' em (a, m, d) inteiros, ou None."""
    try:
        a, m, d = (int(x) for x in str(v).split("-")[:3])
        return a, m, d
    except Exception:
        return None


def _anos(iso, ref):
    p = _iso(iso)
    return (ref - date(*p)).days / 365.25 if p else None


def _filhos(unidades):
    f = defaultdict(list)
    for u in unidades.values():
        f[u.parent_id].append(u.id)
    return f


def kpis(unidades, ref=None) -> dict:
    ref = ref or date.today()
    us = list(unidades.values())
    total = len(us) or 1
    gestores = [u for u in us if _filhos(unidades).get(u.id)]
    tenures = [a for u in us if (a := _anos(u.data_inicio, ref)) is not None]
    vinc = Counter(u.vinculo or "clt" for u in us)
    terceiros = sum(vinc.get(k, 0) for k in TERCEIRIZADOS)
    ativos = sum(1 for u in us if (u.status or "").lower().startswith("ativ"))
    return {
        "total": len(us), "gestores": len(gestores),
        "departamentos": len({u.area for u in us if u.area}),
        "verticais": len({u.vertical for u in us if u.vertical}),
        "tempo_medio": round(sum(tenures) / len(tenures), 1) if tenures else 0,
        "pct_clt": round(vinc.get("clt", 0) / total * 100),
        "pct_terceiros": round(terceiros / total * 100),
        "clt": vinc.get("clt", 0), "terceiros": terceiros,
        "ativos": ativos, "span_medio": round((len(us) - 1) / max(len(gestores), 1), 1),
    }


def _serie(contagem: dict, ordem=None, rotulos=None, limite=None) -> list[dict]:
    """Uma série pronta para gráfico: [{rotulo, valor, chave, pct}], com o máximo
    para a barra proporcional."""
    itens = ([(k, contagem.get(k, 0)) for k in ordem] if ordem
             else sorted(contagem.items(), key=lambda x: -x[1]))
    if limite:
        itens = itens[:limite]
    total = sum(v for _, v in itens) or 1
    topo = max((v for _, v in itens), default=1) or 1
    return [{"chave": k, "rotulo": (rotulos or {}).get(k, k) or "(sem)", "valor": v,
             "pct": round(v / total * 100), "barra": round(v / topo * 100)}
            for k, v in itens]


def distribuicoes(unidades, rotulos_nivel, niveis, ref=None) -> dict:
    ref = ref or date.today()
    us = list(unidades.values())
    vinc = Counter(u.vinculo or "clt" for u in us)
    rot_vinc = {k: v[0] for k, v in dominio.VINCULOS.items()}
    casa = Counter()
    for u in us:
        a = _anos(u.data_inicio, ref)
        if a is None:
            casa["(sem data)"] += 1
            continue
        for rot, lo, hi in FAIXAS_CASA:
            if lo <= a < hi:
                casa[rot] += 1
                break
    adm_ano = Counter()
    for u in us:
        p = _iso(u.data_inicio)
        if p:
            adm_ano[str(p[0])] += 1
    ordem_niv = [n["codigo"] for n in niveis if isinstance(n, dict)]
    return {
        "vinculo": _serie(vinc, rotulos=rot_vinc),
        "nivel": _serie(Counter(u.tipo for u in us), ordem=ordem_niv, rotulos=rotulos_nivel),
        "tempo_casa": _serie(casa, ordem=[r for r, _, _ in FAIXAS_CASA] + ["(sem data)"]),
        "departamento": _serie(Counter(u.area or "(sem depto)" for u in us), limite=12),
        "vertical": _serie(Counter(u.vertical for u in us if u.vertical), limite=12),
        "admissao_ano": _serie(adm_ano, ordem=sorted(adm_ano)),
    }


def ultimas_contratacoes(unidades, ref=None, n=12) -> list[dict]:
    """Quem entrou mais recentemente (data de admissão), com destaque para o mês
    corrente — o que o DP acompanha para onboarding."""
    ref = ref or date.today()
    comdata = [u for u in unidades.values() if _iso(u.data_inicio)]
    comdata.sort(key=lambda u: u.data_inicio, reverse=True)
    saida = []
    for u in comdata[:n]:
        p = _iso(u.data_inicio)
        saida.append({
            "id": u.id, "nome": u.nome, "cargo": u.cargo, "area": u.area,
            "vinculo": dominio.VINCULOS.get(u.vinculo or "clt", (u.vinculo, ""))[0],
            "data": u.data_inicio,
            "no_mes": p and p[0] == ref.year and p[1] == ref.month,
            "dias": (ref - date(*p)).days if p else None,
        })
    return saida


def contratacoes_do_mes(unidades, ref=None) -> list[dict]:
    ref = ref or date.today()
    return [c for c in ultimas_contratacoes(unidades, ref, n=9999) if c["no_mes"]]


def movimentacao(acessos_log, unidades, ref=None, dias_inativo=30) -> dict:
    """A movimentação de ACESSO: últimas saídas, e quem está inativo (nunca entrou
    ou sem acesso há mais de `dias_inativo`). O 'quem saiu / quando' que o DP pede
    vem do log de login/logout — não de um campo que ninguém mantém."""
    ref = ref or date.today()
    ultimo = {}          # uid -> (quando, evento)
    for ev in acessos_log:
        uid = ev.get("usuario_id")
        if uid:
            ultimo[uid] = (ev.get("quando", ""), ev.get("evento"))
    saidas = [{"id": ev.get("usuario_id"), "nome": ev.get("nome") or "—",
               "email": ev.get("email") or "—", "quando": ev.get("quando", "")}
              for ev in reversed(acessos_log) if ev.get("evento") == "sair"][:12]

    def _dias(iso):
        p = _iso((iso or "")[:10])
        return (ref - date(*p)).days if p else None

    inativos = []
    for uid, u in unidades.items():
        q = ultimo.get(uid)
        dias = _dias(q[0]) if q else None
        nunca = q is None
        if nunca or (dias is not None and dias >= dias_inativo):
            inativos.append({"id": uid, "nome": u.nome, "cargo": u.cargo, "area": u.area,
                             "ultimo_acesso": (q[0][:10] if q else ""),
                             "dias": dias, "nunca": nunca})
    inativos.sort(key=lambda x: (not x["nunca"], -(x["dias"] or 0)))
    return {"saidas": saidas, "inativos": inativos[:30],
            "n_inativos": len(inativos), "n_nunca": sum(1 for x in inativos if x["nunca"])}


def _faixa_casa(u, ref):
    a = _anos(u.data_inicio, ref)
    if a is None:
        return "(sem data)"
    for rot, lo, hi in FAIXAS_CASA:
        if lo <= a < hi:
            return rot
    return "(sem data)"


def _seletor(dim, ref):
    """A função que extrai, de cada pessoa, a chave da dimensão do gráfico. É o
    espelho exato do que `distribuicoes` agrupa — a lista de um clique bate com a
    barra clicada."""
    return {
        "vinculo": lambda u: u.vinculo or "clt",
        "nivel": lambda u: u.tipo,
        "departamento": lambda u: u.area or "(sem depto)",
        "vertical": lambda u: u.vertical,
        "tempo_casa": lambda u: _faixa_casa(u, ref),
        "admissao_ano": lambda u: (str(_iso(u.data_inicio)[0]) if _iso(u.data_inicio) else ""),
    }.get(dim)


def _pessoa(u, ref):
    a = _anos(u.data_inicio, ref)
    return {
        "id": u.id, "nome": u.nome, "cargo": u.cargo, "area": u.area,
        "vinculo": dominio.VINCULOS.get(u.vinculo or "clt", (u.vinculo, ""))[0],
        "data": u.data_inicio, "anos": round(a, 1) if a is not None else None,
        "status": (u.status or "ativo"),
    }


def colaboradores_por(unidades, dim, chave, ref=None) -> list[dict]:
    """As pessoas de UMA fatia de gráfico (a barra/segmento clicado). O `dim` diz
    qual eixo, `chave` qual valor. Devolve a lista pronta para o modal, ordenada
    por nome."""
    ref = ref or date.today()
    sel = _seletor(dim, ref)
    if sel is None:
        return []
    alvo = str(chave)
    saida = [_pessoa(u, ref) for u in unidades.values() if str(sel(u)) == alvo]
    saida.sort(key=lambda p: p["nome"].lower())
    return saida


def desligamentos(unidades, ref=None) -> list[dict]:
    """Quem saiu, pela ótica do RH: os colaboradores marcados como inativos
    (desligamento em curso, afastamento ou licença — o RH declara em `status`).
    NÃO é o logout do sistema: saída de gente é status, não sessão."""
    ref = ref or date.today()
    fora = [_pessoa(u, ref) for u in unidades.values()
            if (u.status or "ativo").lower() != "ativo"]
    fora.sort(key=lambda p: p["nome"].lower())
    return fora


def crescimento(unidades, ref=None) -> list[dict]:
    """Curva de crescimento: headcount acumulado por ano de admissão. Como a carga
    remove quem saiu, o acumulado do último ano é o headcount de hoje — a curva é
    a história de como a casa chegou ao tamanho atual."""
    ref = ref or date.today()
    por_ano = Counter()
    for u in unidades.values():
        p = _iso(u.data_inicio)
        if p:
            por_ano[p[0]] += 1
    if not por_ano:
        return []
    anos = list(range(min(por_ano), max(por_ano) + 1))
    topo = sum(por_ano.values()) or 1
    acc, saida = 0, []
    n = len(anos)
    for i, a in enumerate(anos):
        acc += por_ano.get(a, 0)
        saida.append({
            "ano": a, "novos": por_ano.get(a, 0), "acumulado": acc,
            # coordenadas normalizadas (0..100) para o SVG; y invertido
            "x": round(i / (n - 1) * 100, 2) if n > 1 else 0,
            "y": round(100 - acc / topo * 100, 2),
        })
    return saida


def sincronizar_n5(unidades, mapa_cc) -> dict:
    """Preenche o campo N5 de cada colaborador a partir do vínculo com o cadastro
    de centros de custo (o N5 vive lá, não na pessoa). Atualiza SOMENTE o N5 —
    nada mais é tocado. Devolve o que mudou. MUTA as unidades."""
    atualizados, ja_ok, sem_cc = 0, 0, 0
    for uid, u in unidades.items():
        n5 = (mapa_cc.get(uid) or {}).get("n5", "")
        if not n5:
            sem_cc += 1
            continue
        if u.n5 == n5:
            ja_ok += 1
            continue
        u.n5 = n5
        atualizados += 1
    return {"atualizados": atualizados, "ja_corretos": ja_ok, "sem_cc": sem_cc,
            "total": len(unidades)}
