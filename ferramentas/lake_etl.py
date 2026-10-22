"""ETL do lakehouse GPlanSiS — Peoples → bronze (e, por vista, silver e gold).

**Este processo NUNCA escreve na origem.** Ele conecta ao banco do Peoples com
um papel que só tem `SELECT` (`peoples_leitor`) e grava no banco do lakehouse
com um papel que só existe ali (`lake`). Se alguém trocar a credencial por uma
com escrita, a carga continua funcionando igual — mas o desenho é o contrário:
a permissão é o contrato, não o combinado.

Uma carga é atômica e versionada: abre uma linha em `bronze.carga`, escreve o
retrato de cada tabela com aquele `carga_id`, e só então marca `ok`. As vistas
de `silver` leem a ÚLTIMA carga OK — então uma carga interrompida no meio nunca
aparece em métrica nenhuma, e a anterior continua valendo.

Clima entra **agregado**: PTI geral, por pilar e por estrato, com o piso de 5
respondentes aplicado aqui. Resposta individual não sai do Peoples — nem
anônima: cruzar estrato com área pequena identifica gente.

    # no servidor, como o usuário do lakehouse
    sudo -u lake /opt/peoples/.venv/bin/python /opt/peoples/ferramentas/lake_etl.py
    ... --limpar 30      # descarta cargas concluídas com mais de 30 dias

Configuração por ambiente (arquivo `/etc/gplansis/lake.env`, 0640):
    LAKE_DSN=postgresql:///gplansis_lake?host=/var/run/postgresql
    LAKE_ORIGEM_PEOPLES=postgresql://peoples_leitor:SENHA@127.0.0.1:5432/peoples
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

VERSAO = "1.0"
PISO_ESTRATO = 5          # espelha gptw.PISO_ESTRATO: nada abaixo disto é publicado
PISO_POSITIVO = 4         # 4 e 5 contam como positivo no PTI
PILARES = {
    "credibilidade": range(1, 13), "respeito": range(13, 25), "imparcialidade": range(25, 37),
    "orgulho": range(37, 49), "camaradagem": range(49, 61),
}
PILAR_DE = {aid: p for p, faixa in PILARES.items() for aid in faixa}


def ambiente(arquivo: str = "/etc/gplansis/lake.env") -> None:
    p = Path(arquivo)
    if not p.exists():
        return
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        k, v = linha.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def conectar(dsn: str, leitura: bool = False):
    import psycopg
    con = psycopg.connect(dsn, connect_timeout=15)
    if leitura:
        # Cinto e suspensório: mesmo com um papel de escrita, esta sessão não
        # escreve. O contrato de permissão continua sendo o principal.
        con.execute("SET default_transaction_read_only = on")
    return con


# ---------------------------------------------------------------------------
# LEITURA DA ORIGEM — só SELECT
# ---------------------------------------------------------------------------
def ler_peoples(dsn: str) -> dict[str, list[dict]]:
    """O retrato do Peoples, por organograma. Nada aqui muta a origem."""
    with conectar(dsn, leitura=True) as con, con.cursor() as cur:
        cur.execute("SELECT o.slug, o.nome FROM org.organograma o ORDER BY o.slug")
        orgs = cur.fetchall()

        cur.execute("""
            SELECT o.slug, u.origem_id, u.codigo, u.nome, p.email_corp::text, u.cargo,
                   u.tipo::text, u.area, u.centro_custo, u.vertical, u.vinculo::text,
                   p.admissao, p.situacao_rh, pu.origem_id, u.ordem_exibicao, u.competencias
            FROM org.unidade u
            JOIN org.organograma o ON o.id = u.organograma_id
            LEFT JOIN org.unidade pu ON pu.id = u.parent_id
            LEFT JOIN org.alocacao a ON a.unidade_id = u.id AND a.papel = 'responsavel'
                                    AND upper_inf(a.vigencia)
            LEFT JOIN org.pessoa p ON p.id = a.pessoa_id
            WHERE u.parent_id IS NOT NULL""")
        pessoas = [dict(zip(("slug", "origem_id", "codigo", "nome", "email", "cargo", "nivel",
                             "area", "centro_custo", "vertical", "vinculo", "admissao",
                             "situacao", "parent_origem", "ordem", "competencias"), r))
                   for r in cur.fetchall()]

        cur.execute("""
            SELECT o.slug, u.origem_id,
                   row_number() OVER (PARTITION BY o.slug, u.origem_id ORDER BY r.id)::int,
                   r.descricao, r.origem::text
            FROM org.responsabilidade r
            JOIN org.unidade u ON u.id = r.unidade_id
            JOIN org.organograma o ON o.id = u.organograma_id""")
        resp = [dict(zip(("slug", "origem_id", "seq", "descricao", "origem_tipo"), r))
                for r in cur.fetchall()]

        cur.execute("""SELECT slug, ref, cargo, missao, responsabilidades, requisitos, competencias
                       FROM org.dcr_overlay""")
        skills = [dict(zip(("slug", "ref", "cargo", "missao", "responsabilidades",
                            "requisitos", "competencias"), r)) for r in cur.fetchall()]

        cur.execute("""SELECT slug, ref, ano, ciclo, status, data_conversa, lider_nome, conteudo
                       FROM org.cgv_registro""")
        cdv = []
        for slug, ref, ano, ciclo, status, data, lider, conteudo in cur.fetchall():
            c = conteudo if isinstance(conteudo, dict) else {}
            elementos = sum(1 for k in ("entregas", "carreira") if str(c.get(k) or "").strip())
            elementos += 1 if any(str(v or "").strip() for v in (c.get("valores") or {}).values()) else 0
            elementos += 1 if any(str(v or "").strip() for v in (c.get("lideranca") or {}).values()) else 0
            pdi = sum(1 for i in (c.get("pdi") or []) if str(i.get("comp") or "").strip())
            elementos += 1 if pdi else 0
            cdv.append({"slug": slug, "ref": ref, "ano": ano, "ciclo": ciclo, "status": status,
                        "data_conversa": data, "lider_nome": lider, "elementos": elementos,
                        "pdi_itens": pdi})

        cur.execute("""SELECT slug, ref, ano, risco_perda, impacto_perda, prontidao, acao
                       FROM org.mapa_talento""")
        aval = [dict(zip(("slug", "ref", "ano", "risco_perda", "impacto_perda",
                          "prontidao", "acao"), r)) for r in cur.fetchall()]

        cur.execute("""SELECT slug, ano, ciclo, respostas, estrato_nivel, estrato_area,
                              estrato_vinculo, estrato_faixa, modelo_trabalho
                       FROM org.gptw_resposta""")
        clima_bruto = cur.fetchall()

    return {"organogramas": orgs, "pessoas": pessoas, "responsabilidades": resp,
            "skills": skills, "conversas": cdv, "avaliacoes": aval,
            "clima": agregar_clima(clima_bruto)}


def agregar_clima(linhas) -> list[dict]:
    """Respostas individuais → PTI agregado, com piso de 5 respondentes.

    O piso não é formalidade: num estrato de três pessoas, o PTI descreve
    indivíduos, e o instrumento prometeu anonimato. Abaixo do piso, o recorte
    simplesmente não existe no lakehouse."""
    baldes: dict[tuple, list[int]] = {}
    for slug, ano, ciclo, respostas, nivel, area, vinculo, faixa, modelo in linhas:
        vals = [int(v) for v in (respostas or {}).values() if isinstance(v, (int, float))]
        if not vals:
            continue
        chave_base = (slug, ano, ciclo)
        baldes.setdefault((*chave_base, "geral", "geral"), []).extend(vals)
        for aid, v in (respostas or {}).items():
            pilar = PILAR_DE.get(int(aid))
            if pilar:
                baldes.setdefault((*chave_base, "pilar", pilar), []).append(int(v))
        for dim, valor in (("nivel", nivel), ("area", area), ("vinculo", vinculo),
                           ("faixa", faixa), ("modelo", modelo)):
            if valor:
                baldes.setdefault((*chave_base, dim, valor), []).extend(vals)
    # Respondentes por recorte: o número de ENVIOS, não de respostas.
    envios: dict[tuple, int] = {}
    for slug, ano, ciclo, respostas, nivel, area, vinculo, faixa, modelo in linhas:
        if not respostas:
            continue
        chave_base = (slug, ano, ciclo)
        envios[(*chave_base, "geral", "geral")] = envios.get((*chave_base, "geral", "geral"), 0) + 1
        for pilar in PILARES:
            k = (*chave_base, "pilar", pilar)
            envios[k] = envios.get(k, 0) + 1
        for dim, valor in (("nivel", nivel), ("area", area), ("vinculo", vinculo),
                           ("faixa", faixa), ("modelo", modelo)):
            if valor:
                k = (*chave_base, dim, valor)
                envios[k] = envios.get(k, 0) + 1
    saida = []
    for chave, vals in baldes.items():
        n = envios.get(chave, 0)
        if n < PISO_ESTRATO:
            continue
        slug, ano, ciclo, dim, valor = chave
        positivos = sum(1 for v in vals if v >= PISO_POSITIVO)
        saida.append({"slug": slug, "ano": ano, "ciclo": ciclo, "dimensao": dim,
                      "chave": valor, "respondentes": n,
                      "pti": round(100.0 * positivos / len(vals), 2)})
    return saida


# ---------------------------------------------------------------------------
# ESCRITA NO LAKEHOUSE
# ---------------------------------------------------------------------------
def carregar(dsn_lake: str, dados: dict, dominio: str = "*") -> dict:
    with conectar(dsn_lake) as con:
        with con.cursor() as cur:
            cur.execute("INSERT INTO bronze.carga (sistema, dominio, versao_etl) "
                        "VALUES ('peoples', %s, %s) RETURNING id", (dominio, VERSAO))
            carga_id = cur.fetchone()[0]
        contagem = {}
        try:
            with con.cursor() as cur:
                cur.executemany(
                    "INSERT INTO bronze.peoples_pessoa (carga_id, slug, origem_id, codigo, nome, "
                    "email, cargo, nivel, area, centro_custo, vertical, vinculo, admissao, situacao, "
                    "parent_origem, ordem, competencias) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                    "%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                    [(carga_id, p["slug"], p["origem_id"], p["codigo"], p["nome"], p["email"],
                      p["cargo"], p["nivel"], p["area"], p["centro_custo"], p["vertical"],
                      p["vinculo"], p["admissao"], p["situacao"], p["parent_origem"], p["ordem"],
                      json.dumps(p["competencias"] or [], ensure_ascii=False))
                     for p in dados["pessoas"] if p["origem_id"]])
                contagem["peoples_pessoa"] = len(dados["pessoas"])

                cur.executemany(
                    "INSERT INTO bronze.peoples_responsabilidade (carga_id, slug, origem_id, seq, "
                    "descricao, origem_tipo) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    [(carga_id, r["slug"], r["origem_id"], r["seq"], r["descricao"], r["origem_tipo"])
                     for r in dados["responsabilidades"] if r["origem_id"]])
                contagem["peoples_responsabilidade"] = len(dados["responsabilidades"])

                cur.executemany(
                    "INSERT INTO bronze.peoples_skills (carga_id, slug, ref, cargo, missao, "
                    "responsabilidades, requisitos, competencias) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    [(carga_id, s["slug"], s["ref"], s["cargo"], s["missao"],
                      s["responsabilidades"], s["requisitos"], s["competencias"])
                     for s in dados["skills"]])
                contagem["peoples_skills"] = len(dados["skills"])

                cur.executemany(
                    "INSERT INTO bronze.peoples_conversa_valor (carga_id, slug, ref, ano, ciclo, "
                    "status, data_conversa, lider_nome, elementos, pdi_itens) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    [(carga_id, c["slug"], c["ref"], c["ano"], c["ciclo"], c["status"],
                      c["data_conversa"], c["lider_nome"], c["elementos"], c["pdi_itens"])
                     for c in dados["conversas"]])
                contagem["peoples_conversa_valor"] = len(dados["conversas"])

                cur.executemany(
                    "INSERT INTO bronze.peoples_avaliacao (carga_id, slug, ref, ano, risco_perda, "
                    "impacto_perda, prontidao, acao) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    [(carga_id, a["slug"], a["ref"], a["ano"], a["risco_perda"],
                      a["impacto_perda"], a["prontidao"], a["acao"]) for a in dados["avaliacoes"]])
                contagem["peoples_avaliacao"] = len(dados["avaliacoes"])

                cur.executemany(
                    "INSERT INTO bronze.peoples_clima_agregado (carga_id, slug, ano, ciclo, "
                    "dimensao, chave, respondentes, pti) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    [(carga_id, k["slug"], k["ano"], k["ciclo"], k["dimensao"], k["chave"],
                      k["respondentes"], k["pti"]) for k in dados["clima"]])
                contagem["peoples_clima_agregado"] = len(dados["clima"])

                cur.execute("UPDATE bronze.carga SET concluida_em = now(), ok = true, linhas = %s::jsonb "
                            "WHERE id = %s", (json.dumps(contagem), carga_id))
            con.commit()
        except Exception as erro:                       # noqa: BLE001
            con.rollback()
            with con.cursor() as cur:
                cur.execute("UPDATE bronze.carga SET concluida_em = now(), ok = false, erro = %s "
                            "WHERE id = %s", (str(erro)[:500], carga_id))
            con.commit()
            raise
    return {"carga_id": carga_id, **contagem}


def limpar(dsn_lake: str, dias: int) -> int:
    """Descarta cargas antigas — menos a última OK de cada domínio, que é a que
    as vistas de silver leem."""
    with conectar(dsn_lake) as con, con.cursor() as cur:
        cur.execute("""
            DELETE FROM bronze.carga c
            WHERE c.concluida_em < now() - make_interval(days => %s)
              AND c.id NOT IN (SELECT id FROM silver.ultima_carga)""", (dias,))
        n = cur.rowcount
        con.commit()
    return n


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ambiente()
    dsn_lake = os.environ.get("LAKE_DSN", "")
    dsn_origem = os.environ.get("LAKE_ORIGEM_PEOPLES", "")
    if not dsn_lake or not dsn_origem:
        sys.exit("Defina LAKE_DSN e LAKE_ORIGEM_PEOPLES (veja /etc/gplansis/lake.env).")
    inicio = datetime.now(timezone.utc)
    dados = ler_peoples(dsn_origem)
    r = carregar(dsn_lake, dados)
    seg = (datetime.now(timezone.utc) - inicio).total_seconds()
    print(f"carga {r['carga_id']} · " + " · ".join(f"{k.replace('peoples_', '')}={v}"
                                                   for k, v in r.items() if k != "carga_id")
          + f" · {seg:.1f}s")
    if "--limpar" in sys.argv:
        dias = int(sys.argv[sys.argv.index("--limpar") + 1])
        print(f"cargas antigas descartadas: {limpar(dsn_lake, dias)}")
