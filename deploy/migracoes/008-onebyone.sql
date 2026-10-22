-- Migração 008 — tabela do One-on-One (1:1 / PRM / desenvolvimento por pessoa).
--
-- O schema.sql só roda no volume vazio do Postgres; o banco de produção já
-- existe e não o recebe. Esta migração acrescenta org.onebyone_item, e é
-- IDEMPOTENTE: rodar duas vezes não quebra nem duplica. Traz o que o v1.7.0
-- introduz — as conversas 1:1 (FUP), rocks, issues, objetivos do trimestre,
-- missões de evolução, pulso e ciclo de vida, um item por id.
--
-- SIGILO (LGPD, nível pessoa): cada item pertence ao liderado (ref) e ao líder
-- que o escreveu (lider_ref) — as duas matrículas participantes. A leitura é
-- filtrada na aplicação (só participantes ou RH/compliance); o banco guarda as
-- matrículas para que a ACL sobreviva à recriação de ids na reimportação.
--
--   psql -U <user> -d <db> -f 008-onebyone.sql
BEGIN;

CREATE TABLE IF NOT EXISTS org.onebyone_item (
    id             text NOT NULL,
    slug           text NOT NULL,
    tipo           text NOT NULL,
    ref            text NOT NULL,
    lider_ref      text NOT NULL DEFAULT '',
    ano            smallint NOT NULL DEFAULT 0 CHECK (ano = 0 OR ano BETWEEN 2000 AND 2100),
    trimestre      smallint NOT NULL DEFAULT 0 CHECK (trimestre BETWEEN 0 AND 4),
    data_item      date,
    conteudo       jsonb NOT NULL DEFAULT '{}'::jsonb,
    pessoa_nome    text NOT NULL DEFAULT '',
    pessoa_cargo   text NOT NULL DEFAULT '',
    lider_nome     text NOT NULL DEFAULT '',
    registrado_por text NOT NULL DEFAULT '',
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_onebyone PRIMARY KEY (slug, id)
);
CREATE INDEX IF NOT EXISTS ix_onebyone_pessoa ON org.onebyone_item (slug, ref, tipo);
CREATE INDEX IF NOT EXISTS ix_onebyone_lider ON org.onebyone_item (slug, lider_ref);

COMMIT;
