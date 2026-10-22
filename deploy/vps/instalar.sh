#!/usr/bin/env bash
# =============================================================================
#  GPlanSiS|Peoples — instalação no VPS do hub (mesmo método dos demais
#  sistemas: Caddy na frente, serviço no loopback, PostgreSQL
#  do host por socket Unix).
#
#  O QUE ISTO MONTA
#
#      navegador ──HTTPS :443──▶ Caddy ──▶ 127.0.0.1:8400  (uvicorn, orga.main)
#                                            │
#                                            └──▶ /var/run/postgresql  (PG 18 do host,
#                                                 banco `peoples`, peer auth)
#
#  POR QUE NÃO DOCKER AQUI
#
#  O VPS é pequeno e dividido com outros sistemas. Um container com Postgres
#  próprio custaria memória à toa, e o
#  container do app não conseguiria usar peer auth no socket do host (o uid de
#  dentro não existe fora). venv + systemd resolve as duas
#  coisas: o serviço roda como o usuário `peoples`, que é o dono do banco
#  `peoples` — nenhuma senha de banco, nenhuma porta de banco.
#
#  USO (como root, no VPS), depois de `enviar.sh` ter posto o código em /opt:
#     DOMINIO=peoples.gplansis.com bash /opt/peoples/deploy/vps/instalar.sh
#
#  Idempotente: rodar de novo atualiza dependências, reaplica migrações (são
#  idempotentes) e recarrega o Caddy. Não apaga dado nenhum.
# =============================================================================
set -euo pipefail
trap 'echo "  [ERRO]  linha $LINENO: \"$BASH_COMMAND\" falhou (exit $?)" >&2' ERR

DOMINIO="${DOMINIO:-peoples.gplansis.com}"
PORTA="${PORTA:-8400}"
# Nome ALTERNATIVO que já resolve para este VPS (ex.: o hostname técnico do provedor),
# para o sistema ficar alcançável por HTTPS enquanto o A do domínio não aponta.
ALTERNATIVO="${ALTERNATIVO:-}"
APP=/opt/peoples
DADOS=/var/lib/peoples
USUARIO=peoples
BANCO=peoples
AQUI="$(cd "$(dirname "$0")" && pwd)"

ok()    { printf '  \033[32m[ok]\033[0m    %s\n' "$*"; }
aviso() { printf '  \033[33m[aviso]\033[0m %s\n' "$*"; }
erro()  { printf '  \033[31m[ERRO]\033[0m  %s\n' "$*" >&2; }

[[ $EUID -eq 0 ]] || { erro "rode como root"; exit 1; }
[[ -f $APP/orga/main.py ]] || { erro "$APP/orga/main.py não existe — rode enviar.sh antes"; exit 1; }

echo
echo "  ============================================================"
echo "    GPlanSiS|Peoples em $DOMINIO (porta interna $PORTA)"
echo "  ============================================================"
echo

# ---------------------------------------------------------------- DNS
IP_VPS="$(curl -s --max-time 8 https://api.ipify.org || true)"
IP_DNS="$(getent ahostsv4 "$DOMINIO" 2>/dev/null | awk 'NR==1{print $1}' || true)"
if [[ -z "$IP_DNS" ]]; then
  aviso "$DOMINIO ainda não resolve. Instalo tudo; o TLS sai quando o A -> $IP_VPS propagar."
elif [[ "$IP_DNS" != "$IP_VPS" ]]; then
  aviso "$DOMINIO aponta para $IP_DNS, mas este VPS é $IP_VPS. Sem TLS até o DNS bater."
else
  ok "DNS: $DOMINIO -> $IP_VPS"
fi

# ---------------------------------------------------------------- pacotes
export DEBIAN_FRONTEND=noninteractive
command -v caddy >/dev/null || { erro "caddy não está instalado neste VPS (deveria — o hub o usa)"; exit 1; }
command -v psql  >/dev/null || { erro "postgresql não está instalado neste VPS (deveria)"; exit 1; }
apt-get install -y -qq python3-venv python3-dev build-essential libpq-dev >/dev/null 2>&1 || true
ok "pacotes de sistema"

