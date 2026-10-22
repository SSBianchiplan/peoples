"""Acesso ao GPlanSiS|Peoples — sessão assinada e a entrada pelo login próprio.

O desenho da sessão veio do GPlanSIS-Planner: JWT HS256 assinado localmente,
sem biblioteca; segredo do ambiente, aleatório por processo em desenvolvimento;
segredo forte obrigatório quando a autenticação é exigida. Como a tela é
montada no servidor a cada requisição, a sessão viaja em **cookie HttpOnly** —
inacessível a JavaScript, que é o ponto: sem XSS conseguir ler a sessão.

A autenticação é do PRÓPRIO sistema: e-mail + senha, conferidos por
`orga.usuarios` (scrypt, arquivo de credenciais fora do estado, freio a força
bruta). Não há mais SSO corporativo (Microsoft Entra ID): o Peoples vive no hub
gplansis.com, onde cada sistema tem o seu login, e a identidade continua sendo o
e-mail do organograma — a credencial só prova que a pessoa é quem diz ser; papel
e escopo seguem no RBAC (`Config.acessos`).

`ORG_EXIGIR_LOGIN=1` fecha o sistema. Sem isso ele segue aberto — o modo de
trabalho de mesa; ligar por conta própria trancaria a porta de quem já está
usando.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

TTL_PADRAO = 8 * 3600          # jornada de trabalho, não semana
COOKIE = "org_sessao"


# ---------------------------------------------------------------------------
# Configuração de ambiente
# ---------------------------------------------------------------------------
def _env(nome: str, padrao: str = "") -> str:
    return (os.environ.get(nome) or padrao).strip()


def exigir_login() -> bool:
    return _env("ORG_EXIGIR_LOGIN") == "1"


def dominios() -> tuple[str, ...]:
    """Domínios aceitos no login. Vazio = qualquer um (o hub tem convidados)."""
    bruto = _env("ORG_DOMINIOS", "")
    return tuple(d.strip().lower() for d in bruto.split(",") if d.strip())


def superadmins() -> frozenset[str]:
    """E-mails que entram SEMPRE como Administrador total, mesmo estando fora do
    organograma ATIVO — o operador do sistema. Sem isto, trocar o organograma
    ativo para um que não contém o operador o trancava para fora do próprio
    sistema. `ORG_SUPERADMINS` (lista por vírgula) acrescenta; o padrão garante o
    dono à prova de variável esquecida."""
    bruto = _env("ORG_SUPERADMINS", "contato@gplansis.com")
    return frozenset(e.strip().lower() for e in bruto.split(",") if e.strip())


def e_superadmin(email: str) -> bool:
    return bool(email) and email.strip().lower() in superadmins()


# ---------------------------------------------------------------------------
# Segredo
# ---------------------------------------------------------------------------
_SEGREDO_VOLATIL = secrets.token_hex(32)


def segredo() -> str:
    """Segredo de assinatura.

    Com autenticação exigida, um segredo fraco ou ausente é erro de
    configuração e não pode passar em silêncio: seria sessão forjável. Em
    desenvolvimento vale um aleatório por processo — as sessões caem a cada
    reinício, o que é chato e correto.
    """
    s = _env("JWT_SECRET")
    if exigir_login():
        if len(s) < 32:
            raise RuntimeError(
                "ORG_EXIGIR_LOGIN=1 exige JWT_SECRET com 32+ caracteres. Gere com: "
                'python -c "import secrets; print(secrets.token_hex(32))"')
    return s or _SEGREDO_VOLATIL


# ---------------------------------------------------------------------------
# JWT HS256, à mão
# ---------------------------------------------------------------------------
def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode().rstrip("=")


def _deb64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _hmac(dados: str) -> str:
    return _b64(hmac.new(segredo().encode(), dados.encode(), hashlib.sha256).digest())


def assinar(carga: dict, ttl: int = TTL_PADRAO) -> str:
    agora = int(time.time())
    cabecalho = _b64(json.dumps({"alg": "HS256", "typ": "JWT"},
                                separators=(",", ":")).encode())
    corpo = _b64(json.dumps({**carga, "iat": agora, "exp": agora + ttl},
                            separators=(",", ":"), ensure_ascii=False).encode())
    dados = f"{cabecalho}.{corpo}"
    return f"{dados}.{_hmac(dados)}"


def verificar(token: str | None) -> dict | None:
    """Carga do token, ou None. `exp` é obrigatório — token sem prazo é eterno."""
    if not token or not isinstance(token, str):
        return None
    partes = token.split(".")
    if len(partes) != 3:
        return None
    cabecalho, corpo, assinatura = partes
    esperado = _hmac(f"{cabecalho}.{corpo}")
    # Comparação em tempo constante: `==` em string vaza o prefixo correto pelo
    # tempo de resposta, e isso basta para forjar assinatura byte a byte.
    if not hmac.compare_digest(assinatura, esperado):
        return None
    try:
        carga = json.loads(_deb64(corpo))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(carga, dict) or not carga.get("exp"):
        return None
    if int(carga["exp"]) < int(time.time()):
        return None
    return carga


# ---------------------------------------------------------------------------
# Identidade: o e-mail e o organograma
# ---------------------------------------------------------------------------
def dominio_valido(email: str) -> bool:
    email = (email or "").strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        return False
    aceitos = dominios()
    return not aceitos or email.split("@", 1)[1] in aceitos


def por_email(unidades, email: str):
    """A unidade cujo e-mail corporativo é este.

    A pessoa que entra **é** alguém do organograma sempre que puder: se o e-mail
    bate com um nó, a sessão fica vinculada a ele (avatar, escopo "próprio").
    Quem tem senha e não é nó entra desvinculado — o operador do sistema, por
    exemplo — e recebe o acesso definido no RBAC (ou o de superadmin).
    """
    alvo = (email or "").strip().lower()
    if not alvo:
        return None
    us = unidades.values() if isinstance(unidades, dict) else unidades
    return next((u for u in us if (u.email or "").strip().lower() == alvo), None)
