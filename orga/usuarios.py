"""Usuários e senhas do próprio sistema — o login do GPlanSiS|Peoples.

Substitui a entrada corporativa (Microsoft Entra ID) e a "identificação por
e-mail" que não provava nada. Aqui a pessoa PROVA quem é: e-mail + senha,
conferidos contra credenciais que só o servidor lê.

Decisões:

**A identidade continua sendo o e-mail do organograma.** Este módulo guarda só
a CREDENCIAL (o hash da senha); papel, escopo e módulos visíveis seguem no RBAC
do organograma (`Config.acessos`). Quem tem senha mas não é nó de nenhum
organograma entra desvinculado — é o caso do operador do sistema.

**scrypt da biblioteca padrão.** Sem dependência nova, memória-dura (resiste a
GPU), parâmetros gravados junto do hash para poderem subir no futuro sem
invalidar o que existe. Comparação em tempo constante.

**Arquivo próprio, fora do `estado.json`, e espelho no banco.** O estado é por
organograma e viaja em backup, exportação e espelho; credencial não pode ir
junto. O arquivo é GLOBAL (uma senha vale para todos os organogramas) e, com
`ORG_ESPELHO=1` e Postgres pronto, cada gravação desce para `org.usuario` —
o mesmo dual-write não-fatal do resto do sistema. Sem arquivo (máquina nova,
restauração), as credenciais voltam do banco.

**Sem enumeração de usuário.** `conferir` custa o mesmo tempo para e-mail
inexistente e para senha errada, e a mensagem ao usuário é uma só.

**Freio a força bruta em memória.** Cinco erros seguidos por e-mail travam a
conta por um minuto (single worker, como o resto do estado). Não persiste — um
restart zera, e tudo bem: o objetivo é tornar o palpite caro, não punir.

Linha de comando (o primeiro administrador nasce aqui, pela tela de primeiro
acesso, ou por `ORG_ADMIN_EMAIL`/`ORG_ADMIN_SENHA` no primeiro arranque):

    python -m orga.usuarios definir tic@gplansis.com            # pede a senha
    python -m orga.usuarios definir tic@gplansis.com --senha X  # sem prompt
    python -m orga.usuarios listar
    python -m orga.usuarios remover alguem@gplansis.com
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_LOG = logging.getLogger("orga.usuarios")

_DADOS = Path(__file__).resolve().parent.parent / "dados"
ARQUIVO_PADRAO = _DADOS / "usuarios.json"

# scrypt: N=2^14, r=8, p=1 — ~16 MB por hash, ~50 ms numa CPU modesta. Cabe
# num VPS de 1 vCPU sem virar gargalo, e é o piso que a OWASP recomenda.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
SENHA_MINIMA = 8
TENTATIVAS_MAX = 5
TRAVA_SEGUNDOS = 60

# Hash "fantasma" para e-mail inexistente: `conferir` sempre calcula um scrypt,
# senão o tempo de resposta diria quem existe.
_FANTASMA = None

# Cache do arquivo por mtime: a guarda de acesso pergunta "precisa trocar?" a
# cada requisição, e ler+parsear JSON a cada clique seria desperdício.
_CACHE: dict[str, tuple[float, dict]] = {}


def arquivo() -> Path:
    """Onde as credenciais moram. `ORG_USUARIOS_ARQUIVO` permite isolar (testes)."""
    return Path(os.environ.get("ORG_USUARIOS_ARQUIVO") or ARQUIVO_PADRAO)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalizar(email: str) -> str:
    return (email or "").strip().lower()


# ---------------------------------------------------------------------------
# Hash
# ---------------------------------------------------------------------------
def hash_senha(senha: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(senha.encode("utf-8"), salt=salt,
                            n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return "scrypt$%d$%d$%d$%s$%s" % (
        SCRYPT_N, SCRYPT_R, SCRYPT_P,
        base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def senha_confere(senha: str, guardado: str) -> bool:
    try:
        alg, n, r, p, salt_b64, hash_b64 = guardado.split("$")
        if alg != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        esperado = base64.b64decode(hash_b64)
        digest = hashlib.scrypt(senha.encode("utf-8"), salt=salt,
                                n=int(n), r=int(r), p=int(p), dklen=len(esperado))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, esperado)


def politica(senha: str) -> str | None:
    """Motivo da recusa, ou None. Política curta e honesta: tamanho. Regras de
    "maiúscula + símbolo" produzem senhas previsíveis, não fortes. Os textos
    são chaves do catálogo de idiomas — quem exibe traduz."""
    if not senha or len(senha) < SENHA_MINIMA:
        return "A senha precisa ter pelo menos 8 caracteres."
    if len(senha) > 128:
        return "A senha é longa demais (máximo 128 caracteres)."
    if senha.strip() != senha:
        return "A senha não pode começar nem terminar com espaço."
    return None


# ---------------------------------------------------------------------------
# Espelho no banco (dual-write, opt-in, não-fatal — como o resto do sistema)
# ---------------------------------------------------------------------------
def _espelho_ligado() -> bool:
    if os.environ.get("ORG_ESPELHO", "0").strip() != "1":
        return False
    try:
        from . import banco
        return bool(banco.situacao().get("pronto"))
    except Exception:                                # noqa: BLE001
        return False


def _espelhar(d: dict) -> None:
    if not _espelho_ligado():
        return
    try:
        from . import banco
        ok, msg = banco.aplicar(banco.sql_usuarios(d.get("usuarios") or {}))
        if not ok:
            _LOG.warning("espelho de usuários falhou (não-fatal): %s", msg)
    except Exception as erro:                        # noqa: BLE001
        _LOG.warning("espelho de usuários falhou (não-fatal): %s", erro)


def _restaurar_do_banco() -> dict | None:
    """Sem arquivo, as credenciais voltam do banco — e o arquivo é recriado, para
    o caminho quente (a guarda por requisição) não depender do Postgres."""
    if not _espelho_ligado():
        return None
    try:
        from . import banco
        us = banco.carregar_usuarios()
    except Exception:                                # noqa: BLE001
        return None
    if not us:
        return None
    d = {"usuarios": us}
    _gravar_arquivo(d)
    _LOG.info("credenciais restauradas do banco (%d usuário(s))", len(us))
    return d


# ---------------------------------------------------------------------------
# Arquivo
# ---------------------------------------------------------------------------
def ler() -> dict:
    p = arquivo()
    chave = str(p)
    if not p.exists():
        _CACHE.pop(chave, None)
        return _restaurar_do_banco() or {"usuarios": {}}
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return {"usuarios": {}}
    em_cache = _CACHE.get(chave)
    if em_cache and em_cache[0] == mtime:
        return em_cache[1]
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if not (isinstance(d, dict) and isinstance(d.get("usuarios"), dict)):
            d = {"usuarios": {}}
    except (json.JSONDecodeError, OSError):
        d = {"usuarios": {}}
    _CACHE[chave] = (mtime, d)
    return d


def _gravar_arquivo(d: dict) -> None:
    p = arquivo()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)                                   # troca atômica
    try:
        os.chmod(p, 0o600)                           # só o dono lê
    except OSError:
        pass
    _CACHE.pop(str(p), None)


def salvar(d: dict) -> None:
    _gravar_arquivo(d)
    _espelhar(d)


def existe(email: str) -> bool:
    return normalizar(email) in ler()["usuarios"]


def registro(email: str) -> dict | None:
    return ler()["usuarios"].get(normalizar(email))


def listar() -> list[dict]:
    us = ler()["usuarios"]
    return [{"email": e, **{k: v for k, v in r.items() if k != "hash"}}
            for e, r in sorted(us.items())]


def total() -> int:
    return len(ler()["usuarios"])


def definir_senha(email: str, senha: str, precisa_trocar: bool = False,
                  por: str = "") -> None:
    """Cria ou redefine. `precisa_trocar` marca senha temporária dada pelo
    administrador: no primeiro login a pessoa é levada a escolher a sua."""
    email = normalizar(email)
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("E-mail inválido.")
    motivo = politica(senha)
    if motivo:
        raise ValueError(motivo)
    d = ler()
    atual = dict(d["usuarios"].get(email) or {"criado_em": _agora()})
    atual.update({"hash": hash_senha(senha), "atualizado_em": _agora(),
                  "precisa_trocar": bool(precisa_trocar), "ativo": True,
                  "definida_por": por or atual.get("definida_por", "")})
    d = {"usuarios": {**d["usuarios"], email: atual}}
    salvar(d)
    _TENTATIVAS.pop(email, None)


def remover(email: str) -> bool:
    email = normalizar(email)
    d = ler()
    if email not in d["usuarios"]:
        return False
    d = {"usuarios": {k: v for k, v in d["usuarios"].items() if k != email}}
    salvar(d)
    return True


def marcar_trocada(email: str) -> None:
    d = ler()
    r = d["usuarios"].get(normalizar(email))
    if r:
        novo = {**r, "precisa_trocar": False, "atualizado_em": _agora()}
        salvar({"usuarios": {**d["usuarios"], normalizar(email): novo}})


def precisa_trocar(email: str) -> bool:
    r = registro(email)
    return bool(r and r.get("precisa_trocar"))


# ---------------------------------------------------------------------------
# Conferência + freio
# ---------------------------------------------------------------------------
_TENTATIVAS: dict[str, list[float]] = {}


def travado(email: str) -> int:
    """Segundos que faltam da trava, ou 0."""
    email = normalizar(email)
    agora = time.time()
    recentes = [t for t in _TENTATIVAS.get(email, []) if agora - t < TRAVA_SEGUNDOS]
    if recentes:
        _TENTATIVAS[email] = recentes
    else:
        _TENTATIVAS.pop(email, None)
    if len(recentes) >= TENTATIVAS_MAX:
        return int(TRAVA_SEGUNDOS - (agora - recentes[0])) + 1
    return 0


def _anotar_falha(email: str) -> None:
    _TENTATIVAS.setdefault(normalizar(email), []).append(time.time())


def conferir(email: str, senha: str) -> bool:
    """E-mail + senha batem? Tempo constante entre "não existe" e "senha errada"."""
    global _FANTASMA
    email = normalizar(email)
    if travado(email):
        return False
    r = ler()["usuarios"].get(email)
    if r is None or not r.get("ativo", True):
        if _FANTASMA is None:
            _FANTASMA = hash_senha(secrets.token_hex(8))
        senha_confere(senha or "", _FANTASMA)      # paga o mesmo custo
        _anotar_falha(email)
        return False
    ok = senha_confere(senha or "", r.get("hash", ""))
    if ok:
        _TENTATIVAS.pop(email, None)
    else:
        _anotar_falha(email)
    return ok


def bootstrap_do_ambiente() -> str | None:
    """Primeiro arranque: se não há NENHUM usuário e o ambiente traz
    `ORG_ADMIN_EMAIL` + `ORG_ADMIN_SENHA`, cria esse acesso. Devolve o e-mail
    criado, ou None. Nunca sobrescreve: com um usuário que seja, não faz nada."""
    email = normalizar(os.environ.get("ORG_ADMIN_EMAIL", ""))
    senha = os.environ.get("ORG_ADMIN_SENHA", "")
    if not email or not senha or total():
        return None
    try:
        definir_senha(email, senha, precisa_trocar=False, por="ambiente")
    except ValueError:
        return None
    return email


# ---------------------------------------------------------------------------
# Linha de comando
# ---------------------------------------------------------------------------
def _cli(argv: list[str]) -> int:
    if not argv or argv[0] not in ("definir", "listar", "remover"):
        print(__doc__)
        return 2
    if argv[0] == "listar":
        for u in listar():
            marca = " (troca pendente)" if u.get("precisa_trocar") else ""
            print(f"{u['email']}  atualizado em {u.get('atualizado_em', '?')}{marca}")
        print(f"{total()} usuário(s) em {arquivo()}")
        return 0
    if len(argv) < 2:
        print("informe o e-mail")
        return 2
    email = argv[1]
    if argv[0] == "remover":
        print("removido" if remover(email) else "não existia")
        return 0
    if "--senha" in argv:
        senha = argv[argv.index("--senha") + 1]
    else:
        import getpass
        senha = getpass.getpass(f"Senha para {email}: ")
        if senha != getpass.getpass("Repita: "):
            print("as senhas não conferem")
            return 1
    try:
        definir_senha(email, senha, precisa_trocar="--temporaria" in argv, por="cli")
    except ValueError as e:
        print(f"recusado: {e}")
        return 1
    print(f"senha definida para {normalizar(email)} em {arquivo()}")
    return 0


if __name__ == "__main__":
    # O .env entra como no app: sem ele a CLI não veria ORG_ESPELHO nem a URL do
    # banco, e a conta ficaria só no arquivo — o banco descobriria no restart.
    from . import ambiente
    ambiente.carregar()
    sys.exit(_cli(sys.argv[1:]))