# ---------------------------------------------------------------- usuário e pastas
id -u "$USUARIO" >/dev/null 2>&1 || useradd --system --create-home --home-dir "$DADOS" --shell /usr/sbin/nologin "$USUARIO"
mkdir -p "$DADOS"
# O estado (dados/) mora FORA do código: um deploy troca o código e não toca o
# estado. `dados` dentro de /opt/peoples é um link para /var/lib/peoples.
if [[ -d $APP/dados && ! -L $APP/dados ]]; then
  # primeira instalação: o que veio com o código (a base de demonstração) semeia o estado
  cp -n "$APP"/dados/*.json "$DADOS"/ 2>/dev/null || true
  rm -rf "$APP/dados"
fi
[[ -L $APP/dados ]] || ln -s "$DADOS" "$APP/dados"
chown -R "$USUARIO:$USUARIO" "$DADOS"
chown -R root:"$USUARIO" "$APP"
chmod -R g+rX "$APP"
ok "código em $APP · estado em $DADOS (dono: $USUARIO)"

# ---------------------------------------------------------------- python
[[ -x $APP/.venv/bin/python ]] || python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip wheel
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
# psycopg[binary]: o espelho no Postgres precisa do driver; sem ele o sistema
# sobe, mas a aba Banco de dados diz "sem driver" e nada desce para o banco.
"$APP/.venv/bin/pip" install -q "psycopg[binary]>=3.2"
ok "venv com dependências (+ psycopg)"

# ---------------------------------------------------------------- .env
if [[ ! -f $APP/.env ]]; then
  SEGREDO="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  cat > "$APP/.env" <<EOF
# Gerado por instalar.sh em $(date -u +%FT%TZ). Edite à vontade; não versione.
JWT_SECRET=$SEGREDO
ORG_EXIGIR_LOGIN=1
ORG_COOKIE_SEGURO=1
ORG_DOMINIOS=
ORG_EMAIL_EXEMPLO=nome.sobrenome@gplansis.com
ORG_SUPERADMINS=contato@gplansis.com
ORG_IDIOMA=pt-BR
ORG_PORT=$PORTA
# Base de dados local: PostgreSQL 18 do host, socket Unix, peer auth (usuário peoples).
ORG_DATABASE_URL=postgresql:///$BANCO?host=/var/run/postgresql
ORG_ESPELHO=1
# MarIA (opcional): sem a chave o chat fica indisponível, o resto funciona.
ANTHROPIC_API_KEY=
MARIA_MODEL=claude-haiku-4-5
EOF
  ok ".env criado (JWT_SECRET novo, login exigido, espelho no banco ligado)"
else
  ok ".env existente preservado"
fi
chown root:"$USUARIO" "$APP/.env"; chmod 0640 "$APP/.env"

# ---------------------------------------------------------------- banco
# Papel = usuário do SO (peer auth) e dono do banco. Extensões primeiro, como
# superusuário; o schema depois, como `peoples` — assim TUDO fica com o dono
# certo e nada exige senha.
sudo -u postgres psql -v ON_ERROR_STOP=1 -tAc "SELECT 1 FROM pg_roles WHERE rolname='$USUARIO'" | grep -q 1 \
  || sudo -u postgres createuser --no-superuser --no-createdb --no-createrole "$USUARIO"
sudo -u postgres psql -v ON_ERROR_STOP=1 -tAc "SELECT 1 FROM pg_database WHERE datname='$BANCO'" | grep -q 1 \
  || sudo -u postgres createdb -O "$USUARIO" "$BANCO"
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$BANCO" -q -c "CREATE EXTENSION IF NOT EXISTS btree_gist; CREATE EXTENSION IF NOT EXISTS pgcrypto; CREATE EXTENSION IF NOT EXISTS citext;"
if ! sudo -u "$USUARIO" psql -d "$BANCO" -tAc "SELECT 1 FROM information_schema.schemata WHERE schema_name='org'" | grep -q 1; then
  sudo -u "$USUARIO" psql -v ON_ERROR_STOP=1 -d "$BANCO" -q -f "$APP/orga/schema.sql"
  ok "schema.sql aplicado (banco novo)"
fi
# Migrações são idempotentes — reaplicar num banco novo é inofensivo, e num
# banco que já existia é exatamente o que se quer.
for m in "$APP"/deploy/migracoes/0*.sql; do
  sudo -u "$USUARIO" psql -v ON_ERROR_STOP=1 -d "$BANCO" -q -f "$m" >/dev/null 2>&1 \
    || aviso "migração $(basename "$m") avisou (normal se o schema novo já a contém)"
done
ok "banco $BANCO pronto (dono $USUARIO, socket, sem senha)"

# ---------------------------------------------------------------- systemd
sed -e "s#__APP__#$APP#g" -e "s#__DADOS__#$DADOS#g" -e "s#__USUARIO__#$USUARIO#g" \
    "$AQUI/peoples.service" > /etc/systemd/system/peoples.service
systemctl daemon-reload
systemctl enable peoples >/dev/null 2>&1
systemctl restart peoples
sleep 4
systemctl is-active --quiet peoples || { journalctl -u peoples -n 40 --no-pager; erro "peoples não subiu"; exit 1; }
ok "peoples.service ativo (uvicorn em 127.0.0.1:$PORTA, usuário $USUARIO)"

# ---------------------------------------------------------------- caddy
mkdir -p /var/log/caddy && touch /var/log/caddy/peoples.log && chown caddy:caddy /var/log/caddy/peoples.log
sed -e "s#__DOMINIO__#$DOMINIO#g" -e "s#__PORTA__#$PORTA#g" "$AQUI/peoples.caddy" > /etc/caddy/peoples.caddy
if [[ -n "$ALTERNATIVO" ]]; then
  printf '
# Endereço provisório (hostname do VPS) até o A de %s apontar para cá.
%s {
	import peoples_app
}
' "$DOMINIO" "$ALTERNATIVO" >> /etc/caddy/peoples.caddy
fi
if ! grep -q "peoples.caddy" /etc/caddy/Caddyfile; then
  cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak-$(date +%Y%m%d-%H%M%S)"
  printf '\n# GPlanSiS|Peoples (deploy separado — ver /etc/caddy/peoples.caddy)\nimport /etc/caddy/peoples.caddy\n' >> /etc/caddy/Caddyfile
fi
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
systemctl reload caddy
ok "caddy: bloco $DOMINIO${ALTERNATIVO:+ (+ $ALTERNATIVO)} -> 127.0.0.1:$PORTA"

# ---------------------------------------------------------------- prova
CODIGO="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "http://127.0.0.1:$PORTA/api/v1/organograma" || true)"
# 303 é o esperado com ORG_EXIGIR_LOGIN=1 (a API está atrás da mesma porta de login).
[[ "$CODIGO" == 200 || "$CODIGO" == 303 ]] && ok "API responde $CODIGO em /api/v1/organograma" || aviso "API respondeu $CODIGO"
CODIGO="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "http://127.0.0.1:$PORTA/login" || true)"
[[ "$CODIGO" == 200 ]] && ok "tela de login responde 200" || aviso "login respondeu $CODIGO"
echo
echo "  Pronto. Próximos passos:"
echo "   1. DNS: A  peoples -> $IP_VPS  (hPanel › gplansis.com › DNS). O TLS sai sozinho."
echo "   2. Primeiro acesso em https://$DOMINIO/login cria o administrador inicial,"
echo "      ou: sudo -u $USUARIO $APP/.venv/bin/python -m orga.usuarios definir tic@gplansis.com"
echo "   3. Logs: journalctl -u peoples -f   ·   tail -f /var/log/caddy/peoples.log"
echo "   4. Lakehouse (base intermediária do hub, opcional):"
echo "      bash $APP/deploy/lakehouse/instalar-lake.sh"
