-- Migração 003 — tabela do Peoples Place to Work (pesquisa de clima anônima).
--
-- O schema.sql só roda no volume vazio do Postgres; o banco de produção já
-- existe e não o recebe. Esta migração acrescenta org.gptw_resposta, e é
-- IDEMPOTENTE: rodar duas vezes não quebra nem duplica. Traz o que o v1.2.0
-- introduz — a resposta anônima da pesquisa de clima, ligada ao sistema pelos
-- estratos (nível, área, vínculo, faixa de casa), NUNCA pela identidade.
--
--   psql -U <user> -d <db> -f 003-gptw.sql
BEGIN;

-- Peoples Place to Work: uma linha por envio, anônima. As respostas Likert e as
-- abertas em JSONB; os estratos derivados do organograma; sem coluna de pessoa.
CREATE TABLE IF NOT EXISTS org.gptw_resposta (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            text NOT NULL,
    ciclo           text NOT NULL,
    ano             smallint NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    respostas       jsonb NOT NULL DEFAULT '{}'::jsonb,
    abertas         jsonb NOT NULL DEFAULT '{}'::jsonb,
    estrato_nivel   text,
    estrato_area    text,
    estrato_vinculo text,
    estrato_faixa   text,
    modelo_trabalho text,
    criado_em       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_gptw_ciclo ON org.gptw_resposta (slug, ano DESC, ciclo);

COMMIT;
