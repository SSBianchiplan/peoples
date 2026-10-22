"""Multi-organograma: o registro dos organogramas e onde mora o estado de cada um.

O sistema nasceu com UM organograma — um `ESTADO` global, um `estado.json`, um
slug ("peoples") fixo no banco. Este módulo generaliza isso sem quebrar o que
existe:

- um **registro** leve (`dados/organogramas.json`) lista os organogramas e aponta
  o ATIVO — o que fica visível no cabeçalho;
- cada organograma tem seu **estado próprio**: o que já existia continua no
  `dados/estado.json` de sempre (o slug padrão), sem mover arquivo em produção;
  os novos ganham `dados/estado-<slug>.json`;
- o banco já é multi-tenant (`org.organograma.slug`); aqui o slug deixa de ser
  fixo e passa a ser o do organograma ativo.

Sem dependência de `main`: são helpers puros de I/O e de manipulação do registro.
Quem orquestra (carregar/gravar/trocar) é o `main`, que conhece o `ESTADO`.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

# O slug do organograma que já existia. O estado dele fica no arquivo legado
# `dados/estado.json`, e no banco ele é a linha `org.organograma` que a carga já
# escreveu — por isso o padrão não muda de nome nem de caminho.
SLUG_PADRAO = "peoples"
NOME_PADRAO = "GPlanSiS|Peoples"

_DADOS = Path(__file__).resolve().parent.parent / "dados"
REGISTRO = _DADOS / "organogramas.json"

# O banco exige slug ~ '^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$': 3–50 chars, começa e
# termina em alfanumérico, miolo alfanumérico ou hífen. `slugificar` garante isso.
_LIMPAR = re.compile(r"[^a-z0-9]+")
MIN_SLUG, MAX_SLUG = 3, 50


def caminho_estado(slug: str) -> Path:
    """Onde mora o estado de um organograma. O padrão fica no arquivo legado;
    os demais em `estado-<slug>.json`."""
    return _DADOS / "estado.json" if slug == SLUG_PADRAO else _DADOS / f"estado-{slug}.json"


def slugificar(nome: str, existentes: set[str] | None = None) -> str:
    """Nome -> slug válido para o banco, único entre `existentes`."""
    base = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode()
    base = _LIMPAR.sub("-", base.lower()).strip("-")
    if len(base) < MIN_SLUG:
        base = (base + "-org").strip("-")
    base = base[:MAX_SLUG].strip("-") or "org"
    existentes = existentes or set()
    if base not in existentes:
        return base
    # Colisão: sufixo -2, -3… sem estourar o limite de tamanho.
    raiz = base[:MAX_SLUG - 3].strip("-") or "org"
    n = 2
    while f"{raiz}-{n}" in existentes:
        n += 1
    return f"{raiz}-{n}"


def _registro_padrao() -> dict:
    return {"ativo": SLUG_PADRAO,
            "lista": [{"slug": SLUG_PADRAO, "nome": NOME_PADRAO, "criado_em": None}]}


def ler() -> dict:
    """O registro vigente. Devolve o padrão (sem escrever) quando não há arquivo —
    é o que mantém a compatibilidade: quem nunca criou um segundo organograma
    segue com o `peoples` no `estado.json`, sem registro em disco."""
    if REGISTRO.exists():
        try:
            reg = json.loads(REGISTRO.read_text(encoding="utf-8"))
            if isinstance(reg, dict) and reg.get("lista"):
                return _sanear(reg)
        except (json.JSONDecodeError, ValueError, OSError):
            pass
    return _registro_padrao()


def _sanear(reg: dict) -> dict:
    lista = [o for o in reg.get("lista", []) if isinstance(o, dict) and o.get("slug")]
    if not lista:
        return _registro_padrao()
    slugs = {o["slug"] for o in lista}
    ativo = reg.get("ativo")
    if ativo not in slugs:                       # ativo apagado ou ausente
        ativo = lista[0]["slug"]
    return {"ativo": ativo, "lista": lista}


def salvar(reg: dict) -> None:
    _DADOS.mkdir(parents=True, exist_ok=True)
    REGISTRO.write_text(json.dumps(_sanear(reg), ensure_ascii=False, indent=1),
                        encoding="utf-8")


def listar(reg: dict | None = None) -> list[dict]:
    return (reg or ler())["lista"]


def ativo(reg: dict | None = None) -> str:
    return (reg or ler())["ativo"]


def existe(reg: dict, slug: str) -> bool:
    return any(o["slug"] == slug for o in reg.get("lista", []))


def nome_de(reg: dict, slug: str) -> str:
    for o in reg.get("lista", []):
        if o["slug"] == slug:
            return o.get("nome") or slug
    return slug


def adicionar(reg: dict, nome: str, criado_em: str | None = None) -> tuple[dict, str]:
    """Acrescenta um organograma e devolve (registro, slug novo). Não muda o
    ativo — quem chama decide se troca."""
    slug = slugificar(nome, {o["slug"] for o in reg.get("lista", [])})
    reg = _sanear(reg)
    reg["lista"].append({"slug": slug, "nome": (nome or slug).strip()[:80],
                         "criado_em": criado_em})
    return reg, slug


def renomear(reg: dict, slug: str, nome: str) -> dict:
    reg = _sanear(reg)
    for o in reg["lista"]:
        if o["slug"] == slug:
            o["nome"] = (nome or slug).strip()[:80]
    return reg


def remover(reg: dict, slug: str) -> dict:
    """Remove um organograma do registro. Nunca deixa a lista vazia; se o ativo
    sair, o primeiro que sobrar assume."""
    reg = _sanear(reg)
    if len(reg["lista"]) <= 1:
        return reg                                # o último não se apaga
    reg["lista"] = [o for o in reg["lista"] if o["slug"] != slug]
    return _sanear(reg)                            # reelege ativo se preciso


def definir_ativo(reg: dict, slug: str) -> dict:
    reg = _sanear(reg)
    if existe(reg, slug):
        reg["ativo"] = slug
    return reg
