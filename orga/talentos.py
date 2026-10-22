"""
GPlanSiS|Peoples — Avaliação (GEP-FOR-004).

O terceiro da série de Gestão de Talentos, depois do Skills e da Conversa de Valor, e no mesmo
desenho: deriva o que o sistema já sabe (nome, tempo de casa, cargo, líder,
área) e guarda só a leitura que o RH escreve sobre cada colaborador — risco e
impacto de perda, aderência aos valores GPlanSiS, oportunidades, prontidão de
sucessão e a ação imediata (meritocracia/promoção/rotativo). É a folha que
alimenta o Comitê de Meritocracia e a Trilha de Carreira.

Segue a arquitetura do `cgv.py`:

**Deriva da estrutura, não de cadastro novo.** A base sai de `dcr.medir` (cargo,
papel, área, líder) somada ao `tempo.medir` (anos de casa). Ninguém redigita o
que o organograma já tem.

**A camada editável é a leitura do RH.** Vive em `Config.mapa_talentos`, passa
por `commit` e entra no Desfazer. Espelha em `org.mapa_talento` (Postgres)
quando há banco, e no `estado.json` sempre — dev e testes rodam sem banco.

**Idade é editável e opcional, por decisão de LGPD.** O organograma não guarda
data de nascimento (LGPD-01/02); o formulário GEP-FOR-004 pede idade, então ela
entra como campo que o RH preenche à mão, ou deixa em branco — nunca derivada.

**Sem nota de desempenho quantitativa.** Como na Conversa de Valor, o Mapa é conversa de
desenvolvimento e sucessão, não ranking numérico. Risco, impacto e prontidão são
categorias de leitura, não score.
"""
from __future__ import annotations

from . import cgv as cgvmod
from . import dcr
from . import tempo as tempomod
from .cgv import VALORES_TRIO
from .dominio import sem_acento

# Módulo puro: o idioma vigente entra como estado, ajustado por
# `main.alinhar_idioma()` antes de emitir. Mesma convenção de `dcr` e `cgv`.
IDIOMA = "pt-BR"


def _t(texto: str, **p) -> str:
    from . import idiomas
    return idiomas.traduzir(texto, IDIOMA, **p)


# ---------------------------------------------------------------------------
# O FORMULÁRIO CONTROLADO
# ---------------------------------------------------------------------------
FORMULARIO = {"codigo": "GEP-FOR-004", "revisao": "00", "titulo": "Avaliação"}

# ---------------------------------------------------------------------------
# AS ESCALAS — o que a planilha oferece como lista suspensa
# ---------------------------------------------------------------------------
# `codigo, rótulo`. O código persiste e a régua do 9-box usa; o rótulo é o que a
# tela imprime, traduzível. A ordem é a da matriz (do mais crítico ao menos), e
# nunca a de quem preencheu primeiro (RNF-02).
RISCOS = (("alto", "Alto"), ("medio", "Médio"), ("baixo", "Baixo"))
IMPACTOS = (("alto", "Alto"), ("medio", "Médio"), ("baixo", "Baixo"))
ROTULO_RISCO = {c: r for c, r in RISCOS}
ROTULO_IMPACTO = {c: r for c, r in IMPACTOS}
COD_RISCO = tuple(c for c, _r in RISCOS)
COD_IMPACTO = tuple(c for c, _r in IMPACTOS)

# A prontidão de sucessão — quando a pessoa está pronta para o próximo passo.
PRONTIDOES = (
    ("agora", "Pronto agora"),
    ("1ano", "Pronto em 1 ano"),
    ("2anos", "Pronto em 2 anos"),
    ("3mais", "Pronto em 3 anos ou +"),
)
ROTULO_PRONTIDAO = {c: r for c, r in PRONTIDOES}
COD_PRONTIDAO = tuple(c for c, _r in PRONTIDOES)

# A ação imediata — o encaminhamento que a folha propõe ao Comitê de Meritocracia.
ACOES = (
    ("meritocracia", "Meritocracia"),
    ("promocao", "Promoção"),
    ("rotativo", "Rotativo"),
    ("outros", "Outros"),
)
ROTULO_ACAO = {c: r for c, r in ACOES}
COD_ACAO = tuple(c for c, _r in ACOES)

# O código dos quatro valores GPlanSiS, reusado da Conversa de Valor (a mesma cultura, um só texto).
COD_TRIO = tuple(c for c, _s, _r, _f in VALORES_TRIO)

