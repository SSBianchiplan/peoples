-- ===========================================================================
--  GPlanSiS · LAKEHOUSE — a base intermediária do hub
-- ===========================================================================
--  POR QUE ELE EXISTE
--
--  Cada sistema do hub tem o seu banco e é dono dele. Ninguém escreve no banco
--  do outro — nem por engano, nem por conveniência de relatório. Quando um
--  sistema precisa de dado alheio, ele lê AQUI: um banco separado, alimentado
--  por processos de carga que só têm permissão de LEITURA na origem.
--
--      peoples  ──(SELECT, papel `peoples_leitor`)──▶  ETL  ──▶  lakehouse
--      prioria  ──(SELECT, papel próprio)───────────▶  ETL  ──▶  bronze.<sistema>_*
--      pcp/aps  ──(SELECT, papel próprio)───────────▶  ETL  ──▶       │
--                                                                    ▼
--      qualquer sistema/BI ──(SELECT, papel `lake_leitor`)──▶  gold.* + API
--
--  TRÊS CAMADAS, e cada uma responde uma pergunta diferente
--
--    bronze — o retrato cru de cada origem, por snapshot. Uma linha por
--             registro por carga; nada é reescrito, nada é interpretado.
--             Prefixo do sistema no nome: `bronze.peoples_pessoa`.
--    silver — o conformado: uma linha por entidade de negócio, com os campos
--             já padronizados entre sistemas e o vocabulário do hub. É onde
--             "colaborador" quer dizer a mesma coisa vindo do Peoples ou do PCP.
--    gold   — as métricas prontas para consumo: indicadores de gente, cobertura
--             dos rituais, 9-box, clima. É o que a API e os painéis leem.
--
--  REGRAS DA CASA (impostas por permissão, não por combinado)
--
--   1. O lakehouse NUNCA escreve na origem. O papel de carga tem SELECT e nada
--      mais no banco de origem.
--   2. Consumidor NUNCA escreve no lakehouse. `lake_leitor` tem SELECT apenas
--      em `gold` (e em `silver`, quando o caso pede detalhe).
--   3. Toda linha carrega `carregado_em` e `origem` — sem isso não há como
--      saber se um número está velho, e número velho decide errado.
--   4. Sem dado pessoal sensível: o lakehouse recebe o que o Peoples já
--      publica (LGPD-01/02 — nada de remuneração, CPF, endereço ou saúde). As
--      respostas de clima entram apenas agregadas, nunca linha a linha.
--
--   psql -U lake -d gplansis_lake -f schema-lake.sql      (idempotente)
-- ===========================================================================
BEGIN;

-- `unaccent` casa o cargo da estrutura com a chave da ficha Skills sem depender
-- de acentuação. Está disponível no cluster; sem ela o casamento erraria em
-- "Técnico" vs "Tecnico" e a cobertura sairia menor do que é.
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

COMMENT ON SCHEMA bronze IS 'Retrato cru de cada sistema de origem, por snapshot. Só o ETL escreve.';
COMMENT ON SCHEMA silver IS 'Entidades conformadas do hub — vocabulário único entre sistemas.';
COMMENT ON SCHEMA gold   IS 'Métricas prontas. É o que a API e os painéis leem.';

