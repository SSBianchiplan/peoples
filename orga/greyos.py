"""
Encaixe (seam) com o GPlanSiS|OS — DESLIGADO por ora.

O GPlanSiS|OS é o sistema de EOS/gestão (hoje um link no cabeçalho, docs/greyos.html).
As missões de evolução do One-on-One (que vêm do PDI da Conversa de Valor) precisam, um dia,
virar tarefas lá — com reuniões automáticas no Teams. Este módulo é o ponto de
conexão: formata as missões como tarefas do GPlanSiS|OS e as exporta num payload que o
GPlanSiS|OS importa. A conexão VIVA (API/webhook/Teams) fica para depois — no padrão
do `m365.py`: funções puras (`tarefa_de_missao`, `exportar`), sem chamada externa
aqui. `configurado()` é `False` até a federação existir, como o CD por tag.

Puro: recebe missões, devolve dicionários. Nada de rede neste arquivo.
"""
from __future__ import annotations

SCHEMA = "greyos.task"
VERSAO_PAYLOAD = "1"


def tarefa_de_missao(m: dict) -> dict:
    """Uma missão do One-on-One no formato de tarefa do GPlanSiS|OS. `external_id` é o id
    da missão — a reimportação atualiza a mesma tarefa, não empilha."""
    c = m.get("conteudo", {}) if isinstance(m.get("conteudo"), dict) else {}
    return {"external_id": m.get("id", ""), "owner_ref": m.get("ref", ""),
            "leader_ref": m.get("lider_ref", ""), "owner_name": m.get("nome", ""),
            "title": c.get("titulo", ""), "action": c.get("acao", ""),
            "due": c.get("prazo", ""), "status": c.get("status", ""),
            "source": c.get("origem", "One-on-One"), "progress_note": c.get("evolucao", "")}


def exportar(missoes) -> dict:
    """O payload de exportação: todas as missões como tarefas do GPlanSiS|OS. É o que o
    GPlanSiS|OS importa enquanto a integração viva não existe."""
    tarefas = [tarefa_de_missao(m) for m in (missoes or [])
               if m.get("tipo") == "missao"]
    return {"schema": SCHEMA, "version": VERSAO_PAYLOAD,
            "count": len(tarefas), "tasks": tarefas}


def configurado() -> bool:
    """A integração viva com o GPlanSiS|OS/Teams ainda não existe — só a exportação.
    Espelha `m365.configurado()`: quando a federação chegar, isto liga."""
    return False


def enviar(missoes) -> tuple[bool, str]:
    """O ponto de conexão futuro (webhook/API do GPlanSiS|OS). Hoje NÃO conecta: devolve
    o payload pronto e a indicação de usar a exportação. Deixado aqui para a próxima
    fase plugar a chamada real sem mexer no resto."""
    if not configurado():
        return False, "greyos-desconectado"
    return False, "greyos-desconectado"     # sem chamada externa nesta fase
