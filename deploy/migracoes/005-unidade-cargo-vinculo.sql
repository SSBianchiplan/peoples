-- 005 — cargo e vínculo no próprio nó (fecha o round-trip da raiz, Onda DB-3).
--
-- A 004 trouxe área/CC/vertical/responsável/competências/origem_id para
-- org.unidade, mas cargo e vínculo continuavam só em org.alocacao — e a raiz
-- sintética não é pessoa, não tem alocação, então o cargo dela ("Conselho de
-- administração") não voltava do banco. Enquanto a leitura vinha do estado.json
-- isso não aparecia; com o banco virando a fonte da leitura (Onda DB-3), a raiz
-- perderia o cargo no arranque.
--
-- Guardar cargo/vínculo no nó torna o espelho 100% fiel — a estrutura volta
-- INTEIRA, a raiz inclusive. org.alocacao segue como a visão normalizada (com
-- vigência), preenchida pela mesma carga. Idempotente.
ALTER TABLE org.unidade
  ADD COLUMN IF NOT EXISTS cargo   text,
  ADD COLUMN IF NOT EXISTS vinculo org.vinculo;
