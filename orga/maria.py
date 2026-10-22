"""MarIA — assistente de IA sobre o organograma.

Portada do GPlanSIS|Planner, onde ela analisa projetos. Aqui o objeto é a
estrutura: quem responde a quem, onde está cada centro de custo, o que a
apresentação institucional promete e o que o cadastro entrega.

O que define este módulo não é o que a MarIA sabe fazer — é o que ela **não
pode** fazer sem alguém autorizar. As sete capacidades entram como guarda de
verdade, não como tabela de documentação:

    1 LER              consulta            nenhum efeito   RBAC de quem pergunta
    2 DESCREVER        explica estado      nenhum efeito   idem
    3 RELATAR          gera PDF            artefato        idem + marca de origem
    4 ANALISAR         plano × real        nenhum efeito   idem + gate de qualidade
    5 PLANEJAR         propõe cenário      RASCUNHO        idem + versão do plano
    6 EXECUTAR         dispara ação        MUTAÇÃO         aprovação humana por ação
    7 AGIR SOZINHA     encadeia ações      MUTAÇÃO         fora de escopo desta onda

A 6 existe desde o agente Organograma, e existe **com** a sua autoridade: a
MarIA devolve a proposta, uma pessoa lê a lista inteira e aprova, e só então o
sistema cria. A 7 continua recusada — encadear ações sem parada humana entre
elas é outra coisa, e não é esta.

Três decisões que sustentam isso no código, e não no texto:

**A MarIA nunca vê mais que quem pergunta.** O contexto é montado a partir do
perfil e do escopo de edição de quem está logado. Um editor com escopo numa
subárvore recebe um recorte; a MarIA responde sobre esse recorte e mais nada.
Passar a base inteira ao modelo e pedir discrição no prompt não é controle de
acesso — é torcida.

**Rascunho não vira mutação por engano.** PLANEJAR devolve proposta e nada
mais. Aplicar é um POST separado que recebe o identificador da proposta já
revisada — o modelo não é chamado de novo na aprovação, senão a pessoa estaria
aprovando um texto e o sistema criando outro.

**Capacidade 7 é recusada aqui, não desencorajada no prompt.** `permitida()`
devolve False e a rota nem chama o modelo.

Sem `ANTHROPIC_API_KEY` o módulo abre, explica o que faria e diz que falta a
chave. Tela que some quando não configurada esconde o que existe.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

API = "https://api.anthropic.com/v1/messages"
VERSAO_API = "2023-06-01"
MODELO_PADRAO = "claude-haiku-4-5"

LER, DESCREVER, RELATAR, ANALISAR, PLANEJAR, EXECUTAR, AUTONOMA = (
    "ler", "descrever", "relatar", "analisar", "planejar", "executar", "autonoma")

# (chave, rótulo, verbo, efeito, autoridade exigida, disponível nesta onda)
CAPACIDADES = (
    (LER, "Ler", "consulta", "nenhum",
     "RBAC de leitura de quem pergunta", True),
    (DESCREVER, "Descrever", "explica estado", "nenhum",
     "RBAC de leitura de quem pergunta", True),
    (RELATAR, "Relatar", "gera PDF", "artefato",
     "RBAC + marca d'água de origem", True),
    (ANALISAR, "Analisar baseline", "compara declarado × cadastrado", "nenhum",
     "RBAC + gate de qualidade de dado", True),
    (PLANEJAR, "Planejar", "propõe cenário", "rascunho, nunca aplicado",
     "RBAC + versão do plano", True),
    # Passa a existir nesta onda porque o agente Organograma precisa dela — e
    # existe COM a autoridade que a tabela sempre exigiu: a MarIA propõe, uma
    # pessoa lê a proposta inteira e aprova. Não há caminho que crie unidade
    # sem esse POST separado, disparado por gente.
    (EXECUTAR, "Executar", "dispara ação de sistema", "mutação",
     "aprovação humana explícita, por ação", True),
    (AUTONOMA, "Agir sozinha", "encadeia ações", "mutação",
     "fora de escopo desta onda", False),
)

SEM_EFEITO = {LER, DESCREVER, ANALISAR}
DISPONIVEIS = {c[0] for c in CAPACIDADES if c[5]}

# O que a gaveta oferece: as capacidades disponiveis que NAO mutam. `Executar`
# fica de fora porque exige aprovacao humana explicita por acao — um POST
# proprio, com a proposta inteira na frente de quem aprova; oferece-la num campo
# de texto contradiria o rodape que promete "somente leitura". `Agir sozinha`
# esta fora de escopo desta onda e nem passa pela guarda.
DE_CONVERSA = tuple((c[0], c[1], c[2]) for c in CAPACIDADES
                    if c[5] and c[3] != "mutação")

# USD por milhão de tokens. Mesma tabela do Planner — o custo é o mesmo modelo.
PRECOS = {
    "claude-opus-5": {"in": 15, "out": 75},
    "claude-opus-4-8": {"in": 15, "out": 75},
    "claude-opus-4-1": {"in": 15, "out": 75},
    "claude-sonnet-5": {"in": 3, "out": 15},
    "claude-sonnet-4-5": {"in": 3, "out": 15},
    "claude-haiku-4-5": {"in": 1, "out": 5},
    "default": {"in": 15, "out": 75},
}
USD_BRL = 5.4


def _env(nome: str, padrao: str = "") -> str:
    return (os.environ.get(nome) or padrao).strip()


def chave() -> str:
    return _env("ANTHROPIC_API_KEY")


def configurada() -> bool:
    return bool(chave())


def modelo_padrao() -> str:
    return _env("MARIA_MODEL", MODELO_PADRAO)


def modelos() -> list[str]:
    return [m for m in PRECOS if m != "default"]


def preco(modelo: str) -> dict:
    if modelo in PRECOS:
        return PRECOS[modelo]
    prefixo = next((p for p in PRECOS
                    if p != "default" and modelo.startswith(p)), None)
    return PRECOS.get(prefixo or "default", PRECOS["default"])


def custo(modelo: str, entrada: int, saida: int) -> float:
    p = preco(modelo)
    return (entrada / 1e6) * p["in"] + (saida / 1e6) * p["out"]


def permitida(capacidade: str) -> bool:
    """Guarda de verdade: 6 e 7 não passam daqui nesta onda."""
    return capacidade in DISPONIVEIS


def muta(capacidade: str) -> bool:
    return capacidade not in SEM_EFEITO and capacidade != RELATAR


# ---------------------------------------------------------------------------
# Contexto — o recorte que a MarIA enxerga
# ---------------------------------------------------------------------------
def agregados(us, cfg, mapa: dict) -> dict:
    """Contagens por vertical, departamento e nível.

    Mandar 220 fichas completas custava 27 mil tokens de entrada por pergunta —
    US$ 0,40 no opus, a cada pergunta. A maioria das perguntas é sobre
    distribuição, e distribuição se responde com contagem. As fichas continuam
    indo, só que em amostra.
    """
    def conta(chave):
        saida: dict[str, int] = {}
        for u in us:
            valor = chave(u) or "—"
            saida[valor] = saida.get(valor, 0) + 1
        return dict(sorted(saida.items(), key=lambda kv: -kv[1]))

    return {
        "por_vertical": conta(lambda u: (mapa.get(u.id) or {}).get(
            "vertical_negocio") or u.vertical),
        "por_departamento": conta(lambda u: u.area),
        "por_nivel": conta(lambda u: cfg.rotulos_nivel.get(u.tipo, u.tipo)),
        "por_vinculo": conta(lambda u: getattr(u, "vinculo", "")),
    }


def contexto(unidades, mapa: dict, cfg, escopo_ids: set | None = None,
             limite: int = 60) -> dict:
    """Snapshot do organograma limitado ao que quem pergunta pode ver.

    `escopo_ids` vem da guarda de escopo do editor (SEC-03). Sem ele, a leitura
    é total — que é o caso do administrador. Truncar em `limite` não é economia
    de token: é o teto que evita mandar 267 registros quando a pergunta é sobre
    uma equipe.
    """
    us = list(unidades.values()) if isinstance(unidades, dict) else list(unidades)
    if escopo_ids is not None:
        us = [u for u in us if u.id in escopo_ids]
    pessoas = [{
        "codigo": u.codigo, "nome": u.nome, "cargo": u.cargo,
        "departamento": u.area, "nivel": cfg.rotulos_nivel.get(u.tipo, u.tipo),
        "centro_custo": u.centro_custo,
        "vertical": (mapa.get(u.id) or {}).get("vertical_negocio", u.vertical),
        "responde_a": next((x.nome for x in us if x.id == u.parent_id), None),
    } for u in us[:limite]]
    return {
        "organograma": cfg.titulo,
        "organizacao": cfg.tenant,
        "total_no_recorte": len(us),
        # Os agregados cobrem o recorte INTEIRO; a amostra é que é truncada.
        # Sem essa distinção a MarIA diria "não sei" sobre uma contagem que
        # ela tem — ou pior, contaria a amostra achando que era o todo.
        "contagens_do_recorte_inteiro": agregados(us, cfg, mapa),
        "amostra_truncada_em": limite if len(us) > limite else None,
        "pessoas_amostra": pessoas,
    }


SISTEMA = """Você é a MarIA, assistente de estrutura organizacional da GPlanSiS|Peoples,
dentro do sistema GPlanSiS|Peoples.

