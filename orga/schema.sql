-- ===========================================================================
-- GPlanSiS|Peoples - migration 001_org_baseline
-- SPEC-GPLANSIS-ORG-001 secao 7. Alvo: PostgreSQL 18.
-- O app roda em memoria + JSON por padrao; este schema e o alvo de producao.
-- ===========================================================================
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE SCHEMA IF NOT EXISTS org;

-- 'especialista' e a trilha tecnica: senioridade sem gente embaixo.
CREATE TYPE org.tipo_unidade  AS ENUM ('diretoria','gerencia','coordenacao','especialista','area','celula','apoio');
CREATE TYPE org.papel_alocacao AS ENUM ('responsavel','membro','interino','apoio');
CREATE TYPE org.origem_responsabilidade AS ENUM ('propria','delegada','compartilhada');
-- As cinco chaves de dominio.VINCULOS. Enum, e nao text+CHECK, por simetria com
-- tipo_unidade — e porque o importador ja traduz rotulo para chave e recusa o
-- que nao existe, entao o que chega aqui e sempre chave. O preco: acrescentar
-- valor pede ALTER TYPE ... ADD VALUE, que nao roda na mesma transacao da carga.
CREATE TYPE org.vinculo AS ENUM ('clt','pj','estagio','rpa','consultoria');

