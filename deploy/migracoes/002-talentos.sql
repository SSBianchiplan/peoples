-- Migração 002 — tabela da Avaliação (GEP-FOR-004).
--
-- O schema.sql só roda no volume vazio do Postgres; o banco de produção já
-- existe e não o recebe. Esta migração acrescenta org.mapa_talento, e é
-- IDEMPOTENTE: rodar duas vezes não quebra nem duplica. Traz o que o v1.2.0
-- introduz — a leitura de sucessão do RH sobre cada pessoa, um registro por
-- (organograma, matrícula, ano).
--
--   psql -U <user> -d <db> -f 002-talentos.sql
BEGIN;

-- Avaliação: risco/impacto de perda (o 9-box), prontidão de sucessão,
-- ação imediata (o insumo do Comitê de Meritocracia) e o texto rico em JSONB.
CREATE TABLE IF NOT EXISTS org.mapa_talento (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug           text NOT NULL,
    ref            text NOT NULL,
    ano            smallint NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    risco_perda    text NOT NULL DEFAULT '',
    impacto_perda  text NOT NULL DEFAULT '',
    prontidao      text NOT NULL DEFAULT '',
    acao           text NOT NULL DEFAULT '',
    conteudo       jsonb NOT NULL DEFAULT '{}'::jsonb,
    pessoa_nome    text NOT NULL DEFAULT '',
    pessoa_cargo   text NOT NULL DEFAULT '',
    lider_nome     text NOT NULL DEFAULT '',
    registrado_por text NOT NULL DEFAULT '',
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_mapa_talento UNIQUE (slug, ref, ano)
);
CREATE INDEX IF NOT EXISTS ix_mapa_talento ON org.mapa_talento (slug, ref, ano DESC);

COMMIT;
