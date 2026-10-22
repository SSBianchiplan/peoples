-- Migração 011 — a resposta de clima ganha uma CHAVE estável (o id do overlay).
--
-- O banco gerava o próprio uuid e não guardava o id da resposta em memória.
-- Consequências reais: `fundir` não reconhecia a resposta já espelhada e a
-- contava em dobro no painel (participação > 100%), e cada novo espelhamento
-- inseria tudo de novo. Com `chave` única por organograma o INSERT vira UPSERT,
-- e a leitura devolve a mesma identidade que o overlay usa. IDEMPOTENTE.
--
--   psql -U <user> -d <db> -f 011-gptw-chave.sql
BEGIN;
ALTER TABLE org.gptw_resposta ADD COLUMN IF NOT EXISTS chave text;
CREATE UNIQUE INDEX IF NOT EXISTS ux_gptw_chave ON org.gptw_resposta (slug, chave) WHERE chave IS NOT NULL;
COMMIT;
