"""Exporta o estado do sistema para um XLSX 'avançado' — todas as tabelas, os
vínculos (VLOOKUP vivo) e um Painel de RH/DP com gráficos. Recebe o estado
serializado (dict) e devolve os bytes do arquivo. Espelha o que a vista Painel RH
mostra, para tela e planilha nunca divergirem."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from . import dominio

GRAFITE, LARANJA, AMBAR = "2D3336", "EB6A20", "F6A709"
LINHA, CINZA, BRANCO = "D9DBDC", "F4F5F6", "FFFFFF"
_hdr = Font(bold=True, color=BRANCO, size=11)
_fill = PatternFill("solid", fgColor=GRAFITE)
_tit = Font(bold=True, color=GRAFITE, size=18)
_sub = Font(color="4A5053", size=10)
_lbl = Font(bold=True, color=GRAFITE, size=11)
_al = Alignment(horizontal="left", vertical="center")
_altop = Alignment(horizontal="left", vertical="top", wrap_text=True)
_alc = Alignment(horizontal="center", vertical="center")
_bd = Border(*(Side(style="thin", color=LINHA),) * 4)
_LARGAS = {"Payload", "Accountabilities", "Competências", "Módulos visíveis",
           "Mensagem", "O que significa"}
FAIXAS = [("< 1 ano", 0, 1), ("1 a 3 anos", 1, 3), ("3 a 5 anos", 3, 5),
          ("5 a 10 anos", 5, 10), ("10+ anos", 10, 999)]


def _s(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Sim" if v else "Não"
    if isinstance(v, (list, tuple)):
        return " | ".join(_s(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return v


def _tab(ws, nome, cols, linhas, larg=None, r0=1, congelar=None):
    for j, c in enumerate(cols, 1):
        cel = ws.cell(r0, j, c)
        cel.font, cel.fill, cel.alignment, cel.border = _hdr, _fill, _al, _bd
    for i, ln in enumerate(linhas, 1):
        for j, c in enumerate(cols, 1):
            val = ln.get(c, "")
            val = val if isinstance(val, str) and val.startswith("=") else _s(val)
            cel = ws.cell(r0 + i, j, val)
            cel.alignment = _altop if c in _LARGAS else _al
            cel.border = _bd
            if (r0 + i) % 2 == 0:
                cel.fill = PatternFill("solid", fgColor=CINZA)
    if linhas:
        ref = "%s%d:%s%d" % (get_column_letter(1), r0,
                             get_column_letter(len(cols)), r0 + len(linhas))
        t = Table(displayName=nome, ref=ref)
        t.tableStyleInfo = TableStyleInfo(name="TableStyleMedium1")
        ws.add_table(t)
    for j, c in enumerate(cols, 1):
        w = (larg or {}).get(c)
        if not w:
            comp = max([len(str(c))] + [len(str(_s(l.get(c, "")))) for l in linhas[:200]])
            w = min(max(comp + 2, 10), 60)
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws[congelar or ("A%d" % (r0 + 1))]
    ws.sheet_view.showGridLines = False


def _iso(v):
    try:
        return tuple(int(x) for x in str(v).split("-")[:3])
    except Exception:
        return None


def gerar(d: dict, mapa_cc: dict | None = None, ref: date | None = None) -> bytes:
    """`d` é o estado serializado (json.loads(serializar())). Devolve os bytes do
    XLSX. `mapa_cc` (uid->{n5,...}) alimenta o vínculo com o cadastro de CC."""
    ref = ref or date.today()
    mapa_cc = mapa_cc or {}
    uni = d["unidades"]
    cfg = d.get("config", {})
    nome_de = {i: u.get("nome", "") for i, u in uni.items()}
    cargo_de = {i: u.get("cargo", "") for i, u in uni.items()}
    rot_niv = {n["codigo"]: n["rotulo"] for n in cfg.get("niveis", []) if isinstance(n, dict)}
    wb = Workbook()
    idx = wb.active
    idx.title = "Índice"
    idx.sheet_view.showGridLines = False

    # --- Colaboradores (gestor por VLOOKUP vivo) --------------------------
    COLS = ["ID", "Código", "Nome", "Cargo", "Nível", "Departamento", "E-mail",
            "Centro de custo", "Vertical", "N5", "Vínculo", "BU", "Admissão",
            "Situação", "ID do gestor", "Gestor (nome)", "Accountabilities"]
    fml = '=IFERROR(VLOOKUP([@[ID do gestor]],tblColaboradores[[ID]:[Nome]],2,0),"(raiz)")'
    lc = []
    for i, u in uni.items():
        n5 = u.get("n5") or (mapa_cc.get(i) or {}).get("n5", "")
        lc.append({"ID": i, "Código": u.get("codigo"), "Nome": u.get("nome"),
                   "Cargo": u.get("cargo"), "Nível": rot_niv.get(u.get("tipo"), u.get("tipo")),
                   "Departamento": u.get("area"), "E-mail": u.get("email"),
                   "Centro de custo": u.get("centro_custo"), "Vertical": u.get("vertical"),
                   "N5": n5, "Vínculo": u.get("vinculo"), "BU": u.get("bu"),
                   "Admissão": u.get("data_inicio"), "Situação": u.get("status"),
                   "ID do gestor": u.get("parent_id"), "Gestor (nome)": fml,
                   "Accountabilities": [r.get("descricao", "") for r in u.get("responsabilidades", [])]})
    lc.sort(key=lambda x: (str(x["Departamento"] or ""), str(x["Nome"] or "")))
    _tab(wb.create_sheet("Colaboradores"), "tblColaboradores", COLS, lc,
         {"Nome": 30, "Cargo": 32, "Departamento": 26, "E-mail": 30, "Gestor (nome)": 30,
          "Accountabilities": 48})

    # --- Hierarquia -------------------------------------------------------
    lh = [{"ID": i, "Colaborador": u.get("nome"), "Cargo": u.get("cargo"),
           "ID do gestor": u.get("parent_id") or "(raiz)",
           "Gestor": nome_de.get(u.get("parent_id"), "(raiz)"),
           "Cargo do gestor": cargo_de.get(u.get("parent_id"), "")} for i, u in uni.items()]
    lh.sort(key=lambda x: str(x["Gestor"] or ""))
    _tab(wb.create_sheet("Hierarquia"), "tblHierarquia",
         ["ID", "Colaborador", "Cargo", "ID do gestor", "Gestor", "Cargo do gestor"], lh,
         {"Colaborador": 30, "Cargo": 30, "Gestor": 30, "Cargo do gestor": 30})

    # --- Acessos (RBAC, colaborador por VLOOKUP) --------------------------
    rp = {"org.admin": "Administrador", "org.editor": "Editor", "org.viewer": "Visualizador"}
    re = {"tudo": "Tudo (sem recorte)", "proprio": "Só o próprio nó",
          "subarvore": "Subárvore (gestor)", "vertical": "Por vertical",
          "departamento": "Por departamento"}
    fc = '=IFERROR(VLOOKUP([@[Ref (ID)]],tblColaboradores[[ID]:[Nome]],2,0),"(fora)")'
    tmp = []
    for r, a in (cfg.get("acessos") or {}).items():
        e = a.get("escopo") or {}
        tmp.append((rp.get(a.get("papel"), a.get("papel")), nome_de.get(r, "zzz"), {
            "Ref (ID)": r, "Colaborador": fc, "Papel": rp.get(a.get("papel"), a.get("papel")),
            "Escopo (tipo)": re.get(e.get("tipo"), e.get("tipo")),
            "Escopo (valor)": e.get("valor") or "(o da própria pessoa)",
            "Vê tudo?": a.get("ver_tudo", False), "Módulos visíveis": a.get("modulos") or "(todos)"}))
    tmp.sort(key=lambda x: (x[0], x[1]))
    _tab(wb.create_sheet("Acessos (RBAC)"), "tblAcessos",
         ["Ref (ID)", "Colaborador", "Papel", "Escopo (tipo)", "Escopo (valor)",
          "Vê tudo?", "Módulos visíveis"], [t[2] for t in tmp],
         {"Colaborador": 30, "Escopo (valor)": 22, "Módulos visíveis": 36})

    # --- CC, Cargos, Níveis ----------------------------------------------
    _tab(wb.create_sheet("Centros de custo"), "tblCC",
         ["Lógico", "N2", "N3", "Departamento", "N5", "Vertical", "Tipo", "Ativo"],
         [{"Lógico": c.get("logico"), "N2": c.get("n2"), "N3": c.get("n3"),
           "Departamento": c.get("departamento"), "N5": c.get("n5"),
           "Vertical": c.get("vertical"), "Tipo": c.get("tipo"), "Ativo": c.get("ativo", True)}
          for c in cfg.get("centros_custo", []) if isinstance(c, dict)], {"Departamento": 28})
    _tab(wb.create_sheet("Cargos"), "tblCargos", ["Cargo"],
         [{"Cargo": c.get("cargo") if isinstance(c, dict) else c}
          for c in cfg.get("catalogo_cargos", [])], {"Cargo": 40})
    _tab(wb.create_sheet("Níveis"), "tblNiveis", ["Código", "Rótulo", "Cor", "Ativo"],
         [{"Código": n.get("codigo"), "Rótulo": n.get("rotulo"), "Cor": n.get("cor"),
           "Ativo": n.get("ativo", True)} for n in cfg.get("niveis", []) if isinstance(n, dict)])

    # --- Auditoria + Log de acessos --------------------------------------
    le = [{"Seq": e.get("seq"), "Quando (UTC)": e.get("quando"), "Ator": e.get("ator"),
           "Ação": e.get("acao"), "Motivo": e.get("motivo"), "Payload": _s(e.get("payload")),
           "Hash": (e.get("hash") or "")[:16]} for e in d.get("eventos", [])]
    le.sort(key=lambda x: -(x["Seq"] or 0))
    _tab(wb.create_sheet("Auditoria (ledger)"), "tblAuditoria",
         ["Seq", "Quando (UTC)", "Ator", "Ação", "Motivo", "Payload", "Hash"], le,
         {"Motivo": 28, "Payload": 52, "Ator": 24})
    lg = [{"Quando (UTC)": a.get("quando"),
           "Evento": "Entrada" if a.get("evento") == "entrar" else "Saída",
           "Usuário": a.get("nome"), "E-mail": a.get("email")}
          for a in reversed(d.get("acessos_log") or [])]
    _tab(wb.create_sheet("Log de acessos"), "tblLog",
         ["Quando (UTC)", "Evento", "Usuário", "E-mail"], lg, {"Usuário": 30, "E-mail": 30})

    # =====================================================================
    # CÁLCULOS RH (fonte dos gráficos) + PAINEL RH
    # =====================================================================
    def anos(iso):
        p = _iso(iso)
        return (ref - date(*p)).days / 365.25 if p else None

    filhos = defaultdict(list)
    for i, u in uni.items():
        filhos[u.get("parent_id")].append(i)
    total = len(uni) or 1
    gestores = [i for i in uni if filhos.get(i)]
    ten = [a for u in uni.values() if (a := anos(u.get("data_inicio"))) is not None]
    vinc = Counter(u.get("vinculo") or "clt" for u in uni.values())
    rotv = {k: v[0] for k, v in dominio.VINCULOS.items()}
    terc = sum(vinc.get(k, 0) for k in ("pj", "estagio", "rpa", "consultoria"))
    casa = Counter()
    for u in uni.values():
        a = anos(u.get("data_inicio"))
        if a is None:
            casa["(sem data)"] += 1
            continue
        for rot, lo, hi in FAIXAS:
            if lo <= a < hi:
                casa[rot] += 1
                break
    por_dept = Counter(u.get("area") or "(sem)" for u in uni.values())
    por_vert = Counter(u.get("vertical") for u in uni.values() if u.get("vertical"))
    adm = Counter()
    for u in uni.values():
        p = _iso(u.get("data_inicio"))
        if p:
            adm[str(p[0])] += 1
    niv = [(n["codigo"], n["rotulo"]) for n in cfg.get("niveis", []) if isinstance(n, dict)]
    por_niv = Counter(u.get("tipo") for u in uni.values())

    wc = wb.create_sheet("Cálculos RH")
    wc.sheet_view.showGridLines = False

    def bloco(col, titulo, pares, top=None):
        pares = list(pares)[:top] if top else list(pares)
        wc.cell(1, col, titulo).font = _lbl
        wc.cell(2, col, "Categoria").font = _hdr
        wc.cell(2, col).fill = _fill
        wc.cell(2, col + 1, "Qtde").font = _hdr
        wc.cell(2, col + 1).fill = _fill
        for r, (k, v) in enumerate(pares, 3):
            wc.cell(r, col, _s(k))
            wc.cell(r, col + 1, v)
        wc.column_dimensions[get_column_letter(col)].width = 24
        return 2, 2 + len(pares)

    b_dept = bloco(1, "Departamento", sorted(por_dept.items(), key=lambda x: -x[1]), 12)
    b_niv = bloco(4, "Nível", [(rot, por_niv.get(cod, 0)) for cod, rot in niv])
    b_casa = bloco(7, "Tempo de casa", [(r, casa.get(r, 0)) for r, _, _ in FAIXAS])
    b_vinc = bloco(10, "Vínculo", [(rotv.get(k, k), v) for k, v in vinc.most_common()])
    b_adm = bloco(13, "Admissões/ano", sorted(adm.items()))
    b_vert = bloco(16, "Vertical", sorted(por_vert.items(), key=lambda x: -x[1]), 12)

    ws = wb.create_sheet("Painel RH", 1)
    ws.sheet_view.showGridLines = False
    ws.merge_cells("B2:M2")
    ws["B2"] = "Painel de RH / Departamento Pessoal"
    ws["B2"].font = Font(bold=True, color=GRAFITE, size=20)
    ws.merge_cells("B3:M3")
    ws["B3"] = "%s · %s · %s" % (cfg.get("titulo", "Organograma"),
                                 cfg.get("tenant", "GPlanSiS|Peoples"), ref.strftime("%d/%m/%Y"))
    ws["B3"].font = _sub
    KPIS = [("Colaboradores", total, LARANJA), ("Gestores", len(gestores), GRAFITE),
            ("Departamentos", len({u.get("area") for u in uni.values() if u.get("area")}), GRAFITE),
            ("Tempo médio", "%.1f a" % (sum(ten) / len(ten) if ten else 0), AMBAR),
            ("% CLT", "%d%%" % round(vinc.get("clt", 0) / total * 100), GRAFITE),
            ("% Terceiros", "%d%%" % round(terc / total * 100), LARANJA)]
    col = 2
    for rot, val, cor in KPIS:
        ws.merge_cells(start_row=5, start_column=col, end_row=5, end_column=col + 1)
        ws.merge_cells(start_row=6, start_column=col, end_row=7, end_column=col + 1)
        c1 = ws.cell(5, col, rot)
        c1.font, c1.fill, c1.alignment = Font(bold=True, color=BRANCO, size=9), PatternFill("solid", fgColor=cor), _alc
        c2 = ws.cell(6, col, val)
        c2.font, c2.fill, c2.alignment = Font(bold=True, color=cor, size=18), PatternFill("solid", fgColor=CINZA), _alc
        ws.column_dimensions[get_column_letter(col)].width = 12
        ws.column_dimensions[get_column_letter(col + 1)].width = 12
        col += 2

    def grafico(cls, titulo, b_col, hdr, last, onde, pie=False, alt=7.5):
        ch = cls()
        ch.title = titulo
        ch.height, ch.width = alt, 11
        ch.add_data(Reference(wc, min_col=b_col + 1, min_row=hdr, max_row=last),
                    titles_from_data=True)
        ch.set_categories(Reference(wc, min_col=b_col, min_row=hdr + 1, max_row=last))
        if not pie:
            ch.legend = None
            ch.y_axis.majorGridlines = None
        ch.dataLabels = DataLabelList()
        ch.dataLabels.showVal = True
        ws.add_chart(ch, onde)

    grafico(PieChart, "Tipo de vínculo (CLT × terceiros)", 10, *b_vinc, "B9", pie=True)
    grafico(BarChart, "Pirâmide por nível", 4, *b_niv, "H9")
    grafico(BarChart, "Tempo de casa", 7, *b_casa, "B25")
    grafico(LineChart, "Admissões por ano", 13, *b_adm, "H25")
    grafico(BarChart, "Headcount por departamento (top 12)", 1, *b_dept, "B41", alt=9)
    grafico(BarChart, "Headcount por vertical (top 12)", 16, *b_vert, "H41", alt=9)

    # --- Modelo de dados --------------------------------------------------
    wm = wb.create_sheet("Modelo de dados")
    wm.sheet_view.showGridLines = False
    wm["B2"] = "Modelo de dados — tabelas e vínculos"
    wm["B2"].font = _tit
    VINC = [("Colaboradores", "ID do gestor", "→", "Colaboradores", "ID", "Hierarquia (VLOOKUP vivo)"),
            ("Colaboradores", "Centro de custo", "→", "Centros de custo", "N3", "CC do colaborador"),
            ("Colaboradores", "N5", "→", "Centros de custo", "N5", "N5 vinculado ao CC"),
            ("Acessos (RBAC)", "Ref (ID)", "→", "Colaboradores", "ID", "A quem o acesso pertence (VLOOKUP)"),
            ("Acessos (RBAC)", "Escopo (valor)", "→", "Colaboradores / CC", "ID / Vertical", "Base do recorte"),
            ("Log de acessos", "Usuário", "→", "Colaboradores", "ID", "Quem entrou/saiu")]
    COLS_MD = ["Tabela (origem)", "Campo", "Vínculo", "Tabela (destino)", "Campo (destino)", "O que significa"]
    _tab(wm, "tblModelo", COLS_MD, [dict(zip(COLS_MD, v)) for v in VINC],
         {"Tabela (origem)": 18, "Campo": 22, "Vínculo": 8, "Tabela (destino)": 20,
          "Campo (destino)": 18, "O que significa": 40}, r0=4, congelar="A5")

    # --- Índice -----------------------------------------------------------
    idx["B2"] = "GPlanSiS|Peoples — Dados + Painel RH"
    idx["B2"].font = _tit
    idx["B3"] = "%s · %s" % (cfg.get("tenant", "GPlanSiS|Peoples"), ref.strftime("%d/%m/%Y"))
    idx["B3"].font = _sub
    for r, (nome, n) in enumerate([("Painel RH", "dashboard"), ("Colaboradores", len(lc)),
                                   ("Hierarquia", len(lh)), ("Acessos (RBAC)", len(tmp)),
                                   ("Centros de custo", len(cfg.get("centros_custo", []))),
                                   ("Cargos", len(cfg.get("catalogo_cargos", []))),
                                   ("Auditoria (ledger)", len(le)),
                                   ("Log de acessos", len(lg)),
                                   ("Modelo de dados", len(VINC))], 6):
        idx.cell(r, 2, "▸ " + nome).font = _lbl
        idx.cell(r, 3, str(n)).font = _sub
    idx.column_dimensions["B"].width = 22
    idx.column_dimensions["C"].width = 14

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