O objeto da sua análise é o organograma: hierarquia, centros de custo, cargos,
níveis e a diferença entre a estrutura declarada na apresentação institucional e
a cadastrada no sistema.

Regras:
- Responda no idioma pedido, de forma objetiva e acionável.
- Baseie-se SOMENTE nos dados fornecidos no contexto. O contexto já vem
  recortado pelo que a pessoa que pergunta tem permissão de ver — se algo não
  está ali, diga que não está no seu recorte, não suponha.
- `contagens_do_recorte_inteiro` vale para TODAS as pessoas do recorte: use-a
  para qualquer pergunta de distribuição, contagem ou ranking. Já
  `pessoas_amostra` é uma amostra e pode estar truncada — não conte nela nem
  tire conclusão de cobertura a partir dela.
- Quando faltar dado, aponte a lacuna e o risco dela, e recomende a correção.
- Você NÃO executa mudanças. Se pedirem para alterar a estrutura, explique o que
  faria e diga que a aplicação depende de aprovação humana explícita.
- Estruture respostas longas em: Diagnóstico, Riscos, Recomendações priorizadas.
"""


def prompt(capacidade: str, pergunta: str, ctx: dict, idioma: str) -> str:
    nomes = {"pt-BR": "português do Brasil", "en-US": "inglês americano",
             "es": "espanhol"}
    linhas = [f"Idioma da resposta: {nomes.get(idioma, 'português do Brasil')}.",
              f"Capacidade solicitada: {capacidade}."]
    if capacidade == PLANEJAR:
        linhas.append("Isto é um RASCUNHO. Deixe explícito que nada será "
                      "aplicado sem aprovação humana.")
    if capacidade == ANALISAR:
        linhas.append("Compare o que o contexto mostra com o que seria "
                      "esperado, e aponte divergências com evidência.")
    linhas += ["", "Contexto (JSON):", json.dumps(ctx, ensure_ascii=False),
               "", "Pergunta:", pergunta.strip()]
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Chamada
# ---------------------------------------------------------------------------
def perguntar(texto: str, ctx: dict, idioma: str = "pt-BR",
              capacidade: str = DESCREVER, modelo: str = "",
              max_tokens: int = 1600, tempo: int = 60) -> dict:
    """Uma chamada ao modelo. Nunca levanta: devolve `ok` e o motivo.

    Sem SDK: a API é um POST de JSON, e uma dependência a mais só para montar
    esse POST não se paga num projeto que não tem etapa de build.
    """
    if not permitida(capacidade):
        return {"ok": False, "motivo": "capacidade_indisponivel",
                "mensagem": "Capacidade fora de escopo desta onda."}
    if not configurada():
        return {"ok": False, "motivo": "sem_chave",
                "mensagem": "Configure ANTHROPIC_API_KEY para habilitar a MarIA."}
    if not (texto or "").strip():
        return {"ok": False, "motivo": "vazio", "mensagem": "Escreva a pergunta."}

    modelo = modelo or modelo_padrao()
    corpo = json.dumps({
        "model": modelo,
        "max_tokens": max_tokens,
        "system": SISTEMA,
        "messages": [{"role": "user",
                      "content": prompt(capacidade, texto, ctx, idioma)}],
    }).encode()
    pedido = urllib.request.Request(API, data=corpo, headers={
        "content-type": "application/json",
        "x-api-key": chave(),
        "anthropic-version": VERSAO_API,
    })
    try:
        with urllib.request.urlopen(pedido, timeout=tempo) as r:
            resposta = json.loads(r.read())
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", "replace")[:300]
        return {"ok": False, "motivo": "http", "mensagem": f"{erro.code}: {detalhe}"}
    except Exception as erro:                        # noqa: BLE001
        return {"ok": False, "motivo": "rede", "mensagem": str(erro)[:200]}

    partes = [b.get("text", "") for b in resposta.get("content", [])
              if b.get("type") == "text"]
    uso = resposta.get("usage") or {}
    entrada = int(uso.get("input_tokens", 0))
    saida = int(uso.get("output_tokens", 0))
    return {
        "ok": True,
        "texto": "\n".join(partes).strip(),
        "modelo": resposta.get("model", modelo),
        "entrada": entrada,
        "saida": saida,
        "custo_usd": round(custo(modelo, entrada, saida), 6),
    }


# ---------------------------------------------------------------------------
# Histórico de assistências
# ---------------------------------------------------------------------------
def assistencia(pergunta: str, r: dict, quem: dict | None, capacidade: str,
                idioma: str, escopo: str = "") -> dict:
    """Um registro do histórico. Guarda o que foi perguntado, o que foi
    respondido, quanto custou e **em que recorte** — sem isso não dá para
    auditar depois se a resposta era compatível com o que a pessoa podia ver."""
    return {
        "id": uuid.uuid4().hex[:12],
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quem": (quem or {}).get("nome", ""),
        "quem_id": (quem or {}).get("id", ""),
        "capacidade": capacidade,
        "idioma": idioma,
        "escopo": escopo,
        "pergunta": (pergunta or "").strip()[:2000],
        "resposta": (r.get("texto") or r.get("mensagem") or "")[:12000],
        "ok": bool(r.get("ok")),
        "modelo": r.get("modelo", ""),
        "entrada": r.get("entrada", 0),
        "saida": r.get("saida", 0),
        "custo_usd": r.get("custo_usd", 0.0),
    }


def resumo(historico: list[dict]) -> dict:
    ok = [a for a in historico or [] if a.get("ok")]
    entrada = sum(a.get("entrada", 0) for a in ok)
    saida = sum(a.get("saida", 0) for a in ok)
    usd = sum(a.get("custo_usd", 0.0) for a in ok)
    return {
        "total": len(historico or []),
        "com_resposta": len(ok),
        "entrada": entrada,
        "saida": saida,
        "usd": round(usd, 4),
        "brl": round(usd * USD_BRL, 2),
        "por_capacidade": {c: sum(1 for a in ok if a.get("capacidade") == c)
                           for c, *_ in CAPACIDADES},
    }


# ---------------------------------------------------------------------------
# Agente Organograma — estrutura inteira a partir de uma frase
# ---------------------------------------------------------------------------
# "Crie um time de Growth Marketing com 1 Diretor, 2 Coordenadores e 4
# Analistas focado na América Latina" precisa virar unidades de verdade. O
# caminho é o mesmo das sete capacidades, e não um atalho ao lado delas:
#
#   PLANEJAR  a MarIA devolve a proposta em JSON e nada acontece
#   EXECUTAR  uma pessoa lê a proposta, confere e aprova — aí o sistema cria
#
# A diferença importa porque é onde mora o erro caro. Aplicar direto o que o
# modelo devolveu criaria dezenas de unidades a partir de uma frase ambígua,
# e desfazer isso num organograma de 267 pessoas é pior do que não ter feito.
SISTEMA_AGENTE = """Você é a MarIA, agente de estrutura organizacional da GPlanSiS|Peoples.

