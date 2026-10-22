"""Diretório social — reconhecimento e feedback público no card da pessoa.

O organograma diz a quem cada um responde. Não diz quem ajudou quem na semana
passada, e é justamente isso que atravessa a linha do organograma: o
reconhecimento quase sempre vem de fora da própria cadeia.

Três decisões que valem explicar, porque as três podem parecer restrição:

**É público, e por isso é assinado.** Não há anônimo. Reconhecimento anônimo
perde a força (ninguém sabe de quem veio) e feedback anônimo vira canal de
desabafo sem responsável — que é outra ferramenta, com outro cuidado, e não
esta. Quem escreve aparece.

**Feedback não é reconhecimento.** Os dois cabem, com rótulo distinto, porque
misturar "obrigado pela ajuda" com "isso poderia ter sido melhor" numa lista só
faz a pessoa evitar ler a lista.

**Quem escreveu pode apagar; quem recebeu pode ocultar.** Publicar sobre outra
pessoa cria uma obrigação: ela precisa poder tirar do próprio card. Não é
censura — é o mínimo de controle sobre o que fica escrito no seu nome, e o
registro continua no ledger.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

RECONHECIMENTO, FEEDBACK = "reconhecimento", "feedback"
TIPOS = (RECONHECIMENTO, FEEDBACK)

LIMITE = 600            # caracteres por mensagem
MAX_POR_CARD = 200      # teto do que fica guardado por pessoa

# Valores da cultura GPlanSiS|Peoples. O reconhecimento aponta para um deles: sem isso
# vira "valeu!" — simpático e sem informação nenhuma sobre o que a pessoa fez.
VALORES = {
    "teamwork": "Teamwork · trabalho em equipe",
    "respect": "Respect · respeito",
    "innovation": "Innovation · inovação",
    "ownership": "Ownership · atitude de dono",
}


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def valido(texto: str) -> str:
    return " ".join(str(texto or "").split())[:LIMITE]


def publicar(para_id: str, autor: dict, texto: str, tipo: str = RECONHECIMENTO,
             valor: str = "") -> dict | None:
    """Uma mensagem no card de alguém. None quando não há o que publicar."""
    corpo = valido(texto)
    if not corpo or not autor or not autor.get("nome"):
        return None
    return {
        "id": uuid.uuid4().hex[:12],
        "para": para_id,
        "autor_id": autor.get("id", ""),
        "autor": autor["nome"],
        "autor_cargo": autor.get("cargo", ""),
        "texto": corpo,
        "tipo": tipo if tipo in TIPOS else RECONHECIMENTO,
        "valor": valor if valor in VALORES else "",
        "quando": agora(),
        "oculto": False,
    }


def do_card(mural: list[dict], uid: str, incluir_ocultos: bool = False) -> list[dict]:
    """Mensagens de uma pessoa, da mais recente para a mais antiga."""
    itens = [m for m in mural or [] if m.get("para") == uid
             and (incluir_ocultos or not m.get("oculto"))]
    return sorted(itens, key=lambda m: m.get("quando", ""), reverse=True)


def contagem(mural: list[dict], uid: str) -> dict[str, int]:
    itens = do_card(mural, uid)
    return {
        "total": len(itens),
        RECONHECIMENTO: sum(1 for m in itens if m["tipo"] == RECONHECIMENTO),
        FEEDBACK: sum(1 for m in itens if m["tipo"] == FEEDBACK),
    }


def pode_remover(mensagem: dict, quem_id: str, admin: bool = False) -> bool:
    """Autor apaga o que escreveu; destinatário tira do próprio card."""
    if admin:
        return True
    # `bool(...)`: sem isso um `quem_id` vazio devolve a própria string vazia,
    # que é falsa mas não é False — e um teste de identidade falharia.
    return bool(quem_id) and quem_id in (mensagem.get("autor_id"),
                                         mensagem.get("para"))


def remover(mural: list[dict], mid: str, quem_id: str, admin: bool = False) -> bool:
    for i, m in enumerate(mural or []):
        if m.get("id") == mid:
            if not pode_remover(m, quem_id, admin):
                return False
            mural.pop(i)
            return True
    return False


def aparar(mural: list[dict], uid: str) -> None:
    """Mantém o card em MAX_POR_CARD; as mais antigas saem primeiro."""
    do_alvo = [m for m in mural if m.get("para") == uid]
    if len(do_alvo) <= MAX_POR_CARD:
        return
    excedente = sorted(do_alvo, key=lambda m: m.get("quando", ""))[
        :len(do_alvo) - MAX_POR_CARD]
    fora = {m["id"] for m in excedente}
    mural[:] = [m for m in mural if m.get("id") not in fora]


def ranking_valores(mural: list[dict]) -> list[tuple[str, int]]:
    """Quais valores a empresa mais reconhece. Sai da soma, não de pesquisa."""
    contagens: dict[str, int] = {}
    for m in mural or []:
        if m.get("tipo") == RECONHECIMENTO and m.get("valor") and not m.get("oculto"):
            contagens[m["valor"]] = contagens.get(m["valor"], 0) + 1
    return sorted(contagens.items(), key=lambda kv: -kv[1])
