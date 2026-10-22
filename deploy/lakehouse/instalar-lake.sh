#!/usr/bin/env bash
# =============================================================================
#  GPlanSiS · Lakehouse — instalação no VPS do hub
#
#  Cria a base intermediária que os sistemas leem uns dos outros SEM tocar no
#  banco alheio. O que este script monta, e por quê:
#
#    banco `gplansis_lake`  · dono `lake`         — as três camadas (bronze/silver/gold)
#    papel `peoples_leitor` · SELECT em `peoples` — a credencial do ETL na origem
#    papel `lake_leitor`    · SELECT em gold/silver — a credencial de QUEM CONSOME
#    serviço `gplansis-lake-etl.timer`            — a carga, de hora em hora
#
#  As permissões são o contrato: `peoples_leitor` não tem INSERT/UPDATE/DELETE
#  em lugar nenhum, e `lake_leitor` não escreve nem no lakehouse. Um sistema
#  não consegue mexer no outro nem por engano.
#
#  NÃO TOCA em nada que já roda no VPS: não altera bancos existentes (só CRIA
#  papéis e concede SELECT), não mexe no Caddy nem nos outros serviços.
#
#  USO (como root, no VPS):
#     bash /opt/peoples/deploy/lakehouse/instalar-lake.sh
#
#  Idempotente: rodar de novo reaplica schema e permissões, sem duplicar nada.
# =============================================================================
set -euo pipefail
trap 'echo "  [ERRO]  linha $LINENO: \"$BASH_COMMAND\" falhou (exit $?)" >&2' ERR

APP=/opt/peoples
LAKE_DB=gplansis_lake
LAKE_USER=lake
LEITOR_ORIGEM=peoples_leitor      # lê o banco do Peoples (SELECT e nada mais)
LEITOR_LAKE=lake_leitor           # lê o lakehouse (o papel dos consumidores)
ORIGEM_DB=peoples
ENVDIR=/etc/gplansis
ENVFILE=$ENVDIR/lake.env
AQUI="$(cd "$(dirname "$0")" && pwd)"

ok()    { printf '  \033[32m[ok]\033[0m    %s\n' "$*"; }
aviso() { printf '  \033[33m[aviso]\033[0m %s\n' "$*"; }
erro()  { printf '  \033[31m[ERRO]\033[0m  %s\n' "$*" >&2; }

[[ $EUID -eq 0 ]] || { erro "rode como root"; exit 1; }
command -v psql >/dev/null || { erro "postgresql não encontrado"; exit 1; }
[[ -x $APP/.venv/bin/python ]] || { erro "$APP/.venv não existe — instale o Peoples antes"; exit 1; }

echo
echo "  ============================================================"
echo "    GPlanSiS · Lakehouse ($LAKE_DB)"
echo "  ============================================================"
echo

# ---------------------------------------------------------------- usuário e banco
id -u "$LAKE_USER" >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/lake --shell /usr/sbin/nologin "$LAKE_USER"
sudo -u postgres psql -v ON_ERROR_STOP=1 -tAc "SELECT 1 FROM pg_roles WHERE rolname='$LAKE_USER'" | grep -q 1 \
  || sudo -u postgres createuser --no-superuser --no-createdb --no-createrole "$LAKE_USER"
sudo -u postgres psql -v ON_ERROR_STOP=1 -tAc "SELECT 1 FROM pg_database WHERE datname='$LAKE_DB'" | grep -q 1 \
  || sudo -u postgres createdb -O "$LAKE_USER" "$LAKE_DB"
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$LAKE_DB" -q -c "CREATE EXTENSION IF NOT EXISTS unaccent;"
ok "banco $LAKE_DB (dono $LAKE_USER, socket, peer auth)"

