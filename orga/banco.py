"""Banco de dados — o organograma em PostgreSQL.

O sistema roda em memória com persistência em JSON (`dados/estado.json`), e isso
é deliberado: o organograma inteiro cabe em memória, o layout é puro e o ledger
é um arquivo append-only. O Postgres é o **alvo de produção** descrito na SPEC
§7 — multiusuário, concorrência real e retenção do ledger fora do disco local.

Este módulo é a ponte, e ele funciona nos dois mundos:

  **Sem driver instalado** — que é o estado de quem só quer ver o desenho — o
  módulo ainda entrega o que interessa: o DDL, o mapeamento entre o que está em
  memória e cada tabela, e o SQL de carga gerado a partir do estado atual. Dá
  para levar num cliente qualquer e rodar.

  **Com `psycopg` e DSN configurado** — testa a conexão, aplica o schema e
  sincroniza. A escrita é sempre em transação: metade de um organograma no
  banco é pior do que nenhum.

Nada aqui inventa modelo novo. As tabelas são as de `schema.sql`; o que este
módulo faz é dizer de onde cada coluna vem.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

BASE = Path(__file__).parent
ARQUIVO_SCHEMA = BASE / "schema.sql"


# ---------------------------------------------------------------------------
# Mapa: o que vive em memória -> onde mora no Postgres
# ---------------------------------------------------------------------------
# (tabela, de onde vem, o que guarda)
TABELAS = (
    ("org.organograma", "configuracao",
     "Um registro por organograma: título, tenant e orientação padrão."),
    ("org.pessoa", "Unidade.nome / .codigo / .email",
     "A pessoa, com matrícula (ID SAP), admissão e situação declarada pelo RH. "
     "Sem CPF, RG, endereço, dado de saúde ou remuneração (LGPD-01/02)."),
    ("org.unidade", "Unidade",
     "O nó da árvore: código, nome, tipo, pai e ordem de exibição."),
    ("org.unidade_closure", "derivada",
     "Ancestral × descendente com profundidade — é ela que faz subárvore custar "
     "um índice em vez de uma recursão."),
    ("org.alocacao", "Unidade.cargo / .vinculo",
     "Quem ocupa a unidade, em que papel e sob que regime, com vigência. Um "
     "responsável por unidade em cada intervalo, garantido por EXCLUDE."),
    ("org.responsabilidade", "Unidade.responsabilidades",
     "Accountability própria ou delegada, com a guarda de coerência da delegação."),
    ("org.maria_assistencia", "assistências da MarIA",
     "Histórico das respostas: quem perguntou, em que recorte, quanto custou."),
    ("org.evento", "ledger",
     "O mesmo ledger encadeado por SHA-256 que a aba Auditoria verifica."),
    ("org.dcr_overlay", "configuracao.dcr_cargos",
     "A descrição de cargo que o RH escreve (GEP-FOR-003): missão, "
     "responsabilidades, requisitos e competências, uma por função."),
    ("org.cgv_registro", "configuracao.cgv_registros",
     "As Conversas que Geram Valor (GEP-FOR-006): status, data e o formulário "
     "inteiro em JSONB, por pessoa, ano e ciclo."),
    ("org.mapa_talento", "configuracao.mapa_talentos",
     "A Avaliação (GEP-FOR-004): risco e impacto de perda, prontidão e "
     "ação imediata, por pessoa e ano."),
    ("org.gptw_resposta", "respostas da Avaliação Mestre",
     "A pesquisa de clima, anônima: respostas Likert, estratos e abertas — "
     "nenhuma coluna de identidade."),
    ("org.estado_extra", "estado.json (config, colapso, filtros, mural…)",
     "O resto do estado, um documento JSONB por organograma: configuração, RBAC, "
     "colapso, orientação, filtros, provisionamentos e log de acessos."),
    ("org.usuario", "orga.usuarios (login próprio)",
     "Credenciais do login: e-mail e hash scrypt da senha — nunca a senha. "
     "Global: vale para todos os organogramas."),
    ("org.bd_completo_org", "view: unidade + pessoa",
     "A planilha completa (de-para): todas as colunas por colaborador, com gestor "
     "direto e tempo de casa derivados. As colunas financeiras aparecem sempre "
     "NULL — dinheiro não é gravado (LGPD-01/02). Só Admin."),
)


def dsn() -> str:
    return (os.environ.get("ORG_DATABASE_URL") or "").strip()


def driver():
    """`psycopg` se estiver instalado. Ausência não é erro: é o modo padrão."""
    try:
        import psycopg
        return psycopg
    except ImportError:
        return None


def situacao() -> dict:
    d = dsn()
    return {
        "dsn": mascarar(d),
        "tem_dsn": bool(d),
        "tem_driver": driver() is not None,
        "pronto": bool(d) and driver() is not None,
    }


def contagem_real() -> dict:
    """Quantas linhas o banco tem AGORA, por tabela. `{}` se não houver banco.

    A tela mostrava só a contagem PREVISTA — o que a carga escreveria. Isso
    responde "o que eu mandaria", e não "o que está lá", que é a pergunta de
    quem abre a aba depois de carregar. Com as duas lado a lado dá para ver num
    relance se o banco está no mesmo ponto da tela ou se ficou para trás.

    Uma consulta só, com `UNION ALL`: sete `count(*)` em sete idas ao banco
    para desenhar uma tabela de sete linhas é caro à toa. Erro devolve `{}` em
    vez de subir: a aba precisa abrir mesmo com o banco fora do ar — é
    justamente ali que se vai descobrir que ele está fora do ar.
    """
    pg = driver()
    if pg is None or not dsn():
        return {}
    nomes = [t for t, _o, _d in TABELAS]
    consulta = " UNION ALL ".join(
        f"SELECT '{n}' AS t, count(*) AS n FROM {n}" for n in nomes)
    try:
        with pg.connect(dsn(), connect_timeout=6) as con:
            with con.cursor() as cur:
                cur.execute(consulta)
                return {linha[0]: linha[1] for linha in cur.fetchall()}
    except Exception:                               # noqa: BLE001
        return {}


def _tabela_valida(nome: str) -> bool:
    """Só tabelas do catálogo — nunca um nome vindo da URL. É o que impede
    `/config/banco/tabela/pg_shadow` ou uma injeção pelo nome."""
    return nome in {t for t, _o, _d in TABELAS}


def _formatar(v) -> str:
    """Valor de célula para a tela: nulo explícito, JSON compacto, texto cortado."""
    if v is None:
        return "∅"
    if isinstance(v, (dict, list)):
        import json
        v = json.dumps(v, ensure_ascii=False)
    s = str(v)
    return s[:180] + "…" if len(s) > 180 else s


def estrutura_tabela(nome: str) -> list[dict]:
    """As colunas de uma tabela: nome, tipo e se aceita nulo. `[]` sem banco."""
    if not _tabela_valida(nome):
        return []
    pg = driver()
    if pg is None or not dsn():
        return []
    esquema, tab = nome.split(".", 1)
    try:
        with pg.connect(dsn(), connect_timeout=6) as con, con.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
                (esquema, tab))
            return [{"coluna": r[0], "tipo": r[1], "nulo": r[2] == "YES",
                     "padrao": (r[3] or "")[:60]} for r in cur.fetchall()]
    except Exception:                                   # noqa: BLE001
        return []


def amostra_tabela(nome: str, limite: int = 100) -> dict:
    """Uma amostra dos dados de uma tabela (SELECT * LIMIT), só leitura. O nome é
    do catálogo (whitelist), então a interpolação é segura. `total` é a contagem
    real; `linhas` só a amostra pedida."""
    vazio = {"colunas": [], "linhas": [], "total": 0, "limite": limite}
    if not _tabela_valida(nome):
        return {**vazio, "erro": "tabela fora do catálogo"}
    try:
        limite = max(1, min(500, int(limite)))
    except (TypeError, ValueError):
        limite = 100
    pg = driver()
    if pg is None or not dsn():
        return {**vazio, "limite": limite, "erro": "sem banco"}
    try:
        with pg.connect(dsn(), connect_timeout=8) as con, con.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {nome}")
            total = cur.fetchone()[0]
            cur.execute(f"SELECT * FROM {nome} LIMIT {limite}")
            colunas = [d[0] for d in cur.description]
            linhas = [[_formatar(v) for v in row] for row in cur.fetchall()]
        return {"colunas": colunas, "linhas": linhas, "total": total,
                "limite": limite}
    except Exception as erro:                           # noqa: BLE001
        return {**vazio, "limite": limite,
                "erro": str(erro).strip().splitlines()[0][:200]}


def mascarar(url: str) -> str:
    """Nunca mostrar a senha na tela — ela vaza em print, em suporte e em vídeo."""
    if not url or "@" not in url:
        return url
    esquema, resto = url.split("://", 1) if "://" in url else ("", url)
    credencial, servidor = resto.rsplit("@", 1)
    usuario = credencial.split(":", 1)[0]
    return f"{esquema}://{usuario}:••••••@{servidor}" if esquema else f"{usuario}:••••••@{servidor}"


def testar() -> tuple[bool, str]:
    """(ok, mensagem). A mensagem é a do driver — diagnosticar exige o texto real."""
    pg = driver()
    if pg is None:
        return False, "psycopg não está instalado"
    if not dsn():
        return False, "ORG_DATABASE_URL não está definida"
    try:
        with pg.connect(dsn(), connect_timeout=6) as con:
            with con.cursor() as cur:
                cur.execute("select version()")
                return True, (cur.fetchone() or [""])[0]
    except Exception as erro:                       # noqa: BLE001 — texto do driver
        return False, str(erro).strip().splitlines()[0][:200]


def ddl() -> str:
    return ARQUIVO_SCHEMA.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Carga: estado atual -> INSERTs
# ---------------------------------------------------------------------------
def _lit(valor) -> str:
    """Literal SQL. Aspas simples dobradas — a única forma de escapar em SQL."""
    if valor is None or valor == "":
        return "NULL"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return str(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def _jsonb(valor, vazio: str = "[]") -> str:
    """Lista/dict -> literal `jsonb`. `None` vira `vazio` — `'[]'` para
    `competencias` (sempre lista), `'{}'` para `payload` (sempre objeto)."""
    texto = vazio if valor is None else json.dumps(valor, ensure_ascii=False)
    return "'" + texto.replace("'", "''") + "'::jsonb"


def sql_carga(unidades: dict, config, slug: str = "peoples") -> str:
    """SQL que reconstrói o organograma atual num banco vazio.

    Gerado, e não escrito à mão, porque o estado muda a cada edição — um script
    fixo estaria errado no dia seguinte. Roda em transação única: ou entra
    inteiro, ou não entra.
    """
    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    linhas = [
        "-- Gerado por GPlanSiS|Peoples a partir do estado vigente.",
        "-- Requer o schema de schema.sql já aplicado.",
        "BEGIN;",
        "",
        "INSERT INTO org.organograma (slug, nome, orientacao_padrao)",
        f"VALUES ({_lit(slug)}, {_lit(config.titulo)}, "
        f"{_lit(config.orientacao_padrao)})",
        "ON CONFLICT (slug) DO UPDATE SET nome = EXCLUDED.nome,",
        "    orientacao_padrao = EXCLUDED.orientacao_padrao,",
        "    atualizado_em = now();",
        "",
        "-- Pessoas. A matrícula (ID SAP) é a identidade; o e-mail é a segunda.",
        "-- Quem não tinha e-mail era pulado inteiro e, por consequência, ficava",
        "-- sem alocação: existia no organograma e não existia no banco.",
    ]
    for u in us:
        # A raiz é nó, não gente: nasce sintética em `montar_unidades`, sem
        # e-mail e com um código nosso. Entrava como pessoa agora que o código
        # basta para identificar — e uma pessoa chamada "Diretoria" com uma
        # alocação de "Conselho de administração" é ficção que o banco não deve
        # guardar. `importador.analisar` e `m365.analisar` excluem a raiz pela
        # mesma prova: quem não tem pai não é empregado.
        if u.parent_id is None or not (u.email or u.codigo):
            continue
        colunas = ("matricula, nome_completo, nome_exibicao, email_corp, "
                   "admissao, situacao_rh")
        valores = (f"{_lit(u.codigo)}, {_lit(u.nome)}, {_lit(u.nome[:60])}, "
                   f"{_lit(u.email)}, {_lit(u.data_inicio)}, {_lit(u.status)}")
        # Um alvo por statement é o limite do `ON CONFLICT`. Com e-mail o alvo é
        # ele — assim a matrícula entra por cima de quem já estava cadastrado,
        # sem migração à parte; sem e-mail, o alvo é a própria matrícula.
        alvo = "(email_corp)" if u.email else "(matricula)"
        linhas.append(
            f"INSERT INTO org.pessoa ({colunas}) VALUES ({valores}) "
            f"ON CONFLICT {alvo} DO UPDATE SET "
            "matricula = EXCLUDED.matricula, "
            "nome_completo = EXCLUDED.nome_completo, "
            "email_corp = coalesce(EXCLUDED.email_corp, org.pessoa.email_corp), "
            "admissao = EXCLUDED.admissao, situacao_rh = EXCLUDED.situacao_rh, "
            "atualizado_em = now();")

    linhas += ["", "-- Unidades: pais antes dos filhos, senão a FK recusa."]
    ordem, vistos = [], set()

    def emitir(u):
        if u.id in vistos:
            return
        vistos.add(u.id)
        pai = unidades.get(u.parent_id) if u.parent_id else None
        if pai is not None:
            emitir(pai)
        ordem.append(u)

    for u in us:
        emitir(u)

    for u in ordem:
        pai = ("(SELECT id FROM org.unidade WHERE codigo = "
               f"{_lit(unidades[u.parent_id].codigo)} AND organograma_id = o.id)"
               if u.parent_id else "NULL")
        nasc = _lit(u.data_nascimento) + ("::date" if u.data_nascimento else "")
        linhas.append(
            "INSERT INTO org.unidade (organograma_id, codigo, nome, tipo, "
            "parent_id, ordem_exibicao, origem_id, area, centro_custo, "
            "vertical, responsavel, competencias, cargo, vinculo, "
            "tipo_mo, cc_n2, cc_n4, cc_n5, cc_equipe, bu, tipo_class, mo_classe, "
            "categoria_nivel, genero, data_nascimento)\n"
            f"SELECT o.id, {_lit(u.codigo)}, {_lit(u.nome)}, "
            f"{_lit(u.tipo)}::org.tipo_unidade, {pai}, {u.ordem}, "
            # `origem_id` é a identidade do nó em memória (a chave do estado), que
            # não é o código: sem ela o retorno do banco (Onda DB-3) não sabe
            # remontar os ids que `colapsados` e o ledger referenciam.
            f"{_lit(u.id)}, {_lit(u.area)}, {_lit(u.centro_custo)}, "
            f"{_lit(u.vertical)}, {_lit(u.responsavel)}, "
            f"{_jsonb(u.competencias)}, "
            # cargo/vinculo também na unidade: `org.alocacao` guarda o VÍNCULO
            # normalizado (com vigência, um responsável por unidade), mas a raiz
            # sintética não é pessoa e não tem alocação de onde o cargo viesse.
            # Aqui o nó volta INTEIRO do banco (Onda DB-3), a raiz inclusive.
            f"{_lit(u.cargo)}, coalesce({_lit(u.vinculo)}, 'clt')::org.vinculo, "
            # Planilha completa (bd_completo_org) — só organizacionais; o dinheiro
            # não entra (LGPD). Os nomes N2/N4/N5 do Excel viram cc_n2/cc_n4/cc_n5.
            f"{_lit(u.tipo_mo)}, {_lit(u.n2)}, {_lit(u.n4)}, {_lit(u.n5)}, "
            f"{_lit(u.cc_equipe)}, {_lit(u.bu)}, {_lit(u.tipo_class)}, "
            f"{_lit(u.mo_classe)}, {_lit(u.categoria_nivel)}, {_lit(u.genero)}, "
            f"{nasc}\n"
            f"FROM org.organograma o WHERE o.slug = {_lit(slug)}\n"
            # `ordem_exibicao` estava fora do UPDATE: recarregar não corrigia a
            # ordem dos irmãos, e a segunda carga parecia não ter aplicado. Os
            # campos de fidelidade entram no UPDATE pelo mesmo motivo — uma
            # segunda carga tem de corrigir área, CC e afins, não só criá-los.
            "ON CONFLICT (organograma_id, codigo) DO UPDATE SET "
            "nome = EXCLUDED.nome, tipo = EXCLUDED.tipo, "
            "parent_id = EXCLUDED.parent_id, "
            "ordem_exibicao = EXCLUDED.ordem_exibicao, "
            "origem_id = EXCLUDED.origem_id, area = EXCLUDED.area, "
            "centro_custo = EXCLUDED.centro_custo, vertical = EXCLUDED.vertical, "
            "responsavel = EXCLUDED.responsavel, "
            "competencias = EXCLUDED.competencias, cargo = EXCLUDED.cargo, "
            "vinculo = EXCLUDED.vinculo, tipo_mo = EXCLUDED.tipo_mo, "
            "cc_n2 = EXCLUDED.cc_n2, cc_n4 = EXCLUDED.cc_n4, cc_n5 = EXCLUDED.cc_n5, "
            "cc_equipe = EXCLUDED.cc_equipe, bu = EXCLUDED.bu, "
            "tipo_class = EXCLUDED.tipo_class, mo_classe = EXCLUDED.mo_classe, "
            "categoria_nivel = EXCLUDED.categoria_nivel, genero = EXCLUDED.genero, "
            "data_nascimento = EXCLUDED.data_nascimento, atualizado_em = now();")

    linhas += [
        "",
        "-- Alocação: quem ocupa cada unidade, em que papel e sob que regime.",
        "-- Apaga antes de escrever, como as accountabilities e pelo mesmo motivo:",
        "-- `ON CONFLICT DO NOTHING` sem alvo deixava a linha antiga de pé, então",
        "-- cargo e vínculo alterados nunca chegavam, e a segunda carga parecia",
        "-- não ter aplicado. Na mesma transação, ninguém fica sem alocação.",
        "DELETE FROM org.alocacao a",
        "USING org.unidade un, org.organograma o",
        "WHERE a.unidade_id = un.id AND un.organograma_id = o.id",
        f"  AND o.slug = {_lit(slug)};",
    ]
    for u in ordem:
        if u.parent_id is None or not ((u.email or u.codigo) and u.cargo):
            continue
        # Casa por matrícula quando há, por e-mail quando não há: a mesma ordem
        # de identidade do INSERT de pessoa, para as duas metades concordarem.
        casa = (f"p.matricula = {_lit(u.codigo)}" if u.codigo
                else f"p.email_corp = {_lit(u.email)}")
        linhas.append(
            "INSERT INTO org.alocacao (unidade_id, pessoa_id, papel, cargo, "
            "vinculo)\n"
            f"SELECT un.id, p.id, 'responsavel', {_lit(u.cargo)}, "
            f"coalesce({_lit(u.vinculo)}, 'clt')::org.vinculo\n"
            "FROM org.unidade un JOIN org.organograma o "
            "ON o.id = un.organograma_id\n"
            f"JOIN org.pessoa p ON {casa}\n"
            f"WHERE o.slug = {_lit(slug)} AND un.codigo = {_lit(u.codigo)};")

    linhas += [
        "",
        "-- Accountabilities. Não há chave natural aqui: duas linhas com a mesma",
        "-- descrição na mesma unidade são legítimas. Sem `ON CONFLICT` possível,",
        "-- a idempotência vem de apagar antes de escrever — dentro da mesma",
        "-- transação, então em nenhum instante a unidade fica sem as suas.",
        "DELETE FROM org.responsabilidade r",
        "USING org.unidade un, org.organograma o",
        "WHERE r.unidade_id = un.id AND un.organograma_id = o.id",
        f"  AND o.slug = {_lit(slug)};",
    ]
    for u in ordem:
        for i, r in enumerate(u.responsabilidades or []):
            linhas.append(
                "INSERT INTO org.responsabilidade (unidade_id, descricao, origem, "
                "ordem)\n"
                f"SELECT un.id, {_lit(r.get('descricao'))}, "
                f"{_lit(r.get('origem') or 'propria')}::org.origem_responsabilidade,"
                f" {i}\n"
                "FROM org.unidade un JOIN org.organograma o "
                "ON o.id = un.organograma_id\n"
                f"WHERE o.slug = {_lit(slug)} AND un.codigo = {_lit(u.codigo)};")

    # A closure, derivada de `parent_id` DEPOIS de todas as unidades estarem
    # dentro. Ela é a razão de a tabela existir: subárvore passa a custar um
    # índice em vez de uma recursão, e é sobre ela que a SPEC §7.1 apoia as
    # consultas de escopo. Antes disto ninguém a preenchia — o comentário em
    # `contagem_prevista` dizia "calculado no banco" e não havia nada no banco
    # calculando: a tabela ficava vazia, e toda consulta que a usasse devolvia
    # zero linhas sem erro nenhum.
    #
    # Calculada aqui, em SQL, e não montada em Python: os pares saem do que
    # ACABOU de ser gravado, e não de uma segunda travessia da árvore em
    # memória — que divergiria da primeira no dia em que alguém mexesse numa
    # das duas. Inclui o par (n, n) com profundidade 0, senão "a subárvore de X"
    # excluiria o próprio X e toda contagem sairia um a menos.
    linhas += [
        "",
        "INSERT INTO org.unidade_closure (ancestral_id, descendente_id, profundidade)",
        "WITH RECURSIVE ramo AS (",
        "    SELECT u.id AS ancestral_id, u.id AS descendente_id,"
        " 0::smallint AS profundidade",
        "    FROM org.unidade u JOIN org.organograma o ON o.id = u.organograma_id",
        f"    WHERE o.slug = {_lit(slug)}",
        "  UNION ALL",
        "    SELECT r.ancestral_id, f.id, (r.profundidade + 1)::smallint",
        "    FROM ramo r JOIN org.unidade f ON f.parent_id = r.descendente_id",
        ")",
        "SELECT ancestral_id, descendente_id, profundidade FROM ramo",
        "ON CONFLICT (ancestral_id, descendente_id) DO UPDATE",
        "    SET profundidade = EXCLUDED.profundidade;",
    ]

    linhas += ["", "COMMIT;", ""]
    return "\n".join(linhas)


def aplicar(sql: str) -> tuple[bool, str]:
    """Executa SQL no banco configurado. Só existe caminho transacional."""
    pg = driver()
    if pg is None or not dsn():
        return False, "sem driver ou sem DSN"
    try:
        with pg.connect(dsn(), connect_timeout=10) as con:
            with con.cursor() as cur:
                cur.execute(sql)
            con.commit()
        return True, "aplicado"
    except Exception as erro:                       # noqa: BLE001
        return False, str(erro).strip().splitlines()[0][:300]


def _pares_da_closure(us: list) -> int:
    """Quantas linhas a closure recebe: um par por ancestral de cada nó, mais
    o par consigo mesmo. É a mesma conta que o `WITH RECURSIVE` da carga faz —
    escrita aqui só para a tela conferir ANTES de escrever."""
    pai = {u.id: u.parent_id for u in us}
    total = 0
    for u in us:
        atual, degraus = u.id, 1          # o par (n, n)
        while pai.get(atual):
            atual = pai[atual]
            degraus += 1
        total += degraus
    return total


def contagem_prevista(unidades: dict) -> dict[str, int]:
    """Quantas linhas cada tabela receberia — confere antes de escrever."""
    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    return {
        "org.organograma": 1,
        "org.pessoa": sum(1 for u in us
                          if u.parent_id is not None and (u.email or u.codigo)),
        "org.unidade": len(us),
        # Um par por (ancestral, descendente), inclusive (n, n): a soma das
        # profundidades mais uma por nó. Antes isto devolvia `len(us)`, o que
        # dava a contagem certa por acidente só numa árvore de um nível — e a
        # tela de conferência dizia 272 onde o banco receberia 900 e poucos.
        "org.unidade_closure": _pares_da_closure(us),
        "org.alocacao": sum(1 for u in us if u.parent_id is not None
                            and (u.email or u.codigo) and u.cargo),
        "org.responsabilidade": sum(len(u.responsabilidades or []) for u in us),
    }


# ---------------------------------------------------------------------------
# Leitura: banco -> estado (Onda DB-1)
# ---------------------------------------------------------------------------
# O reverso de `sql_carga`. A carga desce o estado para as tabelas normalizadas;
# `carregar_estrutura` sobe de volta um dicionário no mesmo formato de
# `estado["unidades"]` — {id: {campos}}, pronto para `Unidade.de_dict`. É o que
# torna possível, mais adiante (Onda DB-3), o banco virar a fonte da leitura.
#
# A identidade é `origem_id`, gravada na carga: o id do nó em memória, que NÃO é
# o código (em planilha o id é um hash do nome). `parent_id` volta como o
# `origem_id` do pai (auto-join), para o dicionário reconstruído apontar para os
# MESMOS ids que `colapsados` e o ledger já referenciam. O nó volta INTEIRO —
# cargo e vínculo saem da própria unidade, então a raiz sintética (que não é
# pessoa e não tem alocação) também atravessa sem perda. É o que deixa a leitura
# vir do banco (Onda DB-3) com segurança.
_VINCULO_PADRAO = "clt"                 # espelha dominio.VINCULO_PADRAO


def carregar_estrutura(slug: str = "peoples") -> dict | None:
    """Sobe a estrutura do banco como {id: {campos}}.

    `None` quando não há banco/driver ou em erro — o chamador então fica com o
    `estado.json`, sem quebrar. `None` também quando o organograma não existe no
    banco (nada a subir).
    """
    pg = driver()
    if pg is None or not dsn():
        return None
    try:
        with pg.connect(dsn(), connect_timeout=10) as con, con.cursor() as cur:
            cur.execute(
                "SELECT u.origem_id, u.codigo, u.nome, u.tipo::text, "
                "       pu.origem_id, u.ordem_exibicao, u.area, u.centro_custo, "
                "       u.vertical, u.responsavel, u.competencias, "
                "       u.cargo, u.vinculo::text, "
                "       p.email_corp, p.admissao::text, p.situacao_rh, "
                "       u.tipo_mo, u.cc_n2, u.cc_n4, u.cc_n5, u.cc_equipe, u.bu, "
                "       u.tipo_class, u.mo_classe, u.categoria_nivel, u.genero, "
                "       u.data_nascimento::text "
                "FROM org.unidade u "
                "JOIN org.organograma o ON o.id = u.organograma_id "
                "LEFT JOIN org.unidade pu ON pu.id = u.parent_id "
                # cargo/vinculo saem da própria unidade (a raiz não tem alocação);
                # a alocação -> pessoa só é atravessada por e-mail, admissão e
                # situação, que são fatos da PESSOA, não do nó.
                "LEFT JOIN org.alocacao a "
                "  ON a.unidade_id = u.id AND a.papel = 'responsavel' "
                "  AND upper_inf(a.vigencia) "
                "LEFT JOIN org.pessoa p ON p.id = a.pessoa_id "
                "WHERE o.slug = %s "
                "ORDER BY u.ordem_exibicao, u.origem_id",
                (slug,))
            nos = cur.fetchall()
            cur.execute(
                "SELECT u.origem_id, r.descricao, r.origem::text "
                "FROM org.responsabilidade r "
                "JOIN org.unidade u ON u.id = r.unidade_id "
                "JOIN org.organograma o ON o.id = u.organograma_id "
                "WHERE o.slug = %s "
                "ORDER BY u.origem_id, r.ordem",
                (slug,))
            resps = cur.fetchall()
    except Exception:                                   # noqa: BLE001
        return None
    if not nos:
        return None

    por_no: dict[str, list] = {}
    for oid, desc, origem in resps:
        por_no.setdefault(oid, []).append(
            {"descricao": desc, "origem": origem or "propria",
             "delegada_para": None})

    unidades: dict[str, dict] = {}
    for (oid, codigo, nome, tipo, parent, ordem, area, cc, vertical,
         responsavel, competencias, cargo, vinculo, email, admissao,
         situacao, tipo_mo, n2, n4, n5, cc_equipe, bu, tipo_class,
         mo_classe, categoria_nivel, genero, nascimento) in nos:
        if oid is None:                 # nó de carga antiga, sem origem_id
            continue
        d = {
            "id": oid,
            "codigo": codigo or "",
            "nome": nome,
            "tipo": tipo,
            "parent_id": parent,        # None na raiz
            "ordem": int(ordem or 0),
            "area": area or "",
            "centro_custo": cc or "",
            "vertical": vertical or "",
            "responsavel": responsavel or "",
            "competencias": list(competencias or []),
            "cargo": cargo or "",
            "email": email or "",
            "data_inicio": admissao or "",
            "status": situacao or "",
            "responsabilidades": por_no.get(oid, []),
            "tipo_mo": tipo_mo or "", "n2": n2 or "", "n4": n4 or "",
            "n5": n5 or "", "cc_equipe": cc_equipe or "", "bu": bu or "",
            "tipo_class": tipo_class or "", "mo_classe": mo_classe or "",
            "categoria_nivel": categoria_nivel or "", "genero": genero or "",
            "data_nascimento": nascimento or "",
        }
        # `vinculo` só quando o banco tem: ausente (a raiz), a `Unidade` assume o
        # padrão do domínio — mapear NULL para "" inventaria um vínculo vazio que
        # o nó nunca teria.
        if vinculo:
            d["vinculo"] = vinculo
        unidades[oid] = d
    return unidades


def _val(u, chave, padrao=""):
    """Lê `chave` tanto de uma `Unidade` (atributo) quanto de um dict do banco."""
    return u.get(chave, padrao) if isinstance(u, dict) else getattr(u, chave, padrao)


def _canonico(u) -> dict:
    """Um nó reduzido aos campos que o banco espelha, na forma canônica — para
    comparar tela × banco sem falso positivo. As normalizações aqui não escondem
    perda: são as transformações que a própria carga faz de propósito (vínculo
    vazio vira 'clt'; delegada_para=None não é gravada; ordem das listas não é
    identidade)."""
    resp = sorted((str(r.get("descricao", "")).strip(), (r.get("origem") or "propria"))
                  for r in (_val(u, "responsabilidades", []) or []))
    return {
        "codigo": _val(u, "codigo") or "",
        "nome": _val(u, "nome") or "",
        "tipo": _val(u, "tipo") or "",
        "parent_id": _val(u, "parent_id", None),
        "ordem": int(_val(u, "ordem", 0) or 0),
        "area": _val(u, "area") or "",
        "centro_custo": _val(u, "centro_custo") or "",
        "vertical": _val(u, "vertical") or "",
        "responsavel": _val(u, "responsavel") or "",
        "cargo": _val(u, "cargo") or "",
        "vinculo": _val(u, "vinculo") or _VINCULO_PADRAO,
        "email": _val(u, "email") or "",
        "data_inicio": str(_val(u, "data_inicio") or "")[:10],
        "status": _val(u, "status") or "",
        "competencias": sorted(str(c) for c in (_val(u, "competencias", []) or [])),
        "responsabilidades": resp,
        # Campos organizacionais da planilha completa (bd_completo_org).
        "tipo_mo": _val(u, "tipo_mo") or "",
        "n2": _val(u, "n2") or "", "n4": _val(u, "n4") or "",
        "n5": _val(u, "n5") or "", "cc_equipe": _val(u, "cc_equipe") or "",
        "bu": _val(u, "bu") or "", "tipo_class": _val(u, "tipo_class") or "",
        "mo_classe": _val(u, "mo_classe") or "",
        "categoria_nivel": _val(u, "categoria_nivel") or "",
        "genero": _val(u, "genero") or "",
        "data_nascimento": str(_val(u, "data_nascimento") or "")[:10],
    }


def verificar_espelho(unidades: dict, slug: str = "peoples",
                      banco: dict | None = None) -> dict:
    """Compara, campo a campo, a estrutura em memória com a do banco.

    Devolve {ok, total, iguais, divergencias, so_na_tela, so_no_banco}. É a
    verificação-sombra da Onda DB-1: com o dual-write ligado tem de dar zero
    divergência sempre — é o que prova que o banco pode virar a fonte da leitura
    (Onda DB-3) sem perder dado. `banco` pode ser injetado (teste); senão, é lido
    de `carregar_estrutura`.
    """
    vazio = {"ok": False, "total": 0, "iguais": 0, "divergencias": [],
             "so_na_tela": [], "so_no_banco": []}
    if banco is None:
        banco = carregar_estrutura(slug)
    if banco is None:
        return {**vazio, "erro": "sem banco"}
    itens = unidades.values() if isinstance(unidades, dict) else unidades
    mem = {(u.get("id") if isinstance(u, dict) else u.id): u for u in itens}
    divergencias, iguais = [], 0
    for oid, u in mem.items():
        if oid not in banco:
            continue
        a, b = _canonico(u), _canonico(banco[oid])
        difs = [k for k in a if a[k] != b[k]]
        if difs:
            divergencias.append({"id": oid, "nome": a["nome"], "campos": difs})
        else:
            iguais += 1
    so_na_tela = sorted(set(mem) - set(banco))
    so_no_banco = sorted(set(banco) - set(mem))
    return {
        "ok": not divergencias and not so_na_tela and not so_no_banco,
        "total": len(mem), "iguais": iguais, "divergencias": divergencias,
        "so_na_tela": so_na_tela, "so_no_banco": so_no_banco,
    }


def sql_evento(eventos: list[dict], slug: str = "peoples") -> str:
    """Ledger em memória -> banco, SINCRONIZADO: o banco fica igual à memória.

    Apaga os eventos do organograma e reescreve, em vez de só acrescentar: o
    ledger do app é revertível pelo Desfazer (o estado guarda os eventos e uma
    reversão reusa números de seq), então um append-only puro divergiria depois
    de um desfazer. Uma transação: nunca meio ledger. Por organograma (o
    (organograma_id, seq) é a chave)."""
    linhas = ["BEGIN;", "",
              "DELETE FROM org.evento e USING org.organograma o",
              f" WHERE e.organograma_id = o.id AND o.slug = {_lit(slug)};", ""]
    for ev in eventos or []:
        pay = _jsonb(ev.get("payload"), vazio="{}")
        linhas.append(
            "INSERT INTO org.evento (organograma_id, seq, quando, ator, acao, "
            "entidade, entidade_id, motivo, payload, hash_anterior, hash)\n"
            f"SELECT o.id, {int(ev.get('seq', 0))}, {_lit(ev.get('quando'))}, "
            f"{_lit(ev.get('ator'))}, {_lit(ev.get('acao'))}, "
            f"{_lit(ev.get('entidade') or 'unidade')}, "
            f"{_lit(ev.get('entidade_id'))}, {_lit(ev.get('motivo'))}, "
            f"{pay}, {_lit(ev.get('hash_anterior'))}, {_lit(ev.get('hash'))}\n"
            f"FROM org.organograma o WHERE o.slug = {_lit(slug)};")
    linhas += ["", "COMMIT;", ""]
    return "\n".join(linhas)


def carregar_ledger(slug: str = "peoples") -> list[dict] | None:
    """Sobe o ledger do banco, na ordem, no formato dos eventos do app. `None`
    sem banco/driver/erro; `[]` quando o organograma não tem eventos."""
    pg = driver()
    if pg is None or not dsn():
        return None
    try:
        with pg.connect(dsn(), connect_timeout=10) as con, con.cursor() as cur:
            cur.execute(
                "SELECT e.seq, e.quando, e.ator, e.acao, e.entidade_id, e.motivo, "
                "       e.payload, e.hash_anterior, e.hash "
                "FROM org.evento e JOIN org.organograma o "
                "  ON o.id = e.organograma_id "
                "WHERE o.slug = %s ORDER BY e.seq",
                (slug,))
            linhas = cur.fetchall()
    except Exception:                                   # noqa: BLE001
        return None
    return [{"seq": int(s), "quando": q, "ator": at, "acao": ac,
             "entidade_id": eid, "motivo": mo, "payload": pl,
             "hash_anterior": ha, "hash": h}
            for (s, q, at, ac, eid, mo, pl, ha, h) in linhas]


def sql_assistencias(historico: list[dict], slug: str = "peoples") -> str:
    """Histórico da MarIA -> INSERTs. Sai à parte da carga da estrutura: é log,
    não é o organograma, e apagar/recarregar a estrutura não pode levar o
    histórico junto."""
    linhas = ["BEGIN;", ""]
    for a in historico or []:
        linhas.append(
            "INSERT INTO org.maria_assistencia (ocorrido_em, quem, quem_id, "
            "escopo, capacidade, idioma, modelo, pergunta, resposta, ok, "
            "tokens_entrada, tokens_saida, custo_usd) VALUES ("
            f"{_lit(a.get('quando'))}, {_lit(a.get('quem'))}, "
            f"{_lit(a.get('quem_id'))}, {_lit(a.get('escopo') or '-')}, "
            f"{_lit(a.get('capacidade'))}, {_lit(a.get('idioma'))}, "
            f"{_lit(a.get('modelo') or '-')}, {_lit(a.get('pergunta'))}, "
            f"{_lit(a.get('resposta'))}, {_lit(bool(a.get('ok')))}, "
            f"{int(a.get('entrada', 0))}, {int(a.get('saida', 0))}, "
            f"{float(a.get('custo_usd', 0))})\n"
            # Idempotente pela chave natural (instante + quem): rodar a carga
            # duas vezes dobrava o log, e log dobrado mente sobre custo, sobre
            # volume e sobre quem perguntou o quê. Foi o que aconteceu na
            # primeira carga real — 11 assistências viraram 22.
            "ON CONFLICT ON CONSTRAINT uq_assistencia_ocorrencia DO NOTHING;")
    linhas += ["", "COMMIT;", ""]
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# O resto do estado e as credenciais (migração 009)
# ---------------------------------------------------------------------------
def sql_extra(dados: dict, slug: str = "peoples", assinatura: str = "") -> str:
    """Documento JSONB com tudo do estado que não tem tabela própria. Upsert por
    organograma, numa transação — o banco fica igual à memória."""
    return "\n".join([
        "BEGIN;",
        "INSERT INTO org.estado_extra (slug, dados, assinatura, atualizado_em)",
        f"VALUES ({_lit(slug)}, {_jsonb(dados, vazio='{}')}, {_lit(assinatura)}, now())",
        "ON CONFLICT (slug) DO UPDATE SET dados = EXCLUDED.dados,",
        "    assinatura = EXCLUDED.assinatura, atualizado_em = now();",
        "COMMIT;", ""])


def carregar_extra(slug: str = "peoples") -> dict | None:
    """O documento extra do organograma, ou None (sem banco, sem linha, erro)."""
    pg = driver()
    if pg is None or not dsn():
        return None
    try:
        with pg.connect(dsn(), connect_timeout=10) as con, con.cursor() as cur:
            cur.execute("SELECT dados FROM org.estado_extra WHERE slug = %s", (slug,))
            linha = cur.fetchone()
    except Exception:                                   # noqa: BLE001
        return None
    if not linha:
        return None
    dados = linha[0]
    if isinstance(dados, str):
        try:
            dados = json.loads(dados)
        except ValueError:
            return None
    return dados if isinstance(dados, dict) else None


def sql_usuarios(usuarios: dict) -> str:
    """Credenciais em memória -> banco, SINCRONIZADO (apaga e reescreve, como o
    ledger): remover uma conta no arquivo remove no banco. Só o hash viaja."""
    linhas = ["BEGIN;", "DELETE FROM org.usuario;"]
    for email, r in sorted((usuarios or {}).items()):
        if not r.get("hash"):
            continue
        linhas.append(
            "INSERT INTO org.usuario (email, senha_hash, ativo, precisa_trocar, "
            "definida_por, criado_em, atualizado_em) VALUES ("
            f"{_lit(email)}, {_lit(r.get('hash'))}, {_lit(bool(r.get('ativo', True)))}, "
            f"{_lit(bool(r.get('precisa_trocar')))}, {_lit(r.get('definida_por') or '')}, "
            f"COALESCE({_lit(r.get('criado_em'))}::timestamptz, now()), "
            f"COALESCE({_lit(r.get('atualizado_em'))}::timestamptz, now()));")
    linhas += ["COMMIT;", ""]
    return "\n".join(linhas)


def carregar_usuarios() -> dict | None:
    """As credenciais do banco no formato do arquivo `usuarios.json`."""
    pg = driver()
    if pg is None or not dsn():
        return None
    try:
        with pg.connect(dsn(), connect_timeout=10) as con, con.cursor() as cur:
            cur.execute("SELECT email, senha_hash, ativo, precisa_trocar, definida_por, "
                        "criado_em, atualizado_em FROM org.usuario")
            linhas = cur.fetchall()
    except Exception:                                   # noqa: BLE001
        return None
    return {str(e).lower(): {"hash": h, "ativo": bool(a), "precisa_trocar": bool(t),
                             "definida_por": d or "",
                             "criado_em": c.isoformat(timespec="seconds") if c else None,
                             "atualizado_em": u.isoformat(timespec="seconds") if u else None}
            for (e, h, a, t, d, c, u) in linhas}