VAZIO = "—"
LIMITE_CAMPO = 4000
ANO_PADRAO = 2026

# O piso de amostra para publicar proporção numa célula — o mesmo do Skills: abaixo
# disto uma célula do 9-box não vira percentual, para um número que oscila com
# uma pessoa não convidar a decidir sobre ruído.
PISO_GRUPO = 5


def ref_de(linha: dict) -> str:
    """A identidade durável: a matrícula (código SAP). Não o id da unidade, que
    se recria a cada carga — mesma razão da Conversa de Valor."""
    return str(linha.get("codigo") or "").strip() or f"u:{linha['id']}"


# ---------------------------------------------------------------------------
# O CONTEÚDO — os campos de texto do GEP-FOR-004
# ---------------------------------------------------------------------------
# Os quatro enums (risco, impacto, prontidão, ação) ficam no topo do registro
# porque é por eles que a matriz e o Comitê filtram. O resto — o texto que o RH
# redige — vai no `conteudo`, como JSONB no banco.
CAMPOS_TEXTO = ("idade", "trajetoria", "formacoes", "perfil", "performance",
                "bem_estar", "ferramentas", "ingles", "trilha_posicao",
                "acao_nota")


def conteudo_vazio() -> dict:
    return {**{c: "" for c in CAMPOS_TEXTO},
            "valores": {c: "" for c in COD_TRIO}}


def normalizar_conteudo(bruto) -> dict:
    b = bruto if isinstance(bruto, dict) else {}
    def txt(v, n=LIMITE_CAMPO):
        return str(v if v is not None else "").strip()[:n]
    val = b.get("valores") if isinstance(b.get("valores"), dict) else {}
    saida = {c: txt(b.get(c)) for c in CAMPOS_TEXTO}
    saida["idade"] = txt(b.get("idade"), 8)      # idade é curta
    saida["valores"] = {c: txt(val.get(c)) for c in COD_TRIO}
    return saida


def conteudo_tem_texto(c: dict) -> bool:
    c = c or {}
    if any(str(c.get(k) or "").strip() for k in CAMPOS_TEXTO):
        return True
    return any(str(v or "").strip() for v in (c.get("valores") or {}).values())


def conteudo_preenchido(c: dict) -> int:
    """Quantas das seções-chave têm texto — o «N de 8» da tela."""
    c = c or {}
    chaves = ("trajetoria", "formacoes", "perfil", "performance", "bem_estar",
              "ferramentas", "trilha_posicao")
    n = sum(1 for k in chaves if str(c.get(k) or "").strip())
    n += 1 if any(str(v or "").strip() for v in (c.get("valores") or {}).values()) else 0
    return n


# ---------------------------------------------------------------------------
# A CAMADA EDITÁVEL — um registro por (matrícula, ano)
# ---------------------------------------------------------------------------
CAMPOS_SNAP = ("nome", "cargo", "lider")
CAMPOS_ENUM = ("risco_perda", "impacto_perda", "prontidao", "acao")
_VALIDOS = {"risco_perda": set(COD_RISCO), "impacto_perda": set(COD_IMPACTO),
            "prontidao": set(COD_PRONTIDAO), "acao": set(COD_ACAO)}


def _indice_overlay(overlay: list[dict] | None) -> dict:
    return {(r["ref"], int(r["ano"])): r for r in (overlay or [])
            if r.get("ref") and r.get("ano")}


def normalizar_overlay(bruto: list[dict] | None) -> list[dict]:
    """Saneia a folha. Enum fora da lista vira vazio; texto cortado no limite; o
    ano precisa ser plausível. Registro sem nenhum sinal não ocupa lugar."""
    saida: dict[tuple, dict] = {}
    for r in bruto or []:
        ref = str((r or {}).get("ref") or "").strip()[:60]
        try:
            ano = int(r.get("ano"))
        except (TypeError, ValueError):
            continue
        if not ref or not (2000 <= ano <= 2100):
            continue
        linha = {"ref": ref, "ano": ano}
        for campo in CAMPOS_ENUM:
            v = r.get(campo)
            linha[campo] = v if v in _VALIDOS[campo] else ""
        linha["conteudo"] = normalizar_conteudo(r.get("conteudo"))
        for c in CAMPOS_SNAP:
            linha[c] = str(r.get(c) or "").strip()[:120]
        if (any(linha[e] for e in CAMPOS_ENUM)
                or conteudo_tem_texto(linha["conteudo"])):
            saida[(ref, ano)] = linha
    return sorted(saida.values(), key=lambda r: (r["ref"], -r["ano"]))


