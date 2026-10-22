"""Leitura do lakehouse GPlanSiS — a base intermediária do hub.

O Peoples é **dono** do seu banco e **consumidor** do lakehouse. São dois papéis
diferentes, e por isso duas credenciais diferentes: `ORG_DATABASE_URL` (escreve
no `peoples`) e `LAKE_LEITOR_DSN` (só lê `gold` e `silver` do `gplansis_lake`).
Este módulo usa apenas a segunda.

Quem escreve no lakehouse é o ETL (`ferramentas/lake_etl.py`), que roda como
outro usuário do sistema, por outro serviço, com outra credencial. Nada aqui
tem permissão de escrita — e a sessão ainda é marcada como somente-leitura,
por cinto e suspensório.

**Por que a métrica não é calculada aqui.** Ela poderia: o Peoples tem os dados.
Mas então cada sistema do hub calcularia a sua versão de "amplitude média" e as
três divergiriam na terceira correção. A conta mora numa vista de `gold`, uma
vez, e todo mundo lê a mesma.

`ORG_LAKE_TOKENS` (lista por vírgula) libera o consumo máquina-a-máquina por
`Authorization: Bearer <token>` — é como o PriorIA e o PCP leem daqui sem uma
sessão de gente. Sem token configurado, a API do lake exige login normal.
"""
from __future__ import annotations

import hmac
import os

# As vistas publicáveis. Lista fechada, e não "qualquer nome que chegue na URL":
# é o que impede `/api/v1/lake/pg_authid` e qualquer injeção pelo nome.
VISTAS = {
    "painel_executivo": ("gold.painel_executivo", "Uma linha por organograma: o que a diretoria pergunta."),
    "organizacao": ("gold.organizacao", "Headcount, gestores, amplitude, tempo de casa e mix de vínculo."),
    "headcount_por_area": ("gold.headcount_por_area", "Colaboradores, gestores e tempo de casa por área."),
    "headcount_por_vinculo": ("gold.headcount_por_vinculo", "Distribuição por vínculo, com percentual."),
    "tempo_de_casa": ("gold.tempo_de_casa", "Distribuição por faixa de tempo de casa."),
    "skills_cobertura": ("gold.skills_cobertura", "Funções e pessoas cobertas por ficha Skills."),
    "conversa_valor_cobertura": ("gold.conversa_valor_cobertura", "Conversas de Valor por ciclo: previstas, realizadas, pendentes."),
    "conversa_valor_por_area": ("gold.conversa_valor_por_area", "Cobertura da Conversa de Valor por área."),
    "talento_9box": ("gold.talento_9box", "Distribuição do 9-box: risco × impacto, com quadrante nomeado."),
    "sucessao": ("gold.sucessao", "Prontidão de sucessão e as ações do Comitê."),
    "clima_pti": ("gold.clima_pti", "PTI por dimensão e estrato, com o nível de maturidade."),
    "risco_concentracao": ("gold.risco_concentracao", "Funções de um ocupante só com impacto de perda alto."),
    "colaborador": ("silver.colaborador", "O conformado por pessoa (silver) — leitura detalhada."),
}
LIMITE_PADRAO = 500
LIMITE_MAX = 5000


def dsn() -> str:
    return (os.environ.get("LAKE_LEITOR_DSN") or "").strip()


def tokens() -> frozenset[str]:
    bruto = (os.environ.get("ORG_LAKE_TOKENS") or "").strip()
    return frozenset(t.strip() for t in bruto.split(",") if t.strip())


def token_valido(recebido: str | None) -> bool:
    """Comparação em tempo constante contra cada token configurado. `==` vazaria
    o prefixo correto pelo tempo de resposta."""
    if not recebido:
        return False
    return any(hmac.compare_digest(recebido, t) for t in tokens())


def driver():
    try:
        import psycopg
        return psycopg
    except ImportError:
        return None


def situacao() -> dict:
    d = dsn()
    return {"tem_dsn": bool(d), "tem_driver": driver() is not None,
            "pronto": bool(d) and driver() is not None,
            "vistas": len(VISTAS), "tokens": len(tokens())}


def _conectar():
    pg = driver()
    if pg is None or not dsn():
        return None
    con = pg.connect(dsn(), connect_timeout=8)
    con.execute("SET default_transaction_read_only = on")
    return con


def _json_seguro(v):
    """`numeric` vira float e `timestamptz`/`date` viram ISO 8601.

    O JSON do Python não serializa `Decimal` nem `datetime`, e uma métrica que
    derruba a rota com 500 é pior que uma métrica ausente — o consumidor do
    outro lado não tem como saber que o problema é de formato."""
    import datetime as _dt
    import decimal as _dec
    if isinstance(v, _dec.Decimal):
        return float(v)
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _dt.timedelta):
        return v.total_seconds()
    return v


def consultar(vista: str, organograma: str = "", limite: int = LIMITE_PADRAO) -> dict:
    """Uma vista do lakehouse como {colunas, linhas}. O nome vem do catálogo, o
    filtro é parametrizado — nada de string montada com entrada do usuário."""
    if vista not in VISTAS:
        return {"erro": "vista desconhecida", "vistas": sorted(VISTAS)}
    alvo, _descricao = VISTAS[vista]
    limite = max(1, min(int(limite or LIMITE_PADRAO), LIMITE_MAX))
    con = None
    try:
        con = _conectar()
        if con is None:
            return {"erro": "lakehouse indisponível (sem LAKE_LEITOR_DSN ou sem psycopg)"}
        sql = f"SELECT * FROM {alvo}"                 # `alvo` vem do catálogo fechado
        params: list = []
        if organograma:
            sql += " WHERE organograma = %s"
            params.append(organograma)
        sql += f" LIMIT {limite}"
        with con.cursor() as cur:
            cur.execute(sql, params)
            colunas = [d.name for d in cur.description]
            linhas = [{c: _json_seguro(v) for c, v in zip(colunas, r)}
                      for r in cur.fetchall()]
        return {"vista": vista, "fonte": alvo, "colunas": colunas,
                "linhas": linhas, "total": len(linhas)}
    except Exception as erro:                          # noqa: BLE001
        return {"erro": str(erro).strip().splitlines()[0][:200]}
    finally:
        if con is not None:
            con.close()


def ultima_carga() -> dict:
    """Quando o lakehouse foi atualizado pela última vez, por sistema. Métrica
    sem data de carga é métrica que ninguém sabe se ainda vale."""
    con = None
    try:
        con = _conectar()
        if con is None:
            return {}
        with con.cursor() as cur:
            cur.execute("SELECT sistema, dominio, concluida_em, linhas FROM silver.ultima_carga")
            return {"cargas": [{"sistema": s, "dominio": d,
                                "concluida_em": c.isoformat() if c else None, "linhas": l}
                               for s, d, c, l in cur.fetchall()]}
    except Exception:                                  # noqa: BLE001
        return {}
    finally:
        if con is not None:
            con.close()
