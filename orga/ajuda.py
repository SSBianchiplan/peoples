"""
GPlanSiS|Peoples — o passo a passo de boas-vindas.

A MarIA entra pela direita, na base da tela, e leva a pessoa por cada controle
do canvas dizendo o que ele faz. Depois disso ela some, e o sistema é o sistema.

**Os passos vivem aqui, e não no JavaScript.** Dois motivos, ambos práticos:

- Texto de interface passa pelo catálogo de idiomas (`idiomas.py`), e a varredura
  que garante isso lê os módulos do servidor. Passo escrito em JS não seria
  varrido, e um passo novo apareceria em português no meio da tela em inglês sem
  que nada acusasse.
- O passo aponta para um elemento que pode não existir: `.niveis` some abaixo de
  680 px, `Refazer` nasce desabilitado, a gaveta pode estar recolhida. Quem sabe
  o que está desenhado é o servidor — mas quem sabe o que está **na tela** é o
  cliente, então a regra é simples e fica de um lado só: passo cujo alvo não
  existe é pulado, sem buraco na contagem.

O alvo é um seletor CSS. Ele é contrato com o template: se alguém renomear
`#btExportar`, o passo some em silêncio — por isso há teste que abre a página e
confere que todos os alvos existem nela.
"""
from __future__ import annotations

