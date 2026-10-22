"""Cota de IA da MarIA — quanto cada pessoa pode gastar na Anthropic por mês.

Sem isto, uma conta comprometida (ou alguém curioso) gera custo sem teto na
conta da Anthropic: as rotas `/maria/*` chamam o modelo a cada pedido. O
desenho é o do GPlanSiS|Studio:

- cada chamada grava o uso REAL de tokens (o `usage` que a Anthropic devolve) e
  o custo em US$ numa tabela própria, inclusive quando a chamada falha;
- a cota é mensal, em US$, por pessoa; o padrão global é do administrador
  (`Config.maria_cota_usd`) e cada pessoa pode ter uma cota própria
  (sem linha em `ia_cota` = vale o padrão);
- antes de chamar o modelo: gasto do mês >= cota -> 402; mais de 30 chamadas
  por minuto ou 3 simultâneas da mesma pessoa -> 429;
- o corpo das rotas de IA é limitado (413) antes de o formulário ser lido.

Onde mora: um SQLite próprio na pasta de dados (`dados/ia_uso.sqlite3`, ou
`ORG_IA_USO_ARQUIVO`). O estado do Peoples é JSON por organograma e o Postgres
é espelho best-effort; o ledger de custo precisa valer para a pessoa em
qualquer organograma e não pode se perder quando o espelho falha. SQLite é
biblioteca padrão, grava com transação e a criação é idempotente
(`CREATE ... IF NOT EXISTS`) — subir o serviço é a migração.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

COTA_PADRAO_USD = 20.0
COTA_MAXIMA_USD = 10000.0
POR_MINUTO = 30
SIMULTANEAS = 3
CORPO_MAXIMO = 64 * 1024        # formulários da MarIA: pergunta + recorte + capacidade

ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent / "dados" / "ia_uso.sqlite3"

_trava = threading.Lock()
_em_curso: dict[str, int] = defaultdict(int)
_recentes: dict[str, list[float]] = defaultdict(list)


class Recusa(Exception):
    """Pedido recusado antes de chamar o modelo (402, 413 ou 429)."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------
def arquivo() -> Path:
    return Path(os.environ.get("ORG_IA_USO_ARQUIVO") or ARQUIVO_PADRAO)


@contextmanager
def _db():
    caminho = arquivo()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(caminho, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        _migrar(c)
        with c:
            yield c
    finally:
        c.close()


def _migrar(c: sqlite3.Connection) -> None:
    """Idempotente: roda a cada conexão e não faz nada se já está tudo lá."""
    c.executescript("""
    CREATE TABLE IF NOT EXISTS ia_uso(
      id INTEGER PRIMARY KEY, ts REAL NOT NULL, usuario_id TEXT NOT NULL,
      recurso TEXT NOT NULL, modelo TEXT,
      input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
      cache_read INTEGER DEFAULT 0, cache_write INTEGER DEFAULT 0,
      custo_usd REAL DEFAULT 0, ok INTEGER NOT NULL, erro TEXT, ms INTEGER);
    CREATE INDEX IF NOT EXISTS ia_uso_usuario_ts ON ia_uso(usuario_id, ts);
    CREATE TABLE IF NOT EXISTS ia_cota(usuario_id TEXT PRIMARY KEY, cota_usd REAL);
    """)


def inicio_do_mes() -> float:
    t = time.gmtime()
    return time.mktime((t.tm_year, t.tm_mon, 1, 0, 0, 0, 0, 0, -1))


def gasto_do_mes(usuario_id: str) -> float:
    with _db() as c:
        r = c.execute("SELECT COALESCE(SUM(custo_usd),0) s FROM ia_uso "
                      "WHERE usuario_id=? AND ts>=?",
                      (usuario_id, inicio_do_mes())).fetchone()
    return float(r["s"])


def cota_propria(usuario_id: str) -> float | None:
    with _db() as c:
        r = c.execute("SELECT cota_usd FROM ia_cota WHERE usuario_id=?",
                      (usuario_id,)).fetchone()
    return None if r is None or r["cota_usd"] is None else float(r["cota_usd"])


def cota_de(usuario_id: str, padrao: float | None) -> float:
    q = cota_propria(usuario_id)
    if q is not None:
        return q
    return float(COTA_PADRAO_USD if padrao is None else padrao)


def valida_cota(valor) -> float:
    try:
        q = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("Cota inválida.")
    if not (0 <= q <= COTA_MAXIMA_USD) or q != q:
        raise ValueError("Cota fora da faixa (0 a 10.000 US$).")
    return round(q, 2)


def define_cota(usuario_id: str, valor) -> float | None:
    """`valor` vazio/None volta ao padrão (apaga a cota própria)."""
    if valor is None or str(valor).strip() == "":
        with _db() as c:
            c.execute("DELETE FROM ia_cota WHERE usuario_id=?", (usuario_id,))
        return None
    q = valida_cota(valor)
    with _db() as c:
        c.execute("INSERT INTO ia_cota(usuario_id, cota_usd) VALUES(?,?) "
                  "ON CONFLICT(usuario_id) DO UPDATE SET cota_usd=excluded.cota_usd",
                  (usuario_id, q))
    return q


def registrar(usuario_id: str, recurso: str, modelo: str, uso: dict | None,
              custo_usd: float, ok: bool, erro: str | None, ms: int) -> None:
    uso = uso or {}
    with _db() as c:
        c.execute(
            "INSERT INTO ia_uso(ts,usuario_id,recurso,modelo,input_tokens,output_tokens,"
            "cache_read,cache_write,custo_usd,ok,erro,ms) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (time.time(), usuario_id, recurso, modelo,
             int(uso.get("input_tokens") or 0), int(uso.get("output_tokens") or 0),
             int(uso.get("cache_read_input_tokens") or 0),
             int(uso.get("cache_creation_input_tokens") or 0),
             float(custo_usd or 0.0), 1 if ok else 0, (erro or None) and str(erro)[:60], ms))