# ---------------------------------------------------------------- papel de LEITURA na origem
# A senha vive só no .env do lakehouse (0640). O papel não recebe nenhum
# privilégio de escrita — nem agora, nem por herança: `pg_read_all_data` não é
# usado de propósito (ele daria leitura em TODOS os bancos futuros também).
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$LEITOR_ORIGEM'" | grep -q 1; then
  SENHA_ORIGEM="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  sudo -u postgres psql -v ON_ERROR_STOP=1 -q -c \
    "CREATE ROLE $LEITOR_ORIGEM LOGIN PASSWORD '$SENHA_ORIGEM' NOSUPERUSER NOCREATEDB NOCREATEROLE;"
  NOVA_SENHA=1
else
  SENHA_ORIGEM=""
  NOVA_SENHA=0
  aviso "papel $LEITOR_ORIGEM já existe — senha preservada"
fi
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$ORIGEM_DB" -q <<SQL
GRANT CONNECT ON DATABASE $ORIGEM_DB TO $LEITOR_ORIGEM;
GRANT USAGE ON SCHEMA org TO $LEITOR_ORIGEM;
GRANT SELECT ON ALL TABLES IN SCHEMA org TO $LEITOR_ORIGEM;
ALTER DEFAULT PRIVILEGES IN SCHEMA org GRANT SELECT ON TABLES TO $LEITOR_ORIGEM;
-- Explícito, para não depender de "não concedi": nada de escrita.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA org FROM $LEITOR_ORIGEM;
REVOKE CREATE ON SCHEMA org FROM $LEITOR_ORIGEM;
REVOKE ALL ON SCHEMA public FROM $LEITOR_ORIGEM;
SQL
ok "papel $LEITOR_ORIGEM: SELECT em $ORIGEM_DB.org — sem escrita"

# ---------------------------------------------------------------- schema do lakehouse
sudo -u "$LAKE_USER" psql -v ON_ERROR_STOP=1 -d "$LAKE_DB" -q -f "$AQUI/schema-lake.sql"
ok "schema-lake.sql aplicado (bronze · silver · gold)"

# ---------------------------------------------------------------- papel de LEITURA do lakehouse
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$LEITOR_LAKE'" | grep -q 1; then
  SENHA_LAKE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  sudo -u postgres psql -v ON_ERROR_STOP=1 -q -c \
    "CREATE ROLE $LEITOR_LAKE LOGIN PASSWORD '$SENHA_LAKE' NOSUPERUSER NOCREATEDB NOCREATEROLE;"
else
  SENHA_LAKE=""
  aviso "papel $LEITOR_LAKE já existe — senha preservada"
fi
sudo -u "$LAKE_USER" psql -v ON_ERROR_STOP=1 -d "$LAKE_DB" -q <<SQL
GRANT USAGE ON SCHEMA gold, silver TO $LEITOR_LAKE;
GRANT SELECT ON ALL TABLES IN SCHEMA gold, silver TO $LEITOR_LAKE;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold, silver GRANT SELECT ON TABLES TO $LEITOR_LAKE;
-- bronze é retrato cru com nome de gente: fica fora do alcance do consumidor.
REVOKE ALL ON SCHEMA bronze FROM $LEITOR_LAKE;
REVOKE ALL ON SCHEMA public FROM $LEITOR_LAKE;
SQL
sudo -u postgres psql -v ON_ERROR_STOP=1 -q -c "GRANT CONNECT ON DATABASE $LAKE_DB TO $LEITOR_LAKE;"
ok "papel $LEITOR_LAKE: SELECT em gold e silver — sem bronze, sem escrita"

# ---------------------------------------------------------------- .env
mkdir -p "$ENVDIR"
if [[ ! -f $ENVFILE ]]; then
  cat > "$ENVFILE" <<EOF
