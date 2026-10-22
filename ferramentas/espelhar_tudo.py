"""Desce TODOS os organogramas para o banco, agora.

O espelho do sistema é disparado por mutação (`gravar()`): num servidor recém
instalado o banco fica vazio até a primeira edição. Este script força o
dual-write de cada organograma registrado — estrutura, ledger e o resto do
estado (`org.estado_extra`) — e devolve o ativo ao que era.

Roda NO servidor, como o usuário do serviço, com o `.env` de produção:

    cd /opt/peoples && sudo -u peoples .venv/bin/python ferramentas/espelhar_tudo.py

Exige ORG_ESPELHO=1 e ORG_DATABASE_URL (é o que o `.env` do instalador já traz).
Só leitura do estado (a troca de organograma grava o mesmo conteúdo de volta).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from orga import main, banco, organogramas   # noqa: E402


def espelhar(slug: str) -> dict:
    main._ESTRUTURA_ESPELHADA = None
    main._LEDGER_ESPELHADO = None
    main._EXTRA_ESPELHADO = None
    main.espelhar_estrutura()
    main.espelhar_ledger()
    main.espelhar_extra()
    # Os módulos gravam no banco a cada salvamento; aqui desce o que já existe.
    cfg = main.ESTADO.config
    for modulo, regs in ((main.cgvmod, cfg.cgv_registros), (main.dcrmod, cfg.dcr_cargos),
                         (main.talentosmod, cfg.mapa_talentos),
                         (main.gptwmod, cfg.gptw_respostas), (main.obomod, cfg.onebyone)):
        for reg in regs or []:
            try:
                modulo.salvar_no_banco(reg, slug)
            except Exception as erro:                    # noqa: BLE001
                print(f"  aviso: {modulo.__name__} não desceu um registro: {erro}")
    v = banco.verificar_espelho(list(main.ESTADO.unidades.values()), slug=slug)
    return {"slug": slug, "nos": len(main.ESTADO.unidades), "eventos": len(main.ESTADO.eventos),
            "espelho_ok": bool(v.get("ok")), "detalhe": v.get("resumo") or v.get("erro") or ""}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if os.environ.get("ORG_ESPELHO") != "1" or not banco.situacao().get("pronto"):
        sys.exit("ORG_ESPELHO=1 e ORG_DATABASE_URL são obrigatórios (banco pronto).")
    ativo = organogramas.ativo()
    for org in organogramas.listar():
        main.trocar_organograma(org["slug"])
        r = espelhar(org["slug"])
        print(f"{r['slug']:22s} nós={r['nos']:4d} eventos={r['eventos']:4d} "
              f"espelho={'ok' if r['espelho_ok'] else 'DIVERGE'} {r['detalhe']}")
    main.trocar_organograma(ativo)
    from orga import usuarios
    usuarios._espelhar(usuarios.ler())
    print(f"usuários espelhados: {usuarios.total()}")
    print("contagem no banco:", banco.contagem_real())