# (alvo, título, texto, lado preferido do balão)
#
# A ordem é a da leitura, não a do DOM: primeiro o que se vê, depois o que se
# faz, e por último onde se guarda. Alguém que siga até o fim sabe operar o
# sistema; alguém que pare no meio já aprendeu a parte que usa todo dia.
PASSOS: tuple[tuple[str, str, str, str], ...] = (
    ("#canvas .no.raiz",
     "O organograma, de cabeça para baixo",
     "A liderança fica na base e os times liderados, acima. Não é enfeite: quem "
     "sustenta aparece embaixo, e a leitura sobe de quem decide para quem "
     "executa. Cada card é uma posição ocupada por uma pessoa.",
     "direita"),
    ("#canvas .alca",
     "A alça abre e dobra o galho",
     "O `+n` diz quantas pessoas estão escondidas atrás daquele card. Clicar "
     "abre; o `−` dobra de volta. O que está dobrado continua contando no "
     "cabeçalho do desenho — some da tela, não da conta.",
     "direita"),
    (".ferramentas .bt.forte",
     "Criar uma unidade",
     "Cria um subordinado direto da raiz da vista. Toda criação entra no "
     "histórico e pode ser desfeita.",
     "baixo"),
    ("#btOrientacao",
     "Como este desenho é lido",
     "As duas pirâmides discutem de que lado fica a liderança. A **Lateral** "
     "troca o eixo: a raiz à esquerda, cada nível uma coluna para a direita, a "
     "leitura descendo. É vinte vezes mais estreita — e é a vista que se lê no "
     "celular.",
     "baixo"),
    ("#btAgrupamento",
     "Por pessoa, ou por equipe",
     "Recolhe as pessoas dentro do seu time e desenha só a estrutura. Com 267 "
     "cards, \"como a empresa é organizada\" se perde no meio de \"quem é "
     "quem\"; aqui ficam 81 caixas. Equipe é desenho derivado: não se edita.",
     "baixo"),
    ("#hist",
     "Desfazer e refazer",
     "Toda mutação marca um ponto. Os dois nascem desabilitados quando não há "
     "pilha — botão que parece clicável e responde \"nada a desfazer\" ensina a "
     "desconfiar da tela. Editar limpa o futuro.",
     "baixo"),
    ("#btExportar",
     "Levar para fora",
     "PDF A3, XLSX, SVG, CSV e JSON. **Sai o que está na tela**: filtro, colapso, "
     "foco e orientação valem para o arquivo. O XLSX é o único que volta — traz "
     "uma aba com as colunas que a carga assistida lê de novo. O percentual ao "
     "lado é a escala com que o desenho cabe na folha: abaixo de 38 % o texto sai "
     "ilegível, e o botão avisa antes do download, não depois.",
     "baixo"),
    ("#filtros input[type=search]",
     "Busca livre",
     "Procura em nome, cargo, e-mail, código, centro de custo e "
     "accountabilities ao mesmo tempo. Ignora acento.",
     "baixo"),
    ("#chips",
     "Oito critérios, e eles se filtram",
     "Cada chip oferece o que ainda existe **depois do recorte que os outros "
     "fizeram**: escolhida a vertical F&B, o centro de custo passa de 78 para 9. "
     "Opção que sempre devolveria vazio não é escolha, é armadilha. Combinam em "
     "E lógico.",
     "baixo"),
    ("#filtrosAtivos",
     "O que está filtrando agora",
     "Cada valor marcado vira uma pílula, e some no clique. A contagem no chip "
     "diz \"3 centros de custo\" e não diz **quais** — a pílula diz, e deixa "
     "tirar um sem descartar os outros dois.",
     "baixo"),
    ("#niveis",
     "Recorte por profundidade",
     "Mostra só os níveis marcados. Seleção múltipla, porque \"como estão a "
     "diretoria e a coordenação, sem o meio do caminho\" só tem resposta com mais "
     "de um nível ao mesmo tempo. O marcado ganha destaque âmbar; o caminho até "
     "ele fica esmaecido.",
     "baixo"),
    (".arvore-acoes",
     "Abrir e dobrar a árvore",
     "Chevron simples desce um degrau de cada vez; chevron duplo vai ao extremo. "
     "O passo a passo existe porque abrir 267 cards de um golpe responde a "
     "pergunta errada — quem desce nível a nível está lendo a estrutura.",
     "baixo"),
    (".canto .zoom",
     "Enquadrar",
     "`⊙` ajusta à tela, `↔` ajusta à largura, e o percentual abre presets. A "
     "roda do mouse dá zoom **ancorado no cursor**: o que está sob o ponteiro "
     "continua sob o ponteiro. Duplo clique no fundo reenquadra.",
     "direita"),
    ("#painel",
     "A gaveta",
     "Clicar num card abre aqui a ficha inteira, e é daqui que se edita. Ela "
     "grava a partir de qualquer vista e devolve a lista de onde você veio. A "
     "tecla `B` recolhe e expande.",
     "esquerda"),
    ("#btMaria",
     "A assistente MarIA",
     "A assistente lê e analisa a estrutura no **seu** recorte — nunca mais do "
     "que você pode ver. Ela informa e sugere; não altera dados. Cada resposta "
     "vira registro com quem perguntou, em que recorte e quanto custou.",
     "esquerda"),
    ("#btAvatar",
     "Você, e as ferramentas de apoio",
     "Quem está logado, o perfil vigente, o tema e a saída — e também o "
     "**manual**, as **boas-vindas** e o **idioma**, reunidos aqui no lugar da "
     "pessoa, para o cabeçalho ficar só com as vistas. O perfil decide o que você "
     "pode editar: visualizador não muta nada, editor fica confinado à sua "
     "subárvore.",
     "esquerda"),
    ("nav[role=tablist]",
     "As outras vistas",
     "**Estrutura** é a leitura de negócio em funil. **Tabela** é a mesma árvore "
     "em ordem lógica — e o colapso é o mesmo estado do canvas: dobrar aqui dobra "
     "lá. **Configurações** guarda cargos, centros de custo, carga de dados e "
     "permissões.",
     "baixo"),
    ("#palco",
     "Botão direito, nos dois lugares",
     "No card, o que se faz com **aquela pessoa**: editar, mover, promover, "
     "excluir. No vazio, o que se faz com **este desenho**: enquadrar, abrir "
     "níveis, trocar a leitura, sair do foco, limpar filtros. Duas perguntas "
     "diferentes, dois menus.",
     "direita"),
)


def passos() -> tuple[dict, ...]:
    """Os passos como dicionários, para o template não indexar tupla."""
    return tuple({"alvo": a, "titulo": t, "texto": x, "lado": l}
                 for a, t, x, l in PASSOS)
