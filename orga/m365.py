"""GPlanSiS|Peoples — sincronização do centro de custo com o Microsoft 365.

Portado do **GPlanSiS|OS** (`eos-manager/backend/auth.py`): o desenho, não o código.
Lá o cliente do Graph vem do `msal`; aqui o fluxo de credenciais de aplicativo
cabe numa requisição `urllib`, e este projeto não instala pacote por
conveniência — `acesso.py` já troca código de autorização com o mesmo endpoint
sem biblioteca nenhuma. O que foi portado de fato é o que custou descobrir: o
filtro de usuário, o atributo que carrega o CC e a extração do prefixo
numérico.

Quatro decisões que estão no código, e não neste texto:

**Lê, nunca escreve.** O escopo pedido ao Entra é `User.Read.All`. Não existe
função aqui que faça `POST` ou `PATCH` no Graph, e um teste falha se alguém
criar uma. O organograma não corrige o diretório da empresa: quem muda dado no
MS365 é o RH, pelo processo dele.

**Não cria gente.** Conta no MS365 que não casa com ninguém do organograma vira
aviso, nunca unidade nova. O recorte que pedimos ao Graph não traz gestor, e
criar pessoa sem gestor a penduraria na raiz — o mesmo erro que a carga da
planilha recusa (RF-02/RF-03).

**Ausente no MS365 não é ausente na empresa.** O filtro pede conta habilitada e
licenciada, e prestador (PJ) legitimamente não tem licença. Quem não aparece no
Graph é relatado com o vínculo ao lado, e nunca removido.

**Menos preciso não sobrescreve mais preciso.** O MS365 guarda o CC na
granularidade que o RH digitou — às vezes `83`, às vezes `90.11`. O organograma
guarda N4 (`80.31`), que é o que liga uma pessoa à sua equipe. Quando o código
do MS365 é prefixo do que está gravado, as duas fontes concordam no que o MS365
sabe e nada muda. Quando discordam e o MS365 é o menos específico, isso é
conflito para gente resolver, não atualização para aplicar: gravar `83` por
cima de `83.11` apagaria a equipe e quebraria a resolução do cadastro de
centros de custo, que casa por N3.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from . import acesso
from . import idiomas
from .dominio import Unidade

# Idioma vigente, ajustado por `main` antes de cada uso. Mesma solução do
# importador: recusa e aviso vão para a tela e falam a língua de quem sincroniza.
IDIOMA = idiomas.PADRAO


def _t(texto: str, **p) -> str:
    return idiomas.traduzir(texto, IDIOMA, **p)


# ---------------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------------
# Consulta avançada do Graph: conta habilitada e com pelo menos uma licença.
# Sem o segundo termo entram caixas compartilhadas, salas e contas de serviço,
# que não são pessoas e sujariam o relatório inteiro.
FILTRO_USUARIOS = "accountEnabled eq true and assignedLicenses/$count ne 0"

GRAFO = "https://graph.microsoft.com/v1.0/users"

# Onde o MS365 guarda o centro de custo. O padrão é `department` porque é onde
# ele está no tenant da GPlanSiS|Peoples; `costCenter` vive dentro de `employeeOrgData`
# e exige pedir outro campo no `$select`.
ATRIBUTO_PADRAO = "department"
_ALIAS_CUSTO = ("costcenter", "cost_center", "employeeorgdata.costcenter")


def atributo_cc() -> str:
    return (acesso._env("CC_ATTRIBUTE") or ATRIBUTO_PADRAO).strip().lower()


def credenciais() -> dict:
    """Credenciais de APLICATIVO do Microsoft Entra ID, só para a sincronização
    de centro de custo. O login do sistema é próprio (e-mail + senha); estas
    variáveis existem apenas para quem tem um tenant Microsoft 365 e quer ler
    o centro de custo de lá."""
    return {"tenant": acesso._env("AZURE_TENANT_ID", "common"),
            "client_id": acesso._env("AZURE_CLIENT_ID"),
            "client_secret": acesso._env("AZURE_CLIENT_SECRET")}


def configurado() -> bool:
    c = credenciais()
    return bool(c["client_id"] and c["client_secret"])


def campos_graph() -> str:
    base = "id,displayName,mail,userPrincipalName,accountEnabled"
    if atributo_cc() in _ALIAS_CUSTO:
        return base + ",employeeOrgData"
    return base + ",department"


# ---------------------------------------------------------------------------
# LEITURA DO CENTRO DE CUSTO
# ---------------------------------------------------------------------------
def cc_bruto(usuario: dict) -> str | None:
    """O valor como o MS365 guarda, antes de qualquer normalização."""
    if atributo_cc() in _ALIAS_CUSTO:
        return (usuario.get("employeeOrgData") or {}).get("costCenter")
    return usuario.get("department")


# O código quase sempre abre o campo (`80.31 Analista de Processos`), mas o RH
# também escreve `Manutenção 95.31`. A segunda expressão recolhe esse caso, e é
# estreita de propósito: exige a forma `NN.N`/`NN.NN` isolada, senão `Suporte
# 24h` viraria centro de custo 24.
_NO_INICIO = re.compile(r"^(\d+(?:\.\d+)*)")
_NO_MEIO = re.compile(r"(?<![\d.])(\d{2}\.\d{1,2})(?![\d.])")


def extrair_cc(texto: str | None) -> str | None:
    """`"83 - OTC"` → `"83"`; `"90.11 Board"` → `"90.11"`.

    O RH escreve o nome junto do código, e esse nome varia entre as duas fontes
    — no tenant da GPlanSiS|Peoples o campo traz o **cargo**, não o departamento. Por
    isso só o número é lido: ele é o que não muda.
    """
    if not texto:
        return None
    texto = texto.strip()
    achado = _NO_INICIO.match(texto) or _NO_MEIO.search(texto)
    return achado.group(1) if achado else None


def cc_do_usuario(usuario: dict) -> str | None:
    return extrair_cc(cc_bruto(usuario))


def email_do_usuario(usuario: dict) -> str:
    """`mail` é o endereço de verdade; `userPrincipalName` é o login e nem
    sempre coincide. Quem não tem nem um nem outro não dá para parear."""
    return ((usuario.get("mail") or usuario.get("userPrincipalName") or "")
            .strip().lower())


def nivel_cc(cc: str | None) -> int:
    """Que degrau da numeração este código ocupa — 0 quando não é um código.

    O esquema é o mesmo do cadastro de centros de custo, e contar pontos não o
    descreve: `80.0` e `80.31` têm um ponto cada e são coisas diferentes.

        80      1   LogicalCC, o tronco
        80.0    2   N2, a vertical de negócio
        80.30   3   N3, o agrupador — "o N4 com o último dígito zerado"
        80.31   4   N4, a equipe

    Descobri isso no dado, não no papel: o `department` do tenant traz as duas
    formas lado a lado (`80.0 - Engineering` e `80.31 Analista de Processos`),
    e tratá-las como igualmente precisas fazia a vertical inteira aparecer
    como divergência aplicável de quem estava certo.
    """
    if not cc:
        return 0
    partes = cc.split(".")
    if not partes[0].isdigit():
        return 0
    if len(partes) == 1:
        return 1
    fracao = partes[1]
    if not fracao.isdigit():
        return 0
    if len(fracao) < 2:
        return 2
    return 3 if fracao.endswith("0") else 4


def truncar(cc: str, nivel: int) -> str:
    """O mesmo código visto de um degrau mais acima. `87.41` em N2 é `87.0`."""
    partes = cc.split(".")
    tronco = partes[0]
    if nivel <= 1 or len(partes) == 1:
        return tronco if nivel <= 1 else cc
    if nivel == 2:
        return tronco + ".0"
    if nivel == 3:
        return tronco + "." + (partes[1][0] if partes[1] else "0") + "0"
    return cc


def compativel(cc_m365: str, cc_org: str) -> bool:
    """As duas fontes concordam **no que o MS365 sabe**?

    Comparar cru marcaria como divergente todo mundo cujo MS365 guarda só a
    vertical. A pergunta certa é outra: descendo o código gravado até o degrau
    que o MS365 alcança, os dois batem? `87.0` contra `87.41` bate — o RH
    escreveu a vertical, e a vertical está certa.
    """
    nivel = nivel_cc(cc_m365)
    if not nivel or not nivel_cc(cc_org):
        return False
    return truncar(cc_org, nivel) == truncar(cc_m365, nivel)


def _menos_especifico(cc_m365: str, cc_org: str) -> bool:
    return nivel_cc(cc_m365) < nivel_cc(cc_org)


# ---------------------------------------------------------------------------
# GRAPH
# ---------------------------------------------------------------------------
def token_de_aplicativo() -> str:
    """Credenciais de aplicativo: o próprio serviço se autentica, sem usuário
    na frente. É o que permite a sincronização rodar sem alguém logado."""
    c = credenciais()
    if not (c["client_id"] and c["client_secret"]):
        raise RuntimeError(_t("Microsoft Entra ID não configurado: faltam "
                              "AZURE_CLIENT_ID e AZURE_CLIENT_SECRET."))
    corpo = urllib.parse.urlencode({
        "client_id": c["client_id"],
        "client_secret": c["client_secret"],
        "grant_type": "client_credentials",
        "scope": "https://graph.microsoft.com/.default",
    }).encode()
    pedido = urllib.request.Request(
        f"https://login.microsoftonline.com/{c['tenant']}/oauth2/v2.0/token",
        data=corpo, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(pedido, timeout=20) as r:
        dados = json.loads(r.read())
    token = dados.get("access_token")
    if not token:
        # A descrição do erro do Entra é específica ("permissão não concedida",
        # "segredo expirado") e é ela que resolve o chamado — repassar só
        # "falhou" custaria uma ida e volta com quem administra o tenant.
        raise RuntimeError(_t("o Entra ID recusou as credenciais: {erro}",
                              erro=dados.get("error_description")
                              or dados.get("error") or "sem detalhe"))
    return token


def _pegar(url: str, token: str, tempo: int = 30) -> dict:
    pedido = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        # `$count` e o filtro em `assignedLicenses` são consulta avançada: sem
        # este cabeçalho o Graph devolve 400.
        "ConsistencyLevel": "eventual",
    })
    with urllib.request.urlopen(pedido, timeout=tempo) as r:
        return json.loads(r.read())


def buscar_usuarios(limite_paginas: int = 40) -> list[dict]:
    """Pessoas habilitadas e licenciadas, seguindo a paginação do Graph.

    O teto de páginas existe para que um `@odata.nextLink` que não termina —
    por defeito do serviço ou por filtro mal formado — não deixe a tela girando
    para sempre. A 999 por página, 40 páginas cobrem quase 40 mil pessoas.
    """
    token = token_de_aplicativo()
    consulta = urllib.parse.urlencode({
        "$filter": FILTRO_USUARIOS,
        "$count": "true",
        "$select": campos_graph(),
        "$top": "999",
    })
    url = f"{GRAFO}?{consulta}"
    achados: list[dict] = []
    paginas = 0
    while url and paginas < limite_paginas:
        dados = _pegar(url, token)
        achados.extend(dados.get("value", []))
        url = dados.get("@odata.nextLink")
        paginas += 1
    return achados


def erro_legivel(exc: Exception) -> str:
    """O corpo do erro do Graph diz qual permissão falta; o código sozinho não.

    `Authorization_RequestDenied` com 403 é sempre a mesma causa — consentimento
    de administrador não concedido para `User.Read.All` — e essa é a frase que
    resolve, não "403".
    """
    if isinstance(exc, urllib.error.HTTPError):
        try:
            corpo = json.loads(exc.read())
            detalhe = (corpo.get("error") or {}).get("message") or ""
        except Exception:
            detalhe = ""
        if exc.code == 403:
            return _t("o Microsoft 365 recusou a leitura (403). Falta "
                      "consentimento de administrador para User.Read.All. {d}",
                      d=detalhe)
        return _t("o Microsoft 365 respondeu {codigo}. {d}",
                  codigo=exc.code, d=detalhe)
    return str(exc)


# ---------------------------------------------------------------------------
# ANÁLISE DIFERENCIAL
# ---------------------------------------------------------------------------
def analisar(usuarios: list[dict], unidades: dict[str, Unidade]) -> dict:
    """Compara o MS365 com a estrutura vigente. Não altera nada.

    Pura de propósito: recebe a lista já buscada em vez de buscar sozinha, e é
    por isso que os testes cobrem os degraus sem tocar a rede nem o tenant.
    """
    from .importador import chave

    por_chave = {chave(u.nome, u.email): u for u in unidades.values()}

    divergentes: list[dict] = []
    a_preencher: list[dict] = []
    conflitos: list[dict] = []
    compativeis: list[dict] = []
    sem_cc_no_m365: list[dict] = []
    sem_par: list[dict] = []
    vistos: set[str] = set()

    for usuario in usuarios:
        email = email_do_usuario(usuario)
        if not email:
            continue
        unidade = por_chave.get(email)
        if unidade is None:
            sem_par.append({"nome": usuario.get("displayName") or email,
                            "email": email, "cc": cc_do_usuario(usuario)})
            continue
        vistos.add(unidade.id)

        cc_m365 = cc_do_usuario(usuario)
        item = {"id": unidade.id, "codigo": unidade.codigo, "nome": unidade.nome,
                "email": email, "area": unidade.area,
                "cc_org": unidade.centro_custo, "cc_m365": cc_m365,
                "bruto": (cc_bruto(usuario) or "").strip()}

        if not cc_m365:
            sem_cc_no_m365.append(item)
        elif not unidade.centro_custo:
            a_preencher.append(item)
        elif compativel(cc_m365, unidade.centro_custo):
            compativeis.append(item)
        elif _menos_especifico(cc_m365, unidade.centro_custo):
            conflitos.append(item)
        else:
            divergentes.append(item)

    # A raiz fica de fora: ela e um no sintetico, nao uma pessoa. Nasce sem
    # e-mail (`montar_unidades`), entao nenhuma conta do Graph pode casar com
    # ela, e o aviso saia permanentemente errado por um contra um card que nao
    # e gente. `importador.analisar` ja excluia a raiz da lista de ausentes pelo
    # mesmo motivo; aqui faltava.
    fora = [{"id": u.id, "codigo": u.codigo, "nome": u.nome, "email": u.email,
             "cc_org": u.centro_custo, "vinculo": u.vinculo}
            for u in unidades.values()
            if u.id not in vistos and u.parent_id is not None]

    avisos: list[str] = []
    if conflitos:
        avisos.append(_t("{n} pessoa(s) têm no MS365 um centro de custo menos "
                         "específico e diferente do que está gravado. Não são "
                         "aplicáveis: gravar o código curto apagaria a equipe.",
                         n=len(conflitos)))
    if sem_par:
        avisos.append(_t("{n} conta(s) do MS365 não casam com ninguém do "
                         "organograma. Pessoa nova entra pela planilha, não por "
                         "aqui: o MS365 não diz a quem ela responde.",
                         n=len(sem_par)))
    nao_clt = sum(1 for f in fora if f["vinculo"] != "clt")
    if fora:
        avisos.append(_t("{n} pessoa(s) do organograma não têm conta habilitada "
                         "e licenciada no MS365 — {p} delas não são CLT, o que "
                         "explica a ausência. Ninguém é removido por isso.",
                         n=len(fora), p=nao_clt))

    return {"divergentes": divergentes, "a_preencher": a_preencher,
            "conflitos": conflitos, "compativeis": compativeis,
            "sem_cc_no_m365": sem_cc_no_m365, "fora_do_m365": fora,
            "sem_par": sem_par, "avisos": avisos,
            "atributo": atributo_cc(), "total_m365": len(usuarios)}


def aplicar(analise: dict, unidades: dict[str, Unidade],
            atualizar: bool, preencher: bool) -> dict:
    """Grava só as classes marcadas, e só o centro de custo.

    Conflito nunca entra, mesmo com `atualizar` ligado — ele não é uma escolha
    de tela, é uma contradição entre as duas fontes que precisa ser resolvida
    numa delas.
    """
    alterados: list[str] = []

    def _grava(itens: list[dict]) -> None:
        for item in itens:
            unidade = unidades.get(item["id"])
            if unidade is None or not item["cc_m365"]:
                continue
            if unidade.centro_custo == item["cc_m365"]:
                continue
            unidade.centro_custo = item["cc_m365"]
            alterados.append(unidade.id)

    if atualizar:
        _grava(analise.get("divergentes", []))
    if preencher:
        _grava(analise.get("a_preencher", []))

    return {"alterados": len(alterados), "ids": alterados,
            "atributo": analise.get("atributo", ATRIBUTO_PADRAO),
            "total_m365": analise.get("total_m365", 0)}