def registro_de(ref: str, ano: int, overlay: list[dict] | None) -> dict:
    return _indice_overlay(overlay).get(
        (ref, ano),
        {"ref": ref, "ano": ano, **{e: "" for e in CAMPOS_ENUM},
         "conteudo": conteudo_vazio(), **{c: "" for c in CAMPOS_SNAP}})


# ---------------------------------------------------------------------------
# DERIVAÇÃO — a linha de cada pessoa, com tempo de casa
# ---------------------------------------------------------------------------
def medir(unidades, mapa_cc: dict | None = None) -> list[dict]:
    """Uma linha por pessoa: o que o Skills mede + os anos de casa do módulo Tempo.

    Duas leituras da estrutura, unidas por id. É a base do Mapa — a matriz e as
    fichas consomem esta lista, não o dicionário de unidades."""
    base = dcr.medir(unidades, mapa_cc)
    anos = {l["id"]: l for l in tempomod.medir(unidades)}
    for l in base:
        t = anos.get(l["id"], {})
        l["anos_casa"] = t.get("anos")
        l["faixa_casa"] = t.get("faixa")
    return base


def _entrada(l: dict, por_id: dict, reg: dict, ano: int) -> dict:
    ref = ref_de(l)
    lider = por_id.get(l["parent_id"])
    r = reg.get((ref, ano), {})
    return {
        "id": l["id"], "ref": ref, "ano": ano, "nome": l["nome"],
        "cargo": l["cargo"], "papel": l["papel"],
        "papel_rotulo": dcr.ROTULO_PAPEL.get(l["papel"], l["papel"]),
        "setor": l["setor"], "bu": l["bu"], "vertical": l["vertical"],
        "anos_casa": l.get("anos_casa"), "faixa_casa": l.get("faixa_casa"),
        "lider_id": (lider or {}).get("id", ""),
        "lider_nome": (lider or {}).get("nome", ""),
        "risco_perda": r.get("risco_perda", ""),
        "impacto_perda": r.get("impacto_perda", ""),
        "prontidao": r.get("prontidao", ""),
        "acao": r.get("acao", ""),
        "mapeado": bool(r),
    }


def agenda(linhas: list[dict], overlay: list[dict] | None = None,
           ano: int = ANO_PADRAO) -> list[dict]:
    """Uma linha por pessoa, em ordem hierárquica (líder seguido da equipe),
    como a agenda da Conversa de Valor — a leitura de sucessão desce a árvore."""
    por_id = {l["id"]: l for l in linhas}
    reg = _indice_overlay(overlay)
    filhos: dict[str, list[dict]] = {}
    for l in linhas:
        filhos.setdefault(l["parent_id"], []).append(l)
    chave = lambda l: (dcr.ORDEM_PAPEL.get(l["papel"], 99), sem_acento(l["nome"]))
    raizes = sorted((l for l in linhas if l["parent_id"] not in por_id), key=chave)
    saida, pilha, vistos = [], [(l, 0) for l in reversed(raizes)], set()
    while pilha:
        l, prof = pilha.pop()
        if l["id"] in vistos:
            continue
        vistos.add(l["id"])
        e = _entrada(l, por_id, reg, ano)
        e["profundidade"] = prof
        saida.append(e)
        for f in sorted(filhos.get(l["id"], []), key=chave, reverse=True):
            pilha.append((f, prof + 1))
    return saida


# ---------------------------------------------------------------------------
# 9-BOX — Risco × Impacto de perda
# ---------------------------------------------------------------------------
def nine_box(ag: list[dict]) -> dict:
    """A matriz 3×3: risco de perda (linhas) × impacto de perda (colunas), com as
    pessoas de cada célula. A célula alto×alto é a de retenção urgente; baixo×
    baixo, a tranquila. Quem não foi classificado fica de fora da matriz e conta
    à parte, para o total não mentir."""
    celulas = {(ri, im): [] for ri, _r in RISCOS for im, _i in IMPACTOS}
    sem = 0
    for a in ag:
        chave = (a["risco_perda"], a["impacto_perda"])
        if chave in celulas:
            celulas[chave].append(a)
        else:
            sem += 1
    grade = []
    for ri, rot_r in RISCOS:
        linha = {"risco": ri, "risco_rotulo": rot_r, "celulas": []}
        for im, rot_i in IMPACTOS:
            gente = celulas[(ri, im)]
            linha["celulas"].append({
                "impacto": im, "impacto_rotulo": rot_i,
                "n": len(gente),
                "pessoas": [{"ref": g["ref"], "nome": g["nome"],
                             "cargo": g["cargo"]} for g in gente],
                "critica": ri == "alto" and im == "alto",
            })
        grade.append(linha)
    return {"grade": grade, "mapeados": len(ag) - sem, "sem_classificar": sem,
            "total": len(ag)}


