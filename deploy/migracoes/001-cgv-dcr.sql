-- Migração 001 — tabelas da Conversa de Valor e do Skills overlay.
--
-- O schema.sql só roda no volume vazio do Postgres. Bancos que já existem — como
-- o de produção — não recebem as tabelas novas por ele. Esta migração as
-- acrescenta, e é IDEMPOTENTE: rodar duas vezes não quebra nem duplica. Aplica o
-- que faltou do v1.0.0 (org.cgv_registro) e o que o v1.1.0 traz (a coluna
-- conteudo e a org.dcr_overlay).
--
--   psql -U <user> -d <db> -f 001-cgv-dcr.sql
BEGIN;

-- Tipos: CREATE TYPE não tem IF NOT EXISTS; o DO/EXCEPTION cobre o caso de já
-- existirem.
DO $$ BEGIN
  CREATE TYPE org.cgv_ciclo AS ENUM ('completa','checkin1','checkin2');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TYPE org.cgv_status AS ENUM ('pendente','agendada','realizada');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Conversa de Valor: uma linha por (organograma, matrícula, ano, ciclo), com o formulário
-- inteiro em JSONB.
CREATE TABLE IF NOT EXISTS org.cgv_registro (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug           text NOT NULL,
    ref            text NOT NULL,
    ano            smallint NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    ciclo          org.cgv_ciclo NOT NULL,
    status         org.cgv_status NOT NULL DEFAULT 'pendente',
    data_conversa  date,
    nota           text NOT NULL DEFAULT '',
    conteudo       jsonb NOT NULL DEFAULT '{}'::jsonb,
    pessoa_nome    text NOT NULL DEFAULT '',
    pessoa_cargo   text NOT NULL DEFAULT '',
    lider_nome     text NOT NULL DEFAULT '',
    registrado_por text NOT NULL DEFAULT '',
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_cgv_conversa UNIQUE (slug, ref, ano, ciclo)
);
-- Caso a tabela já existisse sem a coluna (banco a meio caminho): garante-a.
ALTER TABLE org.cgv_registro
    ADD COLUMN IF NOT EXISTS conteudo jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS ix_cgv_pessoa ON org.cgv_registro (slug, ref, ano DESC);
CREATE INDEX IF NOT EXISTS ix_cgv_ano ON org.cgv_registro (slug, ano DESC, ciclo);

-- Skills: a descrição de cargo que o RH escreve, uma por função.
CREATE TABLE IF NOT EXISTS org.dcr_overlay (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug               text NOT NULL,
    ref                text NOT NULL,
    cargo              text NOT NULL,
    missao             text NOT NULL DEFAULT '',
    responsabilidades  text NOT NULL DEFAULT '',
    requisitos         text NOT NULL DEFAULT '',
    competencias       text NOT NULL DEFAULT '',
    registrado_por     text NOT NULL DEFAULT '',
    criado_em          timestamptz NOT NULL DEFAULT now(),
    atualizado_em      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_dcr_overlay UNIQUE (slug, ref)
);
CREATE INDEX IF NOT EXISTS ix_dcr_overlay ON org.dcr_overlay (slug, ref);

COMMIT;
