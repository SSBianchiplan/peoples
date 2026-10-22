# Política de segurança

## Versões suportadas
| Versão | Suporte |
|---|---|
| 1.2.x (em produção em peoples.gplansis.com) | ✅ |
| < 1.2 | ❌ |

## Como relatar uma vulnerabilidade
**Não abra issue pública.** Envie um e-mail para **contato@gplansis.com** com o assunto `[SEGURANÇA] GPlanSiS|Peoples`, contendo:
- descrição do problema e impacto;
- passos para reproduzir (ou prova de conceito);
- versão, navegador e ambiente usados.

Confirmamos o recebimento assim que possível, mantemos você informado sobre a correção e damos crédito na publicação, se desejar.

## Escopo
Autenticação e sessão (JWT em cookie HttpOnly, scrypt, freio a força bruta), RBAC e escopo de leitura por pessoa, **sigilo dos módulos de pessoas** (Conversa de Valor, Avaliação, One-on-One, pesquisa de clima anônima com piso de respondentes), trilha de auditoria hash-encadeada, API do lakehouse com tokens de serviço, proxy da MarIA (chave da Anthropic só no servidor) e cabeçalhos/CSP.

Este sistema trata **dado pessoal (LGPD)**. Testes devem ser feitos numa instância local com a base fictícia — **não** teste contra peoples.gplansis.com, não tente acessar dados de outras pessoas e nunca anexe dados reais de colaboradores a um relato.
