"""Envio de e-mail — pronto, esperando a credencial.

O provisionamento de TI já sabe a quem avisar; o que faltava era o carteiro.
Este módulo existe inteiro, com teste, e liga sozinho quando `SMTP_HOST` e
`SMTP_SENHA` aparecerem no ambiente. Até lá `configurado()` devolve False e
quem chama continua funcionando — a fila na tela segue sendo a notificação.

Duas decisões:

**Falha de envio nunca derruba a operação que a disparou.** Abrir um pedido de
provisionamento é o fato importante; avisar por e-mail é consequência. Se o
servidor de e-mail estiver fora, o pedido continua aberto na fila e o erro fica
registrado — o contrário perderia o pedido por causa do carteiro.

**Nada é enviado sem destinatário explícito.** Sem `SMTP_DE` ou sem lista de
destino a função recusa em vez de tentar adivinhar remetente, que é como
mensagem corporativa cai em spam e ninguém entende por quê.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate


def _env(nome: str, padrao: str = "") -> str:
    return (os.environ.get(nome) or padrao).strip()


def ajustes() -> dict:
    return {
        "host": _env("SMTP_HOST"),
        "porta": int(_env("SMTP_PORTA", "587") or 587),
        "usuario": _env("SMTP_USUARIO"),
        "senha": _env("SMTP_SENHA"),
        "de": _env("SMTP_DE"),
        "nome_de": _env("SMTP_NOME", "GPlanSiS|Peoples"),
        # STARTTLS na 587, SSL direto na 465 — a porta diz o modo, e forçar o
        # errado dá "connection reset" sem explicação.
        "ssl_direto": _env("SMTP_SSL") == "1" or _env("SMTP_PORTA") == "465",
    }


def configurado() -> bool:
    a = ajustes()
    return bool(a["host"] and a["de"])


def situacao() -> dict:
    a = ajustes()
    return {
        "configurado": configurado(),
        "host": a["host"],
        "porta": a["porta"],
        "de": a["de"],
        "autenticado": bool(a["usuario"]),
        "modo": "SSL" if a["ssl_direto"] else "STARTTLS",
    }


def montar(para: list[str], assunto: str, texto: str,
           responder_para: str = "") -> EmailMessage:
    a = ajustes()
    msg = EmailMessage()
    msg["From"] = formataddr((a["nome_de"], a["de"]))
    msg["To"] = ", ".join(para)
    msg["Subject"] = assunto
    msg["Date"] = formatdate(localtime=True)
    if responder_para:
        msg["Reply-To"] = responder_para
    msg.set_content(texto)
    return msg


def enviar(para: list[str], assunto: str, texto: str,
           responder_para: str = "", tempo: int = 20) -> tuple[bool, str]:
    """(ok, detalhe). Nunca levanta: quem chama não deve cair por causa disto."""
    destino = [e.strip() for e in (para or []) if e and "@" in e]
    if not destino:
        return False, "sem destinatário"
    if not configurado():
        return False, "SMTP não configurado"

    a = ajustes()
    msg = montar(destino, assunto, texto, responder_para)
    try:
        if a["ssl_direto"]:
            with smtplib.SMTP_SSL(a["host"], a["porta"], timeout=tempo,
                                  context=ssl.create_default_context()) as s:
                if a["usuario"]:
                    s.login(a["usuario"], a["senha"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(a["host"], a["porta"], timeout=tempo) as s:
                s.ehlo()
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
                if a["usuario"]:
                    s.login(a["usuario"], a["senha"])
                s.send_message(msg)
        return True, f"enviado para {len(destino)} destinatário(s)"
    except Exception as erro:                        # noqa: BLE001 — texto do servidor
        return False, str(erro).strip().splitlines()[0][:200]


# ---------------------------------------------------------------------------
# Mensagens do sistema
# ---------------------------------------------------------------------------
def texto_provisionamento(pedido: dict, t) -> tuple[str, str]:
    """(assunto, corpo) de um pedido de provisionamento. `t` traduz."""
    assunto = t("[GPlanSiS|Peoples] Provisionamento: {pessoa} — {de} → {para}",
                pessoa=pedido["pessoa"], de=pedido["de"], para=pedido["para"])
    linhas = [
        t("Mudança de departamento registrada no organograma."),
        "",
        f"{t('Pessoa')}: {pedido['pessoa']} ({pedido['codigo']})",
        f"{t('Cargo')}: {pedido.get('cargo') or '—'}",
        f"{t('E-mail')}: {pedido.get('email') or '—'}",
        f"{t('Mudança')}: {pedido['de']} → {pedido['para']}",
        "",
    ]
    # Revogar primeiro: acesso a mais é risco, acesso a menos é atrito. Só um
    # dos dois piora com o tempo, e é o que a pessoa lê primeiro.
    if pedido["revogar"]:
        linhas.append(t("REVOGAR:"))
        linhas += [f"  - {s}" for s in pedido["revogar"]]
        linhas.append("")
    if pedido["conceder"]:
        linhas.append(t("CONCEDER:"))
        linhas += [f"  + {s}" for s in pedido["conceder"]]
        linhas.append("")
    linhas.append(t("Pedido {id}, aberto em {quando}.",
                    id=pedido["id"], quando=pedido["aberta_em"][:16].replace("T", " ")))
    return assunto, "\n".join(linhas)