def prontidao(ag: list[dict]) -> list[dict]:
    """Distribuição por prazo de prontidão de sucessão — quem está «pronto agora»
    é o banco de sucessores imediato."""
    cont = {c: 0 for c in COD_PRONTIDAO}
    sem = 0
    for a in ag:
        if a["prontidao"] in cont:
            cont[a["prontidao"]] += 1
        else:
            sem += 1
    total = len(ag)
    return [{"codigo": c, "rotulo": ROTULO_PRONTIDAO[c], "n": cont[c],
             "pct": round(100 * cont[c] / total) if total else 0}
            for c in COD_PRONTIDAO] + (
        [{"codigo": "", "rotulo": _t("Sem classificar"), "n": sem,
          "pct": round(100 * sem / total) if total else 0}] if sem else [])


def por_acao(ag: list[dict]) -> dict:
    """Os indicados por tipo de ação imediata — o insumo do Comitê de
    Meritocracia. Só quem tem ação classificada entra."""
    grupos = {c: [] for c in COD_ACAO}
    for a in ag:
        if a["acao"] in grupos:
            grupos[a["acao"]].append(a)
    return {c: {"rotulo": ROTULO_ACAO[c], "pessoas": grupos[c]} for c in COD_ACAO}


def resumo(ag: list[dict]) -> dict:
    mapeados = sum(1 for a in ag if a["mapeado"])
    criticos = sum(1 for a in ag
                   if a["risco_perda"] == "alto" and a["impacto_perda"] == "alto")
    prontos = sum(1 for a in ag if a["prontidao"] == "agora")
    return {
        "pessoas": len(ag),
        "mapeados": mapeados,
        "pct": round(100 * mapeados / len(ag)) if ag else 0,
        "criticos": criticos,
        "prontos_agora": prontos,
        "indicados": sum(1 for a in ag if a["acao"]),
    }


# ---------------------------------------------------------------------------
# FICHA — o Mapa de uma pessoa (para MT-3)
# ---------------------------------------------------------------------------
def _do_cgv(ref: str, ano: int, cgv_registros: list[dict] | None) -> dict:
    """Puxa a aderência aos valores GPlanSiS e o PDI da Conversa de Valor Completa daquele ano (INT-1/INT-3).

    O Mapa e a Conversa de Valor falam da mesma pessoa e do mesmo ano: repetir a aderência aos
    valores e o plano de desenvolvimento seria manter dois textos que divergem na
    primeira edição. Quando a conversa existe, o Mapa a EXIBE e não repergunta; o
    campo próprio do Mapa fica como reserva para quando não há Conversa de Valor."""
    vazio = {"tem": False, "valores": {}, "pdi": [], "carreira": ""}
    if not cgv_registros:
        return vazio
    reg = cgvmod.registro_de(ref, ano, cgvmod.COD_CICLOS[0], cgv_registros)
    ct = reg.get("conteudo") or {}
    val = {c: str((ct.get("valores") or {}).get(c) or "").strip() for c in COD_TRIO}
    pdi = [p for p in (ct.get("pdi") or []) if str(p.get("comp") or "").strip()]
    carreira = str(ct.get("carreira") or "").strip()
    return {"tem": any(val.values()) or bool(pdi) or bool(carreira),
            "valores": val, "pdi": pdi, "carreira": carreira}