def resumo_do_mes(usuario_id: str | None = None) -> list[dict]:
    """Gasto do mês por pessoa (todas, para o administrador; ou só uma)."""
    sql = ("SELECT usuario_id, COUNT(*) n, COALESCE(SUM(custo_usd),0) custo, "
           "COALESCE(SUM(input_tokens),0) entrada, COALESCE(SUM(output_tokens),0) saida "
           "FROM ia_uso WHERE ts>=?")
    args: tuple = (inicio_do_mes(),)
    if usuario_id is not None:
        sql += " AND usuario_id=?"
        args += (usuario_id,)
    sql += " GROUP BY usuario_id ORDER BY custo DESC"
    with _db() as c:
        linhas = [dict(r) for r in c.execute(sql, args).fetchall()]
        cotas = {r["usuario_id"]: r["cota_usd"]
                 for r in c.execute("SELECT usuario_id, cota_usd FROM ia_cota").fetchall()}
    for l in linhas:
        l["custo"] = round(l["custo"], 4)
        l["cota_propria"] = cotas.get(l["usuario_id"])
    return linhas


# ---------------------------------------------------------------------------
# Portão — antes de chamar o modelo
# ---------------------------------------------------------------------------
def verificar(usuario_id: str, cota_padrao: float | None) -> None:
    """Levanta `Recusa` (402/429) se a pessoa não pode chamar o modelo agora."""
    gasto, cota = gasto_do_mes(usuario_id), cota_de(usuario_id, cota_padrao)
    if gasto >= cota:
        raise Recusa(402, f"Cota de IA do mês atingida (US$ {gasto:.2f} de "
                          f"US$ {cota:.2f}). Fale com um administrador.")
    agora = time.time()
    with _trava:
        _recentes[usuario_id] = [t for t in _recentes[usuario_id] if agora - t < 60]
        if len(_recentes[usuario_id]) >= POR_MINUTO or _em_curso[usuario_id] >= SIMULTANEAS:
            raise Recusa(429, "Muitas chamadas de IA seguidas. Aguarde alguns segundos.")


@contextmanager
def em_curso(usuario_id: str):
    """Conta a chamada no limite por minuto e no de simultâneas."""
    with _trava:
        _em_curso[usuario_id] += 1
        _recentes[usuario_id].append(time.time())
    try:
        yield
    finally:
        with _trava:
            _em_curso[usuario_id] -= 1


async def corpo_limitado(req, limite: int = CORPO_MAXIMO) -> None:
    """Lê o corpo com teto ANTES de `req.form()`.

    O Starlette guarda o corpo lido em `_body` e o `form()` seguinte reaproveita;
    assim um corpo gigante é recusado sem ser carregado inteiro na memória.
    """
    cl = req.headers.get("content-length") or ""
    if cl.isdigit() and int(cl) > limite:
        raise Recusa(413, "Pedido grande demais para a IA.")
    buf = bytearray()
    async for pedaco in req.stream():
        buf += pedaco
        if len(buf) > limite:
            raise Recusa(413, "Pedido grande demais para a IA.")
    req._body = bytes(buf)


def zerar_limites() -> None:
    """Para testes: esquece as chamadas recentes e em curso."""
    with _trava:
        _em_curso.clear()
        _recentes.clear()
