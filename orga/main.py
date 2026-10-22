"""
GPlanSiS|Peoples - Canvas Twin do organograma invertido.
SPEC-GPLANSIS-ORG-001 v1.1.0 - ondas W5' (HTMX) e W9 (edicao no canvas),
mais o modulo gerenciador: configuracao, permissoes, cadastro de centros de
custo e carga assistida da planilha.

Arquitetura HTMX server-driven (ADR-010): toda mutacao devolve o fragmento
<svg id="canvas"> re-renderizado. O layout nasce no servidor (ADR-011), que e
a fonte unica de verdade tambem da geometria - por isso tela, PDF e SVG
exportado sao a mesma geometria.

O cliente cuida so do efemero: selecao, menu, gaveta, tooltip, pan e zoom.

Execucao:  uvicorn main:app --reload --port 8080
"""
from __future__ import annotations

import copy
import html as htmlmod
import csv
import zipfile
import hashlib
import io
import json
import logging
import os
import random
import re
import secrets
import time
import uuid
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import (HTMLResponse, JSONResponse,
                               RedirectResponse, Response)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

# O `.env` entra ANTES de qualquer modulo que leia credencial: `acesso` decide
# no import se exige segredo forte, e `maria`/`correio` consultam o ambiente a
# cada chamada. Carregar depois faria o primeiro deles ver um ambiente vazio.
from . import ambiente
ambiente.carregar()

from . import acesso
from . import ajuda
from . import banco as bancomod
from . import cargos as cargosmod
from . import centros
from . import cgv as cgvmod
from . import correio
from . import configuracao as cfgmod
from . import dcr as dcrmod
from . import talentos as talentosmod
from . import gptw as gptwmod
from . import onebyone as obomod
from . import painel_rh as painelmod
from . import dominio
from . import estrutura as estruturamod
from . import grade as grademod
from . import idiomas as idiomasmod
from . import lake as lakemod
from . import importador
from . import gramatica
from . import equipes as equipesmod
from . import m365 as m365mod
from . import maria as mariamod
from . import organogramas as orgsmod
from . import relatorio as relatoriomod
from . import pdf as pdfmod
from . import provisionamento as provmod
from . import social as socialmod
from . import tempo as tempomod
from . import usuarios as usuariosmod
from .configuracao import ADMIN, CAMPOS_CARD, EDITOR, PERFIS, VIEWER, Config
from .dominio import (CRITERIOS, TIPOS, Tokens, Unidade, ancestrais,
                     calcular_layout, com_ancestrais, descendentes, filtrar,
                     mapa_filhos, profundidades, raiz, renumerar, sem_acento,
                     valores_de_filtro)

# `BASE` é o pacote; `RAIZ` é o repositório. O que é código mora no
# primeiro, o que é conteúdo — templates, marca, manual, estado — no
# segundo. Antes os dois eram o mesmo diretório e a distinção não existia.
BASE = Path(__file__).resolve().parent
RAIZ = BASE.parent
# O organograma ATIVO decide qual estado o `ESTADO` global carrega e qual slug o
# banco usa. Um só de cada vez (ativo global — "qual fica visível"), como o
# ESTADO único e o worker único pedem. `SLUG_ATIVO`/`ARQUIVO_ESTADO` são
# re-apontados por `trocar_organograma`; começam no que o registro diz (o legado
# `estado.json`, slug `peoples`, quando não há registro em disco).
SLUG_ATIVO = orgsmod.ativo()
ARQUIVO_ESTADO = orgsmod.caminho_estado(SLUG_ATIVO)
MAX_DESFAZER = 40
ATOR = "operador@local"      # DT-02: sem autenticacao nesta onda

NIVEL_EDITOR = PERFIS[EDITOR]["nivel"]
NIVEL_ADMIN = PERFIS[ADMIN]["nivel"]

# Os módulos (abas do cabeçalho) cuja VISIBILIDADE se define por pessoa. Chave =
# a vista de `/vistas/{chave}`; o rótulo é chave de i18n (a mesma da aba). A
# ordem é a do cabeçalho.
MODULOS = (("painel_rh", "Painel RH"),
           ("canvas", "Canvas"), ("estrutura", "Estrutura"), ("tabela", "Tabela"),
           ("tempo", "Tempo de empresa"), ("dcr", "Skills"), ("cgv", "Conversa de Valor"),
           ("talentos", "Avaliação"), ("gptw", "Avaliação Mestre"),
           ("onebyone", "One-on-One"),
           ("configuracoes", "Configurações"))
MODULOS_CHAVES = {c for c, _ in MODULOS}


# ---------------------------------------------------------------------------
# ESTADO DE PROCESSO  (DT-01/DT-03: JSON e processo unico; alvo e schema.sql)
# ---------------------------------------------------------------------------
def filtros_vazios() -> dict:
    # `profundidade` fica fora de CRITERIOS de proposito: os demais criterios sao
    # atributos da unidade, e este e uma propriedade da arvore desenhada — no
    # modo por equipe ele conta os degraus dos times, nao os das pessoas.
    return {"texto": "", "profundidade": [], **{c: [] for c in CRITERIOS}}


@dataclass
class Estado:
    unidades: dict[str, Unidade] = field(default_factory=dict)
    eventos: list[dict] = field(default_factory=list)
    config: Config = field(default_factory=Config)
    orientacao: str = "invertida"
    # Qual pirâmide devolver ao sair da lateral. Sem isto, quem desenha em
    # convencional e dá uma olhada na árvore indentada volta para a invertida
    # — o sistema desfazendo uma escolha que ninguém pediu para desfazer.
    orientacao_piramide: str = "invertida"
    colapsados: set[str] = field(default_factory=set)
    colapso_aplicado: bool = False    # distingue "nunca aberto" de "tudo expandido"
    provisionamentos: list = field(default_factory=list)
    mural: list = field(default_factory=list)
    assistencias: list = field(default_factory=list)
    # Monitoramento de acessos: login/logout de cada usuário. Trilha SEPARADA do
    # ledger de mutações (não é hash-encadeada); persiste no estado.json.
    acessos_log: list[dict] = field(default_factory=list)
    conversa: list = field(default_factory=list)
    propostas: dict = field(default_factory=dict)
    filtros: dict = field(default_factory=filtros_vazios)
    selecionado: str | None = None
    foco: str | None = None
    historico: list[str] = field(default_factory=list)
    # Pilha do refazer. Fora do `serializar()` de proposito, como o historico:
    # desfazer e refazer sao da sessao de quem esta editando, e restaurar um
    # backup com o "futuro" de outra pessoa dentro seria pior que nao ter.
    refazer: list[str] = field(default_factory=list)
    importacao: dict | None = None    # area de estagio do assistente de carga
    sincronizacao: dict | None = None  # idem, para a leitura do Microsoft 365
    agrupamento: str = "pessoa"       # pessoa | equipe — o que e um no no canvas


ESTADO = Estado()


# ---------------------------------------------------------------------------
# SESSAO POR REQUISICAO  (corrige o vazamento de identidade entre usuarios)
# ---------------------------------------------------------------------------
# O ESTADO.config e GLOBAL e compartilhado: guardar nele a IDENTIDADE e o RBAC
# do usuario logado fazia o ultimo login sobrescrever a sessao de todos. Agora a
# sessao vive POR REQUISICAO: `resolver_sessao` (dependencia global, mais abaixo)
# le o cookie assinado e deposita um Config resolvido neste ContextVar; os
# leitores de sessao passam por `acesso_vigente()`. Sem cookie (dev/testes) o
# ContextVar e None e caimos no ESTADO.config global de sempre — o comportamento
# de hoje, preservado inteiro.
_SESSAO: ContextVar = ContextVar("sessao_vigente", default=None)


def acesso_vigente():
    """O Config da sessao DESTA requisicao (perfil, escopo, usuario_id resolvidos
    do cookie). Sem sessao — dev, testes, rota sem cookie — devolve o ESTADO.config
    global, que segue sendo a sessao efetiva do modo aberto."""
    s = _SESSAO.get()
    return s if s is not None else ESTADO.config


# ---------------------------------------------------------------------------
# PRESENÇA — quem está ativo agora (registro em memória, single-worker)
# ---------------------------------------------------------------------------
# Cada requisição COM sessão carimba o instante aqui (no resolver_sessao); "ativo"
# é quem foi visto dentro da janela. Vive em memória como o ESTADO (uvicorn roda
# com --workers 1); some no restart, e tudo bem — presença é efêmera por natureza.
# Sem login não há identidade, então quem não entrou não aparece (nem deveria).
PRESENCA: dict[str, float] = {}
PRESENCA_JANELA = 120           # segundos: ativo = visto nos últimos 2 min


def _marcar_presenca(uid: str | None) -> None:
    if uid:
        PRESENCA[uid] = time.time()


def usuarios_ativos(eu: str | None = None) -> list[dict]:
    """Quem foi visto na janela, resolvido contra o organograma ativo — só quem é
    nó do ativo aparece (a pessoa desvinculada não tem card a mostrar). O próprio
    usuário vem primeiro, marcado."""
    agora = time.time()
    ativos = []
    for uid, visto in list(PRESENCA.items()):      # cópia: não iterar sob escrita
        if agora - visto > PRESENCA_JANELA:
            continue
        u = ESTADO.unidades.get(uid)
        if u is None:
            continue
        partes = [p for p in u.nome.split() if len(p) > 2] or u.nome.split()
        ativos.append({
            "id": uid, "nome": u.nome, "cargo": u.cargo,
            "iniciais": "".join(p[0] for p in (partes[:1] + partes[-1:]))[:2].upper(),
            "eu": uid == eu,
        })
    ativos.sort(key=lambda a: (not a["eu"], sem_acento(a["nome"])))
    return ativos


def registrar_acesso(evento: str, usuario_id: str | None = None,
                     nome: str = "", email: str = "") -> None:
    """Anota um login/logout no monitoramento de acessos — trilha SEPARADA do
    ledger de mutações (não hash-encadeada). Persiste (espelhar=False: é log local,
    não vai ao Postgres da estrutura). `evento` in {'entrar', 'sair'}."""
    ESTADO.acessos_log.append({"quando": agora_iso(), "evento": evento,
                               "usuario_id": usuario_id, "nome": nome,
                               "email": email})
    gravar(espelhar=False)


def novo_id() -> str:
    return uuid.uuid4().hex[:12]


def proximo_codigo() -> str:
    usados = {u.codigo for u in ESTADO.unidades.values()}
    n = len(ESTADO.unidades) + 1
    while f"ORG-{n:04d}" in usados:
        n += 1
    return f"ORG-{n:04d}"


# ---------------------------------------------------------------------------
# LEDGER HASH-ENCADEADO  (SPEC 7.2 / OBJ-05)
# ---------------------------------------------------------------------------
def _corpo_evento(anterior: str, ev: dict) -> str:
    return "|".join([anterior, ev["quando"], ev["ator"], ev["acao"],
                     ev["entidade_id"], ev["motivo"],
                     json.dumps(ev["payload"], sort_keys=True, ensure_ascii=False)])


def registrar(acao: str, entidade_id: str, motivo: str, payload: dict) -> None:
    """Append-only. A cadeia so e verificavel porque nada aqui e reescrito."""
    anterior = ESTADO.eventos[-1]["hash"] if ESTADO.eventos else "GENESIS"
    ev = {
        "seq": len(ESTADO.eventos) + 1,
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ator": f"{ATOR} ({acesso_vigente().perfil})", "acao": acao,
        "entidade_id": entidade_id, "motivo": motivo, "payload": payload,
        "hash_anterior": anterior,
    }
    ev["hash"] = hashlib.sha256(_corpo_evento(anterior, ev).encode()).hexdigest()
    ESTADO.eventos.append(ev)


def verificar_cadeia() -> dict:
    """O(n) - RNF-06. Valida a cadeia de hash, nao a continuidade de seq (RT-06)."""
    anterior = "GENESIS"
    for ev in ESTADO.eventos:
        if hashlib.sha256(_corpo_evento(anterior, ev).encode()).hexdigest() != ev["hash"]:
            return {"integro": False, "seq_falha": ev["seq"],
                    "total": len(ESTADO.eventos)}
        anterior = ev["hash"]
    return {"integro": True, "seq_falha": None, "total": len(ESTADO.eventos)}


# ---------------------------------------------------------------------------
# PERSISTENCIA
# ---------------------------------------------------------------------------
def serializar() -> str:
    return json.dumps({
        "unidades": {k: asdict(v) for k, v in ESTADO.unidades.items()},
        "eventos": ESTADO.eventos,
        "config": ESTADO.config.para_persistir(),   # sessão é efêmera, não persiste
        "orientacao": ESTADO.orientacao,
        "orientacao_piramide": ESTADO.orientacao_piramide,
        "agrupamento": ESTADO.agrupamento,
        "colapsados": sorted(ESTADO.colapsados),
        "colapso_aplicado": ESTADO.colapso_aplicado,
        "provisionamentos": ESTADO.provisionamentos,
        "mural": ESTADO.mural,
        "assistencias": ESTADO.assistencias,
        "acessos_log": ESTADO.acessos_log,
        "conversa": ESTADO.conversa,
        "propostas": ESTADO.propostas,
        "filtros": ESTADO.filtros,
    }, ensure_ascii=False, indent=1)


# A visão por equipe é derivada, e cara: `agrupar` percorre as 267 pessoas,
# ordena os membros de cada time, resolve âncoras, escopos e competências — 6,6
# ms. Uma requisição do canvas a pedia três vezes (o layout, a profundidade
# máxima dos controles, o cabeçalho do desenho), sempre com o mesmo resultado.
#
# O cache é invalidado por três portas, e são todas as que existem: `gravar`, o
# funil de toda mutação; `adotar`, que troca o estado inteiro no desfazer e na
# restauração; e o início de cada requisição, que é a rede de segurança para
# qualquer caminho que os dois primeiros não cubram. Errar aqui desenha a
# estrutura de antes, então a invalidação é generosa de propósito — o custo de
# recalcular à toa é 6,6 ms, e o de servir o desenho velho não tem preço.
_EQUIPES_EM_CACHE: dict | None = None


def esquecer_equipes() -> None:
    global _EQUIPES_EM_CACHE
    _EQUIPES_EM_CACHE = None


_LOG = logging.getLogger("orga.espelho")

# Saúde do espelho (Onda DB-5): o que o operador vê na aba Banco. `ok=None` = o
# espelho nunca precisou rodar nesta sessão (nada a dizer ainda).
_ESPELHO_SAUDE = {"ok": None, "msg": ""}
_ESTRUTURA_ESPELHADA = None       # (slug, hash do SQL) do último espelho da estrutura


def _saude_espelho(ok: bool, msg: str) -> None:
    _ESPELHO_SAUDE["ok"] = ok
    _ESPELHO_SAUDE["msg"] = msg


def espelhar_estrutura() -> None:
    """Dual-write (Onda DB-2): toda mutação também desce a estrutura para o
    Postgres, para o banco viver EM DIA — o pré-requisito de o banco virar a
    fonte da leitura (Onda DB-3) sem começar defasado.

    É best-effort e NÃO-FATAL: a gravação no `estado.json` já aconteceu quando
    isto roda, então sem o espelho ligado, sem banco, ou se o Postgres recusar, a
    edição está salva e a tela não quebra.

    É OPT-IN: só liga com `ORG_ESPELHO=1` no ambiente, como o `ORG_IDIOMA`. O
    padrão é desligado de propósito — o `.env` de quem desenvolve pode apontar
    para um banco de VERDADE, e não se espelha edição de dev em produção por
    descuido. A produção liga a chave explicitamente (ver deploy/README)."""
    global _ESTRUTURA_ESPELHADA
    if os.environ.get("ORG_ESPELHO", "0").strip() != "1":
        return
    if not bancomod.situacao().get("pronto"):
        return
    # Guarda de assinatura (Onda DB-5): só desce a carga quando a ESTRUTURA
    # mudou. Antes, todo `gravar()` re-cargava as 272 unidades — inclusive um
    # toque de colapso, filtro ou tema, que não tocam a estrutura. O hash do SQL
    # é a assinatura; construí-lo custa milissegundos, a ida ao banco custa cem.
    sql = bancomod.sql_carga(ESTADO.unidades, ESTADO.config, slug=SLUG_ATIVO)
    sig = (SLUG_ATIVO, hashlib.sha256(sql.encode("utf-8")).hexdigest())
    if sig == _ESTRUTURA_ESPELHADA:
        return
    try:
        ok, msg = bancomod.aplicar(sql)
        if ok:
            _ESTRUTURA_ESPELHADA = sig
            _saude_espelho(True, "")
        else:
            _LOG.warning("espelho da estrutura falhou (não-fatal): %s", msg)
            _saude_espelho(False, msg)
    except Exception as erro:                           # noqa: BLE001
        _LOG.warning("espelho da estrutura falhou (não-fatal): %s", erro)
        _saude_espelho(False, str(erro))


_LEDGER_ESPELHADO = None      # assinatura (n, último hash) do último espelho do ledger


def espelhar_ledger() -> None:
    """Dual-write do LEDGER (Onda DB-4): sincroniza org.evento com o ledger em
    memória. Opt-in (ORG_ESPELHO=1) e não-fatal, como o da estrutura. Só toca o
    banco quando o ledger MUDOU desde o último espelho — a maioria das gravações
    (colapso, filtro) não mexe no ledger e não paga a viagem."""
    global _LEDGER_ESPELHADO
    if os.environ.get("ORG_ESPELHO", "0").strip() != "1":
        return
    ev = ESTADO.eventos
    assinatura = (len(ev), ev[-1]["hash"] if ev else None)
    if assinatura == _LEDGER_ESPELHADO:
        return
    if not bancomod.situacao().get("pronto"):
        return
    try:
        ok, msg = bancomod.aplicar(bancomod.sql_evento(ev, slug=SLUG_ATIVO))
        if ok:
            _LEDGER_ESPELHADO = assinatura
            _saude_espelho(True, "")
        else:
            _LOG.warning("espelho do ledger falhou (não-fatal): %s", msg)
            _saude_espelho(False, msg)
    except Exception as erro:                        # noqa: BLE001
        _LOG.warning("espelho do ledger falhou (não-fatal): %s", erro)
        _saude_espelho(False, str(erro))


_EXTRA_ESPELHADO = None       # assinatura do último documento extra espelhado


def espelhar_extra() -> None:
    """Dual-write do RESTO do estado (migração 009): tudo o que o estado.json
    guarda e as tabelas normalizadas não têm — configuração (níveis, cargos,
    centros de custo, RBAC, card, tema), colapso, orientação, filtros,
    provisionamentos, mural e o log de acessos — desce como UM documento JSONB
    por organograma em `org.estado_extra`. Com isto o banco tem o sistema
    INTEIRO, e `carregar()` restaura tudo sem o arquivo. Opt-in (ORG_ESPELHO=1),
    guardado por assinatura (só vai quando mudou) e não-fatal, como os outros."""
    global _EXTRA_ESPELHADO
    if os.environ.get("ORG_ESPELHO", "0").strip() != "1":
        return
    dados = json.loads(serializar())
    dados.pop("unidades", None)                      # já têm tabela própria
    dados.pop("eventos", None)
    texto = json.dumps(dados, sort_keys=True, ensure_ascii=False)
    assinatura = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    sig = (SLUG_ATIVO, assinatura)
    if sig == _EXTRA_ESPELHADO:
        return
    if not bancomod.situacao().get("pronto"):
        return
    try:
        ok, msg = bancomod.aplicar(bancomod.sql_extra(dados, SLUG_ATIVO, assinatura))
        if ok:
            _EXTRA_ESPELHADO = sig
        else:
            _LOG.warning("espelho do estado extra falhou (não-fatal): %s", msg)
            _saude_espelho(False, msg)
    except Exception as erro:                        # noqa: BLE001
        _LOG.warning("espelho do estado extra falhou (não-fatal): %s", erro)
        _saude_espelho(False, str(erro))


def gravar(espelhar: bool = True) -> None:
    esquecer_equipes()
    ARQUIVO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_ESTADO.write_text(serializar(), encoding="utf-8")
    # `espelhar=False` no arranque e na semeadura: mirar o seed no banco de
    # produção apagaria a estrutura real. As 33 mutações de usuário usam o
    # padrão (True) e mantêm o banco em dia.
    if espelhar:
        espelhar_estrutura()
        espelhar_ledger()
        espelhar_extra()


def adotar(bruto: dict) -> None:
    esquecer_equipes()
    ESTADO.unidades = {k: Unidade.de_dict(v) for k, v in bruto["unidades"].items()}
    ESTADO.eventos = bruto.get("eventos", [])
    ESTADO.config = Config.de_dict(bruto.get("config"))
    ESTADO.orientacao = bruto.get("orientacao", ESTADO.config.orientacao_padrao)
    # Estado antigo não tem a pirâmide guardada; a orientação vigente serve de
    # semente, a menos que ela própria seja a lateral.
    ESTADO.orientacao_piramide = bruto.get(
        "orientacao_piramide",
        ESTADO.orientacao if ESTADO.orientacao != "lateral" else "invertida")
    ESTADO.agrupamento = bruto.get("agrupamento", "pessoa")
    ESTADO.colapsados = set(bruto.get("colapsados", []))
    ESTADO.colapso_aplicado = bruto.get("colapso_aplicado", False)
    ESTADO.provisionamentos = bruto.get("provisionamentos", [])
    ESTADO.mural = bruto.get("mural", [])
    ESTADO.assistencias = bruto.get("assistencias", [])
    ESTADO.acessos_log = bruto.get("acessos_log", [])   # [] = estado.json antigo
    ESTADO.conversa = bruto.get("conversa", [])
    ESTADO.propostas = bruto.get("propostas", {})
    ESTADO.filtros = {**filtros_vazios(), **(bruto.get("filtros") or {})}
    ESTADO.config.centros_custo = cadastro_cc(ESTADO.config.centros_custo)
    ESTADO.config.catalogo_cargos = catalogo_cargos()


def _escolher_estrutura(bruto: dict | None, banco_u: dict | None):
    """Decide a estrutura a adotar (Onda DB-3), e de onde ela veio. Puro: não
    toca ESTADO nem o banco.

    - Sem banco → JSON (`'json'`), como sempre foi.
    - Banco pronto e SEM JSON legível → banco restaura a estrutura (`'restauro'`).
    - Banco e JSON, e o banco CONFERE → banco é a fonte (`'banco'`, Postgres
      primeiro).
    - Banco e JSON, mas DIVERGEM → JSON vence (`'divergencia'`): ele é a fonte de
      escrita até as transações da Onda DB-5, e um espelho atrasado não pode
      reverter a última edição.
    """
    u_json = (bruto or {}).get("unidades") or {}
    if not banco_u:
        return u_json, "json"
    if not u_json:
        return banco_u, "restauro"
    v = bancomod.verificar_espelho(list(u_json.values()), banco=banco_u)
    if v.get("ok"):
        return banco_u, "banco"
    return u_json, "divergencia"


def carregar() -> bool:
    """Sobe o estado. A ESTRUTURA vem do banco quando ele está pronto e confere;
    o estado.json é a queda — e a fonte de tudo que o banco NÃO espelha (config,
    colapso, ledger, mural, filtros). Ver `_escolher_estrutura`."""
    bruto = None
    if ARQUIVO_ESTADO.exists():
        try:
            bruto = json.loads(ARQUIVO_ESTADO.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            bruto = None

    banco_u = None
    try:
        if bancomod.situacao().get("pronto"):
            banco_u = bancomod.carregar_estrutura(SLUG_ATIVO)
    except Exception as erro:                        # noqa: BLE001
        _LOG.warning("leitura da estrutura do banco falhou (queda p/ JSON): %s",
                     erro)

    unidades, origem = _escolher_estrutura(bruto, banco_u)
    if not unidades and bruto is None:
        return False
    bruto = {**(bruto or {}), "unidades": unidades}
    if origem == "restauro":
        _LOG.info("estrutura restaurada do banco (%d nós); estado.json ausente "
                  "ou ilegível", len(unidades))
        # Sem JSON, o ledger também vem do banco — a auditoria não se perde com o
        # arquivo. Só na restauração: com JSON, o ledger dele é a fonte.
        if not bruto.get("eventos"):
            led = None
            try:
                led = bancomod.carregar_ledger(SLUG_ATIVO)
            except Exception:                        # noqa: BLE001
                led = None
            if led:
                bruto["eventos"] = led
        # E o resto do estado (config, colapso, filtros, mural, log de acessos):
        # `org.estado_extra` guarda o que as tabelas normalizadas não têm.
        extra = None
        try:
            extra = bancomod.carregar_extra(SLUG_ATIVO)
        except Exception:                            # noqa: BLE001
            extra = None
        for chave, valor in (extra or {}).items():
            bruto.setdefault(chave, valor)
    elif origem == "divergencia":
        _LOG.warning("banco diverge do estado.json; estado.json prevalece, banco "
                     "será reconciliado")

    try:
        adotar(bruto)
    except (KeyError, TypeError):
        return False
    if origem == "divergencia":
        espelhar_estrutura()                         # reconcilia JSON -> banco
    return bool(ESTADO.unidades)


def cadastro_cc(guardado: list[dict]) -> list[dict]:
    """Cadastro vigente de centros de custo.

    Vazio, ou gravado no formato antigo (codigo/nome, sem N3), volta para a
    tabela de referencia e ganha as linhas que a estrutura usa e ela nao tem.
    O que o operador ja editou no formato novo e preservado.
    """
    if not guardado or "n3" not in (guardado[0] or {}):
        guardado = centros.referencia()
    return centros.descobrir(ESTADO.unidades, guardado)


def catalogo_cargos() -> list[dict]:
    """Catalogo vigente. Cargo que a estrutura usa e o catalogo nao tem entra
    classificado pela regra; o que o operador ja decidiu nao e sobrescrito."""
    c = ESTADO.config
    return cargosmod.descobrir(ESTADO.unidades, c.catalogo_cargos,
                               c.regras_cargo, {n["codigo"] for n in c.niveis})


def colapso_por_nivel(nivel: int,
                      unidades: dict[str, Unidade] | None = None) -> set[str]:
    """Colapsa tudo a partir de `nivel`. 267 cards abertos sao 59 000 px.

    Recebe o dicionario desenhado em vez de ler `ESTADO`: no modo por equipe as
    profundidades sao outras, e colapsar por id de pessoa nao mexeria em nada do
    que esta na tela.
    """
    fonte = ESTADO.unidades if unidades is None else unidades
    prof = profundidades(fonte)
    filhos = mapa_filhos(fonte)
    return {uid for uid, d in prof.items() if d >= nivel and filhos.get(uid)}


def trocar_colapso(novo: set[str], equipe: bool) -> None:
    """Troca o colapso de um agrupamento, preservando o do outro.

    O conjunto e um so — `EQ-…` e `ORG-…` convivem nele sem colidir. Sem esta
    separacao, escolher N2 por equipe apagaria o colapso que a pessoa tinha
    montado na visao por pessoa, e voltar para ela mostraria a arvore inteira
    aberta sem que ninguem tenha pedido.

    `equipe` vem de quem chama, e nao de `ESTADO.agrupamento`: a tabela e sempre
    por pessoa, mesmo quando o canvas esta por equipe.
    """
    outros = {c for c in ESTADO.colapsados
              if equipesmod.e_equipe(c) is not equipe}
    ESTADO.colapsados = outros | novo


def nivel_aberto(unidades: dict[str, Unidade], colapsados: set[str]) -> int:
    """Ate que profundidade a arvore esta aberta agora.

    E a profundidade do no mais fundo que da para ver sem atravessar um galho
    dobrado. Derivar do desenho, em vez de guardar um contador, e o que faz o
    passo a passo continuar coerente depois de alguem dobrar um galho na mao:
    um contador guardado diria "estamos em N3" com a tela mostrando N1.
    """
    filhos = mapa_filhos(unidades)
    fundo = 0
    pilha = [(raiz(unidades), 0)] if unidades else []
    while pilha:
        u, d = pilha.pop()
        fundo = max(fundo, d)
        if u.id in colapsados:
            continue
        for f in filhos.get(u.id, []):
            pilha.append((f, d + 1))
    return fundo


def desenho_atual() -> dict[str, Unidade]:
    """As unidades que o canvas esta desenhando agora — pessoas ou equipes."""
    if ESTADO.agrupamento == "equipe":
        return agrupar_atual()["unidades"]
    return ESTADO.unidades


def aplicar_colapso_inicial() -> None:
    """Ao carregar, so a arvore de pessoas: a de equipes e derivada e sempre
    recalculada, entao nao ha estado dela para semear."""
    ESTADO.colapsados = colapso_por_nivel(ESTADO.config.profundidade_aberta)
    ESTADO.colapso_aplicado = True


def semear(spec: bool = False) -> None:
    guardado = ESTADO.config
    adotar(importador.gerar(spec=spec))
    ESTADO.config = guardado                    # configuracao sobrevive a recarga
    ESTADO.config.centros_custo = cadastro_cc(ESTADO.config.centros_custo)
    ESTADO.config.catalogo_cargos = catalogo_cargos()
    ESTADO.orientacao = ESTADO.config.orientacao_padrao
    aplicar_colapso_inicial()
    ESTADO.selecionado = ESTADO.foco = None
    ESTADO.filtros = filtros_vazios()
    gravar(espelhar=False)


def marcar_ponto() -> None:
    """Guarda o estado antes de uma mutacao, e joga fora o futuro.

    Editar depois de desfazer abandona o caminho que tinha sido desfeito — sem
    limpar a pilha, `Refazer` traria de volta um estado montado sobre outra
    versao da estrutura, e o que voltasse nao seria o que ninguem viu.
    """
    ESTADO.historico.append(serializar())
    del ESTADO.historico[:-MAX_DESFAZER]
    ESTADO.refazer.clear()


def commit(acao: str, uid: str, motivo: str, payload: dict) -> None:
    registrar(acao, uid, motivo, payload)
    gravar()


# ---------------------------------------------------------------------------
# MULTI-ORGANOGRAMA  (registro + troca do ativo)
# ---------------------------------------------------------------------------
def _estado_inicial(nome: str) -> dict:
    """Um organograma novo nasce com UMA raiz — a árvore não pode ficar sem raiz
    (`dominio.raiz` levanta ORG-RAIZ), e do topo o usuário monta o resto pelo
    +Unit / criar colaborador."""
    rid = novo_id()
    raiz_u = Unidade(id=rid, codigo="ORG-0001", nome=(nome or "Nova organização")[:80],
                     tipo="diretoria", parent_id=None, ordem=0, cargo="Direção")
    cfg = Config()
    cfg.titulo = (nome or "Nova organização")[:80]
    return {
        "unidades": {rid: asdict(raiz_u)}, "eventos": [],
        "config": cfg.para_persistir(), "orientacao": cfg.orientacao_padrao,
        "colapsados": [], "colapso_aplicado": True,
    }


def _ativar(slug: str) -> None:
    """Aponta o processo para `slug` e carrega o estado dele. NÃO salva o atual —
    quem precisa salvar antes (troca) faz isso; quem não precisa (exclusão do
    ativo) evita reescrever um arquivo que vai embora."""
    global SLUG_ATIVO, ARQUIVO_ESTADO
    SLUG_ATIVO = slug
    ARQUIVO_ESTADO = orgsmod.caminho_estado(slug)
    if not carregar():
        adotar(_estado_inicial(orgsmod.nome_de(orgsmod.ler(), slug)))
        aplicar_colapso_inicial()
        gravar(espelhar=False)
    # Seleção, foco e as pilhas de desfazer/refazer são da sessão de edição do
    # organograma que estava à vista — não atravessam a troca, senão um id do
    # organograma anterior fica selecionado num que não o contém.
    ESTADO.selecionado = ESTADO.foco = None
    ESTADO.historico.clear()
    ESTADO.refazer.clear()


def trocar_organograma(slug: str) -> bool:
    """Guarda o organograma à vista e passa a mostrar `slug`. O ativo é GLOBAL:
    trocar aqui troca para todo o sistema (um ESTADO, um worker). Devolve se
    trocou."""
    reg = orgsmod.ler()
    if not orgsmod.existe(reg, slug) or slug == SLUG_ATIVO:
        return slug == SLUG_ATIVO
    gravar(espelhar=False)                          # fecha o atual antes de trocar
    orgsmod.salvar(orgsmod.definir_ativo(reg, slug))
    _ativar(slug)
    return True


def criar_organograma(nome: str, trocar: bool = True) -> str:
    """Cria um organograma vazio (registro + estado inicial em arquivo) e, por
    padrão, passa a mostrá-lo. Devolve o slug novo."""
    reg = orgsmod.ler()
    reg, slug = orgsmod.adicionar(reg, nome, criado_em=date.today().isoformat())
    orgsmod.salvar(reg)
    caminho = orgsmod.caminho_estado(slug)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(_estado_inicial(nome), ensure_ascii=False, indent=1),
                       encoding="utf-8")
    if trocar:
        trocar_organograma(slug)
    return slug


def excluir_organograma(slug: str) -> bool:
    """Tira um organograma do registro e apaga o arquivo de estado dele. Nunca
    apaga o último, nem deixa o sistema sem ativo. As linhas no banco (se houver)
    ficam — apagá-las em cascata é decisão à parte, e não se faz por descuido."""
    reg = orgsmod.ler()
    if len(orgsmod.listar(reg)) <= 1 or not orgsmod.existe(reg, slug):
        return False
    era_ativo = slug == SLUG_ATIVO
    novo = orgsmod.remover(reg, slug)
    orgsmod.salvar(novo)
    if slug != orgsmod.SLUG_PADRAO:                 # o legado nunca perde o arquivo
        try:
            orgsmod.caminho_estado(slug).unlink(missing_ok=True)
        except OSError:
            pass
    if era_ativo:
        _ativar(orgsmod.ativo(novo))               # sem salvar o que acabou de sair
    return True


if not carregar():
    semear(spec=not importador.PLANILHA.exists())
elif not ESTADO.colapso_aplicado:
    aplicar_colapso_inicial()          # estado recem-importado pela CLI
    gravar(espelhar=False)             # arranque não espelha: só mutação de usuário
# Primeiro arranque do login próprio: ORG_ADMIN_EMAIL/ORG_ADMIN_SENHA criam o
# administrador inicial quando ainda não há usuário nenhum (depois, ignorado).
usuariosmod.bootstrap_do_ambiente()


def _idioma_do_ambiente() -> None:
    """ORG_IDIOMA fixa o idioma de ABERTURA a cada arranque — sobrevive a
    redeploy e a qualquer reversão do estado.json. É o que atende "abrir sempre
    em Inglês" sem depender de um valor gravado que a carga pode reescrever: a
    produção define `ORG_IDIOMA=en-US`. Sem a variável, vale o que o estado
    guarda, e os testes seguem em pt-BR (a língua-fonte do catálogo). O seletor
    continua livre na sessão; o próximo arranque volta ao idioma do ambiente."""
    escolhido = os.environ.get("ORG_IDIOMA", "").strip()
    if escolhido and escolhido in idiomasmod.IDIOMAS:
        ESTADO.config.idioma = escolhido


_idioma_do_ambiente()


# ---------------------------------------------------------------------------
# PERMISSOES  (SEC-02 / SEC-03)
# ---------------------------------------------------------------------------
def escopo_permitido() -> set[str] | None:
    """Conjunto de ids que o usuário da sessão pode EDITAR (base da leitura também);
    `None` = sem recorte (Admin, ou escopo 'tudo').

    Resolve o escopo por-pessoa (Fase D) contra a árvore atual: só o próprio nó,
    a subárvore abaixo dele (gestor), ou por vertical / departamento. Preserva o
    `escopo_id` legado (subárvore) quando o tipo novo não veio.

    FAIL-CLOSED: escopo CONFIGURADO mas não-resolvível (subárvore sem base válida,
    vertical/departamento sem alvo) devolve `set()` (nada), não `None` (tudo) —
    senão uma atribuição torta abriria o organograma inteiro. Admin e escopo
    'tudo' saem antes, pelo caminho de sempre."""
    cfg = acesso_vigente()
    if cfg.nivel >= NIVEL_ADMIN:
        return None
    tipo = cfg.escopo_tipo or ("subarvore" if cfg.escopo_id else "tudo")
    if tipo == "tudo":
        return None
    us = ESTADO.unidades
    eu = us.get(cfg.usuario_id)
    if tipo == "proprio":
        return {cfg.usuario_id} if cfg.usuario_id in us else set()
    if tipo == "subarvore":
        # Vazio => o GESTOR direto (o pai do colaborador): "o time do seu gestor".
        base = cfg.escopo_valor or cfg.escopo_id or (eu.parent_id if eu else None)
        if not base or base not in us:
            return set()
        return {base} | descendentes(us, base)
    if tipo in ("vertical", "departamento"):
        # "Por vertical" recorta pelo campo `vertical` (o único preenchido nas
        # pessoas; o N5 vive só no cadastro de CC e não resolve por colaborador).
        campo = "vertical" if tipo == "vertical" else "area"
        alvo = cfg.escopo_valor or (getattr(eu, campo, "") if eu else "")
        if not alvo:
            return set()
        return {i for i, u in us.items() if getattr(u, campo, "") == alvo}
    return set()


def escopo_leitura() -> set[str] | None:
    """Conjunto de ids que a sessão pode VER. Parte do `escopo_permitido` (edição) e
    ACRESCENTA o contexto que cada tipo mostra sem poder editar: `proprio` vê a
    LIDERANÇA acima (a cadeia de gestores até o topo); `departamento` vê o GESTOR
    imediato a quem a equipe responde. A flag `ver_tudo` abre a leitura inteira."""
    if acesso_vigente().ver_tudo:
        return None
    base = escopo_permitido()
    if not base:                    # None (tudo) ou set() (fail-closed): sem contexto
        return base
    cfg = acesso_vigente()
    tipo = cfg.escopo_tipo or ("subarvore" if cfg.escopo_id else "tudo")
    us = ESTADO.unidades
    if tipo == "proprio" and cfg.usuario_id in us:
        return base | {a.id for a in ancestrais(us, cfg.usuario_id)}
    if tipo == "departamento":
        gestores = {us[i].parent_id for i in base
                    if us[i].parent_id in us and us[i].parent_id not in base}
        return base | gestores
    return base


def universo_visivel() -> dict | None:
    """As unidades que a sessão pode VER — fonte única das vistas humanas. `None` =
    sem recorte (Admin, escopo 'tudo', ou a flag `ver_tudo`). Deriva sempre de
    `acesso_vigente()` (por requisição), nunca do ESTADO.config direto."""
    permitidos = escopo_leitura()
    if permitidos is None:
        return None
    return {k: v for k, v in ESTADO.unidades.items() if k in permitidos}


def fonte_visivel() -> dict:
    """A fonte de pessoas de uma vista PLANA: o universo que a sessão pode ver,
    recortado pelo filtro (achados). Um idioma só para Tempo/Skills/Conversa de Valor/Talentos e as
    fichas — antes repetido em sete lugares. A busca livre por nome nunca casa
    alguém de fora, porque o pós-filtro cruza com o universo."""
    uni = universo_visivel()
    base = ESTADO.unidades if uni is None else uni
    dentro = achados()
    if dentro is None:
        return base
    return {k: v for k, v in base.items() if k in dentro}


def modulo_visivel(chave: str) -> bool:
    """Se o módulo (aba) está visível para o usuário da sessão (Fase D). Admin vê
    tudo; lista de módulos vazia = vê tudo (o padrão)."""
    cfg = acesso_vigente()
    if cfg.nivel >= NIVEL_ADMIN:
        return True
    vis = cfg.modulos_visiveis or []
    return not vis or chave in vis


def _rotulo_escopo() -> str:
    """Como o escopo do usuário se descreve numa mensagem de recusa."""
    cfg = acesso_vigente()
    us = ESTADO.unidades
    eu = us.get(cfg.usuario_id)
    tipo = cfg.escopo_tipo or ("subarvore" if cfg.escopo_id else "")
    if tipo == "proprio":
        return eu.nome if eu else T("seu escopo")
    if tipo == "subarvore":
        base = cfg.escopo_valor or cfg.escopo_id or (eu.parent_id if eu else None)
        return us[base].nome if base in us else T("seu escopo")
    if tipo in ("vertical", "departamento"):
        campo = "vertical" if tipo == "vertical" else "area"
        return (cfg.escopo_valor or (getattr(eu, campo, "") if eu else "")
                or T("seu escopo"))
    return T("seu escopo")


def aplicar_acesso(node_id: str | None, email: str | None = None,
                   cfg=None) -> None:
    """Resolve o papel + escopo da pessoa a partir de `Config.acessos`.

    O operador do sistema (superadmin, `acesso.e_superadmin`) entra SEMPRE como
    Administrador total, esteja ou não no organograma ativo — é o que garante que
    trocar o ativo não tranque quem administra.

    Sem NENHUM acesso configurado, o sistema ainda não foi trancado: todo mundo
    entra como Admin — é o estado de hoje, e é o que deixa o primeiro admin montar
    os acessos. Com acessos definidos, quem não tem atribuição entra como
    Visualizador (lê tudo, não edita).

    `cfg` escolhe ONDE gravar o resolvido: sem ele, no `ESTADO.config` global (o
    override de dev/testes e o seletor manual de perfil); com uma cópia por
    requisição (via `resolver_rbac`), na sessão daquela pessoa — sem tocar o
    global. `acessos` é sempre lido do global (é atribuição compartilhada)."""
    cfg = cfg if cfg is not None else ESTADO.config
    cfg.escopo_id = None                         # o mecanismo novo usa tipo/valor
    cfg.ver_tudo = False                         # padrão: leitura segue o escopo
    cfg.ver_1a1_rh = False                        # padrão: só participante lê o 1:1
    if email and acesso.e_superadmin(email):
        cfg.perfil, cfg.escopo_tipo, cfg.escopo_valor = ADMIN, "tudo", ""
        cfg.modulos_visiveis = []
        cfg.ver_1a1_rh = True                    # o operador vê tudo, inclusive 1:1
        return
    if not cfg.acessos and acesso.acesso_aberto():
        cfg.perfil, cfg.escopo_tipo, cfg.escopo_valor = ADMIN, "tudo", ""
        cfg.modulos_visiveis = []
        cfg.ver_1a1_rh = True                    # sistema destrancado: todos Admin
        return
    a = cfg.acessos.get(node_id or "")
    if a:
        cfg.perfil = a.get("papel") if a.get("papel") in PERFIS else VIEWER
        esc = a.get("escopo") or {}
        cfg.escopo_tipo = esc.get("tipo") or "tudo"
        cfg.escopo_valor = esc.get("valor") or ""
        cfg.modulos_visiveis = list(a.get("modulos") or [])
        cfg.ver_tudo = bool(a.get("ver_tudo"))   # flag de leitura por pessoa
        # RH/compliance lê os 1:1 de todos: Admin sempre, ou grant explícito.
        cfg.ver_1a1_rh = cfg.perfil == ADMIN or bool(a.get("ver_1a1_rh"))
    else:
        cfg.perfil, cfg.escopo_tipo, cfg.escopo_valor = VIEWER, "tudo", ""
        cfg.modulos_visiveis = []


def resolver_rbac(uid: str | None, email: str | None):
    """A sessão de UMA pessoa, resolvida sem tocar o Config global.

    Cópia RASA do global (herda título, níveis, campos, idioma, `acessos`…) sobre
    a qual só os cinco campos de sessão são reatribuídos — `usuario_id` aqui e
    perfil/escopo_tipo/escopo_valor/escopo_id/modulos_visiveis via `aplicar_acesso`.
    Nunca faz mutação in-place em objeto compartilhado (modulos_visiveis vira lista
    nova; `acessos` é só lido), então a cópia rasa é segura."""
    sess = copy.copy(ESTADO.config)
    sess.usuario_id = uid or None
    aplicar_acesso(uid or None, email, cfg=sess)
    return sess


def negado(nivel: int, uid: str | None = None) -> str | None:
    """Mensagem de recusa, ou None se a operacao e permitida.

    Le a sessao DESTA requisicao (`acesso_vigente`), nao o Config global: e o que
    faz o perfil/escopo valerem por pessoa, sem um login vazar para o outro."""
    cfg = acesso_vigente()
    # Equipe e desenho derivado, nao unidade gravada: nao ha o que editar nela.
    # A guarda mora aqui, e nao em cada rota, porque `negado` ja e o funil por
    # onde toda mutacao passa — vinte rotas cobertas de uma vez, e rota nova
    # nasce coberta.
    if equipesmod.e_equipe(uid):
        return T("Ação negada: equipe é um desenho que o sistema deriva das "
                 "pessoas, não uma unidade gravada. Volte à visão por pessoa "
                 "para editar a estrutura.")
    if not cfg.pode(nivel):
        exigido = next(p["rotulo"] for p in PERFIS.values() if p["nivel"] == nivel)
        return T("Ação negada: o perfil {perfil} não altera a estrutura. "
                 "Exige {exigido} ou superior.",
                 perfil=T(PERFIS[cfg.perfil]["rotulo"]), exigido=T(exigido))
    permitido = escopo_permitido()
    if permitido is not None and uid is not None and uid not in permitido:
        return T("Ação negada: fora do escopo de edição ({unidade}).",
                 unidade=_rotulo_escopo())
    return None


# ---------------------------------------------------------------------------
# CONSULTAS DE APOIO
# ---------------------------------------------------------------------------
_CACHE_CC: dict = {"chave": None, "mapa": {}}


def mapa_cc() -> dict[str, dict]:
    """uid -> registro de CC resolvido. Recalcula so quando o cadastro ou a
    estrutura mudam: sao 267 unidades por render e o resultado e estavel."""
    assinatura = (len(ESTADO.unidades), id(ESTADO.config.centros_custo),
                  len(ESTADO.config.centros_custo),
                  sum(hash((u.centro_custo, u.area)) for u in ESTADO.unidades.values()))
    if _CACHE_CC["chave"] != assinatura:
        _CACHE_CC["mapa"] = centros.mapear(ESTADO.unidades,
                                           ESTADO.config.centros_custo)
        _CACHE_CC["chave"] = assinatura
    return _CACHE_CC["mapa"]


def tokens_atuais() -> Tokens:
    c = ESTADO.config
    return Tokens(card_w=c.card_w, gap_h=c.gap_h, gap_v=c.gap_v,
                  max_itens=c.max_itens, campos=frozenset(c.campos),
                  niveis=tuple(c.rotulos_nivel.items()))


def filtro_ativo() -> bool:
    f = ESTADO.filtros
    return bool(f.get("texto", "").strip()) or any(f.get(c) for c in CRITERIOS)


def niveis_do_recorte() -> set[int]:
    return {int(n) for n in ESTADO.filtros.get("profundidade", [])
            if str(n).isdigit()}


def recorte_por_nivel(unidades: dict[str, Unidade]) -> set[str] | None:
    """ids nos niveis marcados no palco. None = nenhum nivel marcado.

    Recebe o dicionario desenhado porque profundidade e propriedade da arvore,
    nao da unidade: por equipe, N1 e o primeiro degrau de times, e nao o
    primeiro degrau de pessoas.
    """
    niveis = niveis_do_recorte()
    if not niveis:
        return None
    prof = profundidades(unidades)
    return {uid for uid, d in prof.items() if d in niveis}


def combinar(*conjuntos: set[str] | None) -> set[str] | None:
    """E logico entre recortes, ignorando os que nao estao ativos."""
    ativos = [c for c in conjuntos if c is not None]
    if not ativos:
        return None
    saida = ativos[0]
    for c in ativos[1:]:
        saida = saida & c
    return saida


def achados() -> set[str] | None:
    por_atributo = filtrar(ESTADO.unidades, ESTADO.filtros, mapa_cc())
    if ESTADO.agrupamento == "equipe":
        # O nivel marcado vale para a arvore de times, e ela so existe depois do
        # agrupamento — aplicar aqui recortaria pessoas pela profundidade errada.
        return por_atributo
    return combinar(por_atributo, recorte_por_nivel(ESTADO.unidades))


def visao_de(unidades: dict[str, Unidade], destaque: set[str] | None,
             colapsados: set[str],
             abrir_recorte: bool = False) -> tuple[set[str], set[str] | None]:
    """(colapsados efetivos, restritos). Filtro abre o caminho ate cada achado.

    Os no que so sustentam o caminho ate um achado entram em `restritos` mas
    ficam fora de `destaque`: e o que o desenho mostra esmaecido. Sem abrir o
    colapso desse caminho, um achado no fundo de um galho dobrado ficaria
    invisivel — o filtro diria "3 encontrados" e a tela nao mostraria nenhum.

    `abrir_recorte` e para o recorte por nivel, onde a regra muda: marcar N1 e
    N2 pede os dois niveis, e o no de N1 **esta** no recorte — nao e passagem.
    Mantendo o colapso dele, o N2 que a pessoa acabou de marcar nunca desenha.
    Nos filtros por atributo o padrao continua certo: achar alguem nao e pedir
    para abrir a equipe inteira dele.
    """
    if destaque is None:
        return colapsados, None
    restritos = com_ancestrais(unidades, destaque)
    if abrir_recorte:
        return colapsados - restritos, restritos
    caminho = restritos - destaque
    return colapsados - caminho, restritos


def visao(destaque: set[str] | None) -> tuple[set[str], set[str] | None]:
    return visao_de(ESTADO.unidades, destaque, ESTADO.colapsados,
                    abrir_recorte=bool(niveis_do_recorte()))


def _linha_contagem(n: int, d: int, pessoas: int = 0) -> str:
    """A linha "N unidades · profundidade D · orientação …". Um formatador só,
    para a tela, o SVG e o PDF nunca divergirem no texto."""
    orientacao = {"invertida": T("invertida — liderança na base"),
                  "lateral": T("lateral — a árvore cresce para a direita"),
                  }.get(ESTADO.orientacao, T("convencional"))
    if pessoas:
        return T("{n} equipes · {p} pessoas · profundidade {d} · "
                 "orientação {orientacao}", n=n, p=pessoas, d=d,
                 orientacao=orientacao)
    return T("{n} unidades · profundidade {d} · orientação {orientacao}",
             n=n, d=d, orientacao=orientacao)


def _linha_dos_nos(nos: list, pessoas: int = 0) -> str:
    """A mesma linha contando os NÓS DESENHADOS: `len(nos)` cards e a
    profundidade do galho mais fundo aberto (`nivel` é o nível lógico absoluto)."""
    return _linha_contagem(len(nos), max((c["nivel"] for c in nos), default=0),
                           pessoas)


def _ajustar_cabecalho_ao_desenho(lay: dict, pessoas: int = 0) -> dict:
    """A legenda do DESENHO conta o que está na tela, não o total do estado.

    Dobrar um galho (ou focar numa subárvore) tira cards do desenho; a legenda
    segue-os — senão diz "272 unidades" embaixo de doze caixas. Lê `lay["nos"]`,
    a única verdade do que foi desenhado, então não reinventa a regra de
    visibilidade (colapso + foco + filtro) nem diverge dela. A planilha
    (XLSX/CSV) NÃO passa por aqui de propósito: ela ignora o colapso — é contrato
    de carga, e sair dobrada viraria remoção em massa na volta."""
    cab, nos = lay.get("cabecalho"), lay.get("nos")
    if cab and cab.get("linhas") and nos is not None:
        cab["linhas"][0] = _linha_dos_nos(nos, pessoas)
    return lay


def cabecalho_layout(destaque: set[str] | None,
                     unidades: dict[str, Unidade] | None = None,
                     pessoas: int = 0) -> dict:
    """A faixa do topo do desenho — que vai à tela, ao SVG e ao PDF.

    Recebe o dicionario que esta sendo desenhado em vez de ler `ESTADO`: no
    modo por equipe os nos sao derivados, e contar `ESTADO.unidades` diria
    "267 unidades" embaixo de um desenho com 81 caixas. O cabecalho e a unica
    legenda que o papel leva junto; ele nao pode descrever outro desenho.
    """
    fonte = ESTADO.unidades if unidades is None else unidades
    # `foco` guarda um id que pode ser de pessoa ou de equipe: procurar no
    # dicionario errado dava KeyError e derrubava a tela inteira.
    alvo = fonte.get(ESTADO.foco) if ESTADO.foco else None
    escopo = alvo.nome if alvo else None
    prof = profundidades(fonte) if fonte else {}
    profundidade = max(prof.values()) if prof else 0
    linhas = [_linha_contagem(len(fonte), profundidade, pessoas)]
    if destaque is not None:
        linhas.append(T("filtro ativo · {n} unidade(s) correspondente(s)",
                        n=len(destaque)))
    return {"titulo": f"{ESTADO.config.titulo} · {escopo}" if escopo
                      else ESTADO.config.titulo,
            "linhas": linhas, "escopo": escopo,
            "data": date.today().strftime("%d/%m/%Y")}


def cabecalho_do_desenho() -> dict:
    """O cabecalho que descreve **o desenho que esta na tela agora**.

    Existe porque o PDF monta o proprio titulo e precisava saber, sem repetir a
    regra, se o que ele vai imprimir sao pessoas ou equipes. Duas montagens da
    mesma legenda divergiriam no primeiro ajuste — e a que sai no papel e
    justamente a que ninguem confere antes de mandar imprimir.
    """
    if ESTADO.agrupamento == "equipe":
        agr = agrupar_atual()
        return cabecalho_layout(achados(), agr["unidades"],
                                pessoas=len(agr["equipe_de"]))
    return cabecalho_layout(achados())


def agrupar_atual() -> dict:
    """A vista agrupada, com o filtro aplicado **antes** do agrupamento.

    A ordem importa: filtrar depois seria filtrar equipe por nome de pessoa, e
    o filtro por gestor — que casa a subárvore inteira — não teria sentido em
    cima de nós derivados. Filtrando antes, o desenho responde "quais times
    sobraram", que é a pergunta que alguém faz com um filtro ligado.
    """
    global _EQUIPES_EM_CACHE
    if _EQUIPES_EM_CACHE is not None:
        return _EQUIPES_EM_CACHE
    achou = achados()
    uni = universo_visivel()
    pessoas = ESTADO.unidades if uni is None else uni   # times só do escopo
    if achou is not None:
        visiveis = com_ancestrais(pessoas, achou)
        pessoas = {k: v for k, v in pessoas.items() if k in visiveis}
    _EQUIPES_EM_CACHE = equipesmod.agrupar(pessoas, mapa_cc())
    return _EQUIPES_EM_CACHE


def _correspondentes(agr: dict, destaque_eq: set[str] | None) -> set[str] | None:
    """Quantos CARDS o filtro deixou de pé, quando os cards são times.

    O cabeçalho conta o que recebe. Passar `achados()` aqui — ids de pessoas —
    escrevia "filtro ativo · 34 unidade(s) correspondente(s)" embaixo de um
    desenho de nove times: exatamente o descasamento que `cabecalho_layout`
    ganhou o parâmetro `unidades` para evitar.

    Com nível marcado, quem manda é o recorte por nível, que já é de times. Sem
    nível e com filtro, todo time desenhado sobreviveu ao filtro — `agrupar_atual`
    recorta as pessoas ANTES de agrupar —, então os correspondentes são todos.
    Sem filtro nenhum, `None`: aí o cabeçalho não fala em filtro.
    """
    if destaque_eq is not None:
        return destaque_eq
    return set(agr["unidades"]) if achados() is not None else None


def _floresta_virtual(permitidos: set) -> tuple[dict, str]:
    """Dict sintetizado com raiz VIRTUAL para o Canvas quando o escopo é ATRIBUTIVO
    e desconexo (vertical/departamento): as unidades do escopo, com as raízes-de-
    escopo reparentadas sob um nó-rótulo ('Vertical X'). Preserva a raiz única que
    o motor exige, sem mutar ESTADO.unidades nem vazar nada de fora do escopo."""
    us = ESTADO.unidades
    virtual = "ESC-RAIZ"
    raizes = {i for i in permitidos if i in us and us[i].parent_id not in permitidos}
    sint = {i: replace(us[i], parent_id=(virtual if i in raizes else us[i].parent_id))
            for i in permitidos if i in us}
    topo = ESTADO.config.niveis[0]["codigo"] if ESTADO.config.niveis else "diretoria"
    sint[virtual] = Unidade(id=virtual, codigo="", nome=_rotulo_escopo(),
                            tipo=topo, parent_id=None, ordem=0)
    return sint, virtual


def bound_canvas(destaque):
    """Parâmetros do desenho (modo pessoa) recortados ao escopo de LEITURA:
    (unidades, foco, colapsados, restritos, destaque). Sem escopo => comportamento
    de sempre (visao/ancestrais). Com escopo, ESTRITO: nenhum ancestral de fora
    é desenhado. Subárvore/próprio (conexo) reancoram o foco na base; vertical/
    departamento (desconexo) desenham a floresta sob uma raiz virtual."""
    permitidos = escopo_leitura()
    if permitidos is None:
        colapsados, restritos = visao(destaque)
        return ESTADO.unidades, ESTADO.foco, colapsados, restritos, destaque
    if not permitidos:              # fail-closed: só a raiz virtual, nada real
        sint, virtual = _floresta_virtual(set())
        return sint, virtual, ESTADO.colapsados, {virtual}, None
    # As RAÍZES do conjunto visível (nó cujo pai está fora dele) decidem a forma do
    # desenho, seja qual for o tipo: uma raiz só = conjunto CONEXO (subárvore do
    # gestor, cadeia da liderança do próprio) e desenha a árvore de verdade; várias
    # = conjunto DESCONEXO (vertical/departamento) e desenha a floresta sob raiz
    # virtual. Ancestrais de fora nunca entram — `calcular_layout` só desce.
    us = ESTADO.unidades
    dest = None if destaque is None else (destaque & permitidos)
    raizes = {i for i in permitidos if i in us and us[i].parent_id not in permitidos}
    foco = ESTADO.foco if ESTADO.foco in permitidos else None
    # A RAIZ do recorte nunca entra colapsada: o colapso global é medido a partir
    # do topo da empresa e dobra tudo que está em profundidade >= profundidade_aberta;
    # como o canvas do escopo é RE-ROOTADO na base do recorte (um nó fundo no
    # organograma), essa base já vinha dobrada e o usuário via só o próprio nó como
    # '+N'. Tirar as raízes do colapso abre o recorte na mesma densidade com que o
    # canvas cheio abre a partir da raiz (raiz + filhos), preservando os colapsos
    # mais fundos que a pessoa fizer.
    colapsados = ESTADO.colapsados - raizes
    if len(raizes) == 1:
        (base,) = tuple(raizes)
        return ESTADO.unidades, (foco or base), colapsados, permitidos, dest
    sint, virtual = _floresta_virtual(permitidos)
    return sint, (foco if foco in sint else virtual), colapsados, \
        (permitidos | {virtual}), dest


def _desenho_do_escopo_vazio() -> dict:
    """Desenho de um escopo VAZIO (fail-closed): só a raiz virtual, nenhum nó real.
    Cobre pessoa E equipe — evita cair em raiz(ESTADO.unidades) (vazaria o topo da
    empresa) e evita raiz({}) (que quebraria o motor)."""
    sint, virtual = _floresta_virtual(set())
    return _ajustar_cabecalho_ao_desenho(calcular_layout(
        sint, ESTADO.orientacao, None, foco=virtual, restritos={virtual},
        cabecalho=cabecalho_layout(None, sint), tokens=tokens_atuais(), extras={}))


def _escopo_vazio() -> bool:
    """Escopo configurado mas não-resolvível (fail-closed): universo = {} (nada)."""
    uni = universo_visivel()
    return uni is not None and not uni


def layout_atual(selecionado: str | None = ..., com_cabecalho: bool = True) -> dict:
    alinhar_idioma()          # o desenho carrega rótulos: ARIA, cota, resumo
    if selecionado is ...:
        selecionado = ESTADO.selecionado
    if _escopo_vazio():       # nada visível: não cair na raiz real nem quebrar
        return _desenho_do_escopo_vazio()
    if ESTADO.agrupamento == "equipe":
        # Colapso e foco valem aqui como valem na visão por pessoa: o mesmo
        # conjunto serve os dois, porque `EQ-…` nunca colide com `ORG-…`. Sem
        # isso, 81 times abertos dariam um desenho de 15 000 px que nenhuma
        # folha A3 imprime legível — dobrar um galho é como se faz caber.
        agr = agrupar_atual()
        # O nivel marcado recorta a arvore de times, que so existe aqui.
        destaque_eq = recorte_por_nivel(agr["unidades"])
        colapsados_eq, restritos_eq = visao_de(agr["unidades"], destaque_eq,
                                               ESTADO.colapsados,
                                               abrir_recorte=True)
        return _ajustar_cabecalho_ao_desenho(calcular_layout(
            agr["unidades"], ESTADO.orientacao, selecionado,
            colapsados=colapsados_eq, foco=ESTADO.foco,
            destaque=destaque_eq or set(), restritos=restritos_eq,
            cabecalho=cabecalho_layout(_correspondentes(agr, destaque_eq),
                                       agr["unidades"],
                                       pessoas=len(agr["equipe_de"]))
            if com_cabecalho else None,
            tokens=tokens_atuais(), extras=agr["extras"],
            chave_bloco=_bloco_por_equipe), pessoas=len(agr["equipe_de"]))
    uni_c, foco_c, colapsados, restritos, dest = bound_canvas(achados())
    return _ajustar_cabecalho_ao_desenho(calcular_layout(
        uni_c, ESTADO.orientacao, selecionado, colapsados=colapsados,
        foco=foco_c, destaque=dest or set(),
        cabecalho=cabecalho_layout(dest, uni_c) if com_cabecalho else None,
        tokens=tokens_atuais(), restritos=restritos, extras=mapa_cc()))


# No modo por equipe cada card JA e um time: empilhar irmaos "por departamento"
# nao tem o que agrupar, e o campo que o padrao leria (`area`) carrega ali o
# efetivo — os times sairiam empilhados por numero de pessoas. Cada um no seu
# bloco e a leitura certa, e o motor segue sem saber que equipe existe.
def _bloco_por_equipe(u: Unidade) -> str:
    return u.id


# As colunas da Tabela: (chave, rótulo, sai por padrão). A grade tinha catorze
# colunas fixas e ganhou mais quatro com a planilha do RH — dezoito de uma vez
# não cabem em tela nenhuma, e esconder as novas seria entregá-las mortas.
#
# Quem escolhe é quem lê, e a escolha fica no estado como qualquer outra: ela
# vale para o CSV, para o PDF e para a próxima sessão. Um seletor que esquece o
# que a pessoa marcou é um seletor que ela usa uma vez.
COLUNAS_TABELA = (
    ("codigo", "Código", True), ("nivel_n", "N", True),
    ("nome", "Unidade / pessoa", True), ("cargo", "Cargo", True),
    ("tipo", "Nível", True), ("area", "Departamento", True),
    ("centro_custo", "CC", True), ("n5", "N5", True),
    ("vertical", "Vertical", True), ("tipo_cc", "Natureza", True),
    ("vinculo", "Vínculo", True), ("sub", "Sub.", True),
    ("accountabilities", "Accountabilities", True),
    # As quatro do RH nascem desligadas: a grade já estava cheia, e quem
    # precisa delas liga uma vez e o sistema lembra.
    ("email", "E-mail", False), ("data_inicio", "Admissão", False),
    ("tempo_casa", "Tempo de casa", False), ("status", "Situação", False),
)
COLUNAS_TABELA_PADRAO = tuple(c for c, _r, p in COLUNAS_TABELA if p)


def colunas_da_tabela() -> list[dict]:
    """As colunas com o estado de marcação, prontas para o template."""
    marcadas = set(ESTADO.config.colunas_tabela or COLUNAS_TABELA_PADRAO)
    return [{"chave": c, "rotulo": r, "on": c in marcadas}
            for c, r, _p in COLUNAS_TABELA]


def linhas_tabela() -> list[dict]:
    """Arvore achatada em pre-ordem, honrando filtro e colapso (uma so verdade).

    Com escopo de LEITURA, a árvore começa nas RAÍZES-DO-ESCOPO (floresta) e nunca
    sobe para ancestrais de fora — ESTRITO: nenhum chefe de fora do escopo aparece,
    nem esmaecido. O filtro segue só como realce, cruzado com o que se pode ver."""
    uni = universo_visivel()
    universo = ESTADO.unidades if uni is None else uni
    filhos = mapa_filhos(universo)
    destaque = achados()
    if uni is None:
        colapsados, restritos = visao(destaque)
    else:
        restritos = set(universo)                      # o recorte é o próprio escopo
        destaque = None if destaque is None else (destaque & restritos)
        colapsados = ESTADO.colapsados
    # Busca por NOME na Tabela não força a árvore a abrir: mantém o colapso que a
    # pessoa deixou e destaca/filtra dentro do que já está aberto, em vez de
    # desdobrar tudo a cada tecla. Os chips (vertical, depto…) seguem abrindo o
    # recorte; o pedido é só sobre a busca livre, e só aqui — o canvas não muda.
    if str(ESTADO.filtros.get("texto", "")).strip():
        colapsados = ESTADO.colapsados
    rotulos = ESTADO.config.rotulos_nivel
    linhas: list[dict] = []

    def caminhar(u: Unidade, d: int) -> None:
        visiveis = [f for f in filhos.get(u.id, [])
                    if restritos is None or f.id in restritos]
        oculto = u.id in colapsados and bool(visiveis)
        desc = descendentes(universo, u.id)
        if restritos is not None:
            desc &= restritos
        linhas.append({
            "u": u, "d": d, "tipo": rotulos.get(u.tipo, u.tipo),
            "cc": mapa_cc().get(u.id, {}),
            "achou": destaque is not None and u.id in destaque,
            "passagem": destaque is not None and u.id not in destaque,
            "n": len(visiveis), "descendentes": len(desc), "colapsado": oculto,
            "anos": dominio.tempo_de_casa(u.data_inicio),
        })
        if oculto:
            return
        for f in visiveis:
            caminhar(f, d + 1)

    if uni is None:
        base = ESTADO.unidades.get(ESTADO.foco) or raiz(ESTADO.unidades)
        caminhar(base, profundidades(ESTADO.unidades).get(base.id, 0))
    else:
        raizes = sorted((u for u in universo.values() if u.parent_id not in universo),
                        key=lambda u: sem_acento(u.nome))
        for base in raizes:
            caminhar(base, 0)
    return linhas


def profundidade_max_visivel() -> int:
    """Profundidade máxima da árvore VISÍVEL. Para escopo desconexo (vertical), é a
    profundidade da FLORESTA relativa às raízes-de-escopo — profundidades() exige
    raiz única e quebraria num universo sem raiz."""
    uni = universo_visivel()
    if uni is None:
        return max(profundidades(ESTADO.unidades).values(), default=0)
    filhos = mapa_filhos(uni)
    fundo = 0
    pilha = [(u.id, 0) for u in uni.values() if u.parent_id not in uni]
    while pilha:
        nid, d = pilha.pop()
        fundo = max(fundo, d)
        for f in filhos.get(nid, []):
            pilha.append((f.id, d + 1))
    return fundo


def layout_para_arquivo(com_cabecalho: bool = True) -> dict:
    """Exporta o que esta na tela: filtro, colapso, foco e agrupamento.

    Sem a marca da raiz: o SVG solto viraria quadrado vazio no Inkscape e o PDF
    nao desenha imagem — o logo do papel vem no cabecalho do proprio PDF. Antes
    a altura era reservada de qualquer jeito, e o card mais visivel do documento
    saia com 55 px de branco no pe.
    """
    if _escopo_vazio():       # fail-closed: o PDF/SVG não vaza o topo da empresa
        return _desenho_do_escopo_vazio()
    if ESTADO.agrupamento == "equipe":
        agr = agrupar_atual()
        destaque_eq = recorte_por_nivel(agr["unidades"])
        colapsados_eq, restritos_eq = visao_de(agr["unidades"], destaque_eq,
                                               ESTADO.colapsados,
                                               abrir_recorte=True)
        return _ajustar_cabecalho_ao_desenho(calcular_layout(
                               agr["unidades"], ESTADO.orientacao, None,
                               colapsados=colapsados_eq, foco=ESTADO.foco,
                               destaque=destaque_eq or set(),
                               restritos=restritos_eq,
                               cabecalho=cabecalho_layout(
                                   _correspondentes(agr, destaque_eq),
                                   agr["unidades"],
                                   pessoas=len(agr["equipe_de"]))
                               if com_cabecalho else None,
                               tokens=tokens_atuais().com(marca=False), extras=agr["extras"],
                               chave_bloco=_bloco_por_equipe),
                               pessoas=len(agr["equipe_de"]))
    uni_c, foco_c, colapsados, restritos, dest = bound_canvas(achados())
    return _ajustar_cabecalho_ao_desenho(calcular_layout(
                           uni_c, ESTADO.orientacao, None,
                           colapsados=colapsados, foco=foco_c,
                           destaque=dest or set(),
                           cabecalho=cabecalho_layout(dest, uni_c) if com_cabecalho else None,
                           tokens=tokens_atuais().com(marca=False), restritos=restritos,
                           extras=mapa_cc()))


def escala_impressao() -> int:
    """Percentual com que o desenho atual cabe na folha A3, em inteiro.

    Sem paginacao, o clique em "PDF A3" seria cego: nada na tela diria que o
    resultado sai a 2 %. Calcular aqui custa um layout a mais por render e
    devolve a informacao no ponto da decisao, nao depois do download.
    """
    _, _, w, h = (float(v) for v in
                  layout_para_arquivo(com_cabecalho=False)["viewbox"].split())
    return round(pdfmod.enquadrar(w, h)[0] * 100)


# O nome de cada critério na barra. Vive aqui, e não espalhado pelo template,
# porque a pílula de filtro ativo precisa do mesmo nome que o chip mostra — dois
# vocabulários para o mesmo critério seriam dois critérios para quem lê.
ROTULO_CRITERIO = {
    "vertical_negocio": "Vertical", "tipo_cc": "Natureza",
    "centro_custo": "Centro de custo", "area": "Departamento",
    "cargo": "Cargo", "gestor": "Gestor", "tipo": "Nível",
    "vinculo": "Vínculo", "vertical": "Vertical (N2)",
}


def filtros_ativos(opcoes: dict) -> list[dict]:
    """Um item por valor marcado — é o que a pílula precisa para sumir sozinha.

    O rótulo sai de `opcoes`, o mesmo que o popover mostra: `82.43 · Software
    Team 3`, e não `82.43`. A pílula é onde se lê o recorte sem abrir nada.
    """
    saida = []
    texto = str(ESTADO.filtros.get("texto", "")).strip()
    if texto:
        saida.append({"campo": "texto", "rotulo_campo": "Busca livre",
                      "valor": texto, "rotulo": texto})
    for campo in CRITERIOS:
        rotulos = dict(opcoes.get(campo, []))
        for valor in ESTADO.filtros.get(campo) or []:
            saida.append({"campo": campo,
                          "rotulo_campo": ROTULO_CRITERIO.get(campo, campo),
                          "valor": valor, "rotulo": rotulos.get(valor, valor)})
    return saida


def contexto_filtros() -> dict:
    # `ESTADO.filtros` entra também como critério: é o que faz os chips se
    # filtrarem uns aos outros. Cada um oferece o que sobrou depois do recorte
    # dos demais — opção que sempre devolveria vazio deixa de ser oferecida.
    opcoes = valores_de_filtro(universo_visivel() or ESTADO.unidades,
                               mapa_cc(), ESTADO.filtros)
    return {"filtros": ESTADO.filtros, "opcoes": opcoes,
            "ativos": filtros_ativos(opcoes),
            "ativo": filtro_ativo(), "tipos": ESTADO.config.rotulos_nivel,
            "escala_pdf": escala_impressao()}


def arvore_json(u: Unidade, filhos: dict, prof: dict) -> dict:
    """API-02: arvore aninhada em ordem logica, independente da orientacao."""
    return {
        "id": u.id, "codigo": u.codigo, "nome": u.nome, "tipo": u.tipo,
        "profundidade": prof[u.id], "ordem_exibicao": u.ordem,
        "responsavel": ({"nome_exibicao": u.responsavel, "cargo": u.cargo}
                        if u.responsavel else
                        ({"nome_exibicao": u.nome, "cargo": u.cargo} if u.cargo
                         else None)),
        "area": u.area, "email_corp": u.email,
        "centro_custo": u.centro_custo, "vertical": u.vertical,
        "centro_custo_resolvido": mapa_cc().get(u.id, {}),
        "responsabilidades": u.responsabilidades,
        "competencias": u.competencias,
        "filhos": [arvore_json(f, filhos, prof) for f in filhos.get(u.id, [])],
    }


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
app = FastAPI(title="GPlanSiS|Peoples — Canvas Twin", version="1.2.0")


async def resolver_sessao(req: Request):
    """Dependência global: resolve a sessão DESTA requisição a partir do cookie
    assinado e a deposita no ContextVar `_SESSAO`, limpando no fim. Sem cookie
    válido, deposita None — e `acesso_vigente()` cai no `ESTADO.config` global.

    Assíncrona de propósito: roda na própria task da requisição (não no threadpool),
    então o valor propaga para os endpoints sync — o Starlette copia o contexto ao
    despachar para o threadpool — e para os async. É generator (set antes do yield,
    reset no finally) para nunca herdar a sessão de uma requisição na seguinte.
    Comprovado por teste de isolamento concorrente (test_sessao_por_requisicao)."""
    carga = sessao_atual(req)
    sess = resolver_rbac(carga.get("uid"), carga.get("sub")) if carga else None
    _marcar_presenca(sess.usuario_id if sess else None)   # "ativo agora"
    req.state.sessao = sess
    tok = _SESSAO.set(sess)
    try:
        modulo = modulo_da_rota(req.url.path)
        if modulo and not modulo_visivel(modulo):
            from fastapi import HTTPException
            raise HTTPException(status_code=403,
                                detail=T("Módulo indisponível para o seu acesso."))
        yield
    finally:
        _SESSAO.reset(tok)


# Toda rota resolve a sessão antes de correr. Mounts (/vendor, /estatico, /marca)
# e 404 fora do roteador não a executam — e não leem sessão, então tudo bem.
app.router.dependencies.append(Depends(resolver_sessao))
app.mount("/vendor", StaticFiles(directory=str(RAIZ / "web" / "vendor")), name="vendor")
# JS próprio que cresceu demais para viver dentro do `base.html`: a grade tem
# umas quatrocentas linhas, e inline elas seriam reenviadas a cada render.
app.mount("/estatico", StaticFiles(directory=str(RAIZ / "web" / "estatico")),
          name="estatico")
app.mount("/marca", StaticFiles(directory=str(RAIZ / "web" / "marca")), name="marca")

# --- ícone de aplicativo (celular) ------------------------------------------
# O manifest existe por UM motivo aqui: fazer o Android usar o ícone da marca no
# atalho da tela inicial. Sem ele o Chrome recorta um retrato da página, e o
# atalho fica com um pedaço do formulário de login dentro.
#
# Servido da raiz, e não de /estatico, porque o `scope` de um manifest é, por
# omissão, a pasta onde ele mora: publicado em /estatico ele descreveria um
# aplicativo cujo escopo é /estatico, e o atalho abriria fora do app.
#
# Não há service worker, e isso é deliberado: o que se pediu foi o ícone. Um SW
# guarda páginas em cache e passaria a decidir o que o usuário vê quando a rede
# falha — decisão grande demais para entrar de carona num ajuste de logotipo.
MANIFESTO = {
    "name": "GPlanSiS|Peoples",
    "short_name": "Peoples",
    "description": "Organograma invertido: entenda sua organização, "
                   "desenvolva talentos e transforme dados humanos em decisões.",
    "lang": "pt-BR",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    # O grafite institucional nas duas: `theme_color` pinta a barra do sistema e
    # `background_color` é a tela que aparece ANTES do primeiro pixel do app —
    # deixá-la branca daria um flash branco na abertura de um app escuro.
    "theme_color": "#2D3336",
    "background_color": "#2D3336",
    "icons": [
        {"src": "/marca/icone-192.png", "sizes": "192x192", "type": "image/png",
         "purpose": "any"},
        {"src": "/marca/icone-512.png", "sizes": "512x512", "type": "image/png",
         "purpose": "any"},
        # O maskable é outro arquivo, não o mesmo com outro rótulo: o aparelho
        # recorta o ícone na forma do seu tema, e o desenho sem margem perde o
        # "P" no corte.
        {"src": "/marca/icone-512-maskable.png", "sizes": "512x512",
         "type": "image/png", "purpose": "maskable"},
    ],
}


@app.get("/manifest.webmanifest")
def manifest():
    """O manifest do aplicativo. Público como os ativos de marca: o celular
    busca este arquivo ANTES de qualquer login, e protegê-lo faria o atalho
    nascer sem ícone."""
    return JSONResponse(MANIFESTO, media_type="application/manifest+json",
                        headers={"Cache-Control": "public, max-age=3600"})

tpl = Jinja2Templates(directory=str(RAIZ / "web" / "templates"))
# Nomes proprios com acento no ledger nao devem virar ç na tela.
# Sai como texto, nao como safe: o autoescape do Jinja continua valendo.
tpl.env.filters["json_br"] = lambda v: json.dumps(v, ensure_ascii=False)
# Markdown da MarIA em HTML. Escapa antes de formatar: nada que o modelo
# escreva sobrevive como tag. Usar com |safe é seguro por causa disso.
tpl.env.filters["md"] = mariamod.formatar


def abrir_provisionamento(u, de: str, para: str) -> dict | None:
    """Mudou de área? TI precisa saber o que revogar e o que conceder.

    O organograma já registrou a mudança; deixar TI descobrir por conta própria
    é como o acesso de uma área antiga sobrevive por meses.
    """
    if not de or not para or de == para:
        return None
    pedido = provmod.abrir(
        u, de, para, provmod.indexar(ESTADO.config.software_por_area),
        por=(usuario_atual() or {}).get("nome", ""))
    if pedido is None:
        return None
    ESTADO.provisionamentos.append(pedido)
    commit("criar", u.id, "provisionamento de TI aberto",
           {"de": de, "para": para,
            "revogar": len(pedido["revogar"]),
            "conceder": len(pedido["conceder"])})
    avisar_ti(pedido)
    return pedido


def avisar_ti(pedido: dict) -> tuple[bool, str]:
    """Manda o pedido por e-mail, se houver SMTP.

    Falha de envio não derruba nada: o pedido já está na fila, e a fila é a
    notificação quando o carteiro não existe. Perder o pedido por causa do
    e-mail seria trocar o importante pelo acessório.
    """
    if not correio.configurado():
        return False, "SMTP não configurado"
    alvo = provmod.destinatarios(ESTADO.unidades, mapa_cc())
    assunto, corpo = correio.texto_provisionamento(pedido, T)
    ok, detalhe = correio.enviar(alvo, assunto, corpo)
    registrar("alterar", "-", "aviso de provisionamento por e-mail",
              {"pedido": pedido["id"], "ok": ok, "detalhe": detalhe,
               "destinatarios": len(alvo)})
    return ok, detalhe


def usuario_atual() -> dict | None:
    """Quem está usando o sistema, na linguagem do próprio organograma.

    A pessoa logada é uma unidade da estrutura — não um registro paralelo. Isso
    evita a duplicidade clássica (cadastro de usuário que discorda do
    organograma) e faz o avatar mostrar exatamente o que o card mostra.
    """
    u = ESTADO.unidades.get(acesso_vigente().usuario_id or "")
    if u is None:
        return None
    cc = (mapa_cc().get(u.id) or {})
    partes = [p for p in u.nome.split() if len(p) > 2] or u.nome.split()
    return {
        "id": u.id, "nome": u.nome, "cargo": u.cargo, "email": u.email,
        "iniciais": "".join(p[0] for p in (partes[:1] + partes[-1:]))[:2].upper(),
        "fatos": [
            ("Nível", ESTADO.config.rotulos_nivel.get(u.tipo, u.tipo)),
            ("Centro de custo", u.centro_custo),
            ("Departamento", u.area),
            ("Vertical (N2)", cc.get("vertical_negocio") or u.vertical),
        ],
    }


def passos_da_visita() -> list[dict]:
    """Os passos já traduzidos e já formatados.

    `ajuda.py` guarda o texto em português; `T()` traduz e `formatar` transforma
    `**` e crase em `<b>` e `<code>` — o mesmo filtro da MarIA, que escapa antes
    de formatar. Fazer isso no cliente pediria um formatador em JavaScript e um
    catálogo em JavaScript, que é onde a tradução costuma se perder.
    """
    return [{**p, "titulo": T(p["titulo"]),
             "texto": mariamod.formatar(T(p["texto"]))}
            for p in ajuda.passos()]


def render(nome: str, **ctx) -> str:
    ctx.setdefault("cfg", acesso_vigente())
    # O nonce da CSP desta requisição: só os <script> do base.html o recebem.
    ctx.setdefault("csp_nonce", _NONCE.get())
    ctx.setdefault("usuario", usuario_atual())
    ctx.setdefault("login_exigido", acesso.exigir_login())
    # A lista de organogramas chega a todo template (o seletor mora no cabeçalho,
    # que é comum a todas as vistas). É uma leitura de um JSON pequeno.
    ctx.setdefault("organogramas", contexto_organogramas())
    # Quem gerencia/troca organograma é Admin: o ativo é global, trocar muda o
    # que TODOS veem. O template mostra o seletor a todos, mas só oferece as ações
    # a quem pode. A checagem de verdade está nas rotas (negado(NIVEL_ADMIN)).
    ctx.setdefault("e_admin", acesso_vigente().nivel >= NIVEL_ADMIN)
    # Visibilidade de módulos por pessoa (Fase D): o cabeçalho esconde as abas
    # que o acesso do usuário não inclui. `modulo_visivel` é o mesmo juiz das
    # rotas — ver a aba e entrar nela nunca divergem.
    ctx.setdefault("modulo_visivel", modulo_visivel)
    # `t` chega a todo template sem que nenhum precise pedir. Um template que
    # esqueça de traduzir mostra português — nunca chave crua, nunca vazio.
    ctx.setdefault("idioma", ESTADO.config.idioma)
    ctx.setdefault("idiomas", idiomasmod.IDIOMAS)
    ctx.setdefault("t", lambda texto, **p: idiomasmod.traduzir(
        texto, ctx.get("idioma", ESTADO.config.idioma), **p))
    # `th`: o texto do catálogo é marcação confiável (tem <b>, <code>), os
    # PARÂMETROS não — saem escapados (Markup.format). Substitui `t(..., p=x)|safe`,
    # que deixava passar como HTML o valor interpolado (rótulo, nome, tabela).
    ctx.setdefault("th", lambda texto, **p: Markup(idiomasmod.traduzir(
        texto, ctx.get("idioma", ESTADO.config.idioma))).format(**p))
    # Piso de leitura: um numero so para a tela e para o papel (pdf.PISO_LEITURA).
    ctx.setdefault("piso_leitura_frac", pdfmod.PISO_LEITURA)
    ctx.setdefault("piso_leitura", round(pdfmod.PISO_LEITURA * 100))
    ctx.setdefault("temas", cfgmod.TEMAS)
    ctx.setdefault("k", cfgmod.cores_canvas(ctx.get("exportando", False)))
    ctx.setdefault("cores", cfgmod.CORES_CANVAS)
    ctx.setdefault("cores_nivel", ESTADO.config.cores_nivel)
    ctx.setdefault("rotulos_nivel", ESTADO.config.rotulos_nivel)
    ctx.setdefault("vinculos", dominio.VINCULOS)
    # O diff da carga carrega valores de tipos diferentes — texto, lista de
    # competências, lista de accountabilities em dicionário. Um `|join` no
    # template resolveria dois dos três e imprimiria `[{'descricao': ...}]` no
    # terceiro, que é justamente o campo novo.
    ctx.setdefault("mostrar", importador.para_texto)
    # Anos de casa com uma casa decimal, e travessão quando não há número.
    # Vazio pareceria dado faltando; `0,0` seria mentira — grupo pequeno demais
    # para uma mediana não tem mediana, e é isso que o travessão diz.
    ctx.setdefault("anos", lambda v: "—" if v is None
                   else f"{v:.1f}".replace(".", ","))
    ctx.setdefault("por_equipe", ESTADO.agrupamento == "equipe")
    # Qual pirâmide o botão de orientação entrega. Estando numa delas é a outra;
    # estando na lateral é a guardada. O rótulo mostra o que se vai receber, e
    # sem isto ele prometia "Convencional" e devolvia a invertida.
    ctx.setdefault("piramide_do_botao",
                   ESTADO.orientacao_piramide if ESTADO.orientacao == "lateral"
                   else ESTADO.orientacao)
    ctx.setdefault("e_lateral", ESTADO.orientacao == "lateral")
    ctx.setdefault("helper", ESTADO.config.helper)
    # Função, e não lista: só a página inteira inclui a visita, e um fragmento
    # não pode pagar a tradução de dezenove passos para devolver um botão.
    ctx.setdefault("passos_ajuda", passos_da_visita)
    ctx.setdefault("niveis_marcados",
                   {str(n) for n in ESTADO.filtros.get("profundidade", [])})
    ctx.setdefault("tem_desfazer", bool(ESTADO.historico))
    ctx.setdefault("tem_refazer", bool(ESTADO.refazer))
    return tpl.get_template(nome).render(**ctx)


def canvas(req: Request, extra: str = "") -> HTMLResponse:
    return HTMLResponse(render("_canvas.html", request=req, layout=layout_atual())
                        + extra)


def T(texto: str, **params) -> str:
    """Tradução das mensagens que o próprio servidor escreve."""
    return idiomasmod.traduzir(texto, ESTADO.config.idioma, **params)


def alinhar_idioma() -> None:
    """Módulos puros não recebem request: recebem o idioma antes de rodar."""
    importador.IDIOMA = ESTADO.config.idioma
    dominio.IDIOMA = ESTADO.config.idioma
    dcrmod.IDIOMA = ESTADO.config.idioma
    cgvmod.IDIOMA = ESTADO.config.idioma
    talentosmod.IDIOMA = ESTADO.config.idioma
    gptwmod.IDIOMA = ESTADO.config.idioma
    m365mod.IDIOMA = ESTADO.config.idioma


def alerta(texto: str) -> str:
    """Todo aviso do servidor passa por aqui — logo, aqui é onde ele traduz.

    Traduzir no funil, e não em cada chamada, é o que evita ter de lembrar de
    envolver 60 mensagens uma a uma (e esquecer algumas). Mensagem montada com
    interpolação não casa com chave nenhuma e sai em português: essas o autor
    precisa passar como `T("… {n} …", n=…)` na chamada.
    """
    # Escapado SEMPRE: o aviso interpola nome, e-mail, erro de planilha e
    # mensagem de driver — dado de usuário que não pode virar marcação (XSS
    # armazenado). Nenhuma mensagem do servidor depende de HTML aqui dentro.
    return ('<div id="alerta" class="alerta" role="status">'
            f'{htmlmod.escape(T(texto), quote=False)}</div>')


def recusar(req: Request, msg: str) -> HTMLResponse:
    """INT-06: recusa responde 200 com o canvas intacto e um aviso."""
    return canvas(req, alerta(msg))


def corpo_painel(req: Request, uid: str, com_canvas: bool = True,
                 vista_origem: str = "canvas", contexto_origem: str = "") -> str:
    uni = universo_visivel()
    universo = ESTADO.unidades if uni is None else uni
    u = universo.get(uid)                   # fora do escopo => painel vazio
    if u is None:
        return render("_painel_vazio.html", request=req)
    filhos = mapa_filhos(universo)
    prof = profundidades(ESTADO.unidades)
    return render(
        "_painel.html", request=req, u=u, tipos=TIPOS,
        pai=universo.get(u.parent_id) if u.parent_id else None,
        u_nivel=prof.get(uid, 0), n_filhos=len(filhos.get(uid, [])),
        n_descendentes=len(descendentes(universo, uid)),
        trilha=[a for a in ancestrais(ESTADO.unidades, uid) if a.id in universo],
        centros=[c for c in ESTADO.config.centros_custo if c.get("ativo", True)],
        cargos_conhecidos=sorted({c["cargo"] for c in ESTADO.config.catalogo_cargos},
                                 key=sem_acento),
        nivel_do_cargo=(cargosmod.classificar(u.cargo, ESTADO.config.indice_cargos,
                                              ESTADO.config.regras_cargo)
                        if u.cargo else ""),
        pode_editar=negado(NIVEL_EDITOR, uid) is None,
        destinos=sorted(
            (x for x in universo.values()
             if x.id != uid and x.id not in descendentes(universo, uid)),
            key=lambda x: (prof.get(x.id, 0), sem_acento(x.nome))),
        texto="\n".join(("> " if r.get("origem") == "delegada" else "")
                        + r.get("descricao", "") for r in u.responsabilidades),
        skills=", ".join(u.competencias),
        oob=com_canvas, layout=layout_atual(uid) if com_canvas else None,
        vista_origem=vista_origem, contexto_origem=contexto_origem,
        vinculos=dominio.VINCULOS,
        mural=socialmod.do_card(ESTADO.mural, uid),
        mural_conta=socialmod.contagem(ESTADO.mural, uid),
        valores_social=socialmod.VALORES,
        eu=(usuario_atual() or {}).get("id", ""),
        sou_admin=acesso_vigente().perfil == ADMIN,
        status_opcoes=dominio.STATUS, hoje_iso=date.today().isoformat(),
        anos_de_casa=dominio.tempo_de_casa(u.data_inicio),
        rotulo_faixa=dict((c, r) for c, r, _p in dominio.FAIXAS_CASA).get(
            dominio.faixa_de_casa(dominio.tempo_de_casa(u.data_inicio)), ""))


def painel_equipe(req: Request, uid: str, pessoa: str | None = None) -> str:
    """A gaveta de uma equipe: a hierarquia dentro dela, e nada editavel.

    Mostra a arvore de comando do time porque e essa a pergunta que sobra
    quando o card diz apenas "12 pessoas" — quais doze, e quem responde a quem
    entre elas. Clicar num nome evidencia a pessoa e abre a sua linha: a quem
    ela responde e quem responde a ela.
    """
    agr = agrupar_atual()
    unidade = agr["unidades"].get(uid)
    membros = agr["membros"].get(uid, [])
    linhas = equipesmod.hierarquia(membros)

    # Só evidencia quem é MEMBRO deste time (agrupar_atual já recorta ao escopo);
    # um `pessoa` de fora, passado por URL, é ignorado. E o chefe / os vínculos vêm
    # do universo — nunca revelam um chefe de fora do escopo.
    uni = universo_visivel()
    universo = ESTADO.unidades if uni is None else uni
    dentro = {m.id for m in membros}
    escolhida = universo.get(pessoa) if (pessoa and pessoa in dentro) else None
    detalhe = None
    if escolhida is not None:
        filhos = mapa_filhos(universo)
        subordinados = filhos.get(escolhida.id, [])
        detalhe = {
            "u": escolhida,
            "chefe": universo.get(escolhida.parent_id)
                     if escolhida.parent_id else None,
            # Quem responde a ela mas está noutro time é o que explica por que
            # aquele time existe: some da lista de dentro e some do card.
            "diretos": subordinados,
            "fora": [f for f in subordinados if f.id not in dentro],
            "cc": mapa_cc().get(escolhida.id, {}),
        }
    return render("_painel_equipe.html", request=req, u=unidade, equipe_id=uid,
                  linhas=linhas, total=len(membros), pessoa=pessoa,
                  detalhe=detalhe)


def painel_atual(req: Request) -> str | None:
    """Recarregar a pagina nao pode perder a selecao: o servidor a guarda."""
    uid = ESTADO.selecionado
    if not uid:
        return None
    if equipesmod.e_equipe(uid):
        return painel_equipe(req, uid)
    if uid not in ESTADO.unidades:
        return None
    return corpo_painel(req, uid, com_canvas=False)


# ---------------------------------------------------------------------------
# SKILLS POR COLABORADOR — a matriz de competências lida contra a pessoa
# ---------------------------------------------------------------------------
_STOP_COMP = {"de", "da", "do", "dos", "das", "em", "para", "com", "por", "and", "the", "of",
              "e", "ou", "a", "o", "um", "uma", "no", "na", "nos", "nas"}


def _casa_competencia(declarada: str, desejavel: str) -> bool:
    """A competência que a pessoa declara cobre a desejável do cargo? Casamento
    por palavra significativa (≥3 letras, sem preposições), sem acento e sem
    caixa: "SCADA" casa "Sistemas SCADA/HMI (WinCC…)"; "Excel" casa "Excel
    avançado". É uma leitura de apoio ao PDI — não nota, não ranking."""
    d = sem_acento(declarada or "").lower()
    t = sem_acento(desejavel or "").lower()
    if not d or not t:
        return False
    if d in t or t in d:
        return True
    palavras = [w for w in re.findall(r"[a-z0-9+#.]+", d) if len(w) >= 3 and w not in _STOP_COMP]
    return any(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", t) for w in palavras)


def _skills_ficha(u, linhas=None, overlay=None):
    """A ficha Skills do CARGO desta pessoa (ou None: raiz, cargo vazio, fora do
    recorte). `linhas`/`overlay` podem vir pré-computados (o .zip de todos)."""
    if not u.cargo:
        return None
    if linhas is None:
        return _ficha_ou_none(dcrmod.chave_funcao(u.cargo))
    return dcrmod.ficha(dcrmod.chave_funcao(u.cargo), linhas, ESTADO.unidades,
                        overlay, ESTADO.config.rotulos_nivel)


def resumo_skills(u, linhas=None, overlay=None) -> dict:
    """O que a ficha do colaborador mostra em cards: missão, competências
    técnicas desejáveis marcadas ✓/○ contra o que a pessoa declara, e a
    aderência (k de n). Vazio quando não há ficha."""
    f = _skills_ficha(u, linhas, overlay)
    if f is None:
        return {"tem": False}
    doc = {s["chave"]: s for s in dcrmod.documento(f)}
    comps = doc["competencias"]["conteudo"]
    tecnicas = [c for c in comps if c.startswith("[Técnica]")] or \
               [c for c in comps if not c.startswith("[")]
    declaradas = list(u.competencias or [])
    itens = []
    for c in tecnicas:
        alvo = re.sub(r"^\[Técnica\]\s*", "", c)
        alvo_sem_nivel = re.sub(r"\s+—\s+nível.*$", "", alvo)
        itens.append({"texto": alvo,
                      "ok": any(_casa_competencia(d, alvo_sem_nivel) for d in declaradas)})
    ok = sum(1 for i in itens if i["ok"])
    return {"tem": True, "chave": f["chave"], "papel": f["papel"],
            "missao": (doc["missao"]["conteudo"] or [""])[0],
            "tecnicas": itens, "ok": ok, "total": len(itens),
            "pct": round(100 * ok / len(itens)) if itens else 0,
            "comportamentais": sum(1 for c in comps if c.startswith("[Comportamental]")),
            "requisitos": len(doc["requisitos"]["conteudo"]),
            "origem": doc["competencias"]["origem"]}


def skills_markdown(u, linhas=None, overlay=None) -> str:
    """O Skills de UMA pessoa em Markdown: quem ela é na estrutura, o que declara,
    a aderência ao cargo e a ficha GEP-FOR-003 do cargo por inteiro. É o
    documento que o RH leva para a Conversa de Valor e para o PDI."""
    pai = ESTADO.unidades.get(u.parent_id) if u.parent_id else None
    filhos = mapa_filhos(ESTADO.unidades).get(u.id, [])
    anos = dominio.tempo_de_casa(u.data_inicio)
    r = resumo_skills(u, linhas, overlay)
    L = [f"# {T('Skills')} — {u.nome}", "",
         f"**{T('Código')}:** {u.codigo}  ",
         f"**{T('Cargo')}:** {u.cargo or dcrmod.VAZIO}  ",
         f"**{T('Nível')}:** {ESTADO.config.rotulos_nivel.get(u.tipo, u.tipo)}  ",
         f"**{T('Departamento')}:** {u.area or dcrmod.VAZIO}  ",
         f"**{T('Centro de custo')}:** {u.centro_custo or dcrmod.VAZIO}  ",
         f"**{T('Vertical (N2)')}:** {u.vertical or dcrmod.VAZIO}  ",
         f"**{T('Vínculo')}:** {dominio.VINCULOS.get(u.vinculo, (u.vinculo,))[0] if u.vinculo else dcrmod.VAZIO}  ",
         f"**{T('Admissão')}:** {u.data_inicio or dcrmod.VAZIO}"
         + (f" ({anos:.1f} {T('anos de casa')})" if anos is not None else "") + "  ",
         f"**{T('Gestor direto')}:** " + (f"{pai.nome} — {pai.cargo}" if pai and pai.parent_id else
                                          (pai.nome if pai else dcrmod.VAZIO)) + "  ",
         f"**{T('Liderados diretos')}:** {len(filhos)}", ""]
    L += [f"## {T('Competências declaradas')}", ""]
    L += [f"- {c}" for c in (u.competencias or [])] or [dcrmod.VAZIO]
    L += ["", f"## {T('Accountabilities')}", ""]
    acc = [("> " if x.get("origem") == "delegada" else "") + x.get("descricao", "")
           for x in (u.responsabilidades or [])]
    L += [f"- {a}" for a in acc] or [dcrmod.VAZIO]
    L += ["", f"## {T('Aderência ao Skills do cargo')}", ""]
    if r["tem"]:
        L.append(T("{k} de {n} competências técnicas desejáveis declaradas ({pct}%).",
                   k=r["ok"], n=r["total"], pct=r["pct"]))
        L.append("")
        L += [f"- {'✓' if i['ok'] else '○'} {i['texto']}" for i in r["tecnicas"]]
        L.append("")
        L.append(T("✓ = competência declarada no cadastro da pessoa; ○ = desejável no cargo e ainda não declarada (gap para o PDI)."))
        L.append("")
        f = _skills_ficha(u, linhas, overlay)
        ficha_md = dcrmod.markdown(f)
        L.append(re.sub(r"^(#+)", r"#\1", ficha_md, flags=re.M))       # rebaixa os títulos
    else:
        L.append(T("Cargo sem ficha Skills no recorte atual."))
    L += ["", "---", f"{T('Gerado em')} {agora_iso()} · GPlanSiS|Peoples · "
          f"{orgsmod.nome_de(orgsmod.ler(), SLUG_ATIVO)}"]
    return "\n".join(L) + "\n"


def _nome_arquivo_md(u) -> str:
    base = sem_acento(u.nome or u.id).lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:60]
    return f"skills-{(u.codigo or u.id).replace('/', '-')}-{base}.md"


# ---------------------------------------------------------------------------
# API DO LAKEHOUSE — somente leitura, para os outros sistemas do hub
# ---------------------------------------------------------------------------
# O Peoples é dono do banco `peoples` e CONSUMIDOR do lakehouse: aqui ele lê o
# `gplansis_lake` com uma credencial que só tem SELECT em `gold`/`silver`. Quem
# escreve lá é o ETL, noutro serviço e com outro usuário. Um sistema do hub que
# queira estes números chama esta API (ou conecta no lakehouse com o papel
# `lake_leitor`) — nunca no banco de outro sistema.
def _lake_autorizado(req: Request) -> bool:
    """Token de serviço válido, ou sessão de Administrador."""
    token = (req.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    if lakemod.token_valido(token):
        return True
    return negado(NIVEL_ADMIN) is None


@app.get("/api/v1/lake")
def lake_catalogo(req: Request):
    """O catálogo: que vistas existem, o que cada uma responde e quando foi a
    última carga. É por onde outro sistema descobre o que pode ler."""
    return JSONResponse({
        "lakehouse": "gplansis_lake", "somente_leitura": True,
        "situacao": lakemod.situacao(),
        "vistas": [{"nome": n, "fonte": f, "descricao": d}
                   for n, (f, d) in sorted(lakemod.VISTAS.items())],
        **lakemod.ultima_carga()})


@app.get("/api/v1/lake/{vista}")
def lake_vista(req: Request, vista: str, organograma: str = "", limite: int = 0):
    """Uma vista do lakehouse em JSON. `organograma` filtra; `limite` corta.

    Sem escrita, por três razões acumuladas: a credencial não tem permissão, a
    sessão é aberta como somente-leitura, e não existe rota de POST aqui.

    Quem lê: o token de serviço (máquina-a-máquina) ou, pelo navegador, só o
    Administrador. As vistas trazem colaborador, 9-box e sucessão da empresa
    inteira, sem o recorte de escopo das telas — com cookie de Visualizador ou
    Editor elas vazavam tudo."""
    if not _lake_autorizado(req):
        return JSONResponse({"erro": "acesso negado"}, status_code=403)
    dados = lakemod.consultar(vista, organograma, limite or lakemod.LIMITE_PADRAO)
    return JSONResponse(dados, status_code=404 if dados.get("erro") == "vista desconhecida" else 200)


@app.get("/unidades/{uid}/skills.md")
def skills_md(req: Request, uid: str):
    """O Skills do colaborador em Markdown, para baixar. Respeita o escopo de
    leitura da sessão (fora do escopo = 404, como a ficha)."""
    uni = universo_visivel()
    universo = ESTADO.unidades if uni is None else uni
    u = universo.get(uid)
    if u is None:
        return Response(status_code=404)
    return Response(skills_markdown(u), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{_nome_arquivo_md(u)}"'})


@app.get("/skills/todos.zip")
def skills_zip(req: Request):
    """Um .md por pessoa do recorte visível, num .zip, com um índice. A ficha de
    cada cargo é montada uma vez (`medir` roda uma vez, não 272)."""
    uni = universo_visivel()
    universo = ESTADO.unidades if uni is None else uni
    fonte = fonte_visivel()
    linhas = dcrmod.medir(fonte, mapa_cc())
    overlay = registros_dcr()
    pessoas = sorted((u for u in universo.values() if u.parent_id),
                     key=lambda x: sem_acento(x.nome))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        indice = [f"# {T('Skills')} — {orgsmod.nome_de(orgsmod.ler(), SLUG_ATIVO)}", "",
                  f"{len(pessoas)} {T('colaboradores')} · {T('Gerado em')} {agora_iso()}", ""]
        for u in pessoas:
            nome = _nome_arquivo_md(u)
            z.writestr(nome, skills_markdown(u, linhas, overlay))
            indice.append(f"- [{u.nome}]({nome}) — {u.cargo or dcrmod.VAZIO} · {u.area or dcrmod.VAZIO}")
        z.writestr("INDICE.md", "\n".join(indice) + "\n")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="skills-{SLUG_ATIVO}.zip"'})


@app.get("/unidades/{uid}/ficha", response_class=HTMLResponse)
def ficha_unidade(req: Request, uid: str, vista: str = "canvas",
                  contexto: str = "") -> HTMLResponse:
    """Ficha COMPLETA do colaborador, em MODAL: todos os campos editáveis num só
    lugar (estilo ficha) + os vínculos dele no sistema (reporte, subárvore, tempo
    de casa e atalhos para Skills/Conversa de Valor/Talentos/Avaliação Mestre). Salva pela mesma rota do painel
    (/unidades/{uid}/salvar), então a edição reflete em todo o sistema."""
    uni = universo_visivel()
    universo = ESTADO.unidades if uni is None else uni
    u = universo.get(uid)                   # fora do escopo => não abre a ficha
    if u is None:
        return HTMLResponse(alerta(T("Unidade não encontrada.")))
    filhos = mapa_filhos(universo)
    prof = profundidades(ESTADO.unidades)
    return HTMLResponse(render(
        "_unidade_ficha.html", request=req, u=u,
        vista_origem=vista, contexto_origem=contexto, oob=(vista == "canvas"),
        pode_editar=negado(NIVEL_EDITOR, uid) is None,
        u_nivel=prof.get(uid, 0),
        pai=universo.get(u.parent_id) if u.parent_id else None,   # só se no escopo
        n_filhos=len(filhos.get(uid, [])),
        n_descendentes=len(descendentes(universo, uid)),
        trilha=[a for a in ancestrais(ESTADO.unidades, uid) if a.id in universo],
        centros=[c for c in ESTADO.config.centros_custo if c.get("ativo", True)],
        cargos_conhecidos=sorted({c["cargo"] for c in ESTADO.config.catalogo_cargos},
                                 key=sem_acento),
        nivel_do_cargo=(cargosmod.classificar(u.cargo, ESTADO.config.indice_cargos,
                                              ESTADO.config.regras_cargo)
                        if u.cargo else ""),
        destinos=sorted(
            (x for x in universo.values()
             if x.id != uid and x.id not in descendentes(universo, uid)),
            key=lambda x: (prof.get(x.id, 0), sem_acento(x.nome))),
        texto="\n".join(("> " if r.get("origem") == "delegada" else "")
                        + r.get("descricao", "") for r in u.responsabilidades),
        skills=", ".join(u.competencias),
        status_opcoes=dominio.STATUS, hoje_iso=date.today().isoformat(),
        anos_de_casa=dominio.tempo_de_casa(u.data_inicio),
        idade=dominio.tempo_de_casa(u.data_nascimento),   # mesma régua, sobre o nascimento
        rotulo_faixa=dict((c, r) for c, r, _p in dominio.FAIXAS_CASA).get(
            dominio.faixa_de_casa(dominio.tempo_de_casa(u.data_inicio)), ""),
        # "Vincular ao sistema" (print 1): as opções de BU/CC_Equipe/N2/N4/N5 são
        # os valores que JÁ existem nos nós — quanto mais preenchido, mais rica a
        # lista. Autocomplete, não domínio fechado.
        opcoes_org={c: sorted({getattr(x, c) for x in universo.values()
                               if getattr(x, c, "")})
                    for c in ("bu", "cc_equipe", "n2", "n4", "n5",
                              "categoria_nivel")},
        modulos_vinculo=[m for m in MODULOS
                         if m[0] in ("dcr", "cgv", "talentos", "gptw", "tempo")],
        # Chaves para os atalhos de módulo abrirem a ficha DESTA pessoa em modal.
        # O Skills agrega por FUNÇÃO (cargo sem acento/caixa) e o Jinja não tem
        # `sem_acento`, então a chave sai pronta daqui. Conversa de Valor e Talentos abrem por
        # matrícula (código), com o mesmo fallback `u:{id}` das listas deles.
        skills_cargo=resumo_skills(u),
        dcr_chave=dcrmod.chave_funcao(u.cargo or ""),
        ref=((u.codigo or "").strip() or f"u:{u.id}")))


def resposta_de_mutacao(req: Request, uid: str, vista: str,
                        contexto: str) -> HTMLResponse:
    """Devolve a tela de onde a gaveta foi aberta.

    No canvas o desenho e o alvo e o painel vai fora de banda. Nas demais
    vistas nao existe `#canvas`: o painel vira o alvo e quem vai fora de banda
    e a lista, senao um nome recem-editado continua velho na tela.
    """
    if vista == "canvas":
        return canvas(req, oob_painel(req, uid))

    painel = corpo_painel(req, uid, com_canvas=False, vista_origem=vista,
                          contexto_origem=contexto)
    if vista == "tabela":
        return HTMLResponse(painel + f'<div id="tabelaCorpo" hx-swap-oob="true">'
                            f'{render("_tabela_corpo.html", request=req, vista="tabela", **contexto_tabela())}</div>')
    if vista == "estrutura":
        p = dict(parse_qsl(contexto))
        corpo = html_vista(req, "estrutura", banda=p.get("banda", ""),
                           vertical=p.get("vertical", ""),
                           departamento=p.get("departamento", ""))
        # A secao ja carrega id="estruturaRaiz"; o atributo entra por injecao.
        corpo = corpo.replace('<section id="estruturaRaiz"',
                              '<section id="estruturaRaiz" hx-swap-oob="true"', 1)
        return HTMLResponse(painel + corpo)
    return HTMLResponse(painel)


def oob_historico(req: Request) -> str:
    """Desfazer/Refazer voltam fora de banda: eles vivem na barra, fora do
    `#canvas`, e o contrato INT-01 nao deixa um fragmento do canvas alvejar
    outra coisa. Sem isto, o botao continuaria clicavel depois de esvaziar a
    pilha."""
    return render("_bt_historico.html", request=req, oob=True)


def oob_chips(req: Request) -> str:
    """Os oito criterios voltam fora de banda depois de cada filtragem.

    Eles se filtram uns aos outros: escolhida a vertical ENG, `Departamento`
    passa a listar so os departamentos de ENG. Dominio que estreita no servidor
    e nao estreita na tela e pior do que nao estreitar — a lista continuaria
    oferecendo o que ja nao devolve ninguem.

    Junto vao as pilulas do que esta filtrando agora: as duas coisas descrevem
    o mesmo estado, e voltar uma sem a outra deixaria a tela contando duas
    historias.

    A busca livre fica de fora de proposito: ela guarda o cursor de quem esta
    digitando, e trocar o campo a cada tecla roubaria o foco.
    """
    ctx = contexto_filtros()
    return (render("_filtros_chips.html", request=req, oob=True, **ctx)
            + render("_filtros_ativos.html", request=req, oob=True, **ctx))


def oob_controles(req: Request) -> str:
    """Tudo o que descreve o desenho e vive fora do `#canvas`.

    Desfazer e refazer trocam o estado inteiro — orientacao, agrupamento, niveis
    marcados e filtros voltam ao que eram. Mandando so o desenho, a barra ficava
    descrevendo um modo que o servidor ja nao tem, e o clique seguinte ia para o
    lado errado: o botao dizia "Por equipe" com o canvas por pessoa.
    """
    return (oob_orientacao(req)
            + render("_bt_agrupamento.html", request=req, oob=True)
            + render("_niveis.html", request=req, oob=True,
                     profundidade_max=max(profundidades(desenho_atual()).values()))
            + oob_chips(req)
            + oob_exportar(req))


def oob_exportar(req: Request) -> str:
    """A escala do PDF muda com o desenho, e ela e a unica coisa no botao que
    diz se o papel sai legivel. Trocar de eixo leva a escala de 2 % a 100 %:
    deixar o rotulo velho ali e mentir no ponto da decisao."""
    return render("_bt_exportar.html", request=req, oob=True,
                  escala_pdf=escala_impressao())


def oob_orientacao(req: Request) -> str:
    """Os botoes de orientacao voltam fora de banda, como o agrupamento e o
    historico: eles descrevem o modo vigente e vivem na barra, fora do
    `#canvas`. Sem isto, clicar em "Lateral" redesenhava o organograma e
    deixava o botao apagado — a tela mostrando uma coisa e o controle outra."""
    return render("_bt_orientacao.html", request=req, oob=True)


def oob_painel(req: Request, uid: str | None) -> str:
    """INT-02: painel acompanha a mutacao por out-of-band, nunca por 2a requisicao."""
    corpo = (render("_painel_vazio.html", request=req) if uid is None
             else corpo_painel(req, uid, com_canvas=False))
    return (f'<aside id="painel" class="painel" aria-label="Detalhes da unidade" '
            f'hx-swap-oob="true">{corpo}</aside>')


# --- pagina e vistas ------------------------------------------------------
def contexto_tempo() -> dict:
    """Os indicadores de tempo de empresa, sobre o RECORTE vigente.

    O filtro vale aqui como vale no canvas: um indicador que ignora o recorte
    responde outra pergunta que a que a pessoa acabou de fazer — ela filtrou
    F&B e quer a média de F&B, não a da empresa.

    A visão por equipe fica de fora de propósito: o time é um nó derivado, sem
    data de admissão, e "tempo de casa de um time" não é coisa que exista.

    **Aqui o recorte é o dos ACHADOS, e não o do desenho.** O canvas e a tabela
    trabalham com `visao()`, que junta aos achados os ancestrais deles: sem o
    caminho até a raiz não há árvore para desenhar nem indentação para mostrar.
    Um relatório não tem esse problema e não pode pagar esse preço — filtrando
    Vínculo = CLT, os ancestrais traziam 30 prestadores para dentro da conta, e
    a tabela "Por vínculo" respondia `Prestador (PJ) 30` embaixo de um filtro
    que dizia CLT. Quem filtra CLT quer a média de CLT.
    """
    fonte = fonte_visivel()
    p = tempomod.panorama(fonte, rotulos_nivel=ESTADO.config.rotulos_nivel)
    return {**p, "r": p["resumo"], "piso_grupo": tempomod.PISO_GRUPO,
            **contexto_filtros()}


def contexto_tabela() -> dict:
    # INT-03: quem pode carregar planilha chega decidido do servidor. O botão
    # de importar não some para quem não pode — nasce desabilitado com o motivo
    # no título, senão a diferença entre "não existe" e "não é para você" fica
    # por conta de adivinhação.
    return {"linhas": linhas_tabela(), "selecionado": ESTADO.selecionado,
            "niveis": ESTADO.config.niveis,
            "profundidade_max": profundidade_max_visivel(),
            "motivo_carga": negado(NIVEL_ADMIN) or "",
            "motivo_edicao": negado(NIVEL_EDITOR) or "",
            "colunas": colunas_da_tabela(),
            "col": {c["chave"] for c in colunas_da_tabela() if c["on"]},
            "status_rotulos": dominio.STATUS,
            **contexto_filtros()}


def corpo_tabela(req: Request) -> HTMLResponse:
    return HTMLResponse(render("_tabela_corpo.html", request=req, vista="tabela",
                               **contexto_tabela()))


def corpo_tempo(req: Request) -> HTMLResponse:
    """Só o relatório de tempo de casa — a barra de filtros fica onde está."""
    return HTMLResponse(render("_tempo_corpo.html", request=req, vista="tempo",
                               **contexto_tempo()))


# As abas do módulo Skills. Uma constante, e não literais espalhados: a rota valida
# contra ela, o template desenha a partir dela, e aba nova entra num lugar só.
SECOES_DCR = ("funcoes", "correlacoes", "lideranca", "competencias")


def contexto_dcr(secao: str = "funcoes") -> dict:
    """O Skills sobre o RECORTE vigente, como a vista de tempo de empresa.

    O filtro vale aqui pelo mesmo motivo de lá: quem filtrou F&B quer a matriz
    de F&B. E pelo mesmo motivo de lá o recorte é o dos ACHADOS, e não o do
    desenho — juntar os ancestrais traria gerentes de fora do filtro para dentro
    da contagem de liderança, que é justamente o número que a tela publica.
    """
    fonte = fonte_visivel()
    p = dcrmod.panorama(fonte, mapa_cc(), registros_dcr(),
                        ESTADO.config.rotulos_nivel)
    return {**p, "r": p["resumo"], "secao": secao,
            "formulario": dcrmod.FORMULARIO,
            "motivo_edicao": negado(NIVEL_EDITOR) or "",
            **contexto_filtros()}


def corpo_dcr(req: Request) -> HTMLResponse:
    """Só o corpo do Skills — a barra de filtros fica onde está."""
    return HTMLResponse(render("_dcr_corpo.html", request=req, vista="dcr",
                               **contexto_dcr()))


# As abas do módulo Conversa de Valor, na ordem da pergunta que cada uma responde: quem
# conversa com quem, quanto já andou, o que o processo pede, e onde estão as
# ferramentas. Constante, e não literais: a rota valida contra ela.
SECOES_CGV = ("agenda", "cobertura", "referencia", "ferramentas")


def ano_cgv() -> int:
    """O ano-referência do processo. Vem do relógio: a Conversa de Valor é anual, e a agenda
    aberta em 2027 é a de 2027 — não a que ficou congelada num literal."""
    return datetime.now(timezone.utc).year


def registros_cgv() -> list[dict]:
    """O acompanhamento vivo, fundido com o histórico durável do banco.

    O overlay do `estado.json` é o que se edita nesta sessão; o Postgres guarda
    os anos que o estado corrente já não carrega. `fundir` junta os dois sem
    duplicar, o overlay vencendo no conflito de mesma chave — é o que o operador
    acabou de gravar, ainda não necessariamente espelhado.
    """
    do_banco = cgvmod.carregar_do_banco(SLUG_ATIVO) if cgvmod.banco_pronto() else []
    return cgvmod.fundir(ESTADO.config.cgv_registros, do_banco)


def registros_dcr() -> list[dict]:
    """A descrição de cargo viva, fundida com a durável do banco. Mesma lógica do
    Conversa de Valor: overlay do estado + Postgres, o overlay vencendo no conflito."""
    do_banco = dcrmod.carregar_do_banco(SLUG_ATIVO) if dcrmod.banco_pronto() else []
    return dcrmod.fundir(ESTADO.config.dcr_cargos, do_banco)


def contexto_cgv(secao: str = "agenda") -> dict:
    """A Conversa de Valor sobre o RECORTE vigente, como o Skills e Tempo de empresa.

    O filtro vale aqui pelo mesmo motivo de lá: quem filtrou F&B quer a agenda
    de F&B. O recorte é o dos ACHADOS, e não o do desenho — juntar ancestrais
    traria líderes de fora do filtro para dentro da cobertura publicada.
    """
    fonte = fonte_visivel()
    p = cgvmod.panorama(fonte, mapa_cc(), registros_cgv(), ano_cgv())
    return {**p, "r": p["resumo"], "secao": secao,
            "fonte_banco": cgvmod.banco_pronto(),
            "motivo_edicao": negado(NIVEL_EDITOR) or "",
            **contexto_filtros()}


def corpo_cgv(req: Request) -> HTMLResponse:
    """Só o corpo da Conversa de Valor — a barra de filtros fica onde está."""
    return HTMLResponse(render("_cgv_corpo.html", request=req, vista="cgv",
                               **contexto_cgv()))


# --- One-on-One (1:1 / PRM) ---------------------------------------------------
# As abas do módulo: a agenda de 1:1, e o painel do PRM (Escuta Ativa, burnout,
# ciclo de vida). O desenvolvimento (rocks/issues/carreira) vive na ficha de cada
# pessoa, atrás do sigilo — não é uma vista de lista.
SECOES_ONEBYONE = ("agenda", "prm")


def _filhos_por() -> dict:
    """node_id do gestor -> ids dos liderados diretos, para medir o span (um dos
    sinais de burnout)."""
    f: dict = {}
    for u in ESTADO.unidades.values():
        f.setdefault(u.parent_id, []).append(u.id)
    return f


def identidade_1a1() -> tuple[str | None, str, bool]:
    """Quem está lendo: (nó, matrícula, é RH/compliance). A matrícula casa com
    `ref`/`lider_ref` no sigilo; `ver_1a1_rh` libera a leitura de todos os 1:1."""
    cfg = acesso_vigente()
    eu_id = cfg.usuario_id
    return eu_id, obomod.matricula_do_no(ESTADO.unidades, eu_id), bool(cfg.ver_1a1_rh)


def registros_onebyone() -> list[dict]:
    """O overlay vivo fundido com o histórico durável do banco (overlay vence)."""
    do_banco = obomod.carregar_do_banco(SLUG_ATIVO) if obomod.banco_pronto() else []
    return obomod.fundir(ESTADO.config.onebyone, do_banco)


def onebyone_visivel() -> list[dict]:
    """TODA leitura do módulo passa por aqui: o registro filtrado pelo sigilo —
    só participantes (líder/liderado) ou RH. Nunca ler `registros_onebyone` cru."""
    _eid, mat, rh = identidade_1a1()
    return obomod.visiveis(registros_onebyone(), mat, rh)


def _lider_ref_de(ref: str, base: list[dict]) -> str:
    """A matrícula do líder de uma pessoa (o outro participante do 1:1): o `codigo`
    do nó pai. É snapshot no registro para o sigilo sobreviver a troca de gestor."""
    porref = {obomod.ref_de(l): l for l in base}
    l = porref.get(ref)
    pai = ESTADO.unidades.get(l.get("parent_id")) if l else None
    return (str(pai.codigo).strip()[:60] if pai and pai.codigo else "")


def contexto_onebyone(secao: str = "agenda") -> dict:
    """A agenda de 1:1 de quem está logado (liderados diretos), ou toda a base
    visível para RH/admin. O conteúdo dos 1:1 já vem filtrado pelo sigilo."""
    eu_id, mat, rh = identidade_1a1()
    base = obomod.base(fonte_visivel(), mapa_cc())
    visivel = obomod.visiveis(registros_onebyone(), mat, rh)
    roster = base if rh else obomod.equipe_de(base, eu_id)
    ag = obomod.agenda(roster, visivel)
    secao = secao if secao in SECOES_ONEBYONE else "agenda"
    prm = obomod.panorama_prm(roster, visivel, _filhos_por()) if secao == "prm" else {}
    return {"secao": secao, "agenda": ag, "resumo": obomod.resumo_agenda(ag),
            "prm": prm, "eu_matricula": mat, "sou_rh": rh, "tem_equipe": bool(roster),
            "cadencias": obomod.CADENCIAS, "rotulo_cadencia": obomod.ROTULO_CADENCIA,
            "hoje": date.today().isoformat(),
            "fonte_banco": obomod.banco_pronto(),
            "motivo_edicao": negado(NIVEL_EDITOR) or "", **contexto_filtros()}


def corpo_onebyone(req: Request) -> HTMLResponse:
    return HTMLResponse(render("_onebyone_corpo.html", request=req, vista="onebyone",
                               **contexto_onebyone()))


# As abas da Avaliação, na ordem da pergunta que cada uma responde: onde
# está cada um no 9-box, a lista para abrir a ficha, quem está pronto para
# suceder, e os indicados ao Comitê de Meritocracia. Constante — a rota valida.
SECOES_TALENTOS = ("mapa", "lista", "prontidao", "comite")


def ano_talentos() -> int:
    """O ano-referência do Mapa. Vem do relógio, como o da Conversa de Valor: o Mapa é anual e
    a leitura de 2027 é a de 2027, não um literal congelado."""
    return datetime.now(timezone.utc).year


def registros_talentos() -> list[dict]:
    """O Mapa vivo, fundido com o durável do banco. Mesma lógica da Conversa de Valor: overlay
    do estado + Postgres, o overlay vencendo no conflito de mesma chave."""
    do_banco = (talentosmod.carregar_do_banco(SLUG_ATIVO)
                if talentosmod.banco_pronto() else [])
    return talentosmod.fundir(ESTADO.config.mapa_talentos, do_banco)


def contexto_talentos(secao: str = "mapa") -> dict:
    """O Mapa sobre o RECORTE vigente, como o Skills, Tempo e Conversa de Valor. Quem filtrou uma
    vertical quer o 9-box daquela vertical, não o da empresa inteira."""
    fonte = fonte_visivel()
    p = talentosmod.panorama(fonte, mapa_cc(), registros_talentos(),
                             ano_talentos())
    # A cobertura de Conversa de Valor por pessoa alimenta o Comitê (INT-2): quem é indicado
    # cruzado com quem já teve a conversa. Um dicionário ref -> realizadas.
    cgv_ag = cgvmod.agenda(p["linhas"], registros_cgv(), ano_talentos())
    cobertura_cgv = {a["ref"]: a["realizadas"] for a in cgv_ag}
    return {**p, "r": p["resumo"], "secao": secao,
            "cobertura_cgv": cobertura_cgv,
            "fonte_banco": talentosmod.banco_pronto(),
            "motivo_edicao": negado(NIVEL_EDITOR) or "",
            **contexto_filtros()}


def corpo_talentos(req: Request) -> HTMLResponse:
    """Só o corpo do Mapa — a barra de filtros fica onde está."""
    return HTMLResponse(render("_talentos_corpo.html", request=req,
                               vista="talentos", **contexto_talentos()))


# As abas do Peoples Place to Work, na ordem da pergunta: o retrato (PTI, maturidade,
# participação), os cinco pilares, os segmentos (com o piso de 5), a devolutiva
# (KPIs e plano de ação), o próprio questionário e a referência do método.
SECOES_GPTW = ("painel", "pilares", "segmentos", "devolutiva", "responder",
               "programar", "referencia")


def ano_gptw() -> int:
    """O ano-referência da pesquisa. Vem do relógio, como o da Conversa de Valor e do Mapa."""
    return datetime.now(timezone.utc).year


def respostas_gptw() -> list[dict]:
    """As respostas vivas, fundidas com as duráveis do banco. Sem contar em
    dobro: a resposta espelhada no Postgres não reaparece pelo overlay."""
    do_banco = (gptwmod.carregar_do_banco(SLUG_ATIVO)
                if gptwmod.banco_pronto() else [])
    return gptwmod.fundir(ESTADO.config.gptw_respostas, do_banco)


def _estrato_do_respondente() -> dict:
    """O estrato de quem está logado, derivado do organograma — o que se grava
    com a resposta, no lugar da identidade. Sem usuário definido, vazio: a
    resposta ainda vale, entra no estrato «não informado»."""
    unidade = ESTADO.unidades.get(acesso_vigente().usuario_id or "")
    return gptwmod.estrato_de(unidade)


def contexto_gptw(secao: str = "painel", ciclo: str = "") -> dict:
    """A Avaliação Mestre sobre a empresa inteira: a pesquisa é da casa, e a segmentação —
    não o filtro do topo — é como se recorta o clima, respeitando o piso de 5."""
    ciclo = ciclo if ciclo in gptwmod.ROTULO_CICLO else gptwmod.CICLO_PADRAO
    p = gptwmod.panorama(ESTADO.unidades, respostas_gptw(), ano_gptw(), ciclo)
    return {**p, "secao": secao, "fonte_banco": gptwmod.banco_pronto(),
            "afirmacoes": gptwmod.afirmacoes_do_ciclo(ciclo),
            "todas_afirmacoes": gptwmod.AFIRMACOES,
            "maturidades": gptwmod.MATURIDADE,
            "programacao": ESTADO.config.gptw_programacao,
            "com_email": len(gptwmod.destinatarios(ESTADO.unidades)),
            "motivo_edicao": negado(NIVEL_EDITOR) or "",
            "rot_pilar": gptwmod.ROTULO_PILAR,
            "rot_likert": gptwmod.ROTULO_LIKERT,
            "por_afirmacao": gptwmod.por_afirmacao(p["respostas"]),
            "estrato": _estrato_do_respondente(),
            "cobertura_cgv": _cobertura_cgv_gptw(),
            "tempo": _tempo_gptw()}


def _cobertura_cgv_gptw() -> dict:
    """A cobertura de Conversa de Valor do ciclo — o KPI que a §7 do spec manda ler da própria
    vista Conversa de Valor, sem coleta nova (integração §8.4)."""
    linhas = dcrmod.medir(ESTADO.unidades, mapa_cc())
    ag = cgvmod.agenda(linhas, registros_cgv(), ano_cgv())
    r = cgvmod.resumo(ag)
    return {"pct": r["pct"], "realizadas": r["realizadas"], "previstas": r["previstas"]}


def _tempo_gptw() -> dict:
    """Tempo médio de casa e faixas — o KPI que a §7 manda ler do módulo Tempo,
    sem coleta nova (integração §8.4)."""
    linhas = tempomod.medir(ESTADO.unidades)
    r = tempomod.resumo(linhas)
    return {"media": r["media"], "faixas": tempomod.por_faixa(linhas)}


TODAS_AS_FAIXAS = "*"


def contexto_estrutura(banda: str, vert: str, departamento: str,
                       conferir: bool) -> dict:
    """Tudo derivado dos parametros: a vista de estrutura nao guarda estado.

    O que o operador escolheu viaja na URL, entao a tela e compartilhavel por
    link e duas abas abertas nao brigam por um `selecionado` no servidor.
    """
    mapa = mapa_cc()
    uni = universo_visivel() or ESTADO.unidades   # estrutura recortada ao escopo
    faixas = estruturamod.funil(uni, mapa)
    validas = {f["chave"] for f in faixas if f["chips"]}
    # `*` abre as quatro faixas de uma vez. Continua sendo estado de URL, e nao
    # do servidor: o link de "tudo aberto" e compartilhavel como qualquer outro.
    banda = banda if banda in validas or banda == TODAS_AS_FAIXAS else ""

    v = None
    if banda and vert:
        # Com todas abertas, a vertical pode estar em qualquer faixa — procurar
        # so na faixa escolhida fecharia as outras ao clicar num chip.
        siglas = {c["sigla"] for f in faixas
                  if banda in (TODAS_AS_FAIXAS, f["chave"]) for c in f["chips"]}
        if vert in siglas:
            v = estruturamod.vertical(uni, mapa, vert,
                                      ESTADO.config.idioma)

    gente, rotulo_dep = [], ""
    if v and departamento:
        alvo = next((d for d in v["departamentos"]
                     if d["departamento"] == departamento), None)
        if alvo:
            gente = estruturamod.pessoas(uni, mapa, v["sigla"],
                                         departamento)
            rotulo_dep = alvo["rotulo"]
        else:
            departamento = ""

    consulta = "&".join(f"{k}={quote(x)}" for k, x in
                        (("banda", banda), ("vertical", v["sigla"] if v else ""),
                         ("departamento", departamento)) if x)
    return {"faixas": faixas, "banda": banda, "vert": v,
            "todas_faixas": TODAS_AS_FAIXAS,
            "tudo_aberto": banda == TODAS_AS_FAIXAS,
            "departamento": departamento, "pessoas": gente,
            "rotulo_dep": rotulo_dep, "conferir": conferir, "consulta": consulta,
            "divergencias": estruturamod.divergencias(
                uni, mapa, ESTADO.config.idioma)}


def _cobertura_n5(fonte: dict, mapa: dict) -> dict:
    """Estado do vínculo N5 ↔ CC: quantos têm N5 resolvível pelo centro de custo e
    quantos já estão gravados — é o que o botão de sincronizar precisa mostrar."""
    resolviveis = sum(1 for uid in fonte if (mapa.get(uid) or {}).get("n5"))
    preenchidos = sum(1 for u in fonte.values() if u.n5)
    return {"resolviveis": resolviveis, "preenchidos": preenchidos,
            "total": len(fonte), "pendentes": resolviveis - preenchidos}


def contexto_painel_rh() -> dict:
    """O Painel de RH sobre o UNIVERSO visível (respeita o escopo de leitura): um
    gerente vê os indicadores do seu recorte; o RH, com escopo total, vê a casa."""
    fonte = universo_visivel() or ESTADO.unidades
    log = [e for e in ESTADO.acessos_log if e.get("usuario_id") in fonte]
    return {
        "kpis": painelmod.kpis(fonte),
        "dist": painelmod.distribuicoes(fonte, ESTADO.config.rotulos_nivel,
                                        ESTADO.config.niveis),
        "contratacoes": painelmod.ultimas_contratacoes(fonte),
        "n_contratacoes_mes": len(painelmod.contratacoes_do_mes(fonte)),
        "mov": painelmod.movimentacao(log, fonte),
        "desligamentos": painelmod.desligamentos(fonte),
        "crescimento": painelmod.crescimento(fonte),
        "cobertura_n5": _cobertura_n5(fonte, mapa_cc()),
        "pode_admin": negado(NIVEL_ADMIN) is None,
        "hoje": date.today().strftime("%d/%m/%Y"),
    }


def html_vista(req: Request, vista: str, aba: str = "geral", **extra) -> str:
    # Guarda de módulo (Fase D): a mesma regra que esconde a aba barra a entrada
    # pela URL. Só vale para os módulos com visibilidade; vistas de apoio (maria)
    # passam. Admin e lista vazia veem tudo.
    if vista in MODULOS_CHAVES and not modulo_visivel(vista):
        return alerta(T("Módulo indisponível para o seu acesso."))
    if vista == "painel_rh":
        return render("_painel_rh.html", request=req, vista="painel_rh",
                      **contexto_painel_rh())
    if vista == "estrutura":
        return render("_estrutura.html", request=req, vista="estrutura",
                      **contexto_estrutura(extra.get("banda", ""),
                                           extra.get("vertical", ""),
                                           extra.get("departamento", ""),
                                           extra.get("conferir", False)))
    if vista == "maria":
        return render("_maria.html", request=req, vista="maria",
                      maria=contexto_maria())
    if vista == "tabela":
        return render("_tabela.html", request=req, vista="tabela",
                      **contexto_tabela())
    if vista == "tempo":
        return render("_tempo.html", request=req, vista="tempo",
                      **contexto_tempo())
    if vista == "dcr":
        return render("_dcr.html", request=req, vista="dcr",
                      **contexto_dcr(aba if aba in SECOES_DCR else "funcoes"))
    if vista == "cgv":
        return render("_cgv.html", request=req, vista="cgv",
                      **contexto_cgv(aba if aba in SECOES_CGV else "agenda"))
    if vista == "talentos":
        return render("_talentos.html", request=req, vista="talentos",
                      **contexto_talentos(aba if aba in SECOES_TALENTOS else "mapa"))
    if vista == "onebyone":
        return render("_onebyone.html", request=req, vista="onebyone",
                      **contexto_onebyone(aba if aba in SECOES_ONEBYONE else "agenda"))
    if vista == "gptw":
        return render("_gptw.html", request=req, vista="gptw",
                      **contexto_gptw(aba if aba in SECOES_GPTW else "painel",
                                      extra.get("ciclo", "")))
    if vista == "auditoria":
        # A auditoria virou aba de Configurações. O caminho antigo continua
        # respondendo — link guardado por alguém não pode virar 404 —, mas
        # renderiza a mesma aba, e não uma segunda cópia da tela.
        return render("_config.html", request=req, **contexto_config("auditoria"))
    if vista == "configuracoes":
        return render("_config.html", request=req, **contexto_config(aba))
    # `profundidade_max` sai do desenho vigente, não de `ESTADO.unidades`: por
    # equipe a árvore tem outra altura, e oferecer um N que não existe daria um
    # botão que não muda nada.
    return render("_vista_canvas.html", request=req, vista="canvas",
                  layout=layout_atual(),
                  profundidade_max=max(profundidades(desenho_atual()).values()),
                  **contexto_filtros())


# ---------------------------------------------------------------------------
# PAINEL RH — corpo, sincronização de N5 e exportação
# ---------------------------------------------------------------------------
@app.get("/painel-rh/corpo", response_class=HTMLResponse)
def painel_corpo(req: Request):
    return HTMLResponse(render("_painel_rh_corpo.html", request=req, vista="painel_rh",
                               **contexto_painel_rh()))


# Rótulos das dimensões para o título do modal — o que a barra clicada representa.
_RH_DIM_ROT = {
    "vinculo": "Tipo de vínculo", "nivel": "Nível", "departamento": "Departamento",
    "vertical": "Vertical", "tempo_casa": "Tempo de casa", "admissao_ano": "Admissões em",
    "desligamentos": "Desligamentos", "contratacoes_mes": "Contratações do mês",
}


@app.get("/painel-rh/lista", response_class=HTMLResponse)
def painel_lista(req: Request, dim: str = "", chave: str = "", rotulo: str = ""):
    """As pessoas por trás de um número do painel — a lista da fatia clicada, em
    modal. Respeita o escopo de leitura (o mesmo universo do painel)."""
    fonte = universo_visivel() or ESTADO.unidades
    if dim == "desligamentos":
        itens = painelmod.desligamentos(fonte)
    elif dim == "contratacoes_mes":
        itens = painelmod.contratacoes_do_mes(fonte)
    else:
        itens = painelmod.colaboradores_por(fonte, dim, chave)
    titulo = _RH_DIM_ROT.get(dim, dim)
    return HTMLResponse(render("_painel_rh_lista.html", request=req,
                               itens=itens, titulo=T(titulo),
                               fatia=(rotulo or chave), total=len(itens)))


@app.post("/painel-rh/sincronizar-n5", response_class=HTMLResponse)
def painel_sincronizar_n5(req: Request):
    """Preenche o N5 dos colaboradores a partir do vínculo com o cadastro de CC —
    é o que faz o recorte 'por vertical/N5' deixar de dar em nada. Só Admin."""
    if (m := negado(NIVEL_ADMIN)):
        return HTMLResponse(alerta(m))
    r = painelmod.sincronizar_n5(ESTADO.unidades, mapa_cc())
    if r["atualizados"]:
        commit("alterar", "-", "N5 vinculado ao centro de custo", r)
    corpo = render("_painel_rh_corpo.html", request=req, vista="painel_rh",
                   **contexto_painel_rh())
    return HTMLResponse(corpo + alerta(T(
        "N5 vinculado ao CC: {n} colaborador(es) atualizado(s), {ok} já corretos, "
        "{sc} sem CC resolvível.", n=r["atualizados"], ok=r["ja_corretos"], sc=r["sem_cc"])))


@app.get("/painel-rh/export.xlsx")
def painel_export_xlsx(req: Request):
    """Exporta todas as tabelas + o Painel RH num XLSX. Dump completo do estado —
    só Admin, como o export.json."""
    if (m := negado(NIVEL_ADMIN)):
        return HTMLResponse(alerta(m))
    from . import exportador_rh
    dados = exportador_rh.gerar(json.loads(serializar()), mapa_cc())
    registrar("alterar", "-", "exportação Painel RH (XLSX)",
              {"formato": "xlsx", "bytes": len(dados)})
    gravar()
    return Response(dados,
                    media_type="application/vnd.openxmlformats-officedocument."
                               "spreadsheetml.sheet",
                    headers={"Content-Disposition":
                             'attachment; filename="GPLANSIS_ORG_painel_RH.xlsx"'})


# --- acesso -----------------------------------------------------------------
LIVRES = ("/login", "/entrar", "/sair", "/marca", "/vendor", "/estatico",
          "/favicon.ico", "/manifest.webmanifest")
# A raiz e livre, e por IGUALDADE EXATA — nunca dentro de `LIVRES`, que e
# testado com `startswith`: "/" ali liberaria o sistema INTEIRO em silencio.
# Sem sessao ela serve a apresentacao publica; com sessao, o aplicativo.
LIVRE_EXATO = ("/",)
# A API do lakehouse é máquina-a-máquina: quem chega com um token de serviço
# válido não passa pela porta de login (não há navegador do outro lado). Sem
# token, ela cai na guarda normal e exige sessão como qualquer outra rota.
LIVRE_COM_TOKEN = "/api/v1/lake"


@app.middleware("http")
async def guarda_de_acesso(req: Request, chamar):
    """Fecha o sistema quando ORG_EXIGIR_LOGIN=1.

    Middleware, e não decorador rota a rota: rota nova nasce protegida por
    omissão. O contrário — proteger uma a uma — falha em silêncio no dia em que
    alguém esquecer, e é justamente o dia que importa.
    """
    esquecer_equipes()          # nenhuma requisição herda o desenho da anterior
    if not acesso.exigir_login() or req.url.path.startswith(LIVRES):
        return await chamar(req)
    if req.url.path.startswith(LIVRE_COM_TOKEN) and lakemod.token_valido(
            (req.headers.get("authorization") or "").removeprefix("Bearer ").strip()):
        return await chamar(req)
    carga = sessao_atual(req)
    if carga:
        # Senha temporária (dada pelo administrador): a pessoa entra, mas só
        # para escolher a própria senha — até lá, toda rota leva a /senha.
        if (not req.url.path.startswith(("/senha", "/sair"))
                and usuariosmod.precisa_trocar(carga.get("sub", ""))):
            if req.headers.get("HX-Request"):
                return Response(status_code=401, headers={"HX-Redirect": "/senha"})
            return RedirectResponse("/senha", status_code=303)
        return await chamar(req)
    # Sem sessão, e SÓ aqui, a raiz passa: ela serve a apresentação pública.
    #
    # A posição é o ponto. Liberar `/` no topo da guarda — que foi a primeira
    # versão disto — passa por cima da regra da senha temporária: quem recebe
    # senha do administrador tem de ser levado a /senha em qualquer rota até
    # escolher a própria, e a raiz liberada antes da verificação de sessão
    # abriria o aplicativo direto.
    if req.url.path in LIVRE_EXATO and not req.headers.get("HX-Request"):
        return await chamar(req)
    if req.headers.get("HX-Request"):
        # Fragmento htmx não pode redirecionar sozinho: o navegador trocaria um
        # pedaço da tela pela página de login inteira.
        return Response(status_code=401, headers={"HX-Redirect": "/login"})
    return RedirectResponse("/login", status_code=303)


# --- cabeçalhos de segurança e CSRF -----------------------------------------
# CSP do aplicativo: script só do próprio site (htmx, AG Grid, /estatico) ou com
# o nonce desta resposta (os <script> do base.html). Nada de 'unsafe-inline' nem
# 'unsafe-eval' em script: os manipuladores inline viraram `data-on-*`
# (web/estatico/csp.js) e o htmx roda com `allowEval: false`. Estilo continua com
# 'unsafe-inline' — o AG Grid injeta estilo e os templates usam `style=` — e
# estilo não executa código. `frame-ancestors` é reescrito pelo Caddy (embed_os)
# para incluir o GPlanSiS|OS.
_NONCE: ContextVar = ContextVar("csp_nonce", default="")
CSP_APP = ("default-src 'self'; script-src 'self' 'nonce-{nonce}'; "
           "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
           "font-src 'self' data:; connect-src 'self'; object-src 'none'; "
           "base-uri 'self'; form-action 'self'; frame-ancestors 'self'")
# Páginas estáticas de apresentação (landing, manuais, histórias): arquivos do
# próprio repositório, sem dado de usuário, com script/estilo inline e fontes do
# Google. Ficam com CSP própria, ainda sem eval e sem objeto.
CSP_ESTATICA = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "img-src 'self' data: blob: https:; connect-src 'self'; "
                "object-src 'none'; base-uri 'self'; form-action 'self'; "
                "frame-ancestors 'self'")
METODOS_INSEGUROS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def pagina_estatica(texto: str) -> HTMLResponse:
    return HTMLResponse(texto, headers={"Content-Security-Policy": CSP_ESTATICA})


def _origem_confiavel(req: Request) -> bool:
    """POST/PUT/PATCH/DELETE só da própria origem. O navegador manda `Origin` em
    toda requisição que muda estado; sem ela, vale o `Referer`; sem nenhum dos
    dois (cliente de linha de comando, testes), passa — o SameSite=Lax do cookie
    segue valendo. Origem de outro site = CSRF, recusado."""
    origem = req.headers.get("origin")
    if not origem or origem == "null":
        ref = req.headers.get("referer")
        if not ref:
            return origem != "null"
        from urllib.parse import urlsplit
        partes = urlsplit(ref)
        origem = f"{partes.scheme}://{partes.netloc}"
    origem = origem.rstrip("/").lower()
    host = (req.headers.get("host") or "").lower()
    from urllib.parse import urlsplit as _us
    if _us(origem).netloc == host and host:
        return True
    return origem in acesso.origens_extras()


@app.middleware("http")
async def cabecalhos_de_seguranca(req: Request, chamar):
    """CSRF por origem e CSP com nonce. Middleware por fora de tudo: vale para
    toda rota, inclusive as que ainda vão nascer."""
    if req.method in METODOS_INSEGUROS and not _origem_confiavel(req):
        return JSONResponse({"erro": "origem não permitida"}, status_code=403)
    nonce = secrets.token_urlsafe(16)
    tok = _NONCE.set(nonce)
    try:
        resp = await chamar(req)
    finally:
        _NONCE.reset(tok)
    if "content-security-policy" not in resp.headers:
        resp.headers["Content-Security-Policy"] = CSP_APP.format(nonce=nonce)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    return resp


# --- módulos ocultos também nas rotas de dado ---------------------------------
# A aba some do cabeçalho e `html_vista` recusa a vista, mas fichas, CSV e PDF
# de cada módulo têm rota própria. A mesma régua (`modulo_visivel`) vale para elas.
ROTAS_DE_MODULO = (("/painel-rh", "painel_rh"), ("/dcr", "dcr"),
                   ("/skills/", "dcr"), ("/cgv", "cgv"),
                   ("/talentos", "talentos"), ("/gptw.csv", "gptw"),
                   ("/gptw/programar", "gptw"), ("/onebyone", "onebyone"))


def modulo_da_rota(caminho: str) -> str | None:
    return next((m for prefixo, m in ROTAS_DE_MODULO
                 if caminho.startswith(prefixo)), None)


def sessao_atual(req: Request) -> dict | None:
    """A carga do cookie, se assinada, no prazo e NÃO revogada. Com o login
    exigido, a conta tem de existir, estar ativa e a versão de sessão bater
    (trocar ou remover a senha encerra as sessões abertas)."""
    carga = acesso.verificar(req.cookies.get(acesso.COOKIE))
    if carga and acesso.exigir_login() and not usuariosmod.sessao_valida(carga):
        return None
    return carga


def abrir_sessao(email: str, uid: str | None) -> RedirectResponse:
    r = RedirectResponse("/", status_code=303)
    v = usuariosmod.versao_sessao(email) or 0
    r.set_cookie(acesso.COOKIE, acesso.assinar({"sub": email, "uid": uid or "",
                                                "v": v}),
                 httponly=True, samesite="lax", max_age=acesso.TTL_PADRAO,
                 secure=req_seguro())
    return r


def req_seguro() -> bool:
    """`secure` só em produção: em http://127.0.0.1 o cookie seria descartado."""
    return acesso._env("ORG_COOKIE_SEGURO") == "1"


@app.get("/login", response_class=HTMLResponse)
def tela_login(req: Request, erro: str = "", aviso: str = ""):
    if sessao_atual(req):
        return RedirectResponse("/", status_code=303)
    # Exemplo fixo: o primeiro e-mail da base é uma pessoa real qualquer, e
    # expor um nome no placeholder de login não serve a ninguém.
    exemplo = acesso._env("ORG_EMAIL_EXEMPLO", "nome.sobrenome@gplansis.com")
    # Primeiro acesso: sem NENHUM usuário, a tela oferece criar o administrador
    # inicial — uma vez só; com um usuário que seja, o formulário some.
    return HTMLResponse(render("login.html", request=req, exemplo=exemplo,
                               erro=erro, aviso=aviso,
                               primeiro=(usuariosmod.total() == 0
                                         and acesso.primeiro_acesso_permitido()),
                               minimo=usuariosmod.SENHA_MINIMA))


def _recusa_de_senha(erro: Exception) -> str:
    """As recusas de `usuarios.politica` são chaves do catálogo. T() com o texto
    literal, e não `T(str(erro))`: é assim que a varredura dos três idiomas vê a
    chave e cobra a tradução."""
    msgs = {
        "A senha precisa ter pelo menos 8 caracteres.":
            T("A senha precisa ter pelo menos 8 caracteres."),
        "A senha é longa demais (máximo 128 caracteres).":
            T("A senha é longa demais (máximo 128 caracteres)."),
        "A senha não pode começar nem terminar com espaço.":
            T("A senha não pode começar nem terminar com espaço."),
        "E-mail inválido.": T("E-mail inválido."),
    }
    return msgs.get(str(erro), str(erro))


def _abrir_para(req: Request, email: str) -> RedirectResponse:
    """Sessão para um e-mail já AUTENTICADO. Se a pessoa é nó do organograma
    ATIVO fica vinculada a ele (avatar, escopo "próprio"); se não é, entra
    desvinculada com o acesso definido — ou como superadmin. Registra a entrada
    com os dados LOCAIS: o cookie só é setado nesta resposta, então
    `acesso_vigente()` ainda seria a sessão anterior. A sessão viaja só no
    cookie (sub+uid); o perfil é resolvido por requisição (resolver_sessao) —
    NÃO se muta nem se persiste o Config global aqui."""
    u = acesso.por_email(ESTADO.unidades, email)
    registrar_acesso("entrar", usuario_id=(u.id if u else None),
                     nome=(u.nome if u else ""), email=(u.email if u else email))
    r = abrir_sessao(u.email if u else email, u.id if u else None)
    if usuariosmod.precisa_trocar(email):
        r.headers["location"] = "/senha"
    return r


@app.post("/entrar")
def entrar(req: Request, email: str = Form(""), senha: str = Form("")):
    """Login do próprio sistema: e-mail + senha conferidos por `usuarios`.

    Uma mensagem só para "não existe" e "senha errada" — não se enumera usuário
    pela tela de login. O domínio (ORG_DOMINIOS) é a primeira porta quando está
    configurado; o freio a força bruta, a segunda; a senha, a terceira."""
    email = usuariosmod.normalizar(email)
    if not acesso.dominio_valido(email):
        if acesso.dominios():
            return tela_login(req, erro=T("Use o e-mail da organização ({dominios}).",
                                          dominios=", ".join(acesso.dominios())))
        return tela_login(req, erro=T("E-mail ou senha inválidos."))
    if (s := usuariosmod.travado(email)):
        return tela_login(req, erro=T("Muitas tentativas. Aguarde {s} segundos e tente de novo.", s=s))
    if not usuariosmod.conferir(email, senha):
        return tela_login(req, erro=T("E-mail ou senha inválidos."))
    return _abrir_para(req, email)


@app.post("/entrar/primeiro")
def entrar_primeiro(req: Request, email: str = Form(""), senha: str = Form(""),
                    repetir: str = Form("")):
    """Cria o administrador inicial — só enquanto não existe usuário NENHUM. A
    partir do primeiro, esta rota recusa: novas contas nascem em Configurações
    › Permissões, pela mão de quem administra."""
    if usuariosmod.total() or not acesso.primeiro_acesso_permitido():
        return tela_login(req, erro=T("Já existe um usuário: peça a senha a quem administra."))
    email = usuariosmod.normalizar(email)
    if not acesso.dominio_valido(email):
        return tela_login(req, erro=T("Use o e-mail da organização ({dominios}).",
                                      dominios=", ".join(acesso.dominios()) or "@"))
    if senha != repetir:
        return tela_login(req, erro=T("As senhas não conferem."))
    try:
        usuariosmod.definir_senha(email, senha, por="primeiro acesso",
                                  operador=True)
    except ValueError as erro:
        return tela_login(req, erro=_recusa_de_senha(erro))
    return _abrir_para(req, email)


@app.get("/senha", response_class=HTMLResponse)
def tela_senha(req: Request, erro: str = "", ok: str = ""):
    carga = sessao_atual(req)
    if not carga:
        return RedirectResponse("/login", status_code=303)
    email = carga.get("sub", "")
    return HTMLResponse(render("senha.html", request=req, email=email, erro=erro, ok=ok,
                               obrigatoria=usuariosmod.precisa_trocar(email),
                               minimo=usuariosmod.SENHA_MINIMA))


@app.post("/senha", response_class=HTMLResponse)
def trocar_senha(req: Request, atual: str = Form(""), nova: str = Form(""),
                 repetir: str = Form("")):
    """A própria pessoa troca a senha: prova a atual, escolhe a nova. Limpa a
    marca de senha temporária e anota no monitoramento de acessos."""
    carga = sessao_atual(req)
    if not carga:
        return RedirectResponse("/login", status_code=303)
    email = carga.get("sub", "")
    if not usuariosmod.conferir(email, atual):
        return tela_senha(req, erro=T("Senha atual incorreta."))
    if nova != repetir:
        return tela_senha(req, erro=T("As senhas não conferem."))
    try:
        usuariosmod.definir_senha(email, nova, por=email)
    except ValueError as erro:
        return tela_senha(req, erro=_recusa_de_senha(erro))
    registrar_acesso("senha", usuario_id=carga.get("uid") or None, email=email)
    # A senha nova sobe a versão de sessão (as outras sessões caem); esta, que
    # acabou de provar a senha, recebe um cookie novo para continuar.
    r = HTMLResponse(render("senha.html", request=req, email=email, erro="",
                            ok=T("Senha alterada."),
                            obrigatoria=usuariosmod.precisa_trocar(email),
                            minimo=usuariosmod.SENHA_MINIMA))
    r.set_cookie(acesso.COOKIE, acesso.assinar({
        "sub": email, "uid": carga.get("uid") or "",
        "v": usuariosmod.versao_sessao(email) or 0}),
        httponly=True, samesite="lax", max_age=acesso.TTL_PADRAO,
        secure=req_seguro())
    return r


@app.post("/sair")
def sair(req: Request):
    """Encerra a sessão: apaga o cookie e registra a saída."""
    # Quem sai ainda tem cookie válido nesta requisição; resolve pela sessão.
    carga = sessao_atual(req)
    if carga:
        u = ESTADO.unidades.get(carga.get("uid") or "")
        registrar_acesso("sair", usuario_id=(carga.get("uid") or None),
                         nome=(u.nome if u else ""), email=carga.get("sub", ""))
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie(acesso.COOKIE)
    return r


@app.get("/presenca", response_class=HTMLResponse)
def presenca(req: Request):
    """Quem está usando o sistema agora — o corpo do popover flutuante do canvas.
    Auto-atualiza (htmx a cada 25s), e cada chamada também renova a presença de
    quem pediu (passa pelo resolver_sessao). Devolve a lista e, por OOB, a contagem
    no crachá do botão."""
    ativos = usuarios_ativos(acesso_vigente().usuario_id)
    return HTMLResponse(render("_presenca_corpo.html", request=req, ativos=ativos))


LANDING = RAIZ / "web" / "publico" / "landing.html"


@app.get("/", response_class=HTMLResponse)
def inicio(req: Request, vista: str = "canvas", aba: str = "geral",
           banda: str = "", vertical: str = "", departamento: str = "",
           conferir: int = 0, ciclo: str = ""):
    """A raiz atende dois publicos, e decide pela sessao.

    SEM sessao: a apresentacao publica (`web/publico/landing.html`), com o
    botao «Entrar» levando a /login. COM sessao: o aplicativo, como sempre.

    A alternativa — landing num endereco proprio e a raiz sempre no login —
    deixaria peoples.gplansis.com abrindo num formulario de senha para quem
    nunca viu o sistema. E servir a landing para todo mundo faria quem trabalha
    passar por marketing a cada acesso.

    `?vista=` torna a vista compartilhavel por link, sem duplicar render.
    """
    if acesso.exigir_login() and not sessao_atual(req):
        if not LANDING.exists():                   # instalacao sem a landing
            return RedirectResponse("/login", status_code=303)
        return pagina_estatica(LANDING.read_text(encoding="utf-8"))
    # Se o módulo pedido não é visível para este acesso (Fase D), abre no
    # primeiro que for — senão a home abriria num aviso de indisponível.
    if vista in MODULOS_CHAVES and not modulo_visivel(vista):
        vista = next((c for c, _ in MODULOS if modulo_visivel(c)), vista)
    return HTMLResponse(render("base.html", request=req, vista=vista,
                               corpo=html_vista(req, vista, aba, banda=banda,
                                                vertical=vertical,
                                                departamento=departamento,
                                                conferir=bool(conferir),
                                                ciclo=ciclo),
                               painel=painel_atual(req)))


@app.get("/vistas/{vista}", response_class=HTMLResponse)
def fragmento_vista(req: Request, vista: str, aba: str = "geral",
                    banda: str = "", vertical: str = "", departamento: str = "",
                    conferir: int = 0, ciclo: str = ""):
    return HTMLResponse(html_vista(req, vista, aba, banda=banda,
                                   vertical=vertical, departamento=departamento,
                                   conferir=bool(conferir), ciclo=ciclo))


# --- fragmentos -----------------------------------------------------------
@app.get("/fragmentos/menu/{uid}", response_class=HTMLResponse)
def fragmento_menu(req: Request, uid: str):
    """INT-03: habilitacao das acoes vem pronta do servidor."""
    if equipesmod.e_equipe(uid):
        # Equipe nao tem acao de estrutura: nao ha o que promover, mover ou
        # excluir num no que o sistema desenha a cada render. Menu vazio e
        # melhor que menu cinza — este nao e um caso de permissao.
        return HTMLResponse("")
    uni = universo_visivel()
    universo = ESTADO.unidades if uni is None else uni
    u = universo.get(uid)                   # fora do escopo => menu vazio (não vaza nome)
    if u is None:
        return HTMLResponse("")
    filhos = mapa_filhos(universo)
    irmaos = [x.id for x in filhos.get(u.parent_id, [])]
    idx = irmaos.index(uid) if uid in irmaos else 0
    pode = negado(NIVEL_EDITOR, uid) is None
    avo = universo.get(u.parent_id) if u.parent_id else None
    return HTMLResponse(render(
        "_menu.html", request=req, u=u, e_raiz=u.parent_id is None, pode=pode,
        pode_esquerda=pode and u.parent_id is not None and idx > 0,
        pode_direita=pode and u.parent_id is not None and idx < len(irmaos) - 1,
        pode_rebaixar=pode and u.parent_id is not None and idx > 0,
        pode_promover=(pode and avo is not None and avo.parent_id is not None),
        tem_filhos=bool(filhos.get(uid)),
        colapsado=uid in ESTADO.colapsados,
        focado=ESTADO.foco == uid))


@app.post("/config/helper")
def config_helper(req: Request, ligado: int = Form(0)):
    """Liga e desliga a visita. Devolve 204: quem pediu já sabe o que pediu.
    É configuração GLOBAL: exige Administrador, como o resto de Configurações."""
    if negado(NIVEL_ADMIN):
        return Response(status_code=403)
    ESTADO.config.helper = bool(ligado)
    gravar()
    return Response(status_code=204)


@app.get("/fragmentos/menu-fundo", response_class=HTMLResponse)
def fragmento_menu_fundo(req: Request):
    """Botao direito no vazio do palco: o que se faz com o desenho.

    O menu do card responde "o que faco com esta pessoa"; este responde "o que
    faco com este desenho" — e ate agora essa pergunta so tinha resposta na
    barra e no canto, que saem da tela assim que alguem arrasta o organograma.

    INT-03 como no menu do card: a habilitacao vem pronta daqui. `nivel_aberto`
    e derivado do desenho, e nao de contador guardado, entao os dois degraus
    sabem quando nao ha mais para onde ir.
    """
    fonte = desenho_atual()
    prof = profundidades(fonte)
    aberto = nivel_aberto(fonte, ESTADO.colapsados)
    return HTMLResponse(render(
        "_menu_fundo.html", request=req,
        raiz_id=raiz(fonte).id if fonte else "",
        pode_abrir=aberto < (max(prof.values()) if prof else 0),
        pode_fechar=aberto > 0,
        tem_foco=bool(ESTADO.foco),
        tem_filtro=filtro_ativo(),
        # Criar unidade so na visao por pessoa: equipe e desenho derivado, e a
        # guarda de `negado` recusaria — botao aceso que responde "acao negada"
        # e a definicao de tela em que nao se confia.
        pode_criar=(negado(NIVEL_EDITOR) is None
                    and ESTADO.agrupamento != "equipe")))


@app.get("/fragmentos/painel/{uid}", response_class=HTMLResponse)
def fragmento_painel(req: Request, uid: str, canvas: int = 1,
                     vista: str = "", contexto: str = ""):
    """`canvas=0` vem da tabela, onde nao existe #canvas para o swap OOB.

    `vista`/`contexto` dizem de onde a gaveta foi aberta, para que salvar
    devolva a tela certa: o painel e a lista que a pessoa esta olhando.
    """
    ESTADO.selecionado = uid
    if equipesmod.e_equipe(uid):
        return HTMLResponse(painel_equipe(req, uid))
    origem = vista or ("canvas" if canvas else "tabela")
    return HTMLResponse(corpo_painel(req, uid, com_canvas=bool(canvas),
                                     vista_origem=origem,
                                     contexto_origem=contexto))


@app.get("/fragmentos/equipe/{cid}", response_class=HTMLResponse)
def fragmento_equipe(req: Request, cid: str, pessoa: str = ""):
    """A mesma gaveta, com uma pessoa evidenciada.

    Rota propria em vez de parametro na do painel porque o alvo do htmx e o
    mesmo `#painel`: trocar so o conteudo mantem a rolagem e o foco de quem
    esta percorrendo um time de doze.
    """
    ESTADO.selecionado = cid
    return HTMLResponse(painel_equipe(req, cid, pessoa or None))


@app.get("/fragmentos/painel-vazio", response_class=HTMLResponse)
def fragmento_painel_vazio(req: Request):
    ESTADO.selecionado = None
    return HTMLResponse(render("_painel_vazio.html", request=req))


# --- mutacoes de estrutura ------------------------------------------------
@app.post("/unidades/{uid}/filho", response_class=HTMLResponse)
def add_filho(req: Request, uid: str):
    if (msg := negado(NIVEL_EDITOR, uid)):
        return recusar(req, msg)
    marcar_ponto()
    novo = Unidade(id=novo_id(), codigo=proximo_codigo(), nome=T("Nova unidade"),
                   tipo="celula", parent_id=uid,
                   ordem=(len(mapa_filhos(ESTADO.unidades).get(uid, [])) + 1) * 10,
                   area=ESTADO.unidades[uid].area,
                   vertical=ESTADO.unidades[uid].vertical)
    ESTADO.unidades[novo.id] = novo
    ESTADO.colapsados.discard(uid)
    ESTADO.selecionado = novo.id
    commit("criar", novo.id, "novo subordinado pelo canvas", {"parent_id": uid})
    return canvas(req, oob_painel(req, novo.id))


@app.post("/colaborador/novo", response_class=HTMLResponse)
def colaborador_novo(req: Request):
    """Cria um colaborador sob o nó SELECIONADO (ou a raiz, se nada estiver
    selecionado) e abre a ficha para preencher. É o "+ Unidade" sem precisar
    clicar num card antes — o botão que monta um organograma novo do zero."""
    alvo = ESTADO.selecionado
    if not alvo or alvo not in ESTADO.unidades:
        alvo = raiz(ESTADO.unidades).id if ESTADO.unidades else None
    if alvo is None:
        return recusar(req, T("Não há onde criar: o organograma está sem raiz."))
    if (msg := negado(NIVEL_EDITOR, alvo)):
        return recusar(req, msg)
    marcar_ponto()
    pai = ESTADO.unidades[alvo]
    novo = Unidade(id=novo_id(), codigo=proximo_codigo(), nome=T("Novo colaborador"),
                   tipo="celula", parent_id=alvo,
                   ordem=(len(mapa_filhos(ESTADO.unidades).get(alvo, [])) + 1) * 10,
                   area=pai.area, vertical=pai.vertical)
    ESTADO.unidades[novo.id] = novo
    ESTADO.colapsados.discard(alvo)
    ESTADO.selecionado = novo.id
    commit("criar", novo.id, "novo colaborador", {"parent_id": alvo})
    return canvas(req, oob_painel(req, novo.id))


@app.post("/unidades/{uid}/duplicar", response_class=HTMLResponse)
def duplicar(req: Request, uid: str):
    if (msg := negado(NIVEL_EDITOR, uid)):
        return recusar(req, msg)
    marcar_ponto()
    o = ESTADO.unidades[uid]
    novo = Unidade(id=novo_id(), codigo=proximo_codigo(), nome=T("{nome} (cópia)", nome=o.nome),
                   tipo=o.tipo, parent_id=o.parent_id, ordem=o.ordem + 5,
                   cargo=o.cargo, area=o.area, centro_custo=o.centro_custo,
                   vertical=o.vertical,
                   responsabilidades=copy.deepcopy(o.responsabilidades),
                   competencias=list(o.competencias))
    ESTADO.unidades[novo.id] = novo          # W9-C7: copia sem pessoa alocada
    renumerar(ESTADO.unidades, novo.parent_id)
    ESTADO.selecionado = novo.id
    commit("criar", novo.id, "duplicação pelo canvas", {"origem": uid})
    return canvas(req, oob_painel(req, novo.id))


@app.post("/unidades/{uid}/reordenar", response_class=HTMLResponse)
def reordenar(req: Request, uid: str, direcao: str = "direita"):
    if (msg := negado(NIVEL_EDITOR, uid)):
        return recusar(req, msg)
    marcar_ponto()
    u = ESTADO.unidades[uid]
    u.ordem += 15 if direcao == "direita" else -15
    renumerar(ESTADO.unidades, u.parent_id)   # W9-C6: renumera em multiplos de 10
    commit("alterar", uid, f"reordenar para {direcao}", {"ordem": u.ordem})
    return canvas(req)


@app.post("/unidades/{uid}/promover", response_class=HTMLResponse)
def promover(req: Request, uid: str):
    if (msg := negado(NIVEL_EDITOR, uid)):
        return recusar(req, msg)
    u = ESTADO.unidades[uid]
    avo = ESTADO.unidades[u.parent_id].parent_id
    if avo is None:
        return recusar(req, "Promoção recusada: não há nível acima do pai.")
    marcar_ponto()
    u.parent_id = avo
    renumerar(ESTADO.unidades, avo)
    commit("mover", uid, "promover um nível", {"novo_pai": avo})
    return canvas(req)


@app.post("/unidades/{uid}/rebaixar", response_class=HTMLResponse)
def rebaixar(req: Request, uid: str):
    """Vira filho do irmao imediatamente anterior."""
    if (msg := negado(NIVEL_EDITOR, uid)):
        return recusar(req, msg)
    u = ESTADO.unidades[uid]
    ids = [x.id for x in mapa_filhos(ESTADO.unidades).get(u.parent_id, [])]
    idx = ids.index(uid)
    if idx == 0:
        return recusar(req, "Rebaixamento recusado: não há irmão anterior.")
    marcar_ponto()
    alvo = ids[idx - 1]
    u.parent_id = alvo
    u.ordem = (len(mapa_filhos(ESTADO.unidades).get(alvo, [])) + 1) * 10
    ESTADO.colapsados.discard(alvo)
    commit("mover", uid, "rebaixar um nível", {"novo_pai": alvo})
    return canvas(req)


@app.post("/unidades/{uid}/mover", response_class=HTMLResponse)
def mover(req: Request, uid: str, destino: str = Form(...),
          vista: str = Form("canvas"), contexto: str = Form("")):
    """Reparent explicito. Guarda de ciclo: RF-02 / INV-02 / W2-C2."""
    if (msg := negado(NIVEL_EDITOR, uid)):
        return recusar(req, msg)
    u = ESTADO.unidades[uid]
    if destino == uid or destino in descendentes(ESTADO.unidades, uid):
        return recusar(req, "Movimento recusado: o destino é descendente da "
                            "unidade (ciclo detectado).")
    marcar_ponto()
    u.parent_id = destino
    u.ordem = (len(mapa_filhos(ESTADO.unidades).get(destino, [])) + 1) * 10
    ESTADO.colapsados.discard(destino)
    commit("mover", uid, "reparent pelo painel", {"novo_pai": destino})
    return resposta_de_mutacao(req, uid, vista, contexto)


@app.post("/unidades/{uid}/salvar", response_class=HTMLResponse)
def salvar(req: Request, uid: str,
           nome: str = Form(...), tipo: str = Form(...),
           responsavel: str = Form(""), cargo: str = Form(""),
           area: str = Form(""), email: str = Form(""),
           centro_custo: str = Form(""), vertical: str = Form(""),
           vinculo: str = Form(dominio.VINCULO_PADRAO),
           data_inicio: str = Form(""), status: str = Form(""),
           responsabilidades: str = Form(""), competencias: str = Form(""),
           tipo_mo: str = Form(""), n2: str = Form(""), n4: str = Form(""),
           n5: str = Form(""), cc_equipe: str = Form(""), bu: str = Form(""),
           tipo_class: str = Form(""), mo_classe: str = Form(""),
           categoria_nivel: str = Form(""), genero: str = Form(""),
           data_nascimento: str = Form(""),
           vista: str = Form("canvas"), contexto: str = Form("")):
    if (msg := negado(NIVEL_EDITOR, uid)):
        return recusar(req, msg)
    marcar_ponto()
    u = ESTADO.unidades[uid]
    u.nome = nome.strip()[:80] or u.nome
    u.tipo = tipo if tipo in TIPOS else u.tipo
    u.responsavel = responsavel.strip()[:60]
    u.cargo = cargo.strip()[:80]
    area_anterior = u.area
    u.area = area.strip()[:60]
    u.email = email.strip()[:120]
    u.centro_custo = centro_custo.strip()[:12]
    u.vertical = vertical.strip()[:12]
    u.vinculo = vinculo if vinculo in dominio.VINCULOS else u.vinculo
    # `<input type=date>` só entrega ISO ou vazio, mas o POST não vem só da
    # tela: guardar lixo aqui envenenaria o tempo de casa, a faixa e o módulo
    # inteiro, e o estrago só apareceria num indicador que ninguém confere.
    u.data_inicio = importador._data(data_inicio)
    u.status = status if status in dominio.STATUS else ""

    itens = []
    for linha in responsabilidades.splitlines():
        texto = linha.strip()
        if not texto:
            continue
        delegada = texto.startswith(">")
        itens.append({"descricao": texto.lstrip("> ").strip()[:200],
                      "origem": "delegada" if delegada else "propria",
                      "delegada_para": None})
    u.responsabilidades = itens
    u.competencias = [s.strip()[:40] for s in competencias.split(",") if s.strip()]
    # Campos organizacionais da planilha completa (bd_completo_org). Sem dinheiro
    # aqui — só o que descreve a posição, não a remuneração (LGPD).
    u.tipo_mo = tipo_mo.strip()[:40]
    u.n2 = n2.strip()[:20]
    u.n4 = n4.strip()[:20]
    u.n5 = n5.strip()[:20]
    u.cc_equipe = cc_equipe.strip()[:40]
    u.bu = bu.strip()[:60]
    u.tipo_class = tipo_class.strip()[:40]
    u.mo_classe = mo_classe.strip()[:40]
    u.categoria_nivel = categoria_nivel.strip()[:40]
    u.genero = genero.strip()[:20]
    u.data_nascimento = importador._data(data_nascimento)

    commit("alterar", uid, "edição pelo painel",
           {"nome": u.nome, "accountabilities": len(itens),
            "competencias": len(u.competencias)})
    abrir_provisionamento(u, area_anterior, u.area)
    return resposta_de_mutacao(req, uid, vista, contexto)


@app.delete("/unidades/{uid}", response_class=HTMLResponse)
def excluir(req: Request, uid: str):
    if (msg := negado(NIVEL_EDITOR, uid)):
        return recusar(req, msg)
    u = ESTADO.unidades[uid]
    if u.parent_id is None:                       # W9-C9
        return recusar(req, "Exclusão recusada: a raiz não pode ser removida.")
    marcar_ponto()
    for f in mapa_filhos(ESTADO.unidades).get(uid, []):   # filhos sobem ao avo
        f.parent_id = u.parent_id
    del ESTADO.unidades[uid]
    ESTADO.colapsados.discard(uid)
    renumerar(ESTADO.unidades, u.parent_id)
    if ESTADO.selecionado == uid:
        ESTADO.selecionado = None
    if ESTADO.foco == uid:
        ESTADO.foco = None
    commit("inativar", uid, "exclusão pelo canvas", {"nome": u.nome})
    return canvas(req, oob_painel(req, None))


# --- comandos de vista (nao mudam o dominio, nao entram no ledger) --------
@app.post("/unidades/{uid}/colapsar", response_class=HTMLResponse)
def colapsar(req: Request, uid: str, vista: str = "canvas"):
    """Colapso e um estado so: dobrar na tabela dobra no canvas."""
    ESTADO.colapsados.symmetric_difference_update({uid})
    gravar()
    return corpo_tabela(req) if vista == "tabela" else canvas(req)


@app.post("/unidades/{uid}/focar", response_class=HTMLResponse)
def focar(req: Request, uid: str):
    ESTADO.foco = None if ESTADO.foco == uid else uid
    if ESTADO.foco:
        ESTADO.colapsados.discard(uid)
    return canvas(req)


@app.post("/foco/limpar", response_class=HTMLResponse)
def limpar_foco(req: Request):
    ESTADO.foco = None
    return canvas(req)


@app.post("/arvore/{modo}", response_class=HTMLResponse)
def expandir_colapsar(req: Request, modo: str, nivel: int = -1, vista: str = "canvas"):
    # A tabela e sempre por pessoa; o canvas segue o agrupamento vigente.
    equipe = vista != "tabela" and ESTADO.agrupamento == "equipe"
    fonte = desenho_atual() if equipe else ESTADO.unidades
    if modo == "expandir":
        trocar_colapso(set(), equipe)
    elif modo == "nivel":
        trocar_colapso(colapso_por_nivel(max(0, nivel), fonte), equipe)
    elif modo in ("mais", "menos"):
        # Um degrau por clique, a partir do que esta aberto agora. Abrir tudo de
        # uma vez em 267 cards e a pergunta errada: quem desce nivel a nivel
        # esta lendo a estrutura, e cada passo precisa caber na tela.
        atual = nivel_aberto(fonte, ESTADO.colapsados)
        alvo = atual + 1 if modo == "mais" else atual - 1
        trocar_colapso(colapso_por_nivel(max(0, alvo), fonte), equipe)
    else:
        trocar_colapso(colapso_por_nivel(ESTADO.config.profundidade_aberta,
                                         fonte), equipe)
    gravar()
    return corpo_tabela(req) if vista == "tabela" else canvas(req)


@app.post("/filtros", response_class=HTMLResponse)
async def aplicar_filtros(req: Request, vista: str = "canvas"):
    """Alveja o desenho; da barra, so os chips voltam — fora de banda.

    O campo de busca continua intocado de proposito: trocar a barra inteira a
    cada tecla roubaria o foco de quem esta digitando. Os chips precisam voltar
    porque os criterios se filtram uns aos outros, e um dominio que estreita no
    servidor sem estreitar na tela continuaria oferecendo opcao morta.

    A contagem vive no cabecalho do desenho, que e re-renderizado de qualquer
    forma.
    """
    form = await req.form()
    # Parte do que está, e não de um dicionário novo: `profundidade` não vive em
    # `CRITERIOS` — é propriedade da árvore desenhada, não atributo da unidade —
    # e o formulário dos chips não a envia. Montando do zero, marcar N2 e depois
    # clicar em qualquer chip apagava o recorte por nível no servidor, enquanto
    # os botões N continuavam apertados na tela: a resposta traz só os chips
    # fora de banda, então `_niveis.html` não voltava para se desmarcar.
    ESTADO.filtros = {
        **ESTADO.filtros,
        "texto": str(form.get("texto", ""))[:80],
        **{c: [v for v in form.getlist(c) if v] for c in CRITERIOS}}
    gravar()
    extra = oob_chips(req)
    # Cada vista devolve o próprio corpo, e a barra volta só como chips fora de
    # banda. Enquanto isto era um ternário "tabela ou canvas", filtrar de dentro
    # do tempo de empresa gravava o recorte e devolvia o desenho — para um
    # `#canvas` que não existe naquela tela. O htmx não reclama de alvo ausente:
    # a filtragem simplesmente não aparecia, e os números seguiam os da base
    # inteira até alguém trocar de aba.
    corpo = {"tabela": corpo_tabela, "tempo": corpo_tempo,
             "dcr": corpo_dcr, "cgv": corpo_cgv,
             "talentos": corpo_talentos, "onebyone": corpo_onebyone}.get(vista)
    return (HTMLResponse(corpo(req).body.decode() + extra) if corpo
            else canvas(req, extra))


# --- a grade editável -----------------------------------------------------
# Rotas de JSON, e não de HTML: a grade é a única parte do sistema que não é
# desenhada pelo servidor, e devolver fragmento para ela seria devolver algo
# que ninguém troca no DOM. O domínio continua sendo do servidor — cada uma
# destas rotas passa pelas mesmas guardas do painel (permissão, ciclo,
# renumeração, ledger, ponto de desfazer) e o cliente recarrega o que mudou.
def _dados_da_grade() -> dict:
    ctx = contexto_filtros()
    return {
        "podeEditar": not negado(NIVEL_EDITOR),
        "motivo": negado(NIVEL_EDITOR) or "",
        "colunas": grademod.colunas(colunas_da_tabela()),
        "dominios": grademod.dominios(ESTADO.config, ctx["opcoes"], T),
        "linhas": [grademod.linha(l, ESTADO.config.rotulos_nivel, _anos_texto)
                   for l in linhas_tabela()],
        # (profundidade, nome) de TODA unidade, e não só das visíveis. O
        # cliente dimensiona com isto a coluna da árvore: a largura de que ela
        # precisa é `recuo + nome`, e o recuo cresce com a profundidade. Medindo
        # só o que está na tela, a coluna encolhia com a árvore recolhida e
        # cortava nomes assim que alguém abria um galho — e mudava de largura a
        # cada dobra, que é a pior coisa que uma coluna pode fazer com o olho de
        # quem está lendo a lista.
        "arvore": [[d, u.nome] for u, d in _todas_as_profundidades()],
    }


def _todas_as_profundidades() -> list[tuple]:
    prof = profundidades(ESTADO.unidades)
    return [(u, prof.get(u.id, 0)) for u in ESTADO.unidades.values()]


def _anos_texto(v) -> str:
    return "—" if v is None else f"{v:.1f}".replace(".", ",")


@app.get("/grade/dados")
def grade_dados():
    return JSONResponse(_dados_da_grade())


@app.post("/grade/celula")
async def grade_celula(req: Request):
    """Grava UM campo de UMA unidade, e devolve a grade inteira de volta.

    Devolver tudo, e não só a célula: mudar o nível repinta o chip, mudar o
    centro de custo troca N5, vertical e natureza na mesma linha, e mudar o
    departamento pode abrir um provisionamento. Uma resposta de uma célula só
    deixaria a linha contando três histórias diferentes.
    """
    form = await req.form()
    uid = str(form.get("uid", ""))
    campo = str(form.get("campo", ""))
    valor = str(form.get("valor", ""))
    if (msg := negado(NIVEL_EDITOR, uid)):
        return JSONResponse({"ok": False, "aviso": msg}, status_code=200)
    if uid not in ESTADO.unidades:
        return JSONResponse({"ok": False, "aviso": T("Unidade não encontrada.")})
    # `campo` chega por POST, e formulário é coisa que se forja: fora da lista
    # branca o pedido é recusado em vez de gravar um atributo qualquer.
    if campo not in grademod.EDITAVEIS:
        return JSONResponse({"ok": False, "aviso": T(
            "Campo {campo} não é editável na grade.", campo=campo)})

    u = ESTADO.unidades[uid]
    antes = getattr(u, campo, "")
    marcar_ponto()
    area_anterior = u.area
    if campo == "tipo":
        u.tipo = valor if valor in TIPOS else u.tipo
    elif campo == "vinculo":
        u.vinculo = valor if valor in dominio.VINCULOS else u.vinculo
    elif campo == "status":
        u.status = valor if valor in dominio.STATUS else ""
    elif campo == "data_inicio":
        u.data_inicio = importador._data(valor)
    elif campo == "accountabilities":
        u.responsabilidades = [
            {"descricao": t.lstrip("> ").strip()[:200],
             "origem": "delegada" if t.startswith(">") else "propria",
             "delegada_para": None}
            for t in (x.strip() for x in valor.splitlines()) if t]
    elif campo == "nome":
        # Nome vazio apagaria a linha da tela sem apagar a unidade: o nome é o
        # que a árvore mostra, e uma linha em branco não é editável de volta.
        u.nome = valor.strip()[:80] or u.nome
    else:
        limite = {"codigo": 12, "cargo": 80, "area": 60,
                  "centro_custo": 12, "email": 120}.get(campo, 80)
        setattr(u, campo, valor.strip()[:limite])

    commit("alterar", uid, f"edição pela grade: {campo}",
           {"campo": campo, "de": str(antes)[:60],
            "para": str(getattr(u, campo, ""))[:60]})
    if campo == "area":
        abrir_provisionamento(u, area_anterior, u.area)
    esquecer_equipes()
    return JSONResponse({"ok": True, **_dados_da_grade()})


@app.post("/grade/mover")
async def grade_mover(req: Request):
    """Indentar, promover, subir, descer e reparent — pelas guardas de sempre.

    As quatro primeiras existiam como rotas do canvas e devolviam HTML. Aqui
    elas devolvem JSON, mas a operação é a mesma função de domínio: duplicar a
    regra de ciclo ou a renumeração numa segunda rota seria escrever a segunda
    versão de um invariante (RF-02 / INV-02).
    """
    form = await req.form()
    uid = str(form.get("uid", ""))
    acao = str(form.get("acao", ""))
    destino = str(form.get("destino", ""))
    if (msg := negado(NIVEL_EDITOR, uid)):
        return JSONResponse({"ok": False, "aviso": msg})
    if uid not in ESTADO.unidades:
        return JSONResponse({"ok": False, "aviso": T("Unidade não encontrada.")})

    u = ESTADO.unidades[uid]
    filhos = mapa_filhos(ESTADO.unidades)
    if acao == "promover":
        if u.parent_id is None:
            return JSONResponse({"ok": False, "aviso": T(
                "Promoção recusada: não há nível acima do pai.")})
        avo = ESTADO.unidades[u.parent_id].parent_id
        if avo is None:
            return JSONResponse({"ok": False, "aviso": T(
                "Promoção recusada: não há nível acima do pai.")})
        marcar_ponto()
        u.parent_id = avo
        renumerar(ESTADO.unidades, avo)
        commit("mover", uid, "promover pela grade", {"novo_pai": avo})
    elif acao == "indentar":
        ids = [x.id for x in filhos.get(u.parent_id, [])]
        if uid not in ids or ids.index(uid) == 0:
            return JSONResponse({"ok": False, "aviso": T(
                "Rebaixamento recusado: não há irmão anterior.")})
        marcar_ponto()
        alvo = ids[ids.index(uid) - 1]
        u.parent_id = alvo
        u.ordem = (len(filhos.get(alvo, [])) + 1) * 10
        ESTADO.colapsados.discard(alvo)
        commit("mover", uid, "indentar pela grade", {"novo_pai": alvo})
    elif acao in ("subir", "descer"):
        marcar_ponto()
        u.ordem += -15 if acao == "subir" else 15
        renumerar(ESTADO.unidades, u.parent_id)
        commit("alterar", uid, f"reordenar pela grade ({acao})",
               {"ordem": u.ordem})
    elif destino:
        if destino == uid or destino in descendentes(ESTADO.unidades, uid):
            return JSONResponse({"ok": False, "aviso": T(
                "Movimento recusado: o destino é descendente da unidade "
                "(ciclo detectado).")})
        if destino not in ESTADO.unidades:
            return JSONResponse({"ok": False, "aviso": T(
                "Unidade não encontrada.")})
        marcar_ponto()
        u.parent_id = destino
        u.ordem = (len(filhos.get(destino, [])) + 1) * 10
        ESTADO.colapsados.discard(destino)
        commit("mover", uid, "reparent pela grade", {"novo_pai": destino})
    else:
        return JSONResponse({"ok": False, "aviso": T("Ação desconhecida.")})

    esquecer_equipes()
    return JSONResponse({"ok": True, **_dados_da_grade()})


@app.post("/grade/no")
async def grade_no(req: Request):
    """Dobrar, criar filho, duplicar e excluir — o que o botão direito oferece.

    Colapso não entra no ledger: é estado de vista, e é o MESMO do canvas —
    dobrar aqui dobra lá, como já acontecia na tabela.
    """
    form = await req.form()
    uid = str(form.get("uid", ""))
    acao = str(form.get("acao", ""))
    if uid not in ESTADO.unidades:
        return JSONResponse({"ok": False, "aviso": T("Unidade não encontrada.")})

    if acao in ("dobrar", "abrir", "alternar"):
        dobrado = uid in ESTADO.colapsados
        if acao == "dobrar" or (acao == "alternar" and not dobrado):
            ESTADO.colapsados.add(uid)
        else:
            ESTADO.colapsados.discard(uid)
        gravar()
        return JSONResponse({"ok": True, **_dados_da_grade()})

    if (msg := negado(NIVEL_EDITOR, uid)):
        return JSONResponse({"ok": False, "aviso": msg})
    u = ESTADO.unidades[uid]
    if acao == "filho":
        marcar_ponto()
        novo = Unidade(id=novo_id(), codigo=proximo_codigo(),
                       nome=T("Nova unidade"), parent_id=uid,
                       tipo=cargosmod.NIVEL_PISO,
                       ordem=(len(mapa_filhos(ESTADO.unidades).get(uid, [])) + 1) * 10)
        ESTADO.unidades[novo.id] = novo
        ESTADO.colapsados.discard(uid)
        commit("criar", novo.id, "novo filho pela grade", {"pai": uid})
    elif acao == "duplicar":
        if u.parent_id is None:
            return JSONResponse({"ok": False, "aviso": T(
                "A raiz não pode ser duplicada.")})
        marcar_ponto()
        # Cópia sem pessoa alocada e com código próprio, como a do canvas: dois
        # nós com o mesmo código romperiam a chave que a carga usa para
        # reconhecer quem já existe.
        copia = copy.deepcopy(u)
        copia.id = novo_id()
        copia.codigo = proximo_codigo()
        copia.nome = T("{nome} (cópia)", nome=u.nome)
        copia.responsavel = ""
        copia.email = ""
        copia.ordem = u.ordem + 5
        ESTADO.unidades[copia.id] = copia
        renumerar(ESTADO.unidades, u.parent_id)
        commit("criar", copia.id, "duplicar pela grade", {"origem": uid})
    elif acao == "excluir":
        if u.parent_id is None:
            return JSONResponse({"ok": False, "aviso": T(
                "Exclusão recusada: a raiz não pode ser removida.")})
        marcar_ponto()
        for f in mapa_filhos(ESTADO.unidades).get(uid, []):
            f.parent_id = u.parent_id
        del ESTADO.unidades[uid]
        ESTADO.colapsados.discard(uid)
        renumerar(ESTADO.unidades, u.parent_id)
        if ESTADO.selecionado == uid:
            ESTADO.selecionado = None
        if ESTADO.foco == uid:
            ESTADO.foco = None
        commit("inativar", uid, "exclusão pela grade", {"nome": u.nome})
    else:
        return JSONResponse({"ok": False, "aviso": T("Ação desconhecida.")})

    esquecer_equipes()
    return JSONResponse({"ok": True, **_dados_da_grade()})


@app.post("/tabela/colunas", response_class=HTMLResponse)
async def escolher_colunas(req: Request):
    """Quais colunas a grade mostra. Devolve a Tabela inteira.

    A grade toda, e não só o `<tbody>`: o cabeçalho muda junto, e devolver
    corpo sem cabeçalho deixaria a tabela com dez títulos sobre catorze
    colunas — a classe de erro que o `hx-swap` de fragmento parcial produz e
    que ninguém vê até imprimir.
    """
    form = await req.form()
    escolhidas = [c for c, _r, _p in COLUNAS_TABELA if c in form.getlist("col")]
    # Nenhuma marcada volta ao padrão. Uma grade sem coluna nenhuma não é um
    # estado que alguém queira: é o resultado de desmarcar tudo por engano.
    ESTADO.config.colunas_tabela = escolhidas or list(COLUNAS_TABELA_PADRAO)
    gravar()
    return corpo_tabela(req)


@app.post("/filtros/limpar", response_class=HTMLResponse)
def limpar_filtros(req: Request, vista: str = "canvas"):
    """Aqui a vista inteira volta: os controles precisam voltar ao estado vazio."""
    ESTADO.filtros = filtros_vazios()
    gravar()
    return HTMLResponse(html_vista(req, vista))


@app.post("/orientacao", response_class=HTMLResponse)
def alternar(req: Request):
    """Vira a pirâmide. W5-C7: só as coordenadas mudam, o DOM não é remontado.

    Estando na lateral, este botão devolve a pirâmide guardada em vez de
    invertê-la: quem clica em "▲ Convencional" olhando uma árvore indentada
    está pedindo a pirâmide, não o oposto de uma pirâmide que não está vendo.
    """
    if ESTADO.orientacao == "lateral":
        ESTADO.orientacao = ESTADO.orientacao_piramide
    else:
        ESTADO.orientacao = ("vertical" if ESTADO.orientacao == "invertida"
                             else "invertida")
        ESTADO.orientacao_piramide = ESTADO.orientacao
    gravar()
    return canvas(req, oob_orientacao(req) + oob_exportar(req))


@app.post("/orientacao/lateral", response_class=HTMLResponse)
def alternar_lateral(req: Request):
    """Entra e sai da árvore indentada, devolvendo a pirâmide de onde se veio.

    Não é uma terceira pirâmide: é o mesmo organograma lido na vertical, com a
    profundidade andando para a direita. Cabe em (D+1) colunas, contra as
    32 000 px que 267 pessoas ocupam deitadas — é a vista que se lê no celular.
    """
    if ESTADO.orientacao == "lateral":
        ESTADO.orientacao = ESTADO.orientacao_piramide
    else:
        ESTADO.orientacao_piramide = ESTADO.orientacao
        ESTADO.orientacao = "lateral"
    gravar()
    return canvas(req, oob_orientacao(req) + oob_exportar(req))


@app.post("/niveis/{n}", response_class=HTMLResponse)
def alternar_nivel(req: Request, n: str):
    """Marca ou desmarca um nivel. `limpar` tira todos.

    Interruptor, e nao escolha unica: a pergunta "como estao a diretoria e a
    coordenacao, sem o meio do caminho" so tem resposta com mais de um nivel
    marcado ao mesmo tempo.
    """
    marcados = [str(x) for x in ESTADO.filtros.get("profundidade", [])]
    if n == "limpar":
        marcados = []
    elif n.isdigit():
        # Empilha do topo ate o clicado: N3 marca N0..N3. Nao ha como mostrar o
        # nivel 3 sem os de cima — eles sao os ancestrais dele, e sairiam
        # esmaecidos de qualquer jeito. Marcar em faixa e dizer isso na tela.
        alvo = int(n)
        atual = max((int(x) for x in marcados), default=-1)
        # Clicar no ultimo marcado sobe um degrau; clicar acima desce ate ele.
        novo_topo = alvo - 1 if alvo == atual else alvo
        marcados = [str(d) for d in range(novo_topo + 1)]
    ESTADO.filtros["profundidade"] = marcados
    gravar()
    extra = render("_niveis.html", request=req, oob=True,
                   profundidade_max=max(profundidades(desenho_atual()).values()),
                   niveis_marcados=set(marcados))
    return canvas(req, extra)


@app.post("/agrupamento", response_class=HTMLResponse)
def alternar_agrupamento(req: Request):
    """Troca o que e um no: a pessoa, ou o time em que ela esta.

    A selecao cai junto. Ela guarda id de pessoa, e um id de pessoa nao existe
    no desenho por equipe — deixar a gaveta aberta sobre alguem que sumiu da
    tela e como um sistema passa a mostrar duas coisas diferentes ao mesmo
    tempo.
    """
    ESTADO.agrupamento = "pessoa" if ESTADO.agrupamento == "equipe" else "equipe"
    ESTADO.selecionado = None
    gravar()
    # O alvo continua sendo `#canvas` (INT-01). O rotulo do botao e os niveis do
    # palco descrevem o modo e vivem fora dele: voltam fora de banda.
    extra = (render("_bt_agrupamento.html", request=req, oob=True)
             + render("_niveis.html", request=req, oob=True,
                      profundidade_max=max(profundidades(desenho_atual()).values()))
             + oob_painel(req, None))
    return canvas(req, extra)


@app.post("/desfazer", response_class=HTMLResponse)
def desfazer(req: Request):
    if (msg := negado(NIVEL_EDITOR)):
        return recusar(req, msg)
    if not ESTADO.historico:
        return recusar(req, "Nada a desfazer.")
    # O estado de agora vira o "futuro": sem guardar aqui, desfazer seria uma
    # porta de mao unica e o refazer nao teria para onde voltar.
    ESTADO.refazer.append(serializar())
    del ESTADO.refazer[:-MAX_DESFAZER]
    _voltar_para(json.loads(ESTADO.historico.pop()), "desfazer")
    return canvas(req, oob_painel(req, None) + oob_historico(req)
                   + oob_controles(req))


def _voltar_para(instantaneo: dict, acao: str) -> None:
    """Volta o DOMÍNIO no tempo sem voltar o LEDGER junto.

    `marcar_ponto` guarda `serializar()`, que inclui `eventos`; `adotar` troca a
    lista inteira. Desfazer restaurava, portanto, o ledger de antes da edição —
    e a edição desaparecia da trilha. Pior: `verificar_cadeia` recalcula os
    hashes sobre a lista que existe, então a cadeia continuava fechando e a aba
    de Auditoria dizia "íntegra" sobre um histórico do qual um trecho tinha sido
    removido. Um ledger que se pode rebobinar não é append-only, e a assinatura
    dele passa a atestar o que sobrou em vez do que aconteceu.

    Aqui o ledger atravessa a operação intacto e ganha mais uma linha: desfazer
    é um fato, e fato entra na trilha como qualquer outro.
    """
    ledger = list(ESTADO.eventos)
    adotar(instantaneo)
    ESTADO.eventos = ledger
    commit("alterar", "-", acao, {"unidades": len(ESTADO.unidades)})


@app.post("/refazer", response_class=HTMLResponse)
def refazer(req: Request):
    """Refaz o que o desfazer tirou. So existe caminho enquanto ninguem editou:
    `marcar_ponto` limpa a pilha, porque editar abandona aquele futuro."""
    if (msg := negado(NIVEL_EDITOR)):
        return recusar(req, msg)
    if not ESTADO.refazer:
        return recusar(req, "Nada a refazer.")
    ESTADO.historico.append(serializar())
    del ESTADO.historico[:-MAX_DESFAZER]
    _voltar_para(json.loads(ESTADO.refazer.pop()), "refazer")
    return canvas(req, oob_painel(req, None) + oob_historico(req)
                   + oob_controles(req))


@app.post("/restaurar", response_class=HTMLResponse)
def restaurar(req: Request, vista: str = "canvas"):
    if (msg := negado(NIVEL_ADMIN)):
        return (vista_config(req, "dados", alerta(msg)) if vista == "configuracoes"
                else recusar(req, msg))
    marcar_ponto()
    semear(spec=not importador.PLANILHA.exists())
    if vista == "configuracoes":
        return vista_config(req, "dados", alerta("Estrutura recarregada da planilha.")
                            + oob_painel(req, None))
    return canvas(req, oob_painel(req, None))


# ---------------------------------------------------------------------------
# MODULO GERENCIADOR — CONFIGURACOES
# ---------------------------------------------------------------------------
def contexto_prov() -> dict:
    fila = ESTADO.provisionamentos
    indice = provmod.indexar(ESTADO.config.software_por_area)
    return {
        "abertas": provmod.abertas(fila),
        # Do mais recente para tras: quem abre esta aba quer ver o que acabou
        # de acontecer, nao o primeiro pedido de 2026.
        "concluidas": [p for p in reversed(fila)
                       if p.get("situacao") == provmod.CONCLUIDA][:12],
        "catalogo": provmod.normalizar(ESTADO.config.software_por_area),
        "destinatarios": provmod.destinatarios(ESTADO.unidades, mapa_cc()),
        "sem_catalogo": provmod.areas_sem_catalogo(ESTADO.unidades, indice),
        "correio": correio.situacao(),
    }


def contexto_banco() -> dict:
    """O que a carga escreveria E o que o banco já tem — lado a lado.

    Só a previsão respondia "o que eu mandaria", que não é a pergunta de quem
    abre a aba depois de carregar. `real` fica vazio quando não há banco, e a
    tela usa isso para não prometer comparação que não pode fazer.
    """
    previsto = bancomod.contagem_prevista(ESTADO.unidades)
    real = bancomod.contagem_real()
    return {**bancomod.situacao(), "tabelas": bancomod.TABELAS,
            "contagem": previsto, "real": real,
            # Divergente é o que muda de número — e o ledger de fora, que é log
            # e cresce sozinho sem a carga ter nada a ver com isso.
            "divergentes": sorted(
                t for t, n in previsto.items()
                if t in real and real[t] != n),
            "em_dia": bool(real) and all(real.get(t) == n
                                         for t, n in previsto.items()),
            # Saúde do dual-write (Onda DB-5): ligado? última escrita passou?
            "espelho": {"ligado": os.environ.get("ORG_ESPELHO", "0").strip() == "1",
                        "ok": _ESPELHO_SAUDE["ok"], "msg": _ESPELHO_SAUDE["msg"]}}


@app.get("/config/banco/tabela/{tabela}", response_class=HTMLResponse)
def banco_explorar(req: Request, tabela: str, limite: int = 100):
    """Abre uma tabela num modal tela cheia — dados (amostra) e estrutura.

    Só Admin, só leitura, e só tabelas do catálogo: `banco.amostra_tabela` recusa
    qualquer nome fora de `TABELAS`, então a interpolação do nome no SQL é segura
    e ninguém alcança `pg_shadow` pela URL."""
    if (m := negado(NIVEL_ADMIN)):
        return HTMLResponse(alerta(m))
    info = next(((t, o, d) for t, o, d in bancomod.TABELAS if t == tabela), None)
    if info is None:
        return HTMLResponse(alerta("Tabela fora do catálogo."))
    return HTMLResponse(render(
        "_banco_explorar.html", request=req, tabela=tabela,
        origem=info[1], descricao=info[2],
        amostra=bancomod.amostra_tabela(tabela, limite),
        estrutura=bancomod.estrutura_tabela(tabela), limites=(50, 100, 500)))


@app.get("/config/banco/fechar", response_class=HTMLResponse)
def banco_fechar():
    """Fecha o explorador — devolver vazio esvazia o alvo do modal."""
    return HTMLResponse("")


@app.get("/config/banco/verificar", response_class=HTMLResponse)
def banco_verificar(req: Request):
    """Confere tela × banco CAMPO A CAMPO (Onda DB-1), não só a contagem.

    Sobe a estrutura do banco (`carregar_estrutura`) e compara com a memória nó a
    nó. Zero divergência é a prova de que o banco pode virar a fonte da leitura
    (Onda DB-3) sem perder dado. Só Admin, só leitura."""
    if (m := negado(NIVEL_ADMIN)):
        return HTMLResponse(alerta(m))
    return HTMLResponse(render(
        "_banco_verificacao.html", request=req,
        v=bancomod.verificar_espelho(ESTADO.unidades)))


def contexto_organogramas() -> dict:
    """A lista de organogramas e o ativo — para a aba de gestão e o seletor do
    cabeçalho. O nome do ativo vem do Config (a fonte viva do título); o dos
    demais, do registro."""
    reg = orgsmod.ler()
    lista = []
    for o in orgsmod.listar(reg):
        e_ativo = o["slug"] == SLUG_ATIVO
        lista.append({
            "slug": o["slug"],
            "nome": ESTADO.config.titulo if e_ativo else (o.get("nome") or o["slug"]),
            "criado_em": o.get("criado_em"),
            "ativo": e_ativo,
            "nos": len(ESTADO.unidades) if e_ativo else None,
        })
    return {"lista": lista, "ativo": SLUG_ATIVO}


def _sugerir_acesso(u, filhos: dict) -> dict:
    """Acesso sugerido pela HIERARQUIA já definida no sistema: a raiz é Admin;
    quem tem gente abaixo é gestor (Editor sobre a própria subárvore); a folha é
    Visualizador do próprio nó. É a proposta editável — o Admin ajusta as exceções."""
    if u.parent_id is None:
        return {"papel": ADMIN, "escopo": {"tipo": "tudo", "valor": ""}}
    if filhos.get(u.id):
        return {"papel": EDITOR, "escopo": {"tipo": "subarvore", "valor": ""}}
    return {"papel": VIEWER, "escopo": {"tipo": "proprio", "valor": ""}}


def contexto_acessos() -> dict:
    """TODOS os colaboradores, com o acesso de cada um resolvido — a lista da aba
    Permissões, onde se define usuário a usuário o papel, o escopo e os módulos
    visíveis (Fase D). Quem não tem atribuição mostra a SUGESTÃO da hierarquia
    (gestor→Editor da subárvore; folha→Visualizador), editável."""
    us = ESTADO.unidades
    acessos = ESTADO.config.acessos or {}
    prof = profundidades(us)
    filhos = mapa_filhos(us)
    lista = []
    for u in sorted(us.values(),
                    key=lambda x: (prof.get(x.id, 0), sem_acento(x.nome))):
        a = acessos.get(u.id)
        esc = (a or {}).get("escopo") or {}
        sug = _sugerir_acesso(u, filhos)
        lista.append({
            "ref": u.id, "nome": u.nome, "codigo": u.codigo, "cargo": u.cargo,
            "atribuido": a is not None, "papel": (a or {}).get("papel"),
            "tipo": esc.get("tipo", "tudo"), "valor": esc.get("valor", ""),
            "modulos": (a or {}).get("modulos") or [],
            "sug_papel": sug["papel"], "sug_tipo": sug["escopo"]["tipo"],
            "login": bool(u.email) and usuariosmod.existe(u.email),
        })
    return {"lista": lista, "tipos": cfgmod.ESCOPO_TIPOS,
            "eu": acesso_vigente().usuario_id, "modulos": MODULOS,
            "contas": usuariosmod.listar(),
            "emails_nos": {(u.email or "").lower() for u in us.values() if u.email},
            "modulos_total": len(MODULOS), "atribuidos": len(acessos),
            "verticais": sorted({u.vertical for u in us.values() if u.vertical}),
            "departamentos": sorted({u.area for u in us.values() if u.area})}


def contexto_config(aba: str = "geral") -> dict:
    prof = profundidades(ESTADO.unidades)
    reg = ESTADO.config.centros_custo
    return {
        "aba": aba, "perfis": PERFIS, "campos_card": CAMPOS_CARD,
        "organogramas": contexto_organogramas(),
        "acessos": contexto_acessos(),
        "banco": contexto_banco(), "prov": contexto_prov(),
        "eventos": list(reversed(ESTADO.eventos)), "cadeia": verificar_cadeia(),
        "acessos_log": list(reversed(ESTADO.acessos_log)),   # mais recente primeiro
        "campos_fixos": cfgmod.CAMPOS_FIXOS, "limites": cfgmod.LIMITES_TOKENS,
        "tipos_unidade": ESTADO.config.rotulos_nivel,
        "centros": [(c, _uso_cc().get(centros.chave(c["n3"], c["departamento"]), 0))
                    for c in reg],
        "colunas_cc": centros.COLUNAS, "tipos_cc": centros.TIPOS_CC,
        "verticais": centros.verticais(reg),
        "uso_cc": _uso_cc(), "conciliacao": centros.conciliar(ESTADO.unidades, reg),
        "unidades_ordenadas": sorted(ESTADO.unidades.values(),
                                     key=lambda u: (prof.get(u.id, 0),
                                                    sem_acento(u.nome))),
        "importacao": ESTADO.importacao,
        "sincronizacao": ESTADO.sincronizacao,
        "m365_ligado": m365mod.configurado(), "m365_campo": m365mod.atributo_cc(),
        "total": len(ESTADO.unidades), "cadeia": verificar_cadeia(),
        "colunas_planilha": importador.COLUNAS,
        # campo interno -> título da coluna. O diff do passo 2 mostrava o nome
        # do atributo Python (`centro_custo`, `vinculo`), que com seis campos
        # novos deixaria de ser adivinhável.
        "titulo_do_campo": {c.campo: c.titulo for c in importador.COLUNAS
                            if c.campo},
        **contexto_cargos(),
    }


def contexto_cargos() -> dict:
    c = ESTADO.config
    uso = cargosmod.uso(ESTADO.unidades)
    por_nivel: dict[str, int] = {}
    for u in ESTADO.unidades.values():
        por_nivel[u.tipo] = por_nivel.get(u.tipo, 0) + 1
    catalogo = [dict(item, pessoas=uso.get(cargosmod.chave(item["cargo"]), 0))
                for item in c.catalogo_cargos]
    return {
        "niveis": c.niveis, "cores_disponiveis": cargosmod.CORES_NIVEL,
        "nivel_piso": cargosmod.NIVEL_PISO,
        "uso_nivel": por_nivel, "regras": c.regras_cargo,
        "catalogo": sorted(catalogo,
                           key=lambda x: (-x["pessoas"], sem_acento(x["cargo"]))),
        "sem_catalogo": sum(1 for u in ESTADO.unidades.values()
                            if u.cargo
                            and cargosmod.chave(u.cargo) not in c.indice_cargos),
        "divergencias": cargosmod.divergencias(ESTADO.unidades,
                                               c.catalogo_cargos, c.regras_cargo),
    }


def _uso_cc() -> dict[str, int]:
    """Pessoas por linha do cadastro, na chave (N3, Departamento)."""
    uso: dict[str, int] = {}
    for m in mapa_cc().values():
        if m["departamento_cc"]:
            k = centros.chave(m["n3"], m["departamento_cc"])
            uso[k] = uso.get(k, 0) + 1
    return uso


def vista_config(req: Request, aba: str = "geral", extra: str = "") -> HTMLResponse:
    return HTMLResponse(render("_config.html", request=req,
                               **contexto_config(aba)) + extra)


@app.post("/config/geral", response_class=HTMLResponse)
def config_geral(req: Request, titulo: str = Form(""), tenant: str = Form(""),
                 orientacao_padrao: str = Form("invertida"),
                 tema: str = Form("claro"),
                 profundidade_aberta: int = Form(1)):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "geral", alerta(negado(NIVEL_ADMIN)))
    c = ESTADO.config
    c.titulo = titulo.strip()[:60] or c.titulo
    c.tenant = tenant.strip()[:40]
    c.orientacao_padrao = orientacao_padrao
    c.tema = tema
    c.profundidade_aberta = profundidade_aberta
    c.sanear()
    commit("alterar", "-", "configuração geral", {"titulo": c.titulo})
    return vista_config(req, "geral", alerta("Configuração salva."))


@app.post("/organogramas/criar")
def org_criar(req: Request, nome: str = Form("")):
    """Cria um organograma vazio e passa a mostrá-lo. Só Admin. Recarrega a
    página inteira — trocar de organograma muda tudo (canvas, config, banco)."""
    if (m := negado(NIVEL_ADMIN)):
        return vista_config(req, "organogramas", alerta(m))
    if not nome.strip():
        return vista_config(req, "organogramas",
                            alerta(T("Dê um nome ao novo organograma.")))
    criar_organograma(nome.strip())
    return Response(status_code=204, headers={"HX-Redirect": "/"})


@app.post("/organogramas/trocar")
def org_trocar(req: Request, slug: str = Form("")):
    """Passa a mostrar outro organograma (ativo global). Só Admin."""
    if (m := negado(NIVEL_ADMIN)):
        return vista_config(req, "organogramas", alerta(m))
    if not trocar_organograma(slug):
        return vista_config(req, "organogramas",
                            alerta(T("Organograma não encontrado.")))
    return Response(status_code=204, headers={"HX-Redirect": "/"})


@app.post("/organogramas/renomear", response_class=HTMLResponse)
def org_renomear(req: Request, slug: str = Form(""), nome: str = Form("")):
    if (m := negado(NIVEL_ADMIN)):
        return vista_config(req, "organogramas", alerta(m))
    orgsmod.salvar(orgsmod.renomear(orgsmod.ler(), slug, nome))
    if slug == SLUG_ATIVO and nome.strip():        # o ativo tira o título do Config
        ESTADO.config.titulo = nome.strip()[:60]
        ESTADO.config.sanear()
        gravar()
    return vista_config(req, "organogramas", alerta(T("Organograma renomeado.")))


@app.post("/organogramas/excluir")
def org_excluir(req: Request, slug: str = Form("")):
    if (m := negado(NIVEL_ADMIN)):
        return vista_config(req, "organogramas", alerta(m))
    if not excluir_organograma(slug):
        return vista_config(req, "organogramas",
                            alerta(T("Não dá para excluir o último organograma.")))
    return Response(status_code=204, headers={"HX-Redirect": "/"})


@app.post("/config/tema", response_class=HTMLResponse)
def config_tema(req: Request, tema: str = Form("claro")):
    """Aparencia e preferencia de exibicao, nao mutacao de dominio: qualquer
    perfil troca, e nao entra no ledger. O cliente ja pintou antes de chamar —
    isto so persiste para a proxima sessao."""
    ESTADO.config.tema = tema
    ESTADO.config.sanear()
    gravar()
    return HTMLResponse("")


RECORTE_CANVAS = "canvas"


def escopo_visivel(recorte: str = "") -> tuple[set | None, str]:
    """(ids que a pessoa pode ver, rótulo do recorte).

    None = leitura total. A MarIA nunca vê mais que quem pergunta, e quem
    decide isso e a mesma guarda de escopo que já rege a edição (SEC-03) — não
    uma regra paralela que pode divergir dela.

    `recorte="canvas"` estreita para o que está desenhado na tela. Estreita e
    só: o resultado é sempre subconjunto do que a guarda já permitia, inclusive
    para o administrador — para quem o padrão é `None` e o canvas devolve um
    conjunto de verdade.
    """
    # A guarda de LEITURA (`escopo_leitura`): o mesmo escopo da edição, mas a flag
    # `ver_tudo` pode abrir a leitura inteira sem abrir a edição. `None` = leitura
    # total (Admin, escopo 'tudo' ou ver_tudo).
    permitidos = escopo_leitura()
    if permitidos is None:
        rotulo = T("organograma inteiro")
    elif not permitidos:
        rotulo = T("nenhum")
    else:
        rotulo = _rotulo_escopo()
    if recorte != RECORTE_CANVAS:
        return permitidos, rotulo
    return recorte_do_canvas(permitidos)


def recorte_do_canvas(permitidos: set | None) -> tuple[set, str]:
    """O que está desenhado agora, cruzado com o que é permitido.

    A tela do canvas é do servidor: foco, colapso e filtro vivem no ESTADO, e
    `layout_atual` é o único produtor de geometria (ADR-011). Perguntar ao
    desenho é o que garante que o recorte não divirja do que a pessoa está
    vendo — uma segunda travessia com as mesmas regras erraria no primeiro
    filtro novo que alguém acrescentasse só de um lado.

    Nunca devolve None. Conjunto vazio aqui significa "nada visível", e é isso
    que a MarIA precisa receber: `None` significaria o organograma inteiro.
    """
    desenhados = {n["id"] for n in layout_atual(None, com_cabecalho=False)["nos"]}
    ids = desenhados if permitidos is None else desenhados & permitidos
    total = len(ESTADO.unidades)
    base = ESTADO.unidades.get(ESTADO.foco)
    if base:
        return ids, T("visível no canvas a partir de {unidade} ({n} de {total})",
                      unidade=base.nome, n=len(ids), total=total)
    return ids, T("visível no canvas ({n} de {total})", n=len(ids), total=total)


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def contexto_maria(ultima: dict | None = None, agente: dict | None = None,
                   recorte: str = "") -> dict:
    ids, rotulo = escopo_visivel(recorte)
    return {
        "configurada": mariamod.configurada(),
        "recorte": recorte,
        "modelo": ESTADO.config.maria_modelo or mariamod.modelo_padrao(),
        "modelos": mariamod.modelos(),
        "capacidades": mariamod.CAPACIDADES,
        "escopo": rotulo,
        "resumo": mariamod.resumo(ESTADO.assistencias),
        "historico": list(reversed(ESTADO.assistencias))[:40],
        "ultima": ultima,
        "agente": agente,
        "propostas": list(ESTADO.propostas.values()),
    }


def quem_chama(req: Request) -> str:
    """A chave do freio de custo da MarIA: o e-mail da sessão (ou o nó)."""
    carga = sessao_atual(req) or {}
    return (carga.get("sub") or acesso_vigente().usuario_id or "anonimo").lower()


@app.post("/maria/perguntar", response_class=HTMLResponse)
async def maria_perguntar(req: Request):
    """Uma pergunta à MarIA. Toda resposta vira registro no histórico."""
    form = await req.form()
    capacidade = str(form.get("capacidade", mariamod.DESCREVER))
    pergunta = str(form.get("pergunta", ""))[:mariamod.PERGUNTA_MAX]
    # O modelo do formulário só vale para Admin e só se for um dos conhecidos:
    # escolher o modelo mais caro é escolher a fatura.
    modelo = str(form.get("modelo", ""))
    if negado(NIVEL_ADMIN) or modelo not in mariamod.modelos():
        modelo = ""
    modelo = modelo or ESTADO.config.maria_modelo
    recorte = str(form.get("recorte", ""))
    ids, rotulo = escopo_visivel(recorte)

    r = mariamod.perguntar(
        pergunta,
        mariamod.contexto(ESTADO.unidades, mapa_cc(), ESTADO.config, ids),
        idioma=ESTADO.config.idioma, capacidade=capacidade, modelo=modelo,
        quem=quem_chama(req))

    registro = mariamod.assistencia(pergunta, r, usuario_atual(), capacidade,
                                    ESTADO.config.idioma, rotulo)
    ESTADO.assistencias.append(registro)
    commit("criar", "-", "assistência da MarIA",
           {"capacidade": capacidade, "ok": registro["ok"],
            "modelo": registro["modelo"], "custo_usd": registro["custo_usd"]})
    return HTMLResponse(render("_maria.html", request=req, vista="maria",
                               maria=contexto_maria(registro, recorte=recorte)))


# Poço de sugestões. As cinco primeiras não têm parâmetro e valem sempre — são
# a reserva que garante cinco opções mesmo num recorte vazio, onde toda
# contagem dá zero. As de baixo só entram quando o número existe de verdade no
# recorte: sugestão que cita um número inventado ensina a desconfiar das outras.
# Poço de sugestões sem parâmetro. Quarenta e cinco perguntas que fazem sentido
# em qualquer recorte, inclusive num vazio — é a reserva que garante cinco
# opções quando toda contagem dá zero.
#
# São muitas de propósito. Com cinco fixas, quem abre a gaveta todo dia vê
# sempre as mesmas cinco e para de ler; com quarenta e cinco sorteadas, a
# vitrine muda e a pessoa descobre que a MarIA responde perguntas que ela ainda
# não tinha pensado em fazer. É a diferença entre um menu e um convite.
#
# Cada uma é uma pergunta que o contexto agregado consegue mesmo responder:
# hierarquia, centro de custo, cargo, vínculo, vertical e as divergências entre
# o declarado e o cadastrado. Nenhuma pede dado que o sistema não tem — sugestão
# que leva a "não sei responder" gasta uma chamada e ensina a não usar a lista.
SUGESTOES = (
    # --- vãos e concentração da hierarquia ---------------------------------
    "Quais departamentos têm gestor sem subordinados diretos?",
    "Onde a estrutura declarada difere do cadastro de centros de custo?",
    "Quais níveis estão concentrados demais numa só vertical?",
    "Onde há pessoa respondendo para fora da própria vertical?",
    "Que cargos aparecem repetidos com nomes diferentes?",
    "Qual gestor tem mais gente reportando direto, e isso é sustentável?",
    "Existe nível hierárquico que só tem uma pessoa em toda a vertical?",
    "Onde a cadeia de comando tem mais degraus do que precisa?",
    "Que áreas dependem de uma pessoa só para não parar?",
    "Quais times têm mais chefia do que gente executando?",
    "Há alguém respondendo a um gestor de nível igual ou inferior ao seu?",
    "Onde a profundidade da árvore destoa do resto da empresa?",
    "Que departamentos cresceram sem ganhar um nível de coordenação?",
    "Qual é o caminho mais longo da base até a diretoria?",
    "Existe vertical inteira sem ninguém em nível de gerência?",
    # --- centros de custo e vocabulário ------------------------------------
    "Que centros de custo têm gente de mais de um departamento?",
    "Quais departamentos aparecem em mais de um centro de custo?",
    "Há centro de custo cadastrado que nenhuma pessoa usa?",
    "Que pessoas estão num centro de custo que não casa com o time delas?",
    "Quais times têm nome parecido e talvez sejam o mesmo?",
    "Que centros de custo concentram mais gente do que a vertical inteira?",
    "Onde o nome do departamento na planilha discorda do cadastro?",
    "Quais verticais de negócio estão sem natureza definida?",
    "Que centros de custo estão sem mnemônico N5 preenchido?",
    "Há departamento com pessoas em verticais diferentes?",
    # --- cargos, vínculo e composição --------------------------------------
    "Que cargos existem em mais de uma vertical, e com que peso em cada?",
    "Quais cargos têm uma pessoa só na empresa inteira?",
    "Onde há mais de um cargo com a mesma responsabilidade?",
    "Que proporção do quadro está fora do vínculo CLT, e onde?",
    "Quais áreas concentram terceiros ou estagiários?",
    "Que cargos de liderança estão em nível de execução, ou o contrário?",
    "Onde o cargo escrito não corresponde ao nível hierárquico atribuído?",
    "Quais times não têm ninguém em nível sênior?",
    "Que cargos aparecem só na diretoria e em nenhum outro nível?",
    "Como o quadro se distribui entre as naturezas de centro de custo?",
    # --- accountabilities e cobertura --------------------------------------
    "Que accountabilities aparecem em mais de uma pessoa ao mesmo tempo?",
    "Quais áreas não têm nenhuma accountability declarada?",
    "Onde há accountability delegada sem quem execute abaixo?",
    "Que responsabilidades ficaram sem dono depois da última mudança?",
    "Quais pessoas acumulam mais accountabilities do que a média?",
    # --- leitura de negócio -------------------------------------------------
    "Se eu tirasse uma vertical, que estrutura de apoio ficaria ociosa?",
    "Onde a estrutura está mais pesada do que o tamanho do time justifica?",
    "Que mudança deixaria a árvore mais rasa sem perder controle?",
    "Quais departamentos estão fora das quatro faixas da apresentação?",
    "O que mais chama atenção neste recorte que eu não perguntei?",
)
# As calculadas: citam um número do recorte, então só entram quando o número
# existe de verdade. Ficam num mapa, e não soltas dentro da função, porque é
# delas que a varredura de idiomas tira as chaves — molde escrito no meio do
# código não seria traduzido, e a sugestão sairia em português no meio da tela
# em inglês. A chave nomeia a pergunta; o texto mora aqui uma vez só.
#
# Uma pergunta só, e não "afirmação ponto pergunta". A vitrine é um convite a
# perguntar: escrita como "O nível Célula tem 179 pessoas. Falta liderança?",
# metade do botão gastava-se contando à pessoa algo que ela já vê na tabela, e
# a pergunta chegava no fim, pequena. O número continua lá — dentro da própria
# pergunta, que é onde ele serve de gancho em vez de servir de aviso.
SUGESTOES_CALCULADAS = {
    "gestor_sem_time":
        "Os {n} gestores sem subordinados diretos justificam o nível que ocupam?",
    "cc_orfao":
        "Por onde começar com as {n} pessoas cujo centro de custo não resolve?",
    "departamento_pesado":
        "A carga está bem distribuída, com {dep} concentrando {n} das {total} "
        "pessoas do recorte?",
    "nivel_pesado":
        "Falta ou sobra liderança no nível {nivel}, que tem {n} pessoas no recorte?",
    "vertical_pesada":
        "A vertical {vertical}, com {n} pessoas, está coberta em todos os níveis?",
}
QUANTAS_SUGESTOES = 5

# Quantas das cinco vagas as calculadas podem tomar. Duas, e não cinco.
#
# Elas nascem do recorte, então numa base cheia as cinco sobreviviam e ocupavam
# a vitrine inteira — sempre as mesmas cinco, sempre na mesma ordem, porque a
# escolha era determinística: ordenava por contagem e cortava. Quem abre a
# gaveta todo dia via a mesma tela e parava de ler, e as quarenta e cinco
# perguntas do poço nunca apareciam.
#
# Duas é o equilíbrio: sobra o bastante para a vitrine mudar de verdade a cada
# abertura, e as duas que ficam continuam citando um número do recorte — que é
# o que mostra à pessoa que a MarIA já leu o que está na tela dela.
TETO_CALCULADAS = 2


def _lideranca() -> set[str]:
    """Níveis acima do piso. Sai da configuração porque o admin edita a régua."""
    niveis = {n["codigo"]: n["ordem"] for n in ESTADO.config.niveis}
    piso = niveis.get(cargosmod.NIVEL_PISO, 40)
    return {c for c, ordem in niveis.items() if ordem < piso}


def sugestoes(ids: set | None) -> list[str]:
    """Cinco perguntas que fazem sentido *neste* recorte.

    Calculadas, não sorteadas de uma lista fixa: uma sugestão que cita o número
    certo mostra à pessoa que a MarIA já leu o recorte dela. Tudo sai do que já
    está em memória — chamar o modelo para gerar sugestão cobraria uma
    requisição toda vez que a gaveta abrisse.
    """
    cfg = ESTADO.config
    us = [u for u in ESTADO.unidades.values() if ids is None or u.id in ids]
    dentro = {u.id for u in us}
    mapa = mapa_cc()
    filhos = mapa_filhos(ESTADO.unidades)
    contas = mariamod.agregados(us, cfg, mapa)
    chefia = _lideranca()

    def topo(dicionario: dict) -> tuple[str, int]:
        for chave, n in dicionario.items():
            if chave and chave != "—" and n:
                return chave, n
        return "", 0

    sem_time = sum(1 for u in us if u.tipo in chefia
                   and not [f for f in filhos.get(u.id, []) if f.id in dentro])
    orfas = sum(1 for u in us
                if (mapa.get(u.id) or {}).get("casamento") == "sem correspondência")
    dep, n_dep = topo(contas["por_departamento"])
    nivel, n_nivel = topo(contas["por_nivel"])
    vertical, n_vert = topo(contas["por_vertical"])

    # (chave do molde, parâmetros, peso). Peso é a contagem: pergunta sobre o
    # que é grande no recorte vem antes da que é marginal. A chave nomeia a
    # pergunta, então trocar a ordem daqui não desalinha nada.
    #
    # O rótulo do nível é interface (o admin edita, e o catálogo traduz);
    # departamento e vertical são dado do cliente e ficam como estão.
    candidatos = [
        ("gestor_sem_time", {"n": sem_time}, sem_time),
        ("cc_orfao", {"n": orfas}, orfas),
        ("departamento_pesado", {"dep": dep, "n": n_dep, "total": len(us)},
         n_dep if dep else 0),
        ("nivel_pesado", {"nivel": T(nivel), "n": n_nivel},
         n_nivel if nivel else 0),
        ("vertical_pesada", {"vertical": vertical, "n": n_vert},
         n_vert if vertical else 0),
    ]
    # Dois é o piso: com n=1 toda frase precisaria de singular, e "1 pessoas"
    # nos três idiomas custaria dez moldes a mais para dizer o que a reserva
    # já diz sem número nenhum.
    elegiveis = [(chave, params, peso) for chave, params, peso in candidatos
                 if peso >= 2]
    # Sorteadas entre as elegíveis, mas com o peso ainda pesando: o truque de
    # Efraimidis-Spirakis dá uma chave `aleatório ** (1/peso)` a cada uma e fica
    # com as maiores. É sorteio sem reposição em que a concentração de 179
    # pessoas aparece muito mais que a de duas — ordenar por peso e cortar
    # mostraria só a de 179, para sempre; sortear liso trataria as duas como se
    # dissessem a mesma coisa.
    elegiveis.sort(key=lambda c: -(random.random() ** (1 / c[2])))
    saida = [T(SUGESTOES_CALCULADAS[chave], **params)
             for chave, params, _ in elegiveis[:TETO_CALCULADAS]]
    # A reserva completa o que faltar: cinco opções sempre, inclusive no recorte
    # vazio, onde nenhuma calculada sobrevive.
    #
    # Sorteio de verdade, e não rotação por índice guardado: guardar o índice
    # seria estado novo no servidor para decidir a ordem de uma vitrine, e a
    # ordem de uma vitrine não é dado do domínio. O preço é RNF-02 não valer
    # aqui — mas RNF-02 rege o *desenho*, que precisa sair idêntico duas vezes
    # para o papel bater com a tela. A gaveta de conversa não é desenho.
    for molde in random.sample(SUGESTOES, len(SUGESTOES)):
        if len(saida) >= QUANTAS_SUGESTOES:
            break
        saida.append(T(molde))
    # Embaralha o conjunto todo: sem isto as calculadas ficariam sempre nas duas
    # primeiras linhas, e a vitrine mudaria de conteúdo mantendo a mesma forma —
    # o olho reconhece a forma antes de ler o texto.
    random.shuffle(saida)
    return saida[:QUANTAS_SUGESTOES]


def capacidade_de_conversa(pedida: str) -> str:
    """A capacidade escolhida na gaveta, se ela for oferecida ali.

    Filtro de entrada, e não de exibição: o `capacidade` chega por formulário,
    e formulário é coisa que se forja. `Executar` e `agir sozinha` não passam —
    a primeira exige aprovação humana por ação, a segunda está fora de escopo.
    """
    oferecidas = {c[0] for c in mariamod.DE_CONVERSA}
    return pedida if pedida in oferecidas else mariamod.DESCREVER


def contexto_chat(recorte: str = "", capacidade: str = "") -> dict:
    ids, rotulo = escopo_visivel(recorte)
    return {"configurada": mariamod.configurada(), "escopo": rotulo,
            "recorte": recorte, "mensagens": ESTADO.conversa[-40:],
            "capacidades": mariamod.DE_CONVERSA,
            "capacidade": capacidade_de_conversa(capacidade),
            # O template só mostra sugestões com a conversa vazia; calcular a
            # cada turno pagaria uma varredura das unidades por mensagem.
            "sugestoes": sugestoes(ids) if not ESTADO.conversa else ()}


@app.get("/maria/chat", response_class=HTMLResponse)
def chat_abrir(req: Request, recorte: str = "", capacidade: str = ""):
    return HTMLResponse(render("_maria_chat.html", request=req,
                               chat=contexto_chat(recorte, capacidade)))


@app.post("/maria/chat", response_class=HTMLResponse)
async def chat_perguntar(req: Request):
    """Um turno da conversa.

    O histórico vai junto no prompt, truncado nos últimos turnos: sem ele a
    MarIA responderia cada pergunta como se fosse a primeira, e conversa que
    não lembra do que foi dito não é conversa.
    """
    form = await req.form()
    pergunta = str(form.get("pergunta", "")).strip()[:mariamod.PERGUNTA_MAX]
    recorte = str(form.get("recorte", ""))
    # A capacidade vem da gaveta e passa pelo filtro: ela muda o prompt, e um
    # valor forjado no formulário não pode virar autoridade que a tela não deu.
    capacidade = capacidade_de_conversa(str(form.get("capacidade", "")))
    if not pergunta:
        return HTMLResponse(render("_maria_chat.html", request=req,
                                   chat=contexto_chat(recorte, capacidade)))

    ids, rotulo = escopo_visivel(recorte)
    ESTADO.conversa.append({"papel": "eu", "texto": pergunta[:2000],
                            "ok": True})

    anteriores = [m for m in ESTADO.conversa[-9:-1]]
    fio = "\n".join(f"{'Pergunta' if m['papel'] == 'eu' else 'MarIA'}: {m['texto']}"
                     for m in anteriores)
    entrada = (f"Conversa anterior:\n{fio}\n\nPergunta atual: {pergunta}"
               if fio else pergunta)

    r = mariamod.perguntar(
        entrada, mariamod.contexto(ESTADO.unidades, mapa_cc(), ESTADO.config, ids),
        idioma=ESTADO.config.idioma, capacidade=capacidade,
        modelo=ESTADO.config.maria_modelo, quem=quem_chama(req))

    registro = mariamod.assistencia(pergunta, r, usuario_atual(),
                                    capacidade, ESTADO.config.idioma,
                                    rotulo)
    ESTADO.conversa.append({
        "papel": "maria", "ok": bool(r.get("ok")),
        "texto": r.get("texto") or r.get("mensagem", ""),
        # A bolha guarda o id da assistência para o PDF sair do próprio turno,
        # sem obrigar a pessoa a caçar a resposta no módulo depois.
        "aid": registro.get("id", ""),
        "modelo": r.get("modelo", ""), "entrada": r.get("entrada", 0),
        "saida": r.get("saida", 0), "custo_usd": r.get("custo_usd", 0.0)})
    # Teto da conversa guardada: o fio é contexto, não arquivo. O histórico
    # completo e auditável vive em `assistencias`.
    del ESTADO.conversa[:-60]

    ESTADO.assistencias.append(registro)
    commit("criar", "-", "assistência da MarIA",
           {"capacidade": capacidade, "ok": bool(r.get("ok")),
            "custo_usd": r.get("custo_usd", 0.0)})
    return HTMLResponse(render("_maria_chat.html", request=req,
                               chat=contexto_chat(recorte, capacidade)))


@app.post("/maria/agente", response_class=HTMLResponse)
async def maria_agente(req: Request):
    """Capacidade 5: a MarIA devolve a estrutura proposta. Nada é criado."""
    if negado(NIVEL_EDITOR):
        return HTMLResponse(render("_maria.html", request=req, vista="maria",
                                   maria=contexto_maria())
                            + alerta(negado(NIVEL_EDITOR)))
    form = await req.form()
    pedido = str(form.get("pedido", "")).strip()
    recorte = str(form.get("recorte", ""))
    # Um cálculo só: `ids` alimenta o contexto E o conjunto `nomes` que
    # validar_proposta usa para recusar um `sob` inventado. Recalcular ali
    # deixaria o agente ancorar unidade nova sob quem a pessoa não estava vendo.
    ids, rotulo = escopo_visivel(recorte)
    us = [u for u in ESTADO.unidades.values()
          if ids is None or u.id in ids]

    r = mariamod.propor_estrutura(
        pedido, mariamod.contexto(ESTADO.unidades, mapa_cc(), ESTADO.config, ids),
        niveis={n["codigo"] for n in ESTADO.config.niveis if n.get("ativo", True)},
        nomes={u.nome for u in us},
        idioma=ESTADO.config.idioma, modelo=ESTADO.config.maria_modelo,
        quem=quem_chama(req))

    ESTADO.assistencias.append(mariamod.assistencia(
        pedido, r, usuario_atual(), mariamod.PLANEJAR, ESTADO.config.idioma,
        rotulo))
    commit("criar", "-", "assistência da MarIA",
           {"capacidade": "agente", "ok": bool(r.get("ok")),
            "custo_usd": r.get("custo_usd", 0.0)})

    proposta = None
    if r.get("ok") and r.get("proposta"):
        # A proposta é guardada com identificador: aprovar depois se refere a
        # ESTA lista, já lida. Chamar o modelo de novo na aprovação faria a
        # pessoa aprovar um texto e o sistema criar outro.
        pid = uuid.uuid4().hex[:12]
        proposta = {**r["proposta"], "id": pid, "pedido": pedido,
                    "problemas": r.get("problemas", []),
                    "quando": agora_iso()}
        ESTADO.propostas[pid] = proposta
        gravar()
    return HTMLResponse(render("_maria.html", request=req, vista="maria",
                               maria=contexto_maria(
                                   agente={"resultado": r, "proposta": proposta})))


@app.post("/maria/agente/{pid}/aplicar", response_class=HTMLResponse)
def maria_agente_aplicar(req: Request, pid: str):
    """Capacidade 6: a pessoa leu a proposta e aprovou. Agora o sistema cria.

    Um único ponto de desfazer cobre a criação inteira — meia estrutura nova
    num organograma de 267 pessoas é pior do que nenhuma.
    """
    def recusa(texto):
        return HTMLResponse(render("_maria.html", request=req, vista="maria",
                                   maria=contexto_maria()) + alerta(texto))

    if (msg := negado(NIVEL_EDITOR)):
        return recusa(msg)
    proposta = ESTADO.propostas.get(pid)
    if not proposta:
        return recusa(T("Proposta não encontrada ou já aplicada."))

    sob = proposta.get("sob") or ""
    pai = next((u for u in ESTADO.unidades.values() if u.nome == sob), None)
    if pai is None:
        # A proposta nomeia o pai por NOME. Não achando, isto caía na raiz em
        # silêncio: a pessoa aprovava "quatro vagas sob Engenharia" e as quatro
        # nasciam no topo do organograma. Renomear a unidade entre a proposta e
        # a aprovação basta para o nome deixar de casar — e o silêncio fazia a
        # diferença passar despercebida até alguém abrir o canvas.
        if sob:
            return recusa(T("A unidade “{sob}” não existe mais. A proposta foi "
                            "feita sobre outra estrutura — descarte e peça de "
                            "novo.", sob=sob))
        pai = raiz(ESTADO.unidades)
    # A guarda de escopo só vale com o ALVO em mãos: `negado(NIVEL_EDITOR)` sem
    # `uid` confere o perfil e passa direto pelo escopo. Um editor restrito a um
    # galho aprovava a proposta e as unidades nasciam sob a raiz, fora do que
    # ele pode editar — a única rota de criação que escapava do funil.
    if (msg := negado(NIVEL_EDITOR, pai.id)):
        return recusa(msg)
    marcar_ponto()
    criadas = []
    for item in proposta["unidades"]:
        for _ in range(item["quantidade"]):
            novo = Unidade(
                id=novo_id(), codigo=proximo_codigo(),
                nome=T("A definir"), tipo=item["nivel"],
                parent_id=pai.id,
                ordem=(len(mapa_filhos(ESTADO.unidades).get(pai.id, [])) + 1) * 10,
                cargo=item["cargo"], area=proposta.get("departamento", ""))
            ESTADO.unidades[novo.id] = novo
            criadas.append(novo.id)
    ESTADO.colapsados.discard(pai.id)
    del ESTADO.propostas[pid]
    commit("criar", pai.id, "estrutura criada pelo agente Organograma",
           {"proposta": pid, "time": proposta.get("time"),
            "unidades": len(criadas), "sob": pai.nome,
            "pedido": proposta.get("pedido", "")[:200]})
    return HTMLResponse(render("_maria.html", request=req, vista="maria",
                               maria=contexto_maria())
                        + alerta(T("{n} unidade(s) criadas sob {pai}. "
                                   "Desfazer reverte a criação inteira.",
                                   n=len(criadas), pai=pai.nome)))


@app.post("/maria/agente/{pid}/descartar", response_class=HTMLResponse)
def maria_agente_descartar(req: Request, pid: str):
    ESTADO.propostas.pop(pid, None)
    gravar()
    return HTMLResponse(render("_maria.html", request=req, vista="maria",
                               maria=contexto_maria())
                        + alerta(T("Proposta descartada.")))


@app.post("/maria/chat/limpar", response_class=HTMLResponse)
def chat_limpar(req: Request, recorte: str = ""):
    """Limpa o fio da conversa, não o histórico: o registro auditável de cada
    resposta continua em Assistências."""
    ESTADO.conversa = []
    gravar()
    return HTMLResponse(render("_maria_chat.html", request=req,
                               chat=contexto_chat(recorte)))


def _assistencia(aid: str) -> dict | None:
    return next((a for a in ESTADO.assistencias if a.get("id") == aid), None)


@app.get("/maria/assistencia/{aid}", response_class=HTMLResponse)
def maria_assistencia(req: Request, aid: str):
    """Resposta inteira, formatada. O histórico mostra o recorte; aqui se lê."""
    a = _assistencia(aid)
    if a is None:
        return HTMLResponse("", status_code=404)
    return HTMLResponse(render("_maria_detalhe.html", request=req, a=a,
                               corpo=mariamod.formatar(a.get("resposta", "")),
                               validacao=gramatica.validar(
                                   a.get("resposta", ""), a.get("idioma", "pt-BR"))))


@app.get("/maria/assistencia/{aid}/pdf")
def maria_pdf(req: Request, aid: str):
    """RQ-808/809/810: PDF no backend, com procedência, atrás do portão.

    O portão bloqueia a EMISSÃO, não a resposta — ela continua na tela e no
    histórico. O que não sai é o artefato que circula fora do sistema e que
    ninguém relê.
    """
    a = _assistencia(aid)
    if a is None:
        return Response(status_code=404)
    texto = gramatica.limpar(a.get("resposta", ""))
    validacao = gramatica.validar(texto, a.get("idioma", ESTADO.config.idioma))
    if not validacao["libera"]:
        registrar("alterar", "-", "emissão de PDF bloqueada pelo portão",
                  {"assistencia": aid, "achados": len(validacao["achados"])})
        return HTMLResponse(render("_maria_detalhe.html", request=req, a=a,
                                   corpo=mariamod.formatar(a.get("resposta", "")),
                                   validacao=validacao), status_code=422)

    correlacao = uuid.uuid4().hex[:16]
    meta = {
        "titulo": T("MarIA · {capacidade}",
                    capacidade=T(a.get("capacidade", "").capitalize())),
        "subtitulo": f"{ESTADO.config.tenant} · {a.get('escopo', '')} · "
                     f"{a.get('quando', '')[:10]}",
        "rodape": f"GPlanSiS|Peoples · MarIA · {ESTADO.config.tenant}",
        "idioma": a.get("idioma", ESTADO.config.idioma),
        "procedencia": relatoriomod.procedencia(
            {**a, "resposta": texto}, f"GET /maria/assistencia/{aid}/pdf",
            correlacao),
    }
    dados = relatoriomod.gerar({**a, "resposta": texto}, meta, validacao)
    registrar("alterar", "-", "relatório PDF da MarIA emitido",
              {"assistencia": aid, "correlacao_id": correlacao,
               "bytes": len(dados), "gramatica": validacao["gramatica"]})
    gravar()
    return Response(dados, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="maria-{aid}.pdf"'})


@app.post("/maria/modelo", response_class=HTMLResponse)
def maria_modelo(req: Request, modelo: str = Form("")):
    if negado(NIVEL_ADMIN):
        return HTMLResponse(render("_maria.html", request=req, vista="maria",
                                   maria=contexto_maria())
                            + alerta(negado(NIVEL_ADMIN)))
    ESTADO.config.maria_modelo = modelo if modelo in mariamod.modelos() else ""
    gravar()
    commit("alterar", "-", "modelo da MarIA", {"modelo": modelo})
    return HTMLResponse(render("_maria.html", request=req, vista="maria",
                               maria=contexto_maria())
                        + alerta(T("Modelo salvo: {modelo}", modelo=modelo)))


# --- diretorio social -------------------------------------------------------
@app.post("/mural/{uid}", response_class=HTMLResponse)
async def mural_publicar(req: Request, uid: str):
    """Reconhecimento ou feedback publico no card de alguem.

    Exige estar identificado: sem autor a mensagem viraria anonima, e anonimo
    e outra ferramenta - com outro cuidado - que nao e esta.
    """
    if uid not in (universo_visivel() or ESTADO.unidades):
        return recusar(req, T("Unidade inexistente."))   # fora do escopo: não publica
    autor = usuario_atual()
    if not autor:
        return HTMLResponse(corpo_painel(req, uid, com_canvas=False)
                            + alerta(T("Vincule-se a uma pessoa da estrutura "
                                       "para publicar: o mural é assinado.")))
    form = await req.form()
    msg = socialmod.publicar(uid, autor, str(form.get("texto", "")),
                             str(form.get("tipo", socialmod.RECONHECIMENTO)),
                             str(form.get("valor", "")))
    if msg is None:
        return HTMLResponse(corpo_painel(req, uid, com_canvas=False)
                            + alerta(T("Escreva algo antes de publicar.")))
    # Ponto de desfazer, como toda mutação que grava. Sem ele o mural entrava
    # no estado sem entrar na pilha, e o Desfazer seguinte — de uma edição
    # QUALQUER, feita antes — restaurava um instantâneo anterior à mensagem e a
    # engolia. Quem publicou via a mensagem sumir por causa de um botão que
    # nada tinha a ver com ela.
    marcar_ponto()
    ESTADO.mural.append(msg)
    socialmod.aparar(ESTADO.mural, uid)
    commit("criar", uid, "mensagem no mural",
           {"tipo": msg["tipo"], "autor": msg["autor"]})
    return HTMLResponse(corpo_painel(req, uid, com_canvas=False,
                                     vista_origem=str(form.get("vista", "")),
                                     contexto_origem=str(form.get("contexto", ""))))


@app.delete("/mural/{uid}/{mid}", response_class=HTMLResponse)
def mural_remover(req: Request, uid: str, mid: str):
    """Autor apaga o que escreveu; destinatario tira do proprio card."""
    quem = (usuario_atual() or {}).get("id", "")
    admin = acesso_vigente().perfil == ADMIN
    # O ponto é marcado ANTES de remover: `marcar_ponto` guarda o estado de
    # agora, e depois da remoção o "agora" já não tem a mensagem para restaurar.
    marcar_ponto()
    if not socialmod.remover(ESTADO.mural, mid, quem, admin):
        # Recusou: o ponto marcado não corresponde a mutação nenhuma, e um
        # Desfazer que não desfaz nada é pior que nenhum — ele consome a vez.
        ESTADO.historico.pop()
        return HTMLResponse(corpo_painel(req, uid, com_canvas=False)
                            + alerta(T("Só o autor, a pessoa do card ou um "
                                       "administrador podem remover.")))
    commit("inativar", uid, "mensagem removida do mural", {"mensagem": mid})
    return HTMLResponse(corpo_painel(req, uid, com_canvas=False))


# --- provisionamento de TI --------------------------------------------------
@app.post("/config/prov/software", response_class=HTMLResponse)
async def prov_software(req: Request):
    """Catalogo de software por area. Salvar aqui nao mexe em pedido aberto:
    o pedido guardou os nomes no instante em que foi criado, e chamado que
    muda sozinho depois de aberto nao e auditavel."""
    if negado(NIVEL_ADMIN):
        return vista_config(req, "prov", alerta(negado(NIVEL_ADMIN)))
    form = await req.form()
    linhas = []
    for i in form.getlist("area_i"):
        linhas.append({"area": str(form.get(f"area_{i}", "")),
                       "softwares": str(form.get(f"softwares_{i}", ""))})
    nova = str(form.get("nova_area", "")).strip()
    if nova:
        linhas.append({"area": nova,
                       "softwares": str(form.get("nova_softwares", ""))})
    ESTADO.config.software_por_area = provmod.normalizar(linhas)
    commit("alterar", "-", "catálogo de software por departamento",
           {"areas": len(ESTADO.config.software_por_area)})
    return vista_config(req, "prov", alerta(
        T("Catálogo salvo com {n} departamento(s).",
          n=len(ESTADO.config.software_por_area))))


@app.post("/config/prov/testar-email", response_class=HTMLResponse)
def prov_testar_email(req: Request):
    """Envio de teste para os destinatários de TI. Existe para descobrir que o
    SMTP está errado antes de um pedido de verdade se perder."""
    if negado(NIVEL_ADMIN):
        return vista_config(req, "prov", alerta(negado(NIVEL_ADMIN)))
    alvo = provmod.destinatarios(ESTADO.unidades, mapa_cc())
    ok, detalhe = correio.enviar(
        alvo, T("[GPlanSiS|Peoples] Teste de envio"),
        T("Se você recebeu esta mensagem, o provisionamento de TI consegue "
          "avisar por e-mail."))
    return vista_config(req, "prov", alerta(
        T("E-mail de teste enviado: {detalhe}", detalhe=detalhe) if ok
        else T("Envio recusado: {detalhe}", detalhe=detalhe)))


@app.post("/config/prov/{pid}/concluir", response_class=HTMLResponse)
def prov_concluir(req: Request, pid: str):
    if negado(NIVEL_EDITOR):
        return vista_config(req, "prov", alerta(negado(NIVEL_EDITOR)))
    quem = (usuario_atual() or {}).get("nome", "")
    if not provmod.concluir(ESTADO.provisionamentos, pid, quem):
        return vista_config(req, "prov", alerta(
            T("Pedido não encontrado ou já concluído.")))
    commit("alterar", "-", "provisionamento de TI concluído", {"pedido": pid})
    return vista_config(req, "prov", alerta(T("Pedido concluído.")))


# --- banco de dados ---------------------------------------------------------
def negado_superadmin(req: Request) -> str | None:
    """Recusa, ou None. Dump do banco é do OPERADOR do sistema: com o login
    exigido, só o superadmin; sem login (modo de mesa), Admin."""
    if (m := negado(NIVEL_ADMIN)):
        return m
    if acesso.exigir_login():
        carga = sessao_atual(req)
        if not (carga and acesso.e_superadmin(carga.get("sub", ""))):
            return T("Ação negada: só o operador do sistema (superadmin) baixa o banco.")
    return None


@app.get("/banco/schema.sql")
def baixar_schema(req: Request):
    if (m := negado_superadmin(req)):
        return JSONResponse({"erro": m}, status_code=403)
    return Response(bancomod.ddl(), media_type="application/sql",
                    headers={"Content-Disposition":
                             'attachment; filename="schema.sql"'})


@app.get("/banco/carga.sql")
def baixar_carga(req: Request):
    """O SQL sai do estado vigente, não de um script fixo: script fixo estaria
    errado na primeira edição depois de escrito.

    A carga é a base de RH inteira (nome, e-mail, matrícula, admissão, gênero,
    nascimento): só o superadmin baixa, e a saída fica no ledger."""
    if (m := negado_superadmin(req)):
        return JSONResponse({"erro": m}, status_code=403)
    registrar("alterar", "-", "exportação SQL (carga do banco)", {"formato": "sql"})
    sql = bancomod.sql_carga(ESTADO.unidades, ESTADO.config)
    return Response(sql, media_type="application/sql",
                    headers={"Content-Disposition":
                             'attachment; filename="organograma-carga.sql"'})


@app.post("/config/banco/testar", response_class=HTMLResponse)
def banco_testar(req: Request):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "banco", alerta(negado(NIVEL_ADMIN)))
    ok, msg = bancomod.testar()
    return vista_config(req, "banco", alerta(
        T("Conexão bem-sucedida: {detalhe}", detalhe=msg) if ok
        else T("Conexão recusada: {detalhe}", detalhe=msg)))


@app.post("/config/banco/schema", response_class=HTMLResponse)
def banco_schema(req: Request):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "banco", alerta(negado(NIVEL_ADMIN)))
    ok, msg = bancomod.aplicar(bancomod.ddl())
    if ok:
        commit("criar", "-", "schema do banco aplicado", {"alvo": "postgres"})
    return vista_config(req, "banco", alerta(
        T("Schema aplicado.") if ok
        else T("Schema recusado: {detalhe}", detalhe=msg)))


@app.post("/config/banco/carga", response_class=HTMLResponse)
def banco_carga(req: Request):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "banco", alerta(negado(NIVEL_ADMIN)))
    contagem = bancomod.contagem_prevista(ESTADO.unidades)
    ok, msg = bancomod.aplicar(
        bancomod.sql_carga(ESTADO.unidades, ESTADO.config))
    if ok:
        commit("alterar", "-", "organograma escrito no banco", contagem)
    return vista_config(req, "banco", alerta(
        T("Organograma escrito: {n} unidades.", n=contagem["org.unidade"]) if ok
        else T("Escrita recusada: {detalhe}", detalhe=msg)))


@app.post("/config/idioma")
def config_idioma(req: Request, idioma: str = Form(idiomasmod.PADRAO)):
    """Troca o idioma da interface.

    Diferente do tema, isto não pode ser resolvido no cliente: a tela inteira é
    montada no servidor, então o idioma novo só existe depois de um novo render.
    `HX-Refresh` manda o navegador recarregar — é o único jeito de garantir que
    nenhum fragmento antigo, em outra língua, sobreviva na página.
    """
    ESTADO.config.idioma = idiomasmod.valido(idioma)
    ESTADO.config.sanear()
    alinhar_idioma()
    gravar()
    return Response(status_code=204, headers={"HX-Refresh": "true"})


@app.post("/config/campos", response_class=HTMLResponse)
async def config_campos(req: Request):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "card", alerta(negado(NIVEL_ADMIN)))
    form = await req.form()
    c = ESTADO.config
    c.campos = [k for k in CAMPOS_CARD if form.get(f"campo_{k}")]
    for nome in ("card_w", "gap_h", "gap_v", "max_itens"):
        if form.get(nome):
            setattr(c, nome, int(form[nome]))
    c.sanear()
    commit("alterar", "-", "campos visíveis do card", {"campos": c.campos})
    return vista_config(req, "card", alerta("Aparência do card atualizada."))


@app.post("/config/permissoes", response_class=HTMLResponse)
def config_permissoes(req: Request, perfil: str = Form(VIEWER),
                      escopo_id: str = Form(""), usuario_id: str = Form("")):
    """Enquanto nao ha OIDC (DT-02), o perfil vigente e escolhido aqui.

    A guarda que ele alimenta e a mesma que um `sub` de JWT alimentaria.
    Rebaixar o proprio perfil e permitido - subir de volta exige admin, entao
    quem se rebaixa perde a chave. E o comportamento correto de um seletor de
    perfil, e por isso ele avisa antes.

    NOTA: escreve o `ESTADO.config` GLOBAL — o FALLBACK de dev/testes, nao a
    sessao de ninguem. Em producao, com login por cookie, `acesso_vigente()`
    devolve a copia por-requisicao e este valor global fica sombreado (inocuo).
    """
    if negado(NIVEL_ADMIN):
        return vista_config(req, "permissoes", alerta(negado(NIVEL_ADMIN)))
    c = ESTADO.config
    c.perfil = perfil if perfil in PERFIS else c.perfil
    c.escopo_id = escopo_id or None
    c.usuario_id = usuario_id if usuario_id in ESTADO.unidades else None
    c.sanear()
    commit("alterar", "-", "perfil e escopo de edição",
           {"perfil": c.perfil, "escopo": c.escopo_id})
    return vista_config(req, "permissoes",
                        alerta(T("Perfil vigente: {perfil}.",
                                 perfil=T(PERFIS[c.perfil]["rotulo"]))))


@app.get("/config/acessos/editar", response_class=HTMLResponse)
def acessos_editar(req: Request, ref: str = ""):
    """O editor de acesso de UMA pessoa (papel + escopo + módulos visíveis), aberto
    a partir da lista. Só Admin."""
    if (m := negado(NIVEL_ADMIN)):
        return HTMLResponse(alerta(m))
    u = ESTADO.unidades.get(ref)
    if u is None:
        return HTMLResponse(alerta(T("Colaborador não encontrado.")))
    acessos = ESTADO.config.acessos or {}
    a = acessos.get(ref) or {}
    esc = a.get("escopo") or {}
    # Sem atribuição, o editor abre já preenchido com a SUGESTÃO da hierarquia —
    # editável. Com atribuição, abre com o que está gravado.
    sug = _sugerir_acesso(u, mapa_filhos(ESTADO.unidades))
    dados = {"ref": ref, "nome": u.nome, "codigo": u.codigo,
             "atribuido": ref in acessos,
             "papel": a.get("papel") or sug["papel"],
             "tipo": esc.get("tipo") or sug["escopo"]["tipo"],
             "valor": esc.get("valor") or "", "modulos": a.get("modulos") or [],
             "ver_tudo": bool(a.get("ver_tudo")),
             "email": u.email, "login": bool(u.email) and usuariosmod.existe(u.email),
             "precisa_trocar": bool(u.email) and usuariosmod.precisa_trocar(u.email),
             "minimo": usuariosmod.SENHA_MINIMA}
    return HTMLResponse(render(
        "_acesso_editor.html", request=req, a=dados, perfis=PERFIS, modulos=MODULOS,
        verticais=sorted({x.vertical for x in ESTADO.unidades.values() if x.vertical}),
        departamentos=sorted({x.area for x in ESTADO.unidades.values() if x.area})))


@app.post("/config/acessos/hierarquia", response_class=HTMLResponse)
def acessos_hierarquia(req: Request):
    """Define de uma vez o acesso de TODOS os colaboradores sem atribuição, pela
    hierarquia (gestor→Editor da subárvore; folha→Visualizador). Não sobrescreve
    quem já foi definido à mão. Tudo continua editável pessoa a pessoa. Só Admin."""
    if (m := negado(NIVEL_ADMIN)):
        return vista_config(req, "permissoes", alerta(m))
    us = ESTADO.unidades
    filhos = mapa_filhos(us)
    c = ESTADO.config
    acessos = dict(c.acessos or {})
    novos = 0
    for u in us.values():
        if u.parent_id is None or u.id in acessos:   # raiz fora; não clobber manual
            continue
        sug = _sugerir_acesso(u, filhos)
        acessos[u.id] = {"papel": sug["papel"], "escopo": sug["escopo"],
                         "modulos": []}
        novos += 1
    eu = acesso_vigente().usuario_id             # o operador DESTA sessão
    if eu and eu in us and eu not in acessos:
        acessos[eu] = {"papel": ADMIN,          # trava anti-lockout
                       "escopo": {"tipo": "tudo", "valor": ""},
                       "modulos": []}
    c.acessos = acessos
    c.sanear()
    commit("alterar", "-", "acessos pela hierarquia", {"novos": novos})
    return vista_config(req, "permissoes",
                        alerta(T("{n} acesso(s) definido(s) pela hierarquia.", n=novos)))


@app.post("/config/acessos/salvar", response_class=HTMLResponse)
def acessos_salvar(req: Request, ref: str = Form(""), papel: str = Form(VIEWER),
                   escopo_tipo: str = Form("tudo"), escopo_valor: str = Form(""),
                   modulos: list[str] = Form(default=[]), ver_tudo: str = Form("")):
    """Atribui papel + escopo + módulos visíveis a um colaborador (RBAC por
    pessoa, Fase D). Só Admin. Resolve-se no login da pessoa (aplicar_acesso)."""
    if (m := negado(NIVEL_ADMIN)):
        return vista_config(req, "permissoes", alerta(m))
    if ref not in ESTADO.unidades:
        return vista_config(req, "permissoes",
                            alerta(T("Escolha um colaborador válido.")))
    c = ESTADO.config
    acessos = dict(c.acessos or {})
    acessos[ref] = {"papel": papel,
                    "escopo": {"tipo": escopo_tipo, "valor": escopo_valor.strip()},
                    "modulos": [m for m in modulos if m in MODULOS_CHAVES],
                    "ver_tudo": bool(ver_tudo)}
    # Trava anti-lockout: quem está montando os acessos (Admin logado) é mantido
    # como Administrador se ainda não tiver a própria entrada — senão popular os
    # acessos dos OUTROS trancaria o próprio autor no próximo login.
    eu = acesso_vigente().usuario_id             # o operador DESTA sessão
    if eu and eu in ESTADO.unidades and eu not in acessos:
        acessos[eu] = {"papel": ADMIN, "escopo": {"tipo": "tudo", "valor": ""}}
    c.acessos = acessos
    c.sanear()
    commit("alterar", ref, "acesso atribuído",
           {"papel": c.acessos[ref]["papel"], "escopo": escopo_tipo})
    return vista_config(req, "permissoes", alerta(T("Acesso atribuído.")))


@app.post("/config/acessos/senha", response_class=HTMLResponse)
def acessos_senha(req: Request, ref: str = Form(""), email: str = Form(""),
                  senha: str = Form(""), temporaria: str = Form("")):
    """Define (ou redefine) a senha de acesso de uma pessoa. Só Admin. `ref` é
    o nó do organograma (usa o e-mail dele); `email` serve para contas fora da
    estrutura — o operador, por exemplo. `temporaria` obriga a troca no
    primeiro login. A credencial não toca o RBAC: papel e escopo seguem em
    `acessos`."""
    if (m := negado(NIVEL_ADMIN)):
        return vista_config(req, "permissoes", alerta(m))
    u = ESTADO.unidades.get(ref) if ref else None
    if ref and u is None:
        return vista_config(req, "permissoes", alerta(T("Escolha um colaborador válido.")))
    alvo = usuariosmod.normalizar(u.email if u else email)
    if not alvo:
        return vista_config(req, "permissoes", alerta(T(
            "Este colaborador não tem e-mail; cadastre um e-mail antes de definir a senha.")))
    if not acesso.dominio_valido(alvo):
        return vista_config(req, "permissoes", alerta(T(
            "Use o e-mail da organização ({dominios}).",
            dominios=", ".join(acesso.dominios()) or "@")))
    try:
        usuariosmod.definir_senha(alvo, senha, precisa_trocar=bool(temporaria),
                                  por=(usuario_atual() or {}).get("email") or "admin")
    except ValueError as erro:
        return vista_config(req, "permissoes", alerta(_recusa_de_senha(erro)))
    commit("alterar", ref or "-", "senha de acesso definida",
           {"email": alvo, "temporaria": bool(temporaria)})
    return vista_config(req, "permissoes",
                        alerta(T("Senha definida para {email}.", email=alvo)))


@app.post("/config/acessos/senha/remover", response_class=HTMLResponse)
def acessos_senha_remover(req: Request, ref: str = Form(""), email: str = Form("")):
    """Remove a credencial: a pessoa deixa de conseguir entrar. Não mexe no RBAC.
    Trava anti-lockout: ninguém remove a própria senha por aqui."""
    if (m := negado(NIVEL_ADMIN)):
        return vista_config(req, "permissoes", alerta(m))
    u = ESTADO.unidades.get(ref) if ref else None
    alvo = usuariosmod.normalizar(u.email if u else email)
    eu = usuariosmod.normalizar((sessao_atual(req) or {}).get("sub", ""))
    if alvo and alvo == eu:
        return vista_config(req, "permissoes",
                            alerta(T("Você não pode remover a própria senha.")))
    if alvo and usuariosmod.remover(alvo):
        commit("alterar", ref or "-", "senha de acesso removida", {"email": alvo})
        return vista_config(req, "permissoes",
                            alerta(T("Senha removida de {email}.", email=alvo)))
    return vista_config(req, "permissoes", alerta(T("Essa conta não tem senha definida.")))


@app.post("/config/acessos/remover", response_class=HTMLResponse)
def acessos_remover(req: Request, ref: str = Form("")):
    if (m := negado(NIVEL_ADMIN)):
        return vista_config(req, "permissoes", alerta(m))
    c = ESTADO.config
    if ref in (c.acessos or {}):
        c.acessos = {k: v for k, v in c.acessos.items() if k != ref}
        c.sanear()
        commit("alterar", ref, "acesso removido", {})
    return vista_config(req, "permissoes", alerta(T("Acesso removido.")))


@app.post("/config/cc", response_class=HTMLResponse)
async def config_cc(req: Request):
    """Salva o cadastro inteiro de uma vez: a tabela e pequena e editar linha a
    linha por requisicao daria 84 round-trips para uma revisao de rotina."""
    if negado(NIVEL_ADMIN):
        return vista_config(req, "cc", alerta(negado(NIVEL_ADMIN)))
    form = await req.form()
    linhas = []
    for i in form.getlist("linha"):
        linhas.append({c: str(form.get(f"{c}_{i}", "")).strip()[:80]
                       for c in centros.CAMPOS}
                      | {"ativo": bool(form.get(f"ativo_{i}"))})
    if str(form.get("novo_departamento", "")).strip():
        linhas.append({c: str(form.get(f"novo_{c}", "")).strip()[:80]
                       for c in centros.CAMPOS} | {"ativo": True})
    ESTADO.config.centros_custo = centros.normalizar(linhas)
    commit("alterar", "-", "cadastro de centros de custo",
           {"linhas": len(ESTADO.config.centros_custo)})
    return vista_config(req, "cc", alerta(T(
        "Cadastro salvo com {n} linha(s).", n=len(ESTADO.config.centros_custo))))


@app.post("/config/cc/redescobrir", response_class=HTMLResponse)
def config_cc_redescobrir(req: Request):
    """Acrescenta os pares (N3, Departamento) que a estrutura usa e o cadastro
    ainda nao tem. Nao apaga nem sobrescreve o que ja esta la."""
    if negado(NIVEL_ADMIN):
        return vista_config(req, "cc", alerta(negado(NIVEL_ADMIN)))
    antes = len(ESTADO.config.centros_custo)
    ESTADO.config.centros_custo = centros.descobrir(ESTADO.unidades,
                                                    ESTADO.config.centros_custo)
    novas = len(ESTADO.config.centros_custo) - antes
    commit("alterar", "-", "centros de custo descobertos a partir da estrutura",
           {"novas": novas})
    return vista_config(req, "cc", alerta(
        T("{n} linha(s) acrescentada(s) a partir da estrutura.", n=novas)
        if novas else T("Nenhuma equipe da estrutura está fora do cadastro.")))


@app.post("/config/cc/referencia", response_class=HTMLResponse)
def config_cc_referencia(req: Request):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "cc", alerta(negado(NIVEL_ADMIN)))
    ESTADO.config.centros_custo = centros.descobrir(ESTADO.unidades,
                                                    centros.referencia())
    commit("alterar", "-", "cadastro de centros de custo restaurado da referência",
           {"linhas": len(ESTADO.config.centros_custo)})
    return vista_config(req, "cc", alerta("Cadastro restaurado da tabela de referência."))


@app.get("/centros.csv")
def export_centros():
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator=chr(10))
    w.writerow([rotulo for _, rotulo, _ in centros.COLUNAS] + ["ativo", "pessoas"])
    uso = _uso_cc()
    for c in ESTADO.config.centros_custo:
        w.writerow([c[campo] for campo, _, _ in centros.COLUNAS]
                   + ["sim" if c["ativo"] else "não",
                      uso.get(centros.chave(c["n3"], c["departamento"]), 0)])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="centros-de-custo.csv"'})


@app.post("/config/niveis", response_class=HTMLResponse)
async def config_niveis(req: Request):
    """Rotulo, cor e ordem dos niveis. O codigo e imutavel: ele casa com o enum
    org.tipo_unidade do banco e com o `tipo` gravado em cada unidade."""
    if negado(NIVEL_ADMIN):
        return vista_config(req, "cargos", alerta(negado(NIVEL_ADMIN)))
    form = await req.form()
    novos = []
    for codigo in form.getlist("nivel"):
        novos.append(cargosmod.nivel(
            codigo=codigo,
            rotulo=str(form.get(f"rotulo_{codigo}", "")).strip(),
            cor=str(form.get(f"cor_{codigo}", "cinza")),
            ordem=int(form.get(f"ordem_{codigo}") or 99),
            ativo=bool(form.get(f"ativo_{codigo}"))))
    ESTADO.config.niveis = cargosmod.normalizar_niveis(novos)
    ESTADO.config.sanear()
    commit("alterar", "-", "niveis hierarquicos",
           {"niveis": len(ESTADO.config.niveis)})
    return vista_config(req, "cargos", alerta("Níveis salvos."))


@app.post("/config/cargos", response_class=HTMLResponse)
async def config_cargos(req: Request):
    """Catalogo cargo -> nivel. Salvar nao reclassifica: aplicar e acao a parte."""
    if negado(NIVEL_ADMIN):
        return vista_config(req, "cargos", alerta(negado(NIVEL_ADMIN)))
    form = await req.form()
    codigos = {n["codigo"] for n in ESTADO.config.niveis}
    catalogo = []
    for i in form.getlist("cargo_i"):
        nome = str(form.get(f"cargo_{i}", "")).strip()
        alvo = str(form.get(f"nivel_{i}", ""))
        if nome and alvo in codigos:
            catalogo.append({"cargo": nome[:120], "nivel": alvo,
                             "origem": "manual"})
    ESTADO.config.catalogo_cargos = sorted(
        {cargosmod.chave(c["cargo"]): c for c in catalogo}.values(),
        key=lambda c: sem_acento(c["cargo"]))
    commit("alterar", "-", "catalogo de cargos",
           {"cargos": len(ESTADO.config.catalogo_cargos)})
    return vista_config(req, "cargos", alerta(T(
        "{n} cargo(s) salvos. Use \u201cAplicar \u00e0s unidades\u201d para "
        "reclassificar a estrutura.", n=len(ESTADO.config.catalogo_cargos))))


@app.post("/config/cargos/novo", response_class=HTMLResponse)
async def config_cargo_novo(req: Request):
    """Cria um cargo no catalogo pelo modal.

    Nao reclassifica ninguem, igual ao salvar: quem decide reescrever o nivel
    de 267 unidades e o botao Aplicar. Cargo repetido e recusado — o catalogo
    e indexado por `chave()` e uma duplicata silenciosa sumiria na deduplicacao
    do salvar, dando a impressao de que a criacao funcionou.
    """
    if negado(NIVEL_ADMIN):
        return vista_config(req, "cargos", alerta(negado(NIVEL_ADMIN)))
    form = await req.form()
    nome = str(form.get("cargo", "")).strip()[:120]
    alvo = str(form.get("nivel", ""))
    codigos = {n["codigo"] for n in ESTADO.config.niveis}

    if not nome:
        return vista_config(req, "cargos", alerta("Informe o nome do cargo."))
    if alvo not in codigos:
        return vista_config(req, "cargos", alerta("Nível inválido."))
    existe = next((c for c in ESTADO.config.catalogo_cargos
                   if cargosmod.chave(c["cargo"]) == cargosmod.chave(nome)), None)
    if existe:
        return vista_config(req, "cargos", alerta(T(
            "“{cargo}” já está no catálogo como {nivel}. "
            "Edite a linha em vez de criar outra.",
            cargo=existe["cargo"],
            nivel=T(ESTADO.config.rotulos_nivel.get(existe["nivel"],
                                                    existe["nivel"])))))

    ESTADO.config.catalogo_cargos = sorted(
        ESTADO.config.catalogo_cargos
        + [{"cargo": nome, "nivel": alvo, "origem": "manual"}],
        key=lambda c: sem_acento(c["cargo"]))
    commit("criar", "-", f"cargo {nome}", {"nivel": alvo})
    usando = sum(1 for u in ESTADO.unidades.values()
                 if cargosmod.chave(u.cargo) == cargosmod.chave(nome))
    return vista_config(req, "cargos", alerta(
        T("Cargo “{nome}” criado como {nivel}.", nome=nome,
          nivel=T(ESTADO.config.rotulos_nivel.get(alvo, alvo)))
        + " "
        + (T("{n} pessoa(s) usam esse cargo — “Aplicar às unidades” "
             "reclassifica.", n=usando) if usando
           else T("Nenhuma pessoa usa esse cargo ainda."))))


@app.post("/config/cargos/regras", response_class=HTMLResponse)
async def config_regras(req: Request):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "cargos", alerta(negado(NIVEL_ADMIN)))
    form = await req.form()
    regras = []
    for i in form.getlist("regra_i"):
        regras.append(cargosmod.regra(
            padrao=str(form.get(f"padrao_{i}", "")).strip(),
            nivel=str(form.get(f"rnivel_{i}", "")),
            ordem=int(form.get(f"rordem_{i}") or 99),
            ativo=bool(form.get(f"rativo_{i}"))))
    nova = str(form.get("nova_padrao", "")).strip()
    if nova:
        regras.append(cargosmod.regra(nova, str(form.get("nova_nivel", "")),
                                      int(form.get("nova_ordem") or 99)))
    ESTADO.config.regras_cargo = cargosmod.normalizar_regras(
        regras, {n["codigo"] for n in ESTADO.config.niveis})
    commit("alterar", "-", "regras de classificacao de cargo",
           {"regras": len(ESTADO.config.regras_cargo)})
    return vista_config(req, "cargos", alerta("Regras salvas."))


@app.post("/config/cargos/descobrir", response_class=HTMLResponse)
def config_cargos_descobrir(req: Request):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "cargos", alerta(negado(NIVEL_ADMIN)))
    antes = len(ESTADO.config.catalogo_cargos)
    ESTADO.config.catalogo_cargos = catalogo_cargos()
    novos = len(ESTADO.config.catalogo_cargos) - antes
    commit("alterar", "-", "cargos descobertos a partir da estrutura",
           {"novos": novos})
    return vista_config(req, "cargos", alerta(
        T("{n} cargo(s) acrescentado(s), classificados pelas regras.", n=novos)
        if novos
        else T("Nenhum cargo da estrutura est\u00e1 fora do cat\u00e1logo.")))


@app.post("/config/cargos/aplicar", response_class=HTMLResponse)
def config_cargos_aplicar(req: Request):
    """Reclassifica as unidades pelo catalogo. Acao explicita: muda a cor de
    todo card e a altura das faixas do desenho."""
    if negado(NIVEL_ADMIN):
        return vista_config(req, "cargos", alerta(negado(NIVEL_ADMIN)))
    marcar_ponto()
    r = cargosmod.aplicar(ESTADO.unidades, ESTADO.config.catalogo_cargos,
                          ESTADO.config.regras_cargo)
    commit("alterar", "-", "reclassificacao de nivel pelo catalogo de cargos",
           {"alteradas": r["alteradas"]})
    return vista_config(req, "cargos", alerta(
        T("{n} unidade(s) reclassificada(s).", n=r["alteradas"]) if r["alteradas"]
        else T("Nenhuma unidade divergia do cat\u00e1logo.")))


# --- assistente de carga (passo a passo) ----------------------------------
@app.post("/config/importar/analisar", response_class=HTMLResponse)
async def importar_analisar(req: Request, arquivo: UploadFile = File(...)):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "dados", alerta(negado(NIVEL_ADMIN)))
    conteudo = await arquivo.read()
    try:
        alinhar_idioma()
        # Os níveis vão junto porque a coluna Nível tem domínio fechado, e o
        # domínio é do tenant: o importador não conhece `Config`, e uma escala
        # embutida nele ignoraria o nível que alguém criou em Configurações.
        ESTADO.importacao = importador.analisar(
            conteudo, ESTADO.unidades, arquivo.filename or "planilha.xlsx",
            niveis=[n for n in ESTADO.config.niveis if n.get("ativo", True)])
    except Exception as erro:                                   # noqa: BLE001
        ESTADO.importacao = None
        return vista_config(req, "dados",
                            alerta(T("Planilha recusada: {erro}", erro=erro)))
    return vista_config(req, "dados")


@app.post("/config/importar/aplicar", response_class=HTMLResponse)
def importar_aplicar(req: Request, criar: str = Form(""), atualizar: str = Form(""),
                     remover: str = Form("")):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "dados", alerta(negado(NIVEL_ADMIN)))
    if not ESTADO.importacao:
        return vista_config(req, "dados", alerta("Nenhuma análise em andamento."))
    marcar_ponto()
    # Quem nasce pela planilha sem coluna Nível recebe o nível pelo MESMO
    # critério de quem nasce pelo canvas: catálogo de cargos, depois regras, e
    # o piso por último. A escada fixa do importador só vale na linha de
    # comando, onde não há configuração para consultar.
    resumo = importador.aplicar(
        ESTADO.importacao, ESTADO.unidades, criar=bool(criar),
        atualizar=bool(atualizar), remover=bool(remover), novo_id=novo_id,
        classificador=lambda cargo: cargosmod.classificar(
            cargo, ESTADO.config.indice_cargos, ESTADO.config.regras_cargo),
        piso_codigo=ESTADO.config.piso_codigo)
    ESTADO.config.piso_codigo = resumo.pop("piso_codigo", 0)
    # O cadastro primeiro ganha as linhas que a estrutura passou a usar, e só
    # então recebe o N5 que a planilha declara: pivotar antes acharia chave que
    # ainda não existe e não preencheria nada.
    ESTADO.config.centros_custo = cadastro_cc(ESTADO.config.centros_custo)
    ESTADO.config.centros_custo, avisos_cc = centros.pivotar(
        ESTADO.importacao.get("linhas") or [], ESTADO.config.centros_custo)
    ESTADO.config.catalogo_cargos = catalogo_cargos()
    ESTADO.importacao = None
    ESTADO.selecionado = None
    aplicar_colapso_inicial()
    commit("alterar", "-", "carga assistida da planilha", resumo)
    return vista_config(req, "dados", alerta(" ".join([T(
        "Carga aplicada: {criados} criada(s), {atualizados} atualizada(s), "
        "{removidos} removida(s).", criados=resumo["criados"],
        atualizados=resumo["atualizados"], removidos=resumo["removidos"])]
        + avisos_cc)))


@app.post("/config/importar/cancelar", response_class=HTMLResponse)
def importar_cancelar(req: Request):
    ESTADO.importacao = None
    return vista_config(req, "dados")


# --- sincronizacao com o Microsoft 365 -------------------------------------
@app.post("/config/m365/analisar", response_class=HTMLResponse)
def m365_analisar(req: Request):
    """Busca o Graph e monta o diff. Nao escreve nada — nem no organograma,
    nem no MS365."""
    if negado(NIVEL_ADMIN):
        return vista_config(req, "dados", alerta(negado(NIVEL_ADMIN)))
    alinhar_idioma()
    try:
        usuarios = m365mod.buscar_usuarios()
        ESTADO.sincronizacao = m365mod.analisar(usuarios, ESTADO.unidades)
    except Exception as erro:                                   # noqa: BLE001
        # A falha aqui e quase sempre de permissao ou segredo, e a frase do
        # proprio Entra e a que resolve o chamado. Nao ha o que desfazer: a
        # leitura nao chegou a tocar o estado.
        ESTADO.sincronizacao = None
        return vista_config(req, "dados", alerta(T(
            "Microsoft 365 não respondeu: {erro}",
            erro=m365mod.erro_legivel(erro))))
    return vista_config(req, "dados")


@app.post("/config/m365/aplicar", response_class=HTMLResponse)
def m365_aplicar(req: Request, atualizar: str = Form(""),
                 preencher: str = Form("")):
    if negado(NIVEL_ADMIN):
        return vista_config(req, "dados", alerta(negado(NIVEL_ADMIN)))
    if not ESTADO.sincronizacao:
        return vista_config(req, "dados", alerta("Nenhuma análise em andamento."))
    marcar_ponto()
    resumo = m365mod.aplicar(ESTADO.sincronizacao, ESTADO.unidades,
                             atualizar=bool(atualizar), preencher=bool(preencher))
    # Mexer no CC muda a vertical de quem foi tocado: o cadastro reconcilia de
    # novo, senao o filtro de vertical ficaria apontando para o CC antigo.
    ESTADO.config.centros_custo = cadastro_cc(ESTADO.config.centros_custo)
    ESTADO.sincronizacao = None
    commit("alterar", "-", "sincronização de centro de custo com o Microsoft 365",
           resumo)
    return vista_config(req, "dados", alerta(T(
        "Sincronização aplicada: {n} centro(s) de custo atualizado(s) a partir "
        "do Microsoft 365.", n=resumo["alterados"])))


@app.post("/config/m365/cancelar", response_class=HTMLResponse)
def m365_cancelar(req: Request):
    ESTADO.sincronizacao = None
    return vista_config(req, "dados")


@app.get("/modelo.xlsx")
def modelo_planilha():
    alinhar_idioma()
    return Response(importador.modelo_xlsx(),
                    media_type="application/vnd.openxmlformats-officedocument."
                               "spreadsheetml.sheet",
                    headers={"Content-Disposition":
                             'attachment; filename="modelo-organograma.xlsx"'})


@app.get("/panorama", response_class=HTMLResponse)
def panorama():
    """Manual de uso, servido pelo proprio app e nao aberto do disco.

    Rota em vez de arquivo solto por dois motivos: o link da barra funciona
    para quem abre o sistema de outra maquina, e o manual fica atras da mesma
    porta que o resto — `ORG_EXIGIR_LOGIN` protege por middleware, entao rota
    nova nasce protegida sem eu lembrar de pedir.
    """
    arquivo = RAIZ / "docs" / "panorama.html"
    if not arquivo.exists():                       # instalacao sem os docs
        return HTMLResponse("<h1>Manual não encontrado</h1>"
                            "<p>Esperado em <code>docs/panorama.html</code>.</p>",
                            status_code=404)
    return pagina_estatica(arquivo.read_text(encoding="utf-8"))


@app.get("/boas-vindas", response_class=HTMLResponse)
def boas_vindas():
    """A apresentacao de entrega, servida pela mesma porta que o manual.

    Mesmo desenho de `/panorama`, e pelos mesmos motivos: quem abre o sistema
    de outra maquina alcanca o link da barra, e a rota nasce atras do
    `ORG_EXIGIR_LOGIN` sem eu precisar lembrar de proteger.

    O deck e um arquivo unico e sem referencia externa — o logotipo vai
    embutido em `data:` —, entao ele tambem serve para anexar num e-mail sem
    quebrar. Por isso o arquivo, e nao um template: nao ha o que renderizar.
    """
    arquivo = RAIZ / "docs" / "boas-vindas.html"
    if not arquivo.exists():                       # instalacao sem os docs
        return HTMLResponse("<h1>Apresentação não encontrada</h1>"
                            "<p>Esperada em <code>docs/boas-vindas.html</code>.</p>",
                            status_code=404)
    return pagina_estatica(arquivo.read_text(encoding="utf-8"))


@app.get("/maria/historia", response_class=HTMLResponse)
def maria_historia():
    """A história da MarIA — arquivo único de `docs/`, servido pela mesma porta
    que o manual e as boas-vindas. É o destino do link no balão de recepção do
    passo a passo, onde a MarIA dá as boas-vindas a quem entrou."""
    arquivo = RAIZ / "docs" / "MarIA_Historia.html"
    if not arquivo.exists():
        return HTMLResponse("<h1>História da MarIA não encontrada</h1>"
                            "<p>Esperada em <code>docs/MarIA_Historia.html</code>.</p>",
                            status_code=404)
    return pagina_estatica(arquivo.read_text(encoding="utf-8"))


@app.get("/greyos", response_class=HTMLResponse)
def greyos():
    """GPlanSiS|OS — o sistema de gestão da GPlanSiS|Peoples sobre a metodologia EOS. Esta
    página explica o método e leva ao sistema em greyos.peoples.dev; é aberta
    pelo botão GPlanSiS|OS do cabeçalho, servida pela mesma porta que o manual."""
    arquivo = RAIZ / "docs" / "greyos.html"
    if not arquivo.exists():
        return HTMLResponse("<h1>GPlanSiS|OS não encontrado</h1>"
                            "<p>Esperado em <code>docs/greyos.html</code>.</p>",
                            status_code=404)
    return pagina_estatica(arquivo.read_text(encoding="utf-8"))


@app.get("/agentes", response_class=HTMLResponse)
def agentes():
    """GPlanSiS|ORG — os agentes de inteligência organizacional. Página única e autocontida
    (fontes, imagens em base64 e JS embutidos — zero dependência externa), aberta
    em aba própria pelo botão do cabeçalho. Seis agentes — MarIA, PlanIA, RotIA,
    OperIA, FluxIA e GentIA —, a história da casa, o método e o Human Gate.
    Servida da pasta `Agentes/`, onde vivem as histórias de cada um."""
    arquivo = RAIZ / "Agentes" / "GPlanSiS_ORG_Agentes.html"
    if not arquivo.exists():
        return HTMLResponse("<h1>Sistema de Agentes não encontrado</h1>"
                            "<p>Esperado em "
                            "<code>Agentes/GPlanSiS_ORG_Agentes.html</code>.</p>",
                            status_code=404)
    return pagina_estatica(arquivo.read_text(encoding="utf-8"))


# --- exportacao -----------------------------------------------------------
@app.get("/export.svg")
def export_svg(req: Request):
    """Mesmo template da tela (ADR-011): paridade estrutural, nao por teste."""
    svg = render("_canvas.html", request=req, layout=layout_para_arquivo(),
                 exportando=True)
    registrar("alterar", "-", "exportação SVG", {"formato": "svg"})   # LGPD-05
    gravar()
    return Response('<?xml version="1.0" encoding="UTF-8"?>\n' + svg,
                    media_type="image/svg+xml",
                    headers={"Content-Disposition":
                             'attachment; filename="organograma.svg"'})


@app.get("/export.pdf")
def export_pdf():
    """A3 paisagem, uma folha, vetorial e pesquisavel (W7-C1/C3)."""
    # sem cabecalho no SVG: o PDF tem o seu, com logo e escala
    layout = layout_para_arquivo(com_cabecalho=False)
    cab = cabecalho_do_desenho()
    # A legenda do PDF conta os nós DESENHADOS (colapso/foco já aplicados no
    # `layout`), como a tela — senão o papel diria "272 unidades" sob doze caixas.
    _pes = len(agrupar_atual()["equipe_de"]) if ESTADO.agrupamento == "equipe" else 0
    if cab.get("linhas"):
        cab["linhas"][0] = _linha_dos_nos(layout["nos"], _pes)
    escopo = f" · {cab['escopo']}" if cab["escopo"] else ""
    # O papel nao tem barra de ferramentas: sem dizer no titulo que aquilo e a
    # visao por equipe, quem recebe o arquivo le "81 caixas" e conclui que a
    # empresa tem 81 pessoas.
    modo = f" · {T('por equipe')}" if ESTADO.agrupamento == "equipe" else ""
    meta = pdfmod.meta_padrao(
        titulo=f"{ESTADO.config.titulo}{escopo}{modo}",
        subtitulo=" · ".join(cab["linhas"]),
        tenant=ESTADO.config.tenant,
        rodape=T("GPlanSiS|Peoples · SPEC-GPLANSIS-ORG-001 · carimbo {hash}",
                 hash=(ESTADO.eventos[-1]["hash"][:12]
                       if ESTADO.eventos else "—")))
    meta["idioma"] = ESTADO.config.idioma
    meta["legenda"] = [(T(n["rotulo"]), cargosmod.CORES_NIVEL[n["cor"]]["claro"])
                       for n in ESTADO.config.niveis if n.get("ativo", True)]
    dados = pdfmod.gerar(layout, meta, RAIZ / "web" / "marca" / "peoples-preto.png")
    registrar("alterar", "-", "exportação PDF A3", {"formato": "pdf",
                                                    "bytes": len(dados)})
    gravar()
    return Response(dados, media_type="application/pdf",
                    headers={"Content-Disposition":
                             'attachment; filename="organograma-a3.pdf"'})


@app.get("/export.json")
def export_json(req: Request):
    # Dump cru do estado inteiro (todas as unidades + acessos + log): só Admin.
    # Sem esta guarda, um escopo estreito baixaria a organização toda por aqui.
    if (m := negado(NIVEL_ADMIN)):
        return JSONResponse({"erro": m}, status_code=403)
    registrar("alterar", "-", "exportação JSON", {"formato": "json"})
    gravar()
    return JSONResponse(json.loads(serializar()),
                        headers={"Content-Disposition":
                                 'attachment; filename="organograma.json"'})


def ids_para_arquivo() -> set[str]:
    """O recorte que vai para CSV e XLSX: filtro e foco. Colapso não.

    O foco faltava, e era defeito: com foco numa subárvore de 59 pessoas, o
    desenho mostrava 59 e o CSV saía com as 272. Foco é uma declaração de
    escopo — "estou trabalhando neste galho" —, e um arquivo que a ignora
    entrega o que ninguém pediu.

    O colapso fica de fora, e isto é decisão, não esquecimento. Dobrar um galho
    é gesto de LEITURA: some da vista para o resto caber na tela, e não diz
    nada sobre o que interessa. O desenho — SVG e PDF — omite o que está
    dobrado porque desenho é o que se vê. A planilha é outra coisa: a aba `ORG`
    é o CONTRATO DE CARGA, e o ciclo é exportar, editar fora, devolver. Saindo
    dobrada, ela volta com menos gente do que a estrutura tem, e a carga lê a
    ausência como remoção — uma dobra na tela viraria demissão em massa no
    passo 3.
    """
    _, restritos = visao(achados())
    if restritos is None:
        dentro = set(ESTADO.unidades)
    else:
        dentro = set(restritos)
    uni = universo_visivel()
    if uni is not None:
        dentro &= set(uni)          # escopo de leitura: o arquivo nunca sai do universo
    if ESTADO.foco and ESTADO.foco in ESTADO.unidades:
        dentro &= {ESTADO.foco} | descendentes(ESTADO.unidades, ESTADO.foco)
    return dentro


@app.get("/export.xlsx")
def export_xlsx():
    """A estrutura em Excel — para ler e para devolver.

    Duas abas com propósitos diferentes: `Organograma` é a apresentação (marca,
    faixas por nível na paleta, agrupamento nativo) e `ORG` é o contrato de
    carga. A segunda existe para o ciclo fechar: quem recebe o arquivo edita e
    devolve pelos três passos de Configurações › Carga de dados, sem precisar
    montar planilha nova a partir do modelo.

    O recorte é o mesmo do CSV, do SVG e do PDF: sai o que está na tela.
    """
    alinhar_idioma()          # o exportador é módulo puro: recebe o idioma antes
    restritos = ids_para_arquivo()
    # `cabecalho_layout` direto, e não `cabecalho_do_desenho()`: em modo equipe
    # aquele descreve o DESENHO ("81 equipes · 267 pessoas"), e esta planilha é
    # sempre de pessoas — a aba ORG precisa das linhas que a carga lê de volta.
    # A legenda tem de descrever o arquivo, não a tela de onde ele saiu.
    cab = cabecalho_layout(achados())
    dados = importador.export_xlsx(
        ESTADO.unidades, recorte=cab["escopo"] or "", ids=restritos,
        titulo=cab["titulo"], subtitulo=" · ".join(cab["linhas"]),
        tenant=ESTADO.config.tenant,
        niveis=[n for n in ESTADO.config.niveis if n.get("ativo", True)],
        marca=RAIZ / "web" / "marca" / "peoples-preto.png")
    registrar("alterar", "-", "exportação XLSX", {"formato": "xlsx",
                                                  "bytes": len(dados)})
    gravar()
    return Response(dados,
                    media_type="application/vnd.openxmlformats-officedocument."
                               "spreadsheetml.sheet",
                    headers={"Content-Disposition":
                             'attachment; filename="organograma.xlsx"'})


@app.get("/export.csv")
def export_csv():
    # Recortado ao escopo: os filhos e o "responde_a" vêm do universo, e a
    # travessia parte das raízes-de-escopo — nunca da raiz real de fora.
    uni = universo_visivel()
    universo = ESTADO.unidades if uni is None else uni
    filhos = mapa_filhos(universo)
    prof = profundidades(ESTADO.unidades)
    restritos = ids_para_arquivo()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(["codigo", "nivel", "nome", "cargo", "tipo", "area", "email",
                "centro_custo", "vertical", "responde_a", "subordinados_diretos",
                "accountabilities", "competencias"])

    def caminhar(u: Unidade) -> None:
        if u.id in restritos:
            pai = universo.get(u.parent_id) if u.parent_id else None
            w.writerow([u.codigo, prof.get(u.id, 0), u.nome, u.cargo,
                        ESTADO.config.rotulos_nivel.get(u.tipo, u.tipo),
                        u.area, u.email, u.centro_custo,
                        u.vertical, pai.nome if pai else "",
                        len(filhos.get(u.id, [])),
                        " | ".join(("> " if r.get("origem") == "delegada" else "")
                                   + r.get("descricao", "")
                                   for r in u.responsabilidades),
                        ", ".join(u.competencias)])
        for f in filhos.get(u.id, []):
            caminhar(f)

    if uni is None:
        caminhar(raiz(ESTADO.unidades))
    else:
        for base in sorted((x for x in universo.values() if x.parent_id not in universo),
                           key=lambda x: sem_acento(x.nome)):
            caminhar(base)
    registrar("alterar", "-", "exportação CSV", {"formato": "csv"})
    gravar()
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="organograma.csv"'})


# --- API JSON  (SPEC 8) ---------------------------------------------------
@app.get("/api/v1/organograma")
def api_organograma(req: Request, orientacao: str = "invertida",
                    vigencia: str | None = None):
    """API-02/03: a arvore e sempre logica; orientacao e so um hint no meta."""
    # A API respeita o escopo de leitura como as vistas: subárvore vem conexa;
    # vertical/departamento (desconexo) vem sob a raiz virtual — nunca a árvore
    # inteira para quem só pode ver um recorte.
    uni = universo_visivel()
    if uni is None:
        fonte = ESTADO.unidades
    else:
        cfg = acesso_vigente()
        tipo = cfg.escopo_tipo or ("subarvore" if cfg.escopo_id else "tudo")
        fonte = (uni if tipo in ("proprio", "subarvore")
                 else _floresta_virtual(set(uni))[0])
    filhos = mapa_filhos(fonte)
    prof = profundidades(fonte)
    v = acesso_vigente()
    # O etag carrega a assinatura do escopo: dois recortes diferentes não podem
    # casar o mesmo etag e um receber o corpo do outro por cache.
    assinatura = (serializar() + (vigencia or "") + (v.usuario_id or "")
                  + str(v.ver_tudo) + v.escopo_tipo + v.escopo_valor)
    etag = 'W/"%s"' % hashlib.sha256(assinatura.encode()).hexdigest()[:16]
    if req.headers.get("if-none-match") == etag:            # API-01
        return Response(status_code=304)
    corpo = {
        "meta": {"slug": "peoples", "vigencia": vigencia or date.today().isoformat(),
                 "orientacao": orientacao,
                 "profundidade_max": max(prof.values(), default=0),
                 "total_unidades": len(fonte), "etag": etag},
        "raiz": arvore_json(raiz(fonte), filhos, prof),
    }
    return JSONResponse(corpo, headers={"ETag": etag})


@app.get("/api/v1/auditoria/verificar")
def api_verificar():
    return JSONResponse(verificar_cadeia())


@app.get("/api/v1/configuracao")
def api_config():
    # Da sessao DESTA requisicao (nao do global): senao a API vazaria o perfil de
    # quem logou por ultimo. `acesso_vigente()` ja carrega os campos de config.
    # Só a CONFIGURAÇÃO: os registros de RH que moram no Config (Conversa de
    # Valor, Avaliação/9-box, respostas da Avaliação Mestre, 1:1) e a tabela de
    # acessos ficam de fora — cada um tem a sua tela, com escopo e sigilo.
    v = acesso_vigente()
    c = {k: x for k, x in v.para_dict().items() if k not in CONFIG_SENSIVEL}
    c["perfil_rotulo"] = PERFIS[v.perfil]["rotulo"]
    return JSONResponse(c)


CONFIG_SENSIVEL = frozenset({"acessos", "cgv_registros", "mapa_talentos",
                             "gptw_respostas", "gptw_programacao", "onebyone",
                             "dcr_cargos", "software_por_area"})


# ---------------------------------------------------------------------------
# Skills — Descrição de Cargo e Responsabilidades (GEP-FOR-003)
# ---------------------------------------------------------------------------
def _ficha_ou_none(chave: str) -> dict | None:
    """A ficha de uma função sobre o recorte vigente."""
    fonte = fonte_visivel()
    linhas = dcrmod.medir(fonte, mapa_cc())
    return dcrmod.ficha(chave, linhas, fonte, registros_dcr(),
                        ESTADO.config.rotulos_nivel)


def _tela_ficha(req: Request, chave: str, extra: str = "") -> HTMLResponse:
    f = _ficha_ou_none(chave)
    if f is None:
        # Cargo extinto na última carga não é erro de servidor: é o caso normal
        # de um link guardado. A ficha vazia diz isso e a lista continua ali.
        return HTMLResponse(render("_dcr_ficha.html", request=req, f=None,
                                   chave=chave, formulario=dcrmod.FORMULARIO,
                                   secoes=[], valores=dcrmod.VALORES,
                                   rotulos=dcrmod.ROTULO_SECAO,
                                   motivo_edicao=negado(NIVEL_EDITOR) or "")
                            + extra)
    return HTMLResponse(render(
        "_dcr_ficha.html", request=req, f=f, chave=chave,
        formulario=dcrmod.FORMULARIO, secoes=dcrmod.documento(f),
        valores=dcrmod.VALORES, rotulos=dcrmod.ROTULO_SECAO,
        campos_lista=dcrmod.CAMPOS_LISTA,
        motivo_edicao=negado(NIVEL_EDITOR) or "") + extra)


@app.get("/dcr/vazio", response_class=HTMLResponse)
def dcr_fechar():
    """Fecha a ficha. Devolver vazio é o que o htmx precisa para esvaziar o
    alvo; um 204 deixaria o documento anterior na tela."""
    return HTMLResponse("")


@app.get("/dcr/ficha/{chave}", response_class=HTMLResponse)
def dcr_ficha(req: Request, chave: str):
    return _tela_ficha(req, chave)


@app.post("/dcr/ficha/{chave}", response_class=HTMLResponse)
async def dcr_salvar(req: Request, chave: str):
    """Grava a camada que o RH escreve. O derivado continua derivado.

    Edição de estrutura exige Editor, e esta também: o Skills é o texto que a
    empresa publica sobre um cargo, e quem não pode mexer na estrutura não pode
    reescrever a descrição dela. `marcar_ponto` antes de mudar coloca a edição
    no Desfazer junto com todas as outras — uma ficha reescrita por engano volta
    pelo mesmo botão que qualquer outro erro.
    """
    if negado(NIVEL_EDITOR):
        return _tela_ficha(req, chave, alerta(negado(NIVEL_EDITOR)))
    f = _ficha_ou_none(chave)
    if f is None:
        return _tela_ficha(req, chave, alerta(
            "Esse cargo não existe no recorte atual. Nada foi gravado."))

    form = await req.form()
    marcar_ponto()
    escrito = {"cargo": f["cargo"],
               **{c: str(form.get(c, "")) for c in dcrmod.CAMPOS_OVERLAY}}
    resto = [o for o in ESTADO.config.dcr_cargos
             if dcrmod.chave_funcao(o.get("cargo", "")) != chave]
    ESTADO.config.dcr_cargos = dcrmod.normalizar_overlay(resto + [escrito])

    # Espelho durável no Postgres: a descrição fica editável no banco, não só no
    # estado.json. Calado quando não há banco — o overlay já guardou.
    banco = "—"
    if dcrmod.banco_pronto():
        ok, msg = dcrmod.salvar_no_banco(
            {**escrito, "por": acesso_vigente().usuario_id or "-"}, SLUG_ATIVO)
        banco = "ok" if ok else msg

    preenchidas = sum(1 for c in dcrmod.CAMPOS_OVERLAY
                      if str(escrito.get(c) or "").strip())
    commit("alterar", "-", f"Skills do cargo {f['cargo']}",
           {"cargo": f["cargo"], "secoes": preenchidas, "banco": banco})
    return _tela_ficha(req, chave, alerta(
        T("Skills de “{cargo}” gravado — {n} de 4 seções preenchidas.",
          cargo=f["cargo"], n=preenchidas)))


@app.get("/dcr/ficha/{chave}/pdf")
def dcr_pdf(req: Request, chave: str):
    """A ficha em PDF, no formulário GEP-FOR-003.

    Segmento próprio, e não sufixo `.pdf`: a chave da função é o cargo sem
    acento, e cargo com ponto existe ("Analista Jr."). Com sufixo, `{chave}`
    engoliria o `.pdf` — e, pior, a rota genérica declarada antes venceria a
    disputa e devolveria HTML com `Content-Type` de PDF para quem baixasse.

    Reaproveita o motor de `relatorio.py`: ele já pagina, quebra linha medindo
    largura real e imprime a procedência no rodapé. O selo de gramática é
    substituído pelo código do formulário — este documento não passa pelo portão
    da MarIA, e carimbá-lo como se tivesse passado seria afirmar o que não houve.
    """
    f = _ficha_ou_none(chave)
    if f is None:
        return Response(status_code=404)

    correlacao = uuid.uuid4().hex[:16]
    quando = datetime.now(timezone.utc).isoformat(timespec="seconds")
    idioma = ESTADO.config.idioma
    meta = {
        "titulo": T("Descrição de Cargo e Responsabilidades"),
        "subtitulo": f"{f['cargo']} · {f['area'] or '—'} · "
                     f"{ESTADO.config.tenant}",
        "rodape": (f"{dcrmod.FORMULARIO['codigo']} · "
                   f"Rev {dcrmod.FORMULARIO['revisao']} · "
                   f"{ESTADO.config.tenant}"),
        "selo": T("{codigo} · Rev {rev} · formulário controlado",
                  codigo=dcrmod.FORMULARIO["codigo"],
                  rev=dcrmod.FORMULARIO["revisao"]),
        "idioma": idioma,
        # RQ-809: o rastro do documento vai impresso nele. Quantas pessoas
        # ocupam o cargo e quantas seções são texto do RH, e não dedução, é o
        # que permite a alguém julgar o quanto desta ficha foi revisado.
        "procedencia": [
            ("origem", f"GET /dcr/ficha/{chave}/pdf"),
            ("correlacao_id", correlacao),
            ("ts_emissao", quando),
            ("formulario", f"{dcrmod.FORMULARIO['codigo']} rev "
                           f"{dcrmod.FORMULARIO['revisao']}"),
            ("cargo", f["cargo"]),
            ("ocupacoes", str(f["n"])),
            ("secoes_escritas", str(sum(1 for s in dcrmod.documento(f)
                                        if s["origem"] == "escrito"))),
            ("recorte", T("filtro ativo") if filtro_ativo() else T("base inteira")),
        ],
    }
    dados = relatoriomod.gerar({"resposta": dcrmod.markdown(f)}, meta,
                               {"locale": idioma, "dicionario": "—",
                                "completa": False})
    registrar("alterar", "-", "Skills emitido em PDF",
              {"cargo": f["cargo"], "correlacao_id": correlacao,
               "bytes": len(dados)})
    gravar()
    nome = sem_acento(f["cargo"]).replace(" ", "-")[:60] or "cargo"
    return Response(dados, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="dcr-{nome}.pdf"'})


@app.get("/dcr.csv")
def dcr_csv():
    """O índice de funções em CSV — cabeçalho em contrato, não traduzido."""
    fonte = fonte_visivel()
    linhas = dcrmod.medir(fonte, mapa_cc())
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator=chr(10))
    w.writerow(["cargo", "papel", "pessoas", "setores", "business_units",
                "competencias_distintas", "descrita"])
    for f in dcrmod.funcoes(linhas, registros_dcr()):
        w.writerow([f["cargo"], f["papel_codigo"], f["n"], f["setores"],
                    f["bus"], f["competencias"],
                    "sim" if f["descrita"] else "nao"])
    return Response("\ufeff" + buf.getvalue(),
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="dcr-funcoes.csv"'})


# ---------------------------------------------------------------------------
# Conversa de Valor \u2014 Conversas que Geram Valor
# ---------------------------------------------------------------------------
def _cgv_ficha_ou_none(ref: str):
    """A ficha de Conversa de Valor de uma matr\u00edcula sobre o recorte vigente."""
    fonte = fonte_visivel()
    linhas = dcrmod.medir(fonte, mapa_cc())
    return cgvmod.ficha(ref, linhas, registros_cgv(), ano_cgv())


def _cgv_tela_ficha(req: Request, ref: str, extra: str = "",
                    aberto: str = "") -> HTMLResponse:
    """A ficha, com o step `aberto` selecionado (o ciclo recém-gravado, ou o
    primeiro por padrão) — assim o operador não perde o lugar após salvar."""
    f = _cgv_ficha_ou_none(ref)
    if aberto not in cgvmod.COD_CICLOS:
        aberto = cgvmod.COD_CICLOS[0]
    return HTMLResponse(render(
        "_cgv_ficha.html", request=req, f=f, status=cgvmod.STATUS,
        valores=cgvmod.VALORES_TRIO, competencias=cgvmod.COMPETENCIAS_LIDERANCA,
        aberto=aberto, motivo_edicao=negado(NIVEL_EDITOR) or "") + extra)


@app.get("/cgv/vazio", response_class=HTMLResponse)
def cgv_fechar():
    """Fecha a ficha. Devolver vazio \u00e9 o que o htmx precisa para esvaziar o
    alvo; um 204 deixaria a ficha anterior na tela."""
    return HTMLResponse("")


@app.get("/cgv/ficha/{ref}", response_class=HTMLResponse)
def cgv_ficha(req: Request, ref: str):
    return _cgv_tela_ficha(req, ref)


def _conteudo_do_form(form) -> dict:
    """O formul\u00e1rio de um ciclo, montado dos campos do POST \u2014 a equipe
    (GEP-FOR-006) e o feedback \u00e0 lideran\u00e7a (GEP-FOR-005), juntos."""
    return {
        "entregas": str(form.get("entregas") or ""),
        "valores": {cod: str(form.get(f"val_{cod}") or "")
                    for cod, _s, _r, _f in cgvmod.VALORES_TRIO},
        "pdi": [{"comp": str(form.get(f"pdi{i}_comp") or ""),
                 "acao": str(form.get(f"pdi{i}_acao") or ""),
                 "prazo": str(form.get(f"pdi{i}_prazo") or "")}
                for i in range(1, cgvmod.PDI_MAX + 1)],
        "carreira": str(form.get("carreira") or ""),
        "lideranca": {cod: str(form.get(f"lid_{cod}") or "")
                      for cod, _r, _it in cgvmod.COMPETENCIAS_LIDERANCA},
    }


@app.post("/cgv/ficha/{ref}/{ciclo}", response_class=HTMLResponse)
async def cgv_salvar_ciclo(req: Request, ref: str, ciclo: str):
    """Grava UM ciclo \u2014 o step \u2014 com o formul\u00e1rio inteiro, no banco e no estado.

    Cada conversa (Completa, Check-in 1, Check-in 2) \u00e9 um step pr\u00f3prio e salva
    sozinho: quem terminou a Completa n\u00e3o espera preencher os check-ins para
    persistir. Exige Editor, como toda edi\u00e7\u00e3o da estrutura. `marcar_ponto` p\u00f5e no
    Desfazer; o overlay \u00e9 a verdade viva e o Postgres \u00e9 o hist\u00f3rico dur\u00e1vel \u2014 a
    grava\u00e7\u00e3o vai aos dois, com o banco silencioso quando n\u00e3o existe.
    """
    if ciclo not in cgvmod.COD_CICLOS:
        return Response(status_code=404)
    if negado(NIVEL_EDITOR):
        return _cgv_tela_ficha(req, ref, alerta(negado(NIVEL_EDITOR)))
    f = _cgv_ficha_ou_none(ref)
    if f is None:
        return _cgv_tela_ficha(req, ref, alerta(
            "Essa pessoa n\u00e3o existe no recorte atual. Nada foi gravado."))

    form = await req.form()
    try:
        ano = int(form.get("ano") or ano_cgv())
    except (TypeError, ValueError):
        ano = ano_cgv()

    # Snapshot de como a pessoa est\u00e1 agora: o hist\u00f3rico precisa ser leg\u00edvel
    # depois que ela mudar de cargo ou de l\u00edder.
    reg = {"ref": ref, "ano": ano, "ciclo": ciclo,
           "status": str(form.get("status") or cgvmod.STATUS_PADRAO),
           "data": str(form.get("data") or ""),
           "conteudo": _conteudo_do_form(form),
           "nome": f["nome"], "cargo": f["cargo"], "lider": f["lider_nome"]}

    marcar_ponto()
    resto = [r for r in ESTADO.config.cgv_registros
             if not (r.get("ref") == ref and int(r.get("ano", 0)) == ano
                     and r.get("ciclo") == ciclo)]
    ESTADO.config.cgv_registros = cgvmod.normalizar_overlay(resto + [reg])

    banco = "\u2014"
    if cgvmod.banco_pronto():
        ok, msg = cgvmod.salvar_no_banco({**reg, "por": acesso_vigente().usuario_id or "-"}, SLUG_ATIVO)
        banco = "ok" if ok else msg

    n = cgvmod.conteudo_preenchido(reg["conteudo"])
    rot = cgvmod.ROTULO_CICLO.get(ciclo, ciclo)
    commit("alterar", "-", f"Conversa de Valor de {f['nome']} \u2014 {rot} ({ano})",
           {"ref": ref, "ano": ano, "ciclo": ciclo, "elementos": n, "banco": banco})
    destino = (T("gravado no banco e no estado") if banco == "ok"
               else T("gravado no estado de trabalho"))
    return _cgv_tela_ficha(req, ref, alerta(
        T("{ciclo} de \u201c{nome}\u201d \u2014 {n} de 5 elementos \u00b7 {destino}.",
          ciclo=T(rot), nome=f["nome"], n=n, destino=destino)), aberto=ciclo)


@app.get("/cgv/ficha/{ref}/pdf")
def cgv_pdf(req: Request, ref: str):
    """O acompanhamento em PDF, no formul\u00e1rio GEP-FOR-006.

    Segmento pr\u00f3prio, e n\u00e3o sufixo `.pdf`: a matr\u00edcula \u00e9 livre, e uma rota com
    sufixo engoliria o `.pdf`. Reaproveita o motor de `relatorio.py`, como o
    Skills. O selo \u00e9 o c\u00f3digo do formul\u00e1rio \u2014 este documento n\u00e3o passa pelo port\u00e3o
    da MarIA, e carimb\u00e1-lo como se tivesse seria afirmar o que n\u00e3o houve.
    """
    f = _cgv_ficha_ou_none(ref)
    if f is None:
        return Response(status_code=404)

    correlacao = uuid.uuid4().hex[:16]
    quando = datetime.now(timezone.utc).isoformat(timespec="seconds")
    idioma = ESTADO.config.idioma
    fmt = cgvmod.FORMULARIO
    meta = {
        "titulo": T("Conversas que Geram Valor"),
        "subtitulo": f"{f['nome']} \u00b7 {f['cargo'] or '\u2014'} \u00b7 {f['ano']} \u00b7 "
                     f"{ESTADO.config.tenant}",
        "rodape": f"{fmt['codigo']} \u00b7 Rev {fmt['revisao']} \u00b7 {ESTADO.config.tenant}",
        "selo": T("{codigo} \u00b7 Rev {rev} \u00b7 formul\u00e1rio controlado",
                  codigo=fmt["codigo"], rev=fmt["revisao"]),
        "idioma": idioma,
        "procedencia": [
            ("origem", f"GET /cgv/ficha/{ref}/pdf"),
            ("correlacao_id", correlacao),
            ("ts_emissao", quando),
            ("formulario", f"{fmt['codigo']} rev {fmt['revisao']}"),
            ("colaborador", f["nome"]),
            ("ano", str(f["ano"])),
            ("realizadas", f"{f['realizadas']} de 3"),
            ("recorte", T("filtro ativo") if filtro_ativo() else T("base inteira")),
        ],
    }
    dados = relatoriomod.gerar({"resposta": cgvmod.markdown(f)}, meta,
                               {"locale": idioma, "dicionario": "\u2014",
                                "completa": False})
    registrar("alterar", "-", "Conversa de Valor emitido em PDF",
              {"ref": ref, "correlacao_id": correlacao, "bytes": len(dados)})
    gravar()
    nome = sem_acento(f["nome"]).replace(" ", "-")[:60] or "cgv"
    return Response(dados, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="cgv-{nome}-{f["ano"]}.pdf"'})


@app.get("/cgv.csv")
def cgv_csv():
    """A agenda em CSV \u2014 cabe\u00e7alho em contrato, n\u00e3o traduzido."""
    fonte = fonte_visivel()
    linhas = dcrmod.medir(fonte, mapa_cc())
    ag = cgvmod.agenda(linhas, registros_cgv(), ano_cgv())
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator=chr(10))
    w.writerow(["ref", "colaborador", "cargo", "lider", "setor",
                *cgvmod.COD_CICLOS, "realizadas", "ano"])
    for a in ag:
        w.writerow([a["ref"], a["nome"], a["cargo"], a["lider_nome"], a["setor"],
                    *[a["ciclos"][c] for c in cgvmod.COD_CICLOS],
                    a["realizadas"], a["ano"]])
    return Response("\ufeff" + buf.getvalue(),
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="cgv-agenda.csv"'})


# Os tr\u00eas arquivos oficiais de `docs/CGV/`. Modelo \u00e9 download, n\u00e3o fonte: o
# sistema n\u00e3o importa planilha de Conversa de Valor, ela \u00e9 o que cada um preenche e envia ao
# RH. Um mapa, e n\u00e3o caminho montado com o que veio da URL \u2014 sen\u00e3o `/cgv/modelo/
# ../../.env` viraria leitura de arquivo arbitr\u00e1rio.
CGV_MODELOS = {
    "equipe": "CGV2026 - Equipe - Seu nome.xlsx",
    "lideranca": "CGV2026 - Lideran\u00e7a_Nome Lideran\u00e7a _Seu nome.xlsx",
}


@app.get("/cgv/modelo/{qual}")
def cgv_modelo(qual: str):
    """O formul\u00e1rio oficial em Excel, para baixar e preencher."""
    arquivo = CGV_MODELOS.get(qual)
    if not arquivo:
        return Response(status_code=404)
    caminho = RAIZ / "docs" / "CGV" / arquivo
    if not caminho.exists():
        return Response(status_code=404)
    saida = f"conversa-de-valor-modelo-{qual}.xlsx"
    return Response(
        caminho.read_bytes(),
        media_type="application/vnd.openxmlformats-officedocument."
                   "spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{saida}"'})


@app.get("/cgv/trio", response_class=HTMLResponse)
def cgv_trio():
    """Os quatro valores GPlanSiS e as competências de liderança (LMA), servidos pelo
    app. Arquivo único e autocontido, embutido na aba Referência da Conversa de Valor."""
    caminho = RAIZ / "docs" / "CGV" / "Valores_GPlanSiS.html"
    if not caminho.exists():
        return HTMLResponse("<h1>Valores GPlanSiS n\u00e3o encontrados</h1>", status_code=404)
    return pagina_estatica(caminho.read_text(encoding="utf-8"))


@app.get("/cgv/manual")
def cgv_manual():
    """O manual completo em PDF, servido pelo app e n\u00e3o aberto do disco \u2014 mesmo
    desenho de `/panorama`: o link funciona de outra m\u00e1quina e nasce atr\u00e1s da
    mesma porta de login."""
    caminho = RAIZ / "docs" / "CGV" / "Manual_Feedback_CGV_rev2026.pdf"
    if not caminho.exists():
        return Response(status_code=404)
    return Response(caminho.read_bytes(), media_type="application/pdf",
                    headers={"Content-Disposition":
                             'inline; filename="manual-cgv.pdf"'})


@app.get("/cgv/interativo", response_class=HTMLResponse)
def cgv_interativo():
    """O passo a passo interativo do processo Conversa de Valor, servido como o manual e as
    boas-vindas: arquivo \u00fanico de `docs/`, atr\u00e1s da mesma porta."""
    arquivo = RAIZ / "docs" / "cgv-manual.html"
    if not arquivo.exists():
        return HTMLResponse("<h1>Passo a passo n\u00e3o encontrado</h1>"
                            "<p>Esperado em <code>docs/cgv-manual.html</code>.</p>",
                            status_code=404)
    return pagina_estatica(arquivo.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# One-on-One \u2014 1:1 (FUP), cad\u00eancia (sigilo por pessoa: s\u00f3 participantes ou RH)
# ---------------------------------------------------------------------------
def _pode_abrir_1a1(ref: str, base: list[dict]) -> bool:
    """A ACL aplicada ANTES de montar a ficha: abre quem \u00e9 a pr\u00f3pria pessoa
    (liderado), o l\u00edder direto dela, ou RH. Fail-closed."""
    _eid, mat, rh = identidade_1a1()
    if rh:
        return True
    if mat and ref == mat:
        return True
    return bool(mat) and _lider_ref_de(ref, base) == mat


def _carreira_pull(ref: str) -> dict:
    """A carreira 'at\u00e9 onde posso chegar' N\u00c3O se reescreve aqui: puxa-se da Conversa de Valor
    (texto de carreira + PDI) e do Talentos (trilha de carreira + prontid\u00e3o de
    sucess\u00e3o), a fonte \u00fanica. Integra\u00e7\u00e3o \u00a7INT-1/INT-3 \u2014 o 1:1 exibe, n\u00e3o duplica."""
    cgvs = sorted((r for r in registros_cgv() if r.get("ref") == ref),
                  key=lambda r: r.get("ano", 0), reverse=True)
    carreira_txt = next((r.get("conteudo", {}).get("carreira") for r in cgvs
                         if r.get("conteudo", {}).get("carreira")), "")
    pdi = next((r.get("conteudo", {}).get("pdi") for r in cgvs
                if r.get("conteudo", {}).get("pdi")), []) or []
    pdi = [p for p in pdi if any((p or {}).get(k) for k in ("comp", "acao", "prazo"))]
    tals = sorted((r for r in registros_talentos() if r.get("ref") == ref),
                  key=lambda r: r.get("ano", 0), reverse=True)
    trilha = next((r.get("conteudo", {}).get("trilha_posicao") for r in tals
                   if r.get("conteudo", {}).get("trilha_posicao")), "")
    prontidao = next((r.get("prontidao") for r in tals if r.get("prontidao")), "")
    return {"carreira_cgv": carreira_txt, "pdi": pdi, "trilha": trilha,
            "prontidao": talentosmod.ROTULO_PRONTIDAO.get(prontidao, "")}


def _tela_ficha_1a1(req: Request, ref: str, base: list[dict],
                    msg: str = "", aberto: str = "") -> HTMLResponse:
    """A ficha do 1:1 de uma pessoa. `f=None` quando fora do sigilo/recorte \u2014 o
    template mostra o aviso, nunca vaza conte\u00fado."""
    ano = datetime.now(timezone.utc).year
    tri = obomod.trimestre_atual()
    f = (obomod.ficha(ref, base, onebyone_visivel(), ano, tri, carreira=_carreira_pull(ref))
         if _pode_abrir_1a1(ref, base) else None)
    corpo = render("_onebyone_ficha.html", request=req, f=f,
                   cadencias=obomod.CADENCIAS, aberto=aberto,
                   status_rock=obomod.STATUS_ROCK, status_issue=obomod.STATUS_ISSUE,
                   status_obj=obomod.STATUS_OBJ, status_missao=obomod.STATUS_MISSAO,
                   estagios=obomod.ESTAGIOS,
                   ano=ano, trimestre=tri, hoje=date.today().isoformat(),
                   motivo_edicao=negado(NIVEL_EDITOR) or "")
    return HTMLResponse(corpo + (msg or ""))


@app.get("/onebyone/vazio", response_class=HTMLResponse)
def onebyone_vazio():
    return HTMLResponse("")


@app.get("/onebyone/ficha/{ref}", response_class=HTMLResponse)
def onebyone_ficha(req: Request, ref: str):
    return _tela_ficha_1a1(req, ref, obomod.base(fonte_visivel(), mapa_cc()))


@app.post("/onebyone/conversa/{ref}", response_class=HTMLResponse)
async def onebyone_salvar_conversa(req: Request, ref: str):
    """Registra/edita uma conversa 1:1 (FUP). Exige Editor E ser participante
    (l\u00edder direto, a pr\u00f3pria pessoa) ou RH. O sigilo \u00e9 gravado no registro: as
    duas matr\u00edculas participantes."""
    base = obomod.base(fonte_visivel(), mapa_cc())
    if (m := negado(NIVEL_EDITOR)):
        return _tela_ficha_1a1(req, ref, base, alerta(m))
    if not _pode_abrir_1a1(ref, base):
        return _tela_ficha_1a1(req, ref, base,
                               alerta(T("Voc\u00ea n\u00e3o participa deste 1:1.")))
    porref = {obomod.ref_de(l): l for l in base}
    l = porref.get(ref)
    if not l:
        return _tela_ficha_1a1(req, ref, base,
                               alerta(T("Pessoa fora do recorte. Nada foi gravado.")))
    form = await req.form()
    _eid, mat, rh = identidade_1a1()
    lider_ref = _lider_ref_de(ref, base) or (mat if not rh else "")
    pai = ESTADO.unidades.get(l.get("parent_id"))
    reg = {
        "id": str(form.get("id") or "").strip() or novo_id(),
        "tipo": "conversa", "ref": ref, "lider_ref": lider_ref,
        "ano": 0, "trimestre": 0, "data": str(form.get("data") or "")[:10],
        "conteudo": {"pauta": form.get("pauta") or "", "notas": form.get("notas") or "",
                     "proximos_passos": form.get("proximos_passos") or "",
                     "sentimento": form.get("sentimento") or 0,
                     "cadencia": form.get("cadencia") or ""},
        "nome": l["nome"], "cargo": l.get("cargo", ""),
        "lider": (pai.nome if pai else ""),
        "por": (usuario_atual() or {}).get("nome", "") or mat,
    }
    marcar_ponto()
    resto = [r for r in ESTADO.config.onebyone if r.get("id") != reg["id"]]
    ESTADO.config.onebyone = obomod.normalizar_overlay(resto + [reg])
    if obomod.banco_pronto():
        obomod.salvar_no_banco({**reg, "por": mat or "-"}, SLUG_ATIVO)
    commit("alterar", "-", "1:1 registrado", {"ref": ref, "id": reg["id"]})
    return _tela_ficha_1a1(req, ref, base,
                           alerta(T("Conversa 1:1 de \u201c{nome}\u201d registrada.", nome=l["nome"])))


@app.post("/onebyone/conversa/{ref}/apagar/{item_id}", response_class=HTMLResponse)
async def onebyone_apagar_conversa(req: Request, ref: str, item_id: str):
    """Apaga uma conversa. S\u00f3 participante/RH e Editor \u2014 e s\u00f3 se o item \u00e9 mesmo
    desta pessoa e o solicitante pode v\u00ea-lo (n\u00e3o se apaga o que n\u00e3o se enxerga)."""
    base = obomod.base(fonte_visivel(), mapa_cc())
    if (m := negado(NIVEL_EDITOR)):
        return _tela_ficha_1a1(req, ref, base, alerta(m))
    _eid, mat, rh = identidade_1a1()
    alvo = next((r for r in ESTADO.config.onebyone if r.get("id") == item_id), None)
    if not (alvo and alvo.get("ref") == ref and obomod.pode_ver(alvo, mat, rh)):
        return _tela_ficha_1a1(req, ref, base,
                               alerta(T("Registro indispon\u00edvel. Nada foi apagado.")))
    marcar_ponto()
    ESTADO.config.onebyone = [r for r in ESTADO.config.onebyone if r.get("id") != item_id]
    if obomod.banco_pronto():
        obomod.apagar_do_banco(item_id, SLUG_ATIVO)
    commit("alterar", "-", "1:1 apagado", {"ref": ref, "id": item_id})
    return _tela_ficha_1a1(req, ref, base, alerta(T("Conversa apagada.")))


_TIPOS_ITEM = ("rock", "issue", "objetivo", "pulso", "ciclo")


@app.post("/onebyone/item/{ref}/{tipo}", response_class=HTMLResponse)
async def onebyone_salvar_item(req: Request, ref: str, tipo: str):
    """Grava um rock, issue ou objetivo (do trimestre, ou de carreira com
    trimestre 0). Mesmo sigilo do 1:1: Editor E participante (ou RH)."""
    if tipo not in _TIPOS_ITEM:
        return Response(status_code=404)
    base = obomod.base(fonte_visivel(), mapa_cc())
    if (m := negado(NIVEL_EDITOR)):
        return _tela_ficha_1a1(req, ref, base, alerta(m))
    if not _pode_abrir_1a1(ref, base):
        return _tela_ficha_1a1(req, ref, base,
                               alerta(T("Voc\u00ea n\u00e3o participa deste 1:1.")))
    porref = {obomod.ref_de(l): l for l in base}
    l = porref.get(ref)
    if not l:
        return _tela_ficha_1a1(req, ref, base,
                               alerta(T("Pessoa fora do recorte. Nada foi gravado.")))
    form = await req.form()
    _eid, mat, rh = identidade_1a1()
    lider_ref = _lider_ref_de(ref, base) or (mat if not rh else "")
    pai = ESTADO.unidades.get(l.get("parent_id"))
    conteudo = {c: form.get(c) for c in obomod.campos_do_tipo(tipo)}
    try:
        ano = int(form.get("ano") or datetime.now(timezone.utc).year)
    except (TypeError, ValueError):
        ano = datetime.now(timezone.utc).year
    try:
        trimestre = int(form.get("trimestre") or 0)
    except (TypeError, ValueError):
        trimestre = 0
    reg = {"id": str(form.get("id") or "").strip() or novo_id(), "tipo": tipo,
           "ref": ref, "lider_ref": lider_ref, "ano": ano, "trimestre": trimestre,
           "data": str(form.get("data") or "")[:10], "conteudo": conteudo,
           "nome": l["nome"], "cargo": l.get("cargo", ""),
           "lider": (pai.nome if pai else ""),
           "por": (usuario_atual() or {}).get("nome", "") or mat}
    marcar_ponto()
    resto = [r for r in ESTADO.config.onebyone if r.get("id") != reg["id"]]
    ESTADO.config.onebyone = obomod.normalizar_overlay(resto + [reg])
    if obomod.banco_pronto():
        obomod.salvar_no_banco({**reg, "por": mat or "-"}, SLUG_ATIVO)
    commit("alterar", "-", "One-on-One item salvo", {"ref": ref, "tipo": tipo, "id": reg["id"]})
    return _tela_ficha_1a1(req, ref, base, alerta(T("Item salvo.")))


@app.post("/onebyone/item/{ref}/apagar/{item_id}", response_class=HTMLResponse)
async def onebyone_apagar_item(req: Request, ref: str, item_id: str):
    """Apaga um rock/issue/objetivo \u2014 mesmo guarda do apagar de conversa."""
    base = obomod.base(fonte_visivel(), mapa_cc())
    if (m := negado(NIVEL_EDITOR)):
        return _tela_ficha_1a1(req, ref, base, alerta(m))
    _eid, mat, rh = identidade_1a1()
    alvo = next((r for r in ESTADO.config.onebyone if r.get("id") == item_id), None)
    if not (alvo and alvo.get("ref") == ref and obomod.pode_ver(alvo, mat, rh)):
        return _tela_ficha_1a1(req, ref, base,
                               alerta(T("Registro indispon\u00edvel. Nada foi apagado.")))
    marcar_ponto()
    ESTADO.config.onebyone = [r for r in ESTADO.config.onebyone if r.get("id") != item_id]
    if obomod.banco_pronto():
        obomod.apagar_do_banco(item_id, SLUG_ATIVO)
    commit("alterar", "-", "One-on-One item apagado", {"ref": ref, "id": item_id})
    return _tela_ficha_1a1(req, ref, base, alerta(T("Item apagado.")))


@app.post("/onebyone/missoes-do-cgv/{ref}", response_class=HTMLResponse)
async def onebyone_missoes_cgv(req: Request, ref: str):
    """Gera miss\u00f5es de evolu\u00e7\u00e3o a partir do PDI da Conversa de Valor da pessoa (INT-2). Cada
    compet\u00eancia do PDI vira uma miss\u00e3o proposta \u2014 sem duplicar as que j\u00e1 existem."""
    base = obomod.base(fonte_visivel(), mapa_cc())
    if (m := negado(NIVEL_EDITOR)):
        return _tela_ficha_1a1(req, ref, base, alerta(m))
    if not _pode_abrir_1a1(ref, base):
        return _tela_ficha_1a1(req, ref, base,
                               alerta(T("Voc\u00ea n\u00e3o participa deste 1:1.")))
    porref = {obomod.ref_de(l): l for l in base}
    l = porref.get(ref)
    if not l:
        return _tela_ficha_1a1(req, ref, base,
                               alerta(T("Pessoa fora do recorte. Nada foi gravado.")))
    _eid, mat, rh = identidade_1a1()
    lider_ref = _lider_ref_de(ref, base) or (mat if not rh else "")
    pai = ESTADO.unidades.get(l.get("parent_id"))
    ja = {(m2.get("conteudo", {}).get("titulo"), m2.get("conteudo", {}).get("origem"))
          for m2 in obomod.itens(ESTADO.config.onebyone, ref, "missao")}
    novos = []
    for d in obomod.missoes_do_cgv(ref, registros_cgv()):
        if (d["titulo"], d["origem"]) in ja:
            continue
        novos.append({"id": novo_id(), "tipo": "missao", "ref": ref,
                      "lider_ref": lider_ref, "ano": 0, "trimestre": 0, "data": "",
                      "conteudo": d, "nome": l["nome"], "cargo": l.get("cargo", ""),
                      "lider": (pai.nome if pai else ""),
                      "por": (usuario_atual() or {}).get("nome", "") or mat})
    if novos:
        marcar_ponto()
        ESTADO.config.onebyone = obomod.normalizar_overlay(ESTADO.config.onebyone + novos)
        if obomod.banco_pronto():
            for n in novos:
                obomod.salvar_no_banco({**n, "por": mat or "-"}, SLUG_ATIVO)
        commit("alterar", "-", "Miss\u00f5es geradas da Conversa de Valor", {"ref": ref, "n": len(novos)})
    return _tela_ficha_1a1(req, ref, base,
                           alerta(T("{n} miss\u00e3o(\u00f5es) gerada(s) da Conversa de Valor.", n=len(novos))))


@app.get("/onebyone/export.json")
def onebyone_export(req: Request):
    """Exporta as miss\u00f5es VIS\u00cdVEIS (respeitando o sigilo) no formato de tarefas do
    GPlanSiS|OS \u2014 o encaixe para o GPlanSiS|OS importar enquanto a integra\u00e7\u00e3o viva n\u00e3o existe."""
    from . import greyos
    missoes = [m for m in onebyone_visivel() if m.get("tipo") == "missao"]
    payload = greyos.exportar(missoes)
    registrar("alterar", "-", "exporta\u00e7\u00e3o de miss\u00f5es (GPlanSiS|OS)",
              {"formato": "json", "tarefas": payload["count"]})
    gravar()
    return JSONResponse(payload, headers={
        "Content-Disposition": 'attachment; filename="onebyone_missoes_greyos.json"'})


# ---------------------------------------------------------------------------
# Avaliação \u2014 GEP-FOR-004
# ---------------------------------------------------------------------------
def _talentos_ficha_ou_none(ref: str):
    """O Mapa de uma matr\u00edcula sobre o recorte vigente \u2014 derivado (cargo, l\u00edder,
    tempo de casa) somado \u00e0 leitura que o RH escreveu."""
    fonte = fonte_visivel()
    linhas = talentosmod.medir(fonte, mapa_cc())
    return talentosmod.ficha(ref, linhas, registros_talentos(), ano_talentos(),
                             registros_cgv())


def _talentos_tela_ficha(req: Request, ref: str, extra: str = "") -> HTMLResponse:
    """A ficha do Mapa, com as escalas e os r\u00f3tulos que a tela precisa."""
    f = _talentos_ficha_ou_none(ref)
    return HTMLResponse(render(
        "_talentos_ficha.html", request=req, f=f,
        formulario=talentosmod.FORMULARIO,
        riscos=talentosmod.RISCOS, impactos=talentosmod.IMPACTOS,
        prontidoes=talentosmod.PRONTIDOES, acoes=talentosmod.ACOES,
        valores=talentosmod.VALORES_TRIO,
        rot_risco=talentosmod.ROTULO_RISCO, rot_impacto=talentosmod.ROTULO_IMPACTO,
        rot_prontidao=talentosmod.ROTULO_PRONTIDAO, rot_acao=talentosmod.ROTULO_ACAO,
        motivo_edicao=negado(NIVEL_EDITOR) or "") + extra)


@app.get("/talentos/vazio", response_class=HTMLResponse)
def talentos_fechar():
    """Fecha a ficha. Devolver vazio \u00e9 o que o htmx precisa para esvaziar o alvo."""
    return HTMLResponse("")


@app.get("/talentos/ficha/{ref}", response_class=HTMLResponse)
def talentos_ficha(req: Request, ref: str):
    return _talentos_tela_ficha(req, ref)


def _conteudo_talentos_do_form(form) -> dict:
    """O GEP-FOR-004 montado dos campos do POST \u2014 o texto rico da folha."""
    return {
        "idade": str(form.get("idade") or ""),
        "trajetoria": str(form.get("trajetoria") or ""),
        "formacoes": str(form.get("formacoes") or ""),
        "perfil": str(form.get("perfil") or ""),
        "performance": str(form.get("performance") or ""),
        "bem_estar": str(form.get("bem_estar") or ""),
        "ferramentas": str(form.get("ferramentas") or ""),
        "ingles": str(form.get("ingles") or ""),
        "trilha_posicao": str(form.get("trilha_posicao") or ""),
        "acao_nota": str(form.get("acao_nota") or ""),
        "valores": {cod: str(form.get(f"val_{cod}") or "")
                    for cod in talentosmod.COD_TRIO},
    }


@app.post("/talentos/ficha/{ref}", response_class=HTMLResponse)
async def talentos_salvar(req: Request, ref: str):
    """Grava o Mapa de uma pessoa \u2014 a folha inteira, no banco e no estado.

    Um registro por (matr\u00edcula, ano): editar atualiza a linha, n\u00e3o empilha. Exige
    Editor, como toda edi\u00e7\u00e3o da estrutura. `marcar_ponto` p\u00f5e no Desfazer; o
    overlay \u00e9 a verdade viva e o Postgres \u00e9 o hist\u00f3rico dur\u00e1vel \u2014 a grava\u00e7\u00e3o vai
    aos dois, com o banco silencioso quando n\u00e3o existe.
    """
    if negado(NIVEL_EDITOR):
        return _talentos_tela_ficha(req, ref, alerta(negado(NIVEL_EDITOR)))
    f = _talentos_ficha_ou_none(ref)
    if f is None:
        return _talentos_tela_ficha(req, ref, alerta(
            "Essa pessoa n\u00e3o existe no recorte atual. Nada foi gravado."))

    form = await req.form()
    try:
        ano = int(form.get("ano") or ano_talentos())
    except (TypeError, ValueError):
        ano = ano_talentos()

    # Snapshot de como a pessoa est\u00e1 agora: o Mapa precisa ser leg\u00edvel depois que
    # ela mudar de cargo ou de l\u00edder.
    reg = {"ref": ref, "ano": ano,
           "risco_perda": str(form.get("risco_perda") or ""),
           "impacto_perda": str(form.get("impacto_perda") or ""),
           "prontidao": str(form.get("prontidao") or ""),
           "acao": str(form.get("acao") or ""),
           "conteudo": _conteudo_talentos_do_form(form),
           "nome": f["nome"], "cargo": f["cargo"], "lider": f["lider_nome"]}

    marcar_ponto()
    resto = [r for r in ESTADO.config.mapa_talentos
             if not (r.get("ref") == ref and int(r.get("ano", 0)) == ano)]
    ESTADO.config.mapa_talentos = talentosmod.normalizar_overlay(resto + [reg])

    banco = "\u2014"
    if talentosmod.banco_pronto():
        ok, msg = talentosmod.salvar_no_banco(
            {**reg, "por": acesso_vigente().usuario_id or "-"}, SLUG_ATIVO)
        banco = "ok" if ok else msg

    n = talentosmod.conteudo_preenchido(reg["conteudo"])
    commit("alterar", "-", f"Avaliação de {f['nome']} ({ano})",
           {"ref": ref, "ano": ano, "elementos": n, "banco": banco})
    destino = (T("gravado no banco e no estado") if banco == "ok"
               else T("gravado no estado de trabalho"))
    return _talentos_tela_ficha(req, ref, alerta(
        T("Mapa de \u201c{nome}\u201d gravado \u2014 {n} de 8 se\u00e7\u00f5es \u00b7 {destino}.",
          nome=f["nome"], n=n, destino=destino)))


@app.get("/talentos/ficha/{ref}/pdf")
def talentos_pdf(req: Request, ref: str):
    """O Mapa em PDF, no formul\u00e1rio GEP-FOR-004. Reaproveita o motor de
    `relatorio.py`, como o Skills e a Conversa de Valor. Segmento pr\u00f3prio, e n\u00e3o sufixo `.pdf`: a
    matr\u00edcula \u00e9 livre e um sufixo engoliria o `.pdf`."""
    f = _talentos_ficha_ou_none(ref)
    if f is None:
        return Response(status_code=404)

    correlacao = uuid.uuid4().hex[:16]
    quando = datetime.now(timezone.utc).isoformat(timespec="seconds")
    idioma = ESTADO.config.idioma
    fmt = talentosmod.FORMULARIO
    meta = {
        "titulo": T("Avaliação"),
        "subtitulo": f"{f['nome']} \u00b7 {f['cargo'] or '\u2014'} \u00b7 {f['ano']} \u00b7 "
                     f"{ESTADO.config.tenant}",
        "rodape": f"{fmt['codigo']} \u00b7 Rev {fmt['revisao']} \u00b7 {ESTADO.config.tenant}",
        "selo": T("{codigo} \u00b7 Rev {rev} \u00b7 formul\u00e1rio controlado",
                  codigo=fmt["codigo"], rev=fmt["revisao"]),
        "idioma": idioma,
        "procedencia": [
            ("origem", f"GET /talentos/ficha/{ref}/pdf"),
            ("correlacao_id", correlacao),
            ("ts_emissao", quando),
            ("formulario", f"{fmt['codigo']} rev {fmt['revisao']}"),
            ("colaborador", f["nome"]),
            ("ano", str(f["ano"])),
            ("recorte", T("filtro ativo") if filtro_ativo() else T("base inteira")),
        ],
    }
    dados = relatoriomod.gerar({"resposta": talentosmod.markdown(f)}, meta,
                               {"locale": idioma, "dicionario": "\u2014",
                                "completa": False})
    registrar("alterar", "-", "Avaliação emitido em PDF",
              {"ref": ref, "correlacao_id": correlacao, "bytes": len(dados)})
    gravar()
    nome = sem_acento(f["nome"]).replace(" ", "-")[:60] or "mapa"
    return Response(dados, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="mapa-{nome}-{f["ano"]}.pdf"'})


@app.get("/talentos.csv")
def talentos_csv():
    """O Mapa em CSV \u2014 cabe\u00e7alho em contrato, n\u00e3o traduzido."""
    fonte = fonte_visivel()
    linhas = talentosmod.medir(fonte, mapa_cc())
    ag = talentosmod.agenda(linhas, registros_talentos(), ano_talentos())
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator=chr(10))
    w.writerow(["ref", "colaborador", "cargo", "lider", "setor",
                "risco_perda", "impacto_perda", "prontidao", "acao", "ano"])
    for a in ag:
        w.writerow([a["ref"], a["nome"], a["cargo"], a["lider_nome"], a["setor"],
                    a["risco_perda"], a["impacto_perda"], a["prontidao"],
                    a["acao"], a["ano"]])
    return Response("\ufeff" + buf.getvalue(),
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="mapa-talentos.csv"'})


# ---------------------------------------------------------------------------
# Peoples Place to Work \u2014 a pesquisa de clima an\u00f4nima
# ---------------------------------------------------------------------------
def _gptw_tela_responder(req: Request, ciclo: str = "", extra: str = "") -> HTMLResponse:
    """O question\u00e1rio \u2014 as afirma\u00e7\u00f5es do ciclo em Likert de 5, an\u00f4nimo."""
    ciclo = ciclo if ciclo in gptwmod.ROTULO_CICLO else gptwmod.CICLO_PADRAO
    return HTMLResponse(render("_gptw_responder.html", request=req, vista="gptw",
                               **contexto_gptw("responder", ciclo)) + extra)


@app.get("/gptw/responder", response_class=HTMLResponse)
def gptw_responder(req: Request, ciclo: str = ""):
    """A página do questionário, inteira e estilizada — é o destino do QR code de
    acesso mobile (spec §3.1). Serve a moldura para a pesquisa não abrir crua num
    celular; o POST devolve só o fragmento, que o htmx troca no lugar."""
    return HTMLResponse(render("base.html", request=req, vista="gptw",
                               corpo=html_vista(req, "gptw", "responder", ciclo=ciclo),
                               painel=painel_atual(req)))


@app.post("/gptw/responder", response_class=HTMLResponse)
async def gptw_enviar(req: Request):
    """Grava uma resposta AN\u00d4NIMA \u2014 no banco e no estado. NUNCA a identidade.

    O estrato (n\u00edvel, \u00e1rea, v\u00ednculo, faixa) \u00e9 derivado no servidor da posi\u00e7\u00e3o de
    quem est\u00e1 logado e gravado sem o `usuario_id`; s\u00f3 o modelo de trabalho vem do
    formul\u00e1rio. Sem `marcar_ponto`: uma resposta de pesquisa n\u00e3o \u00e9 edi\u00e7\u00e3o de
    estrutura para desfazer, e o ledger a registra sem dono."""
    form = await req.form()
    try:
        ano = int(form.get("ano") or ano_gptw())
    except (TypeError, ValueError):
        ano = ano_gptw()
    ciclo = (form.get("ciclo") if form.get("ciclo") in gptwmod.ROTULO_CICLO
             else gptwmod.CICLO_PADRAO)

    respostas = {}
    for aid, *_ in gptwmod.afirmacoes_do_ciclo(ciclo):
        v = form.get(f"af_{aid}")
        if v:
            respostas[aid] = v
    abertas = {qid: str(form.get(f"ab_{qid}") or "").strip()
               for qid, _txt in gptwmod.ABERTAS
               if str(form.get(f"ab_{qid}") or "").strip()}

    # O estrato sai do servidor, n\u00e3o do formul\u00e1rio: cliente n\u00e3o escolhe o pr\u00f3prio
    # recorte, e a identidade nunca entra na linha.
    estrato = _estrato_do_respondente()
    reg = {"id": uuid.uuid4().hex, "ciclo": ciclo, "ano": ano,
           "respostas": respostas, "abertas": abertas, **estrato,
           "modelo": form.get("modelo") or ""}
    limpo = gptwmod.normalizar_resposta(reg)
    if limpo is None:
        return _gptw_tela_responder(req, ciclo, alerta(
            "Marque ao menos uma afirma\u00e7\u00e3o para enviar. Nada foi gravado."))

    ESTADO.config.gptw_respostas = gptwmod.normalizar_overlay(
        ESTADO.config.gptw_respostas + [limpo])

    banco = "\u2014"
    if gptwmod.banco_pronto():
        ok, msg = gptwmod.salvar_no_banco(limpo, SLUG_ATIVO)
        banco = "ok" if ok else msg

    # Ledger sem identidade: conta a resposta, n\u00e3o quem a deu.
    registrar("alterar", "-", "Avaliação Mestre resposta registrada",
              {"ciclo": ciclo, "ano": ano, "afirmacoes": len(limpo["respostas"]),
               "banco": banco})
    gravar()
    destino = (T("gravada no banco e no estado") if banco == "ok"
               else T("gravada no estado de trabalho"))
    return _gptw_tela_responder(req, ciclo, alerta(
        T("Resposta an\u00f4nima registrada \u2014 {n} afirma\u00e7\u00f5es \u00b7 {destino}. Obrigado.",
          n=len(limpo["respostas"]), destino=destino)))


@app.get("/gptw.csv")
def gptw_csv():
    """O PTI afirma\u00e7\u00e3o a afirma\u00e7\u00e3o em CSV \u2014 cabe\u00e7alho em contrato, n\u00e3o traduzido.
    Sem uma linha por resposta: exportar respostas cruas arriscaria o anonimato;
    o que sai \u00e9 o agregado por afirma\u00e7\u00e3o."""
    resp = [r for r in respostas_gptw()
            if r.get("ano") == ano_gptw() and r.get("ciclo") == gptwmod.CICLO_PADRAO]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator=chr(10))
    w.writerow(["pilar", "afirmacao", "gti", "validas", "pulso", "ano"])
    for a in gptwmod.por_afirmacao(resp):
        w.writerow([a["pilar"], a["texto"], a["gti"] if a["gti"] is not None else "",
                    a["validas"], "sim" if a["pulso"] else "nao", ano_gptw()])
    return Response("\ufeff" + buf.getvalue(),
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             'attachment; filename="gptw-gti.csv"'})


@app.post("/gptw/programar", response_class=HTMLResponse)
async def gptw_programar(req: Request):
    """Programa a janela do ciclo e registra a inten\u00e7\u00e3o de notificar por e-mail.

    A programa\u00e7\u00e3o \u00e9 salva de verdade (entra no Desfazer e no ledger). O ENVIO do
    e-mail fica para configurar (SMTP/M365) \u2014 `gptw.notificar` re\u00fane o p\u00fablico e
    monta a mensagem, mas n\u00e3o dispara; a tela diz \u00abprogramado, n\u00e3o enviado\u00bb.
    Exige Editor, como toda altera\u00e7\u00e3o de configura\u00e7\u00e3o."""
    if negado(NIVEL_EDITOR):
        return HTMLResponse(html_vista(req, "gptw", "programar")
                            + alerta(negado(NIVEL_EDITOR)))
    form = await req.form()
    prog = gptwmod.normalizar_programacao({
        "ciclo": form.get("ciclo"),
        "abertura": form.get("abertura"),
        "fechamento": form.get("fechamento"),
        "notificar": bool(form.get("notificar")),
        "status": "programada",
        "agendado_em": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "agendado_por": acesso_vigente().usuario_id or "-",
    })
    marcar_ponto()
    ESTADO.config.gptw_programacao = prog
    extra = ""
    if prog["notificar"]:
        n = gptwmod.notificar(ESTADO.unidades, prog, ESTADO.config.tenant)
        extra = " " + T("Notifica\u00e7\u00e3o preparada para {n} colaboradores com e-mail "
                        "\u2014 {motivo}.", n=n["destinatarios"], motivo=n["motivo"])
    commit("alterar", "-", "Avaliação Mestre pesquisa programada",
           {"ciclo": prog["ciclo"], "notificar": prog["notificar"]})
    rot = gptwmod.ROTULO_CICLO.get(prog["ciclo"], prog["ciclo"])
    return HTMLResponse(html_vista(req, "gptw", "programar") + alerta(
        T("Pesquisa programada \u2014 ciclo {ciclo}.", ciclo=T(rot)) + extra))

