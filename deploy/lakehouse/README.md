# GPlanSiS · Lakehouse — a base intermediária do hub

Cada sistema do hub é dono do seu banco. **Ninguém escreve no banco do outro.**
Quando um sistema precisa de dado alheio, ele lê aqui.

```
peoples  ──SELECT (peoples_leitor)──▶ ETL ──▶  gplansis_lake
prioria  ──SELECT (papel próprio)───▶ ETL ──▶  bronze.<sistema>_*
pcp/aps  ──SELECT (papel próprio)───▶ ETL ──▶       │  silver.*  (conformado)
                                                    ▼  gold.*    (métricas)
     qualquer sistema, BI ou agente ──SELECT (lake_leitor) ou API ──▶ gold/silver
```

## As três camadas

| Camada | O que é | Quem escreve | Quem lê |
|---|---|---|---|
| `bronze` | retrato cru de cada origem, por snapshot (`bronze.peoples_pessoa`, …) | só o ETL | ninguém de fora — tem nome de gente |
| `silver` | o conformado: uma linha por entidade, vocabulário único entre sistemas | vistas sobre bronze | `lake_leitor` |
| `gold` | métricas prontas: headcount, amplitude, cobertura de Skills e Conversa de Valor, 9-box, PTI, riscos | vistas sobre silver | `lake_leitor` + API |

`bronze.carga` registra cada execução (início, fim, ok, linhas por tabela). As
vistas de `silver` leem **a última carga OK** — uma carga interrompida no meio
nunca aparece em métrica nenhuma, e a anterior continua valendo.

## Isolamento — imposto por permissão, não por combinado

| Papel | Pode | Não pode |
|---|---|---|
| `peoples_leitor` | `SELECT` em `peoples.org` | qualquer escrita, em qualquer banco |
| `lake` (dono) | tudo em `gplansis_lake` | nada em `peoples` |
| `lake_leitor` | `SELECT` em `gold` e `silver` | escrever; ler `bronze` |

Provado na instalação (as duas tentativas abaixo **devem** falhar):

```
origem:    ERROR:  permission denied for table unidade
lakehouse: ERROR:  permission denied for schema gold
```

## Instalar (uma vez, como root no VPS)

```bash
bash /opt/peoples/deploy/lakehouse/instalar-lake.sh
```

Cria o banco `gplansis_lake`, os três papéis, o schema, o `/etc/gplansis/lake.env`
(0640) com as credenciais e o timer `gplansis-lake-etl.timer`, que carrega de
hora em hora. É idempotente e **não toca** em nada que já roda no VPS.

## Consumir

**Por SQL** (outro sistema, BI, notebook):

```bash
psql "$LAKE_LEITOR_DSN" -c 'select * from gold.painel_executivo'
psql "$LAKE_LEITOR_DSN" -c "select * from gold.clima_pti where dimensao='pilar'"
```

**Por API** (máquina-a-máquina, com token de serviço em `ORG_LAKE_TOKENS`):

```bash
curl -H "Authorization: Bearer $TOKEN" https://peoples.gplansis.com/api/v1/lake
curl -H "Authorization: Bearer $TOKEN" https://peoples.gplansis.com/api/v1/lake/painel_executivo
curl -H "Authorization: Bearer $TOKEN" \
     "https://peoples.gplansis.com/api/v1/lake/clima_pti?organograma=peoples&limite=50"
```

`GET /api/v1/lake` devolve o catálogo das vistas e a data da última carga. Só
existe `GET`: não há rota de escrita, e o nome da vista vem de um catálogo
fechado (`orga/lake.py`) — nome vindo da URL nunca vira SQL.

## Acrescentar um sistema ao lakehouse

1. No banco de origem, criar um papel `<sistema>_leitor` com `SELECT` e nada mais.
2. Criar as tabelas `bronze.<sistema>_*` em `schema-lake.sql`.
3. Escrever a leitura em `ferramentas/lake_etl.py` (uma função `ler_<sistema>`)
   e um serviço/timer próprio, ou estender o existente.
4. Conformar em `silver` e publicar a métrica em `gold` — **a conta mora numa
   vista só**, para dois sistemas nunca calcularem "amplitude média" de dois
   jeitos.
5. Publicar a vista no catálogo de `orga/lake.py` se ela deve sair pela API.

## LGPD

O lakehouse recebe o que o Peoples já publica: sem remuneração, CPF, endereço
ou dado de saúde. **Clima entra agregado** — nunca a resposta individual —, com
o piso de 5 respondentes por estrato aplicado no ETL: num recorte de três
pessoas o índice descreveria indivíduos, e o instrumento prometeu anonimato.
`bronze` fica fora do alcance de qualquer consumidor.
