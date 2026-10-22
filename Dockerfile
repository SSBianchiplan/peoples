# GPlanSiS|Peoples — imagem de execução.
#
# Uma etapa só. Não há build de front para separar em multi-stage: o htmx está
# vendorizado, não existe transpilação, e o SVG é montado pelo servidor. Um
# segundo estágio aqui copiaria os mesmos arquivos duas vezes para economizar
# nada.
#
# `slim` e não `alpine`: pillow e as rodas de `uvicorn[standard]` têm binário
# pronto para glibc e não para musl. Em alpine, o mesmo `pip install` compila
# do zero e a imagem cresce mais do que a diferença de base economiza.
FROM python:3.12-slim

# `PYTHONDONTWRITEBYTECODE` porque o filesystem da imagem é descartável, e
# `PYTHONUNBUFFERED` porque log em buffer não aparece em `docker logs` quando o
# processo morre — que é justamente quando se quer ler o log.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ORG_PORT=8080

WORKDIR /app

# As dependências antes do código: elas mudam uma vez por mês, o código muda
# dez vezes por dia. Invertendo a ordem, cada edição de template reinstalaria
# fastapi.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Não roda como root. O processo não precisa escrever em lugar nenhum além de
# `/app/dados`, e é esse diretório — e só ele — que muda de dono.
RUN useradd --uid 10001 --no-create-home --home-dir /app --shell /usr/sbin/nologin orga \
    && mkdir -p /app/dados \
    && chown -R orga:orga /app/dados
USER orga

# A porta sai do ambiente, com 8080 de padrão. O `docker-compose.yml` publica
# `${ORG_PORT}:${ORG_PORT}`; com a porta fixa aqui, trocar `ORG_PORT` faria o
# container escutar em 8080 enquanto o compose mapeia outra — o serviço sobe, o
# healthcheck passa por dentro, e de fora nada responde.
EXPOSE 8080

# `/api/v1/organograma` e não `/`: a raiz devolve 200 mesmo com o estado vazio,
# e um healthcheck que passa com o sistema sem dado não está checando nada.
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request,sys; \
p = os.environ.get('ORG_PORT', '8080'); \
sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/api/v1/organograma', timeout=3).status == 200 else 1)"

# Um worker. O estado vive em memória e é gravado num arquivo; dois workers
# seriam dois estados divergentes escrevendo no mesmo `estado.json`, e o último
# a gravar apagaria o trabalho do outro. Escalar isto pede o Postgres do
# `schema.sql` primeiro — está desenhado, não está ligado.
CMD ["sh", "-c", "uvicorn orga.main:app --host 0.0.0.0 --port ${ORG_PORT:-8080} --workers 1"]