-- ---------------------------------------------------------------------------
-- CONTROLE DE CARGA — a trilha de quem trouxe o quê, quando e de onde
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.carga (
    id            bigserial PRIMARY KEY,
    sistema       text NOT NULL,              -- peoples, prioria, pcp…
    dominio       text NOT NULL,              -- o organograma/slug, projeto, planta…
    iniciada_em   timestamptz NOT NULL DEFAULT now(),
    concluida_em  timestamptz,
    ok            boolean,
    linhas        jsonb NOT NULL DEFAULT '{}'::jsonb,   -- {tabela: n}
    erro          text,
    versao_etl    text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_carga_sistema ON bronze.carga (sistema, iniciada_em DESC);

-- ---------------------------------------------------------------------------
-- BRONZE · PEOPLES — o retrato cru, uma linha por registro por carga
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.peoples_pessoa (
    carga_id      bigint NOT NULL REFERENCES bronze.carga(id) ON DELETE CASCADE,
    slug          text NOT NULL,
    origem_id     text NOT NULL,
    codigo        text,
    nome          text,
    email         text,
    cargo         text,
    nivel         text,
    area          text,
    centro_custo  text,
    vertical      text,
    vinculo       text,
    admissao      date,
    situacao      text,
    parent_origem text,
    ordem         integer,
    competencias  jsonb NOT NULL DEFAULT '[]'::jsonb,
    carregado_em  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (carga_id, slug, origem_id)
);

CREATE TABLE IF NOT EXISTS bronze.peoples_responsabilidade (
    carga_id     bigint NOT NULL REFERENCES bronze.carga(id) ON DELETE CASCADE,
    slug         text NOT NULL,
    origem_id    text NOT NULL,
    seq          integer NOT NULL,
    descricao    text NOT NULL,
    origem_tipo  text NOT NULL,               -- propria | delegada
    carregado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (carga_id, slug, origem_id, seq)
);

CREATE TABLE IF NOT EXISTS bronze.peoples_skills (
    carga_id     bigint NOT NULL REFERENCES bronze.carga(id) ON DELETE CASCADE,
    slug         text NOT NULL,
    ref          text NOT NULL,               -- chave da função (cargo normalizado)
    cargo        text NOT NULL,
    missao       text,
    responsabilidades text,
    requisitos   text,
    competencias text,
    carregado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (carga_id, slug, ref)
);

CREATE TABLE IF NOT EXISTS bronze.peoples_conversa_valor (
    carga_id     bigint NOT NULL REFERENCES bronze.carga(id) ON DELETE CASCADE,
    slug         text NOT NULL,
    ref          text NOT NULL,
    ano          smallint NOT NULL,
    ciclo        text NOT NULL,
    status       text NOT NULL,
    data_conversa date,
    lider_nome   text,
    elementos    smallint NOT NULL DEFAULT 0, -- quantos dos 5 elementos têm texto
    pdi_itens    smallint NOT NULL DEFAULT 0,
    carregado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (carga_id, slug, ref, ano, ciclo)
);

CREATE TABLE IF NOT EXISTS bronze.peoples_avaliacao (
    carga_id      bigint NOT NULL REFERENCES bronze.carga(id) ON DELETE CASCADE,
    slug          text NOT NULL,
    ref           text NOT NULL,
    ano           smallint NOT NULL,
    risco_perda   text,
    impacto_perda text,
    prontidao     text,
    acao          text,
    carregado_em  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (carga_id, slug, ref, ano)
);

-- Clima entra AGREGADO: nunca a resposta individual, nem no bronze. O piso de
-- 5 respondentes por estrato é aplicado na origem, antes de chegar aqui.
CREATE TABLE IF NOT EXISTS bronze.peoples_clima_agregado (
    carga_id     bigint NOT NULL REFERENCES bronze.carga(id) ON DELETE CASCADE,
    slug         text NOT NULL,
    ano          smallint NOT NULL,
    ciclo        text NOT NULL,
    dimensao     text NOT NULL,               -- geral | pilar | nivel | area | vinculo | faixa | modelo
    chave        text NOT NULL,
    respondentes integer NOT NULL,
    pti          numeric(5,2),
    carregado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (carga_id, slug, ano, ciclo, dimensao, chave)
);

-- ---------------------------------------------------------------------------
-- SILVER · o conformado — a última carga OK de cada sistema/domínio
-- ---------------------------------------------------------------------------
-- A última carga OK de cada SISTEMA. Por sistema, e não por (sistema, domínio):
-- o ETL traz todos os domínios do sistema numa transação só, então a carga é a
-- unidade atômica. Casar por domínio quebrava tudo quando a carga cobre vários
-- organogramas de uma vez — o `dominio` vira metadado informativo.
CREATE OR REPLACE VIEW silver.ultima_carga AS
SELECT DISTINCT ON (sistema) id, sistema, dominio, concluida_em, linhas
FROM bronze.carga
WHERE ok IS TRUE
ORDER BY sistema, concluida_em DESC;

-- Uma linha por colaborador, com o vocabulário do hub e as derivações que todo
-- consumidor refaria por conta própria (tempo de casa, faixa, span, papel).
CREATE OR REPLACE VIEW silver.colaborador AS
WITH atual AS (SELECT id FROM silver.ultima_carga WHERE sistema = 'peoples'),
     p AS (SELECT b.* FROM bronze.peoples_pessoa b JOIN atual a ON a.id = b.carga_id),
     lider AS (SELECT slug, origem_id, nome, cargo FROM p),
     span AS (SELECT slug, parent_origem AS origem_id, count(*)::int AS liderados
                FROM p WHERE parent_origem IS NOT NULL GROUP BY 1, 2)
SELECT
    p.slug                                   AS organograma,
    p.origem_id                              AS pessoa_id,
    p.codigo                                 AS matricula,
    p.nome, p.email, p.cargo, p.nivel, p.area,
    p.centro_custo, p.vertical, p.vinculo, p.admissao, p.situacao,
    p.parent_origem                          AS lider_id,
    l.nome                                   AS lider_nome,
    l.cargo                                  AS lider_cargo,
    COALESCE(s.liderados, 0)                 AS liderados_diretos,
    (COALESCE(s.liderados, 0) > 0)           AS e_gestor,
    CASE WHEN p.admissao IS NOT NULL
         THEN round((CURRENT_DATE - p.admissao) / 365.25, 2) END AS anos_de_casa,
    CASE
      WHEN p.admissao IS NULL THEN 'sem_data'
      WHEN (CURRENT_DATE - p.admissao) / 365.25 < 1  THEN 'ate1'
      WHEN (CURRENT_DATE - p.admissao) / 365.25 < 3  THEN 'de1a3'
      WHEN (CURRENT_DATE - p.admissao) / 365.25 < 5  THEN 'de3a5'
      WHEN (CURRENT_DATE - p.admissao) / 365.25 < 10 THEN 'de5a10'
      ELSE 'mais10' END                      AS faixa_casa,
    jsonb_array_length(p.competencias)       AS competencias_declaradas,
    p.competencias,
    p.carga_id, p.carregado_em
FROM p
LEFT JOIN lider l ON l.slug = p.slug AND l.origem_id = p.parent_origem
LEFT JOIN span  s ON s.slug = p.slug AND s.origem_id = p.origem_id;

CREATE OR REPLACE VIEW silver.accountability AS
WITH atual AS (SELECT id FROM silver.ultima_carga WHERE sistema = 'peoples')
SELECT r.slug AS organograma, r.origem_id AS pessoa_id, r.seq, r.descricao,
       r.origem_tipo, r.carregado_em
FROM bronze.peoples_responsabilidade r
JOIN atual a ON a.id = r.carga_id;

CREATE OR REPLACE VIEW silver.skills AS
WITH atual AS (SELECT id FROM silver.ultima_carga WHERE sistema = 'peoples')
SELECT s.slug AS organograma, s.ref AS funcao, s.cargo, s.missao,
       -- Contagens que todo consumidor calcularia: quantas linhas cada seção tem.
       (length(coalesce(s.responsabilidades, '')) - length(replace(coalesce(s.responsabilidades, ''), E'\n', '')) + 1) AS n_responsabilidades,
       (length(coalesce(s.requisitos, '')) - length(replace(coalesce(s.requisitos, ''), E'\n', '')) + 1) AS n_requisitos,
       (length(coalesce(s.competencias, '')) - length(replace(coalesce(s.competencias, ''), E'\n', '')) + 1) AS n_competencias,
       s.responsabilidades, s.requisitos, s.competencias, s.carregado_em
FROM bronze.peoples_skills s
JOIN atual a ON a.id = s.carga_id;

CREATE OR REPLACE VIEW silver.conversa_valor AS
WITH atual AS (SELECT id FROM silver.ultima_carga WHERE sistema = 'peoples')
SELECT c.slug AS organograma, c.ref AS matricula, c.ano, c.ciclo, c.status,
       c.data_conversa, c.lider_nome, c.elementos, c.pdi_itens, c.carregado_em
FROM bronze.peoples_conversa_valor c
JOIN atual a ON a.id = c.carga_id;

CREATE OR REPLACE VIEW silver.avaliacao AS
WITH atual AS (SELECT id FROM silver.ultima_carga WHERE sistema = 'peoples')
SELECT v.slug AS organograma, v.ref AS matricula, v.ano,
       v.risco_perda, v.impacto_perda, v.prontidao, v.acao,
       -- O quadrante do 9-box, nomeado uma vez aqui e não em cada painel.
       CASE
         WHEN v.impacto_perda = 'alto'  AND v.risco_perda = 'alto'  THEN 'critico'
         WHEN v.impacto_perda = 'alto'  AND v.risco_perda = 'medio' THEN 'atencao'
         WHEN v.impacto_perda = 'alto'  AND v.risco_perda = 'baixo' THEN 'estrategico'
         WHEN v.impacto_perda = 'medio' AND v.risco_perda = 'alto'  THEN 'reter'
         WHEN v.impacto_perda = 'baixo' AND v.risco_perda = 'alto'  THEN 'observar'
         ELSE 'estavel' END AS quadrante,
       v.carregado_em
FROM bronze.peoples_avaliacao v
JOIN atual a ON a.id = v.carga_id;

CREATE OR REPLACE VIEW silver.clima AS
WITH atual AS (SELECT id FROM silver.ultima_carga WHERE sistema = 'peoples')
SELECT k.slug AS organograma, k.ano, k.ciclo, k.dimensao, k.chave,
       k.respondentes, k.pti, k.carregado_em
FROM bronze.peoples_clima_agregado k
JOIN atual a ON a.id = k.carga_id;

-- ---------------------------------------------------------------------------
-- GOLD · as métricas — é isto que a API e os painéis leem
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.organizacao AS
SELECT organograma,
       count(*)                                        AS colaboradores,
       count(*) FILTER (WHERE e_gestor)                 AS gestores,
       count(DISTINCT area)                             AS areas,
       count(DISTINCT vertical) FILTER (WHERE vertical <> '') AS verticais,
       count(DISTINCT centro_custo) FILTER (WHERE centro_custo <> '') AS centros_custo,
       round(avg(anos_de_casa)::numeric, 2)             AS anos_de_casa_medio,
       round((count(*) - 1)::numeric
             / NULLIF(count(*) FILTER (WHERE e_gestor), 0), 2) AS amplitude_media,
       round(100.0 * count(*) FILTER (WHERE vinculo = 'clt') / NULLIF(count(*), 0), 1) AS pct_clt,
       round(100.0 * count(*) FILTER (WHERE vinculo IN ('pj', 'rpa', 'consultoria'))
             / NULLIF(count(*), 0), 1)                  AS pct_terceirizados,
       round(100.0 * count(*) FILTER (WHERE vinculo = 'estagio') / NULLIF(count(*), 0), 1) AS pct_estagio,
       max(carregado_em)                                AS atualizado_em
FROM silver.colaborador GROUP BY organograma;

CREATE OR REPLACE VIEW gold.headcount_por_area AS
SELECT organograma, COALESCE(NULLIF(area, ''), 'sem área') AS area,
       count(*) AS colaboradores,
       count(*) FILTER (WHERE e_gestor) AS gestores,
       round(avg(anos_de_casa)::numeric, 2) AS anos_de_casa_medio,
       count(*) FILTER (WHERE faixa_casa = 'ate1') AS ate_1_ano,
       max(carregado_em) AS atualizado_em
FROM silver.colaborador GROUP BY organograma, 2;

CREATE OR REPLACE VIEW gold.headcount_por_vinculo AS
SELECT organograma, COALESCE(NULLIF(vinculo, ''), 'não informado') AS vinculo,
       count(*) AS colaboradores,
       round(100.0 * count(*) / SUM(count(*)) OVER (PARTITION BY organograma), 1) AS pct,
       max(carregado_em) AS atualizado_em
FROM silver.colaborador GROUP BY organograma, 2;

CREATE OR REPLACE VIEW gold.tempo_de_casa AS
SELECT organograma, faixa_casa,
       count(*) AS colaboradores,
       round(100.0 * count(*) / SUM(count(*)) OVER (PARTITION BY organograma), 1) AS pct,
       max(carregado_em) AS atualizado_em
FROM silver.colaborador GROUP BY organograma, faixa_casa;

-- Cobertura de Skills: quantas funções têm ficha escrita, e quantas pessoas
-- estão cobertas por uma ficha. Sem ficha, não há PDI que se sustente.
CREATE OR REPLACE VIEW gold.skills_cobertura AS
WITH f AS (SELECT organograma, funcao FROM silver.skills),
     c AS (SELECT organograma, lower(cargo) AS cargo_lower, count(*) AS n
             FROM silver.colaborador WHERE cargo <> '' GROUP BY 1, 2)
SELECT c.organograma,
       count(*)                                    AS funcoes_na_estrutura,
       count(*) FILTER (WHERE f.funcao IS NOT NULL) AS funcoes_com_ficha,
       round(100.0 * count(*) FILTER (WHERE f.funcao IS NOT NULL) / NULLIF(count(*), 0), 1) AS pct_funcoes,
       sum(c.n)                                    AS pessoas,
       sum(c.n) FILTER (WHERE f.funcao IS NOT NULL) AS pessoas_com_ficha,
       round(100.0 * sum(c.n) FILTER (WHERE f.funcao IS NOT NULL) / NULLIF(sum(c.n), 0), 1) AS pct_pessoas
FROM c LEFT JOIN f ON f.organograma = c.organograma
   AND unaccent(lower(f.funcao)) = unaccent(c.cargo_lower)
GROUP BY c.organograma;

-- Cobertura do ritual: a Conversa de Valor realizada, por ciclo e por área. É o
-- indicador que diz se a liderança está conversando — não se o formulário existe.
CREATE OR REPLACE VIEW gold.conversa_valor_cobertura AS
WITH base AS (
  SELECT c.organograma, c.ano, c.ciclo, c.status, col.area
  FROM silver.conversa_valor c
  LEFT JOIN silver.colaborador col
         ON col.organograma = c.organograma AND col.matricula = c.matricula)
SELECT organograma, ano, ciclo,
       count(*)                                          AS previstas,
       count(*) FILTER (WHERE status = 'realizada')       AS realizadas,
       count(*) FILTER (WHERE status = 'agendada')        AS agendadas,
       count(*) FILTER (WHERE status = 'pendente')        AS pendentes,
       round(100.0 * count(*) FILTER (WHERE status = 'realizada') / NULLIF(count(*), 0), 1) AS pct_realizadas
FROM base GROUP BY organograma, ano, ciclo;

CREATE OR REPLACE VIEW gold.conversa_valor_por_area AS
SELECT c.organograma, c.ano, COALESCE(NULLIF(col.area, ''), 'sem área') AS area,
       count(*) AS conversas,
       count(*) FILTER (WHERE c.status = 'realizada') AS realizadas,
       round(100.0 * count(*) FILTER (WHERE c.status = 'realizada') / NULLIF(count(*), 0), 1) AS pct_realizadas
FROM silver.conversa_valor c
LEFT JOIN silver.colaborador col
       ON col.organograma = c.organograma AND col.matricula = c.matricula
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW gold.talento_9box AS
SELECT organograma, ano, impacto_perda, risco_perda, quadrante,
       count(*) AS pessoas,
       round(100.0 * count(*) / SUM(count(*)) OVER (PARTITION BY organograma, ano), 1) AS pct
FROM silver.avaliacao
WHERE impacto_perda <> '' AND risco_perda <> ''
GROUP BY 1, 2, 3, 4, 5;

CREATE OR REPLACE VIEW gold.sucessao AS
SELECT organograma, ano, prontidao,
       count(*) AS pessoas,
       count(*) FILTER (WHERE acao = 'promocao')     AS acao_promocao,
       count(*) FILTER (WHERE acao = 'meritocracia') AS acao_meritocracia,
       count(*) FILTER (WHERE acao = 'rotativo')     AS acao_rotativo
FROM silver.avaliacao WHERE prontidao <> '' GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW gold.clima_pti AS
SELECT organograma, ano, ciclo, dimensao, chave, respondentes, pti,
       CASE WHEN pti >= 90 THEN 'excelencia'
            WHEN pti >= 75 THEN 'alto'
            WHEN pti >= 60 THEN 'desenvolvimento'
            WHEN pti >= 45 THEN 'alerta'
            ELSE 'critico' END AS maturidade
FROM silver.clima;

-- Risco de concentração de conhecimento: função ocupada por UMA pessoa só, com
-- impacto de perda alto. É a pergunta "onde perder alguém dói e não há reserva".
CREATE OR REPLACE VIEW gold.risco_concentracao AS
WITH por_funcao AS (
  SELECT organograma, cargo, count(*) AS ocupantes,
         min(matricula) AS matricula_unica, min(nome) AS nome_unico, min(area) AS area
  FROM silver.colaborador WHERE cargo <> '' GROUP BY 1, 2)
SELECT f.organograma, f.cargo, f.area, f.ocupantes,
       v.impacto_perda, v.risco_perda, v.quadrante, v.prontidao
FROM por_funcao f
LEFT JOIN silver.avaliacao v
       ON v.organograma = f.organograma AND v.matricula = f.matricula_unica
WHERE f.ocupantes = 1 AND COALESCE(v.impacto_perda, '') = 'alto';

-- O painel de uma olhada: uma linha por organograma com o que a diretoria pergunta.
CREATE OR REPLACE VIEW gold.painel_executivo AS
SELECT o.organograma, o.colaboradores, o.gestores, o.amplitude_media,
       o.anos_de_casa_medio, o.pct_clt, o.pct_terceirizados,
       sk.pct_pessoas                          AS pct_pessoas_com_skills,
       cv.pct_realizadas                       AS pct_conversa_valor_realizada,
       (SELECT pti FROM gold.clima_pti c
         WHERE c.organograma = o.organograma AND c.dimensao = 'geral'
         ORDER BY ano DESC, ciclo LIMIT 1)     AS pti_geral,
       (SELECT count(*) FROM gold.risco_concentracao r
         WHERE r.organograma = o.organograma)  AS posicoes_criticas_sem_reserva,
       o.atualizado_em
FROM gold.organizacao o
LEFT JOIN gold.skills_cobertura sk ON sk.organograma = o.organograma
LEFT JOIN (SELECT organograma, round(avg(pct_realizadas), 1) AS pct_realizadas
             FROM gold.conversa_valor_cobertura GROUP BY 1) cv
       ON cv.organograma = o.organograma;

COMMIT;