CREATE TABLE org.organograma (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug              citext NOT NULL UNIQUE
                      CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$'),
    nome              text NOT NULL,
    orientacao_padrao text NOT NULL DEFAULT 'invertida'
                      CHECK (orientacao_padrao IN ('invertida','vertical','lateral')),
    ativo             boolean NOT NULL DEFAULT true,
    criado_em         timestamptz NOT NULL DEFAULT now(),
    atualizado_em     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE org.pessoa (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- O ID SAP. A coluna sempre existiu e ninguem escrevia nela; com a matricula
    -- vinda do RH, ela passa a ser a identidade da pessoa — e quem nao tem
    -- e-mail deixa de ser invisivel para a carga.
    matricula     text UNIQUE,
    nome_completo text NOT NULL CHECK (char_length(btrim(nome_completo)) BETWEEN 2 AND 160),
    nome_exibicao text NOT NULL CHECK (char_length(btrim(nome_exibicao)) BETWEEN 2 AND 60),
    email_corp    citext UNIQUE,
    -- Admissao. NULL e legitimo: o dominio trata "sem data" como diferente de
    -- "zero ano de casa", e NOT NULL recusaria justamente o caso previsto.
    admissao      date,
    -- O rotulo que o RH declara ("Ativo" e afins). Sem CHECK IN de proposito: a
    -- carga e uma transacao so, e um rotulo novo derrubaria os 271 registros.
    situacao_rh   text,
    avatar_url    text,
    ativo         boolean NOT NULL DEFAULT true,
    criado_em     timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

-- Tempo de casa NAO e coluna, aqui nem em lugar nenhum: e derivado da admissao,
-- e um numero desses nasce velho. Tambem nao da para ser coluna gerada, porque
-- CURRENT_DATE nao e IMMUTABLE. Quem quiser em SQL usa a vista, que aplica a
-- mesma regua do RH — dias corridos sobre 365, sem bissexto.
CREATE VIEW org.v_tempo_de_casa AS
SELECT p.id, p.matricula, p.nome_exibicao, p.admissao,
       (CURRENT_DATE - p.admissao) / 365.0 AS anos
FROM org.pessoa p
WHERE p.admissao IS NOT NULL;

CREATE INDEX ix_pessoa_admissao ON org.pessoa (admissao) WHERE admissao IS NOT NULL;
-- LGPD-01/02: proibido CPF, RG, endereco, dado de saude e qualquer remuneracao.

CREATE TABLE org.unidade (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organograma_id uuid NOT NULL REFERENCES org.organograma(id) ON DELETE CASCADE,
    codigo         text NOT NULL,
    nome           text NOT NULL CHECK (char_length(btrim(nome)) BETWEEN 2 AND 80),
    nome_curto     text,
    tipo           org.tipo_unidade NOT NULL,
    parent_id      uuid REFERENCES org.unidade(id) ON DELETE RESTRICT,
    ordem_exibicao smallint NOT NULL DEFAULT 0,
    -- Fidelidade do espelho (Onda DB-1). Sem estas colunas o banco guardava só
    -- metade do nó: área, centro de custo, vertical, responsável e competências
    -- viviam só na tela, e ler a estrutura de volta (Onda DB-3) as perderia.
    -- `origem_id` é a identidade do nó em memória — a chave do `estado.json` —,
    -- que NÃO é o código: na carga da planilha o id é um hash do nome, e
    -- `colapsados`, eventos e provisionamentos apontam para ele. Reconstruir por
    -- código reescreveria essas referências e quebraria o colapso guardado.
    origem_id      text,
    area           text,
    centro_custo   text,
    vertical       text,
    responsavel    text,
    competencias   jsonb NOT NULL DEFAULT '[]'::jsonb,
    -- cargo/vinculo também aqui, e não só em org.alocacao: a alocação é a visão
    -- normalizada (vigência, um responsável por unidade), mas a raiz sintética
    -- não é pessoa e não tem alocação. Guardar no nó deixa a estrutura voltar
    -- INTEIRA do banco (Onda DB-3), a raiz inclusive.
    cargo          text,
    vinculo        org.vinculo,
    -- Planilha completa (bd_completo_org): campos ORGANIZACIONAIS que faltavam.
    -- Nada de remuneração aqui — dinheiro fica na view bd_completo_org, à parte,
    -- e sempre NULL (LGPD-01/02). `data_nascimento` é personal, não proibido.
    tipo_mo         text,
    cc_n2           text,
    cc_n4           text,
    cc_n5           text,
    cc_equipe       text,
    bu              text,
    tipo_class      text,
    mo_classe       text,
    categoria_nivel text,
    genero          text,
    data_nascimento date,
    ativo          boolean NOT NULL DEFAULT true,
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_unidade_codigo UNIQUE (organograma_id, codigo),
    CONSTRAINT ck_unidade_nao_autopai CHECK (parent_id IS DISTINCT FROM id)
);
-- Uma raiz por organograma, conferida no COMMIT (migração 010): índice parcial
-- não é adiável, e a carga que TROCA a raiz passa por um instante com duas.
ALTER TABLE org.unidade
  ADD CONSTRAINT ex_unidade_raiz_unica
  EXCLUDE USING btree (organograma_id WITH =) WHERE (parent_id IS NULL)
  DEFERRABLE INITIALLY DEFERRED;
CREATE UNIQUE INDEX ux_unidade_origem ON org.unidade (organograma_id, origem_id) WHERE origem_id IS NOT NULL;
CREATE INDEX ix_unidade_parent ON org.unidade (parent_id, ordem_exibicao);

CREATE TABLE org.unidade_closure (
    ancestral_id   uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    descendente_id uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    profundidade   smallint NOT NULL CHECK (profundidade >= 0),
    PRIMARY KEY (ancestral_id, descendente_id)
);
CREATE INDEX ix_closure_desc ON org.unidade_closure (descendente_id, profundidade);

CREATE TABLE org.alocacao (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unidade_id uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    pessoa_id  uuid NOT NULL REFERENCES org.pessoa(id)  ON DELETE RESTRICT,
    papel      org.papel_alocacao NOT NULL,
    cargo      text,
    -- O regime e do CONTRATO, nao da pessoa: a mesma pessoa vira CLT depois de
    -- estagiar, e o historico das duas alocacoes tem de contar a verdade de
    -- cada epoca. Nullable porque estado gravado antes desta coluna traz vazio.
    vinculo    org.vinculo,
    vigencia   daterange NOT NULL DEFAULT daterange(CURRENT_DATE, NULL, '[)'),
    criado_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_alocacao_vigencia CHECK (NOT isempty(vigencia)),
    CONSTRAINT ex_alocacao_responsavel_unico
        EXCLUDE USING gist (unidade_id WITH =, vigencia WITH &&) WHERE (papel = 'responsavel')
);

CREATE TABLE org.responsabilidade (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unidade_id uuid NOT NULL REFERENCES org.unidade(id) ON DELETE CASCADE,
    descricao  text NOT NULL CHECK (char_length(btrim(descricao)) BETWEEN 2 AND 200),
    origem     org.origem_responsabilidade NOT NULL DEFAULT 'propria',
    delegada_para_unidade_id uuid REFERENCES org.unidade(id) ON DELETE SET NULL,
    ordem      smallint NOT NULL DEFAULT 0,
    vigencia   daterange NOT NULL DEFAULT daterange(CURRENT_DATE, NULL, '[)'),
    criado_em  timestamptz NOT NULL DEFAULT now(),
    -- Destino nomeado implica delegação; delegação NÃO implica destino nomeado.
    --
    -- A bicondicional que estava aqui — `(origem='delegada') = (destino IS NOT
    -- NULL)` — exigia que toda delegação apontasse para UMA unidade, e o
    -- organograma não delega assim: `_delegar_por_equipe` deriva as
    -- accountabilities do gestor das ÁREAS dos reportes diretos dele, que são
    -- várias e podem ter vários donos cada. Eleger um filho para receber a
    -- delegação inventaria uma precisão que o dado não tem, e a alternativa —
    -- gravar tudo como `propria` — apagaria a distinção que a tela mostra.
    --
    -- O que continua valendo é o que importa: um destino gravado sem
    -- `origem='delegada'` seria um ponteiro sem sentido, e isso segue recusado.
    CONSTRAINT ck_resp_delegacao_coerente
        CHECK (delegada_para_unidade_id IS NULL OR origem = 'delegada'),
    CONSTRAINT ck_resp_nao_autodelegada
        CHECK (delegada_para_unidade_id IS DISTINCT FROM unidade_id)
);
CREATE INDEX ix_resp_unidade ON org.responsabilidade (unidade_id, ordem);

-- Ledger encadeado por SHA-256, o mesmo que a aba Auditoria verifica (Onda DB-4).
-- Guarda cada campo VERBATIM como o app os encadeia: `quando` é texto, não
-- timestamptz, porque a string ISO exata entra no corpo do hash — reformatá-la
-- (o que um timestamptz faria na volta) quebraria a cadeia. `entidade_id` é texto
-- (o id do nó tem 12 hex, não é uuid) e `hash` é hexadecimal em texto (não
-- bytea), pela mesma razão de fidelidade. `payload` em jsonb com sort_keys na
-- verificação, então a ordem das chaves não altera o hash. Append-only e
-- por-organograma: (organograma_id, seq) é a chave, e a carga do ledger só
-- acrescenta o que falta.
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

CREATE TABLE org.maria_assistencia (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ocorrido_em    timestamptz NOT NULL DEFAULT now(),
    quem           text,
    quem_id        text,
    -- O recorte em que a resposta foi dada. Sem ele nao da para auditar depois
    -- se a resposta era compativel com o que a pessoa podia ver.
    escopo         text NOT NULL,
    capacidade     text NOT NULL
                   CHECK (capacidade IN ('ler','descrever','relatar','analisar',
                                         'planejar','executar','autonoma')),
    idioma         text NOT NULL,
    modelo         text NOT NULL,
    pergunta       text NOT NULL,
    resposta       text NOT NULL,
    ok             boolean NOT NULL DEFAULT true,
    tokens_entrada integer NOT NULL DEFAULT 0,
    tokens_saida   integer NOT NULL DEFAULT 0,
    custo_usd      numeric(12,6) NOT NULL DEFAULT 0,
    -- Chave natural da ocorrencia: a mesma pessoa nao faz duas perguntas no
    -- mesmo instante. Sem ela a carga do historico nao era idempotente —
    -- rodar duas vezes dobrava o log, e um log dobrado mente sobre custo,
    -- sobre volume e sobre quem perguntou o que.
    --
    -- NULLS NOT DISTINCT porque `quem_id` e nulo em pergunta anonima: no
    -- padrao do SQL dois nulos sao diferentes, e a guarda nao valeria
    -- justamente nas linhas sem dono.
    CONSTRAINT uq_assistencia_ocorrencia
        UNIQUE NULLS NOT DISTINCT (ocorrido_em, quem_id)
);
CREATE INDEX ix_maria_quando ON org.maria_assistencia (ocorrido_em DESC);
CREATE INDEX ix_maria_quem ON org.maria_assistencia (quem_id, ocorrido_em DESC);

-- ---------------------------------------------------------------------------
-- Conversa de Valor — Conversas que Geram Valor. O acompanhamento do feedback estruturado.
-- ---------------------------------------------------------------------------
-- Esta e a razao de a Conversa de Valor escrever no Postgres, e nao so guardar no estado.json
-- como o resto: o `estado.json` e o retrato de AGORA e some numa reimportacao;
-- o historico de Conversa de Valor precisa atravessar anos. Uma linha por (organograma,
-- matricula, ano, ciclo) — 2026 e 2027 da mesma pessoa coexistem.
--
-- A pessoa e referenciada pela MATRICULA (ref), e nao por FK a org.pessoa: o
-- registro tem de sobreviver a pessoa sair da base e ao organograma ser
-- reimportado. Por isso tambem guarda um SNAPSHOT de nome, cargo e lider —
-- como estava na conversa —, para o historico ser legivel depois que a
-- estrutura mudou. Sem nota de avaliacao: Conversa de Valor e conversa de desenvolvimento,
-- nao ranking (isso e o Comite de Meritocracia, com outra guarda).
CREATE TYPE org.cgv_ciclo  AS ENUM ('completa','checkin1','checkin2');
CREATE TYPE org.cgv_status AS ENUM ('pendente','agendada','realizada');

CREATE TABLE org.cgv_registro (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug           text NOT NULL,
    ref            text NOT NULL,            -- matricula (codigo SAP) da pessoa
    ano            smallint NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    ciclo          org.cgv_ciclo NOT NULL,
    status         org.cgv_status NOT NULL DEFAULT 'pendente',
    data_conversa  date,
    nota           text NOT NULL DEFAULT '',
    -- O formulario inteiro (GEP-FOR-006), em JSONB: entregas, valores TRIO, PDI
    -- (ate 3 competencias com acao 70/20/10 e prazo) e carreira. E o que tira a
    -- Conversa de Valor do Excel — o conteudo da conversa vive no banco, editavel, versionado
    -- por ano/ciclo, e nao num arquivo que roda por e-mail.
    conteudo       jsonb NOT NULL DEFAULT '{}'::jsonb,
    pessoa_nome    text NOT NULL DEFAULT '', -- snapshot: como estava ao gravar
    pessoa_cargo   text NOT NULL DEFAULT '',
    lider_nome     text NOT NULL DEFAULT '',
    registrado_por text NOT NULL DEFAULT '',
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    -- A conversa e unica no ano: editar atualiza a linha, nao empilha. E o que
    -- torna a gravacao idempotente e o UPSERT possivel.
    CONSTRAINT uq_cgv_conversa UNIQUE (slug, ref, ano, ciclo)
);
CREATE INDEX ix_cgv_pessoa ON org.cgv_registro (slug, ref, ano DESC);
CREATE INDEX ix_cgv_ano ON org.cgv_registro (slug, ano DESC, ciclo);

-- One-on-One: 1:1 (FUP), rocks, issues, objetivos do trimestre, missoes, pulso e
-- ciclo de vida. Um item por id (gerado pelo app). SIGILO por pessoa (LGPD): o
-- registro pertence ao liderado (ref) e ao lider que o escreveu (lider_ref) —
-- as duas matriculas participantes; a leitura so e liberada a elas ou a RH. O
-- conteudo type-specific mora no JSONB, como o formulario da Conversa de Valor.
CREATE TABLE org.onebyone_item (
    id             text NOT NULL,            -- id do item, gerado pelo app
    slug           text NOT NULL,
    tipo           text NOT NULL,            -- conversa|rock|issue|objetivo|missao|pulso|ciclo
    ref            text NOT NULL,            -- matricula do liderado (participante)
    lider_ref      text NOT NULL DEFAULT '', -- matricula do lider (participante)
    ano            smallint NOT NULL DEFAULT 0 CHECK (ano = 0 OR ano BETWEEN 2000 AND 2100),
    trimestre      smallint NOT NULL DEFAULT 0 CHECK (trimestre BETWEEN 0 AND 4),
    data_item      date,
    conteudo       jsonb NOT NULL DEFAULT '{}'::jsonb,
    pessoa_nome    text NOT NULL DEFAULT '',  -- snapshot: como estava ao gravar
    pessoa_cargo   text NOT NULL DEFAULT '',
    lider_nome     text NOT NULL DEFAULT '',
    registrado_por text NOT NULL DEFAULT '',
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    -- O id ja e unico por organograma: editar atualiza a linha (UPSERT), nao empilha.
    CONSTRAINT pk_onebyone PRIMARY KEY (slug, id)
);
CREATE INDEX ix_onebyone_pessoa ON org.onebyone_item (slug, ref, tipo);
CREATE INDEX ix_onebyone_lider ON org.onebyone_item (slug, lider_ref);

-- ---------------------------------------------------------------------------
-- Skills — a camada que o RH escreve sobre cada cargo (GEP-FOR-003).
-- ---------------------------------------------------------------------------
-- O que o RH redige — missao, responsabilidades, requisitos e competencias —
-- passa a viver no banco, e nao so no estado.json: assim a descricao dos cargos
-- e editavel e duravel, sobrevive a reimportacao da estrutura e nao se perde num
-- arquivo local. A chave e a FUNCAO (cargo sem acento), nao a pessoa: descreve o
-- cargo, e doze "Analista de Projetos" compartilham uma descricao.
CREATE TABLE org.dcr_overlay (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug               text NOT NULL,
    ref                text NOT NULL,          -- chave_funcao: cargo sem acento
    cargo              text NOT NULL,
    missao             text NOT NULL DEFAULT '',
    responsabilidades  text NOT NULL DEFAULT '',
    requisitos         text NOT NULL DEFAULT '',
    competencias       text NOT NULL DEFAULT '',
    registrado_por     text NOT NULL DEFAULT '',
    criado_em          timestamptz NOT NULL DEFAULT now(),
    atualizado_em      timestamptz NOT NULL DEFAULT now(),
    -- Uma descricao por cargo: editar atualiza a linha, nao empilha.
    CONSTRAINT uq_dcr_overlay UNIQUE (slug, ref)
);
CREATE INDEX ix_dcr_overlay ON org.dcr_overlay (slug, ref);

-- ---------------------------------------------------------------------------
-- MAPA DE TALENTOS — a leitura de sucessao do RH sobre cada pessoa (GEP-FOR-004).
-- ---------------------------------------------------------------------------
-- Um registro por (organograma, matricula, ano). O sistema DERIVA nome, tempo de
-- casa, cargo e lider do organograma; aqui vive so o que o RH escreve — risco e
-- impacto de perda (o 9-box), prontidao de sucessao, acao imediata (o insumo do
-- Comite de Meritocracia) e o texto rico (trajetoria, formacoes, perfil, valores
-- TRIO, oportunidades, trilha) em JSONB. Idade e campo do JSONB, opcional: o
-- organograma nao guarda data de nascimento (LGPD), entao ela nao e derivada.
-- Sem nota quantitativa: como a Conversa de Valor, e leitura de desenvolvimento, nao ranking.
CREATE TABLE org.mapa_talento (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug           text NOT NULL,
    ref            text NOT NULL,            -- matricula (codigo SAP) da pessoa
    ano            smallint NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    risco_perda    text NOT NULL DEFAULT '', -- alto|medio|baixo
    impacto_perda  text NOT NULL DEFAULT '', -- alto|medio|baixo
    prontidao      text NOT NULL DEFAULT '', -- agora|1ano|2anos|3mais
    acao           text NOT NULL DEFAULT '', -- meritocracia|promocao|rotativo|outros
    conteudo       jsonb NOT NULL DEFAULT '{}'::jsonb,
    pessoa_nome    text NOT NULL DEFAULT '', -- snapshot: como estava ao gravar
    pessoa_cargo   text NOT NULL DEFAULT '',
    lider_nome     text NOT NULL DEFAULT '',
    registrado_por text NOT NULL DEFAULT '',
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    -- Um mapa por pessoa e ano: editar atualiza a linha, nao empilha.
    CONSTRAINT uq_mapa_talento UNIQUE (slug, ref, ano)
);
CREATE INDEX ix_mapa_talento ON org.mapa_talento (slug, ref, ano DESC);

-- ---------------------------------------------------------------------------
-- GREY PLACE TO WORK — a pesquisa de clima, ANONIMA (Peoples Trust Index).
-- ---------------------------------------------------------------------------
-- A resposta nao tem dono: nenhuma coluna guarda quem respondeu. O vinculo com
-- o sistema e pelos ESTRATOS (nivel, area, vinculo, faixa de tempo de casa) que
-- o organograma ja conhece, derivados da posicao de quem responde no envio e
-- gravados SEM a identidade. So o modelo de trabalho e perguntado. As respostas
-- Likert (1..5) e as abertas ficam em JSONB. Append-only: cada envio e uma
-- linha, sem chave de pessoa — de proposito, para o anonimato ser estrutural e
-- nao so uma promessa. O piso de 5 respondentes se aplica na LEITURA (por_estrato).
CREATE TABLE org.gptw_resposta (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            text NOT NULL,
    ciclo           text NOT NULL,            -- anual | pulso
    ano             smallint NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    respostas       jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {afirmacao_id: 1..5}
    abertas         jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {pergunta_id: texto}
    estrato_nivel   text,                     -- SEM identidade: apenas estratos
    estrato_area    text,
    estrato_vinculo text,
    estrato_faixa   text,
    modelo_trabalho text,
    -- A chave do overlay (id da resposta em memoria): e o que deixa o espelho
    -- ser UPSERT e a leitura casar com a memoria sem contar em dobro (migr. 011).
    chave           text,
    criado_em       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_gptw_ciclo ON org.gptw_resposta (slug, ano DESC, ciclo);
CREATE UNIQUE INDEX ux_gptw_chave ON org.gptw_resposta (slug, chave) WHERE chave IS NOT NULL;

-- Guardas, closure e encadeamento de hash: ver SPEC secoes 7.1 e 7.2.


-- bd_completo_org — o de-para inteiro da planilha antiga (37 colunas), uma linha
-- por colaborador, gestor e tempo derivados, dinheiro sempre NULL (LGPD-01/02).
-- Mesma definição da migração 007; aqui é para volume novo.
CREATE VIEW org.bd_completo_org AS
SELECT
    o.slug AS organograma, u.codigo AS id_sap, u.nome AS colaborador,
    u.tipo_mo, u.cargo AS cargo_funcao, u.area AS departamento,
    p.email_corp AS email, u.cc_n2 AS n2, u.centro_custo AS n3, u.cc_n4 AS n4,
    u.cc_n5 AS n5, u.vinculo::text AS regime,
    NULL::numeric(14,2) AS salario, NULL::numeric(14,2) AS contrato,
    NULL::numeric(14,2) AS rend_extra, NULL::numeric(14,2) AS total,
    p.admissao AS data_inicio, u.genero,
    CASE WHEN u.data_nascimento IS NOT NULL
         THEN round((CURRENT_DATE - u.data_nascimento) / 365.0, 1) END AS idade,
    u.data_nascimento,
    CASE WHEN p.admissao IS NOT NULL
         THEN round((CURRENT_DATE - p.admissao) / 365.0, 1) END AS tempo_de_empresa,
    NULL::numeric(14,2) AS valor_base_hora, NULL::numeric(14,2) AS valor_total_encargos,
    p.situacao_rh AS status, pu.nome AS gestor_direto, u.vertical, u.bu,
    u.tipo_class, u.mo_classe AS mo, u.categoria_nivel, u.tipo::text AS nivel,
    u.cc_equipe,
    NULL::numeric(14,2) AS custo_unitario, NULL::numeric(14,2) AS custo_interno,
    NULL::numeric(14,2) AS venda_liquida, NULL::numeric(14,2) AS venda_com_impostos,
    NULL::numeric(14,2) AS custo_mensal
FROM org.unidade u
JOIN org.organograma o ON o.id = u.organograma_id
LEFT JOIN org.unidade pu ON pu.id = u.parent_id
LEFT JOIN org.alocacao a
       ON a.unidade_id = u.id AND a.papel = 'responsavel' AND upper_inf(a.vigencia)
LEFT JOIN org.pessoa p ON p.id = a.pessoa_id
ORDER BY o.slug, u.ordem_exibicao, u.nome;


-- ---------------------------------------------------------------------------
-- Login próprio e o resto do estado (migração 009). O banco passa a ter o
-- sistema INTEIRO: estrutura, ledger, módulos, configuração e credenciais.
-- ---------------------------------------------------------------------------
-- Credenciais do login do PRÓPRIO sistema: e-mail + hash scrypt (nunca a
-- senha). GLOBAL (sem slug): uma senha vale para todos os organogramas. Papel
-- e escopo NÃO moram aqui — seguem no RBAC do organograma (Config.acessos).
CREATE TABLE org.usuario (
    email          citext PRIMARY KEY CHECK (email ~ '^[^@\s]+@[^@\s]+$'),
    senha_hash     text NOT NULL,
    ativo          boolean NOT NULL DEFAULT true,
    precisa_trocar boolean NOT NULL DEFAULT false,
    definida_por   text NOT NULL DEFAULT '',
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now()
);

-- Tudo do estado.json que não tem tabela própria (configuração, RBAC, colapso,
-- orientação, filtros, provisionamentos, mural, log de acessos): um documento
-- JSONB por organograma, espelhado a cada gravação e restaurado sem arquivo.
CREATE TABLE org.estado_extra (
    slug           text PRIMARY KEY,
    dados          jsonb NOT NULL DEFAULT '{}'::jsonb,
    assinatura     text NOT NULL DEFAULT '',
    atualizado_em  timestamptz NOT NULL DEFAULT now()
);
