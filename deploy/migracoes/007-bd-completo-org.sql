-- 007 — a planilha completa: campos organizacionais + a view bd_completo_org.
--
-- Traz para org.unidade os campos da planilha antiga (Excel) que o sistema não
-- tinha, TODOS organizacionais — nenhum é remuneração. O dinheiro (salário,
-- custo, venda) NÃO é gravado em lugar nenhum: aparece na view bd_completo_org
-- só como coluna NULL, para manter o de-para completo sem violar LGPD-01/02.
-- Idempotente.
ALTER TABLE org.unidade
  ADD COLUMN IF NOT EXISTS tipo_mo         text,
  ADD COLUMN IF NOT EXISTS cc_n2           text,
  ADD COLUMN IF NOT EXISTS cc_n4           text,
  ADD COLUMN IF NOT EXISTS cc_n5           text,
  ADD COLUMN IF NOT EXISTS cc_equipe       text,
  ADD COLUMN IF NOT EXISTS bu              text,
  ADD COLUMN IF NOT EXISTS tipo_class      text,
  ADD COLUMN IF NOT EXISTS mo_classe       text,
  ADD COLUMN IF NOT EXISTS categoria_nivel text,
  ADD COLUMN IF NOT EXISTS genero          text,
  ADD COLUMN IF NOT EXISTS data_nascimento date;

-- A view é o de-para inteiro (37 colunas), uma linha por colaborador, com o
-- gestor e o tempo de empresa derivados e o dinheiro sempre NULL. Recriável.
DROP VIEW IF EXISTS org.bd_completo_org;
CREATE VIEW org.bd_completo_org AS
SELECT
    o.slug                            AS organograma,
    u.codigo                          AS id_sap,
    u.nome                            AS colaborador,
    u.tipo_mo                         AS tipo_mo,
    u.cargo                           AS cargo_funcao,
    u.area                            AS departamento,
    p.email_corp                      AS email,
    u.cc_n2                           AS n2,
    u.centro_custo                    AS n3,
    u.cc_n4                           AS n4,
    u.cc_n5                           AS n5,
    u.vinculo::text                   AS regime,
    NULL::numeric(14,2)               AS salario,
    NULL::numeric(14,2)               AS contrato,
    NULL::numeric(14,2)               AS rend_extra,
    NULL::numeric(14,2)               AS total,
    p.admissao                        AS data_inicio,
    u.genero                          AS genero,
    CASE WHEN u.data_nascimento IS NOT NULL
         THEN round((CURRENT_DATE - u.data_nascimento) / 365.0, 1) END AS idade,
    u.data_nascimento                 AS data_nascimento,
    CASE WHEN p.admissao IS NOT NULL
         THEN round((CURRENT_DATE - p.admissao) / 365.0, 1) END        AS tempo_de_empresa,
    NULL::numeric(14,2)               AS valor_base_hora,
    NULL::numeric(14,2)               AS valor_total_encargos,
    p.situacao_rh                     AS status,
    pu.nome                           AS gestor_direto,
    u.vertical                        AS vertical,
    u.bu                              AS bu,
    u.tipo_class                      AS tipo_class,
    u.mo_classe                       AS mo,
    u.categoria_nivel                 AS categoria_nivel,
    u.tipo::text                      AS nivel,
    u.cc_equipe                       AS cc_equipe,
    NULL::numeric(14,2)               AS custo_unitario,
    NULL::numeric(14,2)               AS custo_interno,
    NULL::numeric(14,2)               AS venda_liquida,
    NULL::numeric(14,2)               AS venda_com_impostos,
    NULL::numeric(14,2)               AS custo_mensal
FROM org.unidade u
JOIN org.organograma o ON o.id = u.organograma_id
LEFT JOIN org.unidade pu ON pu.id = u.parent_id
LEFT JOIN org.alocacao a
       ON a.unidade_id = u.id AND a.papel = 'responsavel' AND upper_inf(a.vigencia)
LEFT JOIN org.pessoa p ON p.id = a.pessoa_id
ORDER BY o.slug, u.ordem_exibicao, u.nome;
