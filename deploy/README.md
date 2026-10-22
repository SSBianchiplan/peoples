# Implantação — GPlanSiS|Peoples no hub gplansis.com

Como o Peoples vai do repositório ao ar em **peoples.gplansis.com**, e como
operá-lo. Este documento é o mapa; os scripts em `deploy/vps/` são o território.

## Onde e como

Os sistemas do hub que precisam de um processo próprio vivem num **VPS**
(Linux), atrás de um único Caddy que faz TLS automático e encaminha cada nome
para o serviço dele. O Peoples entra pelo mesmo desenho:

```
navegador ──HTTPS :443──▶ Caddy ──▶ 127.0.0.1:8400   uvicorn (orga.main), 1 worker
                                        │
                                        └──▶ /var/run/postgresql   PostgreSQL 18 do host
                                             banco `peoples` · peer auth · sem senha
```

| Onde | O quê |
|---|---|
| `/opt/peoples` | código, venv (`.venv`), `.env` (0640 `root:peoples`) |
| `/var/lib/peoples` | o **estado**: `estado.json`, `estado-<slug>.json`, `organogramas.json`, `usuarios.json` (`/opt/peoples/dados` é um link para cá) |
| `peoples.service` | uvicorn em `127.0.0.1:8400`, usuário `peoples`, hardening systemd |
| `/etc/caddy/peoples.caddy` | o bloco de site, importado pelo `Caddyfile` |
| banco `peoples` | PostgreSQL 18 do host, dono `peoples`, schema `org` (+ migrações 001–009) |
| `/var/log/caddy/peoples.log` · `journalctl -u peoples` | logs |

**Sem Docker em produção, e é decisão.** O VPS é pequeno e dividido com outros
sistemas; um Postgres em container custaria memória à toa, e um container do app
não conseguiria usar peer auth no socket do host. venv + systemd resolve as duas
coisas. O `Dockerfile` e o `docker-compose.yml` continuam
servindo a quem desenvolve ou roda fora do hub.

**Tudo persiste na base de dados local.** Com `ORG_ESPELHO=1` (ligado pelo
instalador), toda gravação desce para o Postgres pela lógica que o sistema já
tinha: estrutura (`org.unidade`, `org.pessoa`, …), ledger (`org.evento`), os
módulos (Skills, Conversa de Valor, Avaliação, Avaliação Mestre, One-on-One) e —
novidade da migração 009 — o **resto do estado** (`org.estado_extra`: configuração,
RBAC, colapso, filtros, provisionamentos, log de acessos) e as **credenciais do
login** (`org.usuario`). O `estado.json` continua sendo escrito a cada mutação e
é a queda: sem banco o sistema segue de pé; sem arquivo, o banco restaura tudo.

## Primeira instalação

Da sua máquina, na raiz do repositório (defina `VPS=root@<seu-servidor>` e, se preciso, `CHAVE=<caminho da chave SSH>`):

```bash
VPS=root@<seu-servidor> COM_DADOS=1 PRIMEIRA=1 bash deploy/vps/enviar.sh
```

O que acontece: o código vai por `tar | ssh` para `/opt/peoples` (sem `.git`,
sem `.env`, sem `planilhas/`); a base de **demonstração** gerada localmente (organograma de teste de
28 pessoas fictícias — ver o README da raiz) semeia `/var/lib/peoples`; e
`instalar.sh` roda no servidor:

1. cria o usuário de sistema `peoples` e o venv com `requirements.txt` + `psycopg`;
2. escreve o `.env` (JWT_SECRET novo, `ORG_EXIGIR_LOGIN=1`, cookie seguro,
   `ORG_DATABASE_URL` pelo socket, `ORG_ESPELHO=1`) — só se ainda não existir;
3. cria o papel e o banco `peoples`, aplica as extensões (como `postgres`), o
   `schema.sql` (como `peoples`, dono de tudo) e as migrações (idempotentes);
4. instala e sobe `peoples.service`, espera e confere `systemctl is-active`;
5. escreve `/etc/caddy/peoples.caddy`, acrescenta o `import` ao `Caddyfile`
   (com backup), valida e recarrega o Caddy;
6. prova `GET /api/v1/organograma` e `GET /login` na porta interna.

Depois disso faltam duas coisas que **não são código**:

- **DNS.** O domínio precisa de um registro `A` apontando para o IP do VPS.
  O Caddy já tem o bloco e reinsiste no certificado com recuo exponencial:
  quando o A propagar, o TLS sai sozinho.
- **O primeiro administrador.** Com nenhum usuário cadastrado, a tela
  `/login` oferece **Criar administrador inicial** (uma vez só). Ou, no
  servidor: `sudo -u peoples /opt/peoples/.venv/bin/python -m orga.usuarios definir admin@exemplo.com`.
  Quem está em `ORG_SUPERADMINS` (padrão `contato@gplansis.com`) entra como
  Administrador total em qualquer organograma; os demais recebem o papel do
  RBAC (Configurações › Permissões) — e a senha, pelo mesmo lugar.

## Atualizar

```bash
bash deploy/vps/enviar.sh
```

Envia o código, reinstala dependências, reaplica as migrações (idempotentes) e
reinicia o serviço. **Não toca em `/var/lib/peoples`**: deploy troca código, não
dado. `COM_DADOS=1` só na primeira vez — ele sobrescreve o estado do servidor.

## Login próprio (sem SSO)

O Entra ID saiu. O login é do próprio sistema: e-mail + senha, hash **scrypt**
(biblioteca padrão), arquivo `usuarios.json` com espelho em `org.usuario`, freio a
força bruta (5 erros → 1 min), mensagem única para "não existe" e "senha errada",
senha temporária com troca obrigatória no primeiro acesso, e troca de senha pelo
menu do avatar (`/senha`). Papel e escopo continuam no RBAC do organograma — a
credencial só prova identidade.

## Operar

```bash
ssh root@<seu-servidor>
systemctl status peoples            # o serviço
journalctl -u peoples -f            # log do app
tail -f /var/log/caddy/peoples.log  # acessos HTTP
sudo -u peoples psql -d peoples -c "select count(*) from org.unidade"
sudo -u peoples /opt/peoples/.venv/bin/python -m orga.usuarios listar
```

Reverter: o código anterior não fica no servidor (tar sobrescreve), então
reverter é reenviar o commit anterior com `enviar.sh`. O estado nunca volta num
deploy — vive em `/var/lib/peoples` e no Postgres, à parte do código.

## Migrações

`schema.sql` só roda em banco novo. Banco que já existe recebe
`deploy/migracoes/00X-*.sql`, idempotentes, que o `enviar.sh` reaplica a cada
envio (num banco novo elas são inofensivas). A `009` traz `org.usuario` e
`org.estado_extra`.

## Duas armadilhas herdadas (não repita)

- **Nunca** imprima a configuração resolvida com segredo à mostra
  (`docker compose config`, `cat .env` em terminal compartilhado).
- **Nunca** mate processo por nome no VPS: a máquina roda outros sistemas.
  Encerre pelo `systemctl` do serviço certo.
