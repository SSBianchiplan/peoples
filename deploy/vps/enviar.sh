#!/usr/bin/env bash
# Envia o código para o VPS do hub e reinicia o serviço. Rode da RAIZ do repo.
#
#   bash deploy/vps/enviar.sh                       # código + restart
#   PRIMEIRA=1 bash deploy/vps/enviar.sh            # também roda instalar.sh
#   COM_DADOS=1 bash deploy/vps/enviar.sh           # envia dados/ (SÓ na 1ª vez:
#                                                   #  sobrescreve o estado do servidor)
#
# tar por SSH, não rsync: o Git Bash do Windows não tem rsync, e tar funciona
# igual nos três sistemas. O estado vive em /var/lib/peoples e NÃO é tocado
# por um envio normal — deploy troca código, não dado.
set -euo pipefail
VPS="${VPS:?defina VPS=root@<seu-servidor>}"
CHAVE="${CHAVE:-$HOME/.ssh/id_ed25519}"
APP=/opt/peoples
SSH="ssh -i $CHAVE -o BatchMode=yes -o ConnectTimeout=20"

echo "==> código -> $VPS:$APP"
EXCLUIR=(--exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache'
         --exclude='.venv' --exclude='.env' --exclude='.env.*' --exclude='planilhas'
         --exclude='ferramentas/_*' --exclude='testes/__pycache__')
[[ "${COM_DADOS:-0}" == 1 ]] || EXCLUIR+=(--exclude='dados')
tar czf - "${EXCLUIR[@]}" . \
  | $SSH "$VPS" "mkdir -p $APP && tar xzf - -C $APP --overwrite --no-same-owner"

if [[ "${COM_DADOS:-0}" == 1 ]]; then
  echo "==> dados/ -> /var/lib/peoples (estado de demonstração)"
  $SSH "$VPS" "if [ -L $APP/dados ]; then :; elif [ -d $APP/dados ]; then mkdir -p /var/lib/peoples && cp -f $APP/dados/*.json /var/lib/peoples/ && rm -rf $APP/dados && ln -s /var/lib/peoples $APP/dados; fi; chown -R peoples:peoples /var/lib/peoples 2>/dev/null || true"
fi

if [[ "${PRIMEIRA:-0}" == 1 ]]; then
  echo "==> instalar.sh"
  $SSH "$VPS" "DOMINIO=${DOMINIO:-peoples.gplansis.com} ALTERNATIVO=${ALTERNATIVO:-} bash $APP/deploy/vps/instalar.sh"
  exit 0
fi

echo "==> dependências, migrações e restart"
$SSH "$VPS" "chown -R root:peoples $APP && chmod -R g+rX $APP \
  && $APP/.venv/bin/pip install -q -r $APP/requirements.txt \
  && for m in $APP/deploy/migracoes/0*.sql; do sudo -u peoples psql -v ON_ERROR_STOP=1 -d peoples -q -f \$m >/dev/null 2>&1 || true; done \
  && systemctl restart peoples && sleep 5 && systemctl is-active peoples \
  && curl -s -o /dev/null -w 'API %{http_code}\n' http://127.0.0.1:8400/api/v1/organograma \
  && curl -s -o /dev/null -w 'login %{http_code}\n' http://127.0.0.1:8400/login"
