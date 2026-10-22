"""Carrega o `.env` para dentro do processo.

Faltava isto. O sistema lê credencial de `os.environ` e o README manda copiar
`.env.exemplo` para `.env` — mas ninguém lia o arquivo, então a chave ficava no
disco sem efeito nenhum. O sintoma foi pior que a causa: como não havia
carregador, a chave acabou preenchida no próprio `.env.exemplo`, que é
versionado, e foi parar no repositório.

Duas decisões:

**O ambiente vence o arquivo.** Variável já exportada no shell, no systemd ou no
contêiner não é sobrescrita por `.env`. Em produção a credencial vem do
orquestrador, e um arquivo esquecido no disco não pode derrubar isso.

**Sem dependência.** `python-dotenv` resolveria em uma linha, mas o projeto não
tem etapa de build nem instala pacote para conveniência — e o formato que este
sistema usa cabe em vinte linhas de leitura honesta.
"""
from __future__ import annotations

import os
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / ".env"


def ler(caminho: Path = ARQUIVO) -> dict[str, str]:
    """Pares do arquivo. Formato deliberadamente pequeno: `CHAVE=valor`,
    comentário com `#`, aspas opcionais em volta do valor."""
    if not caminho.exists():
        return {}
    pares: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        crua = linha.strip()
        if not crua or crua.startswith("#") or "=" not in crua:
            continue
        chave, valor = crua.split("=", 1)
        chave, valor = chave.strip(), valor.strip()
        if not chave:
            continue
        # `export CHAVE=valor` é como muita gente escreve por hábito de shell.
        if chave.startswith("export "):
            chave = chave[7:].strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        pares[chave] = valor
    return pares


def carregar(caminho: Path = ARQUIVO) -> list[str]:
    """Põe no ambiente o que ainda não estiver lá. Devolve os nomes aplicados."""
    aplicados = []
    for chave, valor in ler(caminho).items():
        if os.environ.get(chave):        # o ambiente real vence o arquivo
            continue
        os.environ[chave] = valor
        aplicados.append(chave)
    return aplicados
