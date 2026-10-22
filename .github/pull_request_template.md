## O que muda
<!-- Resumo da mudança e o porquê. Referencie a issue: "Fecha #123". -->

## Tipo
- [ ] Correção de bug
- [ ] Nova funcionalidade
- [ ] Documentação
- [ ] Refatoração / manutenção

## Como testei
<!-- Passos, ambiente (local/Docker), navegadores. `python -m pytest -q` passou? -->

## Capturas
<!-- Se mexeu na interface, antes/depois — só com a base fictícia. -->

## Checklist
- [ ] `python -m pytest -q` passa (inclusive `testes/test_idiomas.py`)
- [ ] Texto novo da interface existe em pt-BR, en-US e es (`orga/idiomas.py`)
- [ ] Permissão e escopo conferidos no servidor (`orga/acesso.py` / `orga/main.py`)
- [ ] Sem segredos, `.env`, `dados/`, planilhas ou **dados reais de colaboradores** no commit
- [ ] Mutação relevante registra evento no ledger
