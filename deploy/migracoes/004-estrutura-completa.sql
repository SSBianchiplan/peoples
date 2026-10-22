-- 004 — Fidelidade do espelho da estrutura (Onda DB-1).
--
-- Até aqui a carga (banco.sql_carga) escrevia um nó pela metade: `area`,
-- `centro_custo`, `vertical`, `responsavel` e `competencias` viviam só na tela
-- (estado.json), e nenhuma coluna guardava a identidade do nó em memória. Ler a
-- estrutura de volta do banco (Onda DB-3) perderia esses cinco campos e não
-- saberia reconstruir os ids — em planilha o id é um hash do NOME, não o código,
-- e `colapsados`, eventos e provisionamentos apontam para esse id.
--
-- Esta migração torna o espelho fiel (round-trip sem perda). Idempotente: roda
-- quantas vezes precisar. O schema.sql já nasce com estas colunas; aqui é para o
-- banco de produção que já existe.
ALTER TABLE org.unidade
  ADD COLUMN IF NOT EXISTS origem_id    text,
  ADD COLUMN IF NOT EXISTS area         text,
  ADD COLUMN IF NOT EXISTS centro_custo text,
  ADD COLUMN IF NOT EXISTS vertical     text,
  ADD COLUMN IF NOT EXISTS responsavel  text,
  ADD COLUMN IF NOT EXISTS competencias jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS ux_unidade_origem
  ON org.unidade (organograma_id, origem_id) WHERE origem_id IS NOT NULL;
