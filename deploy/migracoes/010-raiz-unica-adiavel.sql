-- Migração 010 — a raiz única passa a ser conferida no COMMIT, não a cada linha.
--
-- O índice parcial `ux_unidade_raiz_unica` (organograma_id WHERE parent_id IS
-- NULL) rejeitava a carga sempre que a raiz MUDAVA: inserir a raiz nova (pai
-- NULL) enquanto a antiga ainda estava com pai NULL violava o índice no meio
-- da transação — e o espelho (dual-write) falhava, "não-fatal", deixando o
-- banco para trás. Índice parcial não é adiável; uma EXCLUDE constraint com o
-- mesmo predicado é: a regra continua "uma raiz por organograma", conferida
-- quando a transação inteira já está coerente.
--
-- IDEMPOTENTE.   psql -U <user> -d <db> -f 010-raiz-unica-adiavel.sql
BEGIN;

DROP INDEX IF EXISTS org.ux_unidade_raiz_unica;
ALTER TABLE org.unidade DROP CONSTRAINT IF EXISTS ex_unidade_raiz_unica;
ALTER TABLE org.unidade
  ADD CONSTRAINT ex_unidade_raiz_unica
  EXCLUDE USING btree (organograma_id WITH =) WHERE (parent_id IS NULL)
  DEFERRABLE INITIALLY DEFERRED;

COMMIT;
