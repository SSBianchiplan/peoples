"""
GPlanSiS|Peoples - carga a partir de Organograma.xlsx.

A planilha e person-centric: cada linha e um colaborador e a hierarquia vem
da coluna "Gestor Direto". Quatro diretores apontam para "Board", que nao e
uma linha da planilha; como a SPEC exige raiz unica (RF-03), o Board e
materializado como no sintetico. Isso esta registrado no ledger da carga.

Uso:
    python importador.py                 # grava dados/estado.json
    python importador.py --spec          # grava o seed de referencia da SPEC 13
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import NamedTuple

from . import centros
from . import dominio
from . import idiomas
from .dominio import Unidade, mapa_filhos, raiz, sem_acento


# O importador é chamado tanto pela tela quanto pela linha de comando. Em vez
# de arrastar `idioma` por seis assinaturas, o módulo guarda o idioma vigente e
# `main` o ajusta antes de carregar. Fora da tela vale o padrão.
IDIOMA = idiomas.PADRAO


def _t(texto: str, **p) -> str:
    """Recusa e aviso do importador vão para a tela: falam a língua de quem
    está carregando a planilha."""
    return idiomas.traduzir(texto, IDIOMA, **p)


RAIZ = Path(__file__).resolve().parent.parent
PLANILHA = RAIZ / "planilhas" / "Organograma.xlsx"
ARQUIVO_ESTADO = RAIZ / "dados" / "estado.json"

# --------------------------------------------------------------------------
# O CONTRATO DA PLANILHA
#
# `COLUNAS` é a fonte única: dela saem a ordem do modelo, a leitura, o que a
# carga compara, e o que a exportação escreve na aba ORG. Antes eram quatro
# listas paralelas — um `COL` posicional, os títulos, os campos comparáveis e
# o `append` literal do exportador. Quatro lugares para lembrar de mexer, e o
# que divergisse só apareceria numa carga de produção.
#
# A leitura é por TÍTULO, não por posição. A regra antiga casava o cabeçalho
# por nome mas lia por índice fixo: uma planilha com as colunas certas fora de
# ordem passava na validação e era lida trocada — cargo no lugar do
# departamento, em silêncio. Por título, coluna a mais é ignorada, coluna a
# menos é pulada, e ordem trocada não importa.
# --------------------------------------------------------------------------
class Coluna(NamedTuple):
    titulo: str          # o texto no cabeçalho. NUNCA traduzido: é contrato.
    campo: str           # o atributo de Unidade (ou "gestor", que vira parent)
    obrigatoria: bool    # sem ela a planilha é recusada
    atualiza: bool       # entra na comparação da carga incremental
    ler: object          # célula -> valor do campo
    escrever: object     # (unidade, contexto) -> célula, na exportação
    # Títulos que a leitura também aceita para esta coluna. Existe porque o
    # cabeçalho do RH muda de nome sem mudar de assunto — "ID SAP" hoje era
    # "Código" ontem —, e um arquivo exportado mês passado tem de continuar
    # entrando. O título canônico é o que sai na exportação e no modelo.
    alias: tuple = ()


def _texto(n: int):
    return lambda v: str(v or "").strip()[:n]


def _e_mail(v) -> str:
    return str(v or "").strip().lower()[:120]


def _lista(sep: str, limite: int):
    """Célula com vários itens -> lista. A mesma convenção do painel."""
    return lambda v: [x.strip()[:limite]
                      for x in str(v or "").split(sep) if x.strip()]


def _data(v) -> str:
    """Célula -> data ISO. O Excel entrega `datetime`; o CSV, texto.

    Devolve `""` para o que não é data, em vez de adivinhar: uma admissão
    errada não erra sozinha, ela erra o tempo de casa, a faixa e o indicador.
    """
    if hasattr(v, "date"):                       # datetime do openpyxl
        return v.date().isoformat()
    if hasattr(v, "isoformat"):                  # date
        return v.isoformat()
    texto = str(v or "").strip()
    if not texto:
        return ""
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto[:10], formato).date().isoformat()
        except ValueError:
            continue
    return ""


def _sap(v) -> str:
    """ID SAP -> texto. O Excel devolve `51` como int, e `str(51.0)` daria
    "51.0" — um código que não casaria com nada na carga seguinte."""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v if v is not None else "").strip()[:12]


# Ordem pensada para quem abre a planilha: a identidade primeiro, depois quem
# a pessoa é, depois onde ela está, depois o que ela responde, e por último o
# gestor — que aponta para OUTRA linha e por isso fecha o registro.
#
# As oito colunas originais mantêm entre si a ordem que sempre tiveram; as
# novas foram inseridas entre elas. Quem comparar um arquivo antigo com um
# novo vê inserções, não um embaralhamento.
COLUNAS = [
    # A identidade primeiro. `ID SAP` é o número de matrícula que o RH usa e o
    # sistema passa a adotar como código: `ORG-####` era invenção nossa, boa
    # para numerar e ruim para conversar com o RH, que fala em SAP.
    # `atualiza=True`: o código deixou de ser invenção nossa e passou a ser dado
    # do RH, então ele CHEGA pela planilha como qualquer outro campo. Pareando
    # por código, ele já é igual e não aparece no diff; pareando por e-mail ou
    # nome, o diff mostra `ORG-0067 → 51` e aplicar adota a matrícula de
    # verdade — que é exatamente a migração que esta carga faz.
    Coluna("ID SAP", "codigo", False, True, _sap,
           lambda u, c: u.codigo, alias=("Código", "Codigo", "Matrícula")),
    Coluna("Colaborador", "nome", True, True, _texto(80),
           lambda u, c: u.nome),
    Coluna("Cargo/Função", "cargo", False, True, _texto(80),
           lambda u, c: u.cargo),
    Coluna("Nível", "tipo", False, True, _texto(24),
           lambda u, c: c["rotulos"].get(u.tipo, u.tipo)),
    # `corrigir_departamento` conserta a grafia mas não corta: sem o teto, esta
    # era a única coluna de texto por onde um parágrafo colado entrava inteiro.
    Coluna("Departamento", "area", False, True,
           lambda v: centros.corrigir_departamento(v)[:60],
           lambda u, c: u.area),
    Coluna("E-mail", "email", False, True, _e_mail,
           lambda u, c: u.email),
    Coluna("N2", "vertical", False, True, _texto(12),
           lambda u, c: u.vertical),
    # N3 é derivado de N4 (`centros.n3_de`): sai na exportação porque orienta
    # quem lê, e é descartado na leitura porque gravá-lo criaria uma segunda
    # verdade sobre o mesmo centro de custo.
    Coluna("N3", "", False, False, None,
           lambda u, c: centros.n3_de(u.centro_custo)),
    Coluna("N4", "centro_custo", False, True, _texto(12),
           lambda u, c: u.centro_custo),
    # N5 vem do CADASTRO de centros de custo, não da pessoa — e a planilha do
    # RH concorda com ele em 261 das 271 linhas. As dez exceções são sete
    # combinações (N3, Departamento) que o cadastro ainda não tem e três em que
    # o RH está mais atualizado; as duas coisas viram aviso no passo 2, para
    # alguém consertar o cadastro. Gravar N5 na pessoa faria dela uma segunda
    # verdade sobre a mesma pergunta, e as duas divergiriam no primeiro ajuste.
    Coluna("N5", "n5", False, False, _texto(12),
           lambda u, c: c["cc"].get(u.id, {}).get("n5", "")),
    Coluna("Regime", "vinculo", False, True, _texto(24),
           lambda u, c: dominio.VINCULOS.get(u.vinculo, (u.vinculo,))[0],
           alias=("Vínculo", "Vinculo")),
    Coluna("Data Início", "data_inicio", False, True, _data,
           lambda u, c: u.data_inicio, alias=("Data Inicio", "Admissão")),
    # Derivada da data de início, e por isso só de saída. O RH manda a coluna
    # e ela confere com a conta; guardá-la seria guardar um número que nasce
    # velho — amanhã o arquivo diz 13,24 e a verdade é 13,25.
    Coluna("Tempo de Empresa", "", False, False, None,
           lambda u, c: (lambda a: round(a, 2) if a is not None else "")(
               dominio.tempo_de_casa(u.data_inicio, c.get("hoje")))),
    Coluna("Status", "status", False, True, _texto(24),
           lambda u, c: u.status),
    Coluna("Responsável", "responsavel", False, True, _texto(60),
           lambda u, c: u.responsavel),
    Coluna("Competências", "competencias", False, True, _lista(",", 40),
           lambda u, c: ", ".join(u.competencias)),
    # Só as accountabilities PRÓPRIAS. As delegadas o sistema deriva das
    # equipes dos reportes diretos a cada carga: escrevê-las numa coluna
    # editável convidaria a corrigir à mão o que vai ser recalculado.
    Coluna("Accountabilities", "responsabilidades", False, True,
           _lista("|", 200),
           lambda u, c: " | ".join(r.get("descricao", "")
                                   for r in u.responsabilidades
                                   if r.get("origem") != "delegada")),
    Coluna("Gestor Direto", "gestor", True, True, _texto(80),
           lambda u, c: c["pai"].nome if c["pai"] else ""),
]

TITULOS = [c.titulo for c in COLUNAS]

# Campos que a carga incremental compara e grava. Derivado de `COLUNAS` para
# não haver como acrescentar coluna e esquecer de comparar o campo dela.
CAMPOS_DA_PLANILHA = tuple(c.campo for c in COLUNAS
                           if c.atualiza and c.campo not in ("nome", "gestor"))

# Colunas lidas que NÃO são atributo de `Unidade`: entram na linha, servem a
# outra coisa, e não podem ser gravadas com `setattr`.
FORA_DA_UNIDADE = ("n5",)

# Campos cuja célula VAZIA significa "não mexe", e não "apaga".
#
# A distinção não é estética: é o que deixa uma planilha antiga de oito
# colunas continuar entrando. Sem ela, o arquivo sem a coluna Vínculo
# compararia "" contra o padrão `clt` e marcaria a empresa inteira como
# alterada — e a carga zeraria o vínculo de todo mundo de uma vez.
#
# As oito colunas originais ficam de fora desta regra de propósito: lá vazio
# sempre limpou o campo, e mudar isso mudaria o que planilhas em uso já fazem.
VAZIO_MANTEM = ("codigo", "tipo", "vinculo", "responsavel", "data_inicio",
                "status", "competencias", "responsabilidades")

# Ordena irmaos: lideranca a esquerda, apoio a direita.
# Código da raiz sintética. Ela não vem do RH — não é uma pessoa —, então não
# tem ID SAP: fica com um código próprio, que nenhum SAP vai colidir.
CODIGO_RAIZ = "ORG-RAIZ"


def nome_da_raiz(linhas: list[dict], padrao: str = "Diretoria") -> str:
    """O gestor mais citado que não é ninguém da planilha vira a raiz.

    A raiz é o nó que a planilha pressupõe e não declara: alguém escreve
    "Diretoria" na coluna de gestor e não existe linha com esse nome. Deduzir
    daí é melhor que fixar a palavra no código — o RH mudou de "Board" para
    "Diretoria" entre duas exportações, e nenhuma das duas é mais certa.

    **Depois de `resolver_gestores`**, sempre. Antes dela, o gestor escrito com
    o nome abreviado também parece não existir, e o mais citado deles ganharia:
    numa base real, "Marta Gomes" com treze menções viraria a raiz da empresa.
    """
    nomes = {sem_acento(l["nome"]) for l in linhas}
    fora = defaultdict(int)
    for l in linhas:
        g = (l.get("gestor") or "").strip()
        if g and sem_acento(g) not in nomes:
            fora[g] += 1
    return max(fora, key=lambda g: (fora[g], g)) if fora else padrao


PESO_TIPO = {"diretoria": 0, "gerencia": 1, "coordenacao": 2,
             "especialista": 3, "celula": 4, "area": 5, "apoio": 6}


def classificar(cargo: str) -> str:
    """Cargo -> tipo de unidade (enum org.tipo_unidade).

    Escada fixa, para a carga por linha de comando funcionar sem configuração
    nenhuma. Quem tem o cadastro à mão passa `classificador=` e ganha o
    catálogo de cargos e as regras do próprio tenant — é o que `main` faz.
    """
    c = sem_acento(cargo)
    if any(t in c for t in ("diretor", "ceo", "cto", "cfo", "clo", "conselho")):
        return "diretoria"
    if "gerente" in c or "gerencia" in c:
        return "gerencia"
    if any(t in c for t in ("coordenador", "coordenadora", "supervisor", "lider")):
        return "coordenacao"
    if any(t in c for t in ("estagi", "aprendiz", "assistente", "auxiliar")):
        return "apoio"
    return "celula"


def ler_planilha(caminho=PLANILHA) -> list[dict]:
    """Aceita caminho ou bytes. Casa o cabeçalho por TÍTULO, não por posição.

    A linha devolvida traz `None` na chave de uma coluna que o arquivo não
    tem, e `""` numa que ele tem em branco. Os dois casos são diferentes —
    "a planilha não fala deste campo" não é "a planilha diz que este campo é
    vazio" — e é essa diferença que deixa arquivo antigo e novo conviverem.
    """
    import openpyxl

    origem = io.BytesIO(caminho) if isinstance(caminho, (bytes, bytearray)) else caminho
    wb = openpyxl.load_workbook(origem, data_only=True, read_only=True)
    ws = wb["ORG"] if "ORG" in wb.sheetnames else wb[wb.sheetnames[0]]

    # Sem `max_col`: com ele, uma coluna obrigatória na nona posição sumia da
    # validação e a recusa acusava ausência de algo que estava lá.
    cabecalho = [sem_acento(str(c or "")).strip().lower()
                 for c in next(ws.iter_rows(max_row=1, values_only=True), ())]
    # O título canônico primeiro, os apelidos depois: se o arquivo trouxer os
    # dois — "ID SAP" e "Código" —, vale o canônico, e não a ordem em que
    # aparecem na planilha.
    onde: dict[str, int] = {}
    for c in COLUNAS:
        for nome in (c.titulo, *c.alias):
            chave_titulo = sem_acento(nome).lower()
            if chave_titulo in cabecalho:
                onde[c.titulo] = cabecalho.index(chave_titulo)
                break

    faltando = [c.titulo for c in COLUNAS if c.obrigatoria and c.titulo not in onde]
    if faltando:
        wb.close()
        raise ValueError(
            _t("coluna obrigatória ausente: {faltando}. Esperado: {esperado}",
               faltando=", ".join(faltando), esperado=", ".join(TITULOS)))

    leem = [(c, onde[c.titulo]) for c in COLUNAS if c.ler and c.titulo in onde]
    ausentes = [c.campo for c in COLUNAS if c.ler and c.titulo not in onde]
    i_nome = onde["Colaborador"]

    linhas: list[dict] = []
    for i, bruto in enumerate(ws.iter_rows(min_row=2, values_only=True)):
        if i_nome >= len(bruto) or not str(bruto[i_nome] or "").strip():
            continue
        linha = {"linha": i + 2}
        linha.update({campo: None for campo in ausentes})
        for c, ix in leem:
            linha[c.campo] = c.ler(bruto[ix] if ix < len(bruto) else None)
        linhas.append(linha)
    wb.close()
    return linhas


def presente(linha: dict, campo: str) -> bool:
    """A planilha fala deste campo nesta linha?

    Falso quando a coluna não existe no arquivo (`None`), e também quando a
    célula veio vazia num campo cuja regra é manter. Toda leitura de valor da
    planilha passa por aqui — é o funil que impede a carga de apagar em massa
    o que o arquivo simplesmente não menciona.
    """
    valor = linha.get(campo)
    if valor is None:
        return False
    return bool(valor) or campo not in VAZIO_MANTEM


# --------------------------------------------------------------------------
# DOMÍNIOS FECHADOS
#
# Duas colunas não aceitam texto livre. Quem preenche a planilha escreve o
# rótulo que vê na tela ("Gerência", "Consultoria"); o que o sistema grava é o
# código ("gerencia", "consultoria"). A conversão mora aqui, e é tolerante com
# acento e caixa porque a alternativa é recusar "gerencia" digitado sem crase.
#
# Valor irreconhecível NÃO vira o padrão: vira aviso no passo 2 e o campo
# fica como está. Rebaixar em silêncio uma diretoria para "célula" porque
# alguém escreveu "Diretor" no lugar de "Diretoria" é o tipo de estrago que
# só se descobre olhando o desenho semanas depois.
# --------------------------------------------------------------------------
def _resolver(texto: str, pares: list[tuple[str, str]]) -> str:
    alvo = sem_acento(str(texto or "")).strip().lower()
    for codigo, rotulo in pares:
        if alvo in (sem_acento(codigo).lower(), sem_acento(rotulo).lower()):
            return codigo
    return ""


def normalizar_dominios(linhas: list[dict], niveis: list[dict] | None) -> list[str]:
    """Troca rótulo por código nas colunas de domínio fechado, in loco.

    Devolve os avisos, que sobem para o passo 2 da carga assistida: o operador
    precisa ver "linha 14: nível «Chefe» não existe" ANTES de aplicar, e não
    descobrir depois que catorze pessoas ficaram no nível antigo.

    **Todo caminho que lê planilha passa por aqui** — a carga assistida e a
    carga total. Sem a escala, `tipo` receberia o rótulo cru ("Diretoria" em vez
    de "diretoria"), e o rótulo não casa com nada: `PESO_TIPO` cai no peso 9 e a
    ordem dos irmãos desmonta, `CORES_NIVEL` não acha a cor da fita, e o enum
    `org.tipo_unidade` do Postgres recusaria a linha. É exatamente o valor que
    a própria exportação escreve na coluna, então o ciclo se envenenava sozinho.

    Sem `niveis` — a linha de comando não tem cadastro para consultar — vale a
    escala padrão, que é a mesma que `classificar()` emite.
    """
    from . import cargos

    escalas = {
        "tipo": [(n["codigo"], n.get("rotulo", n["codigo"]))
                 for n in (niveis or cargos.niveis_padrao())],
        "vinculo": [(k, r) for k, (r, _cor) in dominio.VINCULOS.items()],
        "status": list(dominio.STATUS.items()),
    }
    avisos: list[str] = []
    for campo, pares in escalas.items():
        if not pares:
            continue
        recusados: list[str] = []
        for l in linhas:
            if not presente(l, campo):
                continue
            codigo = _resolver(l[campo], pares)
            if codigo:
                l[campo] = codigo
            else:
                recusados.append(f"{l['linha']}: «{l[campo]}»")
                l[campo] = None          # some da comparação: não é alteração
        if recusados:
            rotulo = {"tipo": _t("Nível"), "vinculo": _t("Vínculo")}.get(
                campo, _t("Status"))
            avisos.append(_t(
                "{n} linha(s) com {coluna} que não existe no cadastro — o campo "
                "fica como está: {quais}", n=len(recusados), coluna=rotulo,
                quais=", ".join(recusados[:5]))
                + ("…" if len(recusados) > 5 else ""))
    return avisos


def para_texto(valor) -> str:
    """Qualquer valor do contrato na forma em que ele aparece na planilha.

    Serve ao diff do passo 2, que precisa mostrar lado a lado o que está
    gravado e o que veio no arquivo — e os dois lados nem sempre são texto.
    """
    if isinstance(valor, list):
        return ", ".join(x.get("descricao", "") if isinstance(x, dict) else str(x)
                         for x in valor
                         if not (isinstance(x, dict) and x.get("origem") == "delegada"))
    return str(valor or "")


def indice_de_nomes(nomes) -> dict:
    """Índice para achar alguém pelo nome ABREVIADO.

    O RH escreve o colaborador com o nome inteiro e o gestor com o nome curto:
    a mesma pessoa é "Marta Brito Gomes" numa coluna e "Marta Gomes" na
    outra. Casando só por igualdade, cinco gestores desta base sumiriam e 26
    pessoas cairiam na raiz — um quarto da estrutura achatada por causa de um
    sobrenome omitido.

    A regra é conter, não parecer: os tokens do nome curto têm de estar TODOS
    no nome completo. Nada de distância de edição, que casaria "Ana Silva" com
    "Ana Silveira" e penduraria gente na pessoa errada em silêncio.

    Devolve `{frozenset(tokens): nome}` só para os conjuntos que identificam
    **uma** pessoa. Ambiguidade fica de fora: com dois candidatos, escolher é
    inventar, e a linha vira aviso.
    """
    # `set`, e não `list`: a mesma pessoa chega duas vezes quando o chamador
    # soma a planilha à base já cadastrada, e contar repetição como ambiguidade
    # esvaziava o índice — nesta base ele caía de 271 conjuntos para 6, e os
    # cinco gestores abreviados voltavam a não resolver. Ambíguo é o conjunto
    # que aponta para nomes DIFERENTES.
    por_conjunto: dict[frozenset, set[str]] = defaultdict(set)
    for nome in nomes:
        tokens = frozenset(sem_acento(nome).split())
        if tokens:
            por_conjunto[tokens].add(nome)
    return {k: next(iter(v)) for k, v in por_conjunto.items() if len(v) == 1}


def resolver_nome(curto: str, exatos: dict, indice: dict) -> str:
    """Nome escrito -> nome que existe. `""` quando não dá para decidir.

    Exato primeiro, sempre: um nome que casa inteiro nunca é desempatado por
    aproximação.
    """
    chave_exata = sem_acento(curto or "")
    if chave_exata in exatos:
        return exatos[chave_exata]
    procurado = frozenset(chave_exata.split())
    if not procurado:
        return ""
    achados = [nome for tokens, nome in indice.items() if procurado <= tokens]
    return achados[0] if len(achados) == 1 else ""


def resolver_gestores(linhas: list[dict], tambem=()) -> list[str]:
    """Reescreve `gestor` com o nome que existe, in loco. Devolve os avisos.

    `tambem` são nomes de fora da planilha — as pessoas já cadastradas —, para
    que uma carga parcial possa apontar para quem não veio no arquivo.

    Quem não resolve fica como está: `aplicar` já sabe pendurar na raiz, e o
    passo 2 já avisa. O que este passo evita é o contrário — pendurar na raiz
    quem TEM gestor, só porque o RH escreveu o nome dele pela metade.
    """
    nomes = [l["nome"] for l in linhas] + list(tambem)
    exatos = {sem_acento(n): n for n in nomes}
    indice = indice_de_nomes(nomes)
    ajustados: list[str] = []
    for l in linhas:
        curto = l.get("gestor") or ""
        if not curto or sem_acento(curto) in exatos:
            continue
        inteiro = resolver_nome(curto, exatos, indice)
        if inteiro:
            l["gestor"] = inteiro
            ajustados.append(f"{curto} → {inteiro}")
    if not ajustados:
        return []
    unicos = sorted(set(ajustados))
    return [_t("{n} gestor(es) vieram com o nome abreviado e foram casados "
               "pelo nome completo: {quais}", n=len(unicos),
               quais="; ".join(unicos[:5]))
            + ("…" if len(unicos) > 5 else "")]


def _mesmo_valor(atual, da_planilha) -> bool:
    """Compara pela forma que o usuário vê, não pela representação interna.

    Lista de competências e de accountabilities voltam da planilha como lista
    de strings, e no estado moram como lista de strings e lista de dicionários.
    Comparar os objetos crus faria toda pessoa com uma competência parecer
    alterada em toda carga.
    """
    if isinstance(da_planilha, list):
        if atual and isinstance(atual[0], dict):
            atual = [r.get("descricao", "") for r in atual
                     if r.get("origem") != "delegada"]
        return list(atual or []) == list(da_planilha)
    return str(atual or "") == str(da_planilha or "")


def _gravar_campo(u: Unidade, campo: str, valor) -> None:
    """Escreve um campo da planilha em `Unidade`, respeitando a forma de cada um."""
    if campo == "responsabilidades":
        # As delegadas são derivadas e voltam sozinhas em `_delegar_por_equipe`;
        # a planilha só manda nas próprias.
        u.responsabilidades = [r for r in u.responsabilidades
                               if r.get("origem") == "delegada"] + [
            {"descricao": d, "origem": "propria", "delegada_para": None}
            for d in valor]
    elif campo == "tipo":
        u.tipo = valor or u.tipo
    elif campo == "status":
        u.status = valor or u.status
    elif campo == "vinculo":
        # Última barreira: `normalizar_dominios` já resolveu o rótulo em código,
        # mas gravar aqui é o que de fato altera o estado, e um valor fora do
        # enum não pode passar por descuido de chamador.
        u.vinculo = valor if valor in dominio.VINCULOS else u.vinculo
    else:
        setattr(u, campo, valor)


def _nova_unidade(uid: str, linha: dict, parent_id: str | None,
                  classificador) -> Unidade:
    """Uma linha da planilha vira uma unidade nova.

    Projetado a partir de `COLUNAS`, e não com uma lista de argumentos escrita
    à mão: com a lista, acrescentar coluna gravava o campo em quem já existia
    (o laço da atualização é genérico) e o deixava vazio em quem nascia na
    mesma carga — divergência que não aparece em teste nenhum de uma coluna só.
    """
    u = Unidade(id=uid, codigo="", nome=linha["nome"], parent_id=parent_id,
                ordem=0, tipo=classificador(linha.get("cargo") or ""))
    for c in COLUNAS:
        if (c.atualiza and c.campo not in ("nome", "gestor")
                and c.campo not in FORA_DA_UNIDADE and presente(linha, c.campo)):
            _gravar_campo(u, c.campo, linha[c.campo])
    return u


def montar_unidades(linhas: list[dict], classificador=None, niveis=None
                    ) -> tuple[dict[str, Unidade], dict]:
    """Linhas da planilha -> arvore de Unidades com raiz unica."""
    classificador = classificador or classificar
    # A carga total escreve direto no estado, sem passo 2 para conferir: se o
    # domínio fechado não for resolvido aqui, ninguém percebe antes de a tela
    # abrir errada.
    normalizar_dominios(linhas, niveis)
    resolver_gestores(linhas)
    por_nome = {sem_acento(l["nome"]): l for l in linhas}
    if len(por_nome) != len(linhas):
        contagem: dict[str, int] = defaultdict(int)
        for l in linhas:
            contagem[sem_acento(l["nome"])] += 1
        dup = sorted(k for k, n in contagem.items() if n > 1)
        raise ValueError(_t("ORG-DUPLICIDADE: colaborador repetido na "
                            "planilha: {dup}", dup=dup))

    ids = {chave: uuid.uuid5(uuid.NAMESPACE_OID, "gplansis-org:" + chave).hex[:12]
           for chave in por_nome}

    # Sem gestor conhecido = reporte ao conselho. Vira filho da raiz sintetica.
    raiz_id = uuid.uuid5(uuid.NAMESPACE_OID, "gplansis-org:__board__").hex[:12]
    orfaos = [chave for chave, l in por_nome.items()
              if sem_acento(l["gestor"] or "") not in por_nome
              or sem_acento(l["gestor"] or "") == chave]

    unidades: dict[str, Unidade] = {}
    # O nome da raiz sai da planilha: é o gestor que ninguém consegue casar
    # com uma linha — "Diretoria" nesta base, "Board" na anterior. Fixá-lo no
    # código obrigaria o RH a escrever a palavra que o programa espera.
    unidades[raiz_id] = Unidade(
        id=raiz_id, codigo=CODIGO_RAIZ, nome=nome_da_raiz(linhas),
        tipo="diretoria", parent_id=None, ordem=0,
        cargo="Conselho de administração", area="Governança corporativa",
    )
    for chave, l in por_nome.items():
        pai = sem_acento(l["gestor"] or "")
        unidades[ids[chave]] = _nova_unidade(
            ids[chave], l,
            ids[pai] if pai in por_nome and pai != chave else raiz_id,
            classificador)

    _ordenar_e_codificar(unidades, raiz_id)
    _delegar_por_equipe(unidades)

    relato = {
        "colaboradores": len(linhas),
        "raiz_sintetica": "Board",
        "reportes_ao_conselho": sorted(por_nome[o]["nome"] for o in orfaos),
        "verticais": sorted({l["vertical"] for l in linhas if l.get("vertical")}),
        "equipes": len({l["area"] for l in linhas if l.get("area")}),
    }
    return unidades, relato


def _ordenar_e_codificar(unidades: dict[str, Unidade], raiz_id: str) -> None:
    """Fixa a ordem de exibicao dos irmaos e numera QUEM CHEGOU SEM CODIGO.

    Numerava todo mundo, em pre-ordem. Fazia sentido quando o codigo era
    invencao nossa; com o ID SAP na planilha, reescrever `51` como `ORG-0015`
    joga fora o unico identificador que o RH e o organograma tem em comum — e o
    joga fora justamente na carga que veio para trazer o SAP.
    """
    filhos: dict[str, list[Unidade]] = defaultdict(list)
    for u in unidades.values():
        if u.parent_id:
            filhos[u.parent_id].append(u)
    for k in filhos:
        filhos[k].sort(key=lambda x: (PESO_TIPO.get(x.tipo, 9), x.centro_custo,
                                      sem_acento(x.nome)))
        for i, f in enumerate(filhos[k]):
            f.ordem = (i + 1) * 10

    usados = {u.codigo for u in unidades.values() if u.codigo}
    n = [1]
    pilha = [unidades[raiz_id]]
    while pilha:
        u = pilha.pop(0)
        if not u.codigo:
            while f"ORG-{n[0]:04d}" in usados:
                n[0] += 1
            u.codigo = f"ORG-{n[0]:04d}"
            usados.add(u.codigo)
        pilha = filhos.get(u.id, []) + pilha        # pre-ordem


def _delegar_por_equipe(unidades: dict[str, Unidade]) -> None:
    """Recalcula a accountability DELEGADA. A própria é de quem a escreveu.

    Delegada = as equipes dos reportes diretos: é o único escopo derivável do
    dado sem inventar nada — o que a liderança responde através de terceiros.
    Como é derivada, tem de ser recalculada a cada carga: se um subordinado
    muda de time, o escopo delegado do gestor mudou junto.

    A própria não é derivável de coisa nenhuma. Vem do painel ou da coluna
    Accountabilities, e é preservada aqui — esta função **acrescenta** as
    delegadas às próprias em vez de trocar a lista inteira.

    Trocar era o que ela fazia, e o efeito era o oposto do prometido: toda
    carga assistida apagava a accountability própria de quem tivesse ao menos
    um subordinado. Quem tem subordinado é exatamente quem tem accountability
    que vale a pena escrever, e o teste que cobria isso olhava uma folha —
    o único caso em que a promessa era verdadeira.
    """
    filhos: dict[str, list[Unidade]] = defaultdict(list)
    for u in unidades.values():
        if u.parent_id:
            filhos[u.parent_id].append(u)
    for u in unidades.values():
        proprias = [r for r in u.responsabilidades
                    if r.get("origem") != "delegada"]
        # A equipe do proprio pai nao e escopo delegado: e onde ele mesmo esta.
        seu = {sem_acento(u.area), sem_acento(u.nome)}
        equipes: list[str] = []
        # Uma chave só para os dois testes. Comparando o cru para deduplicar e o
        # normalizado para excluir a equipe do pai, "Produção" e "producao" —
        # a mesma equipe digitada de dois jeitos na planilha — escapavam da
        # deduplicação e o card mostrava a accountability repetida.
        for f in sorted(filhos.get(u.id, []),
                        key=lambda x: (x.ordem, sem_acento(x.nome))):
            k = sem_acento(f.area)
            if f.area and k not in seu:
                seu.add(k)
                equipes.append(f.area)
        u.responsabilidades = proprias + [
            {"descricao": e, "origem": "delegada", "delegada_para": None}
            for e in equipes
        ]


# ---------------------------------------------------------------------------
# SEED DA SPEC 13 (fallback e caso-piloto de RH)
# ---------------------------------------------------------------------------
def montar_seed_spec() -> tuple[dict[str, Unidade], dict]:
    def uid(n: str) -> str:
        return uuid.uuid5(uuid.NAMESPACE_OID, "gplansis-spec:" + n).hex[:12]

    def mk(codigo, nome, tipo, pai, ordem, resp, cargo, itens, skills=()):
        u = Unidade(id=uid(codigo), codigo=codigo, nome=nome, tipo=tipo,
                    parent_id=uid(pai) if pai else None, ordem=ordem,
                    responsavel=resp, cargo=cargo, area="Human Resources",
                    responsabilidades=[{"descricao": d, "origem": o,
                                        "delegada_para": None} for d, o in itens],
                    competencias=list(skills))
        return u

    us = [
        mk("ORG-0001", "Recursos Humanos", "gerencia", None, 0,
           "Marina Albuquerque Sá", "Gerente de RH", [
               ("L.G.R.", "delegada"),
               ("Atração e gestão de talentos", "delegada"),
               ("Desenvolvimento organizacional e cultura", "delegada"),
               ("Remuneração estratégica", "delegada"),
               ("Administração de pessoal", "delegada")]),
        mk("ORG-0002", "Remuneração Estratégica", "area", "ORG-0001", 10,
           "Beatriz Nogueira Pinto", "Coordenadora de RH", [
               ("Remuneração", "propria"), ("Benefícios", "propria"),
               ("Gestão de talentos", "propria"), ("Indicadores", "propria"),
               ("Gestão PJ", "propria")]),
        mk("ORG-0003", "Administração de Pessoal", "area", "ORG-0001", 20,
           "Jaqueline Cavalcanti Cardoso", "Coordenador de Adm. Pessoal", [
               ("L.G.R.", "propria"), ("Folha de pagamento", "propria"),
               ("Admissão / rescisão", "propria"), ("Ponto", "propria"),
               ("Férias", "propria")]),
        mk("ORG-0004", "Desenvolvimento Organizacional", "area", "ORG-0001", 30,
           "Daniela Fontes Ribeiro", "Analista de Desenv. Organizacional", [
               ("Treinamentos", "propria"), ("Programas de capacitação", "propria"),
               ("Gestão de estagiários", "propria"), ("Eventos especiais", "propria"),
               ("GPTW", "propria")]),
        mk("ORG-0005", "Atração de Talentos", "area", "ORG-0001", 40,
           "Lucas Souza Brito", "Analista de Atração de Talentos", [
               ("Recrutamento e seleção", "propria"), ("Onboarding", "propria"),
               ("Offboarding", "propria")]),
        mk("ORG-0006", "Documentação", "apoio", "ORG-0001", 50,
           "Elaine Moreira Lins", "Analista Administrativo", [
               ("Documentação de integração em clientes", "propria"),
               ("Obrigações acessórias", "propria"),
               ("Suporte no onboarding", "propria"),
               ("Suporte em eventos", "propria")]),
    ]
    return {u.id: u for u in us}, {"origem": "SPEC-GPLANSIS-ORG-001 §13",
                                   "colaboradores": len(us)}


# ---------------------------------------------------------------------------
# ESTADO SERIALIZADO
# ---------------------------------------------------------------------------
def evento_genese(motivo: str, payload: dict) -> dict:
    quando = datetime.now(timezone.utc).isoformat(timespec="seconds")
    corpo = "|".join(["GENESIS", quando, "importador@local", "criar", "-", motivo,
                      json.dumps(payload, sort_keys=True, ensure_ascii=False)])
    return {"seq": 1, "quando": quando, "ator": "importador@local", "acao": "criar",
            "entidade_id": "-", "motivo": motivo, "payload": payload,
            "hash_anterior": "GENESIS",
            "hash": hashlib.sha256(corpo.encode()).hexdigest()}


def montar_estado(unidades: dict[str, Unidade], relato: dict, motivo: str) -> dict:
    from dataclasses import asdict
    return {
        "unidades": {k: asdict(v) for k, v in unidades.items()},
        "eventos": [evento_genese(motivo, relato)],
        "orientacao": "invertida",
        "colapsados": [],
    }


def gerar(spec: bool = False) -> dict:
    if spec:
        unidades, relato = montar_seed_spec()
        motivo = "carga do seed de referência da SPEC §13"
    else:
        unidades, relato = montar_unidades(ler_planilha())
        motivo = "carga inicial a partir de Organograma.xlsx"
    return montar_estado(unidades, relato, motivo)


# ---------------------------------------------------------------------------
# CARGA INCREMENTAL ASSISTIDA
# ---------------------------------------------------------------------------
def chave(nome: str, email: str = "") -> str:
    """O segundo dos tres degraus do pareamento: e-mail, com o nome de reserva.

    Casar por nome quebraria em toda mudanca de sobrenome; casar so por e-mail
    perderia quem ainda nao tem conta. A composicao cobre os dois casos — mas
    nao cobre trocar os DOIS no mesmo arquivo, e e por isso que o `Codigo` vem
    antes dela em `analisar`, e o nome sozinho depois.
    """
    return (email or "").strip().lower() or "nome:" + sem_acento(nome)


def analisar(conteudo: bytes, unidades: dict[str, Unidade], nome_arquivo: str,
             niveis: list[dict] | None = None) -> dict:
    """Compara a planilha enviada com a estrutura vigente. Nao altera nada."""
    linhas = ler_planilha(conteudo)
    if not linhas:
        raise ValueError(_t("a planilha não tem nenhuma linha de colaborador"))
    avisos = normalizar_dominios(linhas, niveis)
    avisos += resolver_gestores(linhas, [u.nome for u in unidades.values()])

    # A raiz entra no pareamento - ela tambem pode ter cargo ou e-mail alterado -
    # mas nunca na lista de remocao: RF-03 exige que o organograma tenha raiz.
    atuais = {chave(u.nome, u.email): u for u in unidades.values()}
    por_nome_atual = {sem_acento(u.nome): u for u in unidades.values()}
    # O código é a identidade que sobrevive a trocar nome E e-mail no mesmo
    # arquivo — pelo par nome/e-mail isso vira uma remoção mais uma admissão,
    # e a pessoa perde histórico, accountability e lugar na árvore.
    por_codigo = {u.codigo: u for u in unidades.values() if u.codigo}
    # Código repetido desqualifica o código, dos DOIS lados — a mesma regra que
    # `ambiguos` aplica ao nome logo abaixo, e pelo mesmo motivo.
    #
    # Sem isto, duas linhas com o mesmo ID SAP casavam com a MESMA unidade: a
    # segunda sobrescrevia a primeira, uma das duas pessoas sumia da carga sem
    # aparecer em "removidos", e o passo 2 não dizia nada — havia aviso para
    # nome repetido e nenhum para código repetido, que é a identidade mais
    # forte do contrato. E dois cadastros já gravados com o mesmo código faziam
    # o `dict` ficar com o último em silêncio, então a carga seguinte escrevia
    # na pessoa errada.
    #
    # Desqualificado o código, a linha cai para nome+e-mail, que é o caminho
    # honesto: ou identifica, ou entra como pessoa nova.
    codigos_ambiguos = ({c for c, n in Counter(
        u.codigo for u in unidades.values() if u.codigo).items() if n > 1}
        | {c for c, n in Counter(
            l["codigo"].strip().upper() for l in linhas
            if presente(l, "codigo")).items() if n > 1})
    por_codigo = {c: u for c, u in por_codigo.items()
                  if c.strip().upper() not in codigos_ambiguos}
    # Homônimo não pode ser desempatado pelo nome: fica de fora do último
    # recurso, e cai na regra de cima ou vira linha nova, que é honesto. A
    # ambiguidade desqualifica dos DOIS lados — dois xarás já gravados, ou duas
    # linhas com o mesmo nome no arquivo. Com a guarda só de um lado, uma
    # planilha parcial com dois "Ana Silva" casava as duas com a mesma pessoa:
    # ninguém era admitido, e a segunda linha sobrescrevia a primeira em
    # silêncio, sem um aviso no passo 2.
    def repetidos(nomes) -> set[str]:
        c: dict[str, int] = defaultdict(int)
        for n in nomes:
            c[sem_acento(n)] += 1
        return {k for k, v in c.items() if v > 1}

    ambiguos = repetidos(u.nome for u in unidades.values()) \
        | repetidos(l["nome"] for l in linhas)
    nome_unico = {k: v for k, v in por_nome_atual.items() if k not in ambiguos}

    vistos: set[str] = set()

    def casar(l: dict) -> tuple[Unidade | None, bool]:
        if presente(l, "codigo"):
            achado = por_codigo.get(l["codigo"].strip().upper())
            if achado is not None:
                return achado, True
        achado = atuais.get(chave(l["nome"], l.get("email") or ""))
        if achado is not None:
            return achado, False
        # Último recurso: o nome, e ele vale mesmo quando a linha TEM e-mail.
        #
        # Servia só para a planilha parcial, sem coluna de e-mail. Mas o e-mail
        # também falha quando ele mudou dos dois lados — nesta carga, uma pessoa
        # está sem e-mail na base e outra tem `l.felix@` contra `l.feliz@` na
        # planilha, um dedo trocado. Pelo par nome+e-mail as duas viravam uma
        # demissão mais uma admissão, e perdiam histórico por causa de um typo.
        #
        # É seguro porque `ambiguos` desqualifica homônimo dos DOIS lados: só
        # chega aqui um nome que identifica uma pessoa na base e uma na
        # planilha. O caso que escapa — dois xarás distintos, um saindo e outro
        # entrando no mesmo arquivo — some a partir da próxima carga, quando
        # todo mundo já tiver o ID SAP gravado.
        return nome_unico.get(sem_acento(l["nome"])), False

    novos, alterados, sem_mudanca = [], [], 0
    for l in linhas:
        u, pelo_codigo = casar(l)
        # Uma pessoa não pode ser reivindicada por duas linhas, por caminho
        # nenhum: a segunda vira admissão, que é o que ela de fato parece ser.
        if u is not None and u.id in vistos:
            u = None
        if u is None:
            novos.append(l)
            continue
        vistos.add(u.id)
        mudancas = []
        for campo in CAMPOS_DA_PLANILHA:
            if campo in FORA_DA_UNIDADE or not presente(l, campo):
                continue          # a planilha não fala deste campo nesta linha
            if not _mesmo_valor(getattr(u, campo), l[campo]):
                mudancas.append((campo, getattr(u, campo), l[campo]))
        # Renomear só é uma alteração quando a linha foi casada pelo código.
        # Casada por nome e e-mail, o nome É a chave: ele não pode ter mudado,
        # e é exatamente por isso que a coluna Código existe — sem ela, casar
        # sozinha vira demissão mais admissão.
        if pelo_codigo and l["nome"] != u.nome:
            mudancas.append(("nome", u.nome, l["nome"]))
        if u.parent_id is not None and l.get("gestor"):
            gestor_atual = unidades[u.parent_id].nome
            if sem_acento(gestor_atual) != sem_acento(l["gestor"]):
                mudancas.append(("gestor", gestor_atual, l["gestor"]))
        if mudancas:
            alterados.append({"id": u.id, "codigo": u.codigo, "nome": u.nome,
                              "mudancas": mudancas, "chave": u.id})
        else:
            sem_mudanca += 1

    removidos = [{"id": u.id, "codigo": u.codigo, "nome": u.nome, "cargo": u.cargo,
                  "area": u.area}
                 for u in unidades.values()
                 if u.id not in vistos and u.parent_id is not None]

    if not any(l.get("email") for l in linhas):
        avisos.append(_t("Nenhuma linha tem e-mail: o pareamento cairá para o "
                         "nome, e renomear alguém será lido como troca de "
                         "pessoa."))
    repetidos_no_arquivo = sorted(
        {l["nome"] for l in linhas if sem_acento(l["nome"]) in ambiguos})
    if repetidos_no_arquivo:
        avisos.append(_t(
            "{n} nome(s) aparecem mais de uma vez, aqui ou na estrutura: sem "
            "e-mail ou código não dá para saber de quem é a linha, e ela entra "
            "como pessoa nova. {quais}", n=len(repetidos_no_arquivo),
            quais=", ".join(repetidos_no_arquivo[:5]))
            + ("…" if len(repetidos_no_arquivo) > 5 else ""))
    if codigos_ambiguos:
        quais = sorted(codigos_ambiguos)
        avisos.append(_t(
            "{n} código(s) aparecem mais de uma vez, aqui ou na estrutura. O "
            "código é a identidade mais forte do contrato: repetido, ele deixa "
            "de identificar, e essas linhas caem para nome e e-mail. {quais}",
            n=len(quais), quais=", ".join(quais[:5]))
            + ("…" if len(quais) > 5 else ""))
    fora = [l["nome"] for l in linhas
            if l.get("gestor") and sem_acento(l["gestor"]) not in
            {sem_acento(x["nome"]) for x in linhas} | set(por_nome_atual)]
    if fora:
        avisos.append(_t("{n} linha(s) apontam para gestor inexistente e "
                         "passariam a responder à raiz: {quais}",
                         n=len(fora), quais=", ".join(fora[:5]))
                      + ("…" if len(fora) > 5 else ""))

    return {"arquivo": nome_arquivo, "linhas": linhas, "novos": novos,
            "alterados": alterados, "removidos": removidos,
            "sem_mudanca": sem_mudanca, "avisos": avisos, "total": len(linhas)}


def aplicar(analise: dict, unidades: dict[str, Unidade], criar: bool,
            atualizar: bool, remover: bool, novo_id, classificador=None,
            piso_codigo: int = 0) -> dict:
    """Aplica as classes escolhidas. A raiz nunca e removida nem reparentada."""
    from .dominio import raiz

    classificador = classificador or classificar
    r = raiz(unidades)
    # A marca d'água sobe ANTES de remover: depois, quem saiu já não está no
    # dicionário para ser contado, e o número dele voltaria a ser emitido na
    # mesma operação que o aposentou.
    piso_codigo = max([piso_codigo]
                      + [numero_do_codigo(u.codigo) for u in unidades.values()])
    resumo = {"arquivo": analise["arquivo"], "criados": 0, "atualizados": 0,
              "removidos": 0, "reparentados": 0, "ciclos_recusados": 0}

    # Dois índices montados UMA vez e mantidos ao longo da carga. Antes cada
    # reparentagem reconstruía o índice de nomes, o mapa de filhos e, dentro de
    # `descendentes`, um terceiro mapa de filhos — três varreduras da árvore
    # inteira por pessoa. Numa carga de 265 trocas de gestor davam 785
    # travessias e 778 ms; o trabalho é o mesmo com uma travessia só.
    #
    # A ordem dentro de cada lista não importa aqui: o índice serve para contar
    # irmãos, atravessar a subárvore e achar pai por nome. Quem precisa da ordem
    # canônica chama `mapa_filhos` de novo, depois.
    filhos_de: dict[str | None, list[Unidade]] = {}
    for u in unidades.values():
        filhos_de.setdefault(u.parent_id, []).append(u)
    por_nome = {sem_acento(u.nome): u for u in unidades.values()}

    def esta_abaixo(topo: str, alvo: str) -> bool:
        """`alvo` está na subárvore de `topo`? — a guarda de ciclo (RF-02)."""
        pilha = [topo]
        while pilha:
            for f in filhos_de.get(pilha.pop(), []):
                if f.id == alvo:
                    return True
                pilha.append(f.id)
        return False

    def reparentar(u: Unidade, nome_gestor: str) -> None:
        alvo = por_nome.get(sem_acento(nome_gestor)) if nome_gestor else None
        destino = alvo.id if alvo else r.id
        if u.parent_id == destino or u.id == destino:
            return
        if esta_abaixo(u.id, destino):                   # RF-02 / INV-02
            resumo["ciclos_recusados"] += 1
            return
        irmaos = filhos_de.get(u.parent_id)
        if irmaos:
            filhos_de[u.parent_id] = [f for f in irmaos if f.id != u.id]
        u.parent_id = destino
        filhos_de.setdefault(destino, []).append(u)
        u.ordem = len(filhos_de[destino]) * 10
        resumo["reparentados"] += 1

    if criar:
        pendentes: list[tuple[Unidade, str]] = []
        for l in analise["novos"]:
            uid = novo_id()
            u = _nova_unidade(uid, l, r.id, classificador)
            unidades[uid] = u
            filhos_de.setdefault(r.id, []).append(u)
            por_nome.setdefault(sem_acento(u.nome), u)
            pendentes.append((u, l.get("gestor") or ""))
            resumo["criados"] += 1
        for u, gestor in pendentes:              # so depois que todos existem
            reparentar(u, gestor)

    if atualizar:
        indice = {u.id: u for u in unidades.values()}
        for alt in analise["alterados"]:
            u = indice.get(alt["id"])
            if u is None:
                continue
            for campo, _, novo in alt["mudancas"]:
                if campo == "gestor":
                    reparentar(u, novo)
                else:
                    if campo == "nome":
                        # O índice de nomes é o que resolve "Gestor Direto" das
                        # linhas seguintes: renomear sem avisá-lo faria a linha
                        # que aponta para o nome novo cair na raiz.
                        por_nome.pop(sem_acento(u.nome), None)
                        por_nome[sem_acento(novo)] = u
                    _gravar_campo(u, campo, novo)
            resumo["atualizados"] += 1

    if remover:
        for rem in analise["removidos"]:
            u = unidades.get(rem["id"])
            if u is None or u.parent_id is None:
                continue
            netos = filhos_de.pop(u.id, [])
            for f in netos:                       # filhos sobem ao avo
                f.parent_id = u.parent_id
            irmaos = [f for f in filhos_de.get(u.parent_id, []) if f.id != u.id]
            filhos_de[u.parent_id] = irmaos + netos
            por_nome.pop(sem_acento(u.nome), None)
            del unidades[u.id]
            resumo["removidos"] += 1

    resumo["piso_codigo"] = _renumerar_codigos(unidades, r.id, piso_codigo)
    _delegar_por_equipe(unidades)
    return resumo


def numero_do_codigo(codigo: str) -> int:
    return int(codigo[4:]) if codigo[:4] == "ORG-" and codigo[4:].isdigit() else 0


def _renumerar_codigos(unidades: dict[str, Unidade], raiz_id: str,
                       piso: int = 0) -> int:
    """So numera quem chegou sem codigo: ORG-#### e estavel para quem ja tem.

    E numera **acima do maior já emitido**, sem tapar buraco. Preencher a vaga
    de um removido economizaria números e custaria identidade: o código virou
    chave de pareamento da planilha, e uma planilha guardada de mês passado
    casaria a linha do demitido com quem entrou depois no lugar dele. Buraco na
    sequência é barato; pessoa trocada por outra, não.

    Por isso `piso` — quem saiu não está mais no dicionário para ser contado,
    então o maior já emitido tem de vir guardado de fora (`Config.piso_codigo`).
    Devolve o novo piso, para quem chamou guardar de volta.
    """
    usados = {u.codigo for u in unidades.values() if u.codigo}
    n = max([piso] + [numero_do_codigo(c) for c in usados]) + 1
    for u in sorted(unidades.values(), key=lambda x: (x.ordem, sem_acento(x.nome))):
        if u.codigo:
            continue
        while f"ORG-{n:04d}" in usados:
            n += 1
        u.codigo = f"ORG-{n:04d}"
        usados.add(u.codigo)
    return max([piso] + [numero_do_codigo(u.codigo) for u in unidades.values()])


def _cabecalho_org(ws, Alignment, Font, PatternFill) -> None:
    """O cabeçalho do contrato, igual no modelo e na aba ORG da exportação.

    Obrigatória em grafite, opcional em cinza: dá para ver, antes de preencher,
    quais duas colunas a carga recusa em branco.
    """
    ws.append(TITULOS)
    for i, coluna in enumerate(COLUNAS, start=1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFFFF")
        c.fill = PatternFill("solid",
                             fgColor="FF2D3336" if coluna.obrigatoria else "FF7D8286")
        c.alignment = Alignment(vertical="center")
        ws.column_dimensions[c.column_letter].width = max(14, len(str(c.value)) + 6)
    ws.freeze_panes = "A2"


def _linha_org(u: Unidade, contexto: dict) -> list:
    """A unidade projetada nas colunas do contrato, na ordem do contrato."""
    return [c.escrever(u, contexto) for c in COLUNAS]


def modelo_xlsx() -> bytes:
    """Planilha-modelo com as colunas esperadas e duas linhas de exemplo."""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ORG"
    _cabecalho_org(ws, Alignment, Font, PatternFill)

    # Os exemplos vêm por nome de coluna, e não como lista posicional: com a
    # lista, acrescentar coluna no meio deslocava os dois exemplos em silêncio
    # e o modelo saía ensinando a coisa errada.
    exemplos = [
        {"Código": "", "Colaborador": "Fulano de Tal",
         "Cargo/Função": "Diretor Executivo / CEO", "Nível": "Diretoria",
         "Vínculo": "CLT", "Departamento": "Board",
         "E-mail": "f.tal@empresa.com.br", "N2": "90.0", "N3": "90.10",
         "N4": "90.11", "Responsável": "", "Competências": "Governança, M&A",
         "Accountabilities": "Resultado do grupo | Relação com o conselho",
         "Gestor Direto": "Board"},
        {"Código": "", "Colaborador": "Beltrano de Tal",
         "Cargo/Função": "Gerente de Operações", "Nível": "Gerência",
         "Vínculo": "PJ", "Departamento": "Engineering",
         "E-mail": "b.tal@empresa.com.br", "N2": "80.0", "N3": "80.00",
         "N4": "80.01", "Responsável": "", "Competências": "Lean, PCP",
         "Accountabilities": "Entrega de obra", "Gestor Direto": "Fulano de Tal"},
    ]
    for e in exemplos:
        ws.append([e.get(c.titulo, "") for c in COLUNAS])
    ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(COLUNAS)).column_letter}3"

    # A planilha-modelo é baixada por quem vai preencher: fala a língua dele.
    guia = wb.create_sheet(_t("como preencher")[:31])
    for linha in [
        [_t("GPlanSiS|Peoples — modelo de carga")],
        [],
        [_t("As duas colunas em grafite são obrigatórias; as demais, quando "
            "ficam em branco, seguem a regra descrita ao lado de cada uma. "
            "Coluna que você apagar do arquivo simplesmente não é lida — dá "
            "para mandar só as colunas que quer atualizar.")],
        [],
        [_t("Colaborador"), _t("obrigatório. Identifica a pessoa.")],
        [_t("Gestor Direto"),
         _t("obrigatório. Nome exatamente como aparece em Colaborador. Quem "
            "responde ao conselho recebe um nome que não existe na coluna "
            "Colaborador (ex.: Board) e vira filho da raiz.")],
        [_t("Código"),
         _t("ORG-####, gerado pelo sistema. Não invente: quando vem "
            "preenchido, é ele que diz de quem é a linha, e por isso trocar "
            "nome e e-mail na mesma carga deixa de virar demissão mais "
            "admissão. Em branco, o pareamento cai para e-mail e nome.")],
        [_t("E-mail"),
         _t("recomendado. É a identidade estável entre cargas: sem ele o "
            "pareamento cai para o nome e uma troca de sobrenome vira pessoa "
            "nova.")],
        [_t("Nível"),
         _t("rótulo do nível hierárquico, como aparece em Configurações › "
            "Cargos e níveis (Diretoria, Gerência, Coordenação, Célula, Área, "
            "Apoio). Em branco mantém o nível atual; em linha nova, o sistema "
            "deduz do cargo. Valor que não existe no cadastro vira aviso no "
            "passo 2 e não é gravado.")],
        [_t("Vínculo"),
         _t("CLT, PJ ou Consultoria. Em branco mantém o que está gravado — "
            "coluna vazia não rebaixa ninguém para CLT.")],
        ["N2 / N3 / N4",
         _t("centros de custo. N2 é a vertical, N4 é o CC da equipe. N3 é "
            "derivado do N4 pelo cadastro: sai na exportação para orientar a "
            "leitura, e é ignorado na carga.")],
        [_t("Departamento"), _t("equipe. Aparece no card e alimenta o filtro.")],
        [_t("Responsável"),
         _t("quem responde pela unidade, quando o card representa uma área e "
            "não uma pessoa. Em branco mantém.")],
        [_t("Competências"),
         _t("separadas por vírgula. Em branco mantém — para esvaziar a lista "
            "de alguém, use o painel.")],
        [_t("Accountabilities"),
         _t("separadas por barra vertical (|). São as próprias. As delegadas "
            "o sistema deriva das equipes dos reportes diretos a cada carga e "
            "não se editam aqui. Em branco mantém.")],
    ]:
        guia.append(linha)
    guia.column_dimensions["A"].width = 22
    guia.column_dimensions["B"].width = 92
    for linha in guia.iter_rows():
        for c in linha:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    guia["A1"].font = Font(bold=True, size=13)

    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


# A paleta institucional em ARGB, que é o que o openpyxl fala. As chaves são as
# mesmas de `cargos.CORES_NIVEL`, e de propósito: o nível guarda um nome de cor,
# não um hexadecimal, então a faixa da planilha é pintada pela mesma escolha que
# colore a fita do card. Um dicionário só — dois com os mesmos tons divergiriam
# no primeiro ajuste, e o que sai em arquivo é o que ninguém confere.
#
# Nenhum tom novo, e nenhum deles vira texto: planilha tem fundo branco, e sobre
# branco o laranja dá 3,4:1.
PALETA = {
    "grafite": "FF2D3336",
    "laranja": "FFEB6A20",
    "ambar": "FFF6A709",
    "cinza": "FF7D8286",
    "cinza-claro": "FFB9BDBF",
    "papel": "FFFFFFFF",
}
# Sobre grafite e cinza o texto branco passa; sobre âmbar e cinza-claro, não.
# A régua é a mesma da tela: fundo escuro pede branco, fundo claro pede grafite.
NIVEL_CLARO = ("ambar", "cinza-claro")


def export_xlsx(unidades: dict[str, Unidade], recorte: str = "",
                ids: set[str] | None = None, titulo: str = "Organograma",
                subtitulo: str = "", tenant: str = "",
                niveis: list[dict] | None = None,
                marca: Path | None = None,
                cc: dict | None = None, hoje=None) -> bytes:
    """A estrutura em Excel: uma aba para ler, uma para devolver.

    **`Organograma`** é a que abre: cabeçalho com a marca, e as pessoas
    agrupadas por nível hierárquico, com faixa colorida por nível e recuo por
    profundidade. As linhas levam agrupamento nativo do Excel (`outlineLevel`),
    então o `−` da margem dobra um nível inteiro — a mesma leitura da tabela do
    sistema, dentro da ferramenta de quem recebeu o arquivo.

    `titulo`, `subtitulo` e `tenant` são os mesmos três do PDF (`pdf.meta_padrao`)
    e chegam prontos de fora pelo mesmo motivo: a legenda que descreve o desenho
    é montada num lugar só, senão o papel e a planilha divergem no primeiro
    ajuste — e quem confere a legenda de um arquivo que já saiu é ninguém.

    **`ORG`** é a mesma estrutura no contrato que a carga lê: as colunas de
    `COLUNAS`, cabeçalho na primeira linha, sem decoração. É o que faz o ciclo
    fechar — exporta, edita, devolve pelos três passos. `ler_planilha` procura
    esta aba pelo nome antes de cair na primeira, e é por isso que a apresentação
    pode vir na frente sem quebrar a volta.

    As duas abas saem projetadas de `COLUNAS`, e por isso a de contrato traz
    tudo o que a gaveta edita — inclusive accountability e competência. A
    coluna de accountability leva só as **próprias**: as delegadas o sistema
    deriva das equipes dos reportes diretos a cada carga, e escrevê-las numa
    célula editável convidaria a corrigir à mão o que vai ser recalculado.

    `ids` é o recorte vigente — sai o que está na tela, como no CSV, no SVG e no
    PDF.
    """
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    rotulos = {n["codigo"]: n.get("rotulo", n["codigo"]) for n in (niveis or [])}
    cores = {n["codigo"]: n.get("cor", "cinza") for n in (niveis or [])}
    # `cc` traz o que o cadastro de centros de custo resolveu por unidade — de
    # onde sai o N5. `hoje` fixa a data do tempo de casa: sem ela, dois testes
    # da mesma suíte podem cair em dias diferentes e discordar.
    cc = cc or {}
    hoje = hoje or date.today()

    filhos = mapa_filhos(unidades)
    prof = _profundidades(unidades)
    saem: list[Unidade] = []

    def caminhar(u: Unidade) -> None:
        if ids is None or u.id in ids:
            saem.append(u)
        for f in filhos.get(u.id, []):
            caminhar(f)

    caminhar(raiz(unidades))

    wb = openpyxl.Workbook()

    # ---------------------------------------------------------------- ORG ---
    # A aba do contrato nasce primeiro para ficar em segundo plano depois: o
    # que abre é a apresentação, o que a carga lê é esta.
    ws = wb.active
    ws.title = "ORG"
    _cabecalho_org(ws, Alignment, Font, PatternFill)
    # Projetado por `COLUNAS`, e não escrito à mão: era o único lugar da aba
    # ORG que não derivava do contrato, e uma coluna nova sairia em branco aqui
    # — o que faria o próprio arquivo exportado, ao voltar, marcar a empresa
    # inteira como alterada.
    for u in saem:
        ws.append(_linha_org(u, {
            "pai": unidades.get(u.parent_id) if u.parent_id else None,
            "rotulos": rotulos, "cc": cc, "hoje": hoje}))
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUNAS))}{ws.max_row}"

    # -------------------------------------------------------- Organograma ---
    ap = wb.create_sheet(_t("Organograma")[:31], 0)
    larguras = (13, 42, 34, 26, 30, 9, 9, 9, 13)
    for i, w in enumerate(larguras, start=1):
        ap.column_dimensions[get_column_letter(i)].width = w

    # O cabeçalho: marca ancorada em A1, título e tenant ao lado, e a legenda
    # do desenho na linha de baixo. As duas primeiras linhas crescem para a
    # imagem caber sem empurrar dado; a quarta é o respiro antes da tabela.
    for linha, altura in ((1, 26), (2, 20), (3, 15), (4, 8)):
        ap.row_dimensions[linha].height = altura
    if marca is not None and Path(marca).exists():
        try:
            from openpyxl.drawing.image import Image

            img = Image(str(marca))
            # 2203x397 no arquivo; 190 px de largura mantém a proporção e cabe
            # nas duas linhas reservadas (~64 px) sem esticar.
            img.width, img.height = 190, round(190 * img.height / img.width)
            ap.add_image(img, "A1")
        except Exception:
            # Marca é enfeite: planilha sem logo continua servindo. Falhar a
            # exportação inteira por causa de um PNG seria trocar o dado pelo
            # ornamento.
            pass

    ap["C1"] = titulo
    ap["C1"].font = Font(bold=True, size=15, color=PALETA["grafite"])
    ap["C2"] = tenant
    ap["C2"].font = Font(size=11, color=PALETA["cinza"])
    # A legenda inteira numa linha só, mesclada: é a mesma frase que o PDF
    # imprime, e é ela que diz que havia filtro ligado. Sem isso o arquivo
    # recortado sai indistinguível do inteiro assim que deixa o sistema.
    #
    # A contagem e o escopo só entram quando há recorte. Com o desenho inteiro
    # eles repetiriam o que o subtítulo já disse, e legenda que se repete é a
    # que ninguém termina de ler.
    legenda = [subtitulo]
    if ids is not None or recorte:
        legenda += [_t("{n} pessoa(s)", n=len(saem)),
                    _t("Recorte: {escopo}",
                       escopo=recorte or _t("organograma inteiro"))]
    ap["A3"] = " · ".join(x for x in legenda if x)
    ap["A3"].font = Font(size=10, color=PALETA["cinza"])
    ap.merge_cells("A3:I3")

    cabecalho = [_t("Código"), _t("Unidade / pessoa"), _t("Cargo"),
                 _t("Departamento"), _t("E-mail"), "N2", "N3", "N4",
                 _t("Sub.")]
    linha_cab = 5
    for i, texto in enumerate(cabecalho, start=1):
        ap.cell(row=linha_cab, column=i, value=texto)
    borda = Side(style="thin", color=PALETA["cinza-claro"])
    for i in range(1, len(cabecalho) + 1):
        c = ap.cell(row=linha_cab, column=i)
        c.font = Font(bold=True, size=9, color=PALETA["papel"])
        c.fill = PatternFill("solid", fgColor=PALETA["grafite"])
        c.alignment = Alignment(vertical="center")
    # Por referência, não por `ap.cell(...)`: pedir a célula ao openpyxl a
    # materializa e empurra o cursor do `append`, e nasceria uma linha vazia
    # entre o cabeçalho e a primeira faixa.
    ap.freeze_panes = f"A{linha_cab + 1}"

    # Uma faixa por nível, na cor do nível, e as pessoas daquele nível abaixo
    # dela. A ordem é a do cadastro de níveis — a mesma régua que colore a fita
    # do card e a legenda da tabela.
    por_nivel: dict[str, list[Unidade]] = {}
    for u in saem:
        por_nivel.setdefault(u.tipo, []).append(u)
    ordem = [n["codigo"] for n in (niveis or []) if n["codigo"] in por_nivel]
    ordem += [t for t in por_nivel if t not in ordem]

    for tipo in ordem:
        gente = por_nivel[tipo]
        nome_da_cor = cores.get(tipo, "cinza")
        # Rótulo de nível é editável em Configurações, então pode ser qualquer
        # texto: `traduzir` devolve o próprio quando não conhece a chave.
        ap.append([f"{_t(rotulos.get(tipo, tipo))} — {len(gente)}"])
        faixa = ap.max_row
        ap.merge_cells(start_row=faixa, start_column=1,
                       end_row=faixa, end_column=len(cabecalho))
        c = ap.cell(row=faixa, column=1)
        c.font = Font(bold=True, size=10,
                      color=PALETA["grafite"] if nome_da_cor in NIVEL_CLARO
                      else PALETA["papel"])
        c.fill = PatternFill("solid",
                             fgColor=PALETA.get(nome_da_cor, PALETA["cinza"]))
        c.alignment = Alignment(vertical="center", indent=1)
        ap.row_dimensions[faixa].height = 18

        for u in gente:
            pai = unidades.get(u.parent_id) if u.parent_id else None
            ap.append([u.codigo, u.nome, u.cargo, u.area, u.email, u.vertical,
                       centros.n3_de(u.centro_custo), u.centro_custo,
                       len(filhos.get(u.id, []))])
            r = ap.max_row
            d = prof.get(u.id, 0)
            # Recuo por profundidade: a coluna do nome diz a que altura da
            # árvore aquela pessoa está, sem precisar de uma coluna a mais.
            ap.cell(row=r, column=2).alignment = Alignment(indent=min(d, 15))
            # Agrupamento nativo do Excel: o que dobra é o nível, não o ramo.
            # A faixa fica no nível 0 e os seus no nível 1, então o `−` da
            # margem fecha "Célula" inteira e sobra a leitura de cima. Recuar o
            # `outlineLevel` por profundidade seria tentador, mas as pessoas
            # aqui estão ordenadas por nível e não por ramo: o `−` dobraria um
            # trecho que não corresponde a galho nenhum.
            ap.row_dimensions[r].outlineLevel = 1
            for i in range(1, len(cabecalho) + 1):
                cel = ap.cell(row=r, column=i)
                cel.border = Border(bottom=borda)
                if i in (1, 6, 7, 8):
                    cel.font = Font(size=9, color=PALETA["cinza"])
                    cel.alignment = Alignment(horizontal="left")
                elif i == 9:
                    cel.alignment = Alignment(horizontal="center")

    # A faixa é o resumo do grupo e vem antes dele — sem isto o Excel procura o
    # total embaixo e desenha o colchete de cabeça para baixo. E a profundidade
    # anunciada é o que faz a calha do `−` aparecer na margem: sem ela o
    # agrupamento existe no arquivo e não existe na tela de quem abriu.
    ap.sheet_properties.outlinePr.summaryBelow = False
    ap.sheet_format.outlineLevelRow = 1
    # Sem autofiltro aqui de propósito: as faixas são células mescladas e vazias
    # nas colunas de dado, então qualquer filtro as esconderia junto — a
    # planilha perderia exatamente os rótulos que a organizam. Quem quiser
    # filtrar tem a aba ORG, que é plana.

    # ------------------------------------------------------ como preencher ---
    guia = wb.create_sheet(_t("como preencher")[:31])
    for linha in [
        [_t("GPlanSiS|Peoples — estrutura exportada")],
        [],
        [_t("Recorte"), recorte or _t("organograma inteiro")],
        [_t("Linhas"), len(saem)],
        [],
        [_t("A aba ORG volta pela carga assistida, em Configurações › Carga de "
            "dados: as colunas são exatamente as que o leitor espera. A aba "
            "Organograma é leitura — o que se editar nela não é lido de volta.")],
        [_t("Coluna que você apagar do arquivo não é lida: dá para devolver "
            "só as colunas que quer atualizar. A coluna Accountabilities "
            "carrega as próprias; as delegadas o sistema deriva das equipes "
            "dos reportes diretos a cada carga.")],
        [_t("Atenção: se este arquivo saiu com filtro, quem ficou de fora "
            "aparece como ausente na planilha ao reimportar. A opção de "
            "remover ausentes nasce desmarcada, mas confira o passo 2.")],
    ]:
        guia.append(linha)
    guia.column_dimensions["A"].width = 22
    guia.column_dimensions["B"].width = 92
    for linha in guia.iter_rows():
        for c in linha:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    guia["A1"].font = Font(bold=True, size=13, color=PALETA["grafite"])

    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


def _profundidades(unidades: dict[str, Unidade]) -> dict[str, int]:
    """Profundidade de cada nó. Local para o exportador não arrastar mais uma
    importação do domínio só por uma travessia de sete linhas."""
    filhos = mapa_filhos(unidades)
    prof: dict[str, int] = {}
    pilha = [(raiz(unidades), 0)]
    while pilha:
        u, d = pilha.pop()
        prof[u.id] = d
        for f in filhos.get(u.id, []):
            pilha.append((f, d + 1))
    return prof


def main() -> None:
    p = argparse.ArgumentParser(description="Carga do organograma")
    p.add_argument("--spec", action="store_true",
                   help="usa o seed de referência da SPEC em vez da planilha")
    p.add_argument("--saida", type=Path, default=ARQUIVO_ESTADO)
    args = p.parse_args()

    estado = gerar(spec=args.spec)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(estado, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    relato = estado["eventos"][0]["payload"]
    print(f"gravado: {args.saida}")
    print(f"unidades: {len(estado['unidades'])}")
    for k, v in relato.items():
        print(f"  {k}: {v if not isinstance(v, list) else ', '.join(map(str, v))}")


if __name__ == "__main__":
    main()