# Lakehouse GPlanSiS — gerado por instalar-lake.sh em $(date -u +%FT%TZ).
# O ETL lê a ORIGEM com um papel somente-leitura e escreve só no lakehouse.
LAKE_DSN=postgresql:///$LAKE_DB?host=/var/run/postgresql
LAKE_ORIGEM_PEOPLES=postgresql://$LEITOR_ORIGEM:$SENHA_ORIGEM@127.0.0.1:5432/$ORIGEM_DB
# Credencial de quem CONSOME o lakehouse (outros sistemas do hub, BI):
LAKE_LEITOR_DSN=postgresql://$LEITOR_LAKE:$SENHA_LAKE@127.0.0.1:5432/$LAKE_DB
EOF
  chown root:"$LAKE_USER" "$ENVFILE"; chmod 0640 "$ENVFILE"
  ok "$ENVFILE criado (0640 root:$LAKE_USER)"
else
  aviso "$ENVFILE já existe — preservado"
fi

# O serviço do Peoples lê o lakehouse pela API: recebe só a credencial de LEITURA.
if ! grep -q "^LAKE_LEITOR_DSN=" "$APP/.env" 2>/dev/null; then
  LINHA="$(grep '^LAKE_LEITOR_DSN=' "$ENVFILE" || true)"
  [[ -n "$LINHA" ]] && { echo "$LINHA" >> "$APP/.env"; ok "LAKE_LEITOR_DSN publicado no .env do Peoples (só leitura)"; }
fi

# ---------------------------------------------------------------- serviço + timer
cat > /etc/systemd/system/gplansis-lake-etl.service <<EOF
[Unit]
Description=GPlanSiS Lakehouse — carga (Peoples -> bronze)
After=postgresql.service
Wants=postgresql.service

[Service]
Type=oneshot
User=$LAKE_USER
Group=$LAKE_USER
EnvironmentFile=$ENVFILE
ExecStart=$APP/.venv/bin/python $APP/ferramentas/lake_etl.py --limpar 30
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
EOF
cat > /etc/systemd/system/gplansis-lake-etl.timer <<'EOF'
[Unit]
Description=GPlanSiS Lakehouse — carga de hora em hora

[Timer]
OnCalendar=hourly
RandomizedDelaySec=180
Persistent=true

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now gplansis-lake-etl.timer >/dev/null 2>&1
ok "timer gplansis-lake-etl.timer ativo (de hora em hora)"

# ---------------------------------------------------------------- primeira carga + prova
systemctl start gplansis-lake-etl.service || true
sleep 2
sudo -u "$LAKE_USER" psql -d "$LAKE_DB" -Atc \
  "SELECT 'carga ' || id || ' · ' || COALESCE(ok::text,'?') || ' · ' || linhas::text
     FROM bronze.carga ORDER BY id DESC LIMIT 1" | sed 's/^/  [ok]    /'

echo
echo "  Prova de isolamento (o consumidor não escreve, o ETL não escreve na origem):"
# As duas tentativas abaixo DEVEM falhar — é isso que provam. `set +e` porque
# um erro esperado não pode derrubar o instalador.
set +e
PGPASSWORD="$(grep '^LAKE_ORIGEM_PEOPLES=' "$ENVFILE" | sed 's/.*peoples_leitor://; s/@.*//')" \
  psql -h 127.0.0.1 -U "$LEITOR_ORIGEM" -d "$ORIGEM_DB" -Atc \
  "INSERT INTO org.unidade (organograma_id, codigo, nome, tipo) VALUES (gen_random_uuid(),'X','X','area')" \
  2>&1 | head -1 | sed 's/^/    origem: /'
PGPASSWORD="$(grep '^LAKE_LEITOR_DSN=' "$ENVFILE" | sed 's/.*lake_leitor://; s/@.*//')" \
  psql -h 127.0.0.1 -U "$LEITOR_LAKE" -d "$LAKE_DB" -Atc \
  "CREATE TABLE gold.x(i int)" 2>&1 | head -1 | sed 's/^/    lakehouse: /' || true
set -e
echo
echo "  Consumir de outro sistema:"
echo "    psql \"\$LAKE_LEITOR_DSN\" -c 'select * from gold.painel_executivo'"
echo "    curl -H \"Authorization: Bearer <token>\" https://peoples.gplansis.com/api/v1/lake/painel_executivo"
