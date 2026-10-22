-- 006 — o ledger durável no banco (Onda DB-4).
--
-- org.evento foi desenhada com entidade_id uuid e hash bytea, que não casam com
-- o ledger real do app (id de 12 hex; hash em hexadecimal) — e nunca foi
-- preenchida. Além disso guardava a data como timestamptz, mas a string ISO
-- exata de `quando` entra no corpo do hash: reformatá-la na volta quebraria a
-- cadeia. Como a tabela está VAZIA, recria no formato fiel e por-organograma.
--
-- Idempotente e seguro: só recria se ainda estiver no formato antigo (sem a
-- coluna `quando`) E estiver vazia. Se um dia tiver dados no formato antigo,
-- não apaga nada — para para tratamento manual.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema = 'org' AND table_name = 'evento'
                   AND column_name = 'quando') THEN
    IF EXISTS (SELECT 1 FROM org.evento) THEN
      RAISE EXCEPTION 'org.evento tem dados no formato antigo; migre à mão';
    END IF;
    DROP TABLE IF EXISTS org.evento CASCADE;
    CREATE TABLE org.evento (
        organograma_id uuid NOT NULL REFERENCES org.organograma(id) ON DELETE CASCADE,
        seq            bigint NOT NULL,
        quando         text NOT NULL,
        ator           text NOT NULL,
        acao           text NOT NULL,
        entidade       text NOT NULL DEFAULT 'unidade',
        entidade_id    text NOT NULL,
        motivo         text NOT NULL,
        payload        jsonb NOT NULL,
        hash_anterior  text,
        hash           text NOT NULL,
        registrado_em  timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (organograma_id, seq)
    );
    CREATE UNIQUE INDEX ux_evento_hash ON org.evento (organograma_id, hash);
  END IF;
END $$;
