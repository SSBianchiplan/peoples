-- ===========================================================================
-- GPlanSiS|Peoples - migration 001_org_baseline
-- SPEC-GPLANSIS-ORG-001 secao 7. Alvo: PostgreSQL 18.
-- O app roda em memoria + JSON por padrao; este schema e o alvo de producao.
-- ===========================================================================
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE SCHEMA IF NOT EXISTS org;

CREATE TYPE org.tipo_unidade  AS ENUM ('diretoria','gerencia','coordenacao','area','celula','apoio');
CREATE TYPE org.papel_alocacao AS ENUM ('responsavel','membro','interino','apoio');
CREATE TYPE org.origem_responsabilidade AS ENUM ('propria','delegada','compartilhada');

CREATE TABLE org.organograma (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug              citext NOT NULL UNIQUE
                      CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$'),
    nome              text NOT NULL,
    orientacao_padrao text NOT NULL DEFAULT 'invertida'
                      CHECK (orientacao_padrao IN ('invertida','vertical','lateral')),
    ativo             boolean NOT NULL DEFAULT true,
    criado_em         timestamptz NOT NULL DEFAULT now(),
    atualizado_em     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE org.pessoa (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matricula     text UNIQUE,
    nome_completo text NOT NULL CHECK (char_length(btrim(nome_completo)) BETWEEN 2 AND 160),
    nome_exibicao text NOT NULL CHECK (char_length(btrim(nome_exibicao)) BETWEEN 2 AND 60),
    email_corp    citext UNIQUE,
    avatar_url    text,
    ativo         boolean NOT NULL DEFAULT true,
    criado_em     timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);
-- LGPD-01/02: proibido CPF, RG, endereco, dado de saude e qualquer remuneracao.

CREATE TABLE org.unidade (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organograma_id uuid NOT NULL REFERENCES org.organograma(id) ON DELETE CASCADE,
    codigo         text NOT NULL,
    nome           text NOT NULL CHECK (char_length(btrim(nome)) BETWEEN 2 AND 80),
    nome_curto     text,
    tipo           org.tipo_unidade NOT NULL,
    parent_id      uuid REFERENCES org.unidade(id) ON DELETE RESTRICT,
    ordem_exibicao smallint NOT NULL DEFAULT 0,
    ativo          boolean NOT NULL DEFAULT true,
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_unidade_codigo UNIQUE (organograma_id, codigo),
    CONSTRAINT ck_unidade_nao_autopai CHECK (parent_id IS DISTINCT FROM id)
);
CREATE UNIQUE INDEX ux_unidade_raiz_unica ON org.unidade (organograma_id) WHERE parent_id IS NULL;
CREATE INDEX ix_unidade_parent ON org.unidade (parent_id, ordem_exibicao);

CREATE TABLE org.unidade_closure (
    ancestral_id   uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    descendente_id uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    profundidade   smallint NOT NULL CHECK (profundidade >= 0),
    PRIMARY KEY (ancestral_id, descendente_id)
);
CREATE INDEX ix_closure_desc ON org.unidade_closure (descendente_id, profundidade);

CREATE TABLE org.alocacao (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unidade_id uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    pessoa_id  uuid NOT NULL REFERENCES org.pessoa(id)  ON DELETE RESTRICT,
    papel      org.papel_alocacao NOT NULL,
    cargo      text,
    vigencia   daterange NOT NULL DEFAULT daterange(CURRENT_DATE, NULL, '[)'),
    criado_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_alocacao_vigencia CHECK (NOT isempty(vigencia)),
    CONSTRAINT ex_alocacao_responsavel_unico
        EXCLUDE USING gist (unidade_id WITH =, vigencia WITH &&) WHERE (papel = 'responsavel')
);

CREATE TABLE org.responsabilidade (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unidade_id uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    descricao  text NOT NULL CHECK (char_length(btrim(descricao)) BETWEEN 2 AND 200),
    origem     org.origem_responsabilidade NOT NULL DEFAULT 'propria',
    delegada_para_unidade_id uuid REFERENCES org.unidade(id) ON DELETE SET NULL,
    ordem      smallint NOT NULL DEFAULT 0,
    vigencia   daterange NOT NULL DEFAULT daterange(CURRENT_DATE, NULL, '[)'),
    criado_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_resp_delegacao_coerente
        CHECK ((origem = 'delegada') = (delegada_para_unidade_id IS NOT NULL)),
    CONSTRAINT ck_resp_nao_autodelegada
        CHECK (delegada_para_unidade_id IS DISTINCT FROM unidade_id)
);
CREATE INDEX ix_resp_unidade ON org.responsabilidade (unidade_id, ordem);

CREATE TABLE org.evento (
    seq           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ocorrido_em   timestamptz NOT NULL DEFAULT clock_timestamp(),
    ator          text NOT NULL,
    acao          text NOT NULL CHECK (acao IN ('criar','alterar','mover','inativar','realocar')),
    entidade      text NOT NULL,
    entidade_id   uuid NOT NULL,
    motivo        text NOT NULL CHECK (char_length(btrim(motivo)) BETWEEN 5 AND 200),
    payload       jsonb NOT NULL,
    hash_anterior bytea,
    hash          bytea NOT NULL
);

-- Guardas, closure e encadeamento de hash: ver SPEC secoes 7.1 e 7.2.
