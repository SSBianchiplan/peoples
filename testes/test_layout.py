"""
Cobertura do motor de layout — SPEC §14, casos T-L01 a T-L09, mais os
invariantes normativos da §9 que a implementacao promete cumprir.

    pytest -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orga.dominio import (CARD_W, GAP_H, GAP_V, MARGEM, Unidade, calcular_layout,
                     mapa_filhos, montar_card, quebrar, raiz)


# ---------------------------------------------------------------------------
def arvore(*espec: tuple[str, str | None]) -> dict[str, Unidade]:
    """(id, parent_id) -> dicionario de unidades com conteudo minimo."""
    us = {}
    for i, (uid, pai) in enumerate(espec):
        us[uid] = Unidade(id=uid, codigo=f"ORG-{i + 1:04d}", nome=f"Unidade {uid}",
                          tipo="area", parent_id=pai, ordem=(i + 1) * 10,
                          cargo="Cargo", area="Equipe")
    return us


def indice(layout: dict) -> dict[str, dict]:
    return {n["id"]: n for n in layout["nos"]}


def equipe_larga(n: int) -> dict[str, Unidade]:
    """Raiz → um gestor → `n` subordinados, todos folhas."""
    return arvore(("R", None), ("G", "R"),
                  *[(f"P{i}", "G") for i in range(n)])


def segmentos(d: str) -> list[tuple[float, float, float, float]]:
    """'M x y L x y M …' -> [(x1, y1, x2, y2), …]. Falha se o path fugir do contrato."""
    t = d.split()
    segs = []
    for i in range(0, len(t), 6):
        assert t[i] == "M" and t[i + 3] == "L", f"path fora do contrato: {d}"
        segs.append(tuple(float(v) for v in (t[i + 1], t[i + 2], t[i + 4], t[i + 5])))
    return segs


def horizontais(d: str) -> list[tuple[float, float, float, float]]:
    return [s for s in segmentos(d) if s[1] == s[3] and s[0] != s[2]]


def desenhar(layout: dict) -> str:
    """Serializa pelo mesmo template da tela — a saida de verdade (ADR-011)."""
    from jinja2 import Environment, FileSystemLoader

    from orga.cargos import niveis_padrao
    from orga.configuracao import cores_canvas
    from orga import idiomas

    env = Environment(loader=FileSystemLoader(
        str(Path(__file__).resolve().parents[1] / "web" / "templates")))
    # O template pede `t` como qualquer outro global que o app injeta. Aqui ele
    # entra fixo em pt-BR: o que este teste compara é geometria, e deixá-lo
    # seguir o idioma vigente faria a comparação depender de configuração.
    return env.get_template("_canvas.html").render(
        layout=layout, exportando=True, k=cores_canvas(True),
        t=lambda texto, **p: idiomas.traduzir(texto, idiomas.PADRAO, **p),
        cores_nivel={n["codigo"]: n["cor"] for n in niveis_padrao()})


# --- T-L01 / T-L02 ---------------------------------------------------------
def test_TL01_no_unico_invertida():
    L = calcular_layout(arvore(("r", None)), "invertida")
    assert L["nos"][0]["y"] == MARGEM
    assert L["conectores"] == []
    assert L["profundidade_max"] == 0


def test_TL02_no_unico_orientacoes_identicas():
    """LAY-03: com D = 0 as duas orientacoes produzem a mesma saida.

    A comparacao e feita sobre o desenho serializado, nao sobre o dicionario:
    as ancoras seguem existindo em faces opostas (LAY-04), mas com D = 0 nao
    ha conector que as use. `<title>`/`<desc>` ficam de fora porque A11Y-04
    exige que declarem a orientacao — la a diferenca e obrigatoria.
    """
    us = arvore(("r", None))
    inv = calcular_layout(us, "invertida")
    ver = calcular_layout(us, "vertical")
    desenho = lambda L: desenhar(L).split("</desc>")[1]          # noqa: E731
    assert desenho(inv) == desenho(ver)
    assert [(n["x"], n["y"], n["h"]) for n in inv["nos"]] == \
           [(n["x"], n["y"], n["h"]) for n in ver["nos"]]
    assert inv["viewbox"] == ver["viewbox"]


# --- T-L03 -----------------------------------------------------------------
def test_TL03_invariante_da_inversao():
    """Y(pai) > Y(filho) + altura(filho) para todo par — SPEC §18."""
    us = arvore(("r", None), *[(f"f{i}", "r") for i in range(5)])
    L = calcular_layout(us, "invertida")
    ix = indice(L)
    for i in range(5):
        assert ix["r"]["y"] > ix[f"f{i}"]["y"] + ix[f"f{i}"]["h"]


def test_TL03b_vertical_espelha_a_relacao():
    us = arvore(("r", None), *[(f"f{i}", "r") for i in range(5)])
    L = calcular_layout(us, "vertical")
    ix = indice(L)
    for i in range(5):
        assert ix[f"f{i}"]["y"] > ix["r"]["y"] + ix["r"]["h"]


# --- T-L04 / LAY-05 / LAY-06 ----------------------------------------------
def test_TL04_filho_unico_sem_barramento():
    L = calcular_layout(arvore(("r", None), ("f", "r")), "invertida")
    d = L["conectores"][0]["d"]
    assert d.count("M") == 1 and d.count("L") == 1


def test_LAY05_barramento_e_segmento_unico():
    """Um segmento de min a max, nao n segmentos empilhados."""
    us = arvore(("r", None), ("a", "r"), ("b", "r"), ("c", "r"))
    L = calcular_layout(us, "invertida")
    ix = indice(L)
    barras = horizontais(L["conectores"][0]["d"])
    assert len(barras) == 1
    cxs = [ix[k]["cx"] for k in ("a", "b", "c")]
    assert barras[0] == (min(cxs), ix["r"]["y"] - GAP_V / 2,
                         max(cxs), ix["r"]["y"] - GAP_V / 2)


# --- T-L05 -----------------------------------------------------------------
def test_TL05_profundidade_3_barramentos_distintos():
    us = arvore(("r", None), ("a", "r"), ("b", "r"),
                ("a1", "a"), ("a2", "a"), ("a1x", "a1"), ("a1y", "a1"))
    L = calcular_layout(us, "invertida")
    assert L["profundidade_max"] == 3
    barras = [b for c in L["conectores"] for b in horizontais(c["d"])]
    assert len(barras) == 3                       # um por pai com 2+ filhos
    assert len({b[1] for b in barras}) == 3       # em alturas distintas
    for x1, y, x2, _ in barras:                   # nenhum atravessa um card
        for n in L["nos"]:
            atravessa = (n["y"] < y < n["y"] + n["h"]
                         and x1 < n["x"] + n["w"] and x2 > n["x"])
            assert not atravessa, f"barramento cruza {n['id']}"


# --- T-L06 -----------------------------------------------------------------
def test_TL06_desempate_ordem_nome_id():
    """LAY-12: (ordem, nome, id). Sem o id, RNF-02 cai."""
    us = arvore(("r", None))
    for uid, nome in (("z9", "Beta"), ("a1", "Alfa"), ("a0", "Alfa")):
        us[uid] = Unidade(id=uid, codigo="ORG-9999", nome=nome, tipo="area",
                          parent_id="r", ordem=10)
    ordem = [f.id for f in mapa_filhos(us)["r"]]
    assert ordem == ["a0", "a1", "z9"]


# --- T-L07 -----------------------------------------------------------------
def test_TL07_determinismo_100_execucoes():
    """RNF-02: mesma entrada, saida identica em 100 execucoes."""
    us = arvore(("r", None), ("a", "r"), ("b", "r"), ("a1", "a"), ("a2", "a"))
    referencia = repr(calcular_layout(us, "invertida"))
    assert all(repr(calcular_layout(us, "invertida")) == referencia
               for _ in range(99))


# --- T-L08 -----------------------------------------------------------------
def test_TL08_cabecalho_sempre_interno():
    """LAY-10: cabecalho e faixa dentro do card, em qualquer profundidade."""
    us = arvore(("r", None), ("a", "r"), ("a1", "a"))
    for orient in ("invertida", "vertical"):
        for n in calcular_layout(us, orient)["nos"]:
            for t in n["textos"]:
                assert n["y"] <= t["y"] <= n["y"] + n["h"]
                assert n["x"] <= t["x"] <= n["x"] + n["w"]


# --- T-L09 -----------------------------------------------------------------
def test_TL09_viewbox_e_o_bbox_real():
    """LAY-14: bounding box do conteudo + margem, nunca constante."""
    us = arvore(("r", None), ("a", "r"), ("b", "r"))
    L = calcular_layout(us, "invertida")
    _, _, w, h = (float(v) for v in L["viewbox"].split())
    assert w == max(n["x"] + n["w"] for n in L["nos"]) + MARGEM
    assert h == max(n["y"] + n["h"] for n in L["nos"]) + MARGEM
    assert all(n["x"] >= MARGEM and n["y"] >= MARGEM for n in L["nos"])


def test_viewbox_cresce_com_a_arvore():
    pequena = calcular_layout(arvore(("r", None), ("a", "r")), "invertida")
    grande = calcular_layout(arvore(("r", None), ("a", "r"), ("b", "r")), "invertida")
    assert float(grande["viewbox"].split()[2]) > float(pequena["viewbox"].split()[2])


# --- geometria e ancoras ---------------------------------------------------
def test_ancoras_derivam_da_orientacao():
    """LAY-04: ancora nao e coordenada fixa do card."""
    us = arvore(("r", None), ("a", "r"))
    inv = indice(calcular_layout(us, "invertida"))["r"]
    ver = indice(calcular_layout(us, "vertical"))["r"]
    assert inv["ancora_pai"] == inv["y"]                    # aresta superior
    assert ver["ancora_pai"] == ver["y"] + ver["h"]         # aresta inferior


def test_subarvores_nao_se_sobrepoem_em_x():
    us = arvore(("r", None), ("a", "r"), ("b", "r"),
                ("a1", "a"), ("a2", "a"), ("b1", "b"), ("b2", "b"))
    ix = indice(calcular_layout(us, "invertida"))
    assert max(ix["a1"]["x"], ix["a2"]["x"]) + CARD_W <= min(ix["b1"]["x"], ix["b2"]["x"])
    assert ix["a"]["cx"] == pytest.approx((ix["a1"]["cx"] + ix["a2"]["cx"]) / 2)


def test_espacamento_entre_irmaos_folha():
    us = arvore(("r", None), ("a", "r"), ("b", "r"))
    ix = indice(calcular_layout(us, "invertida"))
    assert ix["b"]["x"] - ix["a"]["x"] == CARD_W + GAP_H


def test_ordem_do_dom_e_logica():
    """FE-03 / A11Y-03: raiz primeiro, pre-ordem, independente da posicao."""
    us = arvore(("r", None), ("a", "r"), ("b", "r"), ("a1", "a"))
    for orient in ("invertida", "vertical"):
        ids = [n["id"] for n in calcular_layout(us, orient)["nos"]]
        assert ids == ["r", "a", "a1", "b"]


def test_aria_level_ignora_a_inversao():
    """A11Y-02: nivel logico, raiz = 0 no dado (1 no ARIA)."""
    us = arvore(("r", None), ("a", "r"), ("a1", "a"))
    for orient in ("invertida", "vertical"):
        ix = indice(calcular_layout(us, orient))
        assert (ix["r"]["nivel"], ix["a"]["nivel"], ix["a1"]["nivel"]) == (0, 1, 2)


def test_alternar_orientacao_nao_remonta_o_dom():
    """W5-C7: mesmos nos, mesma ordem; so as coordenadas mudam."""
    us = arvore(("r", None), ("a", "r"), ("b", "r"), ("a1", "a"))
    inv = calcular_layout(us, "invertida")
    ver = calcular_layout(us, "vertical")
    assert [n["id"] for n in inv["nos"]] == [n["id"] for n in ver["nos"]]
    assert [n["x"] for n in inv["nos"]] == [n["x"] for n in ver["nos"]]
    assert [n["y"] for n in inv["nos"]] != [n["y"] for n in ver["nos"]]


# --- colapso e foco --------------------------------------------------------
def test_colapso_remove_subarvore_do_desenho():
    us = arvore(("r", None), ("a", "r"), ("a1", "a"), ("a2", "a"))
    L = calcular_layout(us, "invertida", colapsados={"a"})
    assert {n["id"] for n in L["nos"]} == {"r", "a"}
    assert indice(L)["a"]["ocultos"] == 2
    assert L["total_oculto"] == 2


def test_colapso_de_folha_nao_gera_alca():
    us = arvore(("r", None), ("a", "r"))
    L = calcular_layout(us, "invertida", colapsados={"a"})
    assert [x["id"] for x in L["alcas"]] == ["r"]


def test_foco_desenha_apenas_a_subarvore_preservando_o_nivel():
    """SIG-02: a cota mostra o nivel logico, nao a posicao na tela."""
    us = arvore(("r", None), ("a", "r"), ("a1", "a"), ("b", "r"))
    L = calcular_layout(us, "invertida", foco="a")
    assert {n["id"] for n in L["nos"]} == {"a", "a1"}
    assert indice(L)["a"]["nivel"] == 1
    assert [c["rotulo"] for c in L["cotas"]] == ["N1", "N2"]


def test_destaque_marca_os_achados():
    us = arvore(("r", None), ("a", "r"))
    L = calcular_layout(us, "invertida", destaque={"a"})
    assert indice(L)["a"]["achou"] and not indice(L)["r"]["achou"]


# --- card ------------------------------------------------------------------
def test_altura_cresce_com_accountabilities():
    u = Unidade(id="x", codigo="ORG-0001", nome="X", tipo="area",
                parent_id=None, ordem=0)
    _, base = montar_card(u, 0, 0)
    u.responsabilidades = [{"descricao": f"item {i}", "origem": "propria"}
                           for i in range(5)]
    _, cheio = montar_card(u, 0, 0)
    assert cheio > base


def test_excedente_de_accountabilities_vira_resumo():
    u = Unidade(id="x", codigo="ORG-0001", nome="X", tipo="area", parent_id=None,
                ordem=0, responsabilidades=[{"descricao": f"i{i}", "origem": "propria"}
                                            for i in range(9)])
    card, _ = montar_card(u, 0, 0)
    assert card["itens"][-1]["txt"].startswith("+ 3")


def test_delegada_tem_marcador_proprio():
    """A11Y-06: a distincao nao pode depender so de cor."""
    u = Unidade(id="x", codigo="ORG-0001", nome="X", tipo="area", parent_id=None,
                ordem=0, responsabilidades=[
                    {"descricao": "propria", "origem": "propria"},
                    {"descricao": "delegada", "origem": "delegada"}])
    card, _ = montar_card(u, 0, 0)
    assert [i["delegada"] for i in card["itens"]] == [False, True]


def test_quebra_de_linha_sinaliza_corte():
    linhas = quebrar("palavra " * 40, 100, 5.6, 2)
    assert len(linhas) == 2 and linhas[-1].endswith("…")
    assert quebrar("", 100, 5.6, 2) == []


def test_palavra_maior_que_a_linha_e_truncada():
    assert quebrar("A" * 80, 60, 5.6, 1)[0].endswith("…")


def test_coordenadas_com_duas_casas():
    """LAY-13."""
    us = arvore(("r", None), ("a", "r"), ("b", "r"), ("c", "r"))
    for n in calcular_layout(us, "invertida")["nos"]:
        for chave in ("x", "y", "w", "h", "cx"):
            assert round(n[chave], 2) == n[chave]


def test_cabecalho_reserva_faixa_no_topo():
    us = arvore(("r", None))
    sem = calcular_layout(us, "invertida")
    com = calcular_layout(us, "invertida", cabecalho={"titulo": "t", "linhas": [],
                                                      "escopo": None, "data": "x"})
    assert com["altura"] > sem["altura"]
    assert com["nos"][0]["y"] > sem["nos"][0]["y"]


# --- guardas do dominio ----------------------------------------------------
def test_raiz_unica_exigida():
    with pytest.raises(ValueError):
        raiz({})


# ---------------------------------------------------------------------------
# PILHAS DE IRMÃOS-FOLHA
# ---------------------------------------------------------------------------
def test_irmaos_folha_demais_empilham_e_o_desenho_estreita():
    """Uma equipe de 17 numa fileira só empurra o desenho para 17 larguras de
    card. Em pilhas de 5 ela ocupa 4 — é a mesma informação em 1/4 do papel."""
    from orga.dominio import PADRAO

    largo = calcular_layout(equipe_larga(17))["largura"]
    fila = calcular_layout(equipe_larga(17),
                           tokens=PADRAO.com(pilha_cards=0))["largura"]
    assert largo < fila
    # 4 colunas contra 17: sobra folga, mas a ordem de grandeza é essa.
    assert largo < fila / 3


def test_poucos_irmaos_continuam_em_fila():
    """Cinco em fila cabem. Empilhar aí só faria o desenho crescer em altura
    sem ganhar nada em largura."""
    from orga.dominio import PADRAO

    for n in (2, 5):
        a = calcular_layout(equipe_larga(n))["largura"]
        b = calcular_layout(equipe_larga(n), tokens=PADRAO.com(pilha_cards=0))["largura"]
        assert a == b


def test_a_pilha_respeita_o_invariante_da_orientacao_invertida():
    """Y(pai) > Y(filho) + altura(filho) para todo par — inclusive para o card
    mais alto da pilha, que é o mais distante do pai."""
    lay = calcular_layout(equipe_larga(17), "invertida")
    ix = indice(lay)
    pai = ix["G"]
    for i in range(17):
        f = ix[f"P{i}"]
        assert pai["y"] > f["y"] + f["h"], f"P{i} não está acima do gestor"


def test_a_pilha_nao_sobrepoe_card_nenhum():
    lay = calcular_layout(equipe_larga(17))
    cards = [ix for uid, ix in indice(lay).items() if uid.startswith("P")]
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            separados = (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"]
                         or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])
            assert separados, "dois cards da pilha se sobrepõem"


def test_empilhar_nao_cria_faixa_nova_de_nivel():
    """A pilha cresce dentro da faixa do próprio nível: a cota continua sendo
    uma por nível, e o card empilhado não muda de N."""
    lay = calcular_layout(equipe_larga(17))
    assert len(lay["cotas"]) == lay["profundidade_max"] + 1
    niveis = {n["nivel"] for uid, n in indice(lay).items() if uid.startswith("P")}
    assert niveis == {2}


def test_a_faixa_engorda_para_caber_a_pilha():
    ix = indice(calcular_layout(equipe_larga(17)))
    ys = {round(ix[f"P{i}"]["y"], 2) for i in range(17)}
    assert len(ys) == 5                      # cinco degraus de pilha
    cota = [c for c in calcular_layout(equipe_larga(17))["cotas"]
            if c["rotulo"] == "N2"][0]
    # `ini`/`fim` e a faixa no eixo que a orientacao usar: Y nas pirâmides, X
    # na lateral. Nomeá-la por eixo dava dois vocabulários para a mesma medida.
    for i in range(17):
        c = ix[f"P{i}"]
        assert cota["ini"] <= c["y"] and c["y"] + c["h"] <= cota["fim"] + .01


def test_a_coluna_empilhada_ganha_um_trilho_e_nao_um_fio_por_card():
    """Um fio por card cruzaria os de baixo. O trilho passa atrás deles."""
    lay = calcular_layout(equipe_larga(17))
    d = [c for c in lay["conectores"] if c["pai"] == "G"][0]["d"]
    verticais = [s for s in segmentos(d) if abs(s[0] - s[2]) < .01]
    # um por coluna, mais a descida do próprio gestor até o barramento
    assert len(verticais) == 4 + 1


def test_familia_mista_empilha_as_folhas_e_deixa_quem_tem_equipe_na_fileira():
    """Contam as folhas, não o total de irmãos.

    A regra antiga — "só grupos puros" — punia justamente o caso mais comum:
    um gerente que acumula time e reportes diretos. Um único irmão com equipe
    deixava as outras oito folhas esticadas numa fileira.

    Quem tem subárvore continua fora da pilha: empilhá-lo faria a subárvore
    dele colidir com a do irmão ao lado, e o motor perde a garantia de
    intervalos disjuntos em X.
    """
    us = equipe_larga(8)
    us.update(arvore(("NETO", "P0")))        # P0 vira gestor; P1..P7 são folhas
    ix = indice(calcular_layout(us))

    folhas = {round(ix[f"P{i}"]["y"], 2) for i in range(1, 8)}
    assert len(folhas) > 1, "as sete folhas deveriam empilhar"
    # P0 tem equipe: fica na fileira, encostado na base da faixa como qualquer
    # nó não empilhado.
    assert round(ix["P0"]["y"] + ix["P0"]["h"], 2) == max(
        round(ix[f"P{i}"]["y"] + ix[f"P{i}"]["h"], 2) for i in range(1, 8))
    # e a subárvore dele não colide com ninguém
    assert ix["NETO"]["y"] + ix["NETO"]["h"] < ix["P0"]["y"]


def test_duas_execucoes_desenham_igual_com_pilha():
    """RNF-02 continua valendo: mesma entrada, mesmos bytes."""
    a = calcular_layout(equipe_larga(17))
    b = calcular_layout(equipe_larga(17))
    assert [(n["id"], n["x"], n["y"]) for n in a["nos"]] == \
           [(n["id"], n["x"], n["y"]) for n in b["nos"]]
    assert a["conectores"] == b["conectores"]


def test_a_pilha_tambem_vale_na_orientacao_convencional():
    lay = calcular_layout(equipe_larga(17), "vertical")
    ix = indice(lay)
    pai = ix["G"]
    for i in range(17):
        f = ix[f"P{i}"]
        assert f["y"] > pai["y"] + pai["h"] - .01


def test_a_pilha_separa_por_time():
    """Uma coluna que mistura Infrastructure com Cybersecurity não responde
    "quem faz o quê" — que é a pergunta que o empilhamento tornou legível."""
    us = arvore(("R", None), ("G", "R"))
    times = ["Infra"] * 5 + ["Cyber"] * 3
    for i, time in enumerate(times):
        us[f"P{i}"] = Unidade(id=f"P{i}", codigo=f"ORG-{i:04d}", nome=f"P{i}",
                              tipo="celula", parent_id="G", ordem=(i + 1) * 10,
                              area=time)
    ix = indice(calcular_layout(us))
    colunas = {}
    for i, time in enumerate(times):
        colunas.setdefault(round(ix[f"P{i}"]["x"], 2), set()).add(time)
    for x, ts in colunas.items():
        assert len(ts) == 1, f"coluna em x={x} mistura {ts}"


def test_a_ordem_dos_times_e_a_da_arvore_e_nao_a_alfabetica():
    """Assim o desenho não se reorganiza sozinho quando alguém renomeia um time."""
    us = arvore(("R", None), ("G", "R"))
    times = ["Zulu"] * 3 + ["Alfa"] * 3
    for i, time in enumerate(times):
        us[f"P{i}"] = Unidade(id=f"P{i}", codigo=f"ORG-{i:04d}", nome=f"P{i}",
                              tipo="celula", parent_id="G", ordem=(i + 1) * 10,
                              area=time)
    ix = indice(calcular_layout(us))
    assert ix["P0"]["x"] < ix["P3"]["x"]        # Zulu veio primeiro na árvore


def test_gestor_dobrado_nao_empilha_e_a_fileira_se_mantem():
    """Nó dobrado ocupa uma coluna e nada abaixo, mas é gestor com equipe atrás
    do `+n`. A fileira é o que mostra quantas frentes a empresa tem naquele
    nível — empilhar gerência esconde a leitura que o nível existe para dar."""
    us = arvore(("R", None), ("G", "R"))
    for i in range(8):
        us[f"M{i}"] = Unidade(id=f"M{i}", codigo=f"ORG-{i:04d}", nome=f"M{i}",
                              tipo="gerencia", parent_id="G", ordem=(i + 1) * 10,
                              area="Time")
        us[f"E{i}"] = Unidade(id=f"E{i}", codigo=f"ORG-9{i:03d}", nome=f"E{i}",
                              tipo="celula", parent_id=f"M{i}", ordem=10,
                              area="Time")
    dobrados = {f"M{i}" for i in range(8)}
    ix = indice(calcular_layout(us, colapsados=dobrados))
    ys = {round(ix[f"M{i}"]["y"], 2) for i in range(8)}
    assert len(ys) == 1, "os gestores dobrados deveriam estar na mesma fileira"


def test_folha_de_verdade_continua_empilhando():
    ix = indice(calcular_layout(equipe_larga(12)))
    assert len({round(ix[f"P{i}"]["y"], 2) for i in range(12)}) > 1


# ---------------------------------------------------------------------------
# ORIENTAÇÃO LATERAL — ÁRVORE INDENTADA
# ---------------------------------------------------------------------------
def familia() -> dict[str, Unidade]:
    return arvore(("r", None), ("a", "r"), ("a1", "a"), ("a2", "a"),
                  ("b", "r"), ("b1", "b"))


def test_lateral_a_profundidade_anda_para_a_direita():
    """Cada nível é uma coluna, e a coluna é a mesma para todos daquele nível."""
    ix = indice(calcular_layout(familia(), "lateral"))
    assert ix["a"]["x"] == ix["b"]["x"] == ix["r"]["x"] + CARD_W + GAP_H
    assert ix["a1"]["x"] == ix["a2"]["x"] == ix["b1"]["x"] == ix["a"]["x"] + CARD_W + GAP_H


def test_lateral_a_leitura_desce_na_ordem_logica():
    """O que faz esta vista caber num celular é a ordem do documento ser a
    ordem da tela: pré-ordem, sem eixo transversal a distribuir."""
    L = calcular_layout(familia(), "lateral")
    assert [n["id"] for n in L["nos"]] == ["r", "a", "a1", "a2", "b", "b1"]
    ys = [n["y"] for n in L["nos"]]
    assert ys == sorted(ys), "a ordem do DOM tem de ser a ordem vertical"


def test_lateral_nenhum_card_encosta_no_outro():
    L = calcular_layout(familia(), "lateral")
    for i, a in enumerate(L["nos"]):
        for b in L["nos"][i + 1:]:
            separados = (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"]
                         or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])
            assert separados, f"{a['id']} e {b['id']} se sobrepõem"


def test_lateral_o_barramento_corre_na_calha_e_nao_cruza_card():
    """A calha entre a coluna do pai e a dos filhos tem `gap_h` de largura e
    nenhum card cai nela — é o que deixa o barramento atravessar a subárvore
    inteira como segmento único (LAY-05)."""
    L = calcular_layout(familia(), "lateral")
    d = [c for c in L["conectores"] if c["pai"] == "r"][0]["d"]
    verticais = [s for s in segmentos(d) if s[0] == s[2] and s[1] != s[3]]
    assert len(verticais) == 1, "o barramento tem de ser um segmento só"
    for x1, y1, x2, y2 in segmentos(d):
        for n in L["nos"]:
            dentro_x = n["x"] < max(x1, x2) and min(x1, x2) < n["x"] + n["w"]
            dentro_y = n["y"] < max(y1, y2) and min(y1, y2) < n["y"] + n["h"]
            assert not (dentro_x and dentro_y), f"o fio cruza {n['id']}"


def test_lateral_estreita_o_desenho():
    """É a razão de existir da vista. A largura da lateral é (D+1) colunas e
    não depende de quanta gente há no nível — que é justamente o que faz a
    pirâmide crescer para o lado.

    Contra a fileira crua o ganho é de uma ordem de grandeza; contra a pirâmide
    já empilhada ele é menor, porque o empilhamento resolve o mesmo problema
    pela metade. Mas a lateral continua mais estreita, e é a única das três em
    que 17 ou 170 pessoas dão a mesma largura.
    """
    from orga.dominio import PADRAO

    fileira = calcular_layout(equipe_larga(17), "invertida",
                              tokens=PADRAO.com(pilha_cards=0))["largura"]
    piramide = calcular_layout(equipe_larga(17), "invertida")["largura"]
    lat = calcular_layout(equipe_larga(17), "lateral")["largura"]
    assert lat < fileira / 3
    assert lat < piramide
    assert lat == calcular_layout(equipe_larga(170), "lateral")["largura"]


def test_lateral_a_cota_vira_regua_no_topo():
    """Os níveis viraram colunas: a faixa de cada um é horizontal, e o trilho
    corre no topo em vez de à esquerda."""
    L = calcular_layout(familia(), "lateral")
    ix = indice(L)
    assert L["trilho"]["y1"] == L["trilho"]["y2"]           # trilho deitado
    assert L["trilho"]["x1"] < L["trilho"]["x2"]
    n1 = [c for c in L["cotas"] if c["rotulo"] == "N1"][0]
    assert n1["ini"] == ix["a"]["x"] and n1["fim"] == ix["a"]["x"] + CARD_W
    assert n1["texto"]["ancora"] == "middle"
    assert L["trilho"]["y1"] < min(n["y"] for n in L["nos"])


def test_a_cota_da_piramide_nao_mudou_de_lugar():
    """A representação da cota passou a ser geométrica para as três orientações.
    Os números das duas antigas têm de continuar sendo os mesmos de sempre."""
    L = calcular_layout(familia(), "invertida")
    trilho_x = MARGEM + 34 - 20                     # TRILHO_X, como antes
    assert L["trilho"] == {"x1": trilho_x, "y1": min(c["ini"] for c in L["cotas"]),
                           "x2": trilho_x, "y2": max(c["fim"] for c in L["cotas"])}
    c = L["cotas"][0]
    assert c["t1"] == {"x1": trilho_x - 4, "y1": c["ini"],
                       "x2": trilho_x + 4, "y2": c["ini"]}
    assert c["texto"] == {"x": trilho_x - 9, "y": round(c["meio"] + 3, 2),
                          "ancora": "end"}
    assert c["marco"] == {"x": trilho_x - 3, "y": round(c["meio"] - 3, 2)}


def test_lateral_o_viewbox_continua_sendo_o_bbox_real():
    """LAY-14 não tem exceção por orientação."""
    L = calcular_layout(familia(), "lateral")
    _, _, w, h = (float(v) for v in L["viewbox"].split())
    assert w == max(n["x"] + n["w"] for n in L["nos"]) + MARGEM
    assert h == max(n["y"] + n["h"] for n in L["nos"]) + MARGEM


def test_lateral_e_deterministica():
    """RNF-02 vale para as três orientações."""
    ref = repr(calcular_layout(familia(), "lateral"))
    assert all(repr(calcular_layout(familia(), "lateral")) == ref for _ in range(20))


def test_lateral_com_um_no_so_nao_tem_fio_nem_quebra():
    L = calcular_layout(arvore(("r", None)), "lateral")
    assert L["conectores"] == [] and L["profundidade_max"] == 0
    assert len(L["cotas"]) == 1


def test_lateral_nao_remonta_o_dom():
    """W5-C7: mesmos nós, mesma ordem — só as coordenadas mudam."""
    us = familia()
    inv = calcular_layout(us, "invertida")
    lat = calcular_layout(us, "lateral")
    assert [n["id"] for n in inv["nos"]] == [n["id"] for n in lat["nos"]]
    assert [n["nivel"] for n in inv["nos"]] == [n["nivel"] for n in lat["nos"]]


def test_lateral_respeita_colapso_foco_e_cabecalho():
    us = familia()
    dobrada = calcular_layout(us, "lateral", colapsados={"a"})
    assert {n["id"] for n in dobrada["nos"]} == {"r", "a", "b", "b1"}
    focada = calcular_layout(us, "lateral", foco="a")
    assert {n["id"] for n in focada["nos"]} == {"a", "a1", "a2"}
    assert [c["rotulo"] for c in focada["cotas"]] == ["N1", "N2"]
    com = calcular_layout(us, "lateral", cabecalho={"titulo": "t", "linhas": [],
                                                    "escopo": None, "data": "x"})
    assert com["nos"][0]["y"] > calcular_layout(us, "lateral")["nos"][0]["y"]


def test_lateral_nao_empilha():
    """O empilhamento existe para estreitar um desenho deitado. Aqui o desenho
    já nasce estreito, e empilhar só quebraria a ordem de leitura."""
    ix = indice(calcular_layout(equipe_larga(17), "lateral"))
    xs = {ix[f"P{i}"]["x"] for i in range(17)}
    assert len(xs) == 1, "as 17 folhas têm de ficar na mesma coluna"


def test_lateral_coordenadas_com_duas_casas():
    """LAY-13."""
    for n in calcular_layout(familia(), "lateral")["nos"]:
        for chave in ("x", "y", "w", "h", "cx", "cy"):
            assert round(n[chave], 2) == n[chave]


# ---------------------------------------------------------------------------
# A MARCA DO CLIENTE NO CARD DA RAIZ
# ---------------------------------------------------------------------------
def _raiz_com_conteudo() -> Unidade:
    return Unidade(
        id="r", codigo="ORG-0001", nome="Board", tipo="diretoria", parent_id=None,
        ordem=0, cargo="Conselho", area="Governança",
        responsabilidades=[{"descricao": "Estratégia", "origem": "propria"},
                           {"descricao": "Risco", "origem": "propria"}],
        competencias=["Governança", "Capital"])


def test_a_marca_e_desenhada_onde_o_card_reservou():
    """Duas contas para o mesmo retângulo divergiam: a altura reservava a marca
    no pé do card e o desenho a ancorava na régua de identidade, no topo. Com a
    raiz vazia sobravam 29 px mortos; com uma accountability, a imagem era
    pintada por cima do texto."""
    card, altura = montar_card(_raiz_com_conteudo(), 40, 74)
    m = card["marca"]
    faixa = (m["y"], m["y"] + m["h"])
    for t in card["itens"] + card["skills"]:
        assert not (faixa[0] <= t["y"] <= faixa[1]), \
            f"a marca cobre {t['txt']!r}"
    # e ela fecha o card, sem sobra: o pé do card é o pé da marca mais o respiro
    assert card["y"] + altura - (m["y"] + m["h"]) <= 14


def test_a_marca_sai_no_mesmo_arredondamento_do_card():
    """LAY-13: derivada do `x` bruto, ela emitia mais casas que o card e deixava
    de casar com a borda que a contém."""
    from orga.dominio import _arredondar_card

    card = _arredondar_card(montar_card(_raiz_com_conteudo(), 40.333333, 74.777)[0])
    m = card["marca"]
    assert m["x"] == card["x"] + 20, "a marca tem de sair do x já arredondado"
    for v in (m["x"], m["y"]):
        assert round(v, 2) == v


def test_sem_marca_o_card_da_raiz_nao_reserva_espaco():
    """A exportação não desenha a imagem — nem o SVG solto, que viraria quadrado
    vazio no Inkscape, nem o PDF, que não tem imagem. Reservar 55 px que ninguém
    preenche deixava um bloco branco no card mais visível do papel."""
    from orga.dominio import PADRAO

    u = _raiz_com_conteudo()
    _, com = montar_card(u, 40, 74)
    card, sem = montar_card(u, 40, 74, PADRAO.com(marca=False))
    assert sem < com
    assert card["marca"] is None
    assert card["raiz"] is True          # continua sendo a raiz: pinta grafite


def test_a_raiz_continua_grafite_na_exportacao():
    from orga.dominio import PADRAO

    L = calcular_layout(familia(), "invertida", tokens=PADRAO.com(marca=False))
    assert indice(L)["r"]["raiz"] is True
    assert indice(L)["a"]["raiz"] is False


# ---------------------------------------------------------------------------
# A legenda do desenho conta os NÓS DESENHADOS, não o total do estado.
# O usuário via "272 unidades · profundidade 5" embaixo de 6 caixas dobradas.
# ---------------------------------------------------------------------------
def test_cabecalho_segue_os_nos_desenhados():
    from orga import main

    # três cards desenhados, o mais fundo no nível 2 → "3 unidades · profundidade 2"
    lay = {"cabecalho": {"linhas": ["a-substituir", "filtro ativo · 9"]},
           "nos": [{"id": "R", "nivel": 0}, {"id": "A", "nivel": 1},
                   {"id": "B", "nivel": 2}]}
    main._ajustar_cabecalho_ao_desenho(lay)
    assert lay["cabecalho"]["linhas"][0].startswith("3 unidades · profundidade 2")
    # a segunda linha (o "filtro ativo …") não é tocada
    assert lay["cabecalho"]["linhas"][1] == "filtro ativo · 9"


def test_cabecalho_no_modo_equipe_conta_equipes_desenhadas():
    from orga import main

    lay = {"cabecalho": {"linhas": ["x"]},
           "nos": [{"id": "T1", "nivel": 0}, {"id": "T2", "nivel": 1}]}
    main._ajustar_cabecalho_ao_desenho(lay, pessoas=40)
    assert lay["cabecalho"]["linhas"][0].startswith(
        "2 equipes · 40 pessoas · profundidade 1")


def test_ajuste_do_cabecalho_nao_quebra_sem_cabecalho():
    from orga import main

    # com_cabecalho=False deixa cabecalho=None: o ajuste não pode estourar
    assert main._ajustar_cabecalho_ao_desenho({"nos": []}) == {"nos": []}
    assert main._ajustar_cabecalho_ao_desenho(
        {"cabecalho": None, "nos": [{"id": "R", "nivel": 0}]})["cabecalho"] is None
