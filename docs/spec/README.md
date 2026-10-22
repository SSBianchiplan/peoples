# GPlanSiS|Peoples — Canvas Twin do organograma invertido

Implementação de referência da **SPEC-GPLANSIS-ORG-001**, ondas W5' e W9.
Canvas editável, clicável, com menu de contexto no botão direito, barra de
ferramentas e navegação entre vistas. Liderança na **base**, times **acima**.

## Executar

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
# http://localhost:8080
```

Sem CDN: o htmx está vendorizado em `vendor/`. Roda em rede fechada.

## Arquitetura

HTMX server-driven. O servidor é a fonte única de verdade — inclusive da geometria.

| Responsabilidade | Onde | Por quê |
|---|---|---|
| Modelo, regras, ledger | Python | integridade e auditoria |
| **Cálculo do layout** | Python (`calcular_layout`) | determinismo e paridade com o export |
| Render do SVG | Jinja (`_canvas.html`) | mesmo fragmento serve tela e arquivo |
| Mutação | HTMX → fragmento `#canvas` | zero estado duplicado no cliente |
| Seleção, menu, pan, zoom | JS (~70 linhas) | efêmero, não vale round-trip |

Nenhum framework de front. Nenhum passo de build.

## Operação do canvas

| Gesto | Efeito |
|---|---|
| Clique no card | abre o painel de edição |
| **Botão direito no card** | menu: editar, adicionar subordinado, duplicar, mover ←/→, promover, rebaixar, excluir |
| Arrastar o fundo | pan |
| `Ctrl` + roda | zoom |
| `+` `-` `0` | aproximar, afastar, ajustar |
| `Esc` | fecha o menu |

Na caixa de responsabilidades, uma por linha. Prefixo `>` marca **delegada**
(renderiza em ciano itálico com marcador vazado).

## Vistas

- **Canvas** — o twin editável.
- **Tabela** — mesma árvore em ordem lógica raiz → folhas.
- **Auditoria** — ledger append-only com verificação da cadeia SHA-256.

## Persistência

Padrão: `dados/estado.json`, gravado a cada mutação. Alvo de produção:
`schema.sql` (PostgreSQL 18). O domínio já está isolado da persistência —
trocar o repositório não toca no motor de layout.

## Invariante que o sistema protege

Em orientação invertida, para todo par (pai, filho):

```
Y(pai) > Y(filho) + altura(filho)
```

A inversão é **projeção de profundidade**, não transformação de matriz.
`scaleY(-1)` está proibido (LAY-02) — espelharia os glifos.
A ordem do DOM e o `aria-level` seguem a hierarquia lógica, não a posição
na tela: a raiz continua sendo nível 1 e o primeiro nó tabulável.
