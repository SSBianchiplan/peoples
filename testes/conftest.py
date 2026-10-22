"""Ajustes válidos para toda a suíte.

O sistema agora fala três idiomas, e a maior parte dos testes afirma texto em
português — o que é correto: é a língua fonte, e a chave do catálogo. Sem fixar
o idioma, bastava alguém deixar a interface em inglês para dezenas de testes
acusarem falha onde não havia defeito nenhum. Quem quiser testar outro idioma
troca dentro do próprio teste e devolve no fim, como faz `test_idiomas.py`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import idiomas                                                  # noqa: E402
from orga import main                                                     # noqa: E402


# Variáveis que mudam o comportamento do sistema e que o `.env` de quem
# desenvolve pode ter preenchido. A suíte fixa todas: o resultado do `pytest`
# não pode depender de qual integração está ligada na máquina de quem roda.
_AMBIENTE_NEUTRO = ("ORG_EXIGIR_LOGIN", "ORG_COOKIE_SEGURO", "CC_ATTRIBUTE",
                    "AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
                    "ORG_DATABASE_URL", "SMTP_HOST", "SMTP_DE", "ORG_ESPELHO",
                    "ORG_DOMINIOS", "ORG_ADMIN_EMAIL", "ORG_ADMIN_SENHA")


@pytest.fixture(scope="session", autouse=True)
def ambiente_isolado():
    """A suíte não depende do `.env` de quem está usando o sistema.

    `main` chama `ambiente.carregar()` no import, então tudo o que está no
    `.env` chega a `os.environ` antes do primeiro teste. Quando o Entra foi
    configurado de verdade nesta máquina, seis testes de acesso caíram de uma
    vez — não por defeito, mas porque `entra_configurado()` passou a ser
    verdadeiro e a entrada por e-mail desaparece nesse caso, que é a regra
    correta. Teste que muda de resultado conforme a credencial do desenvolvedor
    não afirma nada.

    `JWT_SECRET` recebe um valor forte porque parte da suíte assina sessão.
    Quem testa a guarda do segredo fraco sobrepõe com `monkeypatch.setenv`, que
    vence este padrão — é o que `test_segredo_fraco_…` já faz.
    """
    guardado = {k: os.environ.get(k) for k in _AMBIENTE_NEUTRO + ("JWT_SECRET",)}
    for chave in _AMBIENTE_NEUTRO:
        os.environ.pop(chave, None)
    os.environ["JWT_SECRET"] = "t" * 64
    yield
    for chave, valor in guardado.items():
        if valor is None:
            os.environ.pop(chave, None)
        else:
            os.environ[chave] = valor


@pytest.fixture(scope="session", autouse=True)
def estado_isolado(tmp_path_factory):
    """A suíte não escreve no `dados/estado.json` de quem está usando o sistema.

    Os testes exercitam rotas de verdade, e rota de mutação chama `gravar()`.
    Sem isolar o caminho, rodar a suíte reescrevia o estado real — foi assim
    que o usuário vinculado à conta trocou sozinho depois de um `pytest`.
    """
    main.ARQUIVO_ESTADO = tmp_path_factory.mktemp("estado") / "estado.json"
    # As credenciais do login próprio também ficam num arquivo isolado: a suíte
    # cria e apaga contas, e o `dados/usuarios.json` de quem usa o sistema não
    # pode ser tocado por isso.
    os.environ["ORG_USUARIOS_ARQUIVO"] = str(tmp_path_factory.mktemp("usuarios") / "usuarios.json")
    # O gasto da MarIA (freio de custo) também: a suíte não soma no `dados/`.
    os.environ["MARIA_USO_ARQUIVO"] = str(tmp_path_factory.mktemp("maria") / "maria-uso.json")
    yield


SENHA_TESTE = "senha-de-teste-123"


@pytest.fixture()
def conta():
    """Cria uma conta (e-mail + senha) no arquivo isolado; devolve (email, senha)."""
    from orga import usuarios

    def _criar(email: str, senha: str = SENHA_TESTE, **kw):
        usuarios.definir_senha(email, senha, **kw)
        return email, senha
    return _criar


@pytest.fixture(autouse=True)
def idioma_fonte():
    """Cada teste começa em pt-BR e devolve o que encontrou."""
    anterior = main.ESTADO.config.idioma
    main.ESTADO.config.idioma = idiomas.PADRAO
    main.alinhar_idioma()
    yield
    main.ESTADO.config.idioma = anterior
    main.alinhar_idioma()
