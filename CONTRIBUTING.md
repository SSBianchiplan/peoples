# Como contribuir com o GPlanSiS|Peoples

Obrigado pelo interesse! Este guia explica como propor mudanças de forma que a revisão seja rápida.

## Antes de começar
- Leia o [código de conduta](CODE_OF_CONDUCT.md).
- Para mudanças maiores que uma correção pontual, **abra uma issue primeiro** (modelos "Ideia" ou "Bug") e combine a abordagem.
- Falhas de segurança **não** vão em issue pública: siga a [política de segurança](SECURITY.md).
- O Peoples trata **dado pessoal**. Nunca anexe a issues, PRs, testes ou capturas nomes, e-mails, CPF, salários, fotos ou planilhas de pessoas reais — use a base fictícia.

## Ambiente de desenvolvimento
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# base de demonstração fictícia (fica em dados/, fora do Git)
.venv/bin/python ferramentas/organograma_teste.py
.venv/bin/python ferramentas/gerar_skills.py
.venv/bin/python ferramentas/gerar_ciclo_pessoas.py

.venv/bin/uvicorn orga.main:app --reload --port 8080
.venv/bin/python -m pytest -q
```
Sem `.env`, o sistema sobe **aberto** em `http://localhost:8080` — o modo de trabalho de mesa. O frontend não tem etapa de build (templates Jinja + htmx vendorizado): edite e recarregue.

## Organização do código
- `orga/main.py` — o app FastAPI: rotas, vistas e fragmentos htmx.
- `orga/dominio.py` — modelo e motor de layout do organograma (SVG montado no servidor).
- `orga/<assunto>.py` — um módulo por assunto do negócio: `cargos`, `centros`, `dcr` (Skills), `cgv` (Conversa de Valor), `talentos` (Avaliação), `gptw` (clima), `onebyone`, `painel_rh`, `maria`, `importador`, `pdf`, `banco`, `acesso`, `usuarios`, `idiomas`…
- `web/templates/` — HTML (Jinja); `web/marca/` — identidade visual; `web/vendor/` — bibliotecas de terceiros.
- `testes/` — a suíte (`pytest`); `deploy/` — VPS (systemd + Caddy), migrações e lakehouse.
- `docs/DECISOES.md` — por que cada parte é como é. Leia a seção do módulo antes de mexer nele.

## Regras do projeto
- **Três idiomas**: toda string nova da interface nasce em pt-BR, en-US e es (`orga/idiomas.py`); `testes/test_idiomas.py` reprova o que faltar.
- **Sem dependências de build no frontend** e sem CDN no app: tudo é servido localmente.
- **Permissão e escopo no servidor**: qualquer ação nova é conferida no backend, não só escondida na interface.
- **Ledger**: mutação relevante registra evento na trilha hash-encadeada.
- **IA propõe, humano decide**: nenhuma ação da MarIA altera dados sem aprovação explícita.
- **Um worker**: o estado vive em memória; não suba o uvicorn com mais de um worker.
- Nunca inclua segredos, `.env`, `dados/`, `planilhas/` ou dados reais de pessoas em commits ou capturas.

## Pull requests
1. Faça um fork e crie uma branch a partir de `main` (`feat/…`, `fix/…`, `docs/…`).
2. Commits pequenos, com mensagem no imperativo explicando o porquê.
3. Preencha o modelo do PR: o que mudou, como testou, capturas (só com dados fictícios) se mexer na interface.
4. Rode `python -m pytest -q` antes de enviar.

## Dúvidas
Abra uma issue com o modelo "Pergunta" ou escreva para contato@gplansis.com.
