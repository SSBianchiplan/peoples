# GPlanSiS|Peoples — decisões de projeto (documento técnico)

> Este é o documento técnico original do projeto: explica **por que** cada parte
> é como é. A porta de entrada do repositório é o [README da raiz](../README.md).
> Os números citados aqui (contagens, larguras, avisos) vêm de verificações
> feitas sobre a base de trabalho do projeto, que **não** acompanha o repositório
> público — clone e gere a base de demonstração fictícia conforme o README.
> Caminhos relativos neste arquivo partem da raiz do repositório.

Módulo de **Gestão Organizacional, Performance e Talentos** do hub
[gplansis.com](https://gplansis.com) — em produção em `peoples.gplansis.com`
(ver [deploy/README.md](deploy/README.md)). Implementação da
**SPEC-GPLANSIS-ORG-001 v1.1.0** (ondas W5' e W9), desenvolvida sobre uma base de
**demonstração fictícia** (cerca de 270 colaboradores, 60 equipes, 16
verticais de centro de custo, profundidade 5). O repositório público não traz
essa base; traz o gerador do organograma de **teste** (5 níveis, 28 pessoas
fictícias), para treinar e demonstrar.

Liderança na **base**, times liderados **acima** — e, quando a pergunta muda, a
mesma árvore **indentada para a direita**. Canvas clicável e editável, gaveta
lateral recolhível, tooltip de leitura, filtros que **se filtram uns aos outros**,
tabela colapsável por nível, módulo gerenciador com permissões e carga assistida,
trilha de auditoria hash-encadeada, exportação em **PDF A3 paisagem vetorial** e um
ciclo de planilha que **volta**: o XLSX exportado é o mesmo que a carga assistida lê.

Sobre o organograma, uma suíte de **Gestão de Talentos** no mesmo desenho —
derivar da estrutura, camada editável, espelho durável em Postgres, ficha em modal
e os três idiomas: **Skills** (descrição de cargo, GEP-FOR-003), **Conversa de Valor** (conversas de
desenvolvimento em três ciclos, com PDI e valores GPlanSiS), **Avaliação** (9-box
de risco × impacto, prontidão de sucessão e o Comitê de Meritocracia) e **Peoples Place
to Work** (pesquisa de clima anônima — o Peoples Trust Index, cinco pilares, piso de 5
respondentes) e **One-on-One** (1:1/FUP, rocks e issues do EOS, PRM com alertas de
burnout e missões que viram tarefas do GPlanSiS|OS — tudo com sigilo por pessoa, LGPD). O
**Painel RH** resume os indicadores de gente num dashboard clicável. A assistente
**MarIA** lê a estrutura no recorte de quem pergunta,
guia o passo a passo e recebe quem entra pelo nome.

Roda em celular sem virar outro produto: mesmo servidor, mesmas rotas, mesmo
desenho — o que muda é a forma de alcançá-lo.

---

## Executar

```bash
pip install -r requirements.txt
uvicorn orga.main:app --reload --port 8080
# http://localhost:8080          ·  /?vista=tabela  /?vista=configuracoes
# http://localhost:8080/panorama ·  manual de uso (botão "Manual" na barra)
```

Ou em contêiner:

```bash
docker compose up --build       # http://localhost:8080
```

Para levar ao ar — CI/CD, o servidor de produção, deploy por botão ou por tag,
e a federação com o Google Cloud —, veja [deploy/README.md](deploy/README.md).

### No servidor: a imagem vem do registry, não do código

Cada merge na `main` faz o CI rodar a suíte e o portão dos três idiomas e, só
então, publicar a imagem em `ghcr.io/gplansis/peoples`. O servidor
consome esse artefato — o que roda em produção é exatamente o que passou nos
testes, e não uma compilação feita na máquina que serve o organograma.

Se o pacote for privado, o servidor precisa de credencial com
escopo `read:packages` uma única vez:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u <usuario> --password-stdin
docker compose pull             # traz a versão publicada
docker compose up -d
```

**O `pull` não é opcional.** O compose declara `image:` e `build:` juntos, para
que a mesma receita sirva à mesa de quem desenvolve. A consequência é que um
`docker compose up` sem o `pull` **constrói do código-fonte** que estiver no
servidor — e o `schema.sql` entra por bind mount, então esse código está lá. O
sistema sobe, ninguém vê erro, e o que está no ar deixou de ser o artefato
testado.

Em produção, fixe a versão. `ORG_TAG` vazio segue a `latest`, que anda sozinha
no próximo merge; cada publicação também sai etiquetada como `sha-<commit>`, e é
esse número que permite voltar atrás depois de um deploy ruim sem adivinhar para
onde voltar:

```bash
ORG_TAG=sha-7b48f78bfa604a15d1cfb94786cddda473967b92   # no .env do servidor
```

Uma etapa só no `Dockerfile`: não há build de front para separar em
multi-stage — o htmx está vendorizado, não existe transpilação, e o SVG é
montado pelo servidor. `slim` e não `alpine` porque pillow e as rodas de
`uvicorn[standard]` têm binário pronto para glibc; em musl o mesmo
`pip install` compila do zero e a imagem cresce mais do que a base economiza.

**Um worker, e é decisão.** O estado vive em memória e é gravado num arquivo;
dois workers seriam dois estados divergentes escrevendo no mesmo `estado.json`,
e o último a gravar apagaria o trabalho do outro. Escalar isto pede o Postgres
do `schema.sql` primeiro — está desenhado, não está ligado.

`dados/` entra por **volume**, nunca por camada de imagem: uma imagem com estado
dentro serve o organograma de ontem e ninguém percebe. A planilha entra somente
leitura, e `.env` é opcional — sem ele o sistema sobe aberto em localhost, que é
o modo de trabalho de mesa. O healthcheck bate em `/api/v1/organograma` e não na
raiz: a raiz devolve 200 mesmo com o estado vazio, e um healthcheck que passa com
o sistema sem dado não está checando nada.

Sem CDN: o htmx 2.0.4 está vendorizado em `vendor/`. Roda em rede fechada.
Sem passo de build, sem framework de front, sem serviço externo para gerar PDF.

```bash
pytest -q                       # 799 testes
python -m orga.importador          # recarrega dados/estado.json a partir da planilha
python -m orga.importador --spec   # carrega o seed de referência da SPEC §13 (RH)
```

---

## O que aparece no card

A planilha é *person-centric*: cada linha é um colaborador e a hierarquia vem da
coluna **Gestor Direto**. Cada nó do canvas é, portanto, uma posição ocupada por
uma pessoa.

```
┌──────────────────────────────┐
│ ORG-0009   80.01             │  código da unidade · centro de custo (N4)
│ Antônio Braga Soares          │  pessoa
│ Gerente de Operações         │  cargo
│ Engineering                  │  departamento
│ ────────────────────────     │
│ ○ Managers Team              │  accountability delegada (marcador vazado, itálico)
│ ● Planejamento de capacidade │  accountability própria (marcador sólido)
│ ────────────────────────     │
│ SCADA · CLP · Gestão de time │  competências
└──────────────────────────────┘
```

A faixa superior é colorida pelo **nível hierárquico**, configurável em
Configurações → Cargos e níveis. A cor nunca é o único canal: o nível também está
no rótulo ARIA e na vista de tabela (WCAG 1.4.1 / A11Y-06).

## Operação

| Gesto | Efeito |
|---|---|
| **Roda do mouse** | zoom **ancorado no cursor** — o que está sob o ponteiro continua sob o ponteiro |
| `Shift` + roda | desliza na horizontal (o gesto que um desenho muito mais largo que alto pede) |
| **Duplo clique** no card | foca a subárvore · no fundo, reenquadra |
| Arrastar o fundo, ou botão do meio | pan · dois dedos em touch: pinça e arraste |
| Clique no card ou na linha da tabela | abre a **gaveta** de edição (e a expande se estiver recolhida) |
| Passar o mouse no card | **tooltip** com pessoa, cargo, time, CC, e-mail e accountabilities |
| **Botão direito no card** | editar, adicionar subordinado, duplicar, colapsar, focar, mover ←/→, promover, rebaixar, excluir |
| **Botão direito no vazio** | ações do **desenho** — enquadrar, abrir e dobrar níveis, virar a pirâmide, lateral, por equipe, sair do foco, limpar filtros, criar na raiz |
| Alça `+n` / `−` no card | colapsa ou expande a subárvore |
| Alça `‹` na borda da gaveta, ou tecla `B` | recolhe e expande a gaveta |
| Controle de zoom | `⊙` ajustar · `−` `+` · percentual com presets de 50 % a 200 % · `↔` ajustar à largura |
| Teclado | `+` `−` `0` zoom · setas caminham entre cards na direção **visual** · `Enter` abre a gaveta · `Esc` fecha menu e popovers |

O canvas escreve **um `transform` por quadro** (`requestAnimationFrame`): arrastar
267 cards não sobrevive a um layout por evento de `mousemove`. O reenquadramento
automático só age enquanto ninguém tocou no zoom — depois disso, redimensionar a
janela não apaga a navegação de quem estava lendo.

Na caixa de accountabilities, uma por linha. Prefixo `>` marca escopo **delegado** —
aquilo por que a unidade responde mas quem executa é um subordinado.

**Desfazer e refazer** são ícones na barra, e nascem desabilitados quando não há
pilha (INT-03): botão que parece clicável e responde "nada a desfazer" ensina a
desconfiar da tela. Editar limpa o futuro — refazer só existe enquanto ninguém
abandonou aquele caminho. E os dois devolvem **os controles junto com o desenho**:
`adotar` restaura orientação, agrupamento, níveis marcados e filtros, e mandar só
o desenho deixava a barra descrevendo um modo que o servidor já não tinha.

### O helper — a visita guiada

Na primeira vez que alguém entra, a **MarIA acena e entra pela direita, na base
da tela**, e leva a pessoa por cada controle: dezenove passos, um por vez, com o
véu escurecendo tudo menos o que está sendo explicado. Depois ela some, e o
sistema é o sistema.

Liga e desliga em **Configurações → Geral → Helper**, e o botão *Começar a
visita* refaz quando quiser. Ligada por padrão: quem já sabe usar desliga uma
vez e nunca mais vê; quem não sabe não descobre um recurso que nasce desligado.
O custo do padrão errado é assimétrico.

Abre **uma vez por sessão do navegador** — com login exigido, sessão nova é login
novo, que é quando a visita foi pedida. Sem login, recarregar a página no meio do
trabalho não pode reabrir a visita a cada F5. E "Não mostrar de novo" desliga **no
servidor**, não só naquela máquina: a preferência é da pessoa, e ela troca de
navegador.

Três decisões que o código carrega:

**Os passos vivem em `ajuda.py`, não no JavaScript.** Texto de interface passa
pelo catálogo de idiomas, e a varredura que garante isso lê os módulos do
servidor — passo escrito em JS não seria varrido, e apareceria em português no
meio da tela em inglês sem que nada acusasse. Chegam ao cliente já traduzidos e
já formatados, pelo mesmo filtro que a MarIA usa nas respostas.

**Passo cujo alvo não está na tela é pulado.** Não é detalhe: `.niveis` some
abaixo de 680 px, `#filtrosAtivos` só existe com filtro, a gaveta pode estar
recolhida. Apontar para o vazio seria pior que não apontar.

**O véu é uma máscara SVG com um retângulo furado**, e não quatro divs em volta
do alvo: canto arredondado de graça, e uma conta só em vez de quatro que precisam
concordar. Ele intercepta o clique inteiro — durante a visita, a única coisa
clicável é a visita.

Dois dos passos mais importantes nasceram sendo pulados, e a causa foi a mesma
que já tinha aparecido nesta sessão: `#chips` e `#btOrientacao` são
`display:contents`, então **existem e medem zero**. O furo agora cai sobre a
união das caixas dos filhos quando o alvo não tem caixa própria.

### Botão direito no vazio

O menu do card responde *"o que faço com esta pessoa"*. O do fundo responde
*"o que faço com este desenho"* — e essa pergunta só tinha resposta na barra e no
canto, que saem da tela assim que alguém arrasta o organograma para o lado.

Doze ações: enquadrar à tela e à largura; os quatro degraus da árvore; os três
interruptores de leitura; **sair do foco** e **limpar filtros**; e criar unidade na
raiz. Sair do foco só existia na pílula do cabeçalho, que é a saída mais escondida
do sistema.

A habilitação vem pronta do servidor, como no menu do card: com a árvore toda
aberta, *Abrir mais um nível* nasce apagado; sem foco, *Sair do foco* nasce
apagado; na visão por equipe, *Adicionar unidade* nasce apagado — a guarda
recusaria, e botão aceso que responde "ação negada" é a definição de tela em que
não se confia.

### Irmãos-folha empilham de 5 em 5

Uma equipe de 17 pessoas numa fileira só empurra o desenho para 17 larguras de
card. Em pilhas de 5, agrupadas por time, ela ocupa 5 colunas — uma por
departamento. Na base real: **59 038 → 34 934 px**, 41 % mais estreito.

A pilha cresce **para longe do pai**, e a faixa daquele nível engorda para
caber. É isso que mantém a cota sendo uma por nível: nenhum card muda de `N`
por estar empilhado, e o invariante `Y(pai) > Y(filho) + altura(filho)` continua
valendo para o card mais distante da pilha.

**Cada time começa coluna própria.** Uma coluna que mistura Infrastructure com
Cybersecurity não responde "quem faz o quê" — que é justamente a pergunta que o
empilhamento tinha acabado de tornar legível. Time maior que a pilha transborda
para a coluna seguinte e continua sendo o mesmo bloco. A ordem dos times é a da
**primeira aparição na árvore**, e não a alfabética: assim o bloco segue a
hierarquia que `mapa_filhos` já decidiu, e o desenho não se reorganiza sozinho
quando alguém renomeia um time. Custa cerca de 1 300 px no total — 34 934 em vez
de 33 624 — e paga com uma leitura que antes não existia.

**Gerência não empilha, mesmo dobrada.** Um nó dobrado ocupa uma coluna e nada
abaixo dela, então tecnicamente caberia numa pilha. Mas ele é um gestor com
equipe atrás do `+n`, e a fileira é o que mostra quantas frentes a empresa tem
naquele nível. Empilhar gerência esconde exatamente a leitura que aquele nível
existe para dar. Quem empilha é o nível de quem executa.

**Só grupos inteiramente de folhas empilham.** Um filho com subárvore aberta
ocupa um intervalo em X; empilhá-lo faria a subárvore dele colidir com a do
irmão ao lado, e o motor perde a garantia de intervalos disjuntos em que ele
inteiro se apoia. Abaixo de 6 irmãos também não empilha: cinco em fila cabem, e
empilhar ali só cresceria em altura sem ganhar largura.

Cada coluna ganha **um trilho**, e não um fio por card — um fio por card
cruzaria os de baixo. O trilho passa atrás deles, porque LAY-09 desenha conector
antes de card, e o que se vê entre um card e o seguinte é o segmento que sobra.

Os três números são tokens (`pilha_cards`, `pilha_minimo`, `pilha_gap`);
`pilha_cards=0` desliga e o desenho volta a ser uma fileira.

### Níveis, no canto do palco

`N0`…`N5` e `Tudo` abrem a árvore até uma profundidade. É o **mesmo controle da
tabela**, porque o colapso é um estado só: abrir até N2 aqui abre até N2 lá.

Fica sobre o desenho, e não na barra de ferramentas, porque quem procura "abrir
até o nível 2" está olhando o desenho. Mora dentro do palco e **fora do
`#lente`** — deslizar e dar zoom não podem levá-lo junto. E entra na exceção do
arraste (`.no,.alca,.niveis`), senão clicar num botão começaria um pan.

Quantos níveis aparecem sai do **desenho vigente**: por equipe a árvore tem
outra altura, e oferecer um `N` que não existe daria um botão que não muda nada.
O colapso de cada agrupamento é preservado quando se troca de modo — o conjunto
é um só, mas `EQ-…` e `ORG-…` não colidem, e escolher N2 por equipe não apaga o
que estava montado por pessoa.

### Três orientações, e a terceira troca de eixo

As duas pirâmides discutem **de que lado fica a liderança**: invertida (na base) e
convencional (no topo). A **lateral** discute outra coisa — ela troca o eixo. A raiz
fica à esquerda, cada nível recua uma coluna para a direita, e a leitura desce na
ordem lógica. Uma árvore indentada, como a de um explorador de arquivos.

Na base real, com as 267 pessoas abertas:

| | largura × altura |
|---|---|
| pirâmide | **32 576** × 2 630 px |
| lateral | **1 626** × 30 817 px |

Vinte vezes mais estreita — e a largura é `(D+1)` colunas, então **17 ou 170 pessoas
num nível dão a mesma largura**. Nenhuma das pirâmides consegue isso: nelas a
largura é o número de folhas. É a vista que se lê num celular.

O barramento corre na **calha** entre a coluna do pai e a dos filhos — uma faixa de
`gap_h` de largura onde nenhum card jamais cai, porque as colunas são fixas. Por
isso ele pode ser um segmento único (LAY-05) atravessando a subárvore inteira sem
cortar caixa nenhuma. Medido nos 267 cards: **zero sobreposição, zero fio cruzando
card**.

A lateral não empilha. O empilhamento existe para estreitar um desenho deitado, e
aqui o desenho já nasce estreito; empilhar só quebraria a ordem de leitura.

**A cota acompanha.** Os níveis viraram colunas, então o trilho deixou de correr à
esquerda e passou a correr no topo, com `N0`…`N5` centrados sobre cada coluna. Para
isso a geometria da cota passou a sair **pronta do motor** — trilho, ticks, marco e
âncora do texto — e o template e o gerador de PDF desenham o que recebem. Antes cada
um repetia a regra de eixo por conta própria (ADR-011).

O botão fica ao lado de *Invertida* e é **interruptor com estado**: sair da lateral
devolve a pirâmide de onde se veio, e não a invertida por padrão. Quem desenha em
convencional e dá uma olhada na árvore indentada volta para a convencional.

## Por pessoa, ou por equipe

O canvas é *person-centric*: cada nó é uma posição ocupada por alguém. Com 267
cards, a leitura de "como a empresa é organizada" se perde no meio de "quem é
quem". O botão **▢ Por pessoa / ▣ Por equipe**, ao lado da orientação, recolhe
as pessoas dentro do seu time e desenha só a estrutura: **81 caixas no lugar de
267**, e o SVG cai de 59 038 para 15 284 px.

Ele fica ao lado da orientação porque os dois respondem à mesma pergunta: como
este desenho é lido. A orientação diz de que lado fica a liderança; este diz o
que é um nó.

**Não é uma segunda verdade.** Nada é gravado: as equipes são derivadas do mesmo
dicionário de unidades a cada render, e o resultado é um dicionário de `Unidade`
como qualquer outro. Por isso a vista atravessa o motor de layout, o SVG, o PDF
e o CSV sem que nenhum deles saiba que ela existe — quem produz coordenada
continua sendo `dominio.calcular_layout`, e só ele (ADR-011).

Quatro decisões que estão no código, e não neste texto:

**A chave é N3 + Departamento, nunca o nome sozinho.** `Managers Team` existe em
80.20, 81.20, 82.20 e 89.20; `Hardware Design Team`, em quatro verticais.
Agrupar por nome fundiria quatro times num nó só e diria uma inverdade sobre a
empresa. É a mesma chave do cadastro de centros de custo, de propósito.

**O pai de uma equipe é a equipe de quem chefia a âncora** — o membro cujo gestor
está fora do time. Havendo mais de um, vence o mais raso; empatou, decide
(ordem, nome, id), porque duas execuções têm de desenhar igual (RNF-02).

**Ciclo é cortado, não propagado.** Dois times podem chefiar um ao outro por
caminhos diferentes. O laço é quebrado prendendo o time na raiz: um organograma
com ciclo não desenha, e cair de pé mostrando a estrutura vale mais.

**Equipe não se edita.** A guarda mora em `negado()`, que é o funil por onde toda
mutação passa — vinte rotas cobertas de uma vez, e rota nova nasce coberta. O
menu de contexto vem vazio, porque isto não é um caso de permissão.

### A gaveta da equipe

Clicar num time abre a **hierarquia de comando dentro dele**, e não uma lista
alfabética: a indentação é o dado — quem responde a quem naquele departamento.
Quem tem gestor fora do time entra no nível 0, porque do ponto de vista do time
ele é o topo. Clicar num nome **evidencia a pessoa** e abre a linha dela: a quem
responde, quantos respondem a ela, e quais times respondem a ela por fora — que é
justamente o que a visão por equipe esconde de propósito.

### No papel

O PDF sai com o modo no título (`Organograma · por equipe`) e conta o que está
desenhando (`81 equipes · 267 pessoas`): sem isso, quem recebe o arquivo lê 81
caixas e conclui que a empresa tem 81 pessoas.

Colapso e foco valem aqui como valem na visão por pessoa — o mesmo conjunto
serve os dois, porque `EQ-…` nunca colide com `ORG-…`. E é assim que o desenho
cabe na folha: com os 81 times abertos a escala é 7 %, abaixo do piso de leitura
de 38 %; dobrando até N1 ela sobe a 100 %.

| expandir até | caixas | largura | escala A3 |
|---|---|---|---|
| N1 | 5 | 1 136 px | **100 %** |
| N2 | 21 | 4 542 px | 25 % |
| N3 | 63 | 12 926 px | 9 % |
| N4 | 81 | 15 284 px | 7 % |

## Filtros

A mesma barra serve canvas e tabela: **busca livre** mais seis critérios em
**popover de seleção múltipla** — vertical de negócio, natureza do CC, centro de
custo, departamento, cargo, gestor e nível. Cada chip mostra a contagem do que está marcado e ganha uma
**borracha** ao lado, que apaga aquele critério sem abrir o popover; no fim da
barra, *Limpar tudo*. Popovers de lista longa (78 centros de custo, 60 times)
trazem busca interna, que ignora acento como a busca do servidor.

Chip em vez de caixa de rolagem porque 78 opções não cabem numa barra, e a
contagem no chip diz o que está filtrado sem ocupar espaço. Todos os domínios
saem do dado, nunca de lista fixa — CC que não existe não aparece, CC novo aparece
sozinho. Combinam em E lógico.

O centro de custo aparece **com o nome da equipe**: `83.42 · Software Team`. O código
sozinho só diz alguma coisa a quem decorou os 78, e o nome também faz a busca
interna do popover achar por `cyber` sem saber o número. O nome sai da própria
pessoa (`area`), não do cadastro de CC: ao casar só pelo N3, o cadastro devolve o
nome de uma equipe irmã e o rótulo mentiria. Oito N4 abrigam mais de um
departamento (`81.11 · Account Managers, Pre-Engineering`) e aparecem os dois —
mostrar só um prometeria um recorte menor do que o filtro entrega.

### Os filtros se filtram

Cada chip oferece **o que ainda existe depois do recorte que os outros fizeram**.
Opção que sempre devolveria vazio não é escolha, é armadilha.

| | sem filtro | `Vertical = F&B` | `+ CC 82.43` |
|---|---|---|---|
| pessoas | 267 | 45 | 8 |
| centro de custo | 78 | **9** (todos 82.*) | 9 |
| departamento | 61 | **10** | **1** |
| cargo | 119 | 19 | 6 |
| gestor | 42 | 7 | 1 |
| natureza | 3 | **1** | 1 |
| vínculo | 2 | **1** | 1 |

Duas regras que precisavam ficar explícitas:

- **Nenhum chip se filtra por si mesmo.** Por isso o CC continua oferecendo os 9
  mesmo com um marcado — filtrado por si, a primeira marca apagaria as outras
  opções e ninguém conseguiria marcar a segunda.
- **O que está marcado sobrevive sempre**, mesmo quando a combinação não devolve
  ninguém. Se a marca sumisse da lista, não haveria como desmarcá-la e a pessoa
  ficaria presa num recorte vazio.

Chip cujo domínio esvaziou nasce **desabilitado**, com o motivo no `title`
(*"Nenhum gestor sobrou no recorte atual"*). Popover que abre vazio já foi defeito
relatado aqui uma vez; a diferença é que agora o vazio tem causa, e a causa cabe
numa frase.

Os chips voltam **fora de banda** a cada filtragem. Domínio que estreita no servidor
e não estreita na tela é pior do que não estreitar — a lista continuaria oferecendo
o que já não devolve ninguém. O campo de busca fica de fora do swap: ele guarda o
cursor de quem digita. E o popover aberto atravessa a troca com o termo buscado e a
rolagem intactos, porque o chip aberto é justamente o único cuja lista não pode ter
mudado.

### As pílulas do recorte

Uma tira abaixo da barra, que só existe quando há filtro:

```
FILTRANDO POR   [ VERTICAL  F&B ⊗ ]   [ CENTRO DE CUSTO  82.43 · Software Team 3 ⊗ ]
```

Cada pílula é um par (critério, valor) e some no clique. A contagem no chip diz
*"3 centros de custo"* e não diz **quais** — para saber era preciso abrir o popover
e caçar as marcas no meio de 78 linhas. E tirar um só era pior: a borracha apaga o
critério inteiro, então quem queria descartar um CC de três descartava os três e
remarcava dois.

O rótulo é o mesmo que o popover mostra, porque a pílula é onde se lê o recorte sem
abrir nada. O valor viaja em `data-valor`, e não montado dentro do `onclick`:
`Gestão de TIC's` tem apóstrofo, e montar chamada JS em atributo é o caminho mais
curto para quebrar a tela num nome de departamento.

O filtro por **gestor é hierárquico**: casa a unidade e toda a subárvore dela, que é
como se lê "quem responde ao fulano".

Nós que só sustentam o caminho até um achado ficam esmaecidos (`passagem`); os
achados ganham contorno âmbar. O filtro abre os caminhos colapsados **sem alterar o
colapso guardado** — ao limpar, a vista volta como estava. Filtro ativo vale também
para o CSV, o XLSX, o SVG e o PDF exportados: sai o que está na tela.

## Vistas

- **Canvas** — o twin editável.
- **Estrutura** — a leitura de negócio (abaixo).
- **Tabela** — a mesma árvore em ordem lógica raiz → folhas, colapsável por nível
  (`N0`…`N5`, `Tudo`) e por linha. **O colapso é o mesmo estado do canvas**: dobrar
  aqui dobra lá. Duas representações da mesma verdade, não duas verdades. A barra
  traz **Exportar XLSX** e **Importar XLSX** lado a lado, porque é um ciclo só; o
  importar não abre assistente próprio — manda o arquivo para a mesma rota dos três
  passos de *Configurações › Carga de dados* e leva a pessoa para lá, já no passo 2.
  **Colunas** abre as dezessete disponíveis para marcar, e o botão diz quantas
  estão ligadas — o número é o que explica por que a tabela de ontem tinha mais
  campos. A escolha vai para `config.colunas_tabela` e sobrevive ao recarregar;
  quem trabalha com centro de custo o dia inteiro não deve remarcar as mesmas
  caixas toda manhã. O CSV e o XLSX saem com **as colunas que estão na tela**.
  A legenda de níveis abaixo da barra **filtra**: cada cor é um botão que liga
  e desliga aquele nível no chip *Nível* — não há segundo caminho de filtragem,
  é a mesma caixa e o mesmo formulário.
- **Grade editável** — o botão **Editar** liga a edição em célula sobre a
  mesma tabela (abaixo).
- **Painel RH** — o painel de RH/DP: oito KPIs, a rosca de vínculo e a curva de
  crescimento, distribuições por tempo de casa, nível, departamento e vertical —
  tudo clicável, abrindo a lista das pessoas da fatia. Fecha com contratações,
  desligamentos (o status que o RH declara, não o logout) e inativos, mais o
  vínculo N5↔centro de custo e a exportação Excel de tudo. Fonte única da tela e
  da planilha; respeita o recorte de leitura por papel.
- **One-on-One** — 1:1 (FUP) e desenvolvimento por pessoa: agenda de cadência,
  rocks e issues (IDS) do trimestre, objetivo do trimestre e carreira (puxada do
  Conversa de Valor e da Avaliação), o PRM (pulso, clima médio, alertas de burnout e
  ciclo de vida) e as missões que vêm do PDI da Conversa de Valor e se exportam como tarefas do
  GPlanSiS|OS. **Sigilo por pessoa** (LGPD): cada registro é só dos dois participantes
  — o liderado e o líder que o escreveu — ou do RH; a cadeia acima não vê.
- **Tempo de empresa** — a única leitura que fala do passado: distribuição por
  faixa de tempo de casa, média e mediana por vínculo, nível e departamento, o
  ano de entrada de quem está hoje, e as equipes com a casa mais nova. Respeita
  o filtro: filtrou F&B, os números são de F&B. Nada é gravado — a admissão é o
  fato e o resto é aritmética refeita a cada render, porque um tempo de casa
  gravado hoje mente amanhã.
- **Auditoria** — ledger append-only com verificação da cadeia SHA-256.
- **Configurações** — o módulo gerenciador (abaixo).

Cada vista tem link próprio: `/?vista=tabela`, `/?vista=configuracoes&aba=cc`.

A gaveta de edição abre nas três primeiras e **grava a partir de qualquer uma**.
Isso não é acidental: o htmx resolve `hx-target` *antes* de despachar, então
apontar o formulário para `#canvas` a partir da tabela não dava erro nenhum —
fazia a edição não sair do navegador. O painel escolhe o alvo em tempo de render
e devolve a lista da tela de origem fora de banda (`testes/test_app.py::
test_INT01_a_gaveta_alveja_o_que_existe_na_tela_de_origem`).

## Estrutura — o funil institucional

Transcrição viva da apresentação **Estrutura GPlanSiS|Peoples 2026** (20 lâminas,
960×540). Quatro faixas em estádio, centradas, alargando para cima — as larguras
saem dos retângulos da lâmina: 823, 702, 572 e 451 px de 960.

    Cliente                    ← o topo, o mais largo
    Business Units
    Serviços Compartilhados
    Diretoria Executiva        ← a base, sustentando

É a mesma tese do organograma invertido (LAY-01), dita em linguagem de negócio.
Clicar numa faixa abre suas verticais; clicar numa vertical abre os
departamentos; clicar num departamento lista as pessoas, e cada pessoa abre a
**mesma gaveta** do canvas — a estrutura leva à pessoa, não a uma cópia dela.

**As faixas vêm da lâmina; os membros vêm do cadastro de centros de custo.** Uma
apresentação desatualizada não pode inventar uma vertical que não existe. Onde
os dois discordam, o botão *divergências* mostra o quê:

| Divergência | Leitura |
|---|---|
| `P&M` declarada na apresentação, ausente no cadastro | faixa prevista que não virou centro de custo |
| `PFD`, `OTC`, `PMO` no cadastro sem faixa própria na lâmina | 81 pessoas que a apresentação não nomeia |
| `PMO` é *Business Unit* no cadastro, mas a lâmina põe `PCO` nas áreas administrativas | mesma área, classificação oposta |
| departamentos sem nome em português | inclui erros de digitação reais: `Pulp & Papper`, `Enviroment` |

A apresentação é a estrutura **pretendida**; o cadastro é a **vigente**. O
sistema não escolhe entre as duas — impede que a diferença fique invisível.

O vocabulário em português da lâmina (`Managers Team` → *Gestão*,
`Small Panels` → *Gavetas e Pequenos Painéis*) vive em `estrutura.ROTULO_PT`,
sobre os nomes em inglês do cadastro.

## Módulo gerenciador

| Aba | O que controla |
|---|---|
| **Identidade e vista** | título do organograma (vai ao cabeçalho do SVG e do PDF), selo de tenant, orientação padrão, **tema** (claro, escuro ou seguir o sistema), níveis abertos ao carregar |
| **Card do canvas** | quais dos 10 campos aparecem no card, e os tokens de geometria da SPEC §9.6 (largura, gaps, nº de accountabilities). Vale para canvas, SVG e PDF — os três saem do mesmo motor |
| **Permissões** | perfil vigente (`org.viewer` / `org.editor` / `org.admin`) e unidade de escopo do editor (SEC-03) |
| **Cargos e níveis** | níveis hierárquicos (rótulo, cor, ordem), catálogo de 119 cargos com nível por cargo, e as regras de classificação |
| **Centros de custo** | cadastro de sete colunas (abaixo), reconciliação com a estrutura e exportação CSV |
| **Carga de dados** | assistente de atualização em 3 passos e recarga total |

**Permissões são reais, não decorativas.** Toda rota de mutação passa pela guarda:
`viewer` não altera nada, `editor` só altera dentro da subárvore de escopo, `admin`
é irrestrito e é o único que entra na configuração. A recusa responde 200 com o
canvas intacto e um aviso (INT-06) — nunca um 4xx silencioso. Enquanto a
autenticação OIDC é débito declarado (DT-02), o perfil vigente é escolhido na tela;
trocar isso por um `sub` de JWT é uma linha em `negado()`.

**Carga assistida** (passo 1 enviar → passo 2 conferir → passo 3 aplicar): a planilha
é comparada com a estrutura vigente e o sistema mostra o que é **novo**, o que
**mudou** (campo a campo, incluindo troca de gestor) e quem **sumiu** da planilha.
Nada é escrito antes do passo 3, e cada classe é opcional. O pareamento tem três
degraus — `Código`, o par nome + e-mail, e o nome sozinho — descritos em
[O contrato da planilha](#o-contrato-da-planilha). A carga toca **todos os campos
que a gaveta edita**, e coluna que não veio no arquivo não é tocada: dá para mandar
só as colunas que se quer atualizar. Ciclos declarados na planilha são recusados (RF-02) e a
raiz nunca entra na lista de remoção (RF-03). A operação inteira entra no ledger e é
desfazível. Há também uma planilha-modelo para download, com aba de instruções — e um
teste garante que o modelo que o sistema entrega passa no analisador dele mesmo.

## Cargos e níveis

O **nível** é o que a fita colorida do card codifica e o que o filtro *Nível*
seleciona. Ele nasce do cargo por regra de palavra-chave — "Gerente de Operações"
vira gerência, "Estagiário" vira apoio. Enquanto essa regra viveu dentro do
importador ela era **código**: mudar a leitura de um cargo exigia editar Python e
recarregar a base. Agora é dado, em três camadas da mais específica para a mais
geral:

```
1. catálogo   cargo exato → nível     "Montador Líder" → coordenação
2. regras     padrão → nível          "supervisor"     → coordenação
3. piso       nível padrão                                célula
```

O catálogo nasce da aplicação das regras sobre os cargos que existem na base —
**119 distintos na carga atual**, por isso a tela filtra — e a partir da primeira
edição passa a mandar. Descobrir da estrutura acrescenta o que faltar sem
sobrescrever o que já foi decidido.

**Novo cargo** abre um `<dialog>` nativo — ESC, foco preso e fundo inerte vêm do
navegador, não de JavaScript. O campo lista os cargos existentes num `datalist`,
porque o jeito de criar "Coordenador" ao lado de "Coordenador de Automação" sem
perceber é não ver o que já existe. Duplicata é **recusada**, comparando sem
acento e sem caixa: o catálogo é indexado por `cargos.chave()`, e uma duplicata
silenciosa sumiria na deduplicação do salvar dando a impressão de ter funcionado.
O nível nasce no **piso**, não no primeiro item da lista — o primeiro é diretoria,
e um cargo criado sem querer como diretoria muda a cor de todo card ao aplicar.

**Salvar o catálogo não reclassifica ninguém.** Aplicar às unidades é ação à
parte, com confirmação e desfazível: reescrever o nível de 267 pessoas muda a cor
de todo card e a altura das faixas do desenho, então quem manda isso precisa ter
pedido. A tela relata **divergências** — cargos cujo nível no catálogo não bate
com o que está gravado na unidade, o que aparece quando alguém editou o nível
direto no painel ou quando o catálogo mudou e ninguém aplicou.

Nas regras vale a **primeira que casa**, por isso a ordem é editável: hoje
"Assistente de Gerência" cai em gerência; invertendo a ordem, cai em apoio.
Padrão inválido é descartado em vez de derrubar a tela.

São **sete níveis**: diretoria, gerência, coordenação, **especialista**, célula,
área e apoio. O especialista entrou entre coordenação e célula porque é o que a
estrutura já praticava — treze pessoas com *Especialista* no cargo, em
acionamentos, automação, engenharia elétrica, engenharia de processos,
instrumentação e TI, que a fita vinha pintando de célula.

Cadastrar o nível e a regra **não moveu ninguém**, e a ordem das três camadas é
a explicação: o catálogo responde antes das regras, e aqueles sete cargos já
estavam nele apontando para célula. *Descobrir da estrutura* só acrescenta o que
falta — nunca reclassifica o que está lá, e é isso que impede uma regra nova de
desfazer uma decisão manual antiga. Os treze só mudaram depois de corrigir os
sete cargos **no catálogo** e então aplicar. A camada que ganha é a de sempre; o
que faltava era editar a camada certa.

O **código do nível é imutável** — ele casa com o enum `org.tipo_unidade` do
`schema.sql` e com o `tipo` gravado em cada unidade. Rótulo, cor e ordem são
livres.

A cor é um **token**, não um valor: o tema escuro precisa de contrapartida para
cada uma, e deixar digitar hexadecimal furaria a paleta institucional e o
contraste. No escuro a leitura inverte — o nível mais sênior vira o tom mais
claro, senão o grafite da diretoria some dentro do card (1,1:1). Um teste
verifica que todos os tokens passam em 3:1 sobre o card escuro.

## Centros de custo

A planilha de pessoas traz só o CC de nível 4 (`80.31`). Esse número identifica a
equipe, mas não diz a que **vertical de negócio** ela pertence nem que **natureza**
tem. Isso vive em cadastro próprio, com as sete colunas da tabela de origem:

| LogicalCC | N2 | N3 | Departamento | N5 | Vertical | Tipo |
|---|---|---|---|---|---|---|
| 80 | 80.0 | 80.30 | Process Engineering | PRO | ENG | Bussines Unit |

A chave é o par **N3 + Departamento**: *Managers Team* existe em 80.20, 81.20, 82.20
e 89.20; *Hardware Design Team*, em quatro verticais. Nem o código nem o nome
identificam sozinhos. O N4 não aparece no cadastro porque é derivável — **N3 é o N4
com o último dígito zerado** — e é por essa relação que uma pessoa alcança a sua
vertical.

**A resolução tem degraus e diz qual usou.** Exato (N3+Departamento) → por
departamento → por N3 → sem correspondência. A planilha de pessoas e o cadastro de
CC são mantidos por gente diferente: a primeira escreve *Pulp & Papper*, o segundo
*Pulp & Paper*. Mostrar quantas unidades caíram em cada degrau é o único jeito de
essa divergência aparecer em vez de virar dado silenciosamente errado. Na carga
atual: **261 por casamento exato**, 5 por N3 — divergência de grafia no nome do
departamento — e 1 sem CC (a raiz sintética Board).

A tela relata também **linhas sem uso** (estão no cadastro e ninguém caiu nelas —
equipe desativada, ou divergência de grafia) e **linhas a preencher** (vieram da
estrutura, não da referência). *Descobrir da estrutura* cria as que faltam
herdando vertical e natureza do tronco N2 quando há maioria clara; o N5 fica em
branco de propósito, porque é mnemônico da equipe e não há de onde tirar.

**O pivot fecha essa lacuna pelo caminho inverso.** A planilha nova trouxe o N5
por pessoa; `centros.pivotar` agrupa as pessoas por **N3 + Departamento**, que é
a chave do cadastro, e leva o N5 da gente para a linha:

- **em branco** recebe o valor — é o caso que o pivot existe para resolver;
- **preenchido e divergente** fica como está e vira aviso, porque sobrescrever a
  mão de alguém com o que veio da planilha é perder a correção sem avisar;
- **mais de um N5 para a mesma chave** é recusado inteiro, com os candidatos no
  aviso: escolher o mais frequente seria decidir por maioria uma pergunta que
  não é de maioria.

Sobram hoje **dois avisos** desse terceiro tipo — `82.40 / Software Team` entre
`SCA` e `SRV`, e `83.40 / Software Team` entre `OTC` e `SCA`. São duas equipes
sob a mesma chave, e quem resolve é o dono do dado, não o pivot.

Os rótulos saem como estão na origem, inclusive `Bussines Unit` e `Suport Team`.
São valores que podem precisar casar com outros sistemas — corrigir a grafia é
decisão do dono do dado, e a tela permite.

O cadastro alimenta o filtro **Vertical** (ENG, P&P, F&B… no lugar do 80.0
numérico), o filtro **Natureza**, as colunas N5/Vertical/Natureza da tabela e a
linha de código do card.

## PDF A3 paisagem

`PDF A3` na barra gera o arquivo **no próprio processo**, sem Chromium headless e sem
biblioteca de PDF. O SVG que o motor emite é um subconjunto controlado — retângulos,
linhas, paths só com `M`/`L`, círculos e cinco estilos de texto — o que torna viável
escrever o PDF direto.

O ganho não é evitar dependência: é que **o texto continua texto**. O PDF sai vetorial
e pesquisável (`pdftotext` extrai os nomes — W7-C3) porque usa as 14 fontes base do
PDF com WinAnsiEncoding, que cobre o português sem embutir arquivo de fonte.

Traz logo, título, escopo, data, legenda de tipos e carimbo do ledger.

**Sai sempre em uma folha.** A escala é derivada do próprio desenho — o eixo mais
apertado manda, e a folga que sobra vira margem igual dos dois lados. Desenho pequeno
é ampliado até ocupar a folha (teto de 220 %); desenho largo é reduzido. O
enquadramento é a função pura `pdf.enquadrar()`, coberta por testes que verificam,
para nove proporções diferentes, que o desenho inteiro fica dentro da área útil e
centrado.

Com uma folha só, a escala vira a única variável que decide se o papel fica legível —
então ela aparece **antes do clique**, no rótulo do botão (`PDF A3 · 67 %`), e o botão
fica em alerta abaixo do piso de leitura. Sem isso a exportação seria uma ação cega:
você só descobriria o problema depois de abrir o arquivo. O piso é **um número só**,
`pdf.PISO_LEITURA`, que o servidor injeta no JavaScript da página — é o mesmo limite
que faz o *ajustar à tela* parar de encolher e enquadrar a raiz.

---

## A grade editável

O botão **Editar**, na barra da Tabela, liga a edição em célula. Por baixo está
a **AG Grid Community** (MIT), vendorizada em `web/vendor/` como o htmx — sem
CDN em tempo de execução e sem passo de build.

**Ela se monta por cima da tabela do servidor, não no lugar dela.** Sem
JavaScript, com a biblioteca fora do ar ou com `/grade/dados` em erro, o
`<table>` renderizado continua na tela e a vista funciona como sempre
funcionou. O botão nasce escondido e só aparece quando a grade sobe: sem grade
montada ele prometeria uma edição que não existe.

**A grade é vista, não fonte.** Cada edição vai ao servidor por rota própria
(`/grade/celula`, `/grade/mover`, `/grade/no`), passa pelas mesmas guardas do
painel — permissão, ciclo (RF-02/INV-02), renumeração, ledger, ponto de
desfazer — e a resposta traz a grade inteira de volta. Devolver só a célula
deixaria a linha contando três histórias: mudar o nível repinta o chip, mudar o
centro de custo troca N5, vertical e natureza na mesma linha, e mudar o
departamento pode abrir um provisionamento.

| o que | como |
|---|---|
| **Suspensa** | onde o vocabulário é do sistema: nível, vínculo, situação, centro de custo |
| **Suspensa aberta** | cargo e departamento — sugere o que existe, aceita o que ainda não existe |
| **Derivado** | profundidade, subordinados, tempo de casa, N5, vertical e natureza **não** se editam; a dica da célula diz onde se muda de verdade |
| **Hierarquia** | `Tab` indenta, `Shift+Tab` promove, arrastar a linha reparenta |
| **Botão direito** | gaveta, editar célula, dobrar, indentar/promover, subir/descer, novo filho, duplicar, copiar, CSV, excluir |

Fora do modo Editar, clicar numa linha **abre a gaveta** — o mesmo gesto da
tabela e do card.

**Tree Data e o menu de contexto da AG Grid são Enterprise**, e não foram
usados. A hierarquia não custou nada porque o servidor já entrega as linhas
achatadas em pré-ordem com a profundidade em cada uma — é o mesmo que a tabela
usa para indentar; o menu é código nosso, e sai de um `contextmenu` no
contêiner resolvido pelo atributo `row-id`, que é DOM público e estável.

Os filtros por coluna da AG Grid ficam **desligados**: a vista já tem a barra
de filtros do sistema, que recorta o servidor e alimenta chips, pílulas,
contador e as demais telas. Um segundo filtro, só do cliente e só desta grade,
mostraria dez linhas enquanto o resto do sistema diz duzentas.

Duas armadilhas que o código carrega comentadas, porque custaram tela quebrada:
a AG Grid 32 **injeta a folha de estilo dela em tempo de execução**, depois do
`<style>` da base — com `.orga-grade` sozinha, mesma especificidade de
`.ag-theme-quartz`, quem chegava por último ganhava e a grade saía branca
dentro da página escura; e a marca de "já montei" precisa ser gravada **antes**
do `fetch`, senão `htmx:load` e `DOMContentLoaded` passam juntos pela guarda e
a tela termina com três grades empilhadas.

## XLSX: o único formato que volta

`/export.xlsx` entrega **duas abas com propósitos diferentes**, e a escolha está no
nome delas.

`Organograma` é a que abre: marca no cabeçalho, a legenda do desenho (a mesma que o
PDF imprime, montada num lugar só) e as pessoas em faixas por nível hierárquico —
cada faixa na cor que o cadastro de níveis dá àquele nível, a mesma da fita do card.
As linhas levam **agrupamento nativo** do Excel, então o `−` da margem dobra um nível
inteiro; a coluna do nome recua conforme a profundidade na árvore. O agrupamento é
por *nível*, não por ramo — as pessoas ali estão ordenadas por nível, e dobrar por
profundidade fecharia um trecho que não corresponde a galho nenhum.

`ORG` é a mesma gente nas colunas cruas de `importador.COLUNAS`, cabeçalho na primeira
linha, sem decoração. É ela que fecha o ciclo: exporta, edita fora, devolve pelos três
passos da carga assistida. Funciona porque `ler_planilha` procura a aba `ORG` **pelo
nome** antes de cair na primeira — é essa linha que deixa a apresentação vir na frente
sem quebrar a volta:

```python
ws = wb["ORG"] if "ORG" in wb.sheetnames else wb[wb.sheetnames[0]]
```

---

## O contrato da planilha

`importador.COLUNAS` é a **fonte única**: dela saem a ordem do modelo, o que a leitura
extrai, o que a carga compara e o que a exportação escreve na aba `ORG`. Antes eram
quatro listas paralelas — um `COL` posicional, os títulos, os campos comparáveis e um
`append` literal no exportador. Quatro lugares para lembrar de mexer, e o que
divergisse só apareceria numa carga de produção.

São catorze colunas, e elas cobrem tudo o que a gaveta de edição edita:

| coluna | campo | vazia significa |
|---|---|---|
| `Código` | `codigo` | pareia por e-mail e nome |
| `Colaborador`* | `nome` | linha ignorada |
| `Cargo/Função` | `cargo` | limpa |
| `Nível` | `tipo` | mantém |
| `Vínculo` | `vinculo` | mantém |
| `Departamento` | `area` | limpa |
| `E-mail` | `email` | limpa |
| `N2` | `vertical` | limpa |
| `N3` | — | derivada de N4; sai na exportação, ignorada na carga |
| `N4` | `centro_custo` | limpa |
| `Responsável` | `responsavel` | mantém |
| `Competências` | `competencias` | mantém |
| `Accountabilities` | `responsabilidades` (próprias) | mantém |
| `Gestor Direto`* | `parent_id`, por nome | vira filha da raiz |

\* obrigatórias. `id` e `ordem` ficam de fora: o primeiro é hex interno que ninguém
digita certo e concorreria com `Código`; a segunda é derivada da árvore, e uma coluna
para ela daria duas fontes para a ordem de irmãos, que divergem na primeira carga.

### Ler por título, não por posição

O cabeçalho sempre foi **conferido por nome** e os dados **lidos por índice fixo**.
A combinação aceitava uma planilha com as colunas certas fora de ordem e a lia
trocada — cargo gravado no departamento, em silêncio. Agora o título é que decide:
coluna a mais é ignorada, coluna a menos é pulada, ordem trocada não importa.

Foi isso que deixou inserir seis colunas sem quebrar arquivo em uso. E a regra que
sustenta a convivência é uma só: **coluna ausente não é célula vazia**. Ausente vira
`None` e é pulada; vazia obedece à tabela acima. Sem a distinção, um arquivo sem a
coluna `Vínculo` compararia `""` contra o padrão `clt` e marcaria a empresa inteira
como alterada — e a carga zeraria o vínculo de todo mundo de uma vez.

O efeito colateral é a melhor parte: dá para mandar **só as colunas que se quer
atualizar**. Três colunas — `Colaborador`, `Gestor Direto` e `Vínculo` — corrigem o
vínculo de 267 pessoas sem tocar em mais nada.

### Quem é quem entre duas cargas

Três tentativas, nesta ordem: `Código`, depois o par nome + e-mail, e o nome sozinho
como último recurso. O código existe porque trocar nome **e** e-mail no mesmo arquivo,
pelo par, vira uma demissão mais uma admissão — e a pessoa perde o lugar na árvore, a
accountability e o histórico. O último recurso pelo nome existe porque uma planilha
parcial não traz e-mail nenhum; sem ele, mandar três colunas lia a base real como 265
admissões e 265 demissões. Homônimo fica de fora dele: com dois xarás, virar linha
nova é honesto, escolher um não é.

`ORG-####` **não é reciclado**. Preencher a vaga de um removido economizaria números e
custaria identidade: uma planilha guardada do mês passado casaria a linha do demitido
com quem entrou depois no lugar. A marca d'água mora em `Config.piso_codigo` — quem
saiu não está mais no dicionário para ser contado.

### O que a planilha não manda

`Nível` e `Vínculo` têm domínio fechado e aceitam o rótulo que aparece na tela, sem
acento e sem caixa. Valor irreconhecível **não vira o padrão**: vira aviso no passo 2 e
o campo fica como está. Rebaixar em silêncio uma diretoria para "célula" porque alguém
escreveu "Diretor" no lugar de "Diretoria" é o tipo de estrago que só se descobre
olhando o desenho semanas depois.

A coluna `Accountabilities` carrega só as **próprias**. As delegadas — as equipes dos
reportes diretos — o sistema recalcula a cada carga, porque são derivadas: se um
subordinado muda de time, o escopo delegado do gestor mudou junto.

O recorte vale como nos outros formatos, e a legenda **diz** quando havia filtro — sem
isso o arquivo recortado sai indistinguível do inteiro assim que deixa o sistema, e
quem recebe lê "a empresa tem 12 pessoas". Reimportar um arquivo filtrado faz quem
ficou de fora aparecer como ausente; a opção de remover ausentes nasce desmarcada, e o
passo 2 mostra a lista antes de aplicar.

---

## Acesso

O login é **do próprio sistema**: e-mail + senha. O desenho da sessão veio do
GPlanSIS-Planner — JWT HS256 assinado localmente, sem biblioteca; segredo do
ambiente, aleatório por processo em desenvolvimento; **segredo forte
obrigatório** quando a autenticação é exigida. A sessão viaja em cookie
`HttpOnly`: a página inteira vem do servidor a cada requisição, e cookie fora do
alcance de JavaScript é o que impede um XSS de levar a sessão junto.

A credencial mora em `orga/usuarios.py`: hash **scrypt** da biblioteca padrão
(parâmetros gravados junto do hash), arquivo `dados/usuarios.json` fora do
estado — com espelho em `org.usuario` quando há banco —, freio a força bruta
(cinco erros seguidos travam a conta por um minuto), mensagem única para
"não existe" e "senha errada" (não se enumera usuário pela tela), senha
temporária com troca obrigatória no primeiro acesso e troca de senha pelo menu
do avatar (`/senha`).

| | |
|---|---|
| **Primeiro acesso** | sem nenhum usuário, `/login` oferece criar o administrador inicial — uma vez só. Ou `python -m orga.usuarios definir <e-mail>`, ou `ORG_ADMIN_EMAIL`/`ORG_ADMIN_SENHA` no primeiro arranque |
| **Contas** | Configurações › Permissões: cada colaborador ganha senha pelo botão Editar; contas fora do organograma (o operador) nascem em *Contas de acesso* |
| **Papel e escopo** | seguem no RBAC do organograma (`Config.acessos`). A credencial só prova identidade; `ORG_SUPERADMINS` entra sempre como Administrador total |

Quem entra continua sendo, sempre que possível, **alguém da estrutura**: o
e-mail bate com um nó e a sessão fica vinculada a ele (avatar, escopo
"próprio"). Não há SSO corporativo: o Peoples vive no hub gplansis.com, onde
cada sistema tem o seu login.

`ORG_EXIGIR_LOGIN=1` fecha tudo, por middleware e não rota a rota: rota nova
nasce protegida por omissão, e o esquecimento não passa em silêncio. Fragmento
htmx recebe `HX-Redirect`, senão o formulário de login apareceria colado dentro
do canvas.

## Banco de dados

O sistema roda em memória com persistência em JSON; o PostgreSQL de `schema.sql`
é o alvo de produção da SPEC §7. A aba **Configurações › Banco de dados** funciona
nos dois mundos: sem driver instalado ela ainda entrega o DDL, o mapeamento
coluna a coluna e o **SQL de carga gerado a partir do estado vigente** — gerado,
porque um script fixo estaria errado na primeira edição depois de escrito. Com
`psycopg` e `ORG_DATABASE_URL`, aplica.

A carga é uma transação só e é reexecutável: onde há chave natural, `ON
CONFLICT`; em accountability, que não tem chave natural, apagar antes de
escrever, dentro da mesma transação. Os nomes vão escapados — a base tem
`D'Avila`, e aspa solta num script não é defeito cosmético, é instrução a mais.

## Provisionamento de TI

Trocar de departamento raramente é só uma linha no organograma: quem sai de
Engenharia para Suprimentos perde licença de CAD e ganha licença de compras. Na
prática isso vira um chamado escrito à mão, e o que sobra é gente com acesso a
sistema de uma área onde não trabalha mais. **O risco não é a licença esquecida
— é a permissão que ficou.**

O organograma já sabe que a mudança aconteceu. Salvar um novo departamento no
painel abre o pedido sozinho, com o diff item a item: o que revogar e o que
conceder. Três decisões:

- **Software comum às duas áreas não entra em lista nenhuma.** Sairia numa de
  revogar e noutra de conceder, e TI tiraria e devolveria o mesmo acesso.
- **Destino sem catálogo não abre pedido.** A diferença seria "revogar tudo,
  conceder nada" — cortar acesso porque ninguém mapeou o destino. A falta vira
  aviso na tela, não revogação.
- **O pedido guarda os nomes, não a referência.** Editar o catálogo depois não
  reescreve chamado aberto; chamado que muda sozinho não é auditável.

Os destinatários saem do próprio organograma (vertical `OTC`), e não de uma
lista fixa que desatualiza no dia em que alguém entra ou sai de TI.

## Diretório social

O organograma diz a quem cada um responde. Não diz quem ajudou quem — e o
reconhecimento quase sempre atravessa a linha da hierarquia, que é justamente
por que ele mora no card e não no relatório do gestor.

O card do colaborador aceita **reconhecimento** e **feedback**, com rótulo
distinto: misturar "obrigado pela ajuda" com "isso poderia ter sido melhor"
numa lista só faz a pessoa evitar ler a lista. O reconhecimento aponta um dos
quatro valores da cultura — sem isso vira "valeu!", simpático e sem informação.

**É público, e por isso é assinado.** Não há anônimo: reconhecimento anônimo
perde a força e feedback anônimo vira canal de desabafo sem responsável, que é
outra ferramenta com outro cuidado. Quem escreveu pode apagar; **quem recebeu
pode tirar do próprio card** — publicar sobre alguém cria a obrigação de deixar
essa pessoa remover o que ficou escrito no nome dela. O ledger guarda o registro.

## MarIA

Portada do **GPlanSIS|Planner**, onde ela analisa projetos. Aqui o objeto é a
estrutura: quem responde a quem, onde está cada centro de custo, o que a
apresentação institucional promete e o que o cadastro entrega.

O que define este módulo não é o que a MarIA sabe fazer — é o que ela **não
pode** fazer sem alguém autorizar:

| # | Capacidade | Verbo | Efeito | Autoridade exigida | Nesta onda |
|---|---|---|---|---|---|
| 1 | Ler | consulta | nenhum | RBAC de leitura de quem pergunta | disponível |
| 2 | Descrever | explica estado | nenhum | idem | disponível |
| 3 | Relatar | gera PDF | artefato | idem + marca d'água de origem | disponível |
| 4 | Analisar baseline | declarado × cadastrado | nenhum | idem + gate de qualidade | disponível |
| 5 | Planejar | propõe cenário | **rascunho, nunca aplicado** | idem + versão do plano | disponível |
| 6 | Executar | dispara ação | mutação | **aprovação humana, por ação** | recusada |
| 7 | Agir sozinha | encadeia ações | mutação | fora de escopo desta onda | recusada |

Três coisas que estão no código, e não no texto:

**A MarIA nunca vê mais que quem pergunta.** O contexto é montado pela mesma
guarda de escopo que já rege a edição (SEC-03) — não por uma regra paralela que
divergiria dela no primeiro ajuste. Passar a base inteira ao modelo e pedir
discrição no prompt não é controle de acesso; é torcida.

**As capacidades 6 e 7 são recusadas antes da chamada.** `permitida()` devolve
False e a API nem é acionada — pagar por uma resposta que o sistema vai
descartar seria a versão cara do mesmo erro.

**Rascunho não vira mutação por engano.** PLANEJAR devolve texto e nada mais:
não existe rota que aplique o que a MarIA propôs. Um teste falha se alguém
criar uma.

Toda resposta — inclusive a recusada — vira registro com quem perguntou, **em
que recorte**, qual modelo e quanto custou. Sem o recorte não dá para auditar
depois se a resposta era compatível com o que a pessoa podia ver. O histórico
vive no estado e tem tabela própria (`org.maria_assistencia`) no schema.

A chave vem só do ambiente. O modelo é editável na tela — e o que a tela grava
é apenas o nome do modelo: credencial em estado gravado viaja junto no backup.

### As capacidades ficam na gaveta, não só na tabela

A gaveta oferece **cinco chips**: Ler, Descrever, Relatar, Analisar baseline e
Planejar. Elas mudam o prompt de verdade — `analisar` manda comparar declarado ×
cadastrado com evidência, `planejar` marca a resposta como rascunho que ninguém
aplica. Até então a gaveta mandava sempre `descrever`, e as outras só existiam na
tabela acima.

Duas ficam de fora, e é a mesma razão da tabela: **Executar** exige aprovação humana
explícita por ação, num POST próprio com a proposta inteira à vista de quem aprova —
oferecê-la num campo de texto contradiria o rodapé que promete somente leitura.
**Agir sozinha** está fora de escopo e nem passa pela guarda.

São rádios com label, não botões: o valor viaja no próprio envio, sem ida ao
servidor a cada clique, e volta escolhido no turno seguinte porque o POST o
carregou — nenhum estado novo. E há filtro **na entrada**, não só na exibição:
`capacidade` chega por formulário, e formulário é coisa que se forja; um `executar`
injetado no POST cai para `descrever`.

A vitrine de perguntas tem **45 no poço**, e a gaveta sorteia cinco a cada
abertura. Com cinco fixas, quem abre todo dia vê sempre as mesmas cinco e para
de ler; com quarenta e cinco sorteadas, a pessoa descobre que a MarIA responde
perguntas que ela ainda não tinha pensado em fazer — é a diferença entre um menu
e um convite. As **calculadas** vêm antes: sugestão que cita o número certo do
recorte mostra que a MarIA já leu a base dela, e o sorteio só completa o que
faltar. Sorteio de verdade e não rotação por índice guardado — guardar o índice
seria estado novo no servidor para decidir a ordem de uma vitrine.

O `⤢` do cabeçalho **alarga a gaveta para meia tela** (430 → 750 px numa tela de
1500). A resposta da MarIA vem com tabela, e tabela de cinco colunas em 430 px rola
para o lado dentro de uma gaveta que já rola para baixo. A escolha fica guardada na
máquina e atravessa cada turno. O módulo continua a um clique, no menu da MarIA na
barra.

Enquanto ela pensa, um **giro de 14 px** — a mesma altura do texto ao lado. A
ilustração de 22 px que ficava ali empurrava o rodapé a cada pergunta e a gaveta
pulava; com `prefers-reduced-motion` a folha de estilo para toda animação e sobra o
ponto parado, que continua dizendo o mesmo.

## Sincronização com o Microsoft 365

O centro de custo vive em dois lugares: na planilha do RH e no `department` de
cada pessoa no diretório corporativo. Enquanto os dois não conversam, a
diferença só aparece quando alguém percebe.

Portado do **GPlanSiS|OS** (`eos-manager/backend/auth.py`) — o desenho, não o código:
lá o cliente do Graph vem do `msal`; aqui o fluxo de credenciais de aplicativo
cabe numa requisição `urllib`, e este projeto não instala pacote por
conveniência. O que foi portado é o que custou descobrir: o filtro de usuário
(`accountEnabled eq true and assignedLicenses/$count ne 0`, sem o qual entram
salas e contas de serviço), o atributo que carrega o CC e a extração do prefixo
numérico — `80.31 Automation` vira `80.31`, porque o nome da área ao lado do
código tem grafia diferente em cada fonte.

São os **mesmos três passos da carga por planilha**, de propósito: quem já
atualizou a estrutura uma vez não precisa aprender um segundo jeito de conferir
antes de aplicar. Buscar → conferir → aplicar, e nada é escrito antes do
terceiro. A operação entra no ledger e cabe num desfazer.

Quatro decisões que estão no código, e não neste texto:

**Lê, nunca escreve.** O escopo pedido ao Entra é `User.Read.All`. Não existe
função que faça `POST` ou `PATCH` no Graph, e um teste varre o módulo e falha se
alguém criar uma — mudar isso exigiria mudar a permissão concedida no tenant,
que é decisão de quem o administra.

**Não cria gente.** Conta do MS365 que não casa com ninguém vira aviso, nunca
unidade nova. O recorte que pedimos ao Graph não traz gestor, e criar pessoa sem
gestor a penduraria na raiz — o mesmo erro que a carga da planilha recusa.

**Ausente no MS365 não é ausente na empresa.** Prestador (PJ) legitimamente não
tem licença. Quem não aparece é relatado **com o vínculo ao lado**, e nunca
removido.

**Menos preciso não sobrescreve mais preciso.** O MS365 guarda o CC na
granularidade que o RH digitou — às vezes `83`, às vezes `90.11`. O organograma
guarda N4, que é o que liga a pessoa à equipe. Quando o código do MS365 é
prefixo do gravado *em fronteira de ponto*, as duas fontes concordam no que o
MS365 sabe e nada muda. Quando discordam e o MS365 é o menos específico, isso é
**conflito**: relatado, sem caixa de marcar, porque gravar `83` por cima de
`83.11` apagaria a equipe e quebraria a resolução do cadastro de centros de
custo, que casa por N3.

O pareamento é por e-mail — que na carga por planilha é o segundo dos três degraus,
atrás do `Código`. Aqui não há código: o diretório corporativo não conhece o nosso.

## Gestão de terceiros

Toda unidade carrega um **vínculo**: CLT, prestador (PJ) ou consultoria externa.
Só a exceção ganha marca na tabela — marcar CLT, que é a maioria, viraria ruído
em 240 linhas e esconderia justamente quem não é empregado. É filtro próprio na
barra, campo no painel e critério que o organograma passa a distinguir de
verdade: quem não é empregado tem contrato, prazo e acesso diferentes, e não
separar isso é como o acesso de um prestador sobrevive ao fim do contrato.

## E-mail

O provisionamento de TI já sabia a quem avisar; faltava o carteiro. `correio.py`
está inteiro, com teste, e liga sozinho quando `SMTP_HOST` e `SMTP_DE`
aparecerem no ambiente — até lá a fila na tela é a notificação, e a aba diz
isso. Há um botão de envio de teste, que existe para descobrir que o SMTP está
errado antes de um pedido de verdade se perder.

**Falha de envio nunca derruba a operação que a disparou.** Abrir o pedido é o
fato importante; avisar é consequência. Servidor de e-mail fora não pode custar
o pedido.

## Agente Organograma

"Crie um novo time de Growth Marketing com 1 Diretor, 2 Coordenadores e 4
Analistas focado na América Latina" vira estrutura de verdade — pelo caminho das
sete capacidades, não por um atalho ao lado delas:

    PLANEJAR (5)   a MarIA devolve a proposta em JSON e nada acontece
    EXECUTAR (6)   uma pessoa lê a lista inteira, confere e aprova — aí cria

A capacidade 6 **passou a existir nesta onda**, e existe **com** a autoridade que
a tabela sempre exigiu. A 7 continua recusada: encadear ações sem parada humana
entre elas é outra coisa.

O que o modelo devolve é entrada não confiável como qualquer outra. Nível
inexistente, quantidade fora de 1–30 e gestor que não está no recorte são
recusados antes de virarem unidade — criar sob alguém que não existe seria
pendurar um time inteiro num galho imaginário.

A proposta é guardada com identificador, e aprovar cita **essa** lista. O modelo
não é chamado de novo na aprovação: senão a pessoa aprovaria um texto e o
sistema criaria outro, que é o modo mais silencioso de o consentimento não valer
nada. A criação inteira cabe num único desfazer.

## Arquitetura

HTMX server-driven (ADR-010). O servidor é a fonte única de verdade — **inclusive da
geometria** (ADR-011).

| Responsabilidade | Onde | Por quê |
|---|---|---|
| Modelo, regras, ledger | `main.py` | integridade e auditoria |
| **Cálculo do layout** | `dominio.py::calcular_layout` | determinismo e paridade com o export |
| Render do SVG | `templates/_canvas.html` | o mesmo fragmento serve tela e arquivo |
| Mutação | HTMX → fragmento `#canvas` | zero estado duplicado no cliente |
| Seleção, menu, pan, zoom | JS (~90 linhas) | efêmero, não vale round-trip |

### A escada de camadas

Uma escada só, escrita num lugar só, no topo do CSS. `z-index` espalhado é a classe
de defeito que ninguém enxerga lendo o arquivo — só clicando.

```
  6  .canto          controles sobre o desenho
 30  .alca-gaveta
 60  .gaveta         painel de detalhes (tela estreita)
 65  .mc             gaveta da MarIA
 74  .filtros-corpo  painel de filtros (tela estreita)
 84  MENUS E POPOVERS   .modulos .maria-menu .conta-menu .idioma-menu
                        .expo-menu .zoom-menu .pop
 86  .ctx            menu de contexto
 88  #tooltip
 90  .alerta
```

**Todo menu é `position:fixed`, ancorado no gatilho por JS.** Não é preciosismo: em
tela estreita a barra do topo e a de ferramentas viram contêineres de rolagem
(`overflow-x:auto`), e rolagem num eixo recorta os dois — um menu `absolute` ali
dentro era cortado na altura da própria barra. O popover dos filtros já vivia assim,
com o motivo escrito no código; os outros quatro descobriram tarde.

A segunda armadilha foi **contexto de empilhamento**: o menu do zoom morava dentro do
`.canto`, que tem `z-index` próprio. Elemento posicionado com `z-index` abre contexto,
e dentro dele o 84 do menu valia 6 para o resto da página — qualquer painel passava
por cima. O menu saiu do canto e virou filho do palco, que não abre contexto.

Nenhuma das duas apareceria numa leitura do CSS. Apareceram medindo: abrir cada
popover com a gaveta da MarIA aberta e perguntar ao navegador, por
`elementFromPoint`, quem está na frente.

### Colisão de nome de classe

`.chips` já existia na vista Estrutura, com `display:flex; justify-content:center`.
O agrupamento novo dos filtros reusou o nome, e a regra da Estrutura — que vem
depois no arquivo — venceu: os oito filtros apareciam amontoados no meio da barra,
com vãos dos dois lados. Nome de classe é espaço compartilhado; o agrupamento virou
`.grupo-chips`.

```
orga/            o pacote da aplicação — 21 módulos e o schema
  main.py        app FastAPI: estado, ledger, rotas, permissões, API, exportação
  dominio.py     modelo + motor de layout + filtros (puro, sem I/O, sem DOM)
  configuracao.py  Config, perfis RBAC e paleta de tema do canvas
  cargos.py      níveis hierárquicos, catálogo de cargos e regras de classificação
  centros.py     cadastro de centros de custo e reconciliação com a estrutura
  importador.py  planilha → estado; análise diferencial e carga incremental
  equipes.py     pessoas → equipes; a mesma estrutura vista por time
  ajuda.py       os passos da visita guiada
  m365.py        Microsoft Graph → centro de custo; leitura, nunca escrita
  pdf.py         SVG (subconjunto) → PDF A3 paisagem vetorial
  idiomas.py     catálogo pt-BR / en-US / es
  schema.sql     alvo de produção (PostgreSQL 18) — mora ao lado de quem o lê
web/             o que o navegador recebe
  templates/     base + 29 fragmentos Jinja
  marca/         logos, paleta institucional e a MarIA
  vendor/        htmx 2.0.4
dados/           estado.json — derivado da planilha, fora do versionamento
planilhas/       Organograma.xlsx — dado pessoal, fora do versionamento
docs/            manual de uso, SPEC e apresentação — ver docs/README.md
testes/          679 testes: layout, ondas, A11Y, API, LGPD, filtros, permissões,
                 tema, contraste, cargos, centros de custo, carga, M365 e PDF
```

**Um nível dentro de `orga/`, e é decisão.** Os vinte e um módulos são pares,
não camadas: `dominio` é o modelo e o motor, `main` é o app, e os outros
respondem cada um por um assunto do negócio. Agrupá-los em subpastas por
"função técnica" criaria uma hierarquia que o sistema não tem, e obrigaria a
escolher uma gaveta para cada módulo novo sem que a escolha mudasse nada.

Os imports dentro do pacote são **relativos** (`from . import dominio`). Não é
estilo: import absoluto casaria com um módulo de mesmo nome instalado no
ambiente, e `pdf`, `social` e `banco` são nomes que qualquer venv pode ter.

`main.py` separa **`BASE`** (o pacote) de **`RAIZ`** (o repositório): o que é
código mora no primeiro, o que é conteúdo — templates, marca, manual, estado —
no segundo. Antes os dois eram o mesmo diretório e a distinção não existia.

O motor de layout é o único produtor de coordenadas do sistema. `calcular_layout`
é pura e síncrona: testável em Python puro, sem servidor e sem navegador.

### O invariante que o sistema protege

Em orientação invertida, para todo par (pai, filho):

```
Y(pai) > Y(filho) + altura(filho)
```

A inversão é **projeção de índice de nível**, não transformação de matriz.
`scaleY(-1)` está proibido (LAY-02) — espelharia glifos, setas e sombreamento.
Um teste varre o código entregue a cada execução da suíte.

A ordem do DOM e o `aria-level` seguem a hierarquia **lógica**, não a posição na
tela: a raiz continua sendo nível 1 e o primeiro nó tabulável, ainda que o card
esteja na base do desenho.

---

## Decisões tomadas na carga dos dados

Quatro pontos exigiram decisão. Todos estão registrados no ledger da carga.

**1. Raiz sintética `Board`.** Quatro diretores (CEO, CTO, CFO, CLO) apontam para
"Board" na coluna Gestor Direto, e "Board" não é uma linha da planilha. A SPEC exige
raiz única (RF-03), então o Board é materializado como nó. A alternativa — pendurar
os três diretores sob o CEO — inventaria uma relação que o dado não afirma.

**2. Accountability delegada derivada.** O único escopo derivável sem inventar é o
que a liderança responde através de terceiros: as equipes dos seus subordinados
diretos. É exatamente a modelagem da SPEC §13 (*"a gerência responde por estes
escopos, executados por estas áreas"*). Quando os subordinados estão na mesma equipe
do líder, o card nasce sem bullets: não há delegação a declarar.

A delegada é **recalculada a cada carga**, porque é derivada: um subordinado que
troca de time muda o escopo do gestor junto. A própria não se deduz de nada — vem do
painel ou da coluna `Accountabilities` da planilha — e por isso é **preservada** na
rederivação. Não era: `_delegar_por_equipe` atribuía a lista inteira, e toda carga
assistida apagava a accountability própria de quem tivesse ao menos um subordinado.
O teste que cobria isso observava uma folha, o único caso em que a promessa valia.

**3. Tipo derivado do cargo.** Diretor→diretoria, Gerente→gerência,
Coordenador/Supervisor/Líder→coordenação, Estagiário/Aprendiz/Assistente/Auxiliar→apoio,
demais→célula. Editável no painel.

**4. Coluna `MONTAGEM` ignorada.** Marca 66 linhas com "PFD" (a planta de montagem).
Como o dado já aparece em Departamento para essas pessoas, incluí-la duplicaria
informação sem acrescentar estrutura.

### Por que o desenho não ganha camada de GPU em repouso

Com a árvore inteira aberta o SVG mede **59 038 × 1 369 px** — 80 M px de área de
layout, contra um teto típico de 16 384 px por eixo na GPU. Duas regras de CSS
obrigavam o navegador a materializar isso em textura já na abertura da página:
`filter: drop-shadow(...)` no `#canvas` e `will-change: transform` fixo no
`#lente`. O renderer morria tentando alocar, e a aba fechava sozinha.

O filtro saiu — comprava uma sombra sutil que a borda do card já entrega, com
folga de 3:1 nos dois temas. A promoção de camada virou **transitória**: a classe
`.gesto` entra em `aplicar()` (o único escritor do `transform`) e sai 400 ms
depois que o gesto para. Arrastar e dar zoom continuam compostos; parado, o
desenho volta a ser pintado normalmente. Travado por
`testes/test_app.py::test_desenho_gigante_nao_ganha_camada_permanente`.

Vale a régua geral: `will-change` promove **enquanto dura o gesto**. Deixá-lo
fixo num elemento do tamanho do conteúdo é pedir uma textura do tamanho do
conteúdo.

## Tema escuro e responsividade

O tema alcança **também o SVG do canvas**, que carrega o próprio `<style>` por ser
autocontido (INT-07). Na tela as cores do desenho são variáveis CSS, então trocar o
tema é instantâneo — nenhum round-trip, nenhum reflow do desenho; o `POST` só
persiste a preferência. No arquivo exportado as mesmas cores saem como **valor
literal e sempre no tema claro**: papel não tem tema, e variável CSS em SVG solto
não é universalmente suportada (Inkscape). Um teste garante que as duas paletas
definem exatamente as mesmas chaves — chave faltando viraria variável indefinida,
ou seja, elemento invisível.

Os tons escuros derivam de `#2D3336` e `#000000`, dentro da paleta institucional.
Sobre o grafite o laranja sobe para 4,7:1 — só ali ele pode ser texto.

Contraste do tema escuro medido e travado por teste: todo texto do card passa em
AA (o mais apertado é `#9AA0A3` a 5,35:1), e borda, trilho, conector e marcador
passam em 3:1 contra o palco. **A borda do card é objeto gráfico no escuro**, não
enfeite: `#262C2F` sobre `#171B1D` dá 1,4:1 de preenchimento, então quem separa o
card do fundo é a borda — por isso ela é `#5F676A` e não o cinza mais discreto que
o tema claro usa, onde a separação vem do branco sobre cinza mais a sombra.

Três pontos de quebra: em 1100 px o selo de tenant encolhe; em 900 px a gaveta vira
sobreposição e as tabelas ganham rolagem horizontal própria; em **680 px** começa a
tela estreita. Em tela estreita a gaveta **nasce recolhida** — ela cobriria o canvas
inteiro — e tocar fora dela a fecha. Encolher a janela para dentro do ponto de
quebra recolhe; alargar de volta não reabre, porque quem recolheu, recolheu.

### Tela estreita

O princípio: **rolar para o lado é uma forma de esconder** — quem não arrasta não
descobre. Abaixo de 680 px, tudo o que rolava passa a caber.

**O cabeçalho vira um menu.** Canvas, Estrutura, Tabela, Configurações, Manual e
idioma entram num popover ancorado no hamburguer. **MarIA e o avatar ficam de
fora**: são as duas coisas que se abre no meio de uma leitura, e enterrá-las custaria
dois toques onde hoje se gasta um. O logo do cliente fica na barra — com as vistas
dentro do menu, o que sobrou ali é justamente de quem é a estrutura.

Popover, e não folha de largura total: cobrindo a tela inteira ele parecia uma vista
nova, e vista nova se fecha com Voltar, não tocando fora.

**A barra de ferramentas vira ícones.** Ícone e rótulo convivem no HTML; o rótulo
sai por CSS e o nome acessível vem do `aria-label` — botão que fica mudo ao girar o
aparelho não é botão. Um teste percorre os botões com ícone e exige os dois.

**Os oito filtros viram um painel suspenso.** Um toque abre o grupo inteiro, com
contagem de critérios ativos no próprio gatilho, e a barra devolve a altura ao
desenho.

**A tabela vira cartão.** Ela tem catorze colunas e o celular comporta quatro. A
ordem do cartão é a ordem da pergunta: quem é (código, N, nível), como se chama, o
que faz, e só então a ficha de cadastro — Departamento, CC, N5, Vertical, Natureza,
Sub., cada valor com o rótulo miúdo em cima. Nada foi escondido: as catorze
continuam ali.

Trocar o `display` de `<tr>`/`<td>` **apaga a semântica de tabela** no navegador, e o
leitor de tela deixaria de anunciar linha e célula justamente onde a tela já não
mostra o cabeçalho. Por isso `role="table"`, `role="row"` e `role="cell"` estão
escritos no HTML, e o `<thead>` sai da tela mas não do documento.

**O canvas abre onde dá para ler.** O piso de leitura (38 %) é régua de papel A3: num
aparelho, 38 % é um card de 100 px. Em tela estreita o piso deixa de ser número fixo
e passa a ser *o card da raiz cabendo na largura*. Com a árvore inteira aberta — 267
cards, 32 576 px — o celular abre a **100 %**, enquadrado na raiz, e daí se desce
pelos chevrons do canto. Na orientação lateral o desktop ajusta à largura e se lê
descendo; o celular continua enquadrando a raiz, porque as seis colunas cabem em
412 px a 43 % — cabe e não se lê.

## Marca e acessibilidade

A UI usa exclusivamente a paleta institucional (`marca/paleta.png`): `#EB6A20`,
`#F6A709`, `#2D3336`, `#000000`, `#7D8286`. Nenhum tom novo foi criado.

Duas consequências práticas, ambas deliberadas:

- **Laranja e âmbar aparecem em traços, faixas e marcadores, não em texto sobre
  branco.** `#EB6A20` sobre branco dá 3,4:1 — suficiente para objeto gráfico
  (≥3:1), insuficiente para texto (≥4,5:1). Sobre o grafite do card raiz e da barra,
  onde o contraste sobe, o laranja é usado como texto.
- **Texto secundário usa `#4A5053`**, um neutro derivado de `#7D8286` — o cinza
  institucional puro reprovaria em texto pequeno. Neutros de apoio são previstos
  pela própria paleta.

A distinção entre accountability própria e delegada não depende de cor: marcador
sólido × vazado, mais itálico.

O chrome do produto é GPlanSIS (MRK-01); a marca GPlanSiS|Peoples aparece como **selo de
tenant** — "estrutura de GPlanSiS|Peoples" — que é dado do cliente (MRK-02).

---

## Conformidade verificada

`pytest -q` executa os critérios de onda como testes, não como checklist:

| Bloco | Cobre |
|---|---|
| T-L01…T-L09 | contrato de layout da SPEC §9, incluindo LAY-03/05/06/12/13/14 |
| W9-C1…C10 | adicionar, salvar delegada, rebaixar, promover, reordenar, duplicar, excluir, desfazer |
| W2-C2 | guarda de ciclo: destino descendente recusado com 200 + alerta (INT-06) |
| W4-C2/C3 | cadeia íntegra após mutações; adulteração aponta o `seq` correto |
| W5-C3/C4/C6 | zero espelhamento no código; liderança na base; 100 % dos conectores com `fill="none"` |
| RNF-02 | duas renderizações byte-idênticas |
| A11Y-02/03/04 | raiz em `aria-level="1"`, primeira na ordem de tabulação, `<desc>` declara a orientação |
| API-01/02/03 | ETag com 304, árvore aninhada lógica, orientação só no `meta` |
| W8-C6 | varredura do modelo, do estado e do schema por campo de remuneração ou dado sensível |
| SEC-02/03 | viewer não muta nada; editor confinado à subárvore de escopo; só admin configura |
| W7-C1/C3 | PDF A3 paisagem em uma folha, fontes base, texto extraível, enquadramento centrado em nove proporções |
| lateral | colunas por profundidade, leitura em pré-ordem, zero sobreposição, fio na calha, viewBox = bbox, determinismo, não empilha |
| cascata | chip estreita os outros e não a si mesmo, marca sobrevive a recorte vazio, chip vazio nasce desabilitado |
| tela estreita | cartão da tabela com `role` de tabela, `data-rot` por célula, célula vazia some, botão de ícone com `aria-label` |
| OOB | chips, pílulas, orientação, agrupamento, níveis, histórico e escala do PDF voltam fora de banda — e um só de cada |

Os testes de orientação lateral e de cascata nasceram de uma **revisão adversarial**:
52 agentes sobre o diff, 16 achados brutos, 10 confirmados por maioria de três
céticos independentes. Os dez viraram correção. O mais caro deles não estava na
onda nova — a marca do cliente no card da raiz tinha **duas contas para o mesmo
retângulo**, e uma accountability na raiz bastava para o logo ser pintado por cima
do texto.

Um teste roda `node --check` no JavaScript da página e recusa identificador
declarado duas vezes. Ele existe porque um `const esc` colidindo com o `let esc`
do zoom matou o script inteiro em silêncio: a página continuava desenhando — o
desenho é do servidor — e só a interação morria.

Outro teste trava dois invariantes do canvas que só aparecem por interação real:
**o palco nunca fica rolado** (`overflow:hidden` não impede rolagem programática;
focar um card fora da vista por seta ou Tab rolava o container e deslocava a âncora
do zoom em silêncio) e **clicar no fundo tira o foco de campo de texto** (o
`preventDefault` que arma o arraste cancela junto a troca de foco padrão, e sem o
blur as teclas `0`/`+`/`−`/`B` passavam a digitar no filtro). Os dois vieram de
revisão adversarial e foram reproduzidos antes de corrigidos.

Leitura do **INT-01**: o contrato rege a interação do canvas — os fragmentos
`_canvas`, `_menu`, `_painel` e `_vista_canvas` só alvejam `#canvas` e `#painel`, e
um teste garante isso. A troca de vista na barra superior alveja `#area`; é
navegação do shell, não mutação do canvas.

---

## Débito técnico assumido

| # | Débito | Onda |
|---|---|---|
| DT-01 | Persistência em JSON, não PostgreSQL. `schema.sql` entregue; falta o repositório. | W10 |
| DT-02 | Sem autenticação. O RBAC existe e é aplicado, mas o perfil vigente é escolhido na tela em vez de vir de um JWT. | W10 |
| DT-03 | Estado global de processo único — não sobrevive a múltiplos workers uvicorn. | W10 |
| DT-04 | Temporalidade (SCD-2) existe no modelo e no schema, não na tela. | W6 |
| DT-05 | Modo lista para viewport estreita (LAY-15) não implementado. | W8 |
| DT-06 | Export PNG ausente. PDF A3, XLSX, SVG, CSV e JSON entregues. | W7 |
| DT-07 | Delegação para não-descendente não é validada (INV-04 / RT-12). | W10 |
| DT-08 | O PDF ignora `rx` do card (cantos vivos) e não desenha as alças de colapso — ambos irrelevantes em papel. | — |

O HUMAN-GATE da SPEC (HG-01…HG-06) segue aberto: são decisões de negócio, não de
implementação. A carga atual assume `tipo` derivado do cargo (HG-01), cabeçalho
interno (HG-02) e escopo de empresa inteira (HG-04).

Nenhum desses débitos bloqueia o uso do canvas para modelar e revisar a estrutura.