def ficha(ref: str, linhas: list[dict], overlay: list[dict] | None = None,
          ano: int = ANO_PADRAO, cgv_registros: list[dict] | None = None
          ) -> dict | None:
    """A Avaliação de uma pessoa: o derivado + o que o RH escreveu, com a
    aderência aos valores GPlanSiS e o PDI puxados da Conversa de Valor quando a conversa existe (INT).
    `None` quando a matrícula não existe no recorte."""
    por_ref = {ref_de(l): l for l in linhas}
    l = por_ref.get(ref)
    if l is None:
        return None
    por_id = {x["id"]: x for x in linhas}
    lider = por_id.get(l["parent_id"])
    r = registro_de(ref, ano, overlay)
    ct = normalizar_conteudo(r.get("conteudo"))
    return {
        "id": l["id"], "ref": ref, "ano": ano, "nome": l["nome"],
        "cargo": l["cargo"], "papel": dcr.ROTULO_PAPEL.get(l["papel"], l["papel"]),
        "setor": l["setor"], "bu": l["bu"], "vertical": l["vertical"],
        "anos_casa": l.get("anos_casa"), "faixa_casa": l.get("faixa_casa"),
        "lider_nome": (lider or {}).get("nome", ""),
        "risco_perda": r.get("risco_perda", ""),
        "impacto_perda": r.get("impacto_perda", ""),
        "prontidao": r.get("prontidao", ""),
        "acao": r.get("acao", ""),
        "conteudo": ct,
        "preenchidas": conteudo_preenchido(ct),
        "cgv": _do_cgv(ref, ano, cgv_registros),
    }


def markdown(f: dict) -> str:
    """A ficha em Markdown, para o motor de `relatorio.py` (GEP-FOR-004)."""
    ct = f.get("conteudo") or {}
    L = [f"# {_t('Avaliação')}", ""]
    L.append(f"**{_t('Colaborador')}:** {f['nome']}")
    L.append("")
    L.append(f"**{_t('Cargo')}:** {f['cargo'] or VAZIO}")
    L.append("")
    L.append(f"**{_t('Líder direto')}:** {f['lider_nome'] or VAZIO}")
    L.append("")
    anos = f.get("anos_casa")
    L.append(f"**{_t('Tempo de empresa')}:** "
             + (_t('{n} anos', n=round(anos, 1)) if anos is not None else VAZIO))
    L.append("")
    L.append(f"**{_t('Idade')}:** {ct.get('idade') or VAZIO}")
    L.append("")
    def secao(rot, texto):
        L.append(f"## {_t(rot)}")
        L.append(str(texto or "").strip() or VAZIO)
        L.append("")
    secao("Trajetória na empresa", ct.get("trajetoria"))
    secao("Formações e cursos", ct.get("formacoes"))
    secao("Perfil comportamental", ct.get("perfil"))
    secao("Performance", ct.get("performance"))
    secao("Bem-estar", ct.get("bem_estar"))
    L.append(f"## {_t('Risco e impacto de perda')}")
    L.append(f"- **{_t('Risco de perda')}:** {_t(ROTULO_RISCO.get(f['risco_perda'], VAZIO))}")
    L.append(f"- **{_t('Impacto da perda')}:** {_t(ROTULO_IMPACTO.get(f['impacto_perda'], VAZIO))}")
    L.append("")
    # A aderência aos valores GPlanSiS vem da Conversa de Valor quando a conversa existe (INT-1): uma fonte só.
    cgv = f.get("cgv") or {}
    cgv_val = cgv.get("valores") or {}
    L.append(f"## {_t('Aderência aos Valores Organizacionais')}")
    for cod, sig, rot, _frase in VALORES_TRIO:
        docgv = str(cgv_val.get(cod) or "").strip()
        obs = docgv or str((ct.get("valores") or {}).get(cod) or "").strip()
        marca = f" ({_t('da Conversa de Valor')})" if docgv else ""
        L.append(f"- **{sig}** ({_t(rot)}): {obs or VAZIO}{marca}")
    L.append("")
    secao("Oportunidades e Potencialidades", ct.get("ferramentas"))
    L.append(f"**{_t('Inglês')}:** {ct.get('ingles') or VAZIO}")
    L.append("")
    if cgv.get("pdi"):
        L.append(f"## {_t('PDI — vindo da Conversa de Valor')}")
        for p in cgv["pdi"]:
            prazo = f" · {p.get('prazo')}" if p.get("prazo") else ""
            L.append(f"- **{p.get('comp', '')}**{prazo}")
        L.append("")
    secao("Trilha de Carreira", ct.get("trilha_posicao"))
    L.append(f"- **{_t('Prontidão')}:** {_t(ROTULO_PRONTIDAO.get(f['prontidao'], VAZIO))}")
    L.append("")
    L.append(f"## {_t('Ação Imediata')}")
    L.append(f"- **{_t(ROTULO_ACAO.get(f['acao'], VAZIO))}** — {ct.get('acao_nota') or VAZIO}")
    return "\n".join(L)


