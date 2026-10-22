"""Smoke test: percorre TODAS as rotas GET do sistema, nos três idiomas e em
cada organograma registrado, e acusa qualquer 5xx ou exceção.

Roda contra uma CÓPIA do projeto (o estado real não pode ser tocado — importar
`main` e chamar rota grava em `dados/`): copie o repositório para uma pasta
temporária e execute lá.

    python ferramentas/smoke.py
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("ORG_USUARIOS_ARQUIVO", str(RAIZ / "dados" / "usuarios-smoke.json"))

from fastapi.testclient import TestClient      # noqa: E402

from orga import main, organogramas, usuarios  # noqa: E402

IGNORAR = {"/sair", "/desfazer", "/refazer", "/restaurar", "/filtros/limpar",
           "/foco/limpar", "/orientacao", "/orientacao/lateral", "/agrupamento"}
PARAMS = {"{vista}": ["painel_rh", "canvas", "estrutura", "tabela", "tempo", "dcr", "cgv",
                      "talentos", "gptw", "onebyone", "configuracoes"],
          "{modo}": ["pessoa", "equipe"], "{n}": ["2"], "{qual}": ["equipe", "lideranca", "modelo"],
          "{tabela}": ["org.unidade"], "{ciclo}": ["completa"]}


def rotas_get() -> list[str]:
    saida = []
    for r in main.app.routes:
        caminho = getattr(r, "path", "")
        metodos = getattr(r, "methods", None) or set()
        if "GET" in metodos and caminho not in IGNORAR and not caminho.startswith("/openapi"):
            saida.append(caminho)
    return sorted(set(saida))


def expandir(caminho: str, uid: str, ref: str) -> list[str]:
    variantes = [caminho]
    for chave, valores in PARAMS.items():
        if chave in caminho:
            variantes = [v.replace(chave, x) for v in variantes for x in valores]
    variantes = [v.replace("{uid}", uid).replace("{cid}", uid).replace("{ref}", ref)
                  .replace("{chave}", ref).replace("{pid}", "x").replace("{aid}", "x")
                  .replace("{mid}", "x").replace("{item_id}", "x").replace("{tipo}", "fup")
                  .replace("{slug}", "peoples") for v in variantes]
    return variantes


def main_() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    usuarios.definir_senha("smoke@gplansis.com", "smoke-teste-123")
    problemas: list[str] = []
    total = 0
    with TestClient(main.app, raise_server_exceptions=False) as cli:
        cli.post("/entrar", data={"email": "smoke@gplansis.com", "senha": "smoke-teste-123"})
        for org in organogramas.listar():
            main.trocar_organograma(org["slug"])
            us = list(main.ESTADO.unidades.values())
            alvo = next((u for u in us if u.parent_id), us[0])
            for idioma in ("pt-BR", "en-US", "es"):
                cli.post("/config/idioma", data={"idioma": idioma})
                for rota in rotas_get():
                    for url in expandir(rota, alvo.id, alvo.codigo):
                        total += 1
                        t0 = time.perf_counter()
                        try:
                            r = cli.get(url)
                        except Exception as erro:            # noqa: BLE001
                            problemas.append(f"[{org['slug']}/{idioma}] {url}: EXCEÇÃO {erro!r}")
                            continue
                        dt = time.perf_counter() - t0
                        if r.status_code >= 500:
                            trecho = re.sub(r"\s+", " ", r.text[:160])
                            problemas.append(f"[{org['slug']}/{idioma}] {url}: {r.status_code} {trecho}")
                        elif dt > 8:
                            problemas.append(f"[{org['slug']}/{idioma}] {url}: lento ({dt:.1f}s)")
    print(f"{total} requisições GET; {len(problemas)} problema(s)")
    for p in problemas:
        print("  ", p)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main_())
