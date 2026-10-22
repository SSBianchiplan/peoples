-- Migração 009 — o login próprio e o resto do estado no banco.
--
-- O schema.sql só roda no volume vazio do Postgres; um banco que já existe
-- recebe isto. IDEMPOTENTE: rodar duas vezes não quebra nem duplica.
--
-- 1. org.usuario — as credenciais do login do PRÓPRIO sistema (e-mail + hash
--    scrypt). Sem SSO: quem prova identidade é este registro. É GLOBAL (não tem
--    slug): uma senha vale para todos os organogramas. Papel e escopo NÃO moram
--    aqui — seguem no RBAC do organograma (Config.acessos), no estado.
--
-- 2. org.estado_extra — tudo o que o estado.json guarda e que não tinha tabela
--    própria: configuração (níveis, catálogo de cargos, centros de custo, RBAC,
--    card, tema…), colapso, orientação, filtros, provisionamentos, mural e o log
--    de acessos. Um documento JSONB por organograma, espelhado a cada gravação
--    (dual-write, guardado por assinatura, não-fatal — o mesmo desenho da
--    estrutura e do ledger). Com ele, o banco passa a ter o sistema INTEIRO, e
--    `carregar()` restaura tudo quando o estado.json não existe.
--
--   psql -U <user> -d <db> -f 009-usuarios-e-estado.sql
BEGIN;

CREATE TABLE IF NOT EXISTS org.usuario (
    email          citext PRIMARY KEY CHECK (email ~ '^[^@\s]+@[^@\s]+$'),
    senha_hash     text NOT NULL,
    ativo          boolean NOT NULL DEFAULT true,
    precisa_trocar boolean NOT NULL DEFAULT false,
    definida_por   text NOT NULL DEFAULT '',
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS org.estado_extra (
    slug           text PRIMARY KEY,
    dados          jsonb NOT NULL DEFAULT '{}'::jsonb,
    assinatura     text NOT NULL DEFAULT '',
    atualizado_em  timestamptz NOT NULL DEFAULT now()
);

COMMIT;