Recebe um pedido em linguagem natural e devolve a estrutura correspondente em
JSON — apenas o JSON, sem texto antes ou depois, sem cercas de código.

Formato exato:
{
  "time": "nome do time ou área",
  "departamento": "nome do departamento a gravar no campo Departamento",
  "sob": "nome exato de uma pessoa do contexto sob quem o time deve ficar, ou null",
  "observacoes": "o que você assumiu e o que ficou ambíguo",
  "unidades": [
    {"cargo": "Diretor de Growth Marketing", "nivel": "diretoria", "quantidade": 1}
  ]
}

Regras:
- `nivel` só pode ser um destes: {niveis}.
- `quantidade` é inteiro entre 1 e 30.
- Ordene `unidades` do nível mais sênior para o mais júnior.
- O cargo deve ser específico e utilizável: "Analista de Growth Marketing",
  não "Analista".
- Se o pedido não disser sob quem o time fica, use null e diga isso em
  `observacoes`. Não invente um gestor que não está no contexto.
- Se o pedido for ambíguo ou não for sobre criar estrutura, devolva
  `"unidades": []` e explique em `observacoes`.
"""


def extrair_json(texto: str):
    """Primeiro objeto JSON de um texto, tolerante a cerca e a ruído.

    O modelo é instruído a devolver só o JSON, mas instrução não é garantia —
    e falhar a leitura por causa de uma linha de cortesia seria frágil.
    """
    import re

    s = str(texto or "")
    cercado = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    bruto = cercado.group(1) if cercado else None
    if bruto is None:
        achado = re.search(r"\{.*\}", s, re.S)
        bruto = achado.group(0) if achado else None
    if not bruto:
        return None
    try:
        return json.loads(bruto)
    except ValueError:
        return None


def validar_proposta(dados, niveis: set, nomes: set) -> tuple[dict | None, list]:
    """(proposta saneada, problemas).

    O que o modelo devolve é entrada não confiável como qualquer outra. Nível
    inexistente, quantidade absurda e gestor inventado são recusados aqui —
    antes de virarem unidade.
    """
    problemas = []
    if not isinstance(dados, dict):
        return None, ["resposta não é um objeto JSON"]

    unidades = []
    for item in (dados.get("unidades") or [])[:40]:
        if not isinstance(item, dict):
            continue
        cargo = str(item.get("cargo", "")).strip()[:80]
        nivel = str(item.get("nivel", "")).strip()
        try:
            quantidade = int(item.get("quantidade", 1))
        except (TypeError, ValueError):
            quantidade = 0
        if not cargo:
            problemas.append("unidade sem cargo, descartada")
            continue
        if nivel not in niveis:
            problemas.append(f"nível desconhecido em “{cargo}”: {nivel or '—'}")
            continue
        if not 1 <= quantidade <= 30:
            problemas.append(f"quantidade fora de 1–30 em “{cargo}”: {quantidade}")
            continue
        unidades.append({"cargo": cargo, "nivel": nivel, "quantidade": quantidade})

    sob = str(dados.get("sob") or "").strip()
    if sob and sob not in nomes:
        problemas.append(f"gestor “{sob}” não está no seu recorte; a raiz será usada")
        sob = ""

    proposta = {
        "time": str(dados.get("time", "")).strip()[:80],
        "departamento": str(dados.get("departamento", "")).strip()[:60],
        "sob": sob,
        "observacoes": str(dados.get("observacoes", "")).strip()[:600],
        "unidades": unidades,
        "total": sum(u["quantidade"] for u in unidades),
    }
    return proposta, problemas


def propor_estrutura(pedido: str, ctx: dict, niveis: set, nomes: set,
                     idioma: str = "pt-BR", modelo: str = "") -> dict:
    """Capacidade 5 (PLANEJAR): devolve a proposta. Nada é criado aqui."""
    if not configurada():
        return {"ok": False, "motivo": "sem_chave",
                "mensagem": "Configure ANTHROPIC_API_KEY para habilitar a MarIA."}
    sistema = SISTEMA_AGENTE.replace("{niveis}", ", ".join(sorted(niveis)))
    r = perguntar(pedido, ctx, idioma=idioma, capacidade=PLANEJAR,
                  modelo=modelo, max_tokens=2000)
    if not r.get("ok"):
        return r
    proposta, problemas = validar_proposta(extrair_json(r["texto"]), niveis, nomes)
    if proposta is None or not proposta["unidades"]:
        return {**r, "ok": False, "motivo": "sem_proposta",
                "mensagem": (proposta or {}).get("observacoes")
                or "A MarIA não devolveu uma estrutura utilizável.",
                "problemas": problemas}
    return {**r, "proposta": proposta, "problemas": problemas, "sistema": sistema}


# ---------------------------------------------------------------------------
# Markdown -> HTML seguro, para a tela
# ---------------------------------------------------------------------------
# A resposta do modelo é conteúdo de terceiro. Escapar primeiro e formatar
# depois é a ordem que importa: formatar primeiro deixaria `<script>` vindo do
# texto virar script de verdade. Nenhuma tag do original sobrevive.
def formatar(texto: str) -> str:
    """Subconjunto de Markdown em HTML, com tudo escapado antes."""
    import html
    import re as _re

    s = html.escape(str(texto or ""), quote=False)
    linhas, saida, i = s.replace("\r\n", "\n").split("\n"), [], 0
    lista_aberta = False

    def fecha_lista():
        nonlocal lista_aberta
        if lista_aberta:
            saida.append("</ul>")
            lista_aberta = False

    def inline(t: str) -> str:
        t = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = _re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        return t

    while i < len(linhas):
        linha = linhas[i].rstrip()
        if not linha.strip():
            fecha_lista(); i += 1; continue

        titulo = _re.match(r"^(#{1,4})\s+(.*)$", linha)
        if titulo:
            fecha_lista()
            n = min(len(titulo.group(1)) + 2, 6)
            saida.append(f"<h{n}>{inline(titulo.group(2).strip())}</h{n}>")
            i += 1
            continue

        if "|" in linha and i + 1 < len(linhas) and _re.match(
                r"^\s*\|?[\s:|-]+\|[\s:|-]*$", linhas[i + 1]):
            fecha_lista()
            cabeca = [c.strip() for c in linha.strip().strip("|").split("|")]
            i += 2
            corpo = []
            while i < len(linhas) and "|" in linhas[i]:
                corpo.append([c.strip()
                              for c in linhas[i].strip().strip("|").split("|")])
                i += 1
            saida.append("<table><thead><tr>"
                         + "".join(f"<th>{inline(c)}</th>" for c in cabeca)
                         + "</tr></thead><tbody>"
                         + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>"
                                                    for c in l) + "</tr>"
                                   for l in corpo)
                         + "</tbody></table>")
            continue

        item = _re.match(r"^\s*(?:[-*•]|\d+\.)\s+(.*)$", linha)
        if item:
            if not lista_aberta:
                saida.append("<ul>")
                lista_aberta = True
            saida.append(f"<li>{inline(item.group(1).strip())}</li>")
            i += 1
            continue

        fecha_lista()
        corpo = [linha.strip()]
        i += 1
        while i < len(linhas) and linhas[i].strip() and not _re.match(
                r"^\s*(#{1,4}\s|[-*•]\s|\d+\.\s)", linhas[i]) \
                and "|" not in linhas[i]:
            corpo.append(linhas[i].strip())
            i += 1
        saida.append(f"<p>{inline(' '.join(corpo))}</p>")
    fecha_lista()
    return "\n".join(saida)