def panorama(unidades, mapa_cc: dict | None = None,
             overlay: list[dict] | None = None, ano: int = ANO_PADRAO) -> dict:
    """Tudo o que a vista precisa, numa passada só."""
    linhas = medir(unidades, mapa_cc)
    ag = agenda(linhas, overlay, ano)
    return {
        "linhas": linhas, "agenda": ag, "resumo": resumo(ag),
        "nine_box": nine_box(ag), "prontidao": prontidao(ag),
        "por_acao": por_acao(ag), "ano": ano,
        "riscos": RISCOS, "impactos": IMPACTOS, "prontidoes": PRONTIDOES,
        "acoes": ACOES, "valores": VALORES_TRIO,
        "rot_risco": ROTULO_RISCO, "rot_impacto": ROTULO_IMPACTO,
        "rot_prontidao": ROTULO_PRONTIDAO, "rot_acao": ROTULO_ACAO,
    }


# ---------------------------------------------------------------------------
# PERSISTÊNCIA EM POSTGRES — o Mapa durável
# ---------------------------------------------------------------------------
def banco_pronto() -> bool:
    from . import banco
    return banco.situacao().get("pronto", False)


def _conectar():
    from . import banco
    pg = banco.driver()
    return pg.connect(banco.dsn(), connect_timeout=8) if pg and banco.dsn() else None


def salvar_no_banco(reg: dict, slug: str = "peoples") -> tuple[bool, str]:
    """UPSERT de um registro no Postgres. Idempotente por (slug, ref, ano)."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return False, "sem banco"
        import json as _json
        conteudo = _json.dumps(normalizar_conteudo(reg.get("conteudo")),
                               ensure_ascii=False)
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO org.mapa_talento (slug, ref, ano, risco_perda, "
                "impacto_perda, prontidao, acao, conteudo, pessoa_nome, "
                "pessoa_cargo, lider_nome, registrado_por) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s) "
                "ON CONFLICT (slug, ref, ano) DO UPDATE SET "
                "risco_perda=EXCLUDED.risco_perda, impacto_perda=EXCLUDED.impacto_perda, "
                "prontidao=EXCLUDED.prontidao, acao=EXCLUDED.acao, "
                "conteudo=EXCLUDED.conteudo, pessoa_nome=EXCLUDED.pessoa_nome, "
                "pessoa_cargo=EXCLUDED.pessoa_cargo, lider_nome=EXCLUDED.lider_nome, "
                "registrado_por=EXCLUDED.registrado_por, atualizado_em=now()",
                (slug, reg["ref"], reg["ano"], reg.get("risco_perda") or None,
                 reg.get("impacto_perda") or None, reg.get("prontidao") or None,
                 reg.get("acao") or None, conteudo, reg.get("nome") or "",
                 reg.get("cargo") or "", reg.get("lider") or "", reg.get("por") or ""))
        con.commit()
        return True, "gravado no banco"
    except Exception as erro:                          # noqa: BLE001
        return False, str(erro).strip().splitlines()[0][:200]
    finally:
        if con is not None:
            con.close()


def carregar_do_banco(slug: str = "peoples") -> list[dict]:
    """Todos os registros do banco, no formato do overlay. `[]` sem banco."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return []
        with con.cursor() as cur:
            cur.execute(
                "SELECT ref, ano, risco_perda, impacto_perda, prontidao, acao, "
                "conteudo, pessoa_nome, pessoa_cargo, lider_nome "
                "FROM org.mapa_talento WHERE slug=%s", (slug,))
            return [{"ref": r[0], "ano": r[1], "risco_perda": r[2] or "",
                     "impacto_perda": r[3] or "", "prontidao": r[4] or "",
                     "acao": r[5] or "",
                     "conteudo": r[6] if isinstance(r[6], dict) else {},
                     "nome": r[7] or "", "cargo": r[8] or "", "lider": r[9] or ""}
                    for r in cur.fetchall()]
    except Exception:                                  # noqa: BLE001
        return []
    finally:
        if con is not None:
            con.close()


def fundir(overlay: list[dict] | None, do_banco: list[dict] | None) -> list[dict]:
    """Overlay vivo + banco, sem duplicar. O overlay vence no conflito de mesma
    (ref, ano) — é o que o operador acabou de editar."""
    idx = {(r["ref"], int(r["ano"])): r for r in normalizar_overlay(do_banco)}
    idx.update({(r["ref"], int(r["ano"])): r for r in normalizar_overlay(overlay)})
    return sorted(idx.values(), key=lambda r: (r["ref"], -r["ano"]))
