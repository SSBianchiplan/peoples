# SPEC-GPLANSIS-ORG-001 — ORGANOGRAMA INVERTIDO

**Módulo:** `GPlanSiS|Peoples` — Estrutura Organizacional e Responsabilidades
**Metodologia:** SDD·BE (Spec-Driven Development · Black Edition)
**Linguagem normativa:** RFC-2119 (PT-BR) — DEVE / NÃO DEVE / DEVERIA / NÃO DEVERIA / PODE
**Versão:** 1.1.0 · **Status:** SPEC + implementação de referência (ondas W5' e W9 entregues)
**Autor técnico:** GPlanSiS · **Data:** 2026-08-11

---

## 0. SUMÁRIO EXECUTIVO

Sistema de gestão e renderização de estrutura organizacional com **orientação invertida** (base = liderança, topo = times liderados), modelagem temporal (SCD-2), trilha de auditoria hash-encadeada e exportação vetorial.

O caso-piloto é a estrutura de Recursos Humanos (raiz: Marina Albuquerque Sá · 5 unidades filhas), mas o modelo DEVE ser genérico o suficiente para qualquer diretoria, sem hardcode de níveis, nomes ou quantidade de filhos.

**Diferencial normativo:** a inversão é uma propriedade de **apresentação**, jamais de **domínio**. A hierarquia lógica permanece raiz→folhas em banco, API, DOM e ARIA. Somente o eixo Y do SVG é espelhado.

---

## 1. CONTEXTO E PROBLEMA

O artefato atual é um slide estático (PowerPoint) com caixas desenhadas manualmente. Problemas identificados:

| # | Problema | Impacto |
|---|---|---|
| P1 | Sem fonte única de verdade — o slide é o "banco de dados" | Divergência entre RH, TI e portal interno |
| P2 | Sem histórico — não é possível responder "qual era a estrutura em 01/2026?" | Auditoria e compliance trabalhista |
| P3 | Layout manual — cada mudança exige reposicionar caixas | Custo de manutenção alto, erro humano |
| P4 | Responsabilidades da raiz duplicam nomes das áreas filhas | Ambiguidade: é responsabilidade própria ou delegada? |
| P5 | Não acessível (imagem rasterizada, sem semântica) | Falha WCAG 2.1 AA |
| P6 | Orientação convencional (topo-down) contradiz o discurso de liderança servidora | Desalinhamento cultura ↔ artefato |

---

## 2. OBJETIVO E NÃO-OBJETIVO

### 2.1 Objetivo (ESCOPO)

O sistema **DEVE**:

- **OBJ-01** — Persistir unidades organizacionais, pessoas, alocações e responsabilidades com vigência temporal.
- **OBJ-02** — Renderizar o organograma em **orientação invertida** de forma determinística e responsiva.
- **OBJ-03** — Suportar orientação convencional (`vertical`) via parâmetro, sem duplicação de código de layout.
- **OBJ-04** — Responder consultas do tipo "organograma vigente em `D`" para qualquer `D` dentro do histórico.
- **OBJ-05** — Registrar toda mutação em ledger append-only com encadeamento criptográfico.
- **OBJ-06** — Exportar SVG, PNG (@1x/@2x/@3x) e PDF preservando texto selecionável no SVG/PDF.
- **OBJ-07** — Atender WCAG 2.1 AA, incluindo navegação por teclado e leitura por leitor de tela.

### 2.2 Não-objetivo (FORA DE ESCOPO)

O sistema **NÃO DEVE**, nesta versão:

- **NOBJ-01** — Armazenar, exibir ou calcular **remuneração, salário, faixa salarial ou custo de pessoal**. O nó "Remuneração Estratégica" é o *nome de uma área*, não um dado financeiro.
- **NOBJ-02** — Armazenar dado pessoal sensível (CPF, RG, endereço residencial, dados de saúde, dados biométricos).
- **NOBJ-03** — Substituir o sistema de folha de pagamento ou o eSocial.
- **NOBJ-04** — Implementar workflow de aprovação de mudança organizacional (previsto para v2).
- **NOBJ-05** — Suportar matriz (múltiplos pais por unidade). A v1 é estritamente arborescente.
- **NOBJ-06** — Editor drag-and-drop de layout livre. O layout é **derivado**, nunca posicionado à mão.

---

## 3. GLOSSÁRIO

| Termo | Definição |
|---|---|
| **Unidade** | Nó da estrutura. Pode ser diretoria, gerência, coordenação, área, célula ou apoio. |
| **Responsável** | Pessoa alocada a uma unidade com papel `responsavel`. Uma unidade tem no máximo um responsável vigente por período. |
| **Responsabilidade** | Item de escopo funcional atribuído a uma unidade (os *bullets* do card). |
| **Responsabilidade delegada** | Responsabilidade cujo cumprimento é executado por uma unidade filha. |
| **Orientação invertida** | Modo de renderização em que a profundidade 0 (raiz) ocupa a maior coordenada Y (base) e a profundidade máxima ocupa a menor (topo). |
| **Âncora-pai** | Aresta do card por onde saem os conectores para os filhos. Invertida: aresta superior. |
| **Âncora-filho** | Aresta do card por onde entra o conector do pai. Invertida: aresta inferior. |
| **Barramento** | Segmento horizontal que agrega os conectores de um conjunto de irmãos. |
| **L.G.R.** | ⚠️ Sigla presente no artefato de origem, **não definida**. Ver RT-07 e HG-03. |

---

## 4. REQUISITOS

### 4.1 Requisitos funcionais

| ID | Requisito | Prioridade |
|---|---|---|
| RF-01 | O sistema **DEVE** permitir CRUD de unidades com `parent_id` e `ordem_exibicao`. | MUST |
| RF-02 | O sistema **DEVE** rejeitar qualquer operação que crie ciclo na árvore, com erro HTTP 422. | MUST |
| RF-03 | O sistema **DEVE** garantir exatamente uma unidade raiz por organograma. | MUST |
| RF-04 | O sistema **DEVE** impedir duas alocações `responsavel` com vigências sobrepostas na mesma unidade. | MUST |
| RF-05 | O sistema **DEVE** classificar cada responsabilidade como `propria`, `delegada` ou `compartilhada`. | MUST |
| RF-06 | Responsabilidade `delegada` **DEVE** referenciar a unidade destino; `propria` **NÃO DEVE** referenciar. | MUST |
| RF-07 | O endpoint de leitura **DEVE** aceitar `?vigencia=YYYY-MM-DD` e retornar o estado daquela data. | MUST |
| RF-08 | O endpoint de leitura **DEVE** aceitar `?orientacao=invertida\|vertical` (default `invertida`). | MUST |
| RF-09 | A API **DEVE** retornar a árvore em ordem lógica raiz→folhas, independente da orientação. | MUST |
| RF-10 | O frontend **DEVE** calcular o layout no cliente a partir da árvore lógica. | MUST |
| RF-11 | O sistema **DEVE** exportar SVG, PNG e PDF do organograma vigente. | SHOULD |
| RF-12 | O sistema **DEVERIA** exibir badge visual distinguindo responsabilidade delegada de própria. | SHOULD |
| RF-13 | O sistema **PODE** oferecer busca textual por pessoa/responsabilidade com destaque do nó. | MAY |

### 4.2 Requisitos não-funcionais

| ID | Requisito | Critério mensurável |
|---|---|---|
| RNF-01 | Latência de leitura da árvore | p95 < 150 ms para árvore de até 500 nós (backend, sem rede) |
| RNF-02 | Determinismo de layout | Mesma entrada ⇒ SVG byte-idêntico em 100 execuções consecutivas |
| RNF-03 | Acessibilidade | 0 violações `serious`/`critical` no axe-core, perfil WCAG 2.1 AA |
| RNF-04 | Responsividade | Legível de 360 px a 2560 px, sem scroll horizontal aninhado |
| RNF-05 | Cobertura de testes | ≥ 85 % linhas no domínio; 100 % nas funções de layout e ciclo |
| RNF-06 | Auditoria | Cadeia de hash verificável de ponta a ponta em O(n) |
| RNF-07 | Contraste | ≥ 4,5:1 para texto normal, ≥ 3:1 para bordas e traços de conector |

---

## 5. MODELO DE DOMÍNIO

```
Organograma 1 ──── N Unidade
                      │ 1
                      ├──── N Alocacao ──── 1 Pessoa
                      │
                      ├──── N Responsabilidade ──┐
                      │                          │ (delegada_para)
                      └──── N UnidadeClosure ────┘
                            (ancestral × descendente × profundidade)
```

**Invariantes de domínio (INV):**

- **INV-01** — Toda unidade não-raiz **DEVE** ter exatamente um pai ativo.
- **INV-02** — `unidade.parent_id` **NÃO DEVE** referenciar a própria unidade nem qualquer descendente dela.
- **INV-03** — `unidade_closure` **DEVE** conter a linha `(id, id, 0)` para toda unidade (auto-referência).
- **INV-04** — A soma de responsabilidades `delegada` de uma unidade **NÃO DEVE** apontar para unidade que não seja sua descendente direta.
- **INV-05** — `alocacao.vigencia` **NÃO DEVE** ter limite inferior posterior ao limite superior.
- **INV-06** — `org.evento` **NÃO DEVE** aceitar `UPDATE` nem `DELETE` (append-only enforçado por privilégio e trigger).

---

## 6. STACK (ADR)

### 6.1 Decisões

| Camada | Escolha | Versão | ADR |
|---|---|---|---|
| Linguagem backend | Python | 3.14 | ADR-001 |
| Framework HTTP | FastAPI | 0.11x | ADR-001 |
| Validação/serialização | Pydantic | v2 | ADR-001 |
| ORM / Core | SQLAlchemy | 2.0 (async) | ADR-002 |
| Driver | asyncpg | 0.30+ | ADR-002 |
| Migrations | Alembic | 1.14+ | ADR-002 |
| Banco | PostgreSQL | 18 | ADR-003 |
| Extensões PG | `btree_gist`, `pgcrypto`, `citext` | — | ADR-003 |
| ~~Frontend~~ | ~~React + TypeScript~~ → **HTMX** | 2.0 | ~~ADR-004~~ → **ADR-010** |
| ~~Build~~ | ~~Vite~~ → **nenhum** | — | **ADR-010** |
| Estilo | CSS com variáveis (sem framework) | — | **ADR-010** |
| Templates | Jinja2 | 3.1 | **ADR-010** |
| ~~Layout de árvore~~ | ~~`d3-hierarchy` (cliente)~~ → **Python (servidor)** | — | ~~ADR-005~~ → **ADR-011** |
| Render | SVG puro (sem canvas, sem lib de diagramas) | — | ADR-005 |

> ⚠️ ADR-004, ADR-005 e ADR-007 foram superados pelo **ADENDO 01** (fim do documento).
> As linhas tachadas ficam no histórico; a decisão vigente é ADR-010 / ADR-011.
| Testes backend | pytest + pytest-asyncio + testcontainers | — | ADR-006 |
| Testes frontend | Vitest + Testing Library + Playwright | — | ADR-006 |
| Export server-side | Playwright (headless Chromium) | — | ADR-007 |
| Observabilidade | OpenTelemetry + structlog | — | ADR-008 |
| Runtime | Docker + Traefik | — | ADR-009 |

### 6.2 Racional das decisões críticas

**ADR-003 — PostgreSQL 18 com closure table (adjacência como fonte de verdade)**

- *Contexto:* consultas de subárvore, ancestrais e profundidade são o caminho quente do render.
- *Decisão:* `parent_id` é a fonte de verdade; `unidade_closure` é derivada e mantida por trigger.
- *Alternativas rejeitadas:*
  - `ltree` — elegante, mas rebalancear caminho em reparent de subárvore grande é custoso e o path vira dado desnormalizado editável por engano.
  - `WITH RECURSIVE` puro — suficiente para 500 nós, mas não dá índice para "todos os descendentes de X" em consultas de permissão.
  - Nested sets — reparent é O(n) com lock de tabela. Rejeitado.
- *Consequência:* toda mutação de `parent_id` **DEVE** passar pela função `org.fn_mover_unidade`, jamais por `UPDATE` direto.

**ADR-005 — `d3-hierarchy` para layout, SVG escrito à mão para render**

- *Contexto:* precisamos de layout *tidy tree* determinístico e controle total do desenho invertido.
- *Decisão:* `d3.tree()` calcula `(x, y)` no espaço canônico; a inversão é uma transformação afim aplicada depois.
- *Alternativas rejeitadas:*
  - `react-flow` / `mermaid` — trazem canvas, zoom, e um DOM que não controlamos; inversão vira gambiarra de CSS `transform: scaleY(-1)` que **espelha o texto**. Rejeitado categoricamente.
  - Layout manual — quebra RF-10 e RNF-02.
- *Consequência:* `scaleY(-1)` **NÃO DEVE** ser usado em nenhuma hipótese (ver RT-02).

**ADR-007 — Export via Playwright, não via bibliotecas de PDF**

- *Contexto:* o SVG já é a verdade visual; recriá-lo em ReportLab duplicaria a lógica de layout.
- *Decisão:* renderizar a mesma rota React em headless e capturar.
- *Consequência:* o container de export carrega Chromium (~400 MB). Aceito — roda como worker separado, não no pod da API.

---

## 7. MODELO DE DADOS — DDL POSTGRESQL 18

```sql
-- ============================================================
-- SPEC-GPLANSIS-ORG-001 · migration 001_org_baseline
-- ============================================================
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE SCHEMA IF NOT EXISTS org;

CREATE TYPE org.tipo_unidade AS ENUM
    ('diretoria','gerencia','coordenacao','area','celula','apoio');

CREATE TYPE org.papel_alocacao AS ENUM
    ('responsavel','membro','interino','apoio');

CREATE TYPE org.origem_responsabilidade AS ENUM
    ('propria','delegada','compartilhada');

-- ------------------------------------------------------------
-- ORGANOGRAMA (escopo / tenant lógico)
-- ------------------------------------------------------------
CREATE TABLE org.organograma (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          citext NOT NULL UNIQUE
                  CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$'),
    nome          text   NOT NULL,
    orientacao_padrao text NOT NULL DEFAULT 'invertida'
                  CHECK (orientacao_padrao IN ('invertida','vertical')),
    ativo         boolean NOT NULL DEFAULT true,
    criado_em     timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- PESSOA (minimização LGPD — ver §13)
-- ------------------------------------------------------------
CREATE TABLE org.pessoa (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matricula     text UNIQUE,
    nome_completo text NOT NULL
                  CHECK (char_length(btrim(nome_completo)) BETWEEN 2 AND 160),
    nome_exibicao text NOT NULL
                  CHECK (char_length(btrim(nome_exibicao)) BETWEEN 2 AND 60),
    email_corp    citext UNIQUE,
    avatar_url    text,
    ativo         boolean NOT NULL DEFAULT true,
    criado_em     timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- UNIDADE (nó da árvore)
-- ------------------------------------------------------------
CREATE TABLE org.unidade (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organograma_id uuid NOT NULL REFERENCES org.organograma(id) ON DELETE CASCADE,
    codigo         text NOT NULL,                    -- série por módulo: ORG-0001
    nome           text NOT NULL
                   CHECK (char_length(btrim(nome)) BETWEEN 2 AND 80),
    nome_curto     text,                             -- rótulo para card estreito
    tipo           org.tipo_unidade NOT NULL,
    parent_id      uuid REFERENCES org.unidade(id) ON DELETE RESTRICT,
    ordem_exibicao smallint NOT NULL DEFAULT 0,
    cor_token      text CHECK (cor_token ~ '^[a-z-]{3,24}$'),
    ativo          boolean NOT NULL DEFAULT true,
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_unidade_codigo UNIQUE (organograma_id, codigo),
    CONSTRAINT ck_unidade_nao_autopai CHECK (parent_id IS DISTINCT FROM id)
);

-- INV: exatamente uma raiz por organograma
CREATE UNIQUE INDEX ux_unidade_raiz_unica
    ON org.unidade (organograma_id)
    WHERE parent_id IS NULL;

CREATE INDEX ix_unidade_parent  ON org.unidade (parent_id, ordem_exibicao);
CREATE INDEX ix_unidade_org     ON org.unidade (organograma_id) WHERE ativo;

-- ------------------------------------------------------------
-- CLOSURE TABLE (derivada — mantida por trigger)
-- ------------------------------------------------------------
CREATE TABLE org.unidade_closure (
    ancestral_id   uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    descendente_id uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    profundidade   smallint NOT NULL CHECK (profundidade >= 0),
    PRIMARY KEY (ancestral_id, descendente_id)
);
CREATE INDEX ix_closure_desc ON org.unidade_closure (descendente_id, profundidade);

-- ------------------------------------------------------------
-- ALOCACAO (pessoa × unidade × papel × vigência)
-- ------------------------------------------------------------
CREATE TABLE org.alocacao (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unidade_id uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    pessoa_id  uuid NOT NULL REFERENCES org.pessoa(id)  ON DELETE RESTRICT,
    papel      org.papel_alocacao NOT NULL,
    cargo      text CHECK (cargo IS NULL OR char_length(btrim(cargo)) BETWEEN 2 AND 80),
    vigencia   daterange NOT NULL DEFAULT daterange(CURRENT_DATE, NULL, '[)'),
    criado_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_alocacao_vigencia_valida CHECK (NOT isempty(vigencia)),
    -- RF-04: um único responsável vigente por unidade
    CONSTRAINT ex_alocacao_responsavel_unico
        EXCLUDE USING gist (unidade_id WITH =, vigencia WITH &&)
        WHERE (papel = 'responsavel')
);
CREATE INDEX ix_alocacao_unidade ON org.alocacao (unidade_id, papel);
CREATE INDEX ix_alocacao_pessoa  ON org.alocacao (pessoa_id);

-- ------------------------------------------------------------
-- RESPONSABILIDADE (os bullets do card)
-- ------------------------------------------------------------
CREATE TABLE org.responsabilidade (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unidade_id   uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    descricao    text NOT NULL
                 CHECK (char_length(btrim(descricao)) BETWEEN 2 AND 200),
    origem       org.origem_responsabilidade NOT NULL DEFAULT 'propria',
    delegada_para_unidade_id uuid REFERENCES org.unidade(id) ON DELETE SET NULL,
    ordem        smallint NOT NULL DEFAULT 0,
    vigencia     daterange NOT NULL DEFAULT daterange(CURRENT_DATE, NULL, '[)'),
    criado_em    timestamptz NOT NULL DEFAULT now(),
    -- RF-06
    CONSTRAINT ck_resp_delegacao_coerente
        CHECK ((origem = 'delegada') = (delegada_para_unidade_id IS NOT NULL)),
    CONSTRAINT ck_resp_nao_autodelegada
        CHECK (delegada_para_unidade_id IS DISTINCT FROM unidade_id)
);
CREATE INDEX ix_resp_unidade ON org.responsabilidade (unidade_id, ordem);

-- ------------------------------------------------------------
-- LEDGER DE AUDITORIA (append-only, hash-encadeado)
-- ------------------------------------------------------------
CREATE TABLE org.evento (
    seq           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ocorrido_em   timestamptz NOT NULL DEFAULT clock_timestamp(),
    ator          text NOT NULL,
    acao          text NOT NULL CHECK (acao IN ('criar','alterar','mover','inativar','realocar')),
    entidade      text NOT NULL,
    entidade_id   uuid NOT NULL,
    payload       jsonb NOT NULL,
    hash_anterior bytea,
    hash          bytea NOT NULL
);
```

### 7.1 Guarda de ciclo e manutenção da closure

```sql
CREATE OR REPLACE FUNCTION org.fn_guarda_ciclo() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.parent_id IS NULL THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1 FROM org.unidade_closure
        WHERE ancestral_id = NEW.id
          AND descendente_id = NEW.parent_id
    ) THEN
        RAISE EXCEPTION
            'ORG-CICLO: unidade % nao pode ter como pai o proprio descendente %',
            NEW.id, NEW.parent_id
            USING ERRCODE = '23514';
    END IF;

    IF (SELECT organograma_id FROM org.unidade WHERE id = NEW.parent_id)
       IS DISTINCT FROM NEW.organograma_id THEN
        RAISE EXCEPTION 'ORG-ESCOPO: pai pertence a outro organograma'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END $$;

CREATE TRIGGER tg_unidade_guarda_ciclo
    BEFORE INSERT OR UPDATE OF parent_id ON org.unidade
    FOR EACH ROW EXECUTE FUNCTION org.fn_guarda_ciclo();
```

```sql
CREATE OR REPLACE FUNCTION org.fn_sync_closure() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO org.unidade_closure (ancestral_id, descendente_id, profundidade)
        VALUES (NEW.id, NEW.id, 0);

        IF NEW.parent_id IS NOT NULL THEN
            INSERT INTO org.unidade_closure (ancestral_id, descendente_id, profundidade)
            SELECT c.ancestral_id, NEW.id, c.profundidade + 1
            FROM org.unidade_closure c
            WHERE c.descendente_id = NEW.parent_id;
        END IF;

    ELSIF TG_OP = 'UPDATE' AND NEW.parent_id IS DISTINCT FROM OLD.parent_id THEN
        -- desconecta subarvore dos antigos ancestrais
        DELETE FROM org.unidade_closure
        WHERE descendente_id IN (
                SELECT descendente_id FROM org.unidade_closure WHERE ancestral_id = NEW.id)
          AND ancestral_id IN (
                SELECT ancestral_id FROM org.unidade_closure
                WHERE descendente_id = NEW.id AND ancestral_id <> NEW.id);

        -- reconecta aos novos ancestrais
        IF NEW.parent_id IS NOT NULL THEN
            INSERT INTO org.unidade_closure (ancestral_id, descendente_id, profundidade)
            SELECT sup.ancestral_id, sub.descendente_id,
                   sup.profundidade + sub.profundidade + 1
            FROM org.unidade_closure sup
            CROSS JOIN org.unidade_closure sub
            WHERE sup.descendente_id = NEW.parent_id
              AND sub.ancestral_id   = NEW.id;
        END IF;
    END IF;

    RETURN NEW;
END $$;

CREATE TRIGGER tg_unidade_sync_closure
    AFTER INSERT OR UPDATE OF parent_id ON org.unidade
    FOR EACH ROW EXECUTE FUNCTION org.fn_sync_closure();
```

### 7.2 Ledger hash-encadeado

```sql
CREATE OR REPLACE FUNCTION org.fn_evento_encadear() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_anterior bytea;
BEGIN
    SELECT hash INTO v_anterior
    FROM org.evento ORDER BY seq DESC LIMIT 1;

    NEW.hash_anterior := v_anterior;
    NEW.hash := digest(
        coalesce(encode(v_anterior,'hex'),'GENESIS')
        || '|' || NEW.ocorrido_em::text
        || '|' || NEW.ator
        || '|' || NEW.acao
        || '|' || NEW.entidade
        || '|' || NEW.entidade_id::text
        || '|' || NEW.payload::text,
        'sha256');
    RETURN NEW;
END $$;

CREATE TRIGGER tg_evento_encadear
    BEFORE INSERT ON org.evento
    FOR EACH ROW EXECUTE FUNCTION org.fn_evento_encadear();

CREATE OR REPLACE FUNCTION org.fn_evento_imutavel() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'ORG-LEDGER: org.evento e append-only' USING ERRCODE = '42501';
END $$;

CREATE TRIGGER tg_evento_imutavel
    BEFORE UPDATE OR DELETE ON org.evento
    FOR EACH STATEMENT EXECUTE FUNCTION org.fn_evento_imutavel();
```

### 7.3 Consulta do organograma vigente

```sql
CREATE OR REPLACE FUNCTION org.fn_organograma_vigente(
    p_slug     citext,
    p_vigencia date DEFAULT CURRENT_DATE
)
RETURNS TABLE (
    unidade_id       uuid,
    parent_id        uuid,
    profundidade     smallint,
    codigo           text,
    nome             text,
    nome_curto       text,
    tipo             org.tipo_unidade,
    ordem_exibicao   smallint,
    responsavel_nome text,
    responsavel_cargo text,
    responsabilidades jsonb
)
LANGUAGE sql STABLE AS $$
    WITH raiz AS (
        SELECT u.id
        FROM org.unidade u
        JOIN org.organograma o ON o.id = u.organograma_id
        WHERE o.slug = p_slug AND u.parent_id IS NULL
    )
    SELECT
        u.id,
        u.parent_id,
        c.profundidade,
        u.codigo,
        u.nome,
        u.nome_curto,
        u.tipo,
        u.ordem_exibicao,
        p.nome_exibicao,
        a.cargo,
        coalesce(
            (SELECT jsonb_agg(jsonb_build_object(
                        'descricao', r.descricao,
                        'origem',    r.origem,
                        'delegada_para', r.delegada_para_unidade_id
                    ) ORDER BY r.ordem, r.descricao)
             FROM org.responsabilidade r
             WHERE r.unidade_id = u.id
               AND r.vigencia @> p_vigencia),
            '[]'::jsonb)
    FROM raiz
    JOIN org.unidade_closure c ON c.ancestral_id = raiz.id
    JOIN org.unidade u         ON u.id = c.descendente_id AND u.ativo
    LEFT JOIN org.alocacao a   ON a.unidade_id = u.id
                              AND a.papel = 'responsavel'
                              AND a.vigencia @> p_vigencia
    LEFT JOIN org.pessoa p     ON p.id = a.pessoa_id
    ORDER BY c.profundidade, u.ordem_exibicao, u.nome;
$$;
```

---

## 8. CONTRATO DE API

Base: `/api/v1`. Erros **DEVEM** seguir RFC 9457 (`application/problem+json`).

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/organogramas/{slug}` | Árvore vigente. Query: `vigencia`, `orientacao`, `profundidade_max` |
| `GET` | `/organogramas/{slug}/historico` | Marcos de mudança estrutural |
| `POST` | `/organogramas/{slug}/unidades` | Cria unidade |
| `PATCH` | `/unidades/{id}` | Altera atributos (não move) |
| `POST` | `/unidades/{id}/mover` | Reparent. Body: `{ "novo_parent_id": uuid, "ordem": int }` |
| `DELETE` | `/unidades/{id}` | Inativação lógica (`ativo = false`) |
| `PUT` | `/unidades/{id}/responsavel` | Encerra alocação vigente e abre nova |
| `PUT` | `/unidades/{id}/responsabilidades` | Substitui a lista completa (idempotente) |
| `GET` | `/organogramas/{slug}/export` | Query: `formato=svg\|png\|pdf`, `escala=1\|2\|3` |
| `GET` | `/auditoria/verificar` | Valida a cadeia de hash. Retorna `{ integro, seq_falha }` |

**Regras normativas:**

- **API-01** — `GET /organogramas/{slug}` **DEVE** retornar `ETag` derivado de `max(atualizado_em)` + `vigencia`, e honrar `If-None-Match` com `304`.
- **API-02** — A resposta **DEVE** ser uma árvore aninhada em ordem lógica, **jamais** pré-ordenada por posição visual.
- **API-03** — `orientacao` **NÃO DEVE** alterar a estrutura do JSON. É apenas um *hint* devolvido em `meta.orientacao`.
- **API-04** — Violação de ciclo **DEVE** retornar `422` com `type: "urn:gplansis:org:ciclo-detectado"`.
- **API-05** — Toda rota de mutação **DEVE** exigir header `X-Motivo` (texto livre, 5–200 caracteres), gravado no ledger.

**Exemplo de resposta (fragmento):**

```json
{
  "meta": {
    "slug": "rh-peoples",
    "vigencia": "2026-08-11",
    "orientacao": "invertida",
    "profundidade_max": 1,
    "total_unidades": 6,
    "etag": "W/\"7f3a...\""
  },
  "raiz": {
    "id": "0f9c...",
    "codigo": "ORG-0001",
    "nome": "Recursos Humanos",
    "tipo": "gerencia",
    "profundidade": 0,
    "responsavel": { "nome_exibicao": "Marina Albuquerque Sá", "cargo": "Gerente de RH" },
    "responsabilidades": [
      { "descricao": "L.G.R.", "origem": "delegada", "delegada_para": "3ab1..." },
      { "descricao": "Atração e gestão de talentos", "origem": "delegada", "delegada_para": "5cd2..." }
    ],
    "filhos": [
      {
        "id": "3ab1...",
        "codigo": "ORG-0002",
        "nome": "Remuneração Estratégica",
        "nome_curto": "Remuneração",
        "tipo": "area",
        "profundidade": 1,
        "ordem_exibicao": 10,
        "responsavel": { "nome_exibicao": "Beatriz Nogueira Pinto", "cargo": null },
        "responsabilidades": [
          { "descricao": "Remuneração", "origem": "propria", "delegada_para": null },
          { "descricao": "Benefícios",  "origem": "propria", "delegada_para": null }
        ],
        "filhos": []
      }
    ]
  }
}
```

---

## 9. CONTRATO DE LAYOUT INVERTIDO ⭐ (NORMATIVO)

Esta seção é o núcleo da spec. Toda implementação de render **DEVE** aderir literalmente.

### 9.1 Espaço canônico e transformação

O layout ocorre em duas fases estritamente separadas:

**Fase 1 — layout canônico (orientação-agnóstico).** `d3.tree()` produz, para cada nó `n`:
- `n.x` — posição no eixo transversal (irmãos lado a lado)
- `n.depth` — profundidade lógica (raiz = 0)

**Fase 2 — projeção.** Aplicar a função de projeção conforme a orientação:

```
D      = profundidade máxima da árvore
H_liv  = CARD_H + GAP_V                 (altura de uma faixa de nível)

vertical:   Y(n) = MARGEM_TOP + n.depth        * H_liv
invertida:  Y(n) = MARGEM_TOP + (D - n.depth)  * H_liv

X(n) = MARGEM_LEFT + n.x                        (idêntico nas duas orientações)
```

- **LAY-01** — A projeção **DEVE** ser uma translação de índice de nível, nunca uma transformação de matriz sobre o SVG.
- **LAY-02** — `transform="scale(1,-1)"`, `scaleY(-1)`, `flex-direction: column-reverse` e equivalentes **NÃO DEVEM** ser usados. Todos espelham glifos, setas e sombreamento.
- **LAY-03** — Com `D = 0` (organograma de nó único), ambas as orientações **DEVEM** produzir saída idêntica.

### 9.2 Âncoras de conector

| Orientação | Âncora-pai (saída p/ filhos) | Âncora-filho (entrada do pai) | Sentido do barramento |
|---|---|---|---|
| `vertical` | aresta **inferior** do card | aresta **superior** do card | abaixo do pai |
| `invertida` | aresta **superior** do card | aresta **inferior** do card | acima do pai |

- **LAY-04** — As âncoras **DEVEM** ser derivadas da orientação em tempo de layout. Coordenadas de âncora **NÃO DEVEM** ser codificadas literalmente no componente de card.

### 9.3 Geometria do conector

Para um pai `P` com filhos `F₁…Fₙ`, na orientação invertida:

```
y_ancora_pai   = Y(P)                                  (topo do card do pai)
y_barramento   = Y(P) - GAP_V / 2
y_ancora_filho = Y(Fᵢ) + CARD_H                        (base do card do filho)

path = M cx(P) y_ancora_pai
       V y_barramento
       H cx(F₁) … cx(Fₙ)          (segmento único de min a max)
       V y_ancora_filho           (uma vertical por filho)
```

- **LAY-05** — O barramento **DEVE** ser um único segmento horizontal de `min(cx(Fᵢ))` a `max(cx(Fᵢ))`, não `n` segmentos empilhados.
- **LAY-06** — Nó com **um único filho** **DEVE** ser conectado por uma vertical reta, sem barramento.
- **LAY-07** — Conectores **NÃO DEVEM** portar marcador de seta. A relação hierárquica é posicional, não direcional.
- **LAY-08** — Todo `<path>` de conector **DEVE** declarar `fill="none"`.
- **LAY-09** — Conectores **DEVEM** ser emitidos antes dos cards na ordem do documento, garantindo que os cards fiquem por cima.

### 9.4 Posição do cabeçalho do card

O artefato de origem posiciona o cabeçalho (área + nome) **fora** do card, acima dele. Na orientação invertida isso colide com a âncora-pai da raiz.

- **LAY-10** — O modo `cabecalho=interno` **DEVE** ser o padrão em orientação invertida: o cabeçalho é uma faixa dentro do card, com separador de 0,5 px. Elimina toda classe de colisão e é o único modo compatível com profundidade ≥ 2.
- **LAY-11** — O modo `cabecalho=externo` **PODE** ser oferecido para paridade visual com o slide legado. Nesse modo:
  - nó **folha** (sem filhos) → cabeçalho na face oposta à âncora-filho;
  - nó **raiz** (sem pai) → cabeçalho na face oposta à âncora-pai (portanto **abaixo** do card, na invertida);
  - nó **intermediário** (com pai e filhos) → o modo externo **NÃO DEVE** ser aplicado; recai para `interno`.

### 9.5 Ordenação e determinismo

- **LAY-12** — Irmãos **DEVEM** ser ordenados por `(ordem_exibicao ASC, nome ASC, id ASC)`. O `id` é o desempate final que garante RNF-02.
- **LAY-13** — Todas as coordenadas emitidas **DEVEM** ser arredondadas a 2 casas decimais antes da serialização.
- **LAY-14** — O `viewBox` **DEVE** ser calculado como o *bounding box* real do conteúdo + `MARGEM`, nunca fixado por constante.

### 9.6 Tokens de layout

| Token | Padrão | Faixa | Observação |
|---|---|---|---|
| `CARD_W` | 220 px | 140–320 | Largura fixa; conteúdo se adapta |
| `CARD_H_MIN` | 120 px | 80–— | Cresce com nº de responsabilidades |
| `CARD_PAD` | 16 px | 8–24 | — |
| `GAP_H` | 24 px | 16–48 | Espaço entre irmãos |
| `GAP_V` | 88 px | 56–160 | Determina a folga do barramento |
| `MARGEM` | 40 px | 24–80 | Todos os lados |
| `TRACO` | 0,5 px | 0,5–1 | Contraste ≥ 3:1 exigido (RNF-07) |

### 9.7 Comportamento responsivo

- **LAY-15** — Se `n_irmãos × (CARD_W + GAP_H) > largura_viewport` e `viewport < 768 px`, o render **DEVE** alternar para **modo lista hierárquica** (acordeão indentado), preservando a ordem lógica e todo o conteúdo. **NÃO DEVE** reduzir `CARD_W` abaixo de 140 px nem introduzir scroll horizontal aninhado.
- **LAY-16** — No modo lista, a orientação invertida **DEVE** ser expressa por indentação e rótulo textual de nível, **não** por inversão da ordem de leitura.

---

## 10. FRONTEND (React 19)

### 10.1 Estrutura de componentes

```
src/modules/org/
├─ api/
│  ├─ client.ts              fetch tipado + ETag
│  └─ schemas.ts             zod (contrato espelhado da API)
├─ domain/
│  ├─ tree.ts                normalização flat → aninhada
│  ├─ layout.ts              ⭐ projeção canônica → coordenadas
│  └─ layout.test.ts         100 % de cobertura (RNF-05)
├─ components/
│  ├─ OrgChart.tsx           orquestrador; escolhe SVG vs lista
│  ├─ OrgSvgCanvas.tsx       <svg>, viewBox, camadas
│  ├─ OrgConnectors.tsx      paths (emitidos primeiro)
│  ├─ OrgCard.tsx            card + cabeçalho interno/externo
│  ├─ OrgResponsibilityList.tsx
│  ├─ OrgListFallback.tsx    modo acordeão (LAY-15)
│  └─ OrgLegend.tsx          legenda própria × delegada
├─ hooks/
│  ├─ useOrgChart.ts         TanStack Query
│  └─ useRovingTabIndex.ts   navegação por teclado
└─ tokens.css                variáveis de layout e cor
```

### 10.2 Assinatura da função de layout

```ts
export type Orientacao = 'invertida' | 'vertical';

export interface TokensLayout {
  cardW: number; cardHMin: number; cardPad: number;
  gapH: number; gapV: number; margem: number;
}

export interface NoPosicionado {
  id: string;
  profundidade: number;
  x: number; y: number; w: number; h: number;
  ancoraPai: { x: number; y: number };   // face voltada aos filhos
  ancoraFilho: { x: number; y: number }; // face voltada ao pai
  cabecalho: 'interno' | 'externo-antes' | 'externo-depois';
}

export interface ResultadoLayout {
  nos: NoPosicionado[];
  conectores: { paiId: string; d: string }[];
  viewBox: readonly [number, number, number, number];
  profundidadeMax: number;
}

export function calcularLayout(
  raiz: NoArvore,
  orientacao: Orientacao,
  tokens: TokensLayout,
): ResultadoLayout;
```

- **FE-01** — `calcularLayout` **DEVE** ser pura, síncrona e livre de acesso ao DOM. Testável em Node puro.
- **FE-02** — O componente `OrgCard` **NÃO DEVE** conhecer a orientação. Recebe apenas `x, y, w, h, cabecalho`.
- **FE-03** — A ordem dos elementos no DOM **DEVE** seguir a hierarquia lógica (raiz primeiro), independente da posição visual.

---

## 11. ACESSIBILIDADE ⚠️

O ponto de falha mais provável desta feature.

- **A11Y-01** — O container **DEVE** expor `role="tree"`; cada card, `role="treeitem"` com `aria-level`, `aria-setsize`, `aria-posinset`.
- **A11Y-02** — `aria-level` **DEVE** refletir a profundidade **lógica** (raiz = 1). A inversão visual **NÃO DEVE** alterar `aria-level`.
- **A11Y-03** — A ordem de tabulação **DEVE** ser a ordem lógica raiz→folhas. Um leitor de tela anuncia "Recursos Humanos, nível 1" primeiro, ainda que o card esteja na base da tela.
- **A11Y-04** — O `<svg>` **DEVE** portar `role="img"` com `<title>` e `<desc>`; o `<desc>` **DEVE** declarar explicitamente a orientação, ex.: *"Organograma invertido: a liderança ocupa a base; os times liderados, o topo."*
- **A11Y-05** — Navegação por teclado: `↑`/`↓` navegam entre irmãos; `Enter` expande/colapsa; `Home`/`End` vão ao primeiro/último irmão. As setas **DEVEM** mapear a direção **visual** percebida, não a lógica — na invertida, `↑` a partir da raiz move para os filhos.
- **A11Y-06** — Distinção própria × delegada **NÃO DEVE** depender apenas de cor. **DEVE** haver ícone ou marcador textual (RNF-07 / WCAG 1.4.1).
- **A11Y-07** — Todo texto **DEVE** ser `<text>` SVG real, jamais `<image>` ou path convertido. Selecionável e pesquisável.
- **A11Y-08** — `prefers-reduced-motion: reduce` **DEVE** desabilitar transições de expandir/colapsar.

---

## 12. SEGURANÇA, LGPD E AUDITORIA

### 12.1 Autenticação e autorização

- **SEC-01** — Autenticação via OIDC (JWT `RS256`), validação de `aud`, `iss` e `exp`.
- **SEC-02** — RBAC com três papéis: `org.viewer` (leitura), `org.editor` (mutação em subárvore autorizada), `org.admin` (irrestrito).
- **SEC-03** — `org.editor` **DEVE** ter seu escopo validado contra `org.unidade_closure`: só pode mutar unidades que sejam descendentes da sua unidade de escopo.
- **SEC-04** — Rate limit de 30 req/min por identidade nas rotas de mutação.

### 12.2 LGPD

| Base legal | Dado | Justificativa |
|---|---|---|
| Art. 7º, II — obrigação legal | nome, cargo, unidade | Organização do trabalho (CLT) |
| Art. 7º, IX — legítimo interesse | e-mail corporativo, avatar | Comunicação interna |

- **LGPD-01** — O sistema **NÃO DEVE** persistir CPF, RG, endereço residencial, telefone pessoal, dados de saúde ou biométricos.
- **LGPD-02** — O sistema **NÃO DEVE** persistir qualquer valor de remuneração (ver NOBJ-01), ainda que o nome de uma área contenha o termo.
- **LGPD-03** — `avatar_url` **DEVE** apontar para storage interno com URL assinada de curta duração. **NÃO DEVE** ser URL pública permanente.
- **LGPD-04** — Desligamento **DEVE** encerrar a vigência da alocação, preservando o histórico. **NÃO DEVE** apagar `org.pessoa` (integridade do ledger).
- **LGPD-05** — Exportações **DEVEM** ser registradas no ledger com identidade do solicitante.

### 12.3 Marca

- **MRK-01** — Sendo módulo do ecossistema GPlanSIS, materiais *product-facing* (UI, docs de produto, telas de export com marca do produto) **NÃO DEVEM** referenciar GPlanSiS|Peoples.
- **MRK-02** — O **conteúdo** do organograma (nomes de unidades, pessoas, razão social do cliente) é dado de tenant e **PODE** conter qualquer marca. A separação é entre *chrome do produto* e *dado do cliente*.

---

## 13. SEED DE REFERÊNCIA

Derivado do artefato de origem. Orientação: `invertida`. `slug`: `rh-referencia`.

| Código | Unidade | Profund. | Responsável | Ordem |
|---|---|---|---|---|
| ORG-0001 | Recursos Humanos | 0 | Marina Albuquerque Sá | 0 |
| ORG-0002 | Remuneração Estratégica | 1 | Beatriz Nogueira Pinto | 10 |
| ORG-0003 | Administração de Pessoal | 1 | Jaqueline Cavalcanti Cardoso | 20 |
| ORG-0004 | Desenvolvimento Organizacional | 1 | Daniela Fontes Ribeiro | 30 |
| ORG-0005 | Atração de Talentos | 1 | Lucas Souza Brito | 40 |
| ORG-0006 | Documentação | 1 | Elaine Moreira Lins | 50 |

**Responsabilidades da raiz (ORG-0001) — todas classificadas como `delegada`:**

| Descrição | Delegada para |
|---|---|
| L.G.R. | ORG-0003 |
| Atração e gestão de talentos | ORG-0005 |
| Desenvolvimento organizacional e cultura | ORG-0004 |
| Remuneração estratégica | ORG-0002 |
| Administração de pessoal | ORG-0003 |

> **Nota de modelagem:** no artefato de origem, os cinco *bullets* da raiz são exatamente os nomes das cinco áreas filhas. Sem a classificação `delegada`, isso seria duplicação de dado. Com ela, torna-se informação legítima: *"a gerência responde por estes escopos, executados por estas áreas"*. A UI **DEVERIA** renderizar essas linhas com marcador de delegação e link para o nó destino (RF-12).

**Responsabilidades das áreas — todas `propria`:**

- **ORG-0002** — Remuneração · Benefícios · Gestão de talentos · Indicadores · Gestão PJ
- **ORG-0003** — L.G.R. · Folha de pagamento · Admissão/Rescisão · Ponto · Férias
- **ORG-0004** — Treinamentos · Programas de capacitação · Gestão de estagiários · Eventos especiais · GPTW
- **ORG-0005** — Recrutamento e seleção · Onboarding · Offboarding
- **ORG-0006** — Documentação para integração de colaboradores em clientes · Obrigações acessórias · Suporte no onboarding · Suporte em eventos

---

## 14. ESTRATÉGIA DE TESTES

| Camada | Ferramenta | Foco |
|---|---|---|
| Unidade (domínio PY) | pytest | invariantes, validadores Pydantic |
| Integração (SQL) | pytest + testcontainers[postgres] | triggers de ciclo, closure, ledger, `EXCLUDE` |
| Contrato (API) | schemathesis sobre OpenAPI | fuzzing de contrato |
| Unidade (layout TS) | Vitest | ⭐ 100 % de cobertura em `layout.ts` |
| Componente | Testing Library | ordem DOM, atributos ARIA |
| E2E + visual | Playwright | regressão de pixel dos dois modos |
| A11y | axe-core (via Playwright) | 0 violações serious/critical |

**Casos de teste obrigatórios de `layout.ts`:**

| ID | Cenário | Esperado |
|---|---|---|
| T-L01 | Árvore de 1 nó, invertida | `Y = MARGEM`; sem conectores |
| T-L02 | Árvore de 1 nó, ambas orientações | Saídas idênticas (LAY-03) |
| T-L03 | Raiz + 5 filhos, invertida | `Y(raiz) > Y(filho)` para todos os filhos |
| T-L04 | Raiz + 1 filho | Vertical reta, sem barramento (LAY-06) |
| T-L05 | Profundidade 3 | 3 barramentos distintos, sem sobreposição |
| T-L06 | Irmãos com `ordem_exibicao` empatada | Desempate por nome, depois por id (LAY-12) |
| T-L07 | Mesma entrada, 100 execuções | Serialização byte-idêntica (RNF-02) |
| T-L08 | Nó intermediário com `cabecalho=externo` | Recai para `interno` (LAY-11) |
| T-L09 | `viewBox` calculado | Contém todos os nós + margem, sem folga extra (LAY-14) |
| T-L10 | 8 irmãos em viewport de 375 px | Ativa modo lista (LAY-15) |

---

## 15. ROADMAP DE ONDAS (SDD·BE)

Cada onda percorre o loop `SPEC → BUILD → SELF-CHECK → RED-TEAM → HUMAN-GATE → DONE`.
Critérios são **binários**: PASS ou FAIL. Não existe "parcial".

### W0 — Fundação

**Entregáveis:** monorepo (`apps/api`, `apps/web`, `packages/contracts`), Docker Compose (PG 18 + API + Web + Traefik), CI (lint · type-check · test), Alembic baseline.

| # | Critério | PASS se |
|---|---|---|
| W0-C1 | `docker compose up` sobe a stack | 3 containers `healthy` em < 90 s |
| W0-C2 | `alembic upgrade head` em base vazia | Exit 0, sem warning |
| W0-C3 | CI verde em PR limpo | 4 jobs PASS |
| W0-C4 | `mypy --strict` e `tsc --noEmit` | 0 erros |

### W1 — Domínio e DDL

**Entregáveis:** migration `001_org_baseline`, entidades SQLAlchemy, schemas Pydantic, triggers de ciclo/closure/ledger.

| # | Critério | PASS se |
|---|---|---|
| W1-C1 | Inserção de ciclo direto (`A→A`) | `CHECK` viola, erro 23514 |
| W1-C2 | Inserção de ciclo indireto (`A→B→C→A`) | Trigger levanta `ORG-CICLO` |
| W1-C3 | Segunda raiz no mesmo organograma | Índice único viola |
| W1-C4 | Dois `responsavel` com vigência sobreposta | `EXCLUDE` viola |
| W1-C5 | `origem='delegada'` sem `delegada_para` | `CHECK` viola |
| W1-C6 | `UPDATE` em `org.evento` | Erro 42501 |
| W1-C7 | Closure após inserir árvore de 4 níveis | Linhas = Σ(profundidade+1) por nó |

### W2 — Reparent e integridade da closure

**Entregáveis:** `org.fn_mover_unidade`, endpoint `POST /unidades/{id}/mover`, testes de propriedade.

| # | Critério | PASS se |
|---|---|---|
| W2-C1 | Mover subárvore de 12 nós | Closure recalculada 100 % correta vs. CTE recursiva de referência |
| W2-C2 | Mover nó para descendente próprio | 422 `ciclo-detectado` |
| W2-C3 | Mover para outro organograma | 422 `escopo-invalido` |
| W2-C4 | 200 movimentações aleatórias (property-based) | Closure íntegra em 200/200 |
| W2-C5 | Movimentação concorrente (2 sessões) | Sem deadlock; segunda serializada ou rejeitada |

### W3 — API de leitura

**Entregáveis:** `GET /organogramas/{slug}`, `fn_organograma_vigente`, ETag, OpenAPI 3.1.

| # | Critério | PASS se |
|---|---|---|
| W3-C1 | Árvore de 500 nós | p95 < 150 ms em 200 requisições |
| W3-C2 | `If-None-Match` com ETag válido | 304, corpo vazio |
| W3-C3 | `?vigencia` no passado | Retorna responsável histórico correto |
| W3-C4 | `?orientacao=vertical` vs `invertida` | JSON idêntico exceto `meta.orientacao` (API-03) |
| W3-C5 | Schemathesis sobre OpenAPI | 0 falhas de contrato |

### W4 — API de escrita e auditoria

**Entregáveis:** CRUD completo, header `X-Motivo`, `GET /auditoria/verificar`.

| # | Critério | PASS se |
|---|---|---|
| W4-C1 | Mutação sem `X-Motivo` | 400 `motivo-obrigatorio` |
| W4-C2 | 50 mutações sequenciais | Cadeia de hash íntegra; `integro: true` |
| W4-C3 | Adulteração de `payload` via SQL direto | `/auditoria/verificar` aponta `seq_falha` correto |
| W4-C4 | `org.editor` fora do escopo | 403 |
| W4-C5 | `PUT /responsabilidades` executado 2× igual | Estado idêntico; 1 evento no ledger |

### W5 — Render invertido ⭐

**Entregáveis:** `layout.ts`, `OrgSvgCanvas`, `OrgConnectors`, `OrgCard`, tokens.

| # | Critério | PASS se |
|---|---|---|
| W5-C1 | Testes T-L01…T-L10 | 10/10 PASS |
| W5-C2 | Cobertura de `layout.ts` | 100 % linhas e branches |
| W5-C3 | Busca por `scaleY`, `scale(1,-1)`, `column-reverse` no bundle | 0 ocorrências (LAY-02) |
| W5-C4 | Seed de referência renderizado, invertido | `Y(Marina)` é o maior Y entre todos os cards |
| W5-C5 | Regressão visual Playwright | Diff < 0,1 % vs. baseline aprovado |
| W5-C6 | Todo `<path>` conector | 100 % com `fill="none"` (LAY-08) |
| W5-C7 | Alternância invertida ↔ vertical | Sem remontagem do DOM; só coordenadas mudam |

### W6 — Temporalidade

**Entregáveis:** timeline de vigências, endpoint `/historico`, seletor de data na UI.

| # | Critério | PASS se |
|---|---|---|
| W6-C1 | Consulta em data anterior à criação | 404 `organograma-inexistente-na-data` |
| W6-C2 | Troca de responsável em D | D-1 mostra o antigo; D mostra o novo |
| W6-C3 | `/historico` | Retorna apenas datas com mudança real |
| W6-C4 | Vigência aberta (`[D, )`) | Consulta em D+1000 retorna o registro |

### W7 — Exportação

**Entregáveis:** worker Playwright, rotas de export, PDF A3 paisagem.

| # | Critério | PASS se |
|---|---|---|
| W7-C1 | Export SVG | Abre no Inkscape; texto selecionável |
| W7-C2 | Export PNG @3x | Dimensões = 3× o viewBox, ±1 px |
| W7-C3 | Export PDF | Texto pesquisável (`pdftotext` extrai "Marina") |
| W7-C4 | Export de árvore de 200 nós | Conclui em < 20 s |
| W7-C5 | Cada export | 1 evento no ledger com identidade do solicitante |

### W8 — Acessibilidade e hardening

**Entregáveis:** ARIA completo, roving tabindex, modo lista, auditoria LGPD.

| # | Critério | PASS se |
|---|---|---|
| W8-C1 | axe-core WCAG 2.1 AA | 0 violações serious/critical |
| W8-C2 | `aria-level` da raiz, modo invertido | `= 1` (A11Y-02) |
| W8-C3 | Ordem de tabulação | Raiz é o primeiro nó tabulável |
| W8-C4 | Viewport 375 px | Modo lista ativo; sem scroll horizontal |
| W8-C5 | Contraste de conectores | ≥ 3:1 em tema claro e escuro |
| W8-C6 | Varredura de schema por campo proibido | 0 campos de remuneração/dado sensível (LGPD-01/02) |
| W8-C7 | `prefers-reduced-motion` | 0 transições ativas |

---

## 16. RED-TEAM — ACHADOS

| ID | Severidade | Achado | Mitigação |
|---|---|---|---|
| RT-01 | **CRÍTICA** | Inverter via `scaleY(-1)` espelha todo o texto e os ícones. É a implementação "óbvia" e está errada. | LAY-02 proíbe explicitamente; W5-C3 verifica no bundle. |
| RT-02 | **CRÍTICA** | Inverter a ordem do DOM para "combinar" com o visual destrói a hierarquia para leitor de tela — a raiz passaria a ser anunciada por último. | A11Y-02/03; W8-C2/C3. |
| RT-03 | **ALTA** | Área chamada "Remuneração Estratégica" convida escopo a crescer para dados salariais. | NOBJ-01 e LGPD-02 explícitos; W8-C6 varre o schema. |
| RT-04 | **ALTA** | Reparent sem transação corrompe a closure de forma silenciosa e irrecuperável. | `fn_mover_unidade` em transação única; W2-C4 property-based. |
| RT-05 | **ALTA** | Com > 6 irmãos, a largura estoura o viewport. Reduzir o card gera texto ilegível. | LAY-15 (modo lista) com piso rígido de 140 px. |
| RT-06 | **MÉDIA** | Ledger hash-encadeado com `IDENTITY` sofre lacuna de sequência em rollback — não é adulteração, mas dispara falso positivo. | Verificação valida a cadeia de hash, não a continuidade de `seq`. Documentar. |
| RT-07 | **MÉDIA** | "L.G.R." aparece na raiz e em Administração de Pessoal, sem definição em nenhum lugar. | Bloqueio de glossário: HG-03. |
| RT-08 | **MÉDIA** | "Documentação" é a única unidade sem verbo de gestão no nome e cujo escopo é suporte transversal — pode ser função de apoio, não área par. | HG-01 decide `tipo`. |
| RT-09 | **MÉDIA** | `EXCLUDE` em `alocacao` impede sucessão no mesmo dia (`[D,D)` é vazio, `[D,D+1)` colide com quem sai em D). | Convenção: quem sai tem vigência `[…, D)`; quem entra, `[D, …)`. Testar em W6-C2. |
| RT-10 | **BAIXA** | Export via Chromium headless pode divergir de fontes do desktop. | Fontes embarcadas no container; baseline visual congelado. |
| RT-11 | **BAIXA** | Excluir pessoa por requisição LGPD quebraria a integridade do ledger. | LGPD-04: anonimizar `nome_completo`/`email_corp`, preservar a linha e o histórico. |
| RT-12 | **BAIXA** | Delegação para não-descendente é permitida pelo `CHECK` atual. | INV-04 exige validação em camada de aplicação; promover a trigger se recorrer. |

---

## 17. HUMAN-GATE — DECISÕES PENDENTES 🚦

A implementação **NÃO DEVE** iniciar (W1) antes da resolução destes pontos.

| ID | Decisão | Opções | Impacto |
|---|---|---|---|
| **HG-01** | "Documentação / Elaine Moreira Lins" é área par ou função de apoio transversal? | (a) `tipo='area'`, filha direta — 5 filhos, como no slide · (b) `tipo='apoio'`, renderizada com traço tracejado fora do barramento | Layout e leitura da estrutura |
| **HG-02** | Modo de cabeçalho padrão | (a) `interno` — escalável, sem colisão (recomendado) · (b) `externo` — paridade visual com o slide, limitado a profundidade ≤ 1 | Fidelidade visual × escalabilidade |
| **HG-03** | Definir "L.G.R." | Sigla não identificada. Precisa entrar no glossário; se for termo interno, avaliar substituição por descrição legível | Clareza e RT-07 |
| **HG-04** | Escopo do piloto | (a) somente RH · (b) toda a empresa desde a W1 | Volume de seed e prazo da W3 |
| **HG-05** | Estrutura é pública na intranet ou restrita a RH + gestores? | (a) `org.viewer` para todo colaborador autenticado · (b) restrita | SEC-02 e superfície LGPD |
| **HG-06** | Grau de vinculação ao Odoo/eSocial | (a) cadastro manual na v1 · (b) sincronizar `org.pessoa` a partir da folha desde a W1 | Fonte de verdade de `pessoa` |

---

## 18. ANEXO A — PSEUDOCÓDIGO DO LAYOUT

```
FUNCAO calcularLayout(raiz, orientacao, tokens):
    # ---- fase 1: canônico, orientação-agnóstico ----
    hierarquia = d3.hierarchy(raiz)
    hierarquia.sort(por ordem_exibicao, depois nome, depois id)   # LAY-12
    alturas = mapa{ no.id -> max(CARD_H_MIN, alturaConteudo(no)) }
    tree = d3.tree().nodeSize([tokens.cardW + tokens.gapH, 1])
    tree(hierarquia)

    D      = hierarquia.height
    H_liv  = max(alturas.valores) + tokens.gapV

    # ---- fase 2: projeção ----
    PARA CADA no EM hierarquia.descendants():
        nivel = SE orientacao == 'invertida' ENTAO (D - no.depth) SENAO no.depth
        no.px = no.x + tokens.margem
        no.py = nivel * H_liv + tokens.margem
        no.ph = alturas[no.id]

        SE orientacao == 'invertida':
            no.ancoraPai   = (centroX(no), no.py)                 # topo
            no.ancoraFilho = (centroX(no), no.py + no.ph)         # base
        SENAO:
            no.ancoraPai   = (centroX(no), no.py + no.ph)
            no.ancoraFilho = (centroX(no), no.py)

    # ---- conectores ----
    PARA CADA pai COM filhos:
        SE contagem(filhos) == 1:                                  # LAY-06
            emitir path reto pai.ancoraPai -> filhos[0].ancoraFilho
            CONTINUE

        sinal   = SE orientacao == 'invertida' ENTAO -1 SENAO +1
        y_bus   = pai.ancoraPai.y + sinal * (tokens.gapV / 2)
        x_min   = min(f.ancoraFilho.x para f em filhos)
        x_max   = max(f.ancoraFilho.x para f em filhos)

        d  = "M {pai.ancoraPai.x} {pai.ancoraPai.y} V {y_bus}"
        d += " M {x_min} {y_bus} H {x_max}"                        # LAY-05
        PARA CADA f EM filhos:
            d += " M {f.ancoraFilho.x} {y_bus} V {f.ancoraFilho.y}"
        emitir { paiId: pai.id, d: arredondar2(d) }                # LAY-13

    # ---- viewBox pelo bbox real ----                             # LAY-14
    bbox = uniao(caixas de todos os nós)
    viewBox = [0, 0, bbox.largura + 2*margem, bbox.altura + 2*margem]

    RETORNAR { nos, conectores, viewBox, profundidadeMax: D }
```

**Verificação de sanidade (invariante testável):**
Em `orientacao = 'invertida'`, para todo par (pai, filho):
`Y(pai) > Y(filho) + altura(filho)` — o card do pai fica estritamente abaixo do card do filho, com folga.

---

## 19. ANEXO B — ESTRUTURA DO REPOSITÓRIO

```
gplansis-org/
├─ apps/
│  ├─ api/
│  │  ├─ src/org/
│  │  │  ├─ dominio/          # entidades, invariantes, valores
│  │  │  ├─ aplicacao/        # casos de uso (mover, realocar, exportar)
│  │  │  ├─ infra/            # SQLAlchemy, repositórios, ledger
│  │  │  └─ interface/        # routers FastAPI, schemas
│  │  ├─ migrations/
│  │  ├─ tests/
│  │  └─ pyproject.toml
│  ├─ web/
│  │  ├─ src/modules/org/     # ver §10.1
│  │  └─ package.json
│  └─ export-worker/
│     └─ src/                 # Playwright headless
├─ packages/
│  └─ contracts/              # OpenAPI 3.1 → tipos TS + modelos Pydantic
├─ docs/
│  ├─ adr/                    # ADR-001 … ADR-009
│  └─ SPEC-GPLANSIS-ORG-001.md
├─ compose.yaml
└─ Makefile
```

**Packaging vertical:** cada módulo carrega seu domínio, aplicação, infra e interface. Sem camadas horizontais globais (`/models`, `/services`, `/controllers`). Coerente com a arquitetura pragmática — abstração só onde há mais de uma implementação real.

---

## ADENDO 01 — CANVAS TWIN (HTMX)

**Status:** vigente · supersede parcialmente ADR-004 e ADR-005
**Motivo:** requisito de canvas editável e clicável, com ações por botão direito, sob a diretriz explícita de *sistema simples e funcional*.

---

### A1.1 ADR-010 — HTMX no lugar de React

**Contexto.** O produto é um editor de estrutura, não uma aplicação de estado rico. Toda mutação é discreta (renomear, adicionar, mover, excluir) e cada uma invalida o desenho inteiro, porque a posição de qualquer nó depende de toda a árvore. Não existe estado de cliente que sobreviva a uma mutação além de seleção, zoom e posição de pan.

**Decisão.** Servidor devolve HTML. Cada mutação responde com o fragmento `<svg id="canvas">` recalculado e trocado por `hx-swap="outerHTML"`. O painel lateral acompanha por *out-of-band swap*.

**Alternativas rejeitadas.**

- *React + TanStack Query* (ADR-004 original) — exigiria espelhar a árvore, o layout e as regras de ciclo no cliente. Duas implementações da mesma verdade, com deriva garantida entre elas.
- *React só para o canvas* — o pior dos dois: passo de build, e mesmo assim o servidor recalcula tudo.
- *HTMX com patch parcial de SVG* — otimização prematura. Uma árvore de 500 nós serializa em menos de 200 kB.

**Consequências.**

- Zero passo de build. Editar um `.html` e recarregar.
- Sem CDN: o htmx fica vendorizado em `vendor/`, condição de operação em rede fechada.
- O JS do cliente cabe em ~70 linhas e cuida apenas de efêmero: seleção, menu de contexto, pan, zoom.
- **Trade-off aceito:** toda mutação é um round-trip. Em LAN, imperceptível. Se algum dia houver arrasto contínuo de nós, esta decisão precisa ser reavaliada — arrasto a 60 fps não tolera round-trip por quadro.

**RNF-01 revisado:** p95 < 250 ms fim-a-fim (cálculo + render + troca), 500 nós, LAN.

---

### A1.2 ADR-011 — Layout no servidor

**Contexto.** FE-01 previa `calcularLayout` como função pura em TypeScript no cliente. Com ADR-010, o SVG nasce no servidor.

**Decisão.** O motor de layout é `calcular_layout()` em Python, único produtor de geometria em todo o sistema.

**Consequência positiva não prevista na v1.0:** o export (W7) deixa de precisar de Chromium headless. A rota `/export.svg` renderiza **exatamente o mesmo template** que a tela. Paridade visual entre tela e arquivo passa de garantia por teste de regressão a garantia estrutural. **ADR-007 fica obsoleto** e o worker Playwright sai do escopo.

**Consequência negativa:** os testes de layout migram de Vitest para pytest. RNF-05 mantém a exigência de 100 % de cobertura em `calcular_layout`.

---

### A1.3 Contrato de interação (normativo)

| ID | Regra |
|---|---|
| **INT-01** | Todo alvo de HTMX **DEVE** ser `#canvas` (`outerHTML`) ou `#painel` (`innerHTML`). Nenhum outro alvo é permitido. |
| **INT-02** | Mutação que altera a seleção **DEVE** sincronizar `#painel` por `hx-swap-oob`, jamais por segunda requisição. |
| **INT-03** | O menu de contexto **DEVE** ser buscado do servidor a cada abertura (`GET /fragmentos/menu/{id}`). Ações inválidas para o nó chegam já desabilitadas — o cliente **NÃO DEVE** decidir habilitação. |
| **INT-04** | Ações destrutivas **DEVEM** portar `hx-confirm`. |
| **INT-05** | Zoom, pan e posição do menu **DEVEM** viver apenas no cliente e **NÃO DEVEM** ser reiniciados por troca de fragmento. |
| **INT-06** | Recusa de regra de negócio (ciclo) **DEVE** responder 200 com o canvas inalterado mais um alerta, não 4xx — o HTMX não troca conteúdo em erro por padrão, e um 4xx silencioso deixaria o usuário sem retorno. |
| **INT-07** | O `#canvas` **DEVE** permanecer um `<svg>` autocontido, com `<style>` interno, para que a mesma serialização sirva à tela e ao arquivo exportado. |

### A1.4 Ações do menu de contexto

| Ação | Rota | Regra |
|---|---|---|
| Editar dados | `GET /fragmentos/painel/{id}` | sempre disponível |
| Adicionar subordinado | `POST /unidades/{id}/filho` | sempre disponível; abre o painel do novo nó |
| Duplicar | `POST /unidades/{id}/duplicar` | bloqueado na raiz |
| Mover ← / → | `POST /unidades/{id}/reordenar` | bloqueado nos extremos e na raiz |
| Promover um nível | `POST /unidades/{id}/promover` | exige avô; vira irmão do pai |
| Rebaixar um nível | `POST /unidades/{id}/rebaixar` | exige irmão anterior; vira filho dele |
| Excluir | `DELETE /unidades/{id}` | bloqueado na raiz; filhos sobem ao avô |

Reparent arbitrário (`POST /unidades/{id}/mover`) passa pela guarda de ciclo (RF-02 / INV-02): destino igual ao nó ou descendente dele é recusado.

### A1.5 Elemento-assinatura — cota de nível

Trilho vertical cotado à esquerda do canvas, com marcas em cada faixa e rótulos `N0…Nx`. `N0` recebe marcador sólido âmbar. Na orientação invertida, `N0` fica na **base**, tornando a inversão legível sem legenda.

- **SIG-01** — O trilho **DEVE** cobrir toda a extensão vertical do desenho.
- **SIG-02** — Os rótulos **DEVEM** refletir a profundidade lógica; a inversão muda a posição na tela, nunca o número.
- **SIG-03** — O trilho **DEVE** portar `aria-hidden="true"`. É reforço visual de informação já exposta em `aria-level`.

---

### A1.6 Onda W9 — Canvas editável

**Entregáveis:** motor de layout em Python, fragmentos Jinja, menu de contexto, barra de ferramentas, painel de edição, navegação entre vistas, desfazer, exportação.

| # | Critério | PASS se | Resultado |
|---|---|---|---|
| W9-C1 | Adicionar subordinado | nó criado e painel aberto por OOB | **PASS** |
| W9-C2 | Salvar painel com prefixo `>` | item gravado com `origem = delegada` | **PASS** |
| W9-C3 | Rebaixar | vira filho do irmão anterior | **PASS** |
| W9-C4 | Profundidade cresce | novo nível gera faixa e barramento próprios | **PASS** |
| W9-C5 | Promover | volta a responder ao avô | **PASS** |
| W9-C6 | Reordenar irmãos | ordem muda e é renumerada em múltiplos de 10 | **PASS** |
| W9-C7 | Duplicar | cópia com novo código, sem responsável | **PASS** |
| W9-C8 | Excluir | filhos sobem ao avô e o painel é limpo | **PASS** |
| W9-C9 | Excluir raiz | recusado, estrutura intacta | **PASS** |
| W9-C10 | Desfazer | restaura o snapshot anterior | **PASS** |
| W2-C2 | Guarda de ciclo | destino descendente é recusado com alerta | **PASS** |
| W4-C2 | Cadeia de auditoria | íntegra após a sequência completa de mutações | **PASS** |
| W5-C4 | Invariante da inversão | `Y(raiz) > Y(filho) + altura(filho)` para todos | **PASS** |
| W5-C7 | Alternar orientação | relação de Y espelha, DOM inalterado | **PASS** |
| RNF-02 | Determinismo | duas renderizações idênticas byte a byte | **PASS** |
| LAY-02 | Sem espelhamento | zero ocorrências de `scaleY` / `scale(1,-1)` | **PASS** |
| LAY-08 | Conectores | 100 % com `fill="none"` | **PASS** |
| A11Y-02 | Nível da raiz | `aria-level="1"` na orientação invertida | **PASS** |

**Resultado da onda: 18 PASS / 0 FAIL.**

### A1.7 Débito técnico assumido

Itens conscientemente adiados para manter o sistema simples e funcional:

| # | Débito | Onda de destino |
|---|---|---|
| DT-01 | Persistência em arquivo JSON, não PostgreSQL. `schema.sql` já entregue; falta o repositório. | W10 |
| DT-02 | Sem autenticação. `X-Motivo` é preenchido pelo servidor, não pelo operador (API-05 parcialmente atendido). | W10 |
| DT-03 | Estado global de processo único. Não sobrevive a múltiplos workers uvicorn. | W10 |
| DT-04 | Temporalidade (W6) não exposta na UI. O modelo suporta; a tela ainda não. | W6 |
| DT-05 | Modo lista para viewport estreita (LAY-15) não implementado; abaixo de 900 px o painel vira gaveta, mas o canvas continua exigindo pan. | W8 |
| DT-06 | Export PNG/PDF ausente. SVG e JSON entregues. | W7 |

Nenhum desses débitos bloqueia o uso do canvas para modelar e revisar a estrutura.


---

**FIM DA SPEC — SPEC-GPLANSIS-ORG-001 v1.1.0**
*W5' e W9 entregues (18 PASS / 0 FAIL). HUMAN-GATE HG-01 … HG-06 seguem abertos para as ondas de dados.*
