"""Idiomas da interface — pt-BR, en-US e es.

**A chave do catálogo é o próprio texto em português.** Não há `btn.save` nem
`msg.erro_42`. A razão é operacional: numa interface renderizada no servidor,
chave inventada que não existe no catálogo vira string vazia ou o próprio
identificador na tela. Com chave natural, tradução faltando cai no português —
que é texto legítimo, escrito por quem conhece o domínio, e não um defeito
visível para quem opera.

Isso também torna a tradução incremental: acrescentar um idioma é acrescentar
uma coluna, e um template novo já funciona antes de qualquer tradução existir.

O preço é conhecido e aceito: a mesma palavra em português pode precisar de
traduções diferentes conforme o contexto. Quando isso acontece, a chave carrega
o contexto entre colchetes no fim — `"Nível [do cargo]"` — e `traduzir` remove
o sufixo antes de exibir, de modo que a falta de tradução ainda caia num
português correto.

O que **não** passa por aqui, e por quê:

- **Nome de departamento, cargo e vertical** — é dado do cliente. Departamento
  tem camada própria em `estrutura.rotulo(dep, idioma)`, alimentada pela
  apresentação institucional; cargo e vertical saem como estão.
- **Cabeçalho do CSV exportado** (`nome`, `cargo`, `responde_a`…) — é contrato
  de dado: quem consome faz parse por esses nomes.
- **Título de coluna da planilha** (`Colaborador`, `Gestor Direto`…) —
  `importador.ler_planilha` valida o cabeçalho por eles; traduzir recusaria a
  própria planilha-modelo. O texto de ajuda da planilha, esse sim, traduz.
- **Rótulo de nível configurado pelo administrador** — o campo de edição mostra
  o valor gravado, que é a fonte da verdade. A exibição passa por `t()`, então o
  padrão aparece traduzido e um rótulo customizado aparece como foi escrito.
- **Ação e motivo do ledger** — o histórico grava sempre em pt-BR, senão o mesmo
  evento teria texto diferente conforme a língua de quem o criou. A tradução
  acontece na exibição (`_auditoria.html`).
- **Semente de demonstração e linha de comando** — não são interface.

Módulos sem acesso ao request (`importador`, `dominio`, `pdf`) guardam o idioma
vigente em `IDIOMA` de módulo; `main.alinhar_idioma()` o ajusta antes de usar.
"""
from __future__ import annotations

import re

PADRAO = "pt-BR"

# codigo -> (nome no proprio idioma, bandeira em texto para o seletor)
IDIOMAS = {
    "pt-BR": "Português",
    "en-US": "English",
    "es": "Español",
}

# Idiomas que o catalogo de fato preenche (pt-BR e a propria chave).
TRADUZIDOS = ("en-US", "es")

_CONTEXTO = re.compile(r"\s*\[[^\]]*\]$")


def sem_contexto(chave: str) -> str:
    """`"Nível [do cargo]"` -> `"Nível"`. O sufixo desambigua, não aparece."""
    return _CONTEXTO.sub("", chave)


def valido(codigo: str | None) -> str:
    return codigo if codigo in IDIOMAS else PADRAO


# ---------------------------------------------------------------------------
# CATÁLOGO
# ---------------------------------------------------------------------------
# chave (pt-BR, exata como está no template) -> {idioma: tradução}
CATALOGO: dict[str, dict[str, str]] = {
    "Painel RH": {"en-US": "HR Dashboard", "es": "Panel RH"},
    "Painel de RH / Departamento Pessoal": {
        "en-US": "HR / Personnel dashboard", "es": "Panel de RH / Departamento Personal"},
    "Indicadores do seu recorte": {
        "en-US": "Indicators for your scope", "es": "Indicadores de su recorte"},
    "Baixa um Excel com todas as tabelas e o painel": {
        "en-US": "Downloads an Excel with all tables and the dashboard",
        "es": "Descarga un Excel con todas las tablas y el panel"},
    "Exportar Excel": {"en-US": "Export Excel", "es": "Exportar Excel"},
    "N5 dos colaboradores": {"en-US": "Employees' N5", "es": "N5 de los colaboradores"},
    "{ok} de {total} preenchidos · {p} pendentes (o N5 vive no cadastro de CC).": {
        "en-US": "{ok} of {total} filled · {p} pending (N5 lives in the cost-center registry).",
        "es": "{ok} de {total} rellenados · {p} pendientes (el N5 vive en el catálogo de CC)."},
    "Preencher o N5 de {p} colaborador(es) a partir do centro de custo?": {
        "en-US": "Fill the N5 of {p} employee(s) from the cost center?",
        "es": "¿Rellenar el N5 de {p} colaborador(es) desde el centro de costo?"},
    "Vincular N5 ao centro de custo": {
        "en-US": "Link N5 to cost center", "es": "Vincular N5 al centro de costo"},
    "Colaboradores": {"en-US": "Employees", "es": "Colaboradores"},
    "Gestores": {"en-US": "Managers", "es": "Gestores"},
    "Departamentos": {"en-US": "Departments", "es": "Departamentos"},
    "Verticais": {"en-US": "Verticals", "es": "Verticales"},
    "Tempo médio de casa": {"en-US": "Average tenure", "es": "Antigüedad media"},
    "anos": {"en-US": "years", "es": "años"},
    "Span médio": {"en-US": "Average span", "es": "Span medio"},
    "% CLT": {"en-US": "% permanent (CLT)", "es": "% CLT"},
    "% Terceirizados": {"en-US": "% outsourced", "es": "% Tercerizados"},
    "Total de pessoas no recorte visível (cada nó-pessoa do organograma).": {
        "en-US": "Total people in the visible scope (each person-node of the org chart).",
        "es": "Total de personas en el recorte visible (cada nodo-persona del organigrama)."},
    "Quantos têm pelo menos um liderado direto (aparecem como pai de alguém).": {
        "en-US": "How many have at least one direct report (they appear as someone's parent).",
        "es": "Cuántos tienen al menos un subordinado directo (aparecen como padre de alguien)."},
    "Áreas distintas no recorte (o campo Área de cada pessoa).": {
        "en-US": "Distinct areas in the scope (each person's Area field).",
        "es": "Áreas distintas en el recorte (el campo Área de cada persona)."},
    "Verticais de negócio distintas no recorte (o campo Vertical / N2).": {
        "en-US": "Distinct business verticals in the scope (the Vertical / N2 field).",
        "es": "Verticales de negocio distintas en el recorte (el campo Vertical / N2)."},
    "Média dos anos desde a admissão, só de quem tem data de admissão. Dias corridos ÷ 365,25.": {
        "en-US": "Average years since hire, only for those with a hire date. Calendar days ÷ 365.25.",
        "es": "Media de años desde el ingreso, solo de quien tiene fecha. Días corridos ÷ 365,25."},
    "Média de liderados por gestor: (colaboradores − 1) ÷ gestores.": {
        "en-US": "Average reports per manager: (employees − 1) ÷ managers.",
        "es": "Media de subordinados por gestor: (colaboradores − 1) ÷ gestores."},
    "Percentual de vínculo CLT sobre o total do recorte.": {
        "en-US": "Percentage of permanent (CLT) contracts over the scope total.",
        "es": "Porcentaje de vínculo CLT sobre el total del recorte."},
    "Percentual de PJ, estágio, RPA e consultoria somados, sobre o total.": {
        "en-US": "Percentage of PJ, internship, RPA and consultancy combined, over the total.",
        "es": "Porcentaje de PJ, pasantía, RPA y consultoría sumados, sobre el total."},
    "Tipo de vínculo": {"en-US": "Contract type", "es": "Tipo de vínculo"},
    "terceirizados": {"en-US": "outsourced", "es": "tercerizados"},
    "Tempo de casa": {"en-US": "Tenure", "es": "Antigüedad"},
    "Pirâmide por nível": {"en-US": "Level pyramid", "es": "Pirámide por nivel"},
    "Admissões por ano": {"en-US": "Hires per year", "es": "Contrataciones por año"},
    "Headcount por departamento": {
        "en-US": "Headcount by department", "es": "Headcount por departamento"},
    "top 12": {"en-US": "top 12", "es": "top 12"},
    "Headcount por vertical": {
        "en-US": "Headcount by vertical", "es": "Headcount por vertical"},
    "Últimas contratações": {"en-US": "Latest hires", "es": "Últimas contrataciones"},
    "no mês": {"en-US": "this month", "es": "en el mes"},
    "novo": {"en-US": "new", "es": "nuevo"},
    "Sem admissões registradas.": {
        "en-US": "No hires recorded.", "es": "Sin contrataciones registradas."},
    "Distribuição por vínculo": {
        "en-US": "Breakdown by contract type", "es": "Distribución por vínculo"},
    "Curva de crescimento": {
        "en-US": "Growth curve", "es": "Curva de crecimiento"},
    "contratações acumuladas": {
        "en-US": "cumulative hires", "es": "contrataciones acumuladas"},
    "no ano": {"en-US": "in the year", "es": "en el año"},
    "acumulado": {"en-US": "cumulative", "es": "acumulado"},
    "hoje": {"en-US": "today", "es": "hoy"},
    "Sem datas de admissão para traçar a curva.": {
        "en-US": "No hire dates to plot the curve.",
        "es": "Sin fechas de ingreso para trazar la curva."},
    "Desligamentos (RH)": {"en-US": "Terminations (HR)", "es": "Bajas (RR. HH.)"},
    "Ninguém desligado no recorte.": {
        "en-US": "No one terminated in this scope.",
        "es": "Nadie dado de baja en el recorte."},
    "colaborador(es)": {"en-US": "employee(s)", "es": "colaborador(es)"},
    "inativo": {"en-US": "inactive", "es": "inactivo"},
    "Ninguém nesta fatia.": {
        "en-US": "No one in this slice.", "es": "Nadie en este segmento."},
    "Admissões em": {"en-US": "Hires in", "es": "Ingresos en"},
    "Desligamentos": {"en-US": "Terminations", "es": "Bajas"},
    "Contratações do mês": {
        "en-US": "Hires this month", "es": "Contrataciones del mes"},
    "Usuários inativos": {"en-US": "Inactive users", "es": "Usuarios inactivos"},
    "inativos": {"en-US": "inactive", "es": "inactivos"},
    "nunca acessaram": {"en-US": "never signed in", "es": "nunca accedieron"},
    "nunca acessou": {"en-US": "never signed in", "es": "nunca accedió"},
    "há {d} dias": {"en-US": "{d} days ago", "es": "hace {d} días"},
    "Todo mundo com acesso recente.": {
        "en-US": "Everyone signed in recently.", "es": "Todos con acceso reciente."},
    "N5 vinculado ao CC: {n} colaborador(es) atualizado(s), {ok} já corretos, {sc} sem CC resolvível.": {
        "en-US": "N5 linked to CC: {n} employee(s) updated, {ok} already correct, {sc} without a resolvable CC.",
        "es": "N5 vinculado al CC: {n} colaborador(es) actualizado(s), {ok} ya correctos, {sc} sin CC resoluble."},
    "Vê o organograma inteiro (leitura), mesmo com escopo de edição restrito": {
        "en-US": "Sees the whole org chart (read-only), even with a restricted edit scope",
        "es": "Ve el organigrama entero (lectura), aunque el alcance de edición sea restringido",
    },
    "Acessos": {
        "en-US": "Access log",
        "es": "Accesos",
    },
    "Monitoramento de acessos": {
        "en-US": "Access monitoring",
        "es": "Monitoreo de accesos",
    },
    "Registro de entrada e saída de cada usuário — quem entrou, quem saiu e quando. Trilha separada da auditoria de alterações.": {
        "en-US": "Sign-in and sign-out record for each user — who came in, who left and when. A trail separate from the change audit.",
        "es": "Registro de entrada y salida de cada usuario — quién entró, quién salió y cuándo. Un rastro separado de la auditoría de cambios.",
    },
    "Usuário": {
        "en-US": "User",
        "es": "Usuario",
    },
    "Evento": {
        "en-US": "Event",
        "es": "Evento",
    },
    "Nenhum acesso registrado ainda.": {
        "en-US": "No access recorded yet.",
        "es": "Ningún acceso registrado todavía.",
    },
    "Entrada": {
        "en-US": "Signed in",
        "es": "Entrada",
    },
    "Saída": {
        "en-US": "Signed out",
        "es": "Salida",
    },
    "Quem está ativo agora": {
        "en-US": "Who's active now",
        "es": "Quién está activo ahora",
    },
    "Ativos agora": {
        "en-US": "Active now",
        "es": "Activos ahora",
    },
    "Usuários ativos": {
        "en-US": "Active users",
        "es": "Usuarios activos",
    },
    "ativo agora": {
        "en-US": "active now",
        "es": "activo ahora",
    },
    "você": {
        "en-US": "you",
        "es": "usted",
    },
    "Ninguém por aqui agora.": {
        "en-US": "Nobody here right now.",
        "es": "Nadie por aquí ahora.",
    },
    "Agente Organograma": {
        "en-US": "Org chart agent",
        "es": "Agente Organigrama",
    },
    "Descreva o time em uma frase. A MarIA devolve a estrutura proposta — cargos, níveis e quantidades — e nada é criado até você ler a lista inteira e aprovar.": {
        "en-US": "Describe the team in one sentence. MarIA returns the proposed structure — job titles, levels and quantities — and nothing is created until you read the whole list and approve.",
        "es": "Describa el equipo en una frase. MarIA devuelve la estructura propuesta — cargos, niveles y cantidades — y nada se crea hasta que usted lea la lista entera y apruebe.",
    },
    "Pedido": {
        "en-US": "Request",
        "es": "Solicitud",
    },
    "Ex.: Crie um novo time de Growth Marketing com 1 Diretor, 2 Coordenadores e 4 Analistas focado na América Latina": {
        "en-US": "E.g.: Create a new Growth Marketing team with 1 Director, 2 Coordinators and 4 Analysts focused on Latin America",
        "es": "Ej.: Cree un nuevo equipo de Growth Marketing con 1 Director, 2 Coordinadores y 4 Analistas enfocado en América Latina",
    },
    "Propor estrutura": {
        "en-US": "Propose structure",
        "es": "Proponer estructura",
    },
    "Estrutura proposta": {
        "en-US": "Proposed structure",
        "es": "Estructura propuesta",
    },
    "{n} unidade(s)": {
        "en-US": "{n} unit(s)",
        "es": "{n} unidad(es)",
    },
    "sob {pai}": {
        "en-US": "under {pai}",
        "es": "bajo {pai}",
    },
    "a raiz": {
        "en-US": "the root",
        "es": "la raíz",
    },
    "Departamento: {dep}": {
        "en-US": "Department: {dep}",
        "es": "Departamento: {dep}",
    },
    "Quantidade": {
        "en-US": "Quantity",
        "es": "Cantidad",
    },
    "Criar {n} unidade(s) sob {pai}? As pessoas entram como “A definir” e podem ser nomeadas depois. Desfazer reverte tudo de uma vez.": {
        "en-US": "Create {n} unit(s) under {pai}? People come in as “To be defined” and can be named later. Undo reverts everything at once.",
        "es": "¿Crear {n} unidad(es) bajo {pai}? Las personas entran como “Por definir” y pueden nombrarse después. Deshacer revierte todo de una vez.",
    },
    "Aprovar e criar": {
        "en-US": "Approve and create",
        "es": "Aprobar y crear",
    },
    "A definir": {
        "en-US": "To be defined",
        "es": "Por definir",
    },
    "Proposta não encontrada ou já aplicada.": {
        "en-US": "Proposal not found or already applied.",
        "es": "Propuesta no encontrada o ya aplicada.",
    },
    "{n} unidade(s) criadas sob {pai}. Desfazer reverte a criação inteira.": {
        "en-US": "{n} unit(s) created under {pai}. Undo reverts the whole creation.",
        "es": "{n} unidad(es) creadas bajo {pai}. Deshacer revierte la creación entera.",
    },
    "Proposta descartada.": {
        "en-US": "Proposal discarded.",
        "es": "Propuesta descartada.",
    },
    "estrutura criada pelo agente Organograma": {
        "en-US": "structure created by the org chart agent",
        "es": "estructura creada por el agente Organigrama",
    },
    "Vínculo": {
        "en-US": "Employment type",
        "es": "Vínculo",
    },
    "CLT": {
        "en-US": "Employee (CLT)",
        "es": "Empleado (CLT)",
    },
    "Prestador (PJ)": {
        "en-US": "Contractor (PJ)",
        "es": "Prestador (PJ)",
    },
    "Consultoria externa": {
        "en-US": "External consultancy",
        "es": "Consultoría externa",
    },
    "*USE COM MODERAÇÃO, CADA SOLICITAÇÃO GERA CUSTOS": {
        "en-US": "*USE SPARINGLY — EACH REQUEST COSTS MONEY",
        "es": "*USE CON MODERACIÓN, CADA SOLICITUD GENERA COSTOS",
    },
    "Fechar": {
        "en-US": "Close",
        "es": "Cerrar",
    },
    "Olá! Posso ler e analisar o organograma no seu recorte — hierarquia, centros de custo, cargos e divergências. Pergunte ou escolha:": {
        "en-US": "Hi! I can read and analyse the org chart within your scope — hierarchy, cost centers, job titles and discrepancies. Ask or pick:",
        "es": "¡Hola! Puedo leer y analizar el organigrama en su recorte — jerarquía, centros de costo, cargos y divergencias. Pregunte o elija:",
    },
    "Quais departamentos têm gestor sem subordinados diretos?": {
        "en-US": "Which departments have a manager with no direct reports?",
        "es": "¿Qué departamentos tienen gestor sin subordinados directos?",
    },
    "Onde a estrutura declarada difere do cadastro de centros de custo?": {
        "en-US": "Where does the declared structure differ from the cost center registry?",
        "es": "¿Dónde difiere la estructura declarada del registro de centros de costo?",
    },
    "Quais níveis estão concentrados demais numa só vertical?": {
        "en-US": "Which levels are too concentrated in a single vertical?",
        "es": "¿Qué niveles están demasiado concentrados en una sola vertical?",
    },
    "Pergunte à MarIA…": {
        "en-US": "Ask MarIA…",
        "es": "Pregunte a MarIA…",
    },
    "Enviar": {
        "en-US": "Send",
        "es": "Enviar",
    },
    "Parar": {
        "en-US": "Stop",
        "es": "Detener",
    },
    "A MarIA é somente leitura — informa e sugere; não altera dados.": {
        "en-US": "MarIA is read-only — she informs and suggests; she does not change data.",
        "es": "MarIA es solo lectura — informa y sugiere; no altera datos.",
    },
    "Limpar conversa": {
        "en-US": "Clear conversation",
        "es": "Limpiar conversación",
    },
    "Sem ANTHROPIC_API_KEY: a conversa fica indisponível.": {
        "en-US": "No ANTHROPIC_API_KEY: the conversation is unavailable.",
        "es": "Sin ANTHROPIC_API_KEY: la conversación queda no disponible.",
    },
    "Aviso por e-mail: ativo via {host}:{porta} ({modo}), remetente {de}.": {
        "en-US": "E-mail notice: active via {host}:{porta} ({modo}), sender {de}.",
        "es": "Aviso por correo: activo vía {host}:{porta} ({modo}), remitente {de}.",
    },
    "Enviar teste": {
        "en-US": "Send test",
        "es": "Enviar prueba",
    },
    "Aviso por e-mail: inativo. Defina SMTP_HOST e SMTP_DE no ambiente — o resto já está pronto. Até lá, esta fila é a notificação.": {
        "en-US": "E-mail notice: inactive. Set SMTP_HOST and SMTP_DE in the environment — everything else is ready. Until then, this queue is the notification.",
        "es": "Aviso por correo: inactivo. Defina SMTP_HOST y SMTP_DE en el entorno — el resto ya está listo. Hasta entonces, esta cola es la notificación.",
    },
    "[GPlanSiS|Peoples] Teste de envio": {
        "en-US": "[GPlanSiS|Peoples] Send test",
        "es": "[GPlanSiS|Peoples] Prueba de envío",
    },
    "Se você recebeu esta mensagem, o provisionamento de TI consegue avisar por e-mail.": {
        "en-US": "If you received this message, IT provisioning can notify by e-mail.",
        "es": "Si usted recibió este mensaje, el aprovisionamiento de TI puede avisar por correo.",
    },
    "E-mail de teste enviado: {detalhe}": {
        "en-US": "Test e-mail sent: {detalhe}",
        "es": "Correo de prueba enviado: {detalhe}",
    },
    "Envio recusado: {detalhe}": {
        "en-US": "Send refused: {detalhe}",
        "es": "Envío rechazado: {detalhe}",
    },
    "[GPlanSiS|Peoples] Provisionamento: {pessoa} — {de} → {para}": {
        "en-US": "[GPlanSiS|Peoples] Provisioning: {pessoa} — {de} → {para}",
        "es": "[GPlanSiS|Peoples] Aprovisionamiento: {pessoa} — {de} → {para}",
    },
    "Mudança de departamento registrada no organograma.": {
        "en-US": "Department change recorded in the org chart.",
        "es": "Cambio de departamento registrado en el organigrama.",
    },
    "REVOGAR:": {
        "en-US": "REVOKE:",
        "es": "REVOCAR:",
    },
    "CONCEDER:": {
        "en-US": "GRANT:",
        "es": "CONCEDER:",
    },
    "Pedido {id}, aberto em {quando}.": {
        "en-US": "Request {id}, opened on {quando}.",
        "es": "Solicitud {id}, abierta el {quando}.",
    },
    "aviso de provisionamento por e-mail": {
        "en-US": "provisioning notice by e-mail",
        "es": "aviso de aprovisionamiento por correo",
    },
    "MarIA · assistente de estrutura": {
        "en-US": "MarIA · structure assistant",
        "es": "MarIA · asistente de estructura",
    },
    "MarIA Chat": {
        "en-US": "MarIA Chat",
        "es": "MarIA Chat",
    },
    "Converse com a assistente": {
        "en-US": "Talk to the assistant",
        "es": "Converse con la asistente",
    },
    "Abrir módulo MarIA": {
        "en-US": "Open MarIA module",
        "es": "Abrir módulo MarIA",
    },
    "Análise, capacidades, custos e histórico": {
        "en-US": "Analysis, capabilities, costs and history",
        "es": "Análisis, capacidades, costos e historial",
    },
    "Módulo MarIA": {
        "en-US": "MarIA module",
        "es": "Módulo MarIA",
    },
    "Assistente de estrutura organizacional. Lê o organograma no recorte de quem pergunta, descreve, analisa e propõe — e para aí.": {
        "en-US": "Organizational structure assistant. Reads the org chart within the asker's scope, describes, analyses and proposes — and stops there.",
        "es": "Asistente de estructura organizacional. Lee el organigrama en el recorte de quien pregunta, describe, analiza y propone — y ahí se detiene.",
    },
    "Ativa · modelo {modelo}": {
        "en-US": "Active · model {modelo}",
        "es": "Activa · modelo {modelo}",
    },
    "Sem ANTHROPIC_API_KEY": {
        "en-US": "No ANTHROPIC_API_KEY",
        "es": "Sin ANTHROPIC_API_KEY",
    },
    "Recorte: {escopo}": {
        "en-US": "Scope: {escopo}",
        "es": "Recorte: {escopo}",
    },
    "Defina <code>ANTHROPIC_API_KEY</code> no ambiente para conversar. O restante desta tela — capacidades, limites, custos e histórico — continua valendo.": {
        "en-US": "Set <code>ANTHROPIC_API_KEY</code> in the environment to chat. The rest of this screen — capabilities, limits, costs and history — still applies.",
        "es": "Defina <code>ANTHROPIC_API_KEY</code> en el entorno para conversar. El resto de esta pantalla — capacidades, límites, costos e historial — sigue valiendo.",
    },
    "Perguntar": {
        "en-US": "Ask",
        "es": "Preguntar",
    },
    "A MarIA responde sobre o que você pode ver. Se algo está fora do seu escopo, ela diz que está fora — não supõe.": {
        "en-US": "MarIA answers about what you can see. If something is outside your scope, she says so — she does not assume.",
        "es": "MarIA responde sobre lo que usted puede ver. Si algo está fuera de su alcance, lo dice — no supone.",
    },
    "Capacidade": {
        "en-US": "Capability",
        "es": "Capacidad",
    },
    "Modelo": {
        "en-US": "Model",
        "es": "Modelo",
    },
    "Pergunta": {
        "en-US": "Question",
        "es": "Pregunta",
    },
    "Ex.: quais departamentos têm gestor sem subordinados diretos?": {
        "en-US": "E.g.: which departments have a manager with no direct reports?",
        "es": "Ej.: ¿qué departamentos tienen gestor sin subordinados directos?",
    },
    "MarIA está pensando…": {
        "en-US": "MarIA is thinking…",
        "es": "MarIA está pensando…",
    },
    "Isto é um rascunho. Nada foi aplicado ao organograma — aplicar exige ação humana, campo a campo, no painel da unidade.": {
        "en-US": "This is a draft. Nothing was applied to the org chart — applying takes human action, field by field, in the unit panel.",
        "es": "Esto es un borrador. Nada se aplicó al organigrama — aplicar exige acción humana, campo por campo, en el panel de la unidad.",
    },
    "As sete capacidades — cada uma com seu limite": {
        "en-US": "The seven capabilities — each with its limit",
        "es": "Las siete capacidades — cada una con su límite",
    },
    "O que define a MarIA não é o que ela sabe fazer: é o que ela não pode fazer sem alguém autorizar. As duas últimas linhas são recusadas no código, não desencorajadas no prompt.": {
        "en-US": "What defines MarIA is not what she can do: it is what she cannot do without someone authorizing it. The last two rows are refused in code, not discouraged in the prompt.",
        "es": "Lo que define a MarIA no es lo que sabe hacer: es lo que no puede hacer sin que alguien lo autorice. Las dos últimas filas se rechazan en el código, no se desalientan en el prompt.",
    },
    "Verbo": {
        "en-US": "Verb",
        "es": "Verbo",
    },
    "Efeito": {
        "en-US": "Effect",
        "es": "Efecto",
    },
    "Autoridade exigida": {
        "en-US": "Authority required",
        "es": "Autoridad exigida",
    },
    "Nesta onda": {
        "en-US": "In this wave",
        "es": "En esta ola",
    },
    "disponível": {
        "en-US": "available",
        "es": "disponible",
    },
    "recusada": {
        "en-US": "refused",
        "es": "rechazada",
    },
    "Ler": {
        "en-US": "Read",
        "es": "Leer",
    },
    "Descrever": {
        "en-US": "Describe",
        "es": "Describir",
    },
    "Relatar": {
        "en-US": "Report",
        "es": "Reportar",
    },
    "Analisar baseline": {
        "en-US": "Analyse baseline",
        "es": "Analizar baseline",
    },
    "Planejar": {
        "en-US": "Plan",
        "es": "Planificar",
    },
    "Executar": {
        "en-US": "Execute",
        "es": "Ejecutar",
    },
    "Agir sozinha": {
        "en-US": "Act autonomously",
        "es": "Actuar sola",
    },
    "consulta": {
        "en-US": "query",
        "es": "consulta",
    },
    "explica estado": {
        "en-US": "explains state",
        "es": "explica estado",
    },
    "gera PDF": {
        "en-US": "generates PDF",
        "es": "genera PDF",
    },
    "compara declarado × cadastrado": {
        "en-US": "compares declared × registered",
        "es": "compara declarado × registrado",
    },
    "propõe cenário": {
        "en-US": "proposes a scenario",
        "es": "propone escenario",
    },
    "dispara ação de sistema": {
        "en-US": "triggers a system action",
        "es": "dispara acción de sistema",
    },
    "encadeia ações": {
        "en-US": "chains actions",
        "es": "encadena acciones",
    },
    "nenhum": {
        "en-US": "none",
        "es": "ninguno",
    },
    "artefato": {
        "en-US": "artifact",
        "es": "artefacto",
    },
    "rascunho, nunca aplicado": {
        "en-US": "draft, never applied",
        "es": "borrador, nunca aplicado",
    },
    "mutação": {
        "en-US": "mutation",
        "es": "mutación",
    },
    "RBAC de leitura de quem pergunta": {
        "en-US": "Reader RBAC of whoever asks",
        "es": "RBAC de lectura de quien pregunta",
    },
    "RBAC + marca d'água de origem": {
        "en-US": "RBAC + origin watermark",
        "es": "RBAC + marca de agua de origen",
    },
    "RBAC + gate de qualidade de dado": {
        "en-US": "RBAC + data quality gate",
        "es": "RBAC + control de calidad de dato",
    },
    "RBAC + versão do plano": {
        "en-US": "RBAC + plan version",
        "es": "RBAC + versión del plan",
    },
    "aprovação humana explícita, por ação": {
        "en-US": "explicit human approval, per action",
        "es": "aprobación humana explícita, por acción",
    },
    "fora de escopo desta onda": {
        "en-US": "out of scope for this wave",
        "es": "fuera de alcance de esta ola",
    },
    "Custos": {
        "en-US": "Costs",
        "es": "Costos",
    },
    "Somado do histórico, não estimado. Preço por milhão de tokens da tabela do modelo escolhido.": {
        "en-US": "Summed from history, not estimated. Price per million tokens from the chosen model's table.",
        "es": "Sumado del historial, no estimado. Precio por millón de tokens de la tabla del modelo elegido.",
    },
    "assistências": {
        "en-US": "assistances",
        "es": "asistencias",
    },
    "tokens de entrada": {
        "en-US": "input tokens",
        "es": "tokens de entrada",
    },
    "tokens de saída": {
        "en-US": "output tokens",
        "es": "tokens de salida",
    },
    "custo (USD)": {
        "en-US": "cost (USD)",
        "es": "costo (USD)",
    },
    "custo (BRL)": {
        "en-US": "cost (BRL)",
        "es": "costo (BRL)",
    },
    "Modelo padrão do sistema": {
        "en-US": "System default model",
        "es": "Modelo predeterminado del sistema",
    },
    "Sobrepõe <code>MARIA_MODEL</code> do ambiente. A chave da API continua vindo só do ambiente — credencial em estado gravado vai junto no backup.": {
        "en-US": "Overrides <code>MARIA_MODEL</code> from the environment. The API key still comes only from the environment — a credential in saved state travels with the backup.",
        "es": "Sobrescribe <code>MARIA_MODEL</code> del entorno. La clave de la API sigue viniendo solo del entorno — una credencial en estado guardado viaja con el respaldo.",
    },
    "Salvar modelo": {
        "en-US": "Save model",
        "es": "Guardar modelo",
    },
    "Modelo salvo: {modelo}": {
        "en-US": "Model saved: {modelo}",
        "es": "Modelo guardado: {modelo}",
    },
    "Histórico de assistências": {
        "en-US": "Assistance history",
        "es": "Historial de asistencias",
    },
    "Toda resposta fica gravada com quem perguntou, em que recorte e quanto custou. Sem o recorte não dá para auditar depois se a resposta era compatível com o que a pessoa podia ver.": {
        "en-US": "Every answer is stored with who asked, in which scope and how much it cost. Without the scope there is no way to audit later whether the answer matched what that person could see.",
        "es": "Toda respuesta queda grabada con quién preguntó, en qué recorte y cuánto costó. Sin el recorte no hay cómo auditar después si la respuesta era compatible con lo que esa persona podía ver.",
    },
    "Nenhuma assistência registrada ainda.": {
        "en-US": "No assistance recorded yet.",
        "es": "Ninguna asistencia registrada aún.",
    },
    "organograma inteiro": {
        "en-US": "entire org chart",
        "es": "organigrama entero",
    },
    "nenhum": {
        "en-US": "none",
        "es": "ninguno",
    },
    "assistência da MarIA": {
        "en-US": "MarIA assistance",
        "es": "asistencia de MarIA",
    },
    "modelo da MarIA": {
        "en-US": "MarIA model",
        "es": "modelo de MarIA",
    },
    "Histórico das respostas: quem perguntou, em que recorte, quanto custou.": {
        "en-US": "History of answers: who asked, in which scope, how much it cost.",
        "es": "Historial de respuestas: quién preguntó, en qué recorte, cuánto costó.",
    },
    "Reconhecimentos e feedback": {
        "en-US": "Recognition and feedback",
        "es": "Reconocimientos y feedback",
    },
    "Reconhecimentos": {
        "en-US": "Recognition",
        "es": "Reconocimientos",
    },
    "Feedback": {
        "en-US": "Feedback",
        "es": "Feedback",
    },
    "Reconhecimento": {
        "en-US": "Recognition",
        "es": "Reconocimiento",
    },
    "Valor reconhecido": {
        "en-US": "Value recognized",
        "es": "Valor reconocido",
    },
    "— nenhum —": {
        "en-US": "— none —",
        "es": "— ninguno —",
    },
    "Mensagem": {
        "en-US": "Message",
        "es": "Mensaje",
    },
    "O que essa pessoa fez, e que diferença fez.": {
        "en-US": "What this person did, and what difference it made.",
        "es": "Qué hizo esta persona, y qué diferencia hizo.",
    },
    "Publicar": {
        "en-US": "Publish",
        "es": "Publicar",
    },
    "Publicação assinada e visível para todos. Você pode apagar o que escreveu; quem recebeu pode tirar do próprio card.": {
        "en-US": "Signed and visible to everyone. You can delete what you wrote; the recipient can remove it from their own card.",
        "es": "Publicación firmada y visible para todos. Usted puede borrar lo que escribió; quien lo recibió puede quitarlo de su propia tarjeta.",
    },
    "Vincule-se a uma pessoa da estrutura em Configurações › Permissões para publicar — o mural é assinado.": {
        "en-US": "Link yourself to someone in the structure under Settings › Permissions to publish — the wall is signed.",
        "es": "Vincúlese a una persona de la estructura en Configuración › Permisos para publicar — el muro es firmado.",
    },
    "Remover": {
        "en-US": "Remove",
        "es": "Quitar",
    },
    "Remover esta mensagem?": {
        "en-US": "Remove this message?",
        "es": "¿Quitar este mensaje?",
    },
    "Ainda não há mensagens neste card.": {
        "en-US": "No messages on this card yet.",
        "es": "Aún no hay mensajes en esta tarjeta.",
    },
    "Teamwork · trabalho em equipe": {
        "en-US": "Teamwork",
        "es": "Teamwork · trabajo en equipo",
    },
    "Respect · respeito": {
        "en-US": "Respect",
        "es": "Respect · respeto",
    },
    "Innovation · inovação": {
        "en-US": "Innovation",
        "es": "Innovation · innovación",
    },
    "Ownership · atitude de dono": {
        "en-US": "Ownership",
        "es": "Ownership · actitud de dueño",
    },
    "Unidade inexistente.": {
        "en-US": "Unit does not exist.",
        "es": "La unidad no existe.",
    },
    "Vincule-se a uma pessoa da estrutura para publicar: o mural é assinado.": {
        "en-US": "Link yourself to someone in the structure to publish: the wall is signed.",
        "es": "Vincúlese a una persona de la estructura para publicar: el muro es firmado.",
    },
    "Escreva algo antes de publicar.": {
        "en-US": "Write something before publishing.",
        "es": "Escriba algo antes de publicar.",
    },
    "Só o autor, a pessoa do card ou um administrador podem remover.": {
        "en-US": "Only the author, the person on the card or an administrator can remove it.",
        "es": "Solo el autor, la persona de la tarjeta o un administrador pueden quitarlo.",
    },
    "mensagem no mural": {
        "en-US": "message on the wall",
        "es": "mensaje en el muro",
    },
    "mensagem removida do mural": {
        "en-US": "message removed from the wall",
        "es": "mensaje quitado del muro",
    },
    "Provisionamento de TI": {
        "en-US": "IT provisioning",
        "es": "Aprovisionamiento de TI",
    },
    "Quando alguém muda de departamento, o acesso de software muda junto. O organograma já sabe da mudança — aqui ela vira pedido, item a item, em vez de virar um chamado escrito à mão.": {
        "en-US": "When someone changes department, their software access changes with them. The org chart already knows about the move — here it becomes a request, item by item, instead of a hand-written ticket.",
        "es": "Cuando alguien cambia de departamento, el acceso al software cambia con él. El organigrama ya sabe del cambio — aquí se convierte en una solicitud, ítem por ítem, en vez de un ticket escrito a mano.",
    },
    "Destinatários (equipe de TI no organograma): {emails}": {
        "en-US": "Recipients (IT team in the org chart): {emails}",
        "es": "Destinatarios (equipo de TI en el organigrama): {emails}",
    },
    "Ninguém no organograma está marcado como TI: os pedidos ficam nesta fila e não têm a quem ser endereçados.": {
        "en-US": "Nobody in the org chart is marked as IT: requests stay in this queue with no one to address them to.",
        "es": "Nadie en el organigrama está marcado como TI: las solicitudes quedan en esta cola sin destinatario.",
    },
    "Pessoa": {
        "en-US": "Person",
        "es": "Persona",
    },
    "Mudança": {
        "en-US": "Change",
        "es": "Cambio",
    },
    "Revogar": {
        "en-US": "Revoke",
        "es": "Revocar",
    },
    "Conceder": {
        "en-US": "Grant",
        "es": "Conceder",
    },
    "Aberto em": {
        "en-US": "Opened on",
        "es": "Abierto el",
    },
    "Concluir": {
        "en-US": "Complete",
        "es": "Completar",
    },
    "Nenhum pedido em aberto.": {
        "en-US": "No open requests.",
        "es": "Ninguna solicitud abierta.",
    },
    "{n} departamento(s) sem software mapeado.": {
        "en-US": "{n} department(s) with no software mapped.",
        "es": "{n} departamento(s) sin software mapeado.",
    },
    "Mudança para uma dessas áreas não gera pedido — e o silêncio pareceria “nada a fazer”:": {
        "en-US": "A move into one of these areas generates no request — and the silence would read as “nothing to do”:",
        "es": "Un cambio hacia una de estas áreas no genera solicitud — y el silencio parecería “nada que hacer”:",
    },
    "Software por departamento": {
        "en-US": "Software by department",
        "es": "Software por departamento",
    },
    "O que cada área usa. É daqui que sai a diferença entre a área antiga e a nova. Um software em ambas as pontas não entra em nenhuma das listas — TI não deve tirar e devolver o mesmo acesso no mesmo pedido.": {
        "en-US": "What each area uses. This is where the difference between the old and the new area comes from. Software present on both ends enters neither list — IT should not remove and restore the same access in the same request.",
        "es": "Lo que usa cada área. De aquí sale la diferencia entre el área anterior y la nueva. Un software presente en ambos extremos no entra en ninguna lista — TI no debe quitar y devolver el mismo acceso en la misma solicitud.",
    },
    "Softwares (separados por vírgula)": {
        "en-US": "Software (comma-separated)",
        "es": "Software (separado por comas)",
    },
    "novo departamento": {
        "en-US": "new department",
        "es": "nuevo departamento",
    },
    "ex.: ERP · Compras, Portal do Fornecedor": {
        "en-US": "e.g.: ERP · Purchasing, Supplier Portal",
        "es": "ej.: ERP · Compras, Portal del Proveedor",
    },
    "<b>Microsoft 365</b>, <b>Teams</b> e <b>GPlanSiS|Peoples</b> são base comum: não entram nem saem de pedido nenhum.": {
        "en-US": "<b>Microsoft 365</b>, <b>Teams</b> and <b>GPlanSiS|Peoples</b> are common baseline: they never enter or leave any request.",
        "es": "<b>Microsoft 365</b>, <b>Teams</b> y <b>GPlanSiS|Peoples</b> son base común: no entran ni salen de ninguna solicitud.",
    },
    "Salvar catálogo de software": {
        "en-US": "Save software catalog",
        "es": "Guardar catálogo de software",
    },
    "Concluídos": {
        "en-US": "Completed",
        "es": "Completados",
    },
    "Histórico dos últimos pedidos encerrados.": {
        "en-US": "History of the most recently closed requests.",
        "es": "Historial de las últimas solicitudes cerradas.",
    },
    "Concluído em": {
        "en-US": "Completed on",
        "es": "Completado el",
    },
    "Por": {
        "en-US": "By",
        "es": "Por",
    },
    "Catálogo salvo com {n} departamento(s).": {
        "en-US": "Catalog saved with {n} department(s).",
        "es": "Catálogo guardado con {n} departamento(s).",
    },
    "Pedido não encontrado ou já concluído.": {
        "en-US": "Request not found or already completed.",
        "es": "Solicitud no encontrada o ya completada.",
    },
    "Pedido concluído.": {
        "en-US": "Request completed.",
        "es": "Solicitud completada.",
    },
    "provisionamento de TI aberto": {
        "en-US": "IT provisioning opened",
        "es": "aprovisionamiento de TI abierto",
    },
    "provisionamento de TI concluído": {
        "en-US": "IT provisioning completed",
        "es": "aprovisionamiento de TI completado",
    },
    "catálogo de software por departamento": {
        "en-US": "software catalog by department",
        "es": "catálogo de software por departamento",
    },
    "Auditoria/Log": {
        "en-US": "Audit / Log",
        "es": "Auditoría / Log",
    },
    "carga do seed de referência da SPEC §13": {
        "en-US": "load of the SPEC §13 reference seed",
        "es": "carga de la semilla de referencia de la SPEC §13",
    },
    "Raiz → folhas, independente da orientação do canvas.": {
        "en-US": "Root → leaves, regardless of the canvas orientation.",
        "es": "Raíz → hojas, independiente de la orientación del canvas.",
    },
    "{n} linha(s) visível(is)": {
        "en-US": "{n} visible row(s)",
        "es": "{n} fila(s) visible(s)",
    },
    "Clique em uma linha para abrir a gaveta de edição.": {
        "en-US": "Click a row to open the editing panel.",
        "es": "Haga clic en una fila para abrir el panel de edición.",
    },
    "{n} combinação(ões) sem linha no cadastro:": {
        "en-US": "{n} combination(s) with no row in the registry:",
        "es": "{n} combinación(es) sin fila en el registro:",
    },
    "Sem regra que case, o cargo cai no piso <b>{nivel}</b>.": {
        "en-US": "With no matching rule, the job title falls to the floor level <b>{nivel}</b>.",
        "es": "Sin regla que coincida, el cargo cae al nivel base <b>{nivel}</b>.",
    },
    "Organograma em orientação {orientacao}": {
        "en-US": "Org chart in {orientacao} orientation",
        "es": "Organigrama en orientación {orientacao}",
    },
    "Organograma — orientação {orientacao}": {
        "en-US": "Org chart — {orientacao} orientation",
        "es": "Organigrama — orientación {orientacao}",
    },
    "invertida": {
        "en-US": "inverted",
        "es": "invertida",
    },
    "vertical": {
        "en-US": "vertical",
        "es": "vertical",
    },
    "lateral": {
        "en-US": "lateral",
        "es": "lateral",
    },
    "Ações do desenho": {
        "en-US": "Chart actions",
        "es": "Acciones del dibujo",
    },
    "Alargar ou recolher a gaveta": {
        "en-US": "Widen or shrink the drawer",
        "es": "Ensanchar o recoger el cajón",
    },
    "Capacidade": {
        "en-US": "Capability",
        "es": "Capacidad",
    },
    "Adicionar unidade na raiz": {
        "en-US": "Add unit under the root",
        "es": "Agregar unidad en la raíz",
    },
    "▸ Lateral": {
        "en-US": "▸ Lateral",
        "es": "▸ Lateral",
    },
    "Árvore indentada: a leitura desce e a profundidade anda para a direita": {
        "en-US": "Indented tree: reading goes down and depth goes to the right",
        "es": "Árbol indentado: la lectura baja y la profundidad va a la derecha",
    },
    "lateral — a árvore cresce para a direita": {
        "en-US": "lateral — the tree grows to the right",
        "es": "lateral — el árbol crece hacia la derecha",
    },
    "Organograma em árvore indentada: a raiz fica à esquerda, cada nível recua "
    "para a direita e a leitura desce na ordem lógica. A hierarquia e os níveis "
    "anunciados são os mesmos das demais orientações.": {
        "en-US": "Org chart as an indented tree: the root sits on the left, each "
                 "level steps to the right and reading goes down in logical "
                 "order. Hierarchy and announced levels are the same as in the "
                 "other orientations.",
        "es": "Organigrama en árbol indentado: la raíz queda a la izquierda, "
              "cada nivel se desplaza a la derecha y la lectura baja en orden "
              "lógico. La jerarquía y los niveles anunciados son los mismos que "
              "en las demás orientaciones.",
    },
    "Lateral — árvore indentada para a direita": {
        "en-US": "Lateral — tree indented to the right",
        "es": "Lateral — árbol indentado hacia la derecha",
    },
    "nível {n}": {
        "en-US": "level {n}",
        "es": "nivel {n}",
    },
    "{n} subordinado(s) direto(s)": {
        "en-US": "{n} direct report(s)",
        "es": "{n} subordinado(s) directo(s)",
    },
    "por {criterio}": {
        "en-US": "by {criterio}",
        "es": "por {criterio}",
    },
    "departamento": {
        "en-US": "department",
        "es": "departamento",
    },
    "carga inicial a partir de Organograma.xlsx": {
        "en-US": "initial load from Organograma.xlsx",
        "es": "carga inicial desde Organograma.xlsx",
    },
    "schema do banco aplicado": {
        "en-US": "database schema applied",
        "es": "esquema de la base aplicado",
    },
    "organograma escrito no banco": {
        "en-US": "org chart written to the database",
        "es": "organigrama escrito en la base",
    },
    "Banco de dados": {
        "en-US": "Database",
        "es": "Base de datos",
    },
    "O organograma roda em memória com persistência em JSON. O PostgreSQL é o alvo de produção: multiusuário, concorrência real e o ledger fora do disco local. Esta aba não muda o modelo — ela diz de onde cada coluna vem e gera a carga.": {
        "en-US": "The org chart runs in memory with JSON persistence. PostgreSQL is the production target: multi-user, real concurrency and the ledger off the local disk. This tab does not change the model — it tells where each column comes from and generates the load.",
        "es": "El organigrama funciona en memoria con persistencia en JSON. PostgreSQL es el destino de producción: multiusuario, concurrencia real y el registro de auditoría fuera del disco local. Esta pestaña no cambia el modelo — indica de dónde viene cada columna y genera la carga.",
    },
    "Conexão (ORG_DATABASE_URL)": {
        "en-US": "Connection (ORG_DATABASE_URL)",
        "es": "Conexión (ORG_DATABASE_URL)",
    },
    "não configurada": {
        "en-US": "not configured",
        "es": "no configurada",
    },
    "Driver psycopg": {
        "en-US": "psycopg driver",
        "es": "Driver psycopg",
    },
    "instalado": {
        "en-US": "installed",
        "es": "instalado",
    },
    "ausente": {
        "en-US": "missing",
        "es": "ausente",
    },
    "A senha é mascarada de propósito. A conexão vem do ambiente, não do estado gravado — credencial em arquivo de dados vai junto no backup.": {
        "en-US": "The password is masked on purpose. The connection comes from the environment, not from saved state — a credential in a data file travels with the backup.",
        "es": "La contraseña se enmascara a propósito. La conexión viene del entorno, no del estado guardado — una credencial en un archivo de datos viaja con el respaldo.",
    },
    "Testar conexão": {
        "en-US": "Test connection",
        "es": "Probar conexión",
    },
    "Exige driver instalado e ORG_DATABASE_URL definida.": {
        "en-US": "Requires the driver installed and ORG_DATABASE_URL set.",
        "es": "Requiere el driver instalado y ORG_DATABASE_URL definida.",
    },
    "Baixar schema (DDL)": {
        "en-US": "Download schema (DDL)",
        "es": "Descargar esquema (DDL)",
    },
    "Baixar carga do estado atual": {
        "en-US": "Download load from current state",
        "es": "Descargar carga del estado actual",
    },
    "De onde vem cada tabela": {
        "en-US": "Where each table comes from",
        "es": "De dónde viene cada tabla",
    },
    "O que guarda": {
        "en-US": "What it holds",
        "es": "Qué guarda",
    },
    "Linhas": {
        "en-US": "Rows",
        "es": "Filas",
    },
    "Aplicar no banco": {
        "en-US": "Apply to the database",
        "es": "Aplicar en la base",
    },
    "Roda o schema e a carga em uma transação: ou entra inteiro, ou não entra. Metade de um organograma no banco é pior do que nenhum.": {
        "en-US": "Runs the schema and the load in one transaction: either it all lands, or none does. Half an org chart in the database is worse than none.",
        "es": "Ejecuta el esquema y la carga en una transacción: o entra entero, o no entra. Medio organigrama en la base es peor que ninguno.",
    },
    "Indisponível: defina <code>ORG_DATABASE_URL</code> e instale <code>psycopg</code>. Enquanto isso, os dois botões de download acima entregam o mesmo SQL para rodar em qualquer cliente.": {
        "en-US": "Unavailable: set <code>ORG_DATABASE_URL</code> and install <code>psycopg</code>. Meanwhile, the two download buttons above deliver the same SQL to run in any client.",
        "es": "No disponible: defina <code>ORG_DATABASE_URL</code> e instale <code>psycopg</code>. Mientras tanto, los dos botones de descarga arriba entregan el mismo SQL para ejecutar en cualquier cliente.",
    },
    "Aplicar o schema cria tipos, tabelas e índices. Rodar duas vezes falha nos tipos já existentes — é esperado.": {
        "en-US": "Applying the schema creates types, tables and indexes. Running it twice fails on the existing types — that is expected.",
        "es": "Aplicar el esquema crea tipos, tablas e índices. Ejecutarlo dos veces falla en los tipos existentes — es lo esperado.",
    },
    "Aplicar schema": {
        "en-US": "Apply schema",
        "es": "Aplicar esquema",
    },
    "Escrever o organograma vigente no banco?": {
        "en-US": "Write the current org chart to the database?",
        "es": "¿Escribir el organigrama vigente en la base?",
    },
    "Escrever organograma": {
        "en-US": "Write org chart",
        "es": "Escribir organigrama",
    },
    "Conexão bem-sucedida: {detalhe}": {
        "en-US": "Connection succeeded: {detalhe}",
        "es": "Conexión exitosa: {detalhe}",
    },
    "Conexão recusada: {detalhe}": {
        "en-US": "Connection refused: {detalhe}",
        "es": "Conexión rechazada: {detalhe}",
    },
    "Schema aplicado.": {
        "en-US": "Schema applied.",
        "es": "Esquema aplicado.",
    },
    "Schema recusado: {detalhe}": {
        "en-US": "Schema refused: {detalhe}",
        "es": "Esquema rechazado: {detalhe}",
    },
    "Organograma escrito: {n} unidades.": {
        "en-US": "Org chart written: {n} units.",
        "es": "Organigrama escrito: {n} unidades.",
    },
    "Escrita recusada: {detalhe}": {
        "en-US": "Write refused: {detalhe}",
        "es": "Escritura rechazada: {detalhe}",
    },
    "Um registro por organograma: título, tenant e orientação padrão.": {
        "en-US": "One row per org chart: title, tenant and default orientation.",
        "es": "Un registro por organigrama: título, tenant y orientación predeterminada.",
    },
    "A pessoa, com matrícula (ID SAP), admissão e situação declarada pelo RH. Sem CPF, RG, endereço, dado de saúde ou remuneração (LGPD-01/02).": {
        "en-US": "The person, with payroll number (SAP ID), hire date and the "
                 "status HR declares. No national ID, address, health data or "
                 "pay (LGPD-01/02).",
        "es": "La persona, con matrícula (ID SAP), fecha de ingreso y la "
              "situación que declara RR. HH. Sin documento nacional, "
              "dirección, dato de salud ni remuneración (LGPD-01/02).",
    },
    "O nó da árvore: código, nome, tipo, pai e ordem de exibição.": {
        "en-US": "The tree node: code, name, type, parent and display order.",
        "es": "El nodo del árbol: código, nombre, tipo, padre y orden de exhibición.",
    },
    "Ancestral × descendente com profundidade — é ela que faz subárvore custar um índice em vez de uma recursão.": {
        "en-US": "Ancestor × descendant with depth — it is what makes a subtree cost an index instead of a recursion.",
        "es": "Ancestro × descendiente con profundidad — es lo que hace que un subárbol cueste un índice en vez de una recursión.",
    },
    "Quem ocupa a unidade, em que papel e sob que regime, com vigência. Um responsável por unidade em cada intervalo, garantido por EXCLUDE.": {
        "en-US": "Who holds the unit, in what role and under which contract "
                 "type, with a validity range. One owner per unit per "
                 "interval, enforced by EXCLUDE.",
        "es": "Quién ocupa la unidad, en qué rol y bajo qué régimen, con "
              "vigencia. Un responsable por unidad en cada intervalo, "
              "garantizado por EXCLUDE.",
    },
    "Accountability própria ou delegada, com a guarda de coerência da delegação.": {
        "en-US": "Own or delegated accountability, with the delegation coherence guard.",
        "es": "Accountability propia o delegada, con la guarda de coherencia de la delegación.",
    },
    "O mesmo ledger encadeado por SHA-256 que a aba Auditoria verifica.": {
        "en-US": "The same SHA-256 chained ledger that the Audit tab verifies.",
        "es": "El mismo registro encadenado por SHA-256 que la pestaña Auditoría verifica.",
    },
    "Nosso propósito": {
        "en-US": "Our purpose",
        "es": "Nuestro propósito",
    },
    "Entrar": {
        "en-US": "Sign in",
        "es": "Entrar",
    },
    "Conectados pelo sucesso:": {
        "en-US": "Connected by success:",
        "es": "Conectados por el éxito:",
    },
    "explore nossa estrutura organizacional": {
        "en-US": "explore our organizational structure",
        "es": "explore nuestra estructura organizacional",
    },
    "Use o e-mail da organização ({dominios}).": {
        "en-US": "Use your organization e-mail ({dominios}).",
        "es": "Use el correo de la organización ({dominios}).",
    },
    "Quem é você na estrutura": {
        "en-US": "Who you are in the structure",
        "es": "Quién es usted en la estructura",
    },
    "— não vinculado —": {
        "en-US": "— not linked —",
        "es": "— sin vincular —",
    },
    "Alimenta o avatar da barra. Não concede permissão: quem decide isso é o perfil acima.": {
        "en-US": "Feeds the avatar in the top bar. It grants no permission: that is decided by the role above.",
        "es": "Alimenta el avatar de la barra. No concede permiso: eso lo decide el perfil de arriba.",
    },
    "Conta e preferências": {
        "en-US": "Account and preferences",
        "es": "Cuenta y preferencias",
    },
    "Sem usuário vinculado": {
        "en-US": "No linked user",
        "es": "Sin usuario vinculado",
    },
    "Escolha em Configurações › Permissões quem é você na estrutura.": {
        "en-US": "Pick who you are in the structure under Settings › Permissions.",
        "es": "Elija en Configuración › Permisos quién es usted en la estructura.",
    },
    "Perfil": {
        "en-US": "Role",
        "es": "Perfil",
    },
    "Tema escuro": {
        "en-US": "Dark theme",
        "es": "Tema oscuro",
    },
    "Tema claro": {
        "en-US": "Light theme",
        "es": "Tema claro",
    },
    "Sair do sistema": {
        "en-US": "Sign out",
        "es": "Salir del sistema",
    },
    "{n} unidades · perfil vigente <b>{perfil}</b> · ledger": {
        "en-US": "{n} units · current role <b>{perfil}</b> · ledger",
        "es": "{n} unidades · perfil vigente <b>{perfil}</b> · registro de auditoría",
    },
    "íntegro com {n} evento(s)": {
        "en-US": "intact with {n} event(s)",
        "es": "íntegro con {n} evento(s)",
    },
    "rompido no evento #{seq}": {
        "en-US": "broken at event #{seq}",
        "es": "roto en el evento #{seq}",
    },
    "{n} cargo(s) distintos na estrutura. O cargo exato manda sobre a regra de palavra-chave — foi a regra que gerou a primeira versão desta lista, mas o que você decidir aqui passa a valer.": {
        "en-US": "{n} distinct job titles in the structure. The exact job title overrides the keyword rule — the rule produced the first version of this list, but what you decide here is what counts from now on.",
        "es": "{n} cargos distintos en la estructura. El cargo exacto manda sobre la regla de palabra clave — la regla generó la primera versión de esta lista, pero lo que usted decida aquí es lo que vale.",
    },
    "{n} cargo(s) com nível divergente do catálogo.": {
        "en-US": "{n} job title(s) whose level differs from the catalog.",
        "es": "{n} cargo(s) con nivel divergente del catálogo.",
    },
    "Alguém editou o nível direto no painel, ou o catálogo mudou e ninguém aplicou:": {
        "en-US": "Someone edited the level directly in the panel, or the catalog changed and nobody applied it:",
        "es": "Alguien editó el nivel directo en el panel, o el catálogo cambió y nadie lo aplicó:",
    },
    "Nova unidade": {
        "en-US": "New unit",
        "es": "Nueva unidad",
    },
    "{nome} (cópia)": {
        "en-US": "{nome} (copy)",
        "es": "{nome} (copia)",
    },
    "+ {n} accountabilities": {
        "en-US": "+ {n} accountabilities",
        "es": "+ {n} accountabilities",
    },
    "Colapsar subordinados de {nome}": {
        "en-US": "Collapse reports of {nome}",
        "es": "Colapsar subordinados de {nome}",
    },
    "Expandir subordinados de {nome}": {
        "en-US": "Expand reports of {nome}",
        "es": "Expandir subordinados de {nome}",
    },
    "escala {escala}": {
        "en-US": "scale {escala}",
        "es": "escala {escala}",
    },
    "coluna obrigatória ausente: {faltando}. Esperado: {esperado}": {
        "en-US": "required column missing: {faltando}. Expected: {esperado}",
        "es": "columna obligatoria ausente: {faltando}. Esperado: {esperado}",
    },
    "ORG-DUPLICIDADE: colaborador repetido na planilha: {dup}": {
        "en-US": "ORG-DUPLICATE: employee repeated in the spreadsheet: {dup}",
        "es": "ORG-DUPLICIDAD: colaborador repetido en la planilla: {dup}",
    },
    "Nenhuma linha tem e-mail: o pareamento cairá para o nome, e renomear alguém será lido como troca de pessoa.": {
        "en-US": "No row has an e-mail: matching falls back to the name, and renaming someone will read as replacing a person.",
        "es": "Ninguna fila tiene correo: el emparejamiento cae al nombre, y renombrar a alguien se leerá como cambio de persona.",
    },
    "{n} linha(s) apontam para gestor inexistente e passariam a responder à raiz: {quais}": {
        "en-US": "{n} row(s) point to a manager that does not exist and would report to the root: {quais}",
        "es": "{n} fila(s) apuntan a un gestor inexistente y pasarían a reportar a la raíz: {quais}",
    },
    "A {pct} % o texto sai ilegível no papel: filtre, colapse ou foque uma subárvore antes de imprimir.": {
        "en-US": "At {pct} % the text is unreadable on paper: filter, collapse or focus a subtree before printing.",
        "es": "Al {pct} % el texto queda ilegible en papel: filtre, colapse o enfoque un subárbol antes de imprimir.",
    },
    "O desenho atual cabe a {pct} % da escala de tela.": {
        "en-US": "The current chart fits at {pct} % of the screen scale.",
        "es": "El diagrama actual cabe al {pct} % de la escala de pantalla.",
    },
    "PDF A3": {
        "en-US": "A3 PDF",
        "es": "PDF A3",
    },
    "Expandir subárvore": {
        "en-US": "Expand subtree",
        "es": "Expandir subárbol",
    },
    "Colapsar subárvore": {
        "en-US": "Collapse subtree",
        "es": "Colapsar subárbol",
    },
    "manual": {
        "en-US": "manual",
        "es": "manual",
    },
    "criar": {
        "en-US": "create",
        "es": "crear",
    },
    "alterar": {
        "en-US": "change",
        "es": "modificar",
    },
    "mover": {
        "en-US": "move",
        "es": "mover",
    },
    "inativar": {
        "en-US": "deactivate",
        "es": "desactivar",
    },
    "{n} pessoa(s) no cadastro, sem faixa própria na apresentação": {
        "en-US": "{n} people in the registry, with no band of their own in the deck",
        "es": "{n} personas en el registro, sin banda propia en la presentación",
    },
    "{n} pessoa(s) fora das faixas": {
        "en-US": "{n} people outside the bands",
        "es": "{n} personas fuera de las bandas",
    },
    "{n} nome(s) corrigido(s) na leitura": {
        "en-US": "{n} name(s) corrected on read",
        "es": "{n} nombre(s) corregido(s) en la lectura",
    },
    "{n} departamento(s) sem nome em português": {
        "en-US": "{n} departments with no Portuguese name",
        "es": "{n} departamentos sin nombre en portugués",
    },
    " — corrija também na planilha, senão a próxima carga repete": {
        "en-US": " — fix it in the spreadsheet too, otherwise the next load repeats it",
        "es": " — corrija también en la planilla, si no la próxima carga lo repite",
    },
    "Grafia": {
        "en-US": "Spelling",
        "es": "Ortografía",
    },
    "Cadeia íntegra · {n} evento(s) verificado(s)": {
        "en-US": "Chain intact · {n} event(s) verified",
        "es": "Cadena íntegra · {n} evento(s) verificado(s)",
    },
    "Cadeia rompida a partir do evento #{seq}": {
        "en-US": "Chain broken from event #{seq}",
        "es": "Cadena rota a partir del evento #{seq}",
    },
    "Limpar {campo}": {
        "en-US": "Clear {campo}",
        "es": "Limpiar {campo}",
    },
    "Limpar filtro {campo}": {
        "en-US": "Clear {campo} filter",
        "es": "Limpiar filtro {campo}",
    },
    "Filtrar por {campo}": {
        "en-US": "Filter by {campo}",
        "es": "Filtrar por {campo}",
    },
    "Filtrar opções de {campo}": {
        "en-US": "Filter {campo} options",
        "es": "Filtrar opciones de {campo}",
    },
    "filtrar {campo}…": {
        "en-US": "filter {campo}…",
        "es": "filtrar {campo}…",
    },
    "Membros de {faixa}": {
        "en-US": "Members of {faixa}",
        "es": "Miembros de {faixa}",
    },
    "Departamentos de {vertical}": {
        "en-US": "Departments of {vertical}",
        "es": "Departamentos de {vertical}",
    },
    "{n} em {departamento}": {
        "en-US": "{n} in {departamento}",
        "es": "{n} en {departamento}",
    },
    "{n} pessoas atendendo o cliente": {
        "en-US": "{n} people serving the customer",
        "es": "{n} personas atendiendo al cliente",
    },
    "{n} divergência": {
        "en-US": "{n} discrepancy",
        "es": "{n} discrepancia",
    },
    "{n} divergências": {
        "en-US": "{n} discrepancies",
        "es": "{n} discrepancias",
    },
    "Idioma da interface": {
        "en-US": "Interface language",
        "es": "Idioma de la interfaz",
    },
    "Manual": {
        "en-US": "Manual",
        "es": "Manual",
    },
    "Boas-vindas!": {
        "en-US": "Welcome!",
        "es": "¡Bienvenido!",
    },
    # --- poço de sugestões da MarIA (main.SUGESTOES) -----------------------
    'Qual gestor tem mais gente reportando direto, e isso é sustentável?': {
        "en-US": 'Which manager has the most direct reports, and is that sustainable?',
        "es": '¿Qué gerente tiene más gente reportando directo, y eso es sostenible?',
    },
    'Existe nível hierárquico que só tem uma pessoa em toda a vertical?': {
        "en-US": 'Is there a hierarchy level with a single person in the whole vertical?',
        "es": '¿Hay un nivel jerárquico con una sola persona en toda la vertical?',
    },
    'Onde a cadeia de comando tem mais degraus do que precisa?': {
        "en-US": 'Where does the chain of command have more steps than it needs?',
        "es": '¿Dónde la cadena de mando tiene más escalones de los necesarios?',
    },
    'Que áreas dependem de uma pessoa só para não parar?': {
        "en-US": 'Which areas depend on a single person to keep running?',
        "es": '¿Qué áreas dependen de una sola persona para no parar?',
    },
    'Quais times têm mais chefia do que gente executando?': {
        "en-US": 'Which teams have more leadership than people executing?',
        "es": '¿Qué equipos tienen más jefatura que gente ejecutando?',
    },
    'Há alguém respondendo a um gestor de nível igual ou inferior ao seu?': {
        "en-US": 'Is anyone reporting to a manager at the same or a lower level?',
        "es": '¿Hay alguien reportando a un gerente de nivel igual o inferior al suyo?',
    },
    'Onde a profundidade da árvore destoa do resto da empresa?': {
        "en-US": 'Where does the tree depth stand out from the rest of the company?',
        "es": '¿Dónde la profundidad del árbol desentona del resto de la empresa?',
    },
    'Que departamentos cresceram sem ganhar um nível de coordenação?': {
        "en-US": 'Which departments grew without gaining a coordination level?',
        "es": '¿Qué departamentos crecieron sin ganar un nivel de coordinación?',
    },
    'Qual é o caminho mais longo da base até a diretoria?': {
        "en-US": 'What is the longest path from the base to the board?',
        "es": '¿Cuál es el camino más largo de la base hasta la dirección?',
    },
    'Existe vertical inteira sem ninguém em nível de gerência?': {
        "en-US": 'Is there a whole vertical with nobody at management level?',
        "es": '¿Hay una vertical entera sin nadie en nivel de gerencia?',
    },
    'Que centros de custo têm gente de mais de um departamento?': {
        "en-US": 'Which cost centers hold people from more than one department?',
        "es": '¿Qué centros de costo tienen gente de más de un departamento?',
    },
    'Quais departamentos aparecem em mais de um centro de custo?': {
        "en-US": 'Which departments appear in more than one cost center?',
        "es": '¿Qué departamentos aparecen en más de un centro de costo?',
    },
    'Há centro de custo cadastrado que nenhuma pessoa usa?': {
        "en-US": 'Is there a registered cost center that nobody uses?',
        "es": '¿Hay un centro de costo registrado que nadie usa?',
    },
    'Que pessoas estão num centro de custo que não casa com o time delas?': {
        "en-US": 'Which people sit in a cost center that does not match their team?',
        "es": '¿Qué personas están en un centro de costo que no coincide con su equipo?',
    },
    'Quais times têm nome parecido e talvez sejam o mesmo?': {
        "en-US": 'Which teams have similar names and might be the same one?',
        "es": '¿Qué equipos tienen nombre parecido y quizá sean el mismo?',
    },
    'Que centros de custo concentram mais gente do que a vertical inteira?': {
        "en-US": 'Which cost centers hold more people than an entire vertical?',
        "es": '¿Qué centros de costo concentran más gente que la vertical entera?',
    },
    'Onde o nome do departamento na planilha discorda do cadastro?': {
        "en-US": 'Where does the department name in the spreadsheet disagree with the register?',
        "es": '¿Dónde el nombre del departamento en la planilla discrepa del registro?',
    },
    'Quais verticais de negócio estão sem natureza definida?': {
        "en-US": 'Which business verticals have no nature defined?',
        "es": '¿Qué verticales de negocio están sin naturaleza definida?',
    },
    'Que centros de custo estão sem mnemônico N5 preenchido?': {
        "en-US": 'Which cost centers have no N5 mnemonic filled in?',
        "es": '¿Qué centros de costo están sin mnemónico N5 completado?',
    },
    'Há departamento com pessoas em verticais diferentes?': {
        "en-US": 'Is there a department with people in different verticals?',
        "es": '¿Hay un departamento con personas en verticales diferentes?',
    },
    'Que cargos existem em mais de uma vertical, e com que peso em cada?': {
        "en-US": 'Which job titles exist in more than one vertical, and with what weight in each?',
        "es": '¿Qué cargos existen en más de una vertical, y con qué peso en cada una?',
    },
    'Quais cargos têm uma pessoa só na empresa inteira?': {
        "en-US": 'Which job titles have a single person in the whole company?',
        "es": '¿Qué cargos tienen una sola persona en toda la empresa?',
    },
    'Onde há mais de um cargo com a mesma responsabilidade?': {
        "en-US": 'Where is there more than one job title with the same responsibility?',
        "es": '¿Dónde hay más de un cargo con la misma responsabilidad?',
    },
    'Que proporção do quadro está fora do vínculo CLT, e onde?': {
        "en-US": 'What share of the headcount is outside the CLT contract, and where?',
        "es": '¿Qué proporción de la plantilla está fuera del vínculo CLT, y dónde?',
    },
    'Quais áreas concentram terceiros ou estagiários?': {
        "en-US": 'Which areas concentrate contractors or interns?',
        "es": '¿Qué áreas concentran terceros o pasantes?',
    },
    'Que cargos de liderança estão em nível de execução, ou o contrário?': {
        "en-US": 'Which leadership titles sit at an execution level, or the other way round?',
        "es": '¿Qué cargos de liderazgo están en nivel de ejecución, o al revés?',
    },
    'Onde o cargo escrito não corresponde ao nível hierárquico atribuído?': {
        "en-US": 'Where does the written job title not match the assigned hierarchy level?',
        "es": '¿Dónde el cargo escrito no corresponde al nivel jerárquico asignado?',
    },
    'Quais times não têm ninguém em nível sênior?': {
        "en-US": 'Which teams have nobody at a senior level?',
        "es": '¿Qué equipos no tienen a nadie en nivel sénior?',
    },
    'Que cargos aparecem só na diretoria e em nenhum outro nível?': {
        "en-US": 'Which job titles appear only on the board and at no other level?',
        "es": '¿Qué cargos aparecen solo en la dirección y en ningún otro nivel?',
    },
    'Como o quadro se distribui entre as naturezas de centro de custo?': {
        "en-US": 'How is the headcount spread across the cost center natures?',
        "es": '¿Cómo se distribuye la plantilla entre las naturalezas de centro de costo?',
    },
    'Que accountabilities aparecem em mais de uma pessoa ao mesmo tempo?': {
        "en-US": 'Which accountabilities appear on more than one person at the same time?',
        "es": '¿Qué accountabilities aparecen en más de una persona a la vez?',
    },
    'Quais áreas não têm nenhuma accountability declarada?': {
        "en-US": 'Which areas have no accountability declared at all?',
        "es": '¿Qué áreas no tienen ninguna accountability declarada?',
    },
    'Onde há accountability delegada sem quem execute abaixo?': {
        "en-US": 'Where is there a delegated accountability with nobody below to execute it?',
        "es": '¿Dónde hay accountability delegada sin quien la ejecute abajo?',
    },
    'Que responsabilidades ficaram sem dono depois da última mudança?': {
        "en-US": 'Which responsibilities were left ownerless after the last change?',
        "es": '¿Qué responsabilidades quedaron sin dueño tras el último cambio?',
    },
    'Quais pessoas acumulam mais accountabilities do que a média?': {
        "en-US": 'Which people carry more accountabilities than the average?',
        "es": '¿Qué personas acumulan más accountabilities que el promedio?',
    },
    'Se eu tirasse uma vertical, que estrutura de apoio ficaria ociosa?': {
        "en-US": 'If I removed a vertical, which support structure would sit idle?',
        "es": 'Si quitara una vertical, ¿qué estructura de apoyo quedaría ociosa?',
    },
    'Onde a estrutura está mais pesada do que o tamanho do time justifica?': {
        "en-US": 'Where is the structure heavier than the team size justifies?',
        "es": '¿Dónde la estructura está más pesada de lo que el tamaño del equipo justifica?',
    },
    'Que mudança deixaria a árvore mais rasa sem perder controle?': {
        "en-US": 'What change would make the tree shallower without losing control?',
        "es": '¿Qué cambio dejaría el árbol más plano sin perder control?',
    },
    'Quais departamentos estão fora das quatro faixas da apresentação?': {
        "en-US": 'Which departments fall outside the four bands of the presentation?',
        "es": '¿Qué departamentos están fuera de las cuatro franjas de la presentación?',
    },
    'O que mais chama atenção neste recorte que eu não perguntei?': {
        "en-US": 'What else stands out in this slice that I did not ask about?',
        "es": '¿Qué más llama la atención en este recorte que no pregunté?',
    },
    # --- a visita guiada (ajuda.py) ---------------------------------------
    "O organograma, de cabeça para baixo": {
        "en-US": "The org chart, upside down",
        "es": "El organigrama, de cabeza",
    },
    "A liderança fica na base e os times liderados, acima. Não é enfeite: quem "
    "sustenta aparece embaixo, e a leitura sobe de quem decide para quem "
    "executa. Cada card é uma posição ocupada por uma pessoa.": {
        "en-US": "Leadership sits at the base and the teams they lead sit above. "
                 "It is not decoration: whoever carries the weight appears at the "
                 "bottom, and reading goes up from who decides to who executes. "
                 "Each card is a position held by a person.",
        "es": "El liderazgo queda en la base y los equipos liderados, arriba. No "
              "es adorno: quien sostiene aparece abajo, y la lectura sube de quien "
              "decide a quien ejecuta. Cada tarjeta es una posición ocupada por "
              "una persona.",
    },
    "A alça abre e dobra o galho": {
        "en-US": "The handle opens and folds the branch",
        "es": "El tirador abre y pliega la rama",
    },
    "O `+n` diz quantas pessoas estão escondidas atrás daquele card. Clicar "
    "abre; o `−` dobra de volta. O que está dobrado continua contando no "
    "cabeçalho do desenho — some da tela, não da conta.": {
        "en-US": "The `+n` tells how many people are hidden behind that card. "
                 "Clicking opens it; `−` folds it back. What is folded still "
                 "counts in the chart header — it leaves the screen, not the count.",
        "es": "El `+n` dice cuántas personas están escondidas detrás de esa "
              "tarjeta. Al hacer clic se abre; `−` la pliega de vuelta. Lo plegado "
              "sigue contando en el encabezado del dibujo — sale de la pantalla, "
              "no de la cuenta.",
    },
    "Criar uma unidade": {
        "en-US": "Create a unit",
        "es": "Crear una unidad",
    },
    "Cria um subordinado direto da raiz da vista. Toda criação entra no "
    "histórico e pode ser desfeita.": {
        "en-US": "Creates a direct report of the view's root. Every creation "
                 "enters the history and can be undone.",
        "es": "Crea un subordinado directo de la raíz de la vista. Toda creación "
              "entra en el historial y puede deshacerse.",
    },
    "Como este desenho é lido": {
        "en-US": "How this chart is read",
        "es": "Cómo se lee este dibujo",
    },
    "As duas pirâmides discutem de que lado fica a liderança. A **Lateral** "
    "troca o eixo: a raiz à esquerda, cada nível uma coluna para a direita, a "
    "leitura descendo. É vinte vezes mais estreita — e é a vista que se lê no "
    "celular.": {
        "en-US": "The two pyramids argue about which side leadership sits on. "
                 "**Lateral** swaps the axis: root on the left, each level one "
                 "column to the right, reading downward. It is twenty times "
                 "narrower — and it is the view you read on a phone.",
        "es": "Las dos pirámides discuten de qué lado queda el liderazgo. "
              "**Lateral** cambia el eje: la raíz a la izquierda, cada nivel una "
              "columna a la derecha, la lectura bajando. Es veinte veces más "
              "estrecha — y es la vista que se lee en el celular.",
    },
    "Por pessoa, ou por equipe": {
        "en-US": "By person, or by team",
        "es": "Por persona, o por equipo",
    },
    "Recolhe as pessoas dentro do seu time e desenha só a estrutura. Com 267 "
    "cards, \"como a empresa é organizada\" se perde no meio de \"quem é "
    "quem\"; aqui ficam 81 caixas. Equipe é desenho derivado: não se edita.": {
        "en-US": "Collapses people into their team and draws only the structure. "
                 "With 267 cards, \"how the company is organised\" gets lost "
                 "inside \"who is who\"; here there are 81 boxes. A team is a "
                 "derived drawing: it cannot be edited.",
        "es": "Recoge a las personas dentro de su equipo y dibuja solo la "
              "estructura. Con 267 tarjetas, \"cómo está organizada la empresa\" "
              "se pierde entre \"quién es quién\"; aquí quedan 81 cajas. El "
              "equipo es dibujo derivado: no se edita.",
    },
    "Toda mutação marca um ponto. Os dois nascem desabilitados quando não há "
    "pilha — botão que parece clicável e responde \"nada a desfazer\" ensina a "
    "desconfiar da tela. Editar limpa o futuro.": {
        "en-US": "Every mutation marks a point. Both start disabled when there is "
                 "no stack — a button that looks clickable and answers \"nothing "
                 "to undo\" teaches you to distrust the screen. Editing clears "
                 "the future.",
        "es": "Toda mutación marca un punto. Los dos nacen deshabilitados cuando "
              "no hay pila — un botón que parece clicable y responde \"nada que "
              "deshacer\" enseña a desconfiar de la pantalla. Editar limpia el "
              "futuro.",
    },
    "Levar para fora": {
        "en-US": "Take it out",
        "es": "Llevar afuera",
    },
    "PDF A3, XLSX, SVG, CSV e JSON. **Sai o que está na tela**: filtro, colapso, "
    "foco e orientação valem para o arquivo. O XLSX é o único que volta — traz "
    "uma aba com as colunas que a carga assistida lê de novo. O percentual ao "
    "lado é a escala com que o desenho cabe na folha: abaixo de 38 % o texto sai "
    "ilegível, e o botão avisa antes do download, não depois.": {
        "en-US": "A3 PDF, XLSX, SVG, CSV and JSON. **What is on screen is what "
                 "comes out**: filter, collapse, focus and orientation all apply "
                 "to the file. XLSX is the only one that comes back — it carries "
                 "a tab with the columns the assisted load reads again. The "
                 "percentage beside it is the scale at which the chart fits the "
                 "sheet: below 38 % the text comes out illegible, and the button "
                 "warns before the download, not after.",
        "es": "PDF A3, XLSX, SVG, CSV y JSON. **Sale lo que está en la pantalla**: "
              "filtro, colapso, foco y orientación valen para el archivo. El XLSX "
              "es el único que vuelve — trae una hoja con las columnas que la "
              "carga asistida lee de nuevo. El porcentaje al lado es la escala con "
              "que el dibujo cabe en la hoja: por debajo de 38 % el texto sale "
              "ilegible, y el botón avisa antes de la descarga, no después.",
    },
    "Procura em nome, cargo, e-mail, código, centro de custo e "
    "accountabilities ao mesmo tempo. Ignora acento.": {
        "en-US": "Searches name, job title, e-mail, code, cost center and "
                 "accountabilities at once. Accent-insensitive.",
        "es": "Busca en nombre, cargo, correo, código, centro de costo y "
              "accountabilities a la vez. Ignora el acento.",
    },
    "Oito critérios, e eles se filtram": {
        "en-US": "Eight criteria, and they filter each other",
        "es": "Ocho criterios, y se filtran entre sí",
    },
    "Cada chip oferece o que ainda existe **depois do recorte que os outros "
    "fizeram**: escolhida a vertical F&B, o centro de custo passa de 78 para 9. "
    "Opção que sempre devolveria vazio não é escolha, é armadilha. Combinam em "
    "E lógico.": {
        "en-US": "Each chip offers what still exists **after the slice the others "
                 "made**: pick vertical F&B and cost center drops from 78 to 9. An "
                 "option that would always return nothing is not a choice, it is a "
                 "trap. They combine with logical AND.",
        "es": "Cada chip ofrece lo que aún existe **después del recorte que "
              "hicieron los otros**: elegida la vertical F&B, el centro de costo "
              "pasa de 78 a 9. Una opción que siempre devolvería vacío no es "
              "elección, es trampa. Se combinan con Y lógico.",
    },
    "O que está filtrando agora": {
        "en-US": "What is filtering right now",
        "es": "Lo que está filtrando ahora",
    },
    "Cada valor marcado vira uma pílula, e some no clique. A contagem no chip "
    "diz \"3 centros de custo\" e não diz **quais** — a pílula diz, e deixa "
    "tirar um sem descartar os outros dois.": {
        "en-US": "Each checked value becomes a pill, and disappears on click. The "
                 "count on the chip says \"3 cost centers\" and does not say "
                 "**which** — the pill does, and lets you drop one without "
                 "discarding the other two.",
        "es": "Cada valor marcado se vuelve una píldora, y desaparece al hacer "
              "clic. El conteo del chip dice \"3 centros de costo\" y no dice "
              "**cuáles** — la píldora sí, y deja quitar uno sin descartar los "
              "otros dos.",
    },
    "Recorte por profundidade": {
        "en-US": "Slice by depth",
        "es": "Recorte por profundidad",
    },
    "Mostra só os níveis marcados. Seleção múltipla, porque \"como estão a "
    "diretoria e a coordenação, sem o meio do caminho\" só tem resposta com mais "
    "de um nível ao mesmo tempo. O marcado ganha destaque âmbar; o caminho até "
    "ele fica esmaecido.": {
        "en-US": "Shows only the checked levels. Multiple selection, because "
                 "\"how are the board and the coordination doing, without the "
                 "middle\" only has an answer with more than one level at once. "
                 "The checked one gets an amber highlight; the path to it dims.",
        "es": "Muestra solo los niveles marcados. Selección múltiple, porque "
              "\"cómo están la dirección y la coordinación, sin el medio\" solo "
              "tiene respuesta con más de un nivel a la vez. El marcado gana "
              "realce ámbar; el camino hasta él queda atenuado.",
    },
    "Chevron simples desce um degrau de cada vez; chevron duplo vai ao extremo. "
    "O passo a passo existe porque abrir 267 cards de um golpe responde a "
    "pergunta errada — quem desce nível a nível está lendo a estrutura.": {
        "en-US": "A single chevron steps down one level at a time; a double "
                 "chevron goes to the end. The step-by-step exists because opening "
                 "267 cards at once answers the wrong question — someone going "
                 "level by level is reading the structure.",
        "es": "El chevrón simple baja un escalón por vez; el doble va al extremo. "
              "El paso a paso existe porque abrir 267 tarjetas de golpe responde "
              "la pregunta equivocada — quien baja nivel a nivel está leyendo la "
              "estructura.",
    },
    "Enquadrar": {
        "en-US": "Frame it",
        "es": "Encuadrar",
    },
    "`⊙` ajusta à tela, `↔` ajusta à largura, e o percentual abre presets. A "
    "roda do mouse dá zoom **ancorado no cursor**: o que está sob o ponteiro "
    "continua sob o ponteiro. Duplo clique no fundo reenquadra.": {
        "en-US": "`⊙` fits to screen, `↔` fits to width, and the percentage opens "
                 "presets. The mouse wheel zooms **anchored at the cursor**: "
                 "whatever is under the pointer stays under the pointer. "
                 "Double-click on the background refits.",
        "es": "`⊙` ajusta a la pantalla, `↔` ajusta al ancho, y el porcentaje abre "
              "presets. La rueda del ratón hace zoom **anclado en el cursor**: lo "
              "que está bajo el puntero sigue bajo el puntero. Doble clic en el "
              "fondo reencuadra.",
    },
    "A gaveta": {
        "en-US": "The drawer",
        "es": "El cajón",
    },
    "Clicar num card abre aqui a ficha inteira, e é daqui que se edita. Ela "
    "grava a partir de qualquer vista e devolve a lista de onde você veio. A "
    "tecla `B` recolhe e expande.": {
        "en-US": "Clicking a card opens the whole record here, and this is where "
                 "you edit. It saves from any view and gives back the list you "
                 "came from. The `B` key collapses and expands it.",
        "es": "Hacer clic en una tarjeta abre aquí la ficha entera, y desde aquí "
              "se edita. Graba desde cualquier vista y devuelve la lista de donde "
              "viniste. La tecla `B` recoge y expande.",
    },
    "A assistente lê e analisa a estrutura no **seu** recorte — nunca mais do "
    "que você pode ver. Ela informa e sugere; não altera dados. Cada resposta "
    "vira registro com quem perguntou, em que recorte e quanto custou.": {
        "en-US": "The assistant reads and analyses the structure within **your** "
                 "slice — never more than you can see. She informs and suggests; "
                 "she does not change data. Every answer becomes a record with who "
                 "asked, in which slice and how much it cost.",
        "es": "La asistente lee y analiza la estructura en **tu** recorte — nunca "
              "más de lo que puedes ver. Informa y sugiere; no altera datos. Cada "
              "respuesta se vuelve registro con quién preguntó, en qué recorte y "
              "cuánto costó.",
    },
    "A assistente MarIA": {
        "en-US": "MarIA, the assistant",
        "es": "MarIA, la asistente",
    },
    "As outras vistas": {
        "en-US": "The other views",
        "es": "Las otras vistas",
    },
    "**Estrutura** é a leitura de negócio em funil. **Tabela** é a mesma árvore "
    "em ordem lógica — e o colapso é o mesmo estado do canvas: dobrar aqui dobra "
    "lá. **Configurações** guarda cargos, centros de custo, carga de dados e "
    "permissões.": {
        "en-US": "**Structure** is the business reading as a funnel. **Table** is "
                 "the same tree in logical order — and the collapse is the same "
                 "state as the canvas: folding here folds there. **Settings** "
                 "holds job titles, cost centers, data loading and permissions.",
        "es": "**Estructura** es la lectura de negocio en embudo. **Tabla** es el "
              "mismo árbol en orden lógico — y el colapso es el mismo estado del "
              "lienzo: plegar aquí pliega allá. **Configuración** guarda cargos, "
              "centros de costo, carga de datos y permisos.",
    },
    "Botão direito, nos dois lugares": {
        "en-US": "Right-click, in both places",
        "es": "Clic derecho, en los dos lugares",
    },
    "No card, o que se faz com **aquela pessoa**: editar, mover, promover, "
    "excluir. No vazio, o que se faz com **este desenho**: enquadrar, abrir "
    "níveis, trocar a leitura, sair do foco, limpar filtros. Duas perguntas "
    "diferentes, dois menus.": {
        "en-US": "On a card, what you do with **that person**: edit, move, "
                 "promote, delete. On the background, what you do with **this "
                 "chart**: frame it, open levels, change the reading, leave the "
                 "focus, clear filters. Two different questions, two menus.",
        "es": "En la tarjeta, lo que se hace con **esa persona**: editar, mover, "
              "promover, eliminar. En el vacío, lo que se hace con **este "
              "dibujo**: encuadrar, abrir niveles, cambiar la lectura, salir del "
              "foco, limpiar filtros. Dos preguntas distintas, dos menús.",
    },
    "Encerrar a visita": {
        "en-US": "End the tour",
        "es": "Terminar la visita",
    },
    "Não mostrar de novo": {
        "en-US": "Do not show again",
        "es": "No mostrar de nuevo",
    },
    "Anterior": {
        "en-US": "Back",
        "es": "Anterior",
    },
    "Próximo": {
        "en-US": "Next",
        "es": "Siguiente",
    },
    "Entendi": {
        "en-US": "Got it",
        "es": "Entendido",
    },
    "Helper — a visita guiada": {
        "en-US": "Helper — the guided tour",
        "es": "Helper — la visita guiada",
    },
    "A MarIA entra pela direita e apresenta cada controle da tela, um de cada vez.": {
        "en-US": "MarIA comes in from the right and introduces each control on "
                 "screen, one at a time.",
        "es": "MarIA entra por la derecha y presenta cada control de la pantalla, "
              "uno por vez.",
    },
    "Visita de boas-vindas": {
        "en-US": "Welcome tour",
        "es": "Visita de bienvenida",
    },
    "Ligada": {
        "en-US": "On",
        "es": "Activada",
    },
    "Desligada": {
        "en-US": "Off",
        "es": "Desactivada",
    },
    "Ligada, ela abre uma vez a cada sessão — ou seja, a cada login. Desligada, "
    "não entra no HTML da página.": {
        "en-US": "When on, it opens once per session — that is, on every login. "
                 "When off, it does not enter the page HTML at all.",
        "es": "Activada, abre una vez por sesión — es decir, en cada inicio de "
              "sesión. Desactivada, no entra en el HTML de la página.",
    },
    "Rever agora": {
        "en-US": "Replay now",
        "es": "Ver de nuevo",
    },
    "Começar a visita": {
        "en-US": "Start the tour",
        "es": "Comenzar la visita",
    },
    "Passa por cada botão da tela vigente. Passo cujo controle não está visível "
    "é pulado — em tela estreita, alguns moram dentro de menus.": {
        "en-US": "It walks through every button on the current screen. A step "
                 "whose control is not visible gets skipped — on a narrow screen, "
                 "some of them live inside menus.",
        "es": "Recorre cada botón de la pantalla vigente. El paso cuyo control no "
              "está visible se salta — en pantalla estrecha, algunos viven dentro "
              "de menús.",
    },
    # --- tela estreita: menu do cabeçalho e grupo de filtros ---------------
    "Módulos do sistema": {
        "en-US": "System modules",
        "es": "Módulos del sistema",
    },
    "Filtros": {
        "en-US": "Filters",
        "es": "Filtros",
    },
    "Nenhum {campo} sobrou no recorte atual": {
        "en-US": "No {campo} left in the current selection",
        "es": "Ningún {campo} quedó en el recorte actual",
    },
    "Filtros ativos": {
        "en-US": "Active filters",
        "es": "Filtros activos",
    },
    "filtrando por": {
        "en-US": "filtering by",
        "es": "filtrando por",
    },
    "Remover {campo}: {valor}": {
        "en-US": "Remove {campo}: {valor}",
        "es": "Quitar {campo}: {valor}",
    },
    "Vertical (N2)": {
        "en-US": "Vertical (N2)",
        "es": "Vertical (N2)",
    },
    "Busca livre": {
        "en-US": "Free search",
        "es": "Búsqueda libre",
    },
    # --- sincronização com o Microsoft 365 ---------------------------------
    "Sincronizar centro de custo com o Microsoft 365": {
        "en-US": "Sync cost center with Microsoft 365",
        "es": "Sincronizar centro de costo con Microsoft 365",
    },
    "Lê o campo do diretório corporativo e compara com o que está gravado. "
    "Só o centro de custo é tocado, e nada é escrito no Microsoft 365.": {
        "en-US": "Reads the field from the corporate directory and compares it "
                 "with what is stored. Only the cost center is touched, and "
                 "nothing is written back to Microsoft 365.",
        "es": "Lee el campo del directorio corporativo y lo compara con lo "
              "guardado. Solo se toca el centro de costo, y no se escribe nada "
              "en Microsoft 365.",
    },
    "Falta configurar o Microsoft Entra ID. Defina AZURE_TENANT_ID, "
    "AZURE_CLIENT_ID e AZURE_CLIENT_SECRET no ambiente, e conceda a permissão "
    "de aplicativo User.Read.All com consentimento de administrador.": {
        "en-US": "Microsoft Entra ID is not configured yet. Set AZURE_TENANT_ID, "
                 "AZURE_CLIENT_ID and AZURE_CLIENT_SECRET in the environment, "
                 "and grant the User.Read.All application permission with admin "
                 "consent.",
        "es": "Falta configurar Microsoft Entra ID. Defina AZURE_TENANT_ID, "
              "AZURE_CLIENT_ID y AZURE_CLIENT_SECRET en el entorno, y conceda "
              "el permiso de aplicación User.Read.All con consentimiento de "
              "administrador.",
    },
    "Buscar no Microsoft 365": {
        "en-US": "Fetch from Microsoft 365",
        "es": "Buscar en Microsoft 365",
    },
    "Campo lido:": {
        "en-US": "Field read:",
        "es": "Campo leído:",
    },
    "só contas habilitadas e licenciadas entram — sala, caixa compartilhada e "
    "conta de serviço ficam de fora.": {
        "en-US": "only enabled and licensed accounts are included — rooms, "
                 "shared mailboxes and service accounts are left out.",
        "es": "solo entran cuentas habilitadas y con licencia — salas, buzones "
              "compartidos y cuentas de servicio quedan fuera.",
    },
    "Buscar e comparar": {
        "en-US": "Fetch and compare",
        "es": "Buscar y comparar",
    },
    "conta(s) lida(s) do Microsoft 365 · campo": {
        "en-US": "account(s) read from Microsoft 365 · field",
        "es": "cuenta(s) leída(s) de Microsoft 365 · campo",
    },
    "a atualizar": {
        "en-US": "to update",
        "es": "a actualizar",
    },
    "em conflito": {
        "en-US": "in conflict",
        "es": "en conflicto",
    },
    "já conferem": {
        "en-US": "already match",
        "es": "ya coinciden",
    },
    "sem o campo no M365": {
        "en-US": "no field in M365",
        "es": "sin el campo en M365",
    },
    "fora do M365": {
        "en-US": "not in M365",
        "es": "fuera de M365",
    },
    "o Microsoft 365 é pelo menos tão específico quanto o que está gravado": {
        "en-US": "Microsoft 365 is at least as specific as what is stored",
        "es": "Microsoft 365 es al menos tan específico como lo guardado",
    },
    "a unidade não tem centro de custo e o Microsoft 365 tem": {
        "en-US": "the unit has no cost center and Microsoft 365 does",
        "es": "la unidad no tiene centro de costo y Microsoft 365 sí",
    },
    "A atualizar": {
        "en-US": "To update",
        "es": "A actualizar",
    },
    "Gravado": {
        "en-US": "Stored",
        "es": "Guardado",
    },
    "No Microsoft 365": {
        "en-US": "In Microsoft 365",
        "es": "En Microsoft 365",
    },
    "A preencher": {
        "en-US": "To fill in",
        "es": "A completar",
    },
    "Em conflito — não aplicáveis": {
        "en-US": "In conflict — not applicable",
        "es": "En conflicto — no aplicables",
    },
    "O Microsoft 365 traz um código menos específico e diferente do gravado. "
    "Gravá-lo apagaria a equipe, então a correção é numa das duas fontes, "
    "por gente.": {
        "en-US": "Microsoft 365 carries a less specific code that also "
                 "disagrees with the stored one. Writing it would erase the "
                 "team, so the fix belongs in one of the two sources, made by "
                 "a person.",
        "es": "Microsoft 365 trae un código menos específico y distinto del "
              "guardado. Guardarlo borraría el equipo, así que la corrección "
              "va en una de las dos fuentes, hecha por una persona.",
    },
    "Fora do Microsoft 365": {
        "en-US": "Not in Microsoft 365",
        "es": "Fuera de Microsoft 365",
    },
    "Ninguém é removido por não ter conta: prestador e consultoria "
    "legitimamente não têm licença.": {
        "en-US": "Nobody is removed for lacking an account: contractors and "
                 "consultants legitimately have no license.",
        "es": "Nadie se elimina por no tener cuenta: proveedores y consultoría "
              "legítimamente no tienen licencia.",
    },
    "Contas sem par no organograma": {
        "en-US": "Accounts with no match in the org chart",
        "es": "Cuentas sin par en el organigrama",
    },
    "Pessoa nova entra pela planilha, não por aqui: o Microsoft 365 não diz a "
    "quem ela responde, e criar sem gestor a penduraria na raiz.": {
        "en-US": "A new person comes in through the spreadsheet, not here: "
                 "Microsoft 365 does not say who they report to, and creating "
                 "them without a manager would hang them off the root.",
        "es": "Una persona nueva entra por la planilla, no por aquí: Microsoft "
              "365 no dice a quién responde, y crearla sin gestor la colgaría "
              "de la raíz.",
    },
    "Aplicar a sincronização? A operação entra no ledger e pode ser desfeita "
    "uma vez.": {
        "en-US": "Apply the sync? The operation is recorded in the ledger and "
                 "can be undone once.",
        "es": "¿Aplicar la sincronización? La operación entra en el ledger y "
              "puede deshacerse una vez.",
    },
    "o Microsoft 365 respondeu {codigo}. {d}": {
        "en-US": "Microsoft 365 answered {codigo}. {d}",
        "es": "Microsoft 365 respondió {codigo}. {d}",
    },
    "Microsoft Entra ID não configurado: faltam AZURE_CLIENT_ID e "
    "AZURE_CLIENT_SECRET.": {
        "en-US": "Microsoft Entra ID is not configured: AZURE_CLIENT_ID and "
                 "AZURE_CLIENT_SECRET are missing.",
        "es": "Microsoft Entra ID no está configurado: faltan AZURE_CLIENT_ID "
              "y AZURE_CLIENT_SECRET.",
    },
    "o Entra ID recusou as credenciais: {erro}": {
        "en-US": "Entra ID rejected the credentials: {erro}",
        "es": "Entra ID rechazó las credenciales: {erro}",
    },
    "o Microsoft 365 recusou a leitura (403). Falta consentimento de "
    "administrador para User.Read.All. {d}": {
        "en-US": "Microsoft 365 refused the read (403). Admin consent for "
                 "User.Read.All is missing. {d}",
        "es": "Microsoft 365 rechazó la lectura (403). Falta consentimiento de "
              "administrador para User.Read.All. {d}",
    },
    "{n} pessoa(s) têm no MS365 um centro de custo menos específico e "
    "diferente do que está gravado. Não são aplicáveis: gravar o código curto "
    "apagaria a equipe.": {
        "en-US": "{n} person(s) have a cost center in M365 that is both less "
                 "specific and different from the stored one. They are not "
                 "applicable: writing the short code would erase the team.",
        "es": "{n} persona(s) tienen en M365 un centro de costo menos "
              "específico y distinto del guardado. No son aplicables: guardar "
              "el código corto borraría el equipo.",
    },
    "{n} conta(s) do MS365 não casam com ninguém do organograma. Pessoa nova "
    "entra pela planilha, não por aqui: o MS365 não diz a quem ela responde.": {
        "en-US": "{n} M365 account(s) match nobody in the org chart. A new "
                 "person comes in through the spreadsheet, not here: M365 does "
                 "not say who they report to.",
        "es": "{n} cuenta(s) de M365 no coinciden con nadie del organigrama. "
              "Una persona nueva entra por la planilla, no por aquí: M365 no "
              "dice a quién responde.",
    },
    "{n} pessoa(s) do organograma não têm conta habilitada e licenciada no "
    "MS365 — {p} delas não são CLT, o que explica a ausência. Ninguém é "
    "removido por isso.": {
        "en-US": "{n} person(s) in the org chart have no enabled and licensed "
                 "M365 account — {p} of them are not full employees, which "
                 "explains the absence. Nobody is removed for this.",
        "es": "{n} persona(s) del organigrama no tienen cuenta habilitada y "
              "con licencia en M365 — {p} de ellas no son empleadas, lo que "
              "explica la ausencia. Nadie se elimina por eso.",
    },
    "Sincronização aplicada: {n} centro(s) de custo atualizado(s) a partir do "
    "Microsoft 365.": {
        "en-US": "Sync applied: {n} cost center(s) updated from Microsoft 365.",
        "es": "Sincronización aplicada: {n} centro(s) de costo actualizado(s) "
              "desde Microsoft 365.",
    },
    "Microsoft 365 não respondeu: {erro}": {
        "en-US": "Microsoft 365 did not respond: {erro}",
        "es": "Microsoft 365 no respondió: {erro}",
    },
    "sincronização de centro de custo com o Microsoft 365": {
        "en-US": "cost center sync with Microsoft 365",
        "es": "sincronización de centro de costo con Microsoft 365",
    },
    # --- canvas agrupado por equipe ----------------------------------------
    "▣ Por equipe": {
        "en-US": "▣ By team",
        "es": "▣ Por equipo",
    },
    "▢ Por pessoa": {
        "en-US": "▢ By person",
        "es": "▢ Por persona",
    },
    "Recolhe as pessoas dentro do seu time e desenha só a estrutura": {
        "en-US": "Collapses people into their team and draws the structure only",
        "es": "Recoge a las personas dentro de su equipo y dibuja solo la estructura",
    },
    "Equipe": {
        "en-US": "Team",
        "es": "Equipo",
    },
    "por equipe": {
        "en-US": "by team",
        "es": "por equipo",
    },
    "Níveis": {
        "en-US": "Levels",
        "es": "Niveles",
    },
    "Mostrar apenas os níveis marcados": {
        "en-US": "Show only the checked levels",
        "es": "Mostrar solo los niveles marcados",
    },
    "Mostra apenas o nível {n}. Marque mais de um para comparar.": {
        "en-US": "Shows level {n} only. Check more than one to compare.",
        "es": "Muestra solo el nivel {n}. Marque más de uno para comparar.",
    },
    "Volta a mostrar todos os níveis": {
        "en-US": "Shows every level again",
        "es": "Vuelve a mostrar todos los niveles",
    },
    "Limpar": {
        "en-US": "Clear",
        "es": "Limpiar",
    },
    # --- barra do canvas: exportar, desfazer/refazer, abrir/dobrar ----------
    "Exportar": {
        "en-US": "Export",
        "es": "Exportar",
    },
    "Exportar XLSX": {
        "en-US": "Export XLSX",
        "es": "Exportar XLSX",
    },
    "Importar XLSX": {
        "en-US": "Import XLSX",
        "es": "Importar XLSX",
    },
    "Duas abas: a apresentação, agrupada por nível, e a aba ORG com as colunas que a carga lê de volta. Sai o que está na tela.": {
        "en-US": "Two tabs: the presentation one, grouped by level, and the ORG "
                 "tab with the columns the load reads back. What is on screen "
                 "is what comes out.",
        "es": "Dos hojas: la de presentación, agrupada por nivel, y la hoja ORG "
              "con las columnas que la carga lee de vuelta. Sale lo que está en "
              "la pantalla.",
    },
    "Abre a carga assistida em Configurações, já com o arquivo analisado: você confere o que muda antes de aplicar.": {
        "en-US": "Opens the assisted load under Settings with the file already "
                 "analysed: you review what changes before applying it.",
        "es": "Abre la carga asistida en Configuración, ya con el archivo "
              "analizado: usted revisa lo que cambia antes de aplicarlo.",
    },
    "Sai o que está na tela: filtro, colapso e foco valem para o arquivo.": {
        "en-US": "What is on screen is what comes out: filter, collapse and "
                 "focus all apply to the file.",
        "es": "Sale lo que está en la pantalla: filtro, colapso y foco valen "
              "para el archivo.",
    },
    "A {pct} % o texto sai ilegível: filtre, colapse ou foque antes de imprimir.": {
        "en-US": "At {pct} % the text prints illegible: filter, collapse or "
                 "focus before printing.",
        "es": "Al {pct} % el texto sale ilegible: filtre, colapse o enfoque "
              "antes de imprimir.",
    },
    "Uma folha, vetorial e pesquisável.": {
        "en-US": "One sheet, vector and searchable.",
        "es": "Una hoja, vectorial y con búsqueda.",
    },
    "Abre no Inkscape ou no Illustrator e continua editável.": {
        "en-US": "Opens in Inkscape or Illustrator and stays editable.",
        "es": "Se abre en Inkscape o Illustrator y sigue siendo editable.",
    },
    "XLSX": {
        "en-US": "XLSX",
        "es": "XLSX",
    },
    "Excel com a marca e as pessoas agrupadas por nível — e volta pela carga assistida.": {
        "en-US": "Excel with the brand and people grouped by level — and it goes "
                 "back in through the assisted load.",
        "es": "Excel con la marca y las personas agrupadas por nivel — y vuelve "
              "por la carga asistida.",
    },
    "Texto puro, uma linha por unidade, com accountabilities e competências.": {
        "en-US": "Plain text, one row per unit, with accountabilities and skills.",
        "es": "Texto plano, una fila por unidad, con accountabilities y "
              "competencias.",
    },
    "A estrutura inteira, para outro sistema ler.": {
        "en-US": "The whole structure, for another system to read.",
        "es": "La estructura entera, para que otro sistema la lea.",
    },
    "Desfazer e refazer": {
        "en-US": "Undo and redo",
        "es": "Deshacer y rehacer",
    },
    "Refazer": {
        "en-US": "Redo",
        "es": "Rehacer",
    },
    "Nada a refazer.": {
        "en-US": "Nothing to redo.",
        "es": "Nada que rehacer.",
    },
    "Abrir e dobrar a árvore": {
        "en-US": "Expand and collapse the tree",
        "es": "Abrir y plegar el árbol",
    },
    "Abrir e fechar as faixas": {
        "en-US": "Open and close the bands",
        "es": "Abrir y cerrar las franjas",
    },
    "Abrir todas as faixas": {
        "en-US": "Open every band",
        "es": "Abrir todas las franjas",
    },
    "Fechar todas as faixas": {
        "en-US": "Close every band",
        "es": "Cerrar todas las franjas",
    },
    "Abrir mais um nível": {
        "en-US": "Open one more level",
        "es": "Abrir un nivel más",
    },
    "Fechar um nível": {
        "en-US": "Close one level",
        "es": "Cerrar un nivel",
    },
    "Abrir todos os níveis": {
        "en-US": "Open every level",
        "es": "Abrir todos los niveles",
    },
    "Recolher todos os níveis": {
        "en-US": "Collapse every level",
        "es": "Recoger todos los niveles",
    },
    "{n} equipes · {p} pessoas · profundidade {d} · orientação {orientacao}": {
        "en-US": "{n} teams · {p} people · depth {d} · orientation {orientacao}",
        "es": "{n} equipos · {p} personas · profundidad {d} · orientación {orientacao}",
    },
    "Sem departamento": {
        "en-US": "No department",
        "es": "Sin departamento",
    },
    "{n} pessoa(s)": {
        "en-US": "{n} person(s)",
        "es": "{n} persona(s)",
    },
    "{n} pessoa(s) neste time · a indentação é quem responde a quem": {
        "en-US": "{n} person(s) in this team · indentation shows who reports to whom",
        "es": "{n} persona(s) en este equipo · la sangría muestra quién responde a quién",
    },
    "Responde por ela": {
        "en-US": "Reporting to them",
        "es": "Le responden",
    },
    "{n} pessoa(s) direta(s)": {
        "en-US": "{n} direct report(s)",
        "es": "{n} persona(s) directa(s)",
    },
    "{n} em outro time": {
        "en-US": "{n} in another team",
        "es": "{n} en otro equipo",
    },
    "Times que respondem a esta pessoa:": {
        "en-US": "Teams reporting to this person:",
        "es": "Equipos que responden a esta persona:",
    },
    "Abrir ficha": {
        "en-US": "Open record",
        "es": "Abrir ficha",
    },
    "A edição acontece na visão por pessoa": {
        "en-US": "Editing happens in the by-person view",
        "es": "La edición ocurre en la vista por persona",
    },
    "A equipe é desenhada a partir das pessoas, a cada render — ela não é "
    "gravada e não se edita aqui. Volte à visão por pessoa para alterar a "
    "estrutura.": {
        "en-US": "The team is drawn from the people on every render — it is not "
                 "stored and cannot be edited here. Switch to the by-person "
                 "view to change the structure.",
        "es": "El equipo se dibuja a partir de las personas en cada render — no "
              "se guarda y no se edita aquí. Vuelva a la vista por persona para "
              "cambiar la estructura.",
    },
    "Ação negada: equipe é um desenho que o sistema deriva das pessoas, não "
    "uma unidade gravada. Volte à visão por pessoa para editar a estrutura.": {
        "en-US": "Action denied: a team is a drawing the system derives from "
                 "people, not a stored unit. Switch to the by-person view to "
                 "edit the structure.",
        "es": "Acción denegada: un equipo es un dibujo que el sistema deriva de "
              "las personas, no una unidad guardada. Vuelva a la vista por "
              "persona para editar la estructura.",
    },
    "Manual de uso e panorama do sistema": {
        "en-US": "User manual and system overview",
        "es": "Manual de uso y panorama del sistema",
    },
    "Apresentação de boas-vindas ao organograma": {
        "en-US": "Welcome presentation for the org chart",
        "es": "Presentación de bienvenida al organigrama",
    },
    "+ Novo cargo": {
        "en-US": "+ New job title",
        "es": "+ Nuevo cargo",
    },
    "+ Unidade": {
        "en-US": "+ Unit",
        "es": "+ Unidad",
    },
    "<kbd>+</kbd> <kbd>−</kbd> na alça do card colapsa ou expande a subárvore": {
        "en-US": "<kbd>+</kbd> <kbd>−</kbd> on the card handle collapse or expand the subtree",
        "es": "<kbd>+</kbd> <kbd>−</kbd> en el tirador de la tarjeta contraen o expanden el subárbol",
    },
    "<kbd>0</kbd> ajusta à tela · <kbd>B</kbd> recolhe a gaveta": {
        "en-US": "<kbd>0</kbd> fits to screen · <kbd>B</kbd> collapses the drawer",
        "es": "<kbd>0</kbd> ajusta a la pantalla · <kbd>B</kbd> contrae el panel lateral",
    },
    "<kbd>botão direito</kbd> no card, ações da unidade · no fundo, ações do desenho": {
        "en-US": "<kbd>right-click</kbd> on a card, unit actions · on the "
                 "background, chart actions",
        "es": "<kbd>clic derecho</kbd> en la tarjeta, acciones de la unidad · "
              "en el fondo, acciones del dibujo",
    },
    "<kbd>duplo clique</kbd> no card foca a subárvore · no fundo, reenquadra": {
        "en-US": "<kbd>double-click</kbd> a card focuses its subtree · on the background, refits the view",
        "es": "<kbd>doble clic</kbd> en la tarjeta enfoca el subárbol · en el fondo, reencuadra",
    },
    "<kbd>Enter</kbd> abre este painel · <kbd>Esc</kbd> fecha o menu": {
        "en-US": "<kbd>Enter</kbd> opens this panel · <kbd>Esc</kbd> closes the menu",
        "es": "<kbd>Enter</kbd> abre este panel lateral · <kbd>Esc</kbd> cierra el menú",
    },
    "<kbd>roda</kbd> zoom no ponto do cursor · <kbd>shift</kbd>+<kbd>roda</kbd> desliza": {
        "en-US": "<kbd>wheel</kbd> zooms at the cursor · <kbd>shift</kbd>+<kbd>wheel</kbd> pans",
        "es": "<kbd>rueda</kbd> hace zoom en el punto del cursor · <kbd>shift</kbd>+<kbd>rueda</kbd> desplaza",
    },
    "<kbd>setas</kbd> caminham entre os cards na direção visual": {
        "en-US": "<kbd>arrows</kbd> move between cards in the visual direction",
        "es": "<kbd>flechas</kbd> navegan entre las tarjetas en la dirección visual",
    },
    "A apresentação de 2026 descreve a estrutura pretendida;\n       o cadastro de centros de custo descreve a vigente. Onde discordam:": {
        "en-US": "The 2026 presentation describes the intended structure;\n       the cost center registry describes the current one. Where they disagree:",
        "es": "La presentación de 2026 describe la estructura pretendida;\n       el registro de centros de costo describe la vigente. Donde no coinciden:",
    },
    "A base que sustenta o conjunto.": {
        "en-US": "The base that supports the whole structure.",
        "es": "La base que sostiene el conjunto.",
    },
    "A chave é o par <b>N3 + Departamento</b>: “Managers Team” existe em 80.20, 81.20, 82.20 e 89.20, e “Hardware Design Team” em quatro verticais — nem o código nem o nome identificam sozinhos. O N4 que vem na planilha de pessoas é derivável (N3 é o N4 com o último dígito zerado), e é por essa relação que uma pessoa alcança a sua vertical de negócio.": {
        "en-US": "The key is the pair <b>N3 + Department</b>: “Managers Team” exists under 80.20, 81.20, 82.20 and 89.20, and “Hardware Design Team” in four verticals — neither the code nor the name identifies it on its own. The N4 that arrives in the people spreadsheet is derivable (N3 is the N4 with the last digit zeroed), and it is through that relation that a person reaches their business vertical.",
        "es": "La clave es el par <b>N3 + Departamento</b>: “Managers Team” existe en 80.20, 81.20, 82.20 y 89.20, y “Hardware Design Team” en cuatro verticales; ni el código ni el nombre identifican por sí solos. El N4 que viene en la hoja de cálculo de personas es derivable (N3 es el N4 con el último dígito en cero), y es por esa relación que una persona se vincula a su vertical de negocio.",
    },
    "A cor é um <b>token</b>, não um valor: o tema escuro precisa de contrapartida para cada uma, e digitar hexadecimal furaria a paleta institucional e o contraste. No escuro a leitura inverte — o nível mais sênior vira o tom mais claro, senão o grafite da diretoria some dentro do card (1,1:1).": {
        "en-US": "The color is a <b>token</b>, not a value: the dark theme needs a counterpart for each one, and typing a hex code would break the institutional palette and the contrast. In dark the reading inverts — the most senior level becomes the lightest tone, otherwise the Executive graphite vanishes inside the card (1.1:1).",
        "es": "El color es un <b>token</b>, no un valor: el tema oscuro necesita una contraparte para cada uno, y escribir un hexadecimal rompería la paleta institucional y el contraste. En oscuro la lectura se invierte: el nivel más sénior pasa a ser el tono más claro, si no, el grafito de la dirección desaparece dentro de la tarjeta (1,1:1).",
    },
    "a planilha não tem nenhuma linha de colaborador": {
        "en-US": "the spreadsheet has no employee rows",
        "es": "la hoja de cálculo no tiene ninguna fila de colaborador",
    },
    "a preencher": {
        "en-US": "to fill in",
        "es": "por completar",
    },
    "A razão da estrutura: tudo abaixo existe para atendê-lo.": {
        "en-US": "The reason the structure exists: everything below it is there to serve the customer.",
        "es": "La razón de la estructura: todo lo que está debajo existe para atenderlo.",
    },
    "A3 paisagem em uma folha, vetorial e pesquisável.": {
        "en-US": "A3 landscape on a single sheet, vector and searchable.",
        "es": "A3 horizontal en una hoja, vectorial y con texto buscable.",
    },
    "Abrir na gaveta": {
        "en-US": "Open in drawer",
        "es": "Abrir en el panel lateral",
    },
    "Accountabilities": {
        "en-US": "Accountabilities",
        "es": "Accountabilities",
    },
    "Coluna que você apagar do arquivo não é lida: dá para devolver só as colunas que quer atualizar. A coluna Accountabilities carrega as próprias; as delegadas o sistema deriva das equipes dos reportes diretos a cada carga.": {
        "en-US": "A column you delete from the file is not read: you can send "
                 "back only the columns you want to update. The Accountabilities "
                 "column carries the own ones; the delegated ones the system "
                 "derives from the teams of the direct reports on every load.",
        "es": "Una columna que usted borre del archivo no se lee: puede devolver "
              "sólo las columnas que quiera actualizar. La columna "
              "Accountabilities lleva las propias; las delegadas el sistema las "
              "deriva de los equipos de los reportes directos en cada carga.",
    },
    "A aba ORG volta pela carga assistida, em Configurações › Carga de dados: as colunas são exatamente as que o leitor espera. A aba Organograma é leitura — o que se editar nela não é lido de volta.": {
        "en-US": "The ORG tab goes back through the assisted load, under Settings › Data load: the columns are exactly the ones the reader expects. The Org chart tab is for reading — anything edited there is not read back.",
        "es": "La hoja ORG vuelve por la carga asistida, en Configuración › Carga de datos: las columnas son exactamente las que el lector espera. La hoja Organigrama es de lectura — lo que se edite allí no se lee de vuelta.",
    },
    "Atenção: se este arquivo saiu com filtro, quem ficou de fora aparece como ausente na planilha ao reimportar. A opção de remover ausentes nasce desmarcada, mas confira o passo 2.": {
        "en-US": "Heads-up: if this file was exported with a filter on, everyone left out shows up as missing from the spreadsheet on re-import. The remove-missing option starts unchecked, but do check step 2.",
        "es": "Atención: si este archivo salió con un filtro activo, quien quedó fuera aparece como ausente en la hoja al reimportar. La opción de eliminar ausentes nace desmarcada, pero revise el paso 2.",
    },
    "Accountabilities no card": {
        "en-US": "Accountabilities on the card",
        "es": "Accountabilities en la tarjeta",
    },
    "accountability delegada": {
        "en-US": "delegated accountability",
        "es": "accountability delegada",
    },
    "Adiciona uma unidade subordinada à raiz da vista": {
        "en-US": "Adds a unit reporting to the root of this view",
        "es": "Agrega una unidad subordinada a la raíz de la vista",
    },
    "Adicionar subordinado": {
        "en-US": "Add direct report",
        "es": "Agregar subordinado",
    },
    "Administrador": {
        "en-US": "Administrator",
        "es": "Administrador",
    },
    "Afastar": {
        "en-US": "Zoom out",
        "es": "Alejar",
    },
    "Ajustar à largura": {
        "en-US": "Fit to width",
        "es": "Ajustar al ancho",
    },
    "Ajustar à tela": {
        "en-US": "Fit to screen",
        "es": "Ajustar a la pantalla",
    },
    "Ajustar à tela (tecla 0)": {
        "en-US": "Fit to screen (press 0)",
        "es": "Ajustar a la pantalla (tecla 0)",
    },
    "Altera unidades dentro da subárvore de escopo (SEC-03).": {
        "en-US": "Edits units within the scoped subtree (SEC-03).",
        "es": "Modifica unidades dentro del subárbol de alcance (SEC-03).",
    },
    "alterados": {
        "en-US": "changed",
        "es": "modificados",
    },
    "Alterados": {
        "en-US": "Changed",
        "es": "Modificados",
    },
    "Alterna entre pirâmide invertida e convencional": {
        "en-US": "Switches between inverted and conventional pyramid",
        "es": "Alterna entre pirámide invertida y convencional",
    },
    "Analisar": {
        "en-US": "Analyze",
        "es": "Analizar",
    },
    "Aparece no cabeçalho do desenho, no SVG exportado e no PDF.": {
        "en-US": "Shows in the chart header, in the exported SVG and in the PDF.",
        "es": "Aparece en el encabezado del diagrama, en el SVG exportado y en el PDF.",
    },
    "Aparência": {
        "en-US": "Appearance",
        "es": "Apariencia",
    },
    "Aparência do card atualizada.": {
        "en-US": "Card appearance updated.",
        "es": "Apariencia de la tarjeta actualizada.",
    },
    "Aplicar": {
        "en-US": "Apply",
        "es": "Aplicar",
    },
    "Aplicar a carga? A operação entra no ledger e pode ser desfeita uma vez.": {
        "en-US": "Apply the load? The operation goes into the ledger and can be undone once.",
        "es": "¿Aplicar la carga? La operación entra en el ledger y se puede deshacer una vez.",
    },
    "Aplicar e registrar": {
        "en-US": "Apply and log",
        "es": "Aplicar y registrar",
    },
    "Aplicar perfil": {
        "en-US": "Apply role",
        "es": "Aplicar perfil",
    },
    "Aplicar às unidades": {
        "en-US": "Apply to units",
        "es": "Aplicar a las unidades",
    },
    "Apoio": {
        "en-US": "Support",
        "es": "Apoyo",
    },
    "apresentação:": {
        "en-US": "presentation:",
        "es": "presentación:",
    },
    "Aproximar": {
        "en-US": "Zoom in",
        "es": "Acercar",
    },
    "Ativa": {
        "en-US": "Active",
        "es": "Activa",
    },
    "Ativo": {
        "en-US": "Active",
        "es": "Activo",
    },
    "Ator": {
        "en-US": "Actor",
        "es": "Actor",
    },
    "Atualização incremental a partir da planilha, em três passos. Nada é escrito antes do passo 3.": {
        "en-US": "Incremental update from the spreadsheet, in three steps. Nothing is written before step 3.",
        "es": "Actualización incremental a partir de la hoja de cálculo, en tres pasos. Nada se escribe antes del paso 3.",
    },
    "ausentes na planilha": {
        "en-US": "missing from the spreadsheet",
        "es": "ausentes en la hoja",
    },
    "Ausentes na planilha": {
        "en-US": "Missing from the spreadsheet",
        "es": "Ausentes en la hoja de cálculo",
    },
    "Ação": {
        "en-US": "Action",
        "es": "Acción",
    },
    "Ação negada: só o operador do sistema (superadmin) baixa o banco.": {
        "en-US": "Action denied: only the system operator (superadmin) can download the database.",
        "es": "Acción denegada: solo el operador del sistema (superadmin) descarga la base de datos.",
    },
    "exportação SQL (carga do banco)": {
        "en-US": "SQL export (database load)",
        "es": "exportación SQL (carga de la base de datos)",
    },
    "Ação negada: fora do escopo de edição ({unidade}).": {
        "en-US": "Action denied: outside the editing scope ({unidade}).",
        "es": "Acción denegada: fuera del alcance de edición ({unidade}).",
    },
    "Ação negada: o perfil {perfil} não altera a estrutura. Exige {exigido} ou superior.": {
        "en-US": "Action denied: the {perfil} role cannot change the structure. Requires {exigido} or higher.",
        "es": "Acción denegada: el perfil {perfil} no modifica la estructura. Requiere {exigido} o superior.",
    },
    "Ações da unidade": {
        "en-US": "Unit actions",
        "es": "Acciones de la unidad",
    },
    "Baixar planilha-modelo": {
        "en-US": "Download template",
        "es": "Descargar plantilla",
    },
    "Busca livre": {
        "en-US": "Free-text search",
        "es": "Búsqueda libre",
    },
    "buscar pessoa, cargo, e-mail, CC…": {
        "en-US": "search name, job title, email, CC…",
        "es": "buscar persona, cargo, correo, CC…",
    },
    "Business Units": {
        "en-US": "Business Units",
        "es": "Business Units",
    },
    "cadastro de centros de custo": {
        "en-US": "cost center registry",
        "es": "registro de centros de costo",
    },
    "cadastro de centros de custo restaurado da referência": {
        "en-US": "cost center registry restored from the reference table",
        "es": "registro de centros de costo restaurado desde la tabla de referencia",
    },
    "Cadastro restaurado da tabela de referência.": {
        "en-US": "Registry restored from the reference table.",
        "es": "Registro restaurado desde la tabla de referencia.",
    },
    "Cadastro salvo com {n} linha(s).": {
        "en-US": "Registry saved with {n} row(s).",
        "es": "Registro guardado con {n} fila(s).",
    },
    "campos visíveis do card": {
        "en-US": "visible card fields",
        "es": "campos visibles de la tarjeta",
    },
    "Cancelar": {
        "en-US": "Cancel",
        "es": "Cancelar",
    },
    "Canvas": {
        "en-US": "Canvas",
        "es": "Canvas",
    },
    "Card do canvas": {
        "en-US": "Canvas card",
        "es": "Tarjeta del canvas",
    },
    "Carga aplicada: {criados} criada(s), {atualizados} atualizada(s), {removidos} removida(s).": {
        "en-US": "Load applied: {criados} created, {atualizados} updated, {removidos} removed.",
        "es": "Carga aplicada: {criados} creada(s), {atualizados} actualizada(s), {removidos} eliminada(s).",
    },
    "carga assistida da planilha": {
        "en-US": "guided load from the spreadsheet",
        "es": "carga asistida desde la hoja de cálculo",
    },
    "Carga de dados": {
        "en-US": "Data load",
        "es": "Carga de datos",
    },
    "Cargo": {
        "en-US": "Job title",
        "es": "Cargo",
    },
    "Cargo / função": {
        "en-US": "Job title / function",
        "es": "Cargo / función",
    },
    "Cargo “{nome}” criado como {nivel}.": {
        "en-US": "Job title “{nome}” created as {nivel}.",
        "es": "Cargo “{nome}” creado como {nivel}.",
    },
    "todos os campos do contrato — coluna que não veio no arquivo não é tocada": {
        "en-US": "every field in the contract — a column absent from the file is left alone",
        "es": "todos los campos del contrato — una columna ausente del archivo no se toca",
    },
    "cargos descobertos a partir da estrutura": {
        "en-US": "job titles discovered from the structure",
        "es": "cargos descubiertos a partir de la estructura",
    },
    "Cargos e níveis": {
        "en-US": "Job titles and levels",
        "es": "Cargos y niveles",
    },
    "Casamento por departamento ou por N3 significa que a planilha de pessoas e o cadastro divergem no nome — os dois são mantidos por gente diferente.": {
        "en-US": "A match by department or by N3 means the people spreadsheet and the registry disagree on the name — the two are maintained by different people.",
        "es": "Coincidir por departamento o por N3 significa que la hoja de cálculo de personas y el registro difieren en el nombre: los mantienen personas distintas.",
    },
    "catalogo de cargos": {
        "en-US": "job title catalog",
        "es": "catálogo de cargos",
    },
    "Catálogo de cargos": {
        "en-US": "Job title catalog",
        "es": "Catálogo de cargos",
    },
    "CC": {
        "en-US": "CC",
        "es": "CC",
    },
    "Centro de custo": {
        "en-US": "Cost center",
        "es": "Centro de costo",
    },
    "centro de custo não resolve para um tipo (Business Unit, Suport Team ou Diretoria)": {
        "en-US": "cost center does not resolve to a type (Business Unit, Suport Team or Executive Team)",
        "es": "el centro de costo no se resuelve a un tipo (Business Unit, Suport Team o Diretoria)",
    },
    "Centros de custo": {
        "en-US": "Cost centers",
        "es": "Centros de costo",
    },
    "centros de custo descobertos a partir da estrutura": {
        "en-US": "cost centers discovered from the structure",
        "es": "centros de costo descubiertos a partir de la estructura",
    },
    "centros de custo. N2 é a vertical, N4 é o CC da equipe. N3 é derivado do N4 pelo cadastro: sai na exportação para orientar a leitura, e é ignorado na carga.": {
        "en-US": "cost centers. N2 is the vertical, N4 is the team's CC. N3 is "
                 "derived from N4 by the register: it comes out in the export to "
                 "guide the reader, and is ignored on load.",
        "es": "centros de costo. N2 es la vertical, N4 es el CC del equipo. N3 se "
              "deriva del N4 por el registro: sale en la exportación para orientar "
              "la lectura, y se ignora en la carga.",
    },
    "ORG-####, gerado pelo sistema. Não invente: quando vem preenchido, é ele que diz de quem é a linha, e por isso trocar nome e e-mail na mesma carga deixa de virar demissão mais admissão. Em branco, o pareamento cai para e-mail e nome.": {
        "en-US": "ORG-####, generated by the system. Do not make one up: when it "
                 "is filled in, it is what says whose row this is, which is why "
                 "changing name and email in the same load stops reading as a "
                 "termination plus a hire. Left blank, matching falls back to "
                 "email and name.",
        "es": "ORG-####, generado por el sistema. No lo invente: cuando viene "
              "completo, es él quien dice de quién es la fila, y por eso cambiar "
              "nombre y correo en la misma carga deja de leerse como baja más "
              "alta. En blanco, el emparejamiento cae a correo y nombre.",
    },
    "rótulo do nível hierárquico, como aparece em Configurações › Cargos e níveis (Diretoria, Gerência, Coordenação, Célula, Área, Apoio). Em branco mantém o nível atual; em linha nova, o sistema deduz do cargo. Valor que não existe no cadastro vira aviso no passo 2 e não é gravado.": {
        "en-US": "label of the hierarchy level, as it appears under Settings › "
                 "Job titles and levels (Board, Management, Coordination, Cell, "
                 "Area, Support). Left blank it keeps the current level; on a new "
                 "row the system infers it from the job title. A value absent from "
                 "the register becomes a warning at step 2 and is not written.",
        "es": "rótulo del nivel jerárquico, tal como aparece en Configuración › "
              "Cargos y niveles (Dirección, Gerencia, Coordinación, Célula, Área, "
              "Apoyo). En blanco mantiene el nivel actual; en una fila nueva el "
              "sistema lo deduce del cargo. Un valor que no existe en el registro "
              "se convierte en aviso en el paso 2 y no se graba.",
    },
    "CLT, PJ ou Consultoria. Em branco mantém o que está gravado — coluna vazia não rebaixa ninguém para CLT.": {
        "en-US": "Employee, Contractor or Consultancy. Left blank it keeps what is "
                 "on record — an empty column does not demote anyone to Employee.",
        "es": "Empleado, Autónomo o Consultoría. En blanco mantiene lo que está "
              "grabado — una columna vacía no rebaja a nadie a Empleado.",
    },
    "quem responde pela unidade, quando o card representa uma área e não uma pessoa. Em branco mantém.": {
        "en-US": "who answers for the unit, when the card stands for an area "
                 "rather than a person. Left blank it keeps the current value.",
        "es": "quién responde por la unidad, cuando la tarjeta representa un área "
              "y no una persona. En blanco mantiene el valor actual.",
    },
    "separadas por vírgula. Em branco mantém — para esvaziar a lista de alguém, use o painel.": {
        "en-US": "comma-separated. Left blank it keeps the current list — to empty "
                 "someone's list, use the panel.",
        "es": "separadas por coma. En blanco mantiene la lista actual — para vaciar "
              "la lista de alguien, use el panel.",
    },
    "separadas por barra vertical (|). São as próprias. As delegadas o sistema deriva das equipes dos reportes diretos a cada carga e não se editam aqui. Em branco mantém.": {
        "en-US": "separated by a vertical bar (|). These are the own ones. The "
                 "delegated ones the system derives from the teams of the direct "
                 "reports on every load, and they are not edited here. Left blank "
                 "it keeps the current list.",
        "es": "separadas por barra vertical (|). Son las propias. Las delegadas el "
              "sistema las deriva de los equipos de los reportes directos en cada "
              "carga y no se editan aquí. En blanco mantiene la lista actual.",
    },
    "As duas colunas em grafite são obrigatórias; as demais, quando ficam em branco, seguem a regra descrita ao lado de cada uma. Coluna que você apagar do arquivo simplesmente não é lida — dá para mandar só as colunas que quer atualizar.": {
        "en-US": "The two graphite columns are required; the rest, when left blank, "
                 "follow the rule described beside each one. A column you delete "
                 "from the file is simply not read — you can send only the columns "
                 "you want to update.",
        "es": "Las dos columnas en grafito son obligatorias; las demás, cuando "
              "quedan en blanco, siguen la regla descrita al lado de cada una. Una "
              "columna que usted borre del archivo simplemente no se lee — puede "
              "enviar sólo las columnas que quiera actualizar.",
    },
    "Tempo de empresa": {
        "en-US": "Tenure",
        "es": "Antigüedad",
    },
    "Calculado da data de admissão, na mesma régua do RH: dias corridos sobre 365.": {
        "en-US": "Worked out from the hire date, on the same yardstick HR uses: calendar days over 365.",
        "es": "Calculado a partir de la fecha de ingreso, con la misma regla de RR. HH.: días corridos sobre 365.",
    },
    "os números são do recorte que está na tela.": {
        "en-US": "the numbers are for the slice on screen.",
        "es": "los números son del recorte que está en la pantalla.",
    },
    "média": {
        "en-US": "mean",
        "es": "media",
    },
    "mediana": {
        "en-US": "median",
        "es": "mediana",
    },
    "anos somados": {
        "en-US": "years combined",
        "es": "años sumados",
    },
    "sem data": {
        "en-US": "no date",
        "es": "sin fecha",
    },
    "a começar": {
        "en-US": "starting soon",
        "es": "por empezar",
    },
    "Anos somados é o que a empresa perde de uma vez se todos saírem no mesmo dia.": {
        "en-US": "Years combined is what the company loses at once if everyone leaves on the same day.",
        "es": "Años sumados es lo que la empresa pierde de una vez si todos se van el mismo día.",
    },
    "Distribuição": {
        "en-US": "Distribution",
        "es": "Distribución",
    },
    "Faixa": {
        "en-US": "Band",
        "es": "Franja",
    },
    "Proporção": {
        "en-US": "Share",
        "es": "Proporción",
    },
    "Por vínculo": {
        "en-US": "By contract type",
        "es": "Por régimen",
    },
    "Por nível": {
        "en-US": "By level",
        "es": "Por nivel",
    },
    "Por departamento": {
        "en-US": "By department",
        "es": "Por departamento",
    },
    "Quem está hoje, pelo ano em que entrou": {
        "en-US": "Who is here today, by the year they joined",
        "es": "Quién está hoy, por el año en que entró",
    },
    "Não é histórico de contratação: quem saiu não está aqui. A linha diz quantos dos que estão hoje entraram naquele ano.": {
        "en-US": "This is not a hiring history: people who left are not here. The row says how many of those here today joined in that year.",
        "es": "No es un histórico de contratación: quien salió no está aquí. La fila dice cuántos de los que están hoy entraron en aquel año.",
    },
    "Ano": {
        "en-US": "Year",
        "es": "Año",
    },
    "Onde a casa é mais nova": {
        "en-US": "Where the house is newest",
        "es": "Dónde la casa es más nueva",
    },
    "Equipes diretas com pelo menos {n} pessoas, da média mais baixa para a mais alta. Uma equipe inteira abaixo de um ano é um time sem memória — pode ser crescimento, pode ser rotatividade, e as duas leituras pedem ação diferente.": {
        "en-US": "Direct teams with at least {n} people, from the lowest mean to the highest. A whole team under one year is a team with no memory — it may be growth, it may be turnover, and the two readings call for different action.",
        "es": "Equipos directos con al menos {n} personas, de la media más baja a la más alta. Un equipo entero por debajo de un año es un equipo sin memoria — puede ser crecimiento, puede ser rotación, y las dos lecturas piden acciones distintas.",
    },
    "Média": {
        "en-US": "Mean",
        "es": "Media",
    },
    "Mediana": {
        "en-US": "Median",
        "es": "Mediana",
    },
    "Até 1 ano": {
        "en-US": "Up to 1 year",
        "es": "Hasta 1 año",
    },
    "Grupo": {
        "en-US": "Group",
        "es": "Grupo",
    },
    "Mais de 10": {
        "en-US": "Over 10",
        "es": "Más de 10",
    },
    "1 a 3 anos": {
        "en-US": "1 to 3 years",
        "es": "1 a 3 años",
    },
    "3 a 5 anos": {
        "en-US": "3 to 5 years",
        "es": "3 a 5 años",
    },
    "5 a 10 anos": {
        "en-US": "5 to 10 years",
        "es": "5 a 10 años",
    },
    "Mais de 10 anos": {
        "en-US": "Over 10 years",
        "es": "Más de 10 años",
    },
    "A começar": {
        "en-US": "Starting soon",
        "es": "Por empezar",
    },
    "Sem data": {
        "en-US": "No date",
        "es": "Sin fecha",
    },
    "Data de admissão": {
        "en-US": "Hire date",
        "es": "Fecha de ingreso",
    },
    "Data de admissão adiante de hoje: ainda a começar.": {
        "en-US": "Hire date is in the future: not started yet.",
        "es": "Fecha de ingreso posterior a hoy: aún por empezar.",
    },
    "Escrever para {quem}": {
        "en-US": "Write to {quem}",
        "es": "Escribir a {quem}",
    },
    "Inativo não some do organograma: afastamento e desligamento em curso são justamente o que alguém precisa ver.": {
        "en-US": "Inactive does not disappear from the org chart: leave and an exit in progress are exactly what someone needs to see.",
        "es": "Inactivo no desaparece del organigrama: licencia y baja en curso son justamente lo que alguien necesita ver.",
    },
    "Não aplicável": {
        "en-US": "Not applicable",
        "es": "No aplicable",
    },
    "Situação": {
        "en-US": "Status",
        "es": "Situación",
    },
    "Status": {
        "en-US": "Status",
        "es": "Estado",
    },
    "{anos} ano(s) de casa · {faixa}": {
        "en-US": "{anos} year(s) of tenure · {faixa}",
        "es": "{anos} año(s) de antigüedad · {faixa}",
    },
    "— não declarada": {
        "en-US": "— not declared",
        "es": "— no declarada",
    },
    "Inativo": {
        "en-US": "Inactive",
        "es": "Inactivo",
    },
    "Colunas": {
        "en-US": "Columns",
        "es": "Columnas",
    },
    "Admissão": {
        "en-US": "Hire date",
        "es": "Ingreso",
    },
    "Tempo de casa": {
        "en-US": "Tenure",
        "es": "Antigüedad",
    },
    "Menos de {n} pessoas com data: a mediana diria mais sobre o acaso que sobre o grupo.": {
        "en-US": "Fewer than {n} people with a date: the median would say more about chance than about the group.",
        "es": "Menos de {n} personas con fecha: la mediana diría más sobre el azar que sobre el grupo.",
    },
    "{n} pessoa(s) na equipe direta · {novatos} com menos de um ano": {
        "en-US": "{n} person(s) in the direct team · {novatos} under one year",
        "es": "{n} persona(s) en el equipo directo · {novatos} con menos de un año",
    },
    "{n} pessoa(s) que estão hoje entraram em {ano}": {
        "en-US": "{n} of the people here today joined in {ano}",
        "es": "{n} de las personas que están hoy entraron en {ano}",
    },
    "{rotulo}: {n} de {total} pessoas ({pct} %)": {
        "en-US": "{rotulo}: {n} of {total} people ({pct} %)",
        "es": "{rotulo}: {n} de {total} personas ({pct} %)",
    },
    "{rotulo}: {n} pessoa(s) · de {min} a {max} anos de casa": {
        "en-US": "{rotulo}: {n} person(s) · from {min} to {max} years of tenure",
        "es": "{rotulo}: {n} persona(s) · de {min} a {max} años de antigüedad",
    },
    "{n} centro(s) de custo ganharam o N5 que faltava: {quais}": {
        "en-US": "{n} cost center(s) got the N5 they were missing: {quais}",
        "es": "{n} centro(s) de costo recibieron el N5 que faltaba: {quais}",
    },
    "{n} centro(s) de custo têm N5 diferente do que a planilha declara — o cadastro foi mantido: {quais}": {
        "en-US": "{n} cost center(s) have an N5 different from what the spreadsheet declares — the register was kept: {quais}",
        "es": "{n} centro(s) de costo tienen un N5 distinto del que declara la hoja — se mantuvo el registro: {quais}",
    },
    "{n} combinação(ões) de N3 e departamento aparecem com mais de um N5 na planilha, e por isso não foram preenchidas: {quais}": {
        "en-US": "{n} N3-and-department combination(s) show up with more than one N5 in the spreadsheet, and were therefore left unfilled: {quais}",
        "es": "{n} combinación(es) de N3 y departamento aparecen con más de un N5 en la hoja, y por eso no se completaron: {quais}",
    },
    "Especialista": {
        "en-US": "Specialist",
        "es": "Especialista",
    },
    "Estágio": {
        "en-US": "Internship",
        "es": "Pasantía",
    },
    "RPA": {
        "en-US": "RPA",
        "es": "RPA",
    },
    "{n} gestor(es) vieram com o nome abreviado e foram casados pelo nome completo: {quais}": {
        "en-US": "{n} manager(s) came in with a shortened name and were matched "
                 "by their full name: {quais}",
        "es": "{n} jefe(s) vinieron con el nombre abreviado y se emparejaron "
              "por el nombre completo: {quais}",
    },
    "{n} nome(s) aparecem mais de uma vez, aqui ou na estrutura: sem e-mail ou código não dá para saber de quem é a linha, e ela entra como pessoa nova. {quais}": {
        "en-US": "{n} name(s) appear more than once, here or in the structure: "
                 "without an email or a code there is no telling whose row it "
                 "is, and it comes in as a new person. {quais}",
        "es": "{n} nombre(s) aparecen más de una vez, aquí o en la estructura: "
              "sin correo ni código no hay cómo saber de quién es la fila, y "
              "entra como persona nueva. {quais}",
    },
    "{n} linha(s) com {coluna} que não existe no cadastro — o campo fica como está: {quais}": {
        "en-US": "{n} row(s) carry a {coluna} that is not in the register — the "
                 "field is left as it is: {quais}",
        "es": "{n} fila(s) con {coluna} que no existe en el registro — el campo "
              "queda como está: {quais}",
    },
    "Cinza": {
        "en-US": "Gray",
        "es": "Gris",
    },
    "Cinza claro": {
        "en-US": "Light gray",
        "es": "Gris claro",
    },
    "Claro": {
        "en-US": "Light",
        "es": "Claro",
    },
    "Classificação": {
        "en-US": "Classification",
        "es": "Clasificación",
    },
    "Cliente": {
        "en-US": "Customer",
        "es": "Cliente",
    },
    "Clique em um card para editar. Botão direito abre as ações da unidade.": {
        "en-US": "Click a card to edit it. Right-click opens the unit's actions.",
        "es": "Haga clic en una tarjeta para editar. El clic derecho abre las acciones de la unidad.",
    },
    "Colaborador": {
        "en-US": "Employee",
        "es": "Colaborador",
    },
    "Colapsar subárvore": {
        "en-US": "Collapse subtree",
        "es": "Contraer subárbol",
    },
    "Colunas esperadas:": {
        "en-US": "Expected columns:",
        "es": "Columnas esperadas:",
    },
    "Com a árvore inteira aberta o desenho passa de 59 000 px de largura. Abrir 1 nível põe o topo da estrutura na tela em escala legível.": {
        "en-US": "With the whole tree expanded the chart runs past 59,000 px wide. Opening 1 level puts the top of the structure on screen at a readable scale.",
        "es": "Con todo el árbol abierto, el diagrama supera los 59 000 px de ancho. Abrir 1 nivel deja la cima de la estructura en pantalla a una escala legible.",
    },
    "Como cada unidade encontrou o seu centro de custo:": {
        "en-US": "How each unit found its cost center:",
        "es": "Cómo cada unidad encontró su centro de costo:",
    },
    "como preencher": {
        "en-US": "how to fill in",
        "es": "cómo completar",
    },
    "Competências": {
        "en-US": "Skills",
        "es": "Competencias",
    },
    "Conectados pelo sucesso": {
        "en-US": "Connected by success",
        "es": "Conectados por el éxito",
    },
    "Conferir o que muda": {
        "en-US": "Review what changes",
        "es": "Revisar qué cambia",
    },
    "configuração geral": {
        "en-US": "general settings",
        "es": "configuración general",
    },
    "Configuração salva.": {
        "en-US": "Settings saved.",
        "es": "Configuración guardada.",
    },
    "Configurações": {
        "en-US": "Settings",
        "es": "Configuración",
    },
    "Configurações do sistema": {
        "en-US": "System settings",
        "es": "Configuración del sistema",
    },
    "convencional": {
        "en-US": "conventional",
        "es": "convencional",
    },
    "Convencional — liderança no topo": {
        "en-US": "Conventional — leadership at the top",
        "es": "Convencional — liderazgo en la cima",
    },
    "Coordenação": {
        "en-US": "Coordination",
        "es": "Coordinación",
    },
    "Cor": {
        "en-US": "Color",
        "es": "Color",
    },
    "cp": {
        "en-US": "cp",
        "es": "cp",
    },
    "Criar": {
        "en-US": "Create",
        "es": "Crear",
    },
    "CSV": {
        "en-US": "CSV",
        "es": "CSV",
    },
    "Célula": {
        "en-US": "Cell",
        "es": "Célula",
    },
    "Código": {
        "en-US": "Code",
        "es": "Código",
    },
    "Código da unidade": {
        "en-US": "Unit code",
        "es": "Código de la unidad",
    },
    "de": {
        "en-US": "of",
        "es": "de",
    },
    "declarada na apresentação, ausente no cadastro de centros de custo": {
        "en-US": "declared in the presentation, missing from the cost center registry",
        "es": "declarada en la presentación, ausente en el registro de centros de costo",
    },
    "Departamento": {
        "en-US": "Department",
        "es": "Departamento",
    },
    "Derivadas do cadastro. Alimentam o filtro do canvas e da tabela — é por elas que se lê “toda a engenharia”, e não por 80.0.": {
        "en-US": "Derived from the registry. They feed the canvas and table filters — they are how you read “all of engineering” instead of 80.0.",
        "es": "Derivadas del registro. Alimentan el filtro del canvas y de la tabla: por ellas se lee “toda la ingeniería”, y no por 80.0.",
    },
    "Descarta a estrutura atual e refaz a carga da planilha de referência. Diferente da carga incremental: aqui as edições feitas no canvas se perdem.": {
        "en-US": "Discards the current structure and reloads from the reference spreadsheet. Unlike the incremental load: here the edits made on the canvas are lost.",
        "es": "Descarta la estructura actual y rehace la carga desde la hoja de cálculo de referencia. A diferencia de la carga incremental, aquí se pierden las ediciones hechas en el canvas.",
    },
    "Descartar": {
        "en-US": "Discard",
        "es": "Descartar",
    },
    "Descendentes não aparecem na lista: a guarda\n        de ciclo recusaria o movimento (RF-02).": {
        "en-US": "Descendants are not listed: the cycle guard\n        would reject the move (RF-02).",
        "es": "Los descendientes no aparecen en la lista: la guarda\n        de ciclo rechazaría el movimiento (RF-02).",
    },
    "Descobrir da estrutura": {
        "en-US": "Discover from structure",
        "es": "Descubrir desde la estructura",
    },
    "Desfazer": {
        "en-US": "Undo",
        "es": "Deshacer",
    },
    "Detalhes da unidade": {
        "en-US": "Unit details",
        "es": "Detalles de la unidad",
    },
    "Diretoria": {
        "en-US": "Executive",
        "es": "Dirección",
    },
    "Diretoria Executiva": {
        "en-US": "Executive Team",
        "es": "Dirección Ejecutiva",
    },
    "Disponível no Canvas": {
        "en-US": "Available in Canvas",
        "es": "Disponible en Canvas",
    },
    "Divergências entre a apresentação e o cadastro": {
        "en-US": "Discrepancies between the presentation and the registry",
        "es": "Discrepancias entre la presentación y el registro",
    },
    "Duplicar": {
        "en-US": "Duplicate",
        "es": "Duplicar",
    },
    "duplicação pelo canvas": {
        "en-US": "duplication from the canvas",
        "es": "duplicación desde el canvas",
    },
    "E-mail": {
        "en-US": "Email",
        "es": "Correo",
    },
    "E-mail corporativo": {
        "en-US": "Work email",
        "es": "Correo corporativo",
    },
    "ed": {
        "en-US": "ed",
        "es": "ed",
    },
    "Editar dados": {
        "en-US": "Edit details",
        "es": "Editar datos",
    },
    "Editor": {
        "en-US": "Editor",
        "es": "Editor",
    },
    "edição pelo painel": {
        "en-US": "edit from the panel",
        "es": "edición desde el panel lateral",
    },
    "Entra no catálogo com o nível que você escolher. Criar não reclassifica ninguém — quem reescreve o nível das unidades é <b>Aplicar às unidades</b>.": {
        "en-US": "It enters the catalog with the level you choose. Creating reclassifies nobody — what rewrites the level on the units is <b>Apply to units</b>.",
        "es": "Entra en el catálogo con el nivel que elija. Crear no reclasifica a nadie: lo que reescribe el nivel de las unidades es <b>Aplicar a las unidades</b>.",
    },
    "Enviar planilha": {
        "en-US": "Upload spreadsheet",
        "es": "Subir hoja de cálculo",
    },
    "equipe. Aparece no card e alimenta o filtro.": {
        "en-US": "team. Shows on the card and feeds the filter.",
        "es": "equipo. Aparece en la tarjeta y alimenta el filtro.",
    },
    "Escolha um departamento para ver quem o compõe.": {
        "en-US": "Pick a department to see who's in it.",
        "es": "Elija un departamento para ver quiénes lo integran.",
    },
    "Escolher percentual": {
        "en-US": "Choose zoom percentage",
        "es": "Elegir porcentaje",
    },
    "Escuro": {
        "en-US": "Dark",
        "es": "Oscuro",
    },
    "Espaço entre irmãos": {
        "en-US": "Space between siblings",
        "es": "Espacio entre hermanos",
    },
    "Esta é a unidade raiz.": {
        "en-US": "This is the root unit.",
        "es": "Esta es la unidad raíz.",
    },
    "Estrutura": {
        "en-US": "Structure",
        "es": "Estructura",
    },
    "Estrutura em ordem lógica": {
        "en-US": "Structure in logical order",
        "es": "Estructura en orden lógico",
    },
    "Estrutura GPlanSiS|Peoples": {
        "en-US": "GPlanSiS|Peoples structure",
        "es": "Estructura GPlanSiS|Peoples",
    },
    "Estrutura institucional": {
        "en-US": "Company structure",
        "es": "Estructura institucional",
    },
    "Estrutura recarregada da planilha.": {
        "en-US": "Structure reloaded from the spreadsheet.",
        "es": "Estructura recargada desde la hoja de cálculo.",
    },
    "Estão no cadastro e nenhuma pessoa da estrutura caiu nelas. Pode ser equipe desativada — ou divergência de grafia com a planilha.": {
        "en-US": "They are in the registry and nobody in the structure landed on them. Could be a deactivated team — or a spelling mismatch with the spreadsheet.",
        "es": "Están en el registro y ninguna persona de la estructura cayó en ellas. Puede ser un equipo desactivado, o una diferencia de grafía con la hoja de cálculo.",
    },
    "ex.: Coordenador de Automação": {
        "en-US": "e.g. Automation Coordinator",
        "es": "ej.: Coordinador de Automatización",
    },
    "exato": {
        "en-US": "exact",
        "es": "exacto",
    },
    "Excluir unidade": {
        "en-US": "Delete unit",
        "es": "Eliminar unidad",
    },
    "exclusão pelo canvas": {
        "en-US": "deletion from the canvas",
        "es": "eliminación desde el canvas",
    },
    "Exclusão recusada: a raiz não pode ser removida.": {
        "en-US": "Deletion rejected: the root cannot be removed.",
        "es": "Eliminación rechazada: la raíz no se puede eliminar.",
    },
    "Expandir até": {
        "en-US": "Expand to",
        "es": "Expandir hasta",
    },
    "Expandir o painel": {
        "en-US": "Expand the panel",
        "es": "Expandir el panel lateral",
    },
    "Expandir subárvore": {
        "en-US": "Expand subtree",
        "es": "Expandir subárbol",
    },
    "exportação CSV": {
        "en-US": "CSV export",
        "es": "exportación CSV",
    },
    "exportação JSON": {
        "en-US": "JSON export",
        "es": "exportación JSON",
    },
    "exportação PDF A3": {
        "en-US": "A3 PDF export",
        "es": "exportación PDF A3",
    },
    "exportação SVG": {
        "en-US": "SVG export",
        "es": "exportación SVG",
    },
    "exportação XLSX": {
        "en-US": "XLSX export",
        "es": "exportación XLSX",
    },
    "exportação Painel RH (XLSX)": {
        "en-US": "HR Dashboard export (XLSX)",
        "es": "exportación Panel RR. HH. (XLSX)",
    },
    "N5 vinculado ao centro de custo": {
        "en-US": "N5 linked to the cost center",
        "es": "N5 vinculado al centro de costos",
    },
    # --- One-on-One (1:1 / PRM) ---
    "One-on-One": {"en-US": "One-on-One", "es": "One-on-One"},
    "One-on-One — 1:1 e desenvolvimento": {
        "en-US": "One-on-One — 1:1 and development",
        "es": "One-on-One — 1:1 y desarrollo"},
    "Metodologia FUP — acompanhamento de conversas 1:1": {
        "en-US": "FUP methodology — 1:1 conversation follow-up",
        "es": "Metodología FUP — seguimiento de conversaciones 1:1"},
    "Cada 1:1 é privado: só você, a pessoa e o RH/compliance leem. A cadeia de gestão acima não vê.": {
        "en-US": "Each 1:1 is private: only you, the person and HR/compliance can read it. The management chain above cannot.",
        "es": "Cada 1:1 es privado: solo usted, la persona y RR. HH./compliance lo leen. La cadena de gestión superior no."},
    "Você tem acesso de RH: vê os 1:1 de todos.": {
        "en-US": "You have HR access: you see everyone's 1:1s.",
        "es": "Tiene acceso de RR. HH.: ve los 1:1 de todos."},
    "Minha equipe": {"en-US": "My team", "es": "Mi equipo"},
    "1:1 atrasados": {"en-US": "Overdue 1:1s", "es": "1:1 atrasados"},
    "Sem 1:1 ainda": {"en-US": "No 1:1 yet", "es": "Sin 1:1 aún"},
    "Conversas registradas": {"en-US": "Conversations recorded", "es": "Conversaciones registradas"},
    "Você não tem liderados diretos para conduzir 1:1 por aqui.": {
        "en-US": "You have no direct reports to run 1:1s here.",
        "es": "No tiene subordinados directos para 1:1 aquí."},
    "atrasado": {"en-US": "overdue", "es": "atrasado"},
    "sem 1:1": {"en-US": "no 1:1", "es": "sin 1:1"},
    "última": {"en-US": "last", "es": "última"},
    "próxima": {"en-US": "next", "es": "próxima"},
    "nenhuma conversa ainda": {"en-US": "no conversations yet", "es": "ninguna conversación aún"},
    "conversas": {"en-US": "conversations", "es": "conversaciones"},
    "clima": {"en-US": "mood", "es": "clima"},
    "1:1 indisponível": {"en-US": "1:1 unavailable", "es": "1:1 no disponible"},
    "Este 1:1 é privado dos participantes. Você não faz parte dele.": {
        "en-US": "This 1:1 is private to its participants. You are not part of it.",
        "es": "Este 1:1 es privado de sus participantes. Usted no forma parte de él."},
    "Registrar conversa 1:1": {"en-US": "Record 1:1 conversation", "es": "Registrar conversación 1:1"},
    "Registrar 1:1": {"en-US": "Record 1:1", "es": "Registrar 1:1"},
    "Cadência": {"en-US": "Cadence", "es": "Cadencia"},
    "Como a pessoa está? (1–5)": {"en-US": "How is the person? (1–5)", "es": "¿Cómo está la persona? (1–5)"},
    "Pauta": {"en-US": "Agenda", "es": "Agenda"},
    "Notas da conversa": {"en-US": "Conversation notes", "es": "Notas de la conversación"},
    "Notas": {"en-US": "Notes", "es": "Notas"},
    "Próximos passos (FUP)": {"en-US": "Next steps (FUP)", "es": "Próximos pasos (FUP)"},
    "FUP": {"en-US": "FUP", "es": "FUP"},
    "Histórico de conversas": {"en-US": "Conversation history", "es": "Historial de conversaciones"},
    "Nenhuma conversa registrada ainda.": {
        "en-US": "No conversations recorded yet.", "es": "Ninguna conversación registrada aún."},
    "Conversa 1:1 de “{nome}” registrada.": {
        "en-US": "1:1 conversation for “{nome}” recorded.",
        "es": "Conversación 1:1 de «{nome}» registrada."},
    "Conversa apagada.": {"en-US": "Conversation deleted.", "es": "Conversación eliminada."},
    "Apagar esta conversa 1:1?": {"en-US": "Delete this 1:1 conversation?", "es": "¿Eliminar esta conversación 1:1?"},
    "Você não participa deste 1:1.": {
        "en-US": "You are not a participant in this 1:1.", "es": "Usted no participa de este 1:1."},
    "Pessoa fora do recorte. Nada foi gravado.": {
        "en-US": "Person outside the scope. Nothing was saved.",
        "es": "Persona fuera del recorte. No se guardó nada."},
    "Registro indisponível. Nada foi apagado.": {
        "en-US": "Record unavailable. Nothing was deleted.",
        "es": "Registro no disponible. No se eliminó nada."},
    "1:1 registrado": {"en-US": "1:1 recorded", "es": "1:1 registrado"},
    "1:1 apagado": {"en-US": "1:1 deleted", "es": "1:1 eliminado"},
    "Apagar": {"en-US": "Delete", "es": "Eliminar"},
    # cadências
    "Semanal": {"en-US": "Weekly", "es": "Semanal"},
    "Quinzenal": {"en-US": "Biweekly", "es": "Quincenal"},
    "Mensal": {"en-US": "Monthly", "es": "Mensual"},
    "Trimestral": {"en-US": "Quarterly", "es": "Trimestral"},
    # status (rock / issue / objetivo / missão) e estágios de vida
    "No trilho": {"en-US": "On track", "es": "En rumbo"},
    "Fora do trilho": {"en-US": "Off track", "es": "Fuera de rumbo"},
    "Concluído": {"en-US": "Done", "es": "Concluido"},
    "Aberto": {"en-US": "Open", "es": "Abierto"},
    "Em discussão": {"en-US": "Under discussion", "es": "En discusión"},
    "Resolvido": {"en-US": "Resolved", "es": "Resuelto"},
    "Em risco": {"en-US": "At risk", "es": "En riesgo"},
    "Atingido": {"en-US": "Achieved", "es": "Alcanzado"},
    "Proposta": {"en-US": "Proposed", "es": "Propuesta"},
    "Em andamento": {"en-US": "In progress", "es": "En curso"},
    "Concluída": {"en-US": "Completed", "es": "Concluida"},
    "Parada": {"en-US": "Paused", "es": "Detenida"},
    "Onboarding": {"en-US": "Onboarding", "es": "Onboarding"},
    "Desenvolvimento": {"en-US": "Development", "es": "Desarrollo"},
    "Consolidado": {"en-US": "Established", "es": "Consolidado"},
    "Transição": {"en-US": "Transition", "es": "Transición"},
    "Desligamento": {"en-US": "Offboarding", "es": "Baja"},
    # rótulos de tipo (ROTULO_TIPO)
    "Conversa 1:1": {"en-US": "1:1 conversation", "es": "Conversación 1:1"},
    "Rock": {"en-US": "Rock", "es": "Rock"},
    "Issue": {"en-US": "Issue", "es": "Issue"},
    "Objetivo do trimestre": {"en-US": "Quarter objective", "es": "Objetivo del trimestre"},
    "Missão de evolução": {"en-US": "Growth mission", "es": "Misión de evolución"},
    "Pulso": {"en-US": "Pulse", "es": "Pulso"},
    "Ciclo de vida": {"en-US": "Lifecycle", "es": "Ciclo de vida"},
    # rocks / issues / objetivo / carreira (1B-3)
    "O objetivo principal do trimestre": {
        "en-US": "The main objective for the quarter", "es": "El objetivo principal del trimestre"},
    "Métrica / meta": {"en-US": "Metric / target", "es": "Métrica / meta"},
    "Salvar objetivo": {"en-US": "Save objective", "es": "Guardar objetivo"},
    "Rocks do trimestre": {"en-US": "Rocks for the quarter", "es": "Rocks del trimestre"},
    "Novo rock do trimestre…": {"en-US": "New rock for the quarter…", "es": "Nuevo rock del trimestre…"},
    "Apagar este rock?": {"en-US": "Delete this rock?", "es": "¿Eliminar este rock?"},
    "progresso %": {"en-US": "progress %", "es": "progreso %"},
    "Issues (IDS)": {"en-US": "Issues (IDS)", "es": "Issues (IDS)"},
    "Novo issue…": {"en-US": "New issue…", "es": "Nuevo issue…"},
    "Apagar este issue?": {"en-US": "Delete this issue?", "es": "¿Eliminar este issue?"},
    "Carreira — até onde posso chegar": {
        "en-US": "Career — how far I can go", "es": "Carrera — hasta dónde puedo llegar"},
    "da Conversa de Valor e da Avaliação": {
        "en-US": "from Value Conversation and the Assessment", "es": "de la Conversación de Valor y de la Evaluación"},
    "Trilha de carreira": {"en-US": "Career track", "es": "Ruta de carrera"},
    "Aspiração (Conversa de Valor)": {"en-US": "Aspiration (Value Conversation)", "es": "Aspiración (Conversación de Valor)"},
    "Onde quero chegar (longo prazo)": {
        "en-US": "Where I want to get (long term)", "es": "A dónde quiero llegar (largo plazo)"},
    "O plano para chegar lá": {"en-US": "The plan to get there", "es": "El plan para llegar allí"},
    "Salvar objetivo de carreira": {
        "en-US": "Save career objective", "es": "Guardar objetivo de carrera"},
    "Item salvo.": {"en-US": "Item saved.", "es": "Ítem guardado."},
    "Item apagado.": {"en-US": "Item deleted.", "es": "Ítem eliminado."},
    "One-on-One item salvo": {"en-US": "One-on-One item saved", "es": "Ítem One-on-One guardado"},
    "One-on-One item apagado": {"en-US": "One-on-One item deleted", "es": "Ítem One-on-One eliminado"},
    # PRM — Escuta Ativa, burnout, ciclo de vida (1B-4)
    "Agenda 1:1": {"en-US": "1:1 agenda", "es": "Agenda 1:1"},
    "PRM · Escuta ativa": {"en-US": "PRM · Active listening", "es": "PRM · Escucha activa"},
    "Escuta ativa": {"en-US": "Active listening", "es": "Escucha activa"},
    "Clima médio (1–5)": {"en-US": "Average mood (1–5)", "es": "Clima medio (1–5)"},
    "Alertas de burnout": {"en-US": "Burnout alerts", "es": "Alertas de burnout"},
    "Com pulso registrado": {"en-US": "With pulse recorded", "es": "Con pulso registrado"},
    "No recorte": {"en-US": "In scope", "es": "En el recorte"},
    "sinais derivados — insumo da conversa": {
        "en-US": "derived signals — input for the conversation",
        "es": "señales derivadas — insumo de la conversación"},
    "Nenhum sinal de burnout no recorte. 👏": {
        "en-US": "No burnout signals in scope. 👏", "es": "Sin señales de burnout en el recorte. 👏"},
    "Ninguém com estágio de ciclo de vida marcado.": {
        "en-US": "No one with a lifecycle stage set.",
        "es": "Nadie con etapa de ciclo de vida marcada."},
    "Sentimento": {"en-US": "Feeling", "es": "Sentimiento"},
    "Energia": {"en-US": "Energy", "es": "Energía"},
    "energia": {"en-US": "energy", "es": "energía"},
    "Comentário": {"en-US": "Comment", "es": "Comentario"},
    "nota": {"en-US": "note", "es": "nota"},
    "Sem pulso registrado ainda.": {"en-US": "No pulse recorded yet.", "es": "Sin pulso registrado aún."},
    # sinais de burnout (SINAIS_BURNOUT)
    "1:1 atrasado": {"en-US": "1:1 overdue", "es": "1:1 atrasado"},
    "clima baixo": {"en-US": "low mood", "es": "clima bajo"},
    "span alto": {"en-US": "high span", "es": "span alto"},
    "{n} gestor(es) com span alto (≥{k} liderados) — fator de risco; só vira alerta com sinal de engajamento (1:1 atrasado ou clima baixo).": {
        "en-US": "{n} manager(s) with high span (≥{k} reports) — a risk factor; it only becomes an alert with an engagement signal (1:1 overdue or low mood).",
        "es": "{n} gestor(es) con span alto (≥{k} subordinados) — factor de riesgo; solo se vuelve alerta con una señal de compromiso (1:1 atrasado o clima bajo)."},
    # missões + ponte Conversación de Valor + GPlanSiS|OS (1B-5)
    "Missões de evolução": {"en-US": "Growth missions", "es": "Misiones de evolución"},
    "Missão": {"en-US": "Mission", "es": "Misión"},
    "Nova missão de evolução…": {"en-US": "New growth mission…", "es": "Nueva misión de evolución…"},
    "Sem missões. Gere da Conversa de Valor ou adicione uma.": {
        "en-US": "No missions. Generate from Value Conversation or add one.",
        "es": "Sin misiones. Genere de la Conversación de Valor o añada una."},
    "Apagar esta missão?": {"en-US": "Delete this mission?", "es": "¿Eliminar esta misión?"},
    "Evolução": {"en-US": "Progress", "es": "Evolución"},
    "Gera missões a partir do PDI da Conversa de Valor": {
        "en-US": "Generates missions from the Value Conversation PDI",
        "es": "Genera misiones a partir del PDI de la Conversación de Valor"},
    "Missões (GPlanSiS|OS)": {"en-US": "Missions (GPlanSiS|OS)", "es": "Misiones (GPlanSiS|OS)"},
    "Exporta as missões visíveis no formato do GPlanSiS|OS": {
        "en-US": "Exports the visible missions in GPlanSiS|OS format",
        "es": "Exporta las misiones visibles en formato GPlanSiS|OS"},
    "{n} missão(ões) gerada(s) da Conversa de Valor.": {
        "en-US": "{n} mission(s) generated from Value Conversation.",
        "es": "{n} misión(es) generada(s) de la Conversación de Valor."},
    "Missões geradas da Conversa de Valor": {
        "en-US": "Missions generated from Value Conversation", "es": "Misiones generadas de la Conversación de Valor"},
    "exportação de missões (GPlanSiS|OS)": {
        "en-US": "missions export (GPlanSiS|OS)", "es": "exportación de misiones (GPlanSiS|OS)"},
    "filtrar cargo ou nível…": {
        "en-US": "filter job title or level…",
        "es": "filtrar cargo o nivel…",
    },
    "Filtrar cargos": {
        "en-US": "Filter job titles",
        "es": "Filtrar cargos",
    },
    "filtro ativo": {
        "en-US": "filter active",
        "es": "filtro activo",
    },
    "filtro ativo · {n} unidade(s) correspondente(s)": {
        "en-US": "filter active · {n} matching unit(s)",
        "es": "filtro activo · {n} unidad(es) coincidente(s)",
    },
    "Fita": {
        "en-US": "Ribbon",
        "es": "Cinta",
    },
    "Focar nesta subárvore": {
        "en-US": "Focus this subtree",
        "es": "Enfocar este subárbol",
    },
    "Focar subárvore": {
        "en-US": "Focus subtree",
        "es": "Enfocar subárbol",
    },
    "Folga entre níveis": {
        "en-US": "Gap between levels",
        "es": "Holgura entre niveles",
    },
    "Geometria": {
        "en-US": "Geometry",
        "es": "Geometría",
    },
    "Gerência": {
        "en-US": "Management",
        "es": "Gerencia",
    },
    "Gestor": {
        "en-US": "Manager",
        "es": "Jefe",
    },
    "Gestor Direto": {
        "en-US": "Direct Manager",
        "es": "Jefe Directo",
    },
    "GPlanSiS|Peoples · SPEC-GPLANSIS-ORG-001 · carimbo {hash}": {
        "en-US": "GPlanSiS|Peoples · SPEC-GPLANSIS-ORG-001 · stamp {hash}",
        "es": "GPlanSiS|Peoples · SPEC-GPLANSIS-ORG-001 · sello {hash}",
    },
    "GPlanSiS|Peoples — estrutura exportada": {
        "en-US": "GPlanSiS|Peoples — exported structure",
        "es": "GPlanSiS|Peoples — estructura exportada",
    },
    "GPlanSiS|Peoples — modelo de carga": {
        "en-US": "GPlanSiS|Peoples — load template",
        "es": "GPlanSiS|Peoples — plantilla de carga",
    },
    "GPlanSiS|Peoples — organograma invertido": {
        "en-US": "GPlanSiS|Peoples — inverted org chart",
        "es": "GPlanSiS|Peoples — organigrama invertido",
    },
    "Grafite": {
        "en-US": "Graphite",
        "es": "Grafito",
    },
    "Hash": {
        "en-US": "Hash",
        "es": "Hash",
    },
    "Identidade": {
        "en-US": "Identity",
        "es": "Identidad",
    },
    "Identidade e vista": {
        "en-US": "Identity and view",
        "es": "Identidad y vista",
    },
    "identificador": {
        "en-US": "identifier",
        "es": "identificador",
    },
    "Informe o nome do cargo.": {
        "en-US": "Enter the job title.",
        "es": "Indique el nombre del cargo.",
    },
    "Invertida — liderança na base": {
        "en-US": "Inverted — leadership at the bottom",
        "es": "Invertida — liderazgo en la base",
    },
    "invertida — liderança na base": {
        "en-US": "inverted — leadership at the bottom",
        "es": "invertida — liderazgo en la base",
    },
    "Irrestrito, incluindo configuração e carga de dados.": {
        "en-US": "Unrestricted, including configuration and data loading.",
        "es": "Sin restricciones, incluidas la configuración y la carga de datos.",
    },
    "JSON": {
        "en-US": "JSON",
        "es": "JSON",
    },
    "Entenda sua organização, desenvolva talentos e transforme dados humanos em decisões estratégicas.": {
        "en-US": "Understand your organization, develop talent and turn people data into strategic decisions.",
        "es": "Entienda su organización, desarrolle talentos y convierta datos humanos en decisiones estratégicas.",
    },
    "Laranja": {
        "en-US": "Orange",
        "es": "Naranja",
    },
    "Largura do card (px)": {
        "en-US": "Card width (px)",
        "es": "Ancho de la tarjeta (px)",
    },
    "Ledger append-only com encadeamento SHA-256 (OBJ-05). A verificação percorre\n    a cadeia em O(n) e valida cada elo contra o anterior — não a continuidade de\n    <code>seq</code>, que pode ter lacuna legítima por rollback (RT-06).": {
        "en-US": "Append-only ledger with SHA-256 chaining (OBJ-05). Verification walks the\n    chain in O(n) and validates each link against the previous one — not the\n    continuity of <code>seq</code>, which can have a legitimate gap after a rollback (RT-06).",
        "es": "Ledger append-only con encadenamiento SHA-256 (OBJ-05). La verificación recorre\n    la cadena en O(n) y valida cada eslabón contra el anterior — no la continuidad de\n    <code>seq</code>, que puede tener un hueco legítimo por un rollback (RT-06).",
    },
    "Limpar todos os filtros": {
        "en-US": "Clear all filters",
        "es": "Limpiar todos los filtros",
    },
    "Limpar tudo": {
        "en-US": "Clear all",
        "es": "Limpiar todo",
    },
    "linhas": {
        "en-US": "rows",
        "es": "filas",
    },
    "linhas sem uso": {
        "en-US": "unused rows",
        "es": "filas sin uso",
    },
    "Linhas sem uso": {
        "en-US": "Unused rows",
        "es": "Filas sin uso",
    },
    "LogicalCC": {
        "en-US": "LogicalCC",
        "es": "LogicalCC",
    },
    "Lê o organograma, filtra e exporta. Não altera nada.": {
        "en-US": "Reads the org chart, filters and exports. Changes nothing.",
        "es": "Lee el organigrama, filtra y exporta. No modifica nada.",
    },
    "Motivo": {
        "en-US": "Reason",
        "es": "Motivo",
    },
    "Mover": {
        "en-US": "Move",
        "es": "Mover",
    },
    "Mover para a direita": {
        "en-US": "Move right",
        "es": "Mover a la derecha",
    },
    "Mover para a esquerda": {
        "en-US": "Move left",
        "es": "Mover a la izquierda",
    },
    "Movimento recusado: o destino é descendente da unidade (ciclo detectado).": {
        "en-US": "Move rejected: the target is a descendant of the unit (cycle detected).",
        "es": "Movimiento rechazado: el destino es descendiente de la unidad (ciclo detectado).",
    },
    "Mudanças": {
        "en-US": "Changes",
        "es": "Cambios",
    },
    "N5 e vertical de negócio": {
        "en-US": "N5 and business vertical",
        "es": "N5 y vertical de negocio",
    },
    "na subárvore": {
        "en-US": "in subtree",
        "es": "en el subárbol",
    },
    "Nada a desfazer.": {
        "en-US": "Nothing to undo.",
        "es": "No hay nada que deshacer.",
    },
    "Natureza": {
        "en-US": "Type",
        "es": "Naturaleza",
    },
    "Nenhum cargo da estrutura está fora do catálogo.": {
        "en-US": "No job title in the structure is missing from the catalog.",
        "es": "Ningún cargo de la estructura está fuera del catálogo.",
    },
    "Nenhuma análise em andamento.": {
        "en-US": "No analysis in progress.",
        "es": "No hay ningún análisis en curso.",
    },
    "Nenhuma equipe da estrutura está fora do cadastro.": {
        "en-US": "No team in the structure is missing from the registry.",
        "es": "Ningún equipo de la estructura está fuera del registro.",
    },
    "Nenhuma linha tem e-mail: o pareamento cairá para o nome, e renomear alguém será lido como troca de pessoa.": {
        "en-US": "No row has an email: matching will fall back to the name, and renaming someone will read as a different person.",
        "es": "Ninguna fila tiene correo: el emparejamiento caerá al nombre, y renombrar a alguien se leerá como un cambio de persona.",
    },
    "Nenhuma pessoa usa esse cargo ainda.": {
        "en-US": "No one uses this job title yet.",
        "es": "Todavía nadie usa este cargo.",
    },
    "Nenhuma unidade divergia do catálogo.": {
        "en-US": "No unit differed from the catalog.",
        "es": "Ninguna unidad divergía del catálogo.",
    },
    "Nenhuma unidade selecionada": {
        "en-US": "No unit selected",
        "es": "Ninguna unidad seleccionada",
    },
    "niveis hierarquicos": {
        "en-US": "hierarchy levels",
        "es": "niveles jerárquicos",
    },
    "Nome": {
        "en-US": "Name",
        "es": "Nombre",
    },
    "Nome / pessoa": {
        "en-US": "Name / person",
        "es": "Nombre / persona",
    },
    "Nome usado na apresentação": {
        "en-US": "Name used in the presentation",
        "es": "Nombre usado en la presentación",
    },
    "Nova unidade": {
        "en-US": "New unit",
        "es": "Nueva unidad",
    },
    "Novo cargo": {
        "en-US": "New job title",
        "es": "Nuevo cargo",
    },
    "novo padrão, ex.: consultor|especialista": {
        "en-US": "new pattern, e.g. consultant|specialist",
        "es": "nuevo patrón, ej.: consultor|especialista",
    },
    "novo subordinado pelo canvas": {
        "en-US": "new direct report from the canvas",
        "es": "nuevo subordinado desde el canvas",
    },
    "novos": {
        "en-US": "new",
        "es": "nuevos",
    },
    "Novos": {
        "en-US": "New",
        "es": "Nuevos",
    },
    "Níveis abertos ao carregar": {
        "en-US": "Levels expanded on load",
        "es": "Niveles abiertos al cargar",
    },
    "Níveis hierárquicos": {
        "en-US": "Hierarchy levels",
        "es": "Niveles jerárquicos",
    },
    "Níveis salvos.": {
        "en-US": "Levels saved.",
        "es": "Niveles guardados.",
    },
    "Nível": {
        "en-US": "Level",
        "es": "Nivel",
    },
    "Nível inválido.": {
        "en-US": "Invalid level.",
        "es": "Nivel inválido.",
    },
    "nível lógico": {
        "en-US": "logical level",
        "es": "nivel lógico",
    },
    "O editor só altera a unidade de escopo e os descendentes dela. Fora disso, a mutação é recusada com aviso — o canvas não muda.": {
        "en-US": "The editor can only change the scope unit and its descendants. Anything outside that is rejected with a warning — the canvas does not change.",
        "es": "El editor solo modifica la unidad de alcance y sus descendientes. Fuera de eso, la mutación se rechaza con un aviso: el canvas no cambia.",
    },
    "O nível é o que a fita colorida do card codifica e o que o filtro <i>Nível</i> seleciona. O <b>código</b> não é editável: ele casa com o enum <code>org.tipo_unidade</code> do banco e com o <code>tipo</code> gravado em cada unidade.": {
        "en-US": "The level is what the card's colored ribbon encodes and what the <i>Level</i> filter selects. The <b>code</b> is not editable: it matches the <code>org.tipo_unidade</code> enum in the database and the <code>tipo</code> stored on each unit.",
        "es": "El nivel es lo que codifica la cinta de color de la tarjeta y lo que selecciona el filtro <i>Nivel</i>. El <b>código</b> no es editable: coincide con el enum <code>org.tipo_unidade</code> de la base de datos y con el <code>tipo</code> guardado en cada unidad.",
    },
    "O que aparece no card": {
        "en-US": "What shows on the card",
        "es": "Qué aparece en la tarjeta",
    },
    "O tema alcança o SVG do canvas por variável CSS — a troca é instantânea, sem recarregar. O arquivo exportado sai sempre claro: papel não tem tema.": {
        "en-US": "The theme reaches the canvas SVG through a CSS variable — switching is instant, no reload. The exported file always comes out light: paper has no theme.",
        "es": "El tema llega al SVG del canvas por variable CSS: el cambio es instantáneo, sin recargar. El archivo exportado siempre sale en claro: el papel no tiene tema.",
    },
    "obrigatório. Identifica a pessoa.": {
        "en-US": "required. Identifies the person.",
        "es": "obligatorio. Identifica a la persona.",
    },
    "obrigatório. Nome exatamente como aparece em Colaborador. Quem responde ao conselho recebe um nome que não existe na coluna Colaborador (ex.: Board) e vira filho da raiz.": {
        "en-US": "required. The name exactly as it appears in Employee. Whoever reports to the board gets a name that does not exist in the Employee column (e.g. Board) and becomes a child of the root.",
        "es": "obligatorio. El nombre exactamente como aparece en Colaborador. Quien reporta al consejo recibe un nombre que no existe en la columna Colaborador (p. ej.: Board) y pasa a ser hijo de la raíz.",
    },
    "Ordem": {
        "en-US": "Order",
        "es": "Orden",
    },
    "ORG-DUPLICIDADE: colaborador repetido na planilha: {dup}": {
        "en-US": "ORG-DUPLICIDADE: duplicate employee in the spreadsheet: {dup}",
        "es": "ORG-DUPLICIDADE: colaborador repetido en la hoja de cálculo: {dup}",
    },
    "ORG-RAIZ: organograma sem raiz": {
        "en-US": "ORG-RAIZ: org chart with no root",
        "es": "ORG-RAIZ: organigrama sin raíz",
    },
    "Organização (selo de tenant)": {
        "en-US": "Organization (tenant badge)",
        "es": "Organización (sello de tenant)",
    },
    "Organograma": {
        "en-US": "Org chart",
        "es": "Organigrama",
    },
    "Organograma convencional: a liderança ocupa o topo.": {
        "en-US": "Conventional org chart: leadership sits at the top.",
        "es": "Organigrama convencional: el liderazgo ocupa la parte superior.",
    },
    "Organograma invertido: a liderança ocupa a base; os times liderados, o topo. A hierarquia lógica permanece raiz para folhas na ordem de leitura e nos níveis anunciados.": {
        "en-US": "Inverted org chart: leadership sits at the bottom and the teams they lead at the top. The logical hierarchy stays root-to-leaf in reading order and in the announced levels.",
        "es": "Organigrama invertido: el liderazgo ocupa la base y los equipos liderados, la parte superior. La jerarquía lógica se mantiene de la raíz a las hojas en el orden de lectura y en los niveles anunciados.",
    },
    "Orientação padrão": {
        "en-US": "Default orientation",
        "es": "Orientación predeterminada",
    },
    "Origem": {
        "en-US": "Source",
        "es": "Origen",
    },
    "os subordinados sobem um nível": {
        "en-US": "the direct reports move up one level",
        "es": "los subordinados suben un nivel",
    },
    "Padrão": {
        "en-US": "Pattern",
        "es": "Patrón",
    },
    "Painel": {
        "en-US": "Panel",
        "es": "Panel lateral",
    },
    "Passo 1": {
        "en-US": "Step 1",
        "es": "Paso 1",
    },
    "Passo 2": {
        "en-US": "Step 2",
        "es": "Paso 2",
    },
    "Passo 3": {
        "en-US": "Step 3",
        "es": "Paso 3",
    },
    "Payload": {
        "en-US": "Payload",
        "es": "Payload",
    },
    "Perfil e escopo": {
        "en-US": "Role and scope",
        "es": "Perfil y alcance",
    },
    "perfil e escopo de edição": {
        "en-US": "role and editing scope",
        "es": "perfil y alcance de edición",
    },
    "Perfil sem permissão de edição nesta unidade. Os campos\n    estão em leitura.": {
        "en-US": "Your role has no edit permission on this unit. The fields\n    are read-only.",
        "es": "El perfil no tiene permiso de edición en esta unidad. Los campos\n    están en modo lectura.",
    },
    "Perfil vigente: {perfil}.": {
        "en-US": "Current role: {perfil}.",
        "es": "Perfil vigente: {perfil}.",
    },
    "Permissões": {
        "en-US": "Permissions",
        "es": "Permisos",
    },
    "Pessoas": {
        "en-US": "People",
        "es": "Personas",
    },
    "pessoas": {
        "en-US": "people",
        "es": "personas",
    },
    "Planilha (.xlsx)": {
        "en-US": "Spreadsheet (.xlsx)",
        "es": "Hoja de cálculo (.xlsx)",
    },
    "Planilha recusada: {erro}": {
        "en-US": "Spreadsheet rejected: {erro}",
        "es": "Hoja de cálculo rechazada: {erro}",
    },
    "Promover um nível": {
        "en-US": "Promote one level",
        "es": "Promover un nivel",
    },
    "promover um nível": {
        "en-US": "promote one level",
        "es": "promover un nivel",
    },
    "Promoção recusada: não há nível acima do pai.": {
        "en-US": "Promotion rejected: there is no level above the parent unit.",
        "es": "Promoción rechazada: no hay ningún nivel por encima de la unidad padre.",
    },
    "Quando (UTC)": {
        "en-US": "When (UTC)",
        "es": "Cuándo (UTC)",
    },
    "RBAC da SPEC §12.1. Enquanto a autenticação OIDC é débito declarado (DT-02), o perfil vigente é escolhido aqui — mas a guarda que ele alimenta é real: toda rota de mutação passa por ela.": {
        "en-US": "RBAC from SPEC §12.1. While OIDC authentication is declared debt (DT-02), the current role is picked here — but the guard it feeds is real: every mutation route goes through it.",
        "es": "RBAC de la SPEC §12.1. Mientras la autenticación OIDC sea deuda declarada (DT-02), el perfil vigente se elige aquí, pero la guarda que ese perfil alimenta es real: toda ruta de mutación pasa por ella.",
    },
    "Rebaixamento recusado: não há irmão anterior.": {
        "en-US": "Demotion rejected: there is no previous sibling.",
        "es": "Descenso rechazado: no hay una unidad hermana anterior.",
    },
    "Rebaixar o próprio perfil é permitido; voltar a subir exige Administrador. Como não há login, quem se rebaixa perde a chave até editar <code>dados/estado.json</code>.": {
        "en-US": "Lowering your own role is allowed; going back up requires Administrator. With no login, whoever demotes themselves loses the key until they edit <code>dados/estado.json</code>.",
        "es": "Bajar el propio perfil está permitido; volver a subir exige Administrador. Como no hay inicio de sesión, quien se baja pierde la llave hasta editar <code>dados/estado.json</code>.",
    },
    "Rebaixar um nível": {
        "en-US": "Demote one level",
        "es": "Descender un nivel",
    },
    "rebaixar um nível": {
        "en-US": "demote one level",
        "es": "descender un nivel",
    },
    "Recarga total": {
        "en-US": "Full reload",
        "es": "Recarga total",
    },
    "Recarregar de Organograma.xlsx": {
        "en-US": "Reload from Organograma.xlsx",
        "es": "Recargar desde Organograma.xlsx",
    },
    "Recarregar do zero? Toda edição feita no canvas será perdida.": {
        "en-US": "Reload from scratch? Every edit made on the canvas will be lost.",
        "es": "¿Recargar desde cero? Se perderá toda edición hecha en el canvas.",
    },
    "reclassificacao de nivel pelo catalogo de cargos": {
        "en-US": "level reclassification from the job title catalog",
        "es": "reclasificación de nivel según el catálogo de cargos",
    },
    "Reclassificar as unidades pelo catálogo? Muda a cor dos cards e a altura das faixas. Pode ser desfeito uma vez.": {
        "en-US": "Reclassify the units by the catalog? It changes card colors and band heights. Can be undone once.",
        "es": "¿Reclasificar las unidades según el catálogo? Cambia el color de las tarjetas y la altura de las franjas. Se puede deshacer una vez.",
    },
    "Recolher o painel": {
        "en-US": "Collapse the panel",
        "es": "Contraer el panel lateral",
    },
    "Recolher ou expandir o painel": {
        "en-US": "Collapse or expand the panel",
        "es": "Contraer o expandir el panel lateral",
    },
    "recomendado. É a identidade estável entre cargas: sem ele o pareamento cai para o nome e uma troca de sobrenome vira pessoa nova.": {
        "en-US": "recommended. This is the stable identity across loads: without it, matching falls back to the name and a change of last name turns into a new person.",
        "es": "recomendado. Es la identidad estable entre cargas: sin él el emparejamiento cae al nombre y un cambio de apellido se vuelve una persona nueva.",
    },
    "regra": {
        "en-US": "rule",
        "es": "regla",
    },
    "regras de classificacao de cargo": {
        "en-US": "job title classification rules",
        "es": "reglas de clasificación de cargo",
    },
    "Regras de classificação": {
        "en-US": "Classification rules",
        "es": "Reglas de clasificación",
    },
    "Regras salvas.": {
        "en-US": "Rules saved.",
        "es": "Reglas guardadas.",
    },
    "reparent pelo painel": {
        "en-US": "reparent from the panel",
        "es": "reasignación de padre desde el panel lateral",
    },
    "Reporte": {
        "en-US": "Reporting line",
        "es": "Línea de reporte",
    },
    "Responde a": {
        "en-US": "Reports to",
        "es": "Reporta a",
    },
    "responde a": {
        "en-US": "reports to",
        "es": "reporta a",
    },
    "Responsável": {
        "en-US": "Owner",
        "es": "Responsable",
    },
    "Restaurar a tabela de referência? As edições de nome, N5, vertical e tipo serão perdidas.": {
        "en-US": "Restore the reference table? Edits to name, N5, vertical and type will be lost.",
        "es": "¿Restaurar la tabla de referencia? Se perderán las ediciones de nombre, N5, vertical y tipo.",
    },
    "Restaurar referência": {
        "en-US": "Restore reference",
        "es": "Restaurar referencia",
    },
    "roda = zoom · shift+roda = deslizar · duplo clique = focar · B = gaveta": {
        "en-US": "wheel = zoom · shift+wheel = pan · double-click = focus · B = drawer",
        "es": "rueda = zoom · shift+rueda = desplazar · doble clic = enfocar · B = panel lateral",
    },
    "Rótulo": {
        "en-US": "Label",
        "es": "Etiqueta",
    },
    "Sair do foco": {
        "en-US": "Exit focus",
        "es": "Salir del foco",
    },
    "Salvar": {
        "en-US": "Save",
        "es": "Guardar",
    },
    "Salvar cadastro": {
        "en-US": "Save registry",
        "es": "Guardar registro",
    },
    "Salvar catálogo": {
        "en-US": "Save catalog",
        "es": "Guardar catálogo",
    },
    "Salvar níveis": {
        "en-US": "Save levels",
        "es": "Guardar niveles",
    },
    "Salvar regras": {
        "en-US": "Save rules",
        "es": "Guardar reglas",
    },
    "se o card for uma área": {
        "en-US": "if the card is an area",
        "es": "si la tarjeta es un área",
    },
    "Seguir o sistema": {
        "en-US": "Match system",
        "es": "Seguir el sistema",
    },
    "sem correspondência": {
        "en-US": "unmatched",
        "es": "sin coincidencia",
    },
    "sem mudança": {
        "en-US": "unchanged",
        "es": "sin cambios",
    },
    "Sem nome em português no vocabulário da apresentação": {
        "en-US": "No Portuguese name in the presentation vocabulary",
        "es": "Sin nombre en portugués en el vocabulario de la presentación",
    },
    "sempre visível": {
        "en-US": "always visible",
        "es": "siempre visible",
    },
    "separadas por vírgula": {
        "en-US": "comma-separated",
        "es": "separadas por comas",
    },
    "Seq": {
        "en-US": "Seq",
        "es": "Sec.",
    },
    "Serviços Compartilhados": {
        "en-US": "Shared Services",
        "es": "Servicios Compartidos",
    },
    "Seções de configuração": {
        "en-US": "Settings sections",
        "es": "Secciones de configuración",
    },
    "Sub.": {
        "en-US": "Reports",
        "es": "Sub.",
    },
    "subordinados diretos": {
        "en-US": "direct reports",
        "es": "subordinados directos",
    },
    "SVG": {
        "en-US": "SVG",
        "es": "SVG",
    },
    "Tabela": {
        "en-US": "Table",
        "es": "Tabla",
    },
    "Time": {
        "en-US": "Team",
        "es": "Equipo",
    },
    "Tipo": {
        "en-US": "Type",
        "es": "Tipo",
    },
    "Tokens de layout da SPEC §9.6. Fora das faixas o motor recusa e volta ao limite.": {
        "en-US": "Layout tokens from SPEC §9.6. Outside the ranges the engine rejects the value and falls back to the limit.",
        "es": "Tokens de layout de la SPEC §9.6. Fuera de los rangos el motor rechaza y vuelve al límite.",
    },
    "Trilha de auditoria": {
        "en-US": "Audit trail",
        "es": "Registro de auditoría",
    },
    "Tudo": {
        "en-US": "All",
        "es": "Todo",
    },
    "Título do organograma": {
        "en-US": "Org chart title",
        "es": "Título del organigrama",
    },
    "Uma por linha. Prefixe com <code>&gt;</code> para marcar escopo\n        <strong>delegado</strong> — aquilo por que a unidade responde mas quem executa\n        é um subordinado.": {
        "en-US": "One per line. Prefix with <code>&gt;</code> to mark the scope as\n        <strong>delegated</strong> — what the unit answers for but a direct report\n        actually does.",
        "es": "Una por línea. Anteponga <code>&gt;</code> para marcar alcance\n        <strong>delegado</strong> — aquello de lo que responde la unidad pero que\n        ejecuta un subordinado.",
    },
    "Unidade": {
        "en-US": "Unit",
        "es": "Unidad",
    },
    "Unidade / pessoa": {
        "en-US": "Unit / person",
        "es": "Unidad / persona",
    },
    "Unidade de escopo do editor (SEC-03)": {
        "en-US": "Editor scope unit (SEC-03)",
        "es": "Unidad de alcance del editor (SEC-03)",
    },
    "unidades resolvidas": {
        "en-US": "resolved units",
        "es": "unidades resueltas",
    },
    "Usadas quando o cargo não está no catálogo — na próxima carga da planilha, por exemplo. A <b>primeira regra que casa vence</b>, por isso a ordem importa. O padrão é expressão regular sobre o cargo sem acento e em minúsculas; padrão inválido é descartado em vez de derrubar a tela.": {
        "en-US": "Used when the job title is not in the catalog — on the next spreadsheet load, for example. The <b>first rule that matches wins</b>, which is why order matters. The pattern is a regular expression over the title with accents stripped and lowercased; an invalid pattern is discarded instead of taking the screen down.",
        "es": "Se usan cuando el cargo no está en el catálogo, por ejemplo en la próxima carga de la hoja de cálculo. <b>Gana la primera regla que coincide</b>, por eso el orden importa. El patrón es una expresión regular sobre el cargo sin acentos y en minúsculas; un patrón inválido se descarta en lugar de romper la pantalla.",
    },
    "Use <i>Descobrir da estrutura</i> para criá-las já preenchidas com o que o dado sabe.": {
        "en-US": "Use <i>Discover from structure</i> to create them already filled with what the data knows.",
        "es": "Use <i>Descubrir desde la estructura</i> para crearlas ya completadas con lo que el dato sabe.",
    },
    "Vale para o canvas, o SVG e o PDF — os três saem do mesmo motor. O card encolhe junto: menos campo, mais nó por tela.": {
        "en-US": "Applies to the canvas, the SVG and the PDF — all three come out of the same engine. The card shrinks with it: fewer fields, more nodes per screen.",
        "es": "Vale para el canvas, el SVG y el PDF: los tres salen del mismo motor. La tarjeta se encoge con ellos: menos campos, más nodos por pantalla.",
    },
    "verticais": {
        "en-US": "verticals",
        "es": "verticales",
    },
    "Verticais de negócio": {
        "en-US": "Business verticals",
        "es": "Verticales de negocio",
    },
    "Verticais que entregam ao cliente.": {
        "en-US": "Verticals that deliver to the customer.",
        "es": "Verticales que entregan al cliente.",
    },
    "Vertical": {
        "en-US": "Vertical",
        "es": "Vertical",
    },
    "Vertical (CC N2)": {
        "en-US": "Vertical (CC N2)",
        "es": "Vertical (CC N2)",
    },
    "Vertical (N2)": {
        "en-US": "Vertical (N2)",
        "es": "Vertical (N2)",
    },
    "Vieram da estrutura, não da tabela de referência — a vertical foi herdada do tronco N2 quando havia maioria clara; o N5 é mnemônico da equipe e não há de onde tirar.": {
        "en-US": "They came from the structure, not from the reference table — the vertical was inherited from the N2 trunk where there was a clear majority; the N5 is the team's mnemonic and there is nowhere to pull it from.",
        "es": "Vinieron de la estructura, no de la tabla de referencia: la vertical se heredó del tronco N2 cuando había mayoría clara; el N5 es el mnemónico del equipo y no hay de dónde sacarlo.",
    },
    "Vistas": {
        "en-US": "Views",
        "es": "Vistas",
    },
    "Visualizador": {
        "en-US": "Viewer",
        "es": "Visualizador",
    },
    "Vocabulário": {
        "en-US": "Vocabulary",
        "es": "Vocabulario",
    },
    "Voltar ao organograma completo": {
        "en-US": "Back to the full org chart",
        "es": "Volver al organigrama completo",
    },
    "Zoom do canvas": {
        "en-US": "Canvas zoom",
        "es": "Zoom del canvas",
    },
    "{nome} (cópia)": {
        "en-US": "{nome} (copy)",
        "es": "{nome} (copia)",
    },
    "{n} cargo(s) acrescentado(s), classificados pelas regras.": {
        "en-US": "{n} job title(s) added, classified by the rules.",
        "es": "{n} cargo(s) agregado(s), clasificados por las reglas.",
    },
    "{n} cargo(s) salvos. Use “Aplicar às unidades” para reclassificar a estrutura.": {
        "en-US": "{n} job title(s) saved. Use “Apply to units” to reclassify the structure.",
        "es": "{n} cargo(s) guardado(s). Use “Aplicar a las unidades” para reclasificar la estructura.",
    },
    "{n} linha(s) acrescentada(s) a partir da estrutura.": {
        "en-US": "{n} row(s) added from the structure.",
        "es": "{n} fila(s) agregada(s) a partir de la estructura.",
    },
    "{n} pessoa(s) usam esse cargo — “Aplicar às unidades” reclassifica.": {
        "en-US": "{n} person(s) already use this job title — “Apply to units” reclassifies them.",
        "es": "{n} persona(s) usan este cargo — “Aplicar a las unidades” las reclasifica.",
    },
    "{n} unidade(s) reclassificada(s).": {
        "en-US": "{n} unit(s) reclassified.",
        "es": "{n} unidad(es) reclasificada(s).",
    },
    "{n} unidades · profundidade {d} · orientação {orientacao}": {
        "en-US": "{n} units · depth {d} · orientation {orientacao}",
        "es": "{n} unidades · profundidad {d} · orientación {orientacao}",
    },
    "Área": {
        "en-US": "Area",
        "es": "Área",
    },
    "Áreas administrativas que sustentam as verticais.": {
        "en-US": "Administrative areas that support the verticals.",
        "es": "Áreas administrativas que sustentan las verticales.",
    },
    "Âmbar": {
        "en-US": "Amber",
        "es": "Ámbar",
    },
    "— (raiz)": {
        "en-US": "— (root)",
        "es": "— (raíz)",
    },
    "— as marcadas com * são obrigatórias.": {
        "en-US": "— the ones marked * are required.",
        "es": "— las marcadas con * son obligatorias.",
    },
    "— sem restrição de subárvore —": {
        "en-US": "— no subtree restriction —",
        "es": "— sin restricción de subárbol —",
    },
    "“{cargo}” já está no catálogo como {nivel}. Edite a linha em vez de criar outra.": {
        "en-US": "“{cargo}” is already in the catalog as {nivel}. Edit that row instead of creating another.",
        "es": "“{cargo}” ya está en el catálogo como {nivel}. Edite esa fila en lugar de crear otra.",
    },
    "▲ Convencional": {
        "en-US": "▲ Conventional",
        "es": "▲ Convencional",
    },
    "▼ Invertida": {
        "en-US": "▼ Inverted",
        "es": "▼ Invertida",
    },
    "◂ todo o organograma": {
        "en-US": "◂ full org chart",
        "es": "◂ todo el organigrama",
    },

    # --- relatório PDF da MarIA (RQ-808/809/810)
    'emissão de PDF bloqueada pelo portão': {
        "en-US": 'PDF issuance blocked by the gate',
        "es": 'emisión de PDF bloqueada por la compuerta'},
    'relatório PDF da MarIA emitido': {
        "en-US": "MarIA PDF report issued",
        "es": 'informe PDF de MarIA emitido'},
    'Ver resposta': {
        "en-US": 'View answer',
        "es": 'Ver respuesta'},
    'Baixar PDF': {
        "en-US": 'Download PDF',
        "es": 'Descargar PDF'},
    'MarIA · {capacidade}': {
        "en-US": 'MarIA · {capacidade}',
        "es": 'MarIA · {capacidade}'},
    '{n} achado(s) bloqueiam a emissão do PDF.': {
        "en-US": '{n} finding(s) block the PDF from being issued.',
        "es": '{n} hallazgo(s) impiden la emisión del PDF.'},
    'O texto continua aqui e no histórico — o que não sai é o artefato que circula fora do sistema. Peça a resposta de novo à MarIA.': {
        "en-US": 'The text stays here and in the history — what is withheld is the artefact that travels outside the system. Ask MarIA again.',
        "es": 'El texto permanece aquí y en el historial — lo que no sale es el artefacto que circula fuera del sistema. Pídele la respuesta de nuevo a MarIA.'},
    '{entrada}→{saida} tokens · US$ {custo} · validação: {estado}': {
        "en-US": '{entrada}→{saida} tokens · US$ {custo} · validation: {estado}',
        "es": '{entrada}→{saida} tokens · US$ {custo} · validación: {estado}'},
    'gramática {locale}': {
        "en-US": '{locale} grammar',
        "es": 'gramática {locale}'},
    'checagem mecânica': {
        "en-US": 'mechanical check',
        "es": 'revisión mecánica'},
    'gramática {locale} · {dicionario}': {
        "en-US": '{locale} grammar · {dicionario}',
        "es": 'gramática {locale} · {dicionario}'},
    'checagem mecânica · {locale}': {
        "en-US": 'mechanical check · {locale}',
        "es": 'revisión mecánica · {locale}'},
    '{n}/{total} · layout v{versao}': {
        "en-US": '{n}/{total} · layout v{versao}',
        "es": '{n}/{total} · diseño v{versao}'},

    # --- recorte pelo canvas e sugestões calculadas
    'Recorte': {
        "en-US": 'Scope',
        "es": 'Recorte'},
    'Tudo o que posso ver': {
        "en-US": 'Everything I can see',
        "es": 'Todo lo que puedo ver'},
    'Só o que está no canvas': {
        "en-US": 'Only what is on the canvas',
        "es": 'Sólo lo que está en el lienzo'},
    'visível no canvas ({n} de {total})': {
        "en-US": 'visible on the canvas ({n} of {total})',
        "es": 'visible en el lienzo ({n} de {total})'},
    'visível no canvas a partir de {unidade} ({n} de {total})': {
        "en-US": 'visible on the canvas from {unidade} ({n} of {total})',
        "es": 'visible en el lienzo desde {unidade} ({n} de {total})'},
    'Onde há pessoa respondendo para fora da própria vertical?': {
        "en-US": 'Is anyone reporting outside their own vertical?',
        "es": '¿Hay alguien que reporte fuera de su propia vertical?'},
    'Que cargos aparecem repetidos com nomes diferentes?': {
        "en-US": 'Which roles appear more than once under different names?',
        "es": '¿Qué cargos aparecen repetidos con nombres distintos?'},
    'Os {n} gestores sem subordinados diretos justificam o nível que ocupam?': {
        "en-US": 'Do the {n} managers with no direct reports justify the level they hold?',
        "es": '¿Los {n} gestores sin subordinados directos justifican el nivel que ocupan?'},
    'A carga está bem distribuída, com {dep} concentrando {n} das {total} pessoas do recorte?': {
        "en-US": 'Is the load well distributed, with {dep} holding {n} of the {total} people in scope?',
        "es": '¿La carga está bien distribuida, con {dep} concentrando {n} de las {total} personas del recorte?'},
    'Por onde começar com as {n} pessoas cujo centro de custo não resolve?': {
        "en-US": 'Where should we start with the {n} people whose cost centre does not resolve?',
        "es": '¿Por dónde empezar con las {n} personas cuyo centro de coste no resuelve?'},
    'Falta ou sobra liderança no nível {nivel}, que tem {n} pessoas no recorte?': {
        "en-US": 'Is there too little leadership or too much at level {nivel}, which has {n} people in scope?',
        "es": '¿Falta o sobra liderazgo en el nivel {nivel}, que tiene {n} personas en el recorte?'},
    'A vertical {vertical}, com {n} pessoas, está coberta em todos os níveis?': {
        "en-US": 'Is vertical {vertical}, with {n} people, covered at every level?',
        "es": '¿La vertical {vertical}, con {n} personas, está cubierta en todos los niveles?'},

    # --- guardas acrescentadas depois da verificação completa
    'A unidade “{sob}” não existe mais. A proposta foi feita sobre outra estrutura — descarte e peça de novo.': {
        "en-US": 'The unit “{sob}” no longer exists. The proposal was made over a different structure — discard it and ask again.',
        "es": 'La unidad «{sob}» ya no existe. La propuesta se hizo sobre otra estructura — descártela y pida de nuevo.'},
    '{n} código(s) aparecem mais de uma vez, aqui ou na estrutura. O código é a identidade mais forte do contrato: repetido, ele deixa de identificar, e essas linhas caem para nome e e-mail. {quais}': {
        "en-US": '{n} code(s) appear more than once, here or in the structure. The code is the strongest identity in the contract: repeated, it stops identifying, and those rows fall back to name and e-mail. {quais}',
        "es": '{n} código(s) aparecen más de una vez, aquí o en la estructura. El código es la identidad más fuerte del contrato: repetido, deja de identificar, y esas filas caen a nombre y correo. {quais}'},

    # --- aba Banco de dados: o que está na tela x o que está no banco
    'Ligado: o banco respondeu e tem {n} unidade(s) gravada(s).': {
        "en-US": 'Connected: the database answered and holds {n} unit(s).',
        "es": 'Conectado: la base de datos respondió y tiene {n} unidad(es).'},
    'A conexão está configurada, mas o banco não respondeu. Use <b>Testar conexão</b> para ver a mensagem do driver.': {
        "en-US": 'The connection is configured, but the database did not answer. Use <b>Test connection</b> to see the driver message.',
        "es": 'La conexión está configurada, pero la base de datos no respondió. Use <b>Probar conexión</b> para ver el mensaje del controlador.'},
    'Mapeamento entre o modelo em memória e o schema.': {
        "en-US": 'Mapping between the in-memory model and the schema.',
        "es": 'Correspondencia entre el modelo en memoria y el esquema.'},
    '“Na tela” é o que a carga escreveria agora; “no banco” é o que está lá neste momento.': {
        "en-US": '“On screen” is what the load would write now; “in the database” is what is there right now.',
        "es": '«En pantalla» es lo que la carga escribiría ahora; «en la base» es lo que hay allí en este momento.'},
    'A contagem é o que a carga escreveria agora.': {
        "en-US": 'The count is what the load would write now.',
        "es": 'El recuento es lo que la carga escribiría ahora.'},
    'O banco está no mesmo ponto da tela.': {
        "en-US": 'The database is at the same point as the screen.',
        "es": 'La base de datos está en el mismo punto que la pantalla.'},
    'O banco está atrasado em relação à tela: {n} tabela(s) divergem ({quais}). Use <b>Escrever organograma</b> para igualar.': {
        "en-US": 'The database is behind the screen: {n} table(s) differ ({quais}). Use <b>Write org chart</b> to bring it level.',
        "es": 'La base de datos está atrasada respecto a la pantalla: {n} tabla(s) difieren ({quais}). Use <b>Escribir organigrama</b> para igualar.'},
    'Na tela': {
        "en-US": 'On screen',
        "es": 'En pantalla'},
    'No banco': {
        "en-US": 'In the database',
        "es": 'En la base'},
    'A tela tem {n}; o banco, {r}.': {
        "en-US": 'The screen has {n}; the database, {r}.',
        "es": 'La pantalla tiene {n}; la base, {r}.'},
    'Conferir campo a campo': {
        "en-US": 'Check field by field',
        "es": 'Verificar campo a campo'},
    'Não foi possível conferir: o banco não respondeu.': {
        "en-US": 'Could not check: the database did not respond.',
        "es": 'No se pudo verificar: la base de datos no respondió.'},
    'Tela e banco batem campo a campo: {n} nó(s) conferido(s), nada perdido no caminho.': {
        "en-US": 'Screen and database match field by field: {n} node(s) checked, nothing lost along the way.',
        "es": 'Pantalla y base coinciden campo a campo: {n} nodo(s) verificado(s), nada perdido en el camino.'},
    '{d} de {n} nó(s) divergem entre tela e banco.': {
        "en-US": '{d} of {n} node(s) differ between screen and database.',
        "es": '{d} de {n} nodo(s) difieren entre pantalla y base.'},
    'Só na tela: {n}.': {
        "en-US": 'Only on screen: {n}.',
        "es": 'Solo en pantalla: {n}.'},
    'Só no banco: {n}.': {
        "en-US": 'Only in the database: {n}.',
        "es": 'Solo en la base: {n}.'},
    'Nó': {
        "en-US": 'Node',
        "es": 'Nodo'},
    'Campos que divergem': {
        "en-US": 'Fields that differ',
        "es": 'Campos que difieren'},
    'Mostrando os primeiros 50 de {n}.': {
        "en-US": 'Showing the first 50 of {n}.',
        "es": 'Mostrando los primeros 50 de {n}.'},
    'Use <b>Escrever organograma</b> para reescrever o banco a partir da tela e zerar a divergência.': {
        "en-US": 'Use <b>Write org chart</b> to rewrite the database from the screen and clear the difference.',
        "es": 'Use <b>Escribir organigrama</b> para reescribir la base desde la pantalla y eliminar la divergencia.'},
    '<b>closure</b> é derivada: a carga a calcula em SQL a partir da árvore que acabou de gravar, e é ela que faz consulta de subárvore custar um índice em vez de uma recursão. São mais linhas que unidades — um par por ancestral de cada nó, mais o par consigo mesmo.': {
        "en-US": '<b>closure</b> is derived: the load computes it in SQL from the tree it has just written, and it is what makes a subtree query cost an index instead of a recursion. There are more rows than units — one pair per ancestor of each node, plus the pair with itself.',
        "es": '<b>closure</b> es derivada: la carga la calcula en SQL a partir del árbol que acaba de grabar, y es la que hace que consultar un subárbol cueste un índice en vez de una recursión. Son más filas que unidades — un par por antepasado de cada nodo, más el par consigo mismo.'},
    'O ledger (<code>org.evento</code>) e o histórico da MarIA não entram na carga do organograma: são log, e recarregar a estrutura não pode levá-los junto.': {
        "en-US": 'The ledger (<code>org.evento</code>) and MarIA’s history are not part of the org chart load: they are logs, and reloading the structure must not take them along.',
        "es": 'El ledger (<code>org.evento</code>) y el historial de MarIA no entran en la carga del organigrama: son registro, y recargar la estructura no puede llevárselos.'},

    # --- a legenda de níveis, que virou filtro
    'Filtrar por nível': {
        "en-US": 'Filter by level',
        "es": 'Filtrar por nivel'},
    'Filtrar por {nivel}': {
        "en-US": 'Filter by {nivel}',
        "es": 'Filtrar por {nivel}'},

    # --- a grade editável da Tabela (AG Grid Community)
    'Editar': {
        "en-US": 'Edit',
        "es": 'Editar'},
    'Liga a edição na grade: Enter edita a célula, Tab indenta, Shift+Tab promove, e o botão direito abre as ações da linha.': {
        "en-US": 'Turns on editing in the grid: Enter edits the cell, Tab indents, Shift+Tab promotes, and right-click opens the row actions.',
        "es": 'Activa la edición en la cuadrícula: Enter edita la celda, Tab indenta, Shift+Tab promueve, y el clic derecho abre las acciones de la fila.'},
    'Edição ligada. Enter edita, Tab indenta, Shift+Tab promove, botão direito abre as ações.': {
        "en-US": 'Editing on. Enter edits, Tab indents, Shift+Tab promotes, right-click opens the actions.',
        "es": 'Edición activada. Enter edita, Tab indenta, Shift+Tab promueve, el clic derecho abre las acciones.'},
    'Linha copiada.': {
        "en-US": 'Row copied.',
        "es": 'Fila copiada.'},
    'Nenhuma linha neste recorte.': {
        "en-US": 'No rows in this scope.',
        "es": 'Ninguna fila en este recorte.'},
    'Abrir': {
        "en-US": 'Expand',
        "es": 'Abrir'},
    'Dobrar': {
        "en-US": 'Collapse',
        "es": 'Plegar'},
    'Editar esta célula': {
        "en-US": 'Edit this cell',
        "es": 'Editar esta celda'},
    'Indentar': {
        "en-US": 'Indent',
        "es": 'Indentar'},
    'Promover': {
        "en-US": 'Promote',
        "es": 'Promover'},
    'Subir entre os irmãos': {
        "en-US": 'Move up among siblings',
        "es": 'Subir entre los hermanos'},
    'Descer entre os irmãos': {
        "en-US": 'Move down among siblings',
        "es": 'Bajar entre los hermanos'},
    'Nova unidade aqui dentro': {
        "en-US": 'New unit inside this one',
        "es": 'Nueva unidad aquí dentro'},
    'Copiar a linha': {
        "en-US": 'Copy the row',
        "es": 'Copiar la fila'},
    'Exportar a grade em CSV': {
        "en-US": 'Export the grid as CSV',
        "es": 'Exportar la cuadrícula en CSV'},
    'Excluir': {
        "en-US": 'Delete',
        "es": 'Eliminar'},
    'Excluir esta unidade? Os subordinados sobem para o gestor acima.': {
        "en-US": 'Delete this unit? Its reports move up to the manager above.',
        "es": '¿Eliminar esta unidad? Los subordinados suben al gestor de arriba.'},
    'A raiz não pode ser duplicada.': {
        "en-US": 'The root cannot be duplicated.',
        "es": 'La raíz no puede duplicarse.'},
    'Ação desconhecida.': {
        "en-US": 'Unknown action.',
        "es": 'Acción desconocida.'},
    'Unidade não encontrada.': {
        "en-US": 'Unit not found.',
        "es": 'Unidad no encontrada.'},
    'Campo {campo} não é editável na grade.': {
        "en-US": 'Field {campo} is not editable in the grid.',
        "es": 'El campo {campo} no es editable en la cuadrícula.'},
    'Carregando…': {
        "en-US": 'Loading…',
        "es": 'Cargando…'},
    'Filtrar…': {
        "en-US": 'Filter…',
        "es": 'Filtrar…'},
    'Buscar…': {
        "en-US": 'Search…',
        "es": 'Buscar…'},
    '(em branco)': {
        "en-US": '(blanks)',
        "es": '(en blanco)'},
    '(marcar tudo)': {
        "en-US": '(select all)',
        "es": '(marcar todo)'},
    'Contém': {
        "en-US": 'Contains',
        "es": 'Contiene'},
    'Igual a': {
        "en-US": 'Equals',
        "es": 'Igual a'},
    'Começa com': {
        "en-US": 'Starts with',
        "es": 'Empieza con'},
    'Termina com': {
        "en-US": 'Ends with',
        "es": 'Termina con'},
    'promover pela grade': {
        "en-US": 'promote from the grid',
        "es": 'promoción desde la cuadrícula'},
    'indentar pela grade': {
        "en-US": 'indent from the grid',
        "es": 'indentación desde la cuadrícula'},
    'reparent pela grade': {
        "en-US": 'reparent from the grid',
        "es": 'reasignación de padre desde la cuadrícula'},
    'novo filho pela grade': {
        "en-US": 'new child from the grid',
        "es": 'nuevo hijo desde la cuadrícula'},
    'duplicar pela grade': {
        "en-US": 'duplicate from the grid',
        "es": 'duplicado desde la cuadrícula'},
    'exclusão pela grade': {
        "en-US": 'deletion from the grid',
        "es": 'eliminación desde la cuadrícula'},

    # --- filtro que não sobrou ninguém, no tempo de empresa
    'Nenhuma pessoa neste recorte. Afrouxe o filtro para ver os números.': {
        "en-US": 'No one in this scope. Loosen the filter to see the numbers.',
        "es": 'Nadie en este recorte. Afloje el filtro para ver los números.'},

    # -----------------------------------------------------------
    # Skills — Descrição de Cargo e Responsabilidades (GEP-FOR-003)
    # -----------------------------------------------------------
    'Skills': {
        "en-US": 'Skills',
        "es": 'Skills',
    },
    'Skills — Descrição de Cargo e Responsabilidades': {
        "en-US": 'Skills — Job Description and Responsibilities',
        "es": 'Skills — Descripción de Cargo y Responsabilidades',
    },
    'Descrição de Cargo e Responsabilidades': {
        "en-US": 'Job Description and Responsibilities',
        "es": 'Descripción de Cargo y Responsabilidades',
    },
    'Descrição de Cargo': {
        "en-US": 'Job Description',
        "es": 'Descripción de Cargo',
    },
    'Formulário {codigo} · Rev {rev}. Cada ficha é montada da estrutura vigente e completada pelo RH.': {
        "en-US": 'Form {codigo} · Rev {rev}. Each sheet is assembled from the current structure and completed by HR.',
        "es": 'Formulario {codigo} · Rev {rev}. Cada ficha se monta a partir de la estructura vigente y la completa RR. HH.',
    },
    'Seções do Skills': {
        "en-US": 'Skills sections',
        "es": 'Secciones del Skills',
    },
    'Funções e fichas': {
        "en-US": 'Roles and sheets',
        "es": 'Funciones y fichas',
    },
    'Funções por setor': {
        "en-US": 'Roles by department',
        "es": 'Funciones por sector',
    },
    'Correlações': {
        "en-US": 'Correlations',
        "es": 'Correlaciones',
    },
    'Correlação entre variáveis': {
        "en-US": 'Correlation between variables',
        "es": 'Correlación entre variables',
    },
    'Liderança por unidade': {
        "en-US": 'Leadership by unit',
        "es": 'Liderazgo por unidad',
    },
    'Liderança por Business Unit': {
        "en-US": 'Leadership by Business Unit',
        "es": 'Liderazgo por Business Unit',
    },
    'Liderança por vertical': {
        "en-US": 'Leadership by vertical',
        "es": 'Liderazgo por vertical',
    },
    'Liderança por setor': {
        "en-US": 'Leadership by department',
        "es": 'Liderazgo por sector',
    },
    'Matriz de competência': {
        "en-US": 'Competency matrix',
        "es": 'Matriz de competencia',
    },
    'funções': {
        "en-US": 'roles',
        "es": 'funciones',
    },
    'setores': {
        "en-US": 'departments',
        "es": 'sectores',
    },
    'business units': {
        "en-US": 'business units',
        "es": 'business units',
    },
    'gestores': {
        "en-US": 'managers',
        "es": 'gestores',
    },
    'amplitude': {
        "en-US": 'span of control',
        "es": 'amplitud',
    },
    'Amplitude': {
        "en-US": 'Span of control',
        "es": 'Amplitud',
    },
    'Amplitude é pessoas por gestor — diretoria, gerência e coordenação somadas. Liderança técnica e especialista não entram na conta: respondem por profundidade, não por gente.': {
        "en-US": 'Span of control is people per manager — board, management and coordination combined. Technical leads and specialists are left out: they answer for depth, not for people.',
        "es": 'La amplitud es personas por gestor — dirección, gerencia y coordinación sumadas. Liderazgo técnico y especialista quedan fuera: responden por profundidad, no por gente.',
    },
    'Liderança técnica': {
        "en-US": 'Technical lead',
        "es": 'Liderazgo técnico',
    },
    'Execução': {
        "en-US": 'Execution',
        "es": 'Ejecución',
    },
    'Papel': {
        "en-US": 'Role',
        "es": 'Rol',
    },
    'Função': {
        "en-US": 'Role',
        "es": 'Función',
    },
    'Funções': {
        "en-US": 'Roles',
        "es": 'Funciones',
    },
    'Setor': {
        "en-US": 'Department',
        "es": 'Sector',
    },
    'Setores': {
        "en-US": 'Departments',
        "es": 'Sectores',
    },
    'BUs': {
        "en-US": 'BUs',
        "es": 'BUs',
    },
    'Business Unit': {
        "en-US": 'Business Unit',
        "es": 'Business Unit',
    },
    'Ficha': {
        "en-US": 'Sheet',
        "es": 'Ficha',
    },
    'descrita': {
        "en-US": 'described',
        "es": 'descrita',
    },
    'a escrever': {
        "en-US": 'to be written',
        "es": 'por escribir',
    },
    'Exportar CSV': {
        "en-US": 'Export CSV',
        "es": 'Exportar CSV',
    },
    'Abrir a ficha de {cargo}': {
        "en-US": 'Open the sheet for {cargo}',
        "es": 'Abrir la ficha de {cargo}',
    },
    '{n} funções distintas. “Descrita” marca a função cuja ficha já foi escrita pelo RH; o resto sai só do que a estrutura deduz.': {
        "en-US": '{n} distinct roles. “Described” marks the role whose sheet HR has already written; the rest comes only from what the structure infers.',
        "es": '{n} funciones distintas. «Descrita» marca la función cuya ficha ya escribió RR. HH.; el resto sale solo de lo que la estructura deduce.',
    },
    'V de Cramér com correção de viés (Bergsma, 2013): mede associação entre variáveis categóricas, de 0 a 1. Diz que saber uma reduz a incerteza sobre a outra — não diz que uma causa a outra, e 0,60 não é «60 % de explicação».': {
        "en-US": "Cramér's V with bias correction (Bergsma, 2013): measures association between categorical variables, from 0 to 1. It says that knowing one reduces uncertainty about the other — it does not say one causes the other, and 0.60 is not “60 % explained”.",
        "es": 'V de Cramér con corrección de sesgo (Bergsma, 2013): mide asociación entre variables categóricas, de 0 a 1. Dice que conocer una reduce la incertidumbre sobre la otra — no dice que una cause la otra, y 0,60 no es «60 % de explicación».',
    },
    'Par de variáveis': {
        "en-US": 'Variable pair',
        "es": 'Par de variables',
    },
    'Força': {
        "en-US": 'Strength',
        "es": 'Fuerza',
    },
    'Sem correção': {
        "en-US": 'Uncorrected',
        "es": 'Sin corrección',
    },
    'Categorias': {
        "en-US": 'Categories',
        "es": 'Categorías',
    },
    'Ressalva': {
        "en-US": 'Caveat',
        "es": 'Salvedad',
    },
    'amostra rala': {
        "en-US": 'sparse sample',
        "es": 'muestra escasa',
    },
    '{n} célula(s) com valor esperado abaixo de 5 — regra de Cochran. O número sai, com a ressalva colada nele.': {
        "en-US": "{n} cell(s) with expected value below 5 — Cochran's rule. The number is still shown, with the caveat attached to it.",
        "es": '{n} celda(s) con valor esperado por debajo de 5 — regla de Cochran. El número sale igual, con la salvedad pegada a él.',
    },
    'muito forte': {
        "en-US": 'very strong',
        "es": 'muy fuerte',
    },
    'forte': {
        "en-US": 'strong',
        "es": 'fuerte',
    },
    'moderada': {
        "en-US": 'moderate',
        "es": 'moderada',
    },
    'fraca': {
        "en-US": 'weak',
        "es": 'débil',
    },
    'desprezível': {
        "en-US": 'negligible',
        "es": 'insignificante',
    },
    'Business Unit × papel': {
        "en-US": 'Business Unit × role',
        "es": 'Business Unit × rol',
    },
    'Business Unit × função': {
        "en-US": 'Business Unit × job title',
        "es": 'Business Unit × función',
    },
    'Vertical × papel': {
        "en-US": 'Vertical × role',
        "es": 'Vertical × rol',
    },
    'Vertical × função': {
        "en-US": 'Vertical × job title',
        "es": 'Vertical × función',
    },
    'Setor × papel': {
        "en-US": 'Department × role',
        "es": 'Sector × rol',
    },
    'Vínculo × papel': {
        "en-US": 'Contract type × role',
        "es": 'Vínculo × rol',
    },
    'Total': {
        "en-US": 'Total',
        "es": 'Total',
    },
    'outras ({n})': {
        "en-US": 'others ({n})',
        "es": 'otras ({n})',
    },
    'Onde cada função se concentra': {
        "en-US": 'Where each role concentrates',
        "es": 'Dónde se concentra cada función',
    },
    'A matriz de {n} funções por Business Unit tem números demais para ler inteira. Esta é a leitura que sobra: a BU dominante de cada função e o quanto ela pesa. Funções com menos de {piso} pessoas entram agregadas — jogá-las fora faria o total parar de fechar.': {
        "en-US": "A matrix of {n} roles by Business Unit has too many numbers to read whole. This is the reading that remains: each role's dominant BU and how much it weighs. Roles with fewer than {piso} people are aggregated — dropping them would stop the total from adding up.",
        "es": 'Una matriz de {n} funciones por Business Unit tiene demasiados números para leerla entera. Esta es la lectura que queda: la BU dominante de cada función y cuánto pesa. Las funciones con menos de {piso} personas entran agregadas — descartarlas haría que el total dejara de cuadrar.',
    },
    'BU dominante': {
        "en-US": 'Dominant BU',
        "es": 'BU dominante',
    },
    'Concentração': {
        "en-US": 'Concentration',
        "es": 'Concentración',
    },
    'BUs em que aparece': {
        "en-US": 'BUs it appears in',
        "es": 'BUs en que aparece',
    },
    'Diretos': {
        "en-US": 'Direct reports',
        "es": 'Directos',
    },
    'Amplitude medida na árvore': {
        "en-US": 'Span measured on the tree',
        "es": 'Amplitud medida en el árbol',
    },
    'Subordinados diretos de cada gestor, contados na estrutura. O contraponto da tabela acima, que conta por cadastro: onde os dois números divergem muito, há gente pendurada num centro de custo que não é o de quem a lidera — e isso é achado de dado, não de organização.': {
        "en-US": "Direct reports per manager, counted on the structure. The counterpoint to the table above, which counts by registry: where the two numbers diverge sharply, there are people hanging on a cost centre that is not their leader's — and that is a data finding, not an org one.",
        "es": 'Subordinados directos de cada gestor, contados en la estructura. El contrapunto de la tabla anterior, que cuenta por registro: donde los dos números divergen mucho, hay gente colgada de un centro de costo que no es el de quien la lidera — y eso es hallazgo de dato, no de organización.',
    },
    '{d} de {p} pessoas declararam alguma competência ({c} %). A cobertura vem antes de qualquer célula: numa área onde 8 de 30 preencheram, a matriz descreve os 8 — e não a área.': {
        "en-US": '{d} of {p} people declared at least one competency ({c} %). Coverage comes before any cell: in an area where 8 out of 30 filled it in, the matrix describes the 8 — not the area.',
        "es": '{d} de {p} personas declararon alguna competencia ({c} %). La cobertura viene antes de cualquier celda: en un área donde 8 de 30 completaron, la matriz describe a los 8 — y no al área.',
    },
    'Nenhuma competência declarada neste recorte. O campo existe no cadastro de cada pessoa e na carga da planilha; enquanto ninguém o preenche, a matriz não tem o que cruzar.': {
        "en-US": "No competency declared in this selection. The field exists in each person's record and in the spreadsheet load; while nobody fills it in, the matrix has nothing to cross.",
        "es": 'Ninguna competencia declarada en este recorte. El campo existe en el registro de cada persona y en la carga de la planilla; mientras nadie lo complete, la matriz no tiene qué cruzar.',
    },
    'Mostrando as {n} competências mais frequentes; outras {o} ficaram de fora da matriz.': {
        "en-US": 'Showing the {n} most frequent competencies; another {o} were left out of the matrix.',
        "es": 'Mostrando las {n} competencias más frecuentes; otras {o} quedaron fuera de la matriz.',
    },
    'Cobertura': {
        "en-US": 'Coverage',
        "es": 'Cobertura',
    },
    'Rev': {
        "en-US": 'Rev',
        "es": 'Rev',
    },
    'Cargo fora do recorte': {
        "en-US": 'Job title outside the selection',
        "es": 'Cargo fuera del recorte',
    },
    'Essa função não existe na estrutura vigente ou está fora do filtro atual. Cargo some da base a cada carga da planilha — um link guardado para uma ficha antiga cai aqui.': {
        "en-US": 'This role does not exist in the current structure or is outside the active filter. Job titles disappear from the base at every spreadsheet load — a saved link to an old sheet lands here.',
        "es": 'Esa función no existe en la estructura vigente o está fuera del filtro actual. El cargo desaparece de la base en cada carga de la planilla — un enlace guardado de una ficha antigua cae aquí.',
    },
    'Missão do Cargo': {
        "en-US": 'Job Mission',
        "es": 'Misión del Cargo',
    },
    'Principais Responsabilidades': {
        "en-US": 'Main Responsibilities',
        "es": 'Principales Responsabilidades',
    },
    'Requisitos Desejáveis': {
        "en-US": 'Desirable Requirements',
        "es": 'Requisitos Deseables',
    },
    'Competências Desejáveis': {
        "en-US": 'Desirable Competencies',
        "es": 'Competencias Deseables',
    },
    'Valores': {
        "en-US": 'Values',
        "es": 'Valores',
    },
    'Acreditamos que só crescemos juntos.': {
        "en-US": 'We believe we only grow together.',
        "es": 'Creemos que solo crecemos juntos.',
    },
    'Somos abertos e acolhemos as diferenças.': {
        "en-US": 'We are open and we welcome differences.',
        "es": 'Somos abiertos y acogemos las diferencias.',
    },
    'Superamos nossos desafios.': {
        "en-US": 'We overcome our challenges.',
        "es": 'Superamos nuestros desafíos.',
    },
    'Somos conscientes e protagonistas.': {
        "en-US": 'We are aware and we take the lead.',
        "es": 'Somos conscientes y protagonistas.',
    },
    'deduzido da estrutura': {
        "en-US": 'inferred from the structure',
        "es": 'deducido de la estructura',
    },
    'escrito pelo RH': {
        "en-US": 'written by HR',
        "es": 'escrito por RR. HH.',
    },
    'Extraído do que está gravado na estrutura. É ponto de partida para o RH escrever, não texto aprovado.': {
        "en-US": 'Extracted from what is stored in the structure. It is a starting point for HR to write from, not approved text.',
        "es": 'Extraído de lo que está guardado en la estructura. Es punto de partida para que RR. HH. escriba, no texto aprobado.',
    },
    'não preenchida — escreva abaixo': {
        "en-US": 'not filled in — write it below',
        "es": 'sin completar — escriba abajo',
    },
    'O que a estrutura diz sobre este cargo': {
        "en-US": 'What the structure says about this job title',
        "es": 'Lo que la estructura dice sobre este cargo',
    },
    'Ocupações': {
        "en-US": 'Occupancies',
        "es": 'Ocupaciones',
    },
    'Subordinados diretos': {
        "en-US": 'Direct reports',
        "es": 'Subordinados directos',
    },
    'Ocupam hoje': {
        "en-US": 'Currently held by',
        "es": 'Ocupan hoy',
    },
    'Escrever a ficha': {
        "en-US": 'Write the sheet',
        "es": 'Escribir la ficha',
    },
    'Uma linha por item nas três listas. O que for escrito aqui substitui o texto deduzido no documento e no PDF — o deduzido continua visível acima, como sugestão.': {
        "en-US": 'One line per item in the three lists. What is written here replaces the inferred text in the document and in the PDF — the inferred one stays visible above, as a suggestion.',
        "es": 'Una línea por ítem en las tres listas. Lo que se escriba aquí sustituye al texto deducido en el documento y en el PDF — el deducido sigue visible arriba, como sugerencia.',
    },
    'A missão do {cargo} é contribuir para…': {
        "en-US": 'The mission of the {cargo} is to contribute to…',
        "es": 'La misión del {cargo} es contribuir a…',
    },
    'Uma responsabilidade por linha.': {
        "en-US": 'One responsibility per line.',
        "es": 'Una responsabilidad por línea.',
    },
    'Formação, experiência e disponibilidade — um por linha. Nada disto se deduz do organograma.': {
        "en-US": 'Education, experience and availability — one per line. None of this can be inferred from the org chart.',
        "es": 'Formación, experiencia y disponibilidad — uno por línea. Nada de esto se deduce del organigrama.',
    },
    'Uma competência por linha.': {
        "en-US": 'One competency per line.',
        "es": 'Una competencia por línea.',
    },
    'Gravar a ficha': {
        "en-US": 'Save the sheet',
        "es": 'Guardar la ficha',
    },
    'Skills de “{cargo}” gravado — {n} de 4 seções preenchidas.': {
        "en-US": 'Skills for “{cargo}” saved — {n} of 4 sections filled in.',
        "es": 'Skills de «{cargo}» guardado — {n} de 4 secciones completadas.',
    },
    'Esse cargo não existe no recorte atual. Nada foi gravado.': {
        "en-US": 'This job title does not exist in the current selection. Nothing was saved.',
        "es": 'Ese cargo no existe en el recorte actual. No se guardó nada.',
    },
    'Skills emitido em PDF': {
        "en-US": 'Skills issued as PDF',
        "es": 'Skills emitido en PDF',
    },
    '{codigo} · Rev {rev} · formulário controlado': {
        "en-US": '{codigo} · Rev {rev} · controlled form',
        "es": '{codigo} · Rev {rev} · formulario controlado',
    },
    'base inteira': {
        "en-US": 'whole base',
        "es": 'base entera',
    },
    "A agenda do ano": {
        "en-US": "The year's schedule",
        "es": "La agenda del año",
    },
    "A autoavaliação e a conversa do líder com cada liderado. Três abas: Completa, Check-in 1 e Check-in 2.": {
        "en-US": "Self-assessment and the leader's conversation with each team member. Three tabs: Complete, Check-in 1 and Check-in 2.",
        "es": "La autoevaluación y la conversación del líder con cada colaborador. Tres pestañas: Completa, Check-in 1 y Check-in 2.",
    },
    "A liderança usa o formulário como preparação — um arquivo por pessoa — e agenda cada Conversa de Valor. O colaborador faz a autoavaliação e prepara o feedback para a liderança direta.": {
        "en-US": "Leadership uses the form to prepare — one file per person — and schedules each Value Conversation. The employee self-assesses and prepares feedback for their direct leader.",
        "es": "El liderazgo usa el formulario como preparación —un archivo por persona— y agenda cada Conversación de Valor. El colaborador se autoevalúa y prepara la retroalimentación para su líder directo.",
    },
    "A necessidade por trás do sentimento.": {
        "en-US": "The need behind the feeling.",
        "es": "La necesidad detrás del sentimiento.",
    },
    "Abrir PDF": {
        "en-US": "Open PDF",
        "es": "Abrir PDF",
    },
    "Abrir a Conversa de Valor de {nome}": {
        "en-US": "Open {nome}'s Value Conversation",
        "es": "Abrir la Conversación de Valor de {nome}",
    },
    "Abrir o passo a passo": {
        "en-US": "Open the walkthrough",
        "es": "Abrir el paso a paso",
    },
    "Aderência aos Valores Organizacionais": {
        "en-US": "Adherence to Organizational Values",
        "es": "Adherencia a los Valores Organizacionales",
    },
    "Agenda de pessoas": {
        "en-US": "People schedule",
        "es": "Agenda de personas",
    },
    "Agenda {ano}": {
        "en-US": "{ano} schedule",
        "es": "Agenda {ano}",
    },
    "Agendada": {
        "en-US": "Scheduled",
        "es": "Agendada",
    },
    "Aprender com os outros: ensinar, observar, modelar.": {
        "en-US": "Learn from others: teaching, observing, modeling.",
        "es": "Aprender de los demás: enseñar, observar, modelar.",
    },
    "Aprender fazendo: colocar o conhecimento em prática, experimentando.": {
        "en-US": "Learn by doing: putting knowledge into practice, experimenting.",
        "es": "Aprender haciendo: poner el conocimiento en práctica, experimentando.",
    },
    "Aprender por cursos, leitura, documentários e vídeos.": {
        "en-US": "Learn through courses, reading, documentaries and videos.",
        "es": "Aprender mediante cursos, lectura, documentales y vídeos.",
    },
    "Aprendizado experimental": {
        "en-US": "Experiential learning",
        "es": "Aprendizaje experiencial",
    },
    "Aprendizado formal": {
        "en-US": "Formal learning",
        "es": "Aprendizaje formal",
    },
    "Aprendizado social": {
        "en-US": "Social learning",
        "es": "Aprendizaje social",
    },
    "Assume riscos calculados e está à frente das mudanças necessárias.": {
        "en-US": "Takes calculated risks and leads the necessary changes.",
        "es": "Asume riesgos calculados y está al frente de los cambios necesarios.",
    },
    "Atitude de dono": {
        "en-US": "Ownership",
        "es": "Actitud de dueño",
    },
    "Baixar modelo": {
        "en-US": "Download template",
        "es": "Descargar plantilla",
    },
    "Banco não configurado: o acompanhamento vive no estado de trabalho. Ligue o PostgreSQL (aba Configurações) para o histórico atravessar anos.": {
        "en-US": "Database not configured: tracking lives in the working state. Enable PostgreSQL (Settings tab) for the history to span years.",
        "es": "Base de datos no configurada: el seguimiento vive en el estado de trabajo. Active PostgreSQL (pestaña Configuración) para que el historial atraviese los años.",
    },
    "Conversa de Valor": {
        "en-US": "Value Conversation",
        "es": "Conversación de Valor",
    },
    "Conversa de Valor Completa": {
        "en-US": "Complete Value Conversation",
        "es": "Conversación de Valor Completa",
    },
    "Conversa de Valor emitido em PDF": {
        "en-US": "Value Conversation exported as PDF",
        "es": "Conversación de Valor emitida en PDF",
    },
    "Conversa de Valor — Conversas que Geram Valor": {
        "en-US": "Value Conversation — Value-Generating Conversations",
        "es": "Conversación de Valor — Conversaciones que Generan Valor",
    },
    "Cada líder conduz as três conversas de cada liderado. A ordem começa por quem tem menos caminho andado — é onde o processo precisa de empurrão.": {
        "en-US": "Each leader runs the three conversations for each team member. The order starts with whoever is furthest behind — where the process needs a push.",
        "es": "Cada líder conduce las tres conversaciones de cada colaborador. El orden empieza por quien tiene menos camino recorrido — donde el proceso necesita un empujón.",
    },
    "Check-in 1": {
        "en-US": "Check-in 1",
        "es": "Check-in 1",
    },
    "Check-in 2": {
        "en-US": "Check-in 2",
        "es": "Check-in 2",
    },
    "Cobertura por ciclo": {
        "en-US": "Coverage by cycle",
        "es": "Cobertura por ciclo",
    },
    "Como isso faz você se sentir.": {
        "en-US": "How that makes you feel.",
        "es": "Cómo te hace sentir eso.",
    },
    "Comportamentos do dia a dia que endossam os valores GPlanSiS. Quais são pontos fortes a potencializar e quais merecem mais atenção.": {
        "en-US": "Everyday behaviors that embody the GPlanSiS values. Which are strengths to build on and which deserve more attention.",
        "es": "Comportamientos cotidianos que respaldan los valores GPlanSiS. Cuáles son fortalezas a potenciar y cuáles merecen más atención.",
    },
    "Comunicação Não-Violenta: observação, sentimento, necessidade e pedido. O exemplo do manual, na íntegra.": {
        "en-US": "Nonviolent Communication: observation, feeling, need and request. The manual's example, in full.",
        "es": "Comunicación No Violenta: observación, sentimiento, necesidad y petición. El ejemplo del manual, íntegro.",
    },
    "Conclusão": {
        "en-US": "Completion",
        "es": "Conclusión",
    },
    "Constrói relações de confiança e respeito com a equipe.": {
        "en-US": "Builds relationships of trust and respect with the team.",
        "es": "Construye relaciones de confianza y respeto con el equipo.",
    },
    "Contrata pessoas alinhadas com os valores da empresa.": {
        "en-US": "Hires people aligned with the company's values.",
        "es": "Contrata personas alineadas con los valores de la empresa.",
    },
    "Conversas": {
        "en-US": "Conversations",
        "es": "Conversaciones",
    },
    "Conversas anteriores": {
        "en-US": "Previous conversations",
        "es": "Conversaciones anteriores",
    },
    "Conversas que Geram Valor": {
        "en-US": "Value-Generating Conversations",
        "es": "Conversaciones que Generan Valor",
    },
    "Dar e receber feedback tem a ver com aprendizado e crescimento — intenção positiva.": {
        "en-US": "Giving and receiving feedback is about learning and growth — positive intent.",
        "es": "Dar y recibir retroalimentación tiene que ver con aprendizaje y crecimiento — intención positiva.",
    },
    "Data": {
        "en-US": "Date",
        "es": "Fecha",
    },
    "Define a estratégia, os objetivos e as metas da equipe e se responsabiliza pelos resultados.": {
        "en-US": "Sets the team's strategy, objectives and goals and takes responsibility for the results.",
        "es": "Define la estrategia, los objetivos y las metas del equipo y se responsabiliza por los resultados.",
    },
    "Delega tarefas de forma eficaz, conforme a competência e a maturidade de cada pessoa.": {
        "en-US": "Delegates tasks effectively, according to each person's competence and maturity.",
        "es": "Delega tareas de forma eficaz, según la competencia y la madurez de cada persona.",
    },
    "Encerramento": {
        "en-US": "Closing",
        "es": "Cierre",
    },
    "Enfatizar a perspectiva de pontos fortes — nossas qualidades como recursos para lidar com os desafios.": {
        "en-US": "Emphasize strengths — our qualities as resources to face challenges.",
        "es": "Enfatizar la perspectiva de fortalezas — nuestras cualidades como recursos para afrontar los desafíos.",
    },
    "Entregas e Resultados": {
        "en-US": "Deliveries and Results",
        "es": "Entregas y Resultados",
    },
    "Essa matrícula não existe na estrutura vigente ou está fora do filtro atual. Pessoa some da base a cada carga — um link guardado cai aqui.": {
        "en-US": "This ID doesn't exist in the current structure or is outside the active filter. People drop from the base on each load — a saved link lands here.",
        "es": "Ese registro no existe en la estructura vigente o está fuera del filtro actual. Una persona sale de la base en cada carga — un enlace guardado cae aquí.",
    },
    "Essa pessoa não existe no recorte atual. Nada foi gravado.": {
        "en-US": "This person doesn't exist in the current selection. Nothing was saved.",
        "es": "Esa persona no existe en la selección actual. No se guardó nada.",
    },
    "Estabelece expectativas claras e faz acompanhamento.": {
        "en-US": "Sets clear expectations and follows up.",
        "es": "Establece expectativas claras y hace seguimiento.",
    },
    "Estrutura do feedback (CNV)": {
        "en-US": "Feedback structure (NVC)",
        "es": "Estructura de la retroalimentación (CNV)",
    },
    "Eu observei que o relatório não sairá no prazo combinado": {
        "en-US": "I observed that the report won't be ready by the agreed deadline",
        "es": "Observé que el informe no saldrá en el plazo acordado",
    },
    "Expectativa de Carreira": {
        "en-US": "Career Expectations",
        "es": "Expectativa de Carrera",
    },
    "Feedback, aprendabilidade e o processo Conversa de Valor, por Marina Albuquerque Sá — rev. junho 2026.": {
        "en-US": "Feedback, learnability and the Value Conversation process, by Marina Albuquerque Sá — rev. June 2026.",
        "es": "Retroalimentación, aprendibilidad y el proceso Conversación de Valor, por Marina Albuquerque Sá — rev. junio 2026.",
    },
    "Ferramentas": {
        "en-US": "Tools",
        "es": "Herramientas",
    },
    "Ferramentas do processo": {
        "en-US": "Process tools",
        "es": "Herramientas del proceso",
    },
    "Formulário da Equipe": {
        "en-US": "Team Form",
        "es": "Formulario del Equipo",
    },
    "Formulário da Liderança": {
        "en-US": "Leadership Form",
        "es": "Formulario del Liderazgo",
    },
    "Gerenciar": {
        "en-US": "Manage",
        "es": "Gestionar",
    },
    "Histórico durável no PostgreSQL: as conversas de anos anteriores vêm do banco e sobrevivem à reimportação da base.": {
        "en-US": "Durable history in PostgreSQL: conversations from previous years come from the database and survive a base reimport.",
        "es": "Historial duradero en PostgreSQL: las conversaciones de años anteriores vienen de la base de datos y sobreviven a la reimportación de la base.",
    },
    "Imaginar-se no lugar do outro em uma situação difícil.": {
        "en-US": "Put yourself in the other person's shoes in a difficult situation.",
        "es": "Ponerse en el lugar del otro en una situación difícil.",
    },
    "Incentiva e apoia o desenvolvimento das pessoas.": {
        "en-US": "Encourages and supports people's development.",
        "es": "Fomenta y apoya el desarrollo de las personas.",
    },
    "Inovação": {
        "en-US": "Innovation",
        "es": "Innovación",
    },
    "Inspira e é exemplo de comportamento.": {
        "en-US": "Inspires and sets an example of behavior.",
        "es": "Inspira y es ejemplo de comportamiento.",
    },
    "Julho": {
        "en-US": "July",
        "es": "Julio",
    },
    "Liderados": {
        "en-US": "Team members",
        "es": "Colaboradores",
    },
    "Liderar": {
        "en-US": "Lead",
        "es": "Liderar",
    },
    "Líder": {
        "en-US": "Leader",
        "es": "Líder",
    },
    "Líder direto": {
        "en-US": "Direct leader",
        "es": "Líder directo",
    },
    "MANUAL": {
        "en-US": "MANUAL",
        "es": "MANUAL",
    },
    "Manual completo": {
        "en-US": "Full manual",
        "es": "Manual completo",
    },
    "Março e Abril": {
        "en-US": "March and April",
        "es": "Marzo y Abril",
    },
    "Nenhuma Conversa de Valor realizada em anos anteriores — ou o banco ainda não tem esse histórico.": {
        "en-US": "No Value Conversation done in previous years — or the database doesn't have that history yet.",
        "es": "Ninguna Conversación de Valor realizada en años anteriores — o la base de datos aún no tiene ese historial.",
    },
    "Nenhuma pessoa neste recorte. Afrouxe o filtro para ver a agenda.": {
        "en-US": "No people in this selection. Loosen the filter to see the schedule.",
        "es": "Ninguna persona en esta selección. Afloje el filtro para ver la agenda.",
    },
    "Novembro": {
        "en-US": "November",
        "es": "Noviembre",
    },
    "O Plano de Desenvolvimento Individual acelera o crescimento por ações estruturadas. Priorizar até três competências, factíveis.": {
        "en-US": "The Individual Development Plan accelerates growth through structured actions. Prioritize up to three feasible competencies.",
        "es": "El Plan de Desarrollo Individual acelera el crecimiento mediante acciones estructuradas. Priorizar hasta tres competencias, factibles.",
    },
    "O colaborador começa pela autoavaliação. A liderança contribui com suas observações. Registra-se a versão final de consenso. O colaborador dá feedback à liderança pelo formulário GEP-FOR-005.": {
        "en-US": "The employee starts with the self-assessment. Leadership adds its observations. The final consensus version is recorded. The employee gives feedback to leadership via form GEP-FOR-005.",
        "es": "El colaborador empieza por la autoevaluación. El liderazgo aporta sus observaciones. Se registra la versión final de consenso. El colaborador da retroalimentación al liderazgo mediante el formulario GEP-FOR-005.",
    },
    "O colaborador envia à liderança o formulário da liderança. A liderança encaminha ao RH e ao colaborador a versão final do feedback e o que recebeu. O colaborador recebe a versão enviada ao RH.": {
        "en-US": "The employee sends leadership the leadership form. Leadership forwards to HR and to the employee the final feedback version and what it received. The employee receives the version sent to HR.",
        "es": "El colaborador envía al liderazgo el formulario del liderazgo. El liderazgo remite a RR. HH. y al colaborador la versión final de la retroalimentación y lo que recibió. El colaborador recibe la versión enviada a RR. HH.",
    },
    "O feedback deve olhar para frente.": {
        "en-US": "Feedback should look forward.",
        "es": "La retroalimentación debe mirar hacia adelante.",
    },
    "O feedback estruturado da casa, três vezes ao ano. A agenda é montada da estrutura vigente; o acompanhamento é gravado por pessoa, ano e ciclo.": {
        "en-US": "The company's structured feedback, three times a year. The schedule is built from the current structure; tracking is saved by person, year and cycle.",
        "es": "La retroalimentación estructurada de la casa, tres veces al año. La agenda se arma de la estructura vigente; el seguimiento se guarda por persona, año y ciclo.",
    },
    "O feedback que o liderado dá à liderança direta, sobre Liderar, Gerenciar e Responsabilizar-se.": {
        "en-US": "The feedback the team member gives to their direct leader, on Lead, Manage and Take Responsibility.",
        "es": "La retroalimentación que el colaborador da a su líder directo, sobre Liderar, Gestionar y Responsabilizarse.",
    },
    "O que aconteceu, sem julgamento.": {
        "en-US": "What happened, without judgment.",
        "es": "Lo que ocurrió, sin juicio.",
    },
    "O que podemos fazer para entregar até sexta?": {
        "en-US": "What can we do to deliver by Friday?",
        "es": "¿Qué podemos hacer para entregar el viernes?",
    },
    "O roteiro da Conversa de Valor Completa, no formulário da equipe (GEP-FOR-006).": {
        "en-US": "The Complete Value Conversation script, in the team form (GEP-FOR-006).",
        "es": "El guion de la Conversación de Valor Completa, en el formulario del equipo (GEP-FOR-006).",
    },
    "Oferece feedback constante e construtivo.": {
        "en-US": "Offers constant, constructive feedback.",
        "es": "Ofrece retroalimentación constante y constructiva.",
    },
    "Oferecer ajuda para contribuir com o processo de aprendizado.": {
        "en-US": "Offer help to support the learning process.",
        "es": "Ofrecer ayuda para contribuir al proceso de aprendizaje.",
    },
    "Os formulários oficiais em Excel, o manual completo em PDF e o passo a passo interativo. O sistema não importa as planilhas: elas são o modelo que cada um preenche e envia ao RH, como o manual manda.": {
        "en-US": "The official Excel forms, the full manual in PDF and the interactive walkthrough. The system doesn't import the spreadsheets: they are the template each person fills in and sends to HR, as the manual requires.",
        "es": "Los formularios oficiales en Excel, el manual completo en PDF y el paso a paso interactivo. El sistema no importa las planillas: son la plantilla que cada uno completa y envía a RR. HH., como indica el manual.",
    },
    "Os próximos passos desejados e como a organização pode apoiar. As etapas de desenvolvimento e o plano para alcançar a meta.": {
        "en-US": "The desired next steps and how the organization can support them. The development stages and the plan to reach the goal.",
        "es": "Los próximos pasos deseados y cómo la organización puede apoyar. Las etapas de desarrollo y el plan para alcanzar la meta.",
    },
    "Os quatro elementos da conversa": {
        "en-US": "The four elements of the conversation",
        "es": "Los cuatro elementos de la conversación",
    },
    "PDI — Plano de Desenvolvimento Individual": {
        "en-US": "IDP — Individual Development Plan",
        "es": "PDI — Plan de Desarrollo Individual",
    },
    "Passo a passo interativo": {
        "en-US": "Interactive walkthrough",
        "es": "Paso a paso interactivo",
    },
    "Pendente": {
        "en-US": "Pending",
        "es": "Pendiente",
    },
    "Pessoa fora do recorte": {
        "en-US": "Person outside the selection",
        "es": "Persona fuera de la selección",
    },
    "Por líder": {
        "en-US": "By leader",
        "es": "Por líder",
    },
    "Preparação": {
        "en-US": "Preparation",
        "es": "Preparación",
    },
    "Principais contribuições do período. Reforçar os aspectos positivos, os aprendizados gerados e as oportunidades — visão de futuro.": {
        "en-US": "Main contributions of the period. Reinforce the positives, the lessons learned and the opportunities — a forward-looking view.",
        "es": "Principales contribuciones del período. Reforzar los aspectos positivos, los aprendizajes generados y las oportunidades — visión de futuro.",
    },
    "Priorizar até três competências, definindo ações no formato 70/20/10 e prazos. O plano deve ser factível; o acompanhamento é do indivíduo, com o suporte da empresa.": {
        "en-US": "Prioritize up to three competencies, defining actions in the 70/20/10 format and deadlines. The plan must be feasible; tracking belongs to the individual, with the company's support.",
        "es": "Priorizar hasta tres competencias, definiendo acciones en el formato 70/20/10 y plazos. El plan debe ser factible; el seguimiento es del individuo, con el apoyo de la empresa.",
    },
    "Promove uma cultura de trabalho positiva e motivadora.": {
        "en-US": "Fosters a positive, motivating work culture.",
        "es": "Promueve una cultura de trabajo positiva y motivadora.",
    },
    "Quanto cada uma das três conversas do ano já foi realizada. Só «realizada» conta — agendada é intenção, não feito.": {
        "en-US": "How much of each of the year's three conversations is done. Only «done» counts — scheduled is intent, not done.",
        "es": "Cuánto se realizó de cada una de las tres conversaciones del año. Solo «realizada» cuenta — agendada es intención, no hecho.",
    },
    "Realizada": {
        "en-US": "Done",
        "es": "Realizada",
    },
    "Realizadas": {
        "en-US": "Done",
        "es": "Realizadas",
    },
    "Referência": {
        "en-US": "Reference",
        "es": "Referencia",
    },
    "Respeito": {
        "en-US": "Respect",
        "es": "Respeto",
    },
    "Responsabilizar-se": {
        "en-US": "Take Responsibility",
        "es": "Responsabilizarse",
    },
    "Régra 70/20/10 — o PDI": {
        "en-US": "70/20/10 rule — the IDP",
        "es": "Regla 70/20/10 — el PDI",
    },
    "Seções da Conversa de Valor": {
        "en-US": "Value Conversation sections",
        "es": "Secciones de la Conversación de Valor",
    },
    "Sistematiza e simplifica os processos para torná-los mais ágeis e eficazes.": {
        "en-US": "Systematizes and simplifies processes to make them more agile and effective.",
        "es": "Sistematiza y simplifica los procesos para hacerlos más ágiles y eficaces.",
    },
    "Toma decisões difíceis em prol do propósito e dos valores da empresa.": {
        "en-US": "Makes tough decisions for the sake of the company's purpose and values.",
        "es": "Toma decisiones difíciles en favor del propósito y los valores de la empresa.",
    },
    "Trabalho em equipe": {
        "en-US": "Teamwork",
        "es": "Trabajo en equipo",
    },
    "Um feedback de qualidade contextualiza a situação observada e a percepção sobre o comportamento.": {
        "en-US": "Quality feedback contextualizes the observed situation and the perception of the behavior.",
        "es": "Una retroalimentación de calidad contextualiza la situación observada y la percepción sobre el comportamiento.",
    },
    "Um guia navegável do processo: os princípios do feedback, a estrutura da CNV, a régua 70/20/10 e a dinâmica das conversas — para quem vai conduzir ou receber uma Conversa de Valor pela primeira vez.": {
        "en-US": "A navigable guide to the process: the feedback principles, the NVC structure, the 70/20/10 rule and the dynamics of the conversations — for those about to run or receive a Value Conversation for the first time.",
        "es": "Una guía navegable del proceso: los principios de la retroalimentación, la estructura de la CNV, la regla 70/20/10 y la dinámica de las conversaciones — para quien va a conducir o recibir una Conversación de Valor por primera vez.",
    },
    "Um pedido ou acordo positivo.": {
        "en-US": "A request or positive agreement.",
        "es": "Una petición o acuerdo positivo.",
    },
    "ano": {
        "en-US": "year",
        "es": "año",
    },
    "cargo à época": {
        "en-US": "job title at the time",
        "es": "cargo en su momento",
    },
    "conclusão": {
        "en-US": "completion",
        "es": "conclusión",
    },
    "conversas no ano": {
        "en-US": "conversations in the year",
        "es": "conversaciones en el año",
    },
    "e isso me deixa preocupado, porque": {
        "en-US": "and that worries me, because",
        "es": "y eso me preocupa, porque",
    },
    "gravado no banco e no estado": {
        "en-US": "saved to the database and the state",
        "es": "guardado en la base de datos y en el estado",
    },
    "gravado no estado de trabalho": {
        "en-US": "saved to the working state",
        "es": "guardado en el estado de trabajo",
    },
    "líder": {
        "en-US": "leader",
        "es": "líder",
    },
    "líderes": {
        "en-US": "leaders",
        "es": "líderes",
    },
    "necessidade": {
        "en-US": "need",
        "es": "necesidad",
    },
    "observação": {
        "en-US": "observation",
        "es": "observación",
    },
    "pedido": {
        "en-US": "request",
        "es": "petición",
    },
    "realizadas": {
        "en-US": "done",
        "es": "realizadas",
    },
    "reservar {n} min por pessoa": {
        "en-US": "reserve {n} min per person",
        "es": "reservar {n} min por persona",
    },
    "sentimento": {
        "en-US": "feeling",
        "es": "sentimiento",
    },
    "{a} agendadas · {p} pendentes": {
        "en-US": "{a} scheduled · {p} pending",
        "es": "{a} agendadas · {p} pendientes",
    },
    "{f} de {t} realizadas": {
        "en-US": "{f} of {t} done",
        "es": "{f} de {t} realizadas",
    },
    "é importante para mim que o prazo seja cumprido, para que os colegas confiem em nós.": {
        "en-US": "it matters to me that the deadline is met, so that our colleagues trust us.",
        "es": "es importante para mí que se cumpla el plazo, para que los colegas confíen en nosotros.",
    },
    "Alternar edição": {
        "en-US": "Toggle editing",
        "es": "Alternar edición",
    },
    "Uma linha por pessoa, em ordem hierárquica: cada líder vem seguido da sua equipe. Os três selos são os ciclos do ano. Clique para registrar ou consultar a conversa.": {
        "en-US": "One row per person, in hierarchical order: each leader is followed by their team. The three chips are the year's cycles. Click to record or review the conversation.",
        "es": "Una fila por persona, en orden jerárquico: cada líder va seguido de su equipo. Los tres sellos son los ciclos del año. Haga clic para registrar o consultar la conversación.",
    },
    "Ação (70/20/10)": {
        "en-US": "Action (70/20/10)",
        "es": "Acción (70/20/10)",
    },
    "Ação — 70% prática · 20% social · 10% formal": {
        "en-US": "Action — 70% practice · 20% social · 10% formal",
        "es": "Acción — 70% práctica · 20% social · 10% formal",
    },
    "Competência": {
        "en-US": "Competency",
        "es": "Competencia",
    },
    "Competência a desenvolver": {
        "en-US": "Competency to develop",
        "es": "Competencia a desarrollar",
    },
    "Comportamento observado neste valor.": {
        "en-US": "Behavior observed for this value.",
        "es": "Comportamiento observado en este valor.",
    },
    "Gravar {ciclo}": {
        "en-US": "Save {ciclo}",
        "es": "Guardar {ciclo}",
    },
    "Prazo": {
        "en-US": "Deadline",
        "es": "Plazo",
    },
    "Principais contribuições do período — pontos fortes e oportunidades.": {
        "en-US": "Main contributions of the period — strengths and opportunities.",
        "es": "Principales contribuciones del período — fortalezas y oportunidades.",
    },
    "Próximos passos desejados e como a organização pode apoiar.": {
        "en-US": "Desired next steps and how the organization can support them.",
        "es": "Próximos pasos deseados y cómo la organización puede apoyar.",
    },
    "Salva na base de dados. Sem depender do Excel.": {
        "en-US": "Saved to the database. No Excel needed.",
        "es": "Se guarda en la base de datos. Sin depender de Excel.",
    },
    "Abrir em tela cheia": {
        "en-US": "Open full screen",
        "es": "Abrir en pantalla completa",
    },
    "Aderência às Competências de Liderança": {
        "en-US": "Adherence to Leadership Competencies",
        "es": "Adherencia a las Competencias de Liderazgo",
    },
    "O dossiê de cultura: os quatro valores lidos como um intertravamento — cada um precisa estar fechado para a entrega energizar — e o LMA, que define quem opera a linha (Liderar, Gerenciar, Responsabilizar-se).": {
        "en-US": "The culture dossier: the four values read as an interlock — each must be closed for delivery to energize — and LMA, which defines who runs the line (Lead, Manage, Take Responsibility).",
        "es": "El dosier de cultura: los cuatro valores leídos como un enclavamiento — cada uno debe estar cerrado para que la entrega se energice — y el LMA, que define quién opera la línea (Liderar, Gestionar, Responsabilizarse).",
    },
    "O que o liderado observa na liderança direta, sobre cada competência.": {
        "en-US": "What the team member observes in their direct leader, for each competency.",
        "es": "Lo que el colaborador observa en su líder directo, sobre cada competencia.",
    },
    "Registro sobre esta competência de liderança.": {
        "en-US": "Note on this leadership competency.",
        "es": "Registro sobre esta competencia de liderazgo.",
    },
    "Valores GPlanSiS e competências de liderança": {
        "en-US": "GPlanSiS values and leadership competencies",
        "es": "Valores GPlanSiS y competencias de liderazgo",
    },
    "{ciclo} de “{nome}” — {n} de 5 elementos · {destino}.": {
        "en-US": "{ciclo} of “{nome}” — {n} of 5 elements · {destino}.",
        "es": "{ciclo} de «{nome}» — {n} de 5 elementos · {destino}.",
    },
    # ---- Evaluación (GEP-FOR-004) ----
    "9-box": {
        "en-US": "9-box",
        "es": "9-box",
    },
    "9-box · {ano}": {
        "en-US": "9-box · {ano}",
        "es": "9-box · {ano}",
    },
    "A leitura de sucessão da casa: risco e impacto de perda, prontidão e a ação imediata. A base vem da estrutura vigente; a leitura é gravada por pessoa e ano.": {
        "en-US": "The company's succession read: risk and impact of loss, readiness and the immediate action. The base comes from the current structure; the read is recorded per person and year.",
        "es": "La lectura de sucesión de la casa: riesgo e impacto de pérdida, preparación y la acción inmediata. La base viene de la estructura vigente; la lectura se registra por persona y año.",
    },
    "A pauta que sai do Mapa: os indicados por ação, cruzados com a prontidão e com a cobertura de Conversa de Valor do ano. A decisão é do comitê; o sistema só reúne o que já sabe.": {
        "en-US": "The agenda drawn from the Map: those nominated by action, cross-referenced with readiness and the year's Value Conversation coverage. The decision is the committee's; the system only gathers what it already knows.",
        "es": "La agenda que sale del Mapa: los indicados por acción, cruzados con la preparación y con la cobertura de Conversación de Valor del año. La decisión es del comité; el sistema solo reúne lo que ya sabe.",
    },
    "Abrir o Mapa de {nome}": {
        "en-US": "Open {nome}'s Map",
        "es": "Abrir el Mapa de {nome}",
    },
    "Alto": {
        "en-US": "High",
        "es": "Alto",
    },
    "Ação Imediata": {
        "en-US": "Immediate Action",
        "es": "Acción Inmediata",
    },
    "Ação imediata": {
        "en-US": "Immediate action",
        "es": "Acción inmediata",
    },
    "Baixo": {
        "en-US": "Low",
        "es": "Bajo",
    },
    "Banco não configurado: o Mapa vive no estado de trabalho. Ligue o PostgreSQL (aba Configurações) para a leitura atravessar anos.": {
        "en-US": "Database not configured: the Map lives in the working state. Turn on PostgreSQL (Settings tab) for the read to span years.",
        "es": "Base de datos no configurada: el Mapa vive en el estado de trabajo. Active PostgreSQL (pestaña Configuración) para que la lectura atraviese años.",
    },
    "Bem-estar": {
        "en-US": "Well-being",
        "es": "Bienestar",
    },
    "Conversa de Valor no ano": {
        "en-US": "Value Conversation this year",
        "es": "Conversación de Valor en el año",
    },
    "Classificação de sucessão": {
        "en-US": "Succession classification",
        "es": "Clasificación de sucesión",
    },
    "Colaboradores · {ano}": {
        "en-US": "Employees · {ano}",
        "es": "Colaboradores · {ano}",
    },
    "Comitê de Meritocracia": {
        "en-US": "Meritocracy Committee",
        "es": "Comité de Meritocracia",
    },
    "DISC, âncoras, estilo de trabalho.": {
        "en-US": "DISC, anchors, work style.",
        "es": "DISC, anclas, estilo de trabajo.",
    },
    "Escrever o Mapa": {
        "en-US": "Write the Map",
        "es": "Escribir el Mapa",
    },
    "Formações e cursos": {
        "en-US": "Education and courses",
        "es": "Formación y cursos",
    },
    "Gravar o Mapa": {
        "en-US": "Save the Map",
        "es": "Guardar el Mapa",
    },
    "Idade": {
        "en-US": "Age",
        "es": "Edad",
    },
    "Impacto": {
        "en-US": "Impact",
        "es": "Impacto",
    },
    "Impacto da perda": {
        "en-US": "Impact of loss",
        "es": "Impacto de la pérdida",
    },
    "Inglês": {
        "en-US": "English",
        "es": "Inglés",
    },
    "Lista": {
        "en-US": "List",
        "es": "Lista",
    },
    "Avaliação": {
        "en-US": "Assessment",
        "es": "Evaluación",
    },
    "Avaliação emitido em PDF": {
        "en-US": "Assessment issued as PDF",
        "es": "Evaluación emitido en PDF",
    },
    "Mapa de “{nome}” gravado — {n} de 8 seções · {destino}.": {
        "en-US": "{nome}'s Map saved — {n} of 8 sections · {destino}.",
        "es": "Mapa de «{nome}» guardado — {n} de 8 secciones · {destino}.",
    },
    "Mapa durável no PostgreSQL: a leitura de anos anteriores vem do banco e sobrevive à reimportação da base.": {
        "en-US": "Durable Map in PostgreSQL: the read of prior years comes from the database and survives re-importing the base.",
        "es": "Mapa duradero en PostgreSQL: la lectura de años anteriores viene de la base de datos y sobrevive a la reimportación de la base.",
    },
    "Matriz 9-box: Risco × Impacto de perda": {
        "en-US": "9-box matrix: Risk × Impact of loss",
        "es": "Matriz 9-box: Riesgo × Impacto de pérdida",
    },
    "Meritocracia": {
        "en-US": "Meritocracy",
        "es": "Meritocracia",
    },
    "Movimentações, promoções, projetos marcantes.": {
        "en-US": "Moves, promotions, standout projects.",
        "es": "Movimientos, promociones, proyectos destacados.",
    },
    "Médio": {
        "en-US": "Medium",
        "es": "Medio",
    },
    "Nenhuma ação imediata registrada neste recorte. Abra as fichas e classifique a «Ação Imediata» para montar a pauta.": {
        "en-US": "No immediate action recorded in this selection. Open the records and classify the “Immediate Action” to build the agenda.",
        "es": "Ninguna acción inmediata registrada en este recorte. Abra las fichas y clasifique la «Acción Inmediata» para armar la agenda.",
    },
    "Nenhuma pessoa neste recorte. Afrouxe o filtro para ver o Mapa.": {
        "en-US": "No one in this selection. Loosen the filter to see the Map.",
        "es": "Ninguna persona en este recorte. Afloje el filtro para ver el Mapa.",
    },
    "Nota da ação": {
        "en-US": "Action note",
        "es": "Nota de la acción",
    },
    "Nível e meta.": {
        "en-US": "Level and goal.",
        "es": "Nivel y meta.",
    },
    "O encaminhamento que a folha propõe para cada pessoa. Alimenta o Comitê de Meritocracia.": {
        "en-US": "The path the sheet proposes for each person. Feeds the Meritocracy Committee.",
        "es": "El encaminamiento que la hoja propone para cada persona. Alimenta el Comité de Meritocracia.",
    },
    "Oportunidades e Potencialidades": {
        "en-US": "Opportunities and Potential",
        "es": "Oportunidades y Potencialidades",
    },
    "Oportunidades e Trilha de Carreira": {
        "en-US": "Opportunities and Career Path",
        "es": "Oportunidades y Trayectoria de Carrera",
    },
    "Outros": {
        "en-US": "Other",
        "es": "Otros",
    },
    "Perfil comportamental": {
        "en-US": "Behavioral profile",
        "es": "Perfil comportamental",
    },
    "Performance": {
        "en-US": "Performance",
        "es": "Desempeño",
    },
    "Por que esta ação, e o que ela pede.": {
        "en-US": "Why this action, and what it calls for.",
        "es": "Por qué esta acción, y qué requiere.",
    },
    "Promoção": {
        "en-US": "Promotion",
        "es": "Promoción",
    },
    "Prontidão": {
        "en-US": "Readiness",
        "es": "Preparación",
    },
    "Prontidão de sucessão": {
        "en-US": "Succession readiness",
        "es": "Preparación para la sucesión",
    },
    "Pronto agora": {
        "en-US": "Ready now",
        "es": "Listo ahora",
    },
    "Pronto em 1 ano": {
        "en-US": "Ready in 1 year",
        "es": "Listo en 1 año",
    },
    "Pronto em 2 anos": {
        "en-US": "Ready in 2 years",
        "es": "Listo en 2 años",
    },
    "Pronto em 3 anos ou +": {
        "en-US": "Ready in 3 years or +",
        "es": "Listo en 3 años o +",
    },
    "Próximo passo na trilha e horizonte.": {
        "en-US": "Next step on the path and time horizon.",
        "es": "Próximo paso en la trayectoria y horizonte.",
    },
    "Quando cada pessoa mapeada estará pronta para o próximo passo. «Pronto agora» é o banco de sucessores imediato.": {
        "en-US": "When each mapped person will be ready for the next step. “Ready now” is the immediate succession pool.",
        "es": "Cuándo cada persona mapeada estará lista para el próximo paso. «Listo ahora» es el banco de sucesores inmediato.",
    },
    "Risco": {
        "en-US": "Risk",
        "es": "Riesgo",
    },
    "Risco de perda": {
        "en-US": "Risk of loss",
        "es": "Riesgo de pérdida",
    },
    "Risco de perda no eixo vertical, impacto da perda no horizontal. O canto Alto × Alto é a retenção urgente. Clique num nome para abrir a ficha.": {
        "en-US": "Risk of loss on the vertical axis, impact of loss on the horizontal. The High × High corner is urgent retention. Click a name to open the record.",
        "es": "Riesgo de pérdida en el eje vertical, impacto de la pérdida en el horizontal. La esquina Alto × Alto es la retención urgente. Haga clic en un nombre para abrir la ficha.",
    },
    "Risco e impacto de perda": {
        "en-US": "Risk and impact of loss",
        "es": "Riesgo e impacto de pérdida",
    },
    "Risco/Impacto": {
        "en-US": "Risk/Impact",
        "es": "Riesgo/Impacto",
    },
    "Rotativo": {
        "en-US": "Rotation",
        "es": "Rotativo",
    },
    "Sem classificar": {
        "en-US": "Unclassified",
        "es": "Sin clasificar",
    },
    "Seções da Avaliação": {
        "en-US": "Assessment sections",
        "es": "Secciones de la Evaluación",
    },
    "Sistemas e ferramentas a desenvolver.": {
        "en-US": "Systems and tools to develop.",
        "es": "Sistemas y herramientas a desarrollar.",
    },
    "Sobre a pessoa": {
        "en-US": "About the person",
        "es": "Sobre la persona",
    },
    "Avaliação": {
        "en-US": "Assessment",
        "es": "Evaluación",
    },
    "Trajetória na empresa": {
        "en-US": "Journey at the company",
        "es": "Trayectoria en la empresa",
    },
    "Trilha de Carreira": {
        "en-US": "Career Path",
        "es": "Trayectoria de Carrera",
    },
    "Trilha de Carreira — posição desejada": {
        "en-US": "Career Path — desired position",
        "es": "Trayectoria de Carrera — posición deseada",
    },
    "Uma linha por pessoa, em ordem hierárquica: cada líder vem seguido da sua equipe. Clique para abrir ou editar o Mapa.": {
        "en-US": "One row per person, in hierarchical order: each leader is followed by their team. Click to open or edit the Map.",
        "es": "Una fila por persona, en orden jerárquico: cada líder viene seguido de su equipo. Haga clic para abrir o editar el Mapa.",
    },
    "cobertura": {
        "en-US": "coverage",
        "es": "cobertura",
    },
    "críticos": {
        "en-US": "critical",
        "es": "críticos",
    },
    "em anos": {
        "en-US": "in years",
        "es": "en años",
    },
    "indicados": {
        "en-US": "nominated",
        "es": "indicados",
    },
    "mapeadas": {
        "en-US": "mapped",
        "es": "mapeadas",
    },
    "ninguém indicado": {
        "en-US": "no one nominated",
        "es": "nadie indicado",
    },
    "não preenchido — clique em Editar": {
        "en-US": "not filled in — click Edit",
        "es": "no completado — haga clic en Editar",
    },
    "opcional — o sistema não deriva; LGPD": {
        "en-US": "optional — the system does not derive it; LGPD",
        "es": "opcional — el sistema no lo deriva; LGPD",
    },
    "prontos agora": {
        "en-US": "ready now",
        "es": "listos ahora",
    },
    "{m} de {t} pessoas classificadas.": {
        "en-US": "{m} of {t} people classified.",
        "es": "{m} de {t} personas clasificadas.",
    },
    "{n} ainda sem leitura de risco/impacto — abra a ficha para posicioná-las.": {
        "en-US": "{n} still without a risk/impact read — open the record to position them.",
        "es": "{n} aún sin lectura de riesgo/impacto — abra la ficha para posicionarlas.",
    },
    "{n} anos": {
        "en-US": "{n} years",
        "es": "{n} años",
    },
    # ---- Evaluación ↔ Conversación de Valor (integração) ----
    "A aderência aos valores vem da Conversa de Valor Completa deste ano — editável lá, exibida aqui, sem redigitar.": {
        "en-US": "Values adherence comes from this year's Full Value Conversation — editable there, shown here, no re-typing.",
        "es": "La adherencia a los valores viene de la Conversación de Valor Completa de este año — editable allá, mostrada aquí, sin redigitar.",
    },
    "O plano de desenvolvimento é o mesmo da Conversa de Valor — editável lá.": {
        "en-US": "The development plan is the same as the Value Conversation's — editable there.",
        "es": "El plan de desarrollo es el mismo de la Conversación de Valor — editable allá.",
    },
    "PDI vindo da Conversa de Valor": {
        "en-US": "PDP from Value Conversation",
        "es": "PDI que viene de la Conversación de Valor",
    },
    "PDI — vindo da Conversa de Valor": {
        "en-US": "PDP — from Value Conversation",
        "es": "PDI — que viene de la Conversación de Valor",
    },
    "da Conversa de Valor": {
        "en-US": "from Value Conversation",
        "es": "de la Conversación de Valor",
    },
    # ---- Peoples Place to Work (Evaluación Maestra / GEP §clima) ----
    "12 por pilar; as 15 marcadas com ★ compõem o pulso semestral. Redação na primeira pessoa, sob a ótica do colaborador; a liderança referida é o gestor direto.": {
        "en-US": "12 per pillar; the 15 marked with ★ make up the semiannual pulse. Written in the first person, from the employee's viewpoint; the leadership referred to is the direct manager.",
        "es": "12 por pilar; las 15 marcadas con ★ componen el pulso semestral. Redacción en primera persona, desde la óptica del colaborador; el liderazgo referido es el gestor directo.",
    },
    "15 afirmações-chave · jul/nov": {
        "en-US": "15 key statements · Jul/Nov",
        "es": "15 afirmaciones clave · jul/nov",
    },
    "60 afirmações · mar/abr": {
        "en-US": "60 statements · Mar/Apr",
        "es": "60 afirmaciones · mar/abr",
    },
    "A alocação de projetos é justa entre as pessoas do time.": {
        "en-US": "Project allocation is fair among the people on the team.",
        "es": "La asignación de proyectos es justa entre las personas del equipo.",
    },
    "A comunicação flui bem entre squads e equipes de projeto, não só dentro da minha área.": {
        "en-US": "Communication flows well between squads and project teams, not just within my area.",
        "es": "La comunicación fluye bien entre squads y equipos de proyecto, no solo dentro de mi área.",
    },
    "A confiança é o pilar estruturante. Todos são medidos sob a ótica do colaborador.": {
        "en-US": "Trust is the structuring pillar. All are measured from the employee's viewpoint.",
        "es": "La confianza es el pilar estructurante. Todos se miden desde la óptica del colaborador.",
    },
    "A empresa apoia meu desenvolvimento de carreira.": {
        "en-US": "The company supports my career development.",
        "es": "La empresa apoya mi desarrollo de carrera.",
    },
    "A empresa investe em quem está começando (estagiários e menos de 1 ano de casa).": {
        "en-US": "The company invests in those just starting (interns and under 1 year here).",
        "es": "La empresa invierte en quienes están empezando (pasantes y menos de 1 año en casa).",
    },
    "A empresa trata todos de forma justa e sem discriminação.": {
        "en-US": "The company treats everyone fairly and without discrimination.",
        "es": "La empresa trata a todos de forma justa y sin discriminación.",
    },
    "A liderança admite quando erra.": {
        "en-US": "Leadership admits when it is wrong.",
        "es": "El liderazgo admite cuando se equivoca.",
    },
    "A liderança age de forma coerente com o que fala.": {
        "en-US": "Leadership acts consistently with what it says.",
        "es": "El liderazgo actúa de forma coherente con lo que dice.",
    },
    "A liderança mantém a equipe informada sobre decisões que nos afetam.": {
        "en-US": "Leadership keeps the team informed about decisions that affect us.",
        "es": "El liderazgo mantiene al equipo informado sobre decisiones que nos afectan.",
    },
    "A liderança se importa com meu bem-estar.": {
        "en-US": "Leadership cares about my well-being.",
        "es": "El liderazgo se preocupa por mi bienestar.",
    },
    "A pesquisa de clima da casa, conduzida internamente, com o rigor de medição que a GPlanSiS|Peoples usa em chão de fábrica. O indicador-mestre é o Peoples Trust Index (PTI).": {
        "en-US": "The company's climate survey, run internally, with the measurement rigor GPlanSiS|Peoples uses on the shop floor. The master indicator is the Peoples Trust Index (PTI).",
        "es": "La encuesta de clima de la casa, conducida internamente, con el rigor de medición que GPlanSiS|Peoples usa en planta. El indicador maestro es el Peoples Trust Index (PTI).",
    },
    "A qualidade das relações interpessoais.": {
        "en-US": "The quality of interpersonal relationships.",
        "es": "La calidad de las relaciones interpersonales.",
    },
    "A remuneração percebida é coerente com a responsabilidade (percepção, não valor).": {
        "en-US": "The pay I perceive is consistent with the responsibility (perception, not amount).",
        "es": "La remuneración percibida es coherente con la responsabilidad (percepción, no valor).",
    },
    "Achado (evidência)": {
        "en-US": "Finding (evidence)",
        "es": "Hallazgo (evidencia)",
    },
    "Afirmação 40": {
        "en-US": "Statement 40",
        "es": "Afirmación 40",
    },
    "Ainda não há respostas neste ciclo. Abra «Responder» para participar — ou divulgue o link da pesquisa.": {
        "en-US": "There are no responses in this cycle yet. Open «Respond» to take part — or share the survey link.",
        "es": "Aún no hay respuestas en este ciclo. Abra «Responder» para participar — o difunda el enlace de la encuesta.",
    },
    "Alerta": {
        "en-US": "Alert",
        "es": "Alerta",
    },
    "Algo que não perguntamos e você gostaria de dizer.": {
        "en-US": "Something we didn't ask that you'd like to say.",
        "es": "Algo que no preguntamos y le gustaría decir.",
    },
    "Alto Desempenho": {
        "en-US": "High Performance",
        "es": "Alto Desempeño",
    },
    "Ambiente forte, com pontos de melhoria pontuais.": {
        "en-US": "Strong environment, with occasional points to improve.",
        "es": "Ambiente fuerte, con puntos de mejora puntuales.",
    },
    "Anexo B — preenchido por cada um dos 44 líderes para o recorte que já lidera na árvore, após a devolutiva. De 3 a 5 iniciativas, factíveis: o mesmo princípio do PDI da Conversa de Valor («priorizar 3»).": {
        "en-US": "Annex B — filled in by each of the 44 leaders for the slice they already lead in the tree, after the debrief. 3 to 5 feasible initiatives: the same principle as the Value Conversation's PDP («prioritize 3»).",
        "es": "Anexo B — completado por cada uno de los 44 líderes para el recorte que ya lidera en el árbol, tras la devolutiva. De 3 a 5 iniciativas, factibles: el mismo principio del PDI de la Conversación de Valor («priorizar 3»).",
    },
    "Anonimato e LGPD": {
        "en-US": "Anonymity and LGPD",
        "es": "Anonimato y LGPD",
    },
    "Anônima por construção": {
        "en-US": "Anonymous by design",
        "es": "Anónima por construcción",
    },
    "Anônima. Nenhuma resposta é ligada a você — o sistema guarda só o estrato e as marcações. Leva poucos minutos.": {
        "en-US": "Anonymous. No response is tied to you — the system keeps only the stratum and the ratings. It takes a few minutes.",
        "es": "Anónima. Ninguna respuesta se vincula a usted — el sistema guarda solo el estrato y las marcaciones. Lleva pocos minutos.",
    },
    "As 60 afirmações (Anexo A)": {
        "en-US": "The 60 statements (Annex A)",
        "es": "Las 60 afirmaciones (Anexo A)",
    },
    "As mudanças de rota em projetos são explicadas, não apenas impostas.": {
        "en-US": "Changes of course in projects are explained, not just imposed.",
        "es": "Los cambios de rumbo en proyectos se explican, no solo se imponen.",
    },
    "As pessoas aqui se importam umas com as outras.": {
        "en-US": "People here care about one another.",
        "es": "Las personas aquí se preocupan unas por otras.",
    },
    "As promessas e combinados feitos pela liderança são cumpridos.": {
        "en-US": "Promises and agreements made by leadership are kept.",
        "es": "Las promesas y acuerdos hechos por el liderazgo se cumplen.",
    },
    "As relações no trabalho são autênticas.": {
        "en-US": "Relationships at work are authentic.",
        "es": "Las relaciones en el trabajo son auténticas.",
    },
    "As soluções que construímos me deixam orgulhoso.": {
        "en-US": "The solutions we build make me proud.",
        "es": "Las soluciones que construimos me enorgullecen.",
    },
    "Atual": {
        "en-US": "Current",
        "es": "Actual",
    },
    "Auditoria (cargas datadas)": {
        "en-US": "Audit (dated loads)",
        "es": "Auditoría (cargas fechadas)",
    },
    "Auditoria / Ledger": {
        "en-US": "Audit / Ledger",
        "es": "Auditoría / Ledger",
    },
    "Banco não configurado: as respostas vivem no estado de trabalho. Ligue o PostgreSQL (aba Configurações) para acumular ciclos.": {
        "en-US": "Database not configured: responses live in the working state. Turn on PostgreSQL (Settings tab) to accumulate cycles.",
        "es": "Base de datos no configurada: las respuestas viven en el estado de trabajo. Active PostgreSQL (pestaña Configuración) para acumular ciclos.",
    },
    "Base sólida, exige planos de ação estruturados.": {
        "en-US": "Solid base, requires structured action plans.",
        "es": "Base sólida, exige planes de acción estructurados.",
    },
    "Cada KPI aponta para onde já é medido no GPlanSiS|Peoples — a mesma fonte única do resto da gestão de pessoas.": {
        "en-US": "Each KPI points to where it is already measured in GPlanSiS|Peoples — the same single source as the rest of people management.",
        "es": "Cada KPI apunta a donde ya se mide en GPlanSiS|Peoples — la misma fuente única del resto de la gestión de personas.",
    },
    "Camaradagem": {
        "en-US": "Camaraderie",
        "es": "Compañerismo",
    },
    "Campo": {
        "en-US": "Field",
        "es": "Campo",
    },
    "Celebramos as conquistas juntos.": {
        "en-US": "We celebrate achievements together.",
        "es": "Celebramos los logros juntos.",
    },
    "Clima por segmento": {
        "en-US": "Climate by segment",
        "es": "Clima por segmento",
    },
    "Cobertura de Conversa de Valor do ciclo": {
        "en-US": "Value Conversation coverage for the cycle",
        "es": "Cobertura de Conversación de Valor del ciclo",
    },
    "Como é a integração entre áreas/projetos na sua visão?": {
        "en-US": "How is the integration between areas/projects in your view?",
        "es": "¿Cómo es la integración entre áreas/proyectos en su visión?",
    },
    "Concordo": {
        "en-US": "Agree",
        "es": "De acuerdo",
    },
    "Concordo totalmente": {
        "en-US": "Strongly agree",
        "es": "Totalmente de acuerdo",
    },
    "Confio nas informações que a empresa divulga internamente.": {
        "en-US": "I trust the information the company shares internally.",
        "es": "Confío en la información que la empresa divulga internamente.",
    },
    "Conflitos são resolvidos de forma imparcial.": {
        "en-US": "Conflicts are resolved impartially.",
        "es": "Los conflictos se resuelven de forma imparcial.",
    },
    "Consigo equilibrar vida pessoal e profissional, considerando viagens e deslocamentos a cliente.": {
        "en-US": "I can balance personal and professional life, considering travel and client trips.",
        "es": "Consigo equilibrar la vida personal y profesional, considerando viajes y desplazamientos a cliente.",
    },
    "Conteúdo": {
        "en-US": "Content",
        "es": "Contenido",
    },
    "Conto com meus colegas quando preciso de ajuda.": {
        "en-US": "I can count on my colleagues when I need help.",
        "es": "Cuento con mis colegas cuando necesito ayuda.",
    },
    "Credibilidade": {
        "en-US": "Credibility",
        "es": "Credibilidad",
    },
    "Crítico": {
        "en-US": "Critical",
        "es": "Crítico",
    },
    "Cultura de referência, candidata a benchmarks externos.": {
        "en-US": "Reference culture, a candidate for external benchmarks.",
        "es": "Cultura de referencia, candidata a benchmarks externos.",
    },
    "Descreva um momento em que se sentiu valorizado.": {
        "en-US": "Describe a moment when you felt valued.",
        "es": "Describa un momento en que se sintió valorado.",
    },
    "Descrição": {
        "en-US": "Description",
        "es": "Descripción",
    },
    "Devolutiva": {
        "en-US": "Debrief",
        "es": "Devolutiva",
    },
    "Discordo": {
        "en-US": "Disagree",
        "es": "En desacuerdo",
    },
    "Discordo totalmente": {
        "en-US": "Strongly disagree",
        "es": "Totalmente en desacuerdo",
    },
    "Em Desenvolvimento": {
        "en-US": "Developing",
        "es": "En Desarrollo",
    },
    "Enviar resposta anônima": {
        "en-US": "Submit anonymous response",
        "es": "Enviar respuesta anónima",
    },
    "Escala": {
        "en-US": "Scale",
        "es": "Escala",
    },
    "Escala Likert de 5 pontos": {
        "en-US": "5-point Likert scale",
        "es": "Escala Likert de 5 puntos",
    },
    "Esta pesquisa": {
        "en-US": "This survey",
        "es": "Esta encuesta",
    },
    "Excelência": {
        "en-US": "Excellence",
        "es": "Excelencia",
    },
    "Existe informalidade saudável no dia a dia.": {
        "en-US": "There is healthy informality day to day.",
        "es": "Existe informalidad saludable en el día a día.",
    },
    "Faixa do PTI": {
        "en-US": "PTI range",
        "es": "Rango del PTI",
    },
    "Falo bem da empresa para pessoas de fora.": {
        "en-US": "I speak well of the company to outsiders.",
        "es": "Hablo bien de la empresa con personas de fuera.",
    },
    "Fonte": {
        "en-US": "Source",
        "es": "Fuente",
    },
    "Forças e oportunidades aparecem quando há respostas suficientes (piso de {n}).": {
        "en-US": "Strengths and opportunities appear when there are enough responses (floor of {n}).",
        "es": "Fortalezas y oportunidades aparecen cuando hay respuestas suficientes (piso de {n}).",
    },
    "Fui bem acolhido quando entrei na empresa.": {
        "en-US": "I was well welcomed when I joined the company.",
        "es": "Fui bien acogido cuando entré en la empresa.",
    },
    "Avaliação Mestre": {
        "en-US": "Master Assessment",
        "es": "Evaluación Maestra",
    },
    "Avaliação Mestre resposta registrada": {
        "en-US": "Master Assessment response recorded",
        "es": "Evaluación Maestra respuesta registrada",
    },
    "PTI": {
        "en-US": "PTI",
        "es": "PTI",
    },
    "PTI geral": {
        "en-US": "Overall PTI",
        "es": "PTI general",
    },
    "PTI por pilar": {
        "en-US": "PTI by pillar",
        "es": "PTI por pilar",
    },
    "PTI por pilar (menor)": {
        "en-US": "PTI by pillar (lowest)",
        "es": "PTI por pilar (menor)",
    },
    "Peoples Place to Work": {
        "en-US": "Peoples Place to Work",
        "es": "Peoples Place to Work",
    },
    "Peoples Trust Index geral": {
        "en-US": "Overall Peoples Trust Index",
        "es": "Peoples Trust Index general",
    },
    "Guarda de anonimato (inegociável): nenhum recorte com menos de {n} respondentes é impresso; comentários que identifiquem alguém são removidos antes da devolutiva.": {
        "en-US": "Anonymity safeguard (non-negotiable): no slice with fewer than {n} respondents is printed; comments that identify anyone are removed before the debrief.",
        "es": "Salvaguarda de anonimato (innegociable): ningún recorte con menos de {n} encuestados se imprime; los comentarios que identifiquen a alguien se eliminan antes de la devolutiva.",
    },
    "Há espaço para momentos de descontração.": {
        "en-US": "There is room for lighthearted moments.",
        "es": "Hay espacio para momentos de distensión.",
    },
    "Há flexibilidade quando surgem necessidades pessoais legítimas.": {
        "en-US": "There is flexibility when legitimate personal needs arise.",
        "es": "Hay flexibilidad cuando surgen necesidades personales legítimas.",
    },
    "Há um senso de comunidade entre as unidades e times.": {
        "en-US": "There is a sense of community across units and teams.",
        "es": "Hay un sentido de comunidad entre las unidades y equipos.",
    },
    "Híbrido": {
        "en-US": "Hybrid",
        "es": "Híbrido",
    },
    "Idade e gênero de fora": {
        "en-US": "Age and gender left out",
        "es": "Edad y género fuera",
    },
    "Imparcialidade": {
        "en-US": "Fairness",
        "es": "Imparcialidad",
    },
    "Indicador": {
        "en-US": "Indicator",
        "es": "Indicador",
    },
    "Indicador de sucesso": {
        "en-US": "Success indicator",
        "es": "Indicador de éxito",
    },
    "Indicadores do programa": {
        "en-US": "Program indicators",
        "es": "Indicadores del programa",
    },
    "Iniciativa": {
        "en-US": "Initiative",
        "es": "Iniciativa",
    },
    "Integração com o GPlanSiS|Peoples": {
        "en-US": "Integration with GPlanSiS|Peoples",
        "es": "Integración con GPlanSiS|Peoples",
    },
    "MarIA": {
        "en-US": "MarIA",
        "es": "MarIA",
    },
    "Marque ao menos uma afirmação para enviar. Nada foi gravado.": {
        "en-US": "Mark at least one statement to submit. Nothing was saved.",
        "es": "Marque al menos una afirmación para enviar. Nada fue guardado.",
    },
    "Maturidade": {
        "en-US": "Maturity",
        "es": "Madurez",
    },
    "Me sinto à vontade para discordar de um colega com respeito.": {
        "en-US": "I feel comfortable disagreeing with a colleague respectfully.",
        "es": "Me siento cómodo para discrepar de un colega con respeto.",
    },
    "Meta": {
        "en-US": "Target",
        "es": "Meta",
    },
    "Meta: nenhum pilar abaixo de {m} %. As barras em laranja estão abaixo da meta.": {
        "en-US": "Target: no pillar below {m}%. Bars in orange are below target.",
        "es": "Meta: ningún pilar por debajo de {m} %. Las barras en naranja están por debajo de la meta.",
    },
    "Meu gestor direto comunica com clareza o que se espera do meu trabalho.": {
        "en-US": "My direct manager clearly communicates what is expected of my work.",
        "es": "Mi gestor directo comunica con claridad lo que se espera de mi trabajo.",
    },
    "Meu gestor é tecnicamente competente para conduzir o time.": {
        "en-US": "My manager is technically competent to lead the team.",
        "es": "Mi gestor es técnicamente competente para conducir el equipo.",
    },
    "Meu tempo é respeitado (reuniões, prazos, horas extras).": {
        "en-US": "My time is respected (meetings, deadlines, overtime).",
        "es": "Mi tiempo es respetado (reuniones, plazos, horas extra).",
    },
    "Minha opinião é considerada nas decisões que afetam meu trabalho.": {
        "en-US": "My opinion is considered in decisions that affect my work.",
        "es": "Mi opinión es considerada en las decisiones que afectan mi trabajo.",
    },
    "Modelo de trabalho": {
        "en-US": "Work model",
        "es": "Modelo de trabajo",
    },
    "Módulo": {
        "en-US": "Module",
        "es": "Módulo",
    },
    "Módulo Tempo de empresa": {
        "en-US": "Tenure module",
        "es": "Módulo Tiempo de empresa",
    },
    "Necessidade de intervenção cultural imediata.": {
        "en-US": "Need for immediate cultural intervention.",
        "es": "Necesidad de intervención cultural inmediata.",
    },
    "Nenhum recorte com menos de cinco respostas é publicado — o mesmo piso de amostra que o Skills aplica nas matrizes. Recorte pequeno sobe agregado.": {
        "en-US": "No slice with fewer than five responses is published — the same sample floor the Skills applies in its matrices. A small slice rolls up aggregated.",
        "es": "Ningún recorte con menos de cinco respuestas se publica — el mismo piso de muestra que el Skills aplica en las matrices. El recorte pequeño sube agregado.",
    },
    "Nenhum recorte com menos de {n} respondentes é publicado.": {
        "en-US": "No slice with fewer than {n} respondents is published.",
        "es": "Ningún recorte con menos de {n} encuestados se publica.",
    },
    "Nenhum recorte desta dimensão atingiu o piso de {n} respondentes.": {
        "en-US": "No slice of this dimension reached the floor of {n} respondents.",
        "es": "Ningún recorte de esta dimensión alcanzó el piso de {n} encuestados.",
    },
    "Nenhuma resposta guarda quem respondeu. O vínculo com o sistema é pelos estratos (nível, área, vínculo, faixa de casa) que o organograma já conhece — derivados no envio e gravados sem a identidade.": {
        "en-US": "No response records who answered. The link to the system is through the strata (level, area, contract, tenure band) the org chart already knows — derived at submission and stored without the identity.",
        "es": "Ninguna respuesta guarda quién respondió. El vínculo con el sistema es por los estratos (nivel, área, vínculo, franja de antigüedad) que el organigrama ya conoce — derivados en el envío y guardados sin la identidad.",
    },
    "Neutro": {
        "en-US": "Neutral",
        "es": "Neutral",
    },
    "Novos colegas e estagiários são bem integrados.": {
        "en-US": "New colleagues and interns are well integrated.",
        "es": "Los nuevos colegas y pasantes se integran bien.",
    },
    "Nº de respondentes / participação": {
        "en-US": "No. of respondents / participation",
        "es": "N.º de encuestados / participación",
    },
    "Não há «panelinhas» que definem quem sobe.": {
        "en-US": "There are no «cliques» that decide who gets ahead.",
        "es": "No hay «camarillas» que definan quién asciende.",
    },
    "Não informado": {
        "en-US": "Not informed",
        "es": "No informado",
    },
    "Não percebo favoritismo na distribuição de reconhecimento.": {
        "en-US": "I don't perceive favoritism in how recognition is distributed.",
        "es": "No percibo favoritismo en la distribución del reconocimiento.",
    },
    "Níveis de maturidade": {
        "en-US": "Maturity levels",
        "es": "Niveles de madurez",
    },
    "Nível hierárquico": {
        "en-US": "Hierarchical level",
        "es": "Nivel jerárquico",
    },
    "A Avaliação Mestre consome": {
        "en-US": "Master Assessment consumes",
        "es": "El Evaluación Maestra consume",
    },
    "A Avaliação Mestre devolve": {
        "en-US": "Master Assessment returns",
        "es": "El Evaluación Maestra devuelve",
    },
    "A Avaliação Mestre não é um sistema à parte (§8.4): apoia-se nos módulos que a casa já opera. De onde tira insumo, e para onde devolve resultado.": {
        "en-US": "Master Assessment is not a separate system (§8.4): it relies on the modules the company already operates. Where it draws input from, and where it returns results.",
        "es": "El Evaluación Maestra no es un sistema aparte (§8.4): se apoya en los módulos que la casa ya opera. De dónde toma insumo, y a dónde devuelve resultado.",
    },
    "O PTI conta 4 e 5 como positivo. 3 é neutro, não positivo.": {
        "en-US": "The PTI counts 4 and 5 as positive. 3 is neutral, not positive.",
        "es": "El PTI cuenta 4 y 5 como positivo. 3 es neutral, no positivo.",
    },
    "O PTI recortado pelos estratos que o organograma já conhece. Nenhum recorte com menos de {n} respondentes é publicado — sobe agregado, para não isolar quem respondeu.": {
        "en-US": "The PTI sliced by the strata the org chart already knows. No slice with fewer than {n} respondents is published — it rolls up aggregated, so as not to isolate who answered.",
        "es": "El PTI recortado por los estratos que el organigrama ya conoce. Ningún recorte con menos de {n} encuestados se publica — sube agregado, para no aislar a quien respondió.",
    },
    "O PTI é o percentual de respostas «Concordo» e «Concordo totalmente» (4–5) sobre as válidas.": {
        "en-US": "The PTI is the percentage of «Agree» and «Strongly agree» (4–5) responses over the valid ones.",
        "es": "El PTI es el porcentaje de respuestas «De acuerdo» y «Totalmente de acuerdo» (4–5) sobre las válidas.",
    },
    "O modelo de trabalho (presencial/híbrido/remoto/campo) que exerço é compatível com minhas entregas.": {
        "en-US": "The work model (on-site/hybrid/remote/field) I follow is compatible with my deliverables.",
        "es": "El modelo de trabajo (presencial/híbrido/remoto/campo) que ejerzo es compatible con mis entregas.",
    },
    "O método": {
        "en-US": "The method",
        "es": "El método",
    },
    "O organograma não guarda data de nascimento nem gênero (LGPD). A pesquisa não os coleta; recorte etário ou de gênero, se preciso, é opt-in e fora daqui.": {
        "en-US": "The org chart stores neither date of birth nor gender (LGPD). The survey does not collect them; an age or gender slice, if needed, is opt-in and outside here.",
        "es": "El organigrama no guarda fecha de nacimiento ni género (LGPD). La encuesta no los recoge; un recorte etario o de género, si hace falta, es opt-in y fuera de aquí.",
    },
    "O que a liderança poderia fazer diferente?": {
        "en-US": "What could leadership do differently?",
        "es": "¿Qué podría hacer diferente el liderazgo?",
    },
    "O que faria você recomendar (ou não) a empresa?": {
        "en-US": "What would make you recommend (or not) the company?",
        "es": "¿Qué le haría recomendar (o no) la empresa?",
    },
    "O que fazemos aqui melhora a indústria dos nossos clientes.": {
        "en-US": "What we do here improves our clients' industry.",
        "es": "Lo que hacemos aquí mejora la industria de nuestros clientes.",
    },
    "O que mais te dá orgulho aqui?": {
        "en-US": "What makes you proudest here?",
        "es": "¿Qué es lo que más te enorgullece aquí?",
    },
    "O que mais te incomoda?": {
        "en-US": "What bothers you most?",
        "es": "¿Qué es lo que más te incomoda?",
    },
    "O que melhoraria seu equilíbrio vida-trabalho?": {
        "en-US": "What would improve your work-life balance?",
        "es": "¿Qué mejoraría su equilibrio vida-trabajo?",
    },
    "O sentimento de orgulho pelo trabalho, equipe e empresa.": {
        "en-US": "The sense of pride in the work, team and company.",
        "es": "El sentimiento de orgullo por el trabajo, el equipo y la empresa.",
    },
    "O total de marcações Likert consideradas no PTI.": {
        "en-US": "The total Likert ratings considered in the PTI.",
        "es": "El total de marcaciones Likert consideradas en el PTI.",
    },
    "O único dado que a estrutura não carrega — por isso é perguntado.": {
        "en-US": "The only datum the structure doesn't hold — that's why it's asked.",
        "es": "El único dato que la estructura no lleva — por eso se pregunta.",
    },
    "Orgulho": {
        "en-US": "Pride",
        "es": "Orgullo",
    },
    "Os cinco pilares": {
        "en-US": "The five pillars",
        "es": "Los cinco pilares",
    },
    "Os cinco pilares do Peoples Trust Index": {
        "en-US": "The five pillars of the Peoples Trust Index",
        "es": "Los cinco pilares del Peoples Trust Index",
    },
    "Os colaboradores se sentem apoiados profissional e pessoalmente.": {
        "en-US": "Employees feel supported professionally and personally.",
        "es": "Los colaboradores se sienten apoyados profesional y personalmente.",
    },
    "Os critérios de avaliação são claros e aplicados igualmente.": {
        "en-US": "The evaluation criteria are clear and applied equally.",
        "es": "Los criterios de evaluación son claros y se aplican por igual.",
    },
    "Os líderes comunicam com clareza, são competentes e íntegros.": {
        "en-US": "Leaders communicate clearly, are competent and act with integrity.",
        "es": "Los líderes comunican con claridad, son competentes e íntegros.",
    },
    "Participação": {
        "en-US": "Participation",
        "es": "Participación",
    },
    "Perguntas abertas (opcionais)": {
        "en-US": "Open questions (optional)",
        "es": "Preguntas abiertas (opcionales)",
    },
    "Pesquisa anual": {
        "en-US": "Annual survey",
        "es": "Encuesta anual",
    },
    "Pesquisa de Clima — Peoples Trust Index": {
        "en-US": "Climate Survey — Peoples Trust Index",
        "es": "Encuesta de Clima — Peoples Trust Index",
    },
    "Pessoas em vínculos diferentes (CLT, PJ, estágio) são tratadas com o mesmo respeito.": {
        "en-US": "People on different contract types (CLT, contractor, intern) are treated with the same respect.",
        "es": "Personas con vínculos diferentes (CLT, PJ, pasantía) son tratadas con el mismo respeto.",
    },
    "Pilar-foco": {
        "en-US": "Focus pillar",
        "es": "Pilar foco",
    },
    "Pilares": {
        "en-US": "Pillars",
        "es": "Pilares",
    },
    "Piso de 5 respondentes": {
        "en-US": "Floor of 5 respondents",
        "es": "Piso de 5 encuestados",
    },
    "Piso de anonimato": {
        "en-US": "Anonymity floor",
        "es": "Piso de anonimato",
    },
    "Plano de ação por área": {
        "en-US": "Action plan by area",
        "es": "Plan de acción por área",
    },
    "Posso ser eu mesmo no ambiente de trabalho.": {
        "en-US": "I can be myself in the workplace.",
        "es": "Puedo ser yo mismo en el ambiente de trabajo.",
    },
    "Presencial": {
        "en-US": "On-site",
        "es": "Presencial",
    },
    "Problemas recorrentes que afetam retenção e engajamento.": {
        "en-US": "Recurring problems that affect retention and engagement.",
        "es": "Problemas recurrentes que afectan la retención y el compromiso.",
    },
    "Promoções e oportunidades são baseadas em mérito, não em preferências pessoais.": {
        "en-US": "Promotions and opportunities are based on merit, not personal preferences.",
        "es": "Las promociones y oportunidades se basan en el mérito, no en preferencias personales.",
    },
    "Pulso semestral": {
        "en-US": "Semiannual pulse",
        "es": "Pulso semestral",
    },
    "Que apoio falta ao seu desenvolvimento?": {
        "en-US": "What support is missing for your development?",
        "es": "¿Qué apoyo falta para su desarrollo?",
    },
    "Quem entrega mais é reconhecido por isso.": {
        "en-US": "Those who deliver more are recognized for it.",
        "es": "Quien entrega más es reconocido por ello.",
    },
    "Recebo reconhecimento pelo esforço, não só pelo resultado.": {
        "en-US": "I receive recognition for effort, not just for results.",
        "es": "Recibo reconocimiento por el esfuerzo, no solo por el resultado.",
    },
    "Recebo respostas honestas quando faço perguntas difíceis.": {
        "en-US": "I get honest answers when I ask hard questions.",
        "es": "Recibo respuestas honestas cuando hago preguntas difíciles.",
    },
    "Recomendaria a GPlanSiS|Peoples como um bom lugar para trabalhar.": {
        "en-US": "I would recommend GPlanSiS|Peoples as a good place to work.",
        "es": "Recomendaría a GPlanSiS|Peoples como un buen lugar para trabajar.",
    },
    "Remoto": {
        "en-US": "Remote",
        "es": "Remoto",
    },
    "Respondentes": {
        "en-US": "Respondents",
        "es": "Encuestados",
    },
    "Responder": {
        "en-US": "Respond",
        "es": "Responder",
    },
    "Resposta anônima registrada — {n} afirmações · {destino}. Obrigado.": {
        "en-US": "Anonymous response recorded — {n} statements · {destino}. Thank you.",
        "es": "Respuesta anónima registrada — {n} afirmaciones · {destino}. Gracias.",
    },
    "Respostas duráveis e anônimas no PostgreSQL: nenhuma linha guarda quem respondeu — só o estrato e as respostas.": {
        "en-US": "Durable, anonymous responses in PostgreSQL: no row records who answered — only the stratum and the responses.",
        "es": "Respuestas duraderas y anónimas en PostgreSQL: ninguna fila guarda quién respondió — solo el estrato y las respuestas.",
    },
    "Respostas válidas": {
        "en-US": "Valid responses",
        "es": "Respuestas válidas",
    },
    "Respostas ÷ elegíveis (organograma)": {
        "en-US": "Responses ÷ eligible (org chart)",
        "es": "Respuestas ÷ elegibles (organigrama)",
    },
    "Segmentos": {
        "en-US": "Segments",
        "es": "Segmentos",
    },
    "Sei a quem recorrer quando preciso de uma decisão.": {
        "en-US": "I know whom to turn to when I need a decision.",
        "es": "Sé a quién recurrir cuando necesito una decisión.",
    },
    "Seu recorte (do sistema, anônimo)": {
        "en-US": "Your slice (from the system, anonymous)",
        "es": "Su recorte (del sistema, anónimo)",
    },
    "Seções do Peoples Place to Work": {
        "en-US": "Peoples Place to Work sections",
        "es": "Secciones del Peoples Place to Work",
    },
    "Sinto que contribuo para algo maior que minhas tarefas.": {
        "en-US": "I feel I contribute to something bigger than my tasks.",
        "es": "Siento que contribuyo a algo mayor que mis tareas.",
    },
    "Sinto que faço parte de um time, não apenas de um projeto.": {
        "en-US": "I feel part of a team, not just a project.",
        "es": "Siento que formo parte de un equipo, no solo de un proyecto.",
    },
    "Sinto que meu trabalho tem significado e impacto.": {
        "en-US": "I feel my work has meaning and impact.",
        "es": "Siento que mi trabajo tiene significado e impacto.",
    },
    "Sinto que pertenço a esta empresa.": {
        "en-US": "I feel I belong to this company.",
        "es": "Siento que pertenezco a esta empresa.",
    },
    "Sou tratado como pessoa, não apenas como recurso de projeto.": {
        "en-US": "I am treated as a person, not just a project resource.",
        "es": "Soy tratado como persona, no solo como recurso de proyecto.",
    },
    "Sou tratado de forma justa independentemente de gênero, raça, orientação ou idade.": {
        "en-US": "I am treated fairly regardless of gender, race, orientation or age.",
        "es": "Soy tratado de forma justa independientemente de género, raza, orientación o edad.",
    },
    "Suas respostas entram no agregado; nunca no seu nome.": {
        "en-US": "Your responses go into the aggregate; never under your name.",
        "es": "Sus respuestas entran en el agregado; nunca a su nombre.",
    },
    "Taxa de participação": {
        "en-US": "Participation rate",
        "es": "Tasa de participación",
    },
    "Tempo médio de permanência": {
        "en-US": "Average tenure",
        "es": "Tiempo medio de permanencia",
    },
    "Tenho acesso a capacitação técnica relevante (trilhas, certificações técnicas).": {
        "en-US": "I have access to relevant technical training (tracks, technical certifications).",
        "es": "Tengo acceso a capacitación técnica relevante (rutas, certificaciones técnicas).",
    },
    "Tenho as mesmas chances de crescer que meus pares.": {
        "en-US": "I have the same chances to grow as my peers.",
        "es": "Tengo las mismas oportunidades de crecer que mis pares.",
    },
    "Tenho clareza sobre a estratégia da minha área.": {
        "en-US": "I have clarity about my area's strategy.",
        "es": "Tengo claridad sobre la estrategia de mi área.",
    },
    "Tenho orgulho da reputação da GPlanSiS|Peoples no mercado.": {
        "en-US": "I am proud of GPlanSiS|Peoples's reputation in the market.",
        "es": "Estoy orgulloso de la reputación de GPlanSiS|Peoples en el mercado.",
    },
    "Tenho orgulho das entregas do meu time.": {
        "en-US": "I am proud of my team's deliveries.",
        "es": "Estoy orgulloso de las entregas de mi equipo.",
    },
    "Tenho orgulho do trabalho que entrego.": {
        "en-US": "I am proud of the work I deliver.",
        "es": "Estoy orgulloso del trabajo que entrego.",
    },
    "Tenho os recursos e ferramentas necessários para fazer um bom trabalho.": {
        "en-US": "I have the resources and tools I need to do a good job.",
        "es": "Tengo los recursos y herramientas necesarios para hacer un buen trabajo.",
    },
    "Top forças": {
        "en-US": "Top strengths",
        "es": "Top fortalezas",
    },
    "Top oportunidades": {
        "en-US": "Top opportunities",
        "es": "Top oportunidades",
    },
    "Trust Index™ adaptado para condução 100% interna. Um excelente lugar para trabalhar é aquele em que as pessoas confiam em quem lideram e trabalham ao lado, têm orgulho do que fazem e gostam de quem têm como colegas. A confiança é o pilar estruturante.": {
        "en-US": "Trust Index™ adapted for fully internal use. A great place to work is one where people trust those they lead and work alongside, take pride in what they do, and enjoy the people they work with. Trust is the structuring pillar.",
        "es": "Trust Index™ adaptado para conducción 100% interna. Un excelente lugar para trabajar es aquel en que las personas confían en quienes lideran y trabajan al lado, se enorgullecen de lo que hacen y disfrutan de quienes tienen como colegas. La confianza es el pilar estructurante.",
    },
    "Turnover voluntário": {
        "en-US": "Voluntary turnover",
        "es": "Rotación voluntaria",
    },
    "Uma sugestão concreta de melhoria.": {
        "en-US": "One concrete suggestion for improvement.",
        "es": "Una sugerencia concreta de mejora.",
    },
    "Vale a pena o esforço que dedico aqui.": {
        "en-US": "The effort I put in here is worth it.",
        "es": "Vale la pena el esfuerzo que dedico aquí.",
    },
    "Vejo futuro para mim aqui.": {
        "en-US": "I see a future for myself here.",
        "es": "Veo futuro para mí aquí.",
    },
    "Vista Conversa de Valor": {
        "en-US": "Value Conversation view",
        "es": "Vista Conversación de Valor",
    },
    "Vínculo com o ciclo": {
        "en-US": "Link to the cycle",
        "es": "Vínculo con el ciclo",
    },
    "a agenda e a cobertura por líder — o canal qualitativo de escuta": {
        "en-US": "the schedule and coverage by leader — the qualitative listening channel",
        "es": "la agenda y la cobertura por líder — el canal cualitativo de escucha",
    },
    "a árvore de gestor direto, os 6 níveis, as 60 áreas — a população e os estratos": {
        "en-US": "the direct-manager tree, the 6 levels, the 60 areas — the population and the strata",
        "es": "el árbol de gestor directo, los 6 niveles, las 60 áreas — la población y los estratos",
    },
    "afirmação(ões) e comentários que sustentam a prioridade": {
        "en-US": "statement(s) and comments that support the priority",
        "es": "afirmación(es) y comentarios que sustentan la prioridad",
    },
    "ação concreta (1 linha)": {
        "en-US": "concrete action (1 line)",
        "es": "acción concreta (1 línea)",
    },
    "cargas datadas da estrutura — turnover e movimentação": {
        "en-US": "dated loads of the structure — turnover and movement",
        "es": "cargas fechadas de la estructura — rotación y movimiento",
    },
    "como saberemos que funcionou (preferir número)": {
        "en-US": "how we'll know it worked (prefer a number)",
        "es": "cómo sabremos que funcionó (preferir número)",
    },
    "correlação clima × tempo de casa": {
        "en-US": "climate × tenure correlation",
        "es": "correlación clima × antigüedad",
    },
    "crescimento YoY": {
        "en-US": "YoY growth",
        "es": "crecimiento interanual",
    },
    "data": {
        "en-US": "date",
        "es": "fecha",
    },
    "do relatório de devolutiva; oculto se < 5": {
        "en-US": "from the debrief report; hidden if < 5",
        "es": "del informe de devolutiva; oculto si < 5",
    },
    "eNPS": {
        "en-US": "eNPS",
        "es": "eNPS",
    },
    "eNPS (proxy)": {
        "en-US": "eNPS (proxy)",
        "es": "eNPS (proxy)",
    },
    "faixas de casa e tempo médio — segmento nativo do PTI e do onboarding": {
        "en-US": "tenure bands and average tenure — a native segment of the PTI and of onboarding",
        "es": "franjas de antigüedad y tiempo medio — segmento nativo del PTI y del onboarding",
    },
    "faltam {n}": {
        "en-US": "{n} to go",
        "es": "faltan {n}",
    },
    "gravada no banco e no estado": {
        "en-US": "saved to the database and the state",
        "es": "guardada en la base de datos y en el estado",
    },
    "gravada no estado de trabalho": {
        "en-US": "saved to the working state",
        "es": "guardada en el estado de trabajo",
    },
    "lacunas de clareza de papel viram revisão de Skills": {
        "en-US": "role-clarity gaps become Skills revisions",
        "es": "brechas de claridad de rol se vuelven revisión de Skills",
    },
    "leitura assistida dos resultados no idioma do usuário": {
        "en-US": "assisted reading of the results in the user's language",
        "es": "lectura asistida de los resultados en el idioma del usuario",
    },
    "maturidade": {
        "en-US": "maturity",
        "es": "madurez",
    },
    "meta atingida": {
        "en-US": "target met",
        "es": "meta alcanzada",
    },
    "nenhum < {m} %": {
        "en-US": "none < {m}%",
        "es": "ninguno < {m} %",
    },
    "o histórico do PTI encadeia-se como evento auditável": {
        "en-US": "the PTI history chains as an auditable event",
        "es": "el histórico del PTI se encadena como evento auditable",
    },
    "o que cada cargo é — expectativa × percepção por função": {
        "en-US": "what each role is — expectation × perception by function",
        "es": "lo que es cada cargo — expectativa × percepción por función",
    },
    "participação": {
        "en-US": "participation",
        "es": "participación",
    },
    "perguntas sobre clima sobre o recorte vigente": {
        "en-US": "climate questions about the current slice",
        "es": "preguntas sobre clima sobre el recorte vigente",
    },
    "pessoa (não «a área»)": {
        "en-US": "a person (not «the area»)",
        "es": "persona (no «el área»)",
    },
    "pilar com menor PTI no recorte": {
        "en-US": "pillar with the lowest PTI in the slice",
        "es": "pilar con menor PTI en el recorte",
    },
    "pulso semestral": {
        "en-US": "semiannual pulse",
        "es": "pulso semestral",
    },
    "puxado do organograma — gestor direto e recorte": {
        "en-US": "pulled from the org chart — direct manager and slice",
        "es": "extraído del organigrama — gestor directo y recorte",
    },
    "recortes de clima por área/nível na mesma estrutura": {
        "en-US": "climate slices by area/level in the same structure",
        "es": "recortes de clima por área/nivel en la misma estructura",
    },
    "reflete no próximo pulso / na próxima Conversa de Valor?": {
        "en-US": "reflected in the next pulse / next Value Conversation?",
        "es": "¿se refleja en el próximo pulso / en la próxima Conversación de Valor?",
    },
    "respostas": {
        "en-US": "responses",
        "es": "respuestas",
    },
    "sem amostra": {
        "en-US": "no sample",
        "es": "sin muestra",
    },
    "temas do PTI entram no roteiro da Conversa de Valor; a devolutiva fecha o loop": {
        "en-US": "PTI themes enter the Value Conversation script; the debrief closes the loop",
        "es": "temas del PTI entran en el guion de la Conversación de Valor; la devolutiva cierra el bucle",
    },
    "{o} recorte(s) com menos de {n} respondentes ({r} respostas) ficaram ocultos pelo piso de anonimato.": {
        "en-US": "{o} slice(s) with fewer than {n} respondents ({r} responses) were hidden by the anonymity floor.",
        "es": "{o} recorte(s) con menos de {n} encuestados ({r} respuestas) quedaron ocultos por el piso de anonimato.",
    },
    "{p} promotores · {n} neutros · {d} detratores. Derivado da afirmação «Recomendaria a GPlanSiS|Peoples». Meta ≥ {m}.": {
        "en-US": "{p} promoters · {n} passives · {d} detractors. Derived from the statement «I would recommend GPlanSiS|Peoples». Target ≥ {m}.",
        "es": "{p} promotores · {n} neutros · {d} detractores. Derivado de la afirmación «Recomendaría a GPlanSiS|Peoples». Meta ≥ {m}.",
    },
    "{r} de {e} elegíveis responderam ({p} %). Meta: {m} %.": {
        "en-US": "{r} of {e} eligible responded ({p}%). Target: {m}%.",
        "es": "{r} de {e} elegibles respondieron ({p} %). Meta: {m} %.",
    },
    "Área / líder": {
        "en-US": "Area / leader",
        "es": "Área / líder",
    },
    "Áreas técnicas, comerciais e de suporte têm peso equivalente nas decisões.": {
        "en-US": "Technical, commercial and support areas carry equivalent weight in decisions.",
        "es": "Las áreas técnicas, comerciales y de soporte tienen peso equivalente en las decisiones.",
    },
    "−10 %/ano": {
        "en-US": "−10%/year",
        "es": "−10 %/año",
    },
    # ---- Evaluación Maestra · programação da pesquisa e notificação ----
    "A pesquisa fica aberta de {de} a {ate}.": {
        "en-US": "The survey is open from {de} to {ate}.",
        "es": "La encuesta está abierta del {de} al {ate}.",
    },
    "Abertura": {
        "en-US": "Opening",
        "es": "Apertura",
    },
    "Ciclo": {
        "en-US": "Cycle",
        "es": "Ciclo",
    },
    "Convidar por e-mail ao programar": {
        "en-US": "Invite by e-mail when scheduling",
        "es": "Invitar por correo al programar",
    },
    "Defina o ciclo e a janela de resposta, e registre a intenção de convidar os colaboradores por e-mail. O envio do e-mail é um passo à parte, a configurar.": {
        "en-US": "Set the cycle and the response window, and register the intent to invite collaborators by e-mail. Sending the e-mail is a separate step, to be configured.",
        "es": "Defina el ciclo y la ventana de respuesta, y registre la intención de invitar a los colaboradores por correo. El envío del correo es un paso aparte, a configurar.",
    },
    "Fechamento": {
        "en-US": "Closing",
        "es": "Cierre",
    },
    "Avaliação Mestre pesquisa programada": {
        "en-US": "Master Assessment survey scheduled",
        "es": "Evaluación Maestra encuesta programada",
    },
    "Janela do ciclo": {
        "en-US": "Cycle window",
        "es": "Ventana del ciclo",
    },
    "Notificar colaboradores": {
        "en-US": "Notify collaborators",
        "es": "Notificar colaboradores",
    },
    "Notificação preparada para {n} colaboradores com e-mail — {motivo}.": {
        "en-US": "Notification prepared for {n} collaborators with e-mail — {motivo}.",
        "es": "Notificación preparada para {n} colaboradores con correo — {motivo}.",
    },
    "Pesquisa programada — ciclo {ciclo}.": {
        "en-US": "Survey scheduled — cycle {ciclo}.",
        "es": "Encuesta programada — ciclo {ciclo}.",
    },
    "Programada": {
        "en-US": "Scheduled",
        "es": "Programada",
    },
    "Programar": {
        "en-US": "Schedule",
        "es": "Programar",
    },
    "Programar a pesquisa": {
        "en-US": "Schedule the survey",
        "es": "Programar la encuesta",
    },
    "Programar pesquisa": {
        "en-US": "Schedule survey",
        "es": "Programar encuesta",
    },
    "Salva a programação. O e-mail é passo à parte, a configurar depois.": {
        "en-US": "Saves the schedule. The e-mail is a separate step, to configure later.",
        "es": "Guarda la programación. El correo es un paso aparte, a configurar después.",
    },
    "Sua opinião importa, e é anônima. Responda à pesquisa de clima ({ciclo}) — leva poucos minutos.{janela} O sistema não guarda quem respondeu.": {
        "en-US": "Your opinion matters, and it's anonymous. Take the climate survey ({ciclo}) — it takes a few minutes.{janela} The system does not record who answered.",
        "es": "Su opinión importa, y es anónima. Responda la encuesta de clima ({ciclo}) — lleva pocos minutos.{janela} El sistema no guarda quién respondió.",
    },
    "em": {
        "en-US": "on",
        "es": "el",
    },
    "envio de e-mail a configurar (SMTP/M365)": {
        "en-US": "e-mail sending to be configured (SMTP/M365)",
        "es": "envío de correo a configurar (SMTP/M365)",
    },
    "{n} afirmações": {
        "en-US": "{n} statements",
        "es": "{n} afirmaciones",
    },
    "{n} colaboradores têm e-mail cadastrado no organograma. O disparo em si fica pendente de configuração de correio (SMTP/M365) — por ora, a programação é registrada e o convite fica pronto, não enviado.": {
        "en-US": "{n} collaborators have an e-mail registered in the org chart. The actual dispatch is pending mail configuration (SMTP/M365) — for now, the schedule is recorded and the invite is ready, not sent.",
        "es": "{n} colaboradores tienen correo registrado en el organigrama. El disparo en sí queda pendiente de configuración de correo (SMTP/M365) — por ahora, la programación se registra y la invitación queda lista, no enviada.",
    },
    "{tenant} · Pesquisa de Clima (Peoples Place to Work)": {
        "en-US": "{tenant} · Climate Survey (Peoples Place to Work)",
        "es": "{tenant} · Encuesta de Clima (Peoples Place to Work)",
    },
    # ---- MarIA · balão de boas-vindas no passo a passo ----
    "Conheça a minha história": {
        "en-US": "Discover my story",
        "es": "Conozca mi historia",
    },
    "Olá, {nome}! Sou a MarIA — que bom te ver por aqui.": {
        "en-US": "Hi, {nome}! I'm MarIA — great to see you here.",
        "es": "¡Hola, {nome}! Soy MarIA — qué bueno verte por aquí.",
    },
    "colega": {
        "en-US": "colleague",
        "es": "colega",
    },
    # ---- GPlanSiS|ORG · Agentes (cabeçalho) ----
    # ---- avatar reúne as ferramentas de apoio + idioma ----
    "Idioma": {
        "en-US": "Language",
        "es": "Idioma",
    },
    "Quem está logado, o perfil vigente, o tema e a saída — e também o **manual**, as **boas-vindas** e o **idioma**, reunidos aqui no lugar da pessoa, para o cabeçalho ficar só com as vistas. O perfil decide o que você pode editar: visualizador não muta nada, editor fica confinado à sua subárvore.": {
        "en-US": "Who's logged in, the current profile, the theme and the exit — plus the **manual**, the **welcome** and the **language**, gathered here in the person's place, so the header keeps only the views. The profile decides what you can edit: a viewer changes nothing, an editor stays confined to their subtree.",
        "es": "Quién está conectado, el perfil vigente, el tema y la salida — y también el **manual**, la **bienvenida** y el **idioma**, reunidos aquí en el lugar de la persona, para que el encabezado quede solo con las vistas. El perfil decide lo que usted puede editar: un visualizador no cambia nada, un editor queda confinado a su subárbol.",
    },
    "Você, e as ferramentas de apoio": {
        "en-US": "You, and the support tools",
        "es": "Usted, y las herramientas de apoyo",
    },
    # ---- Banco de dados: explorador de tabelas ----
    "A descrição de cargo que o RH escreve (GEP-FOR-003): missão, responsabilidades, requisitos e competências, uma por função.": {
        "en-US": "The job description the HR writes (GEP-FOR-003): mission, responsibilities, requirements and competencies, one per role.",
        "es": "La descripción de cargo que RR.HH. escribe (GEP-FOR-003): misión, responsabilidades, requisitos y competencias, una por función.",
    },
    "A pesquisa de clima, anônima: respostas Likert, estratos e abertas — nenhuma coluna de identidade.": {
        "en-US": "The climate survey, anonymous: Likert answers, strata and open text — no identity column.",
        "es": "La encuesta de clima, anónima: respuestas Likert, estratos y abiertas — ninguna columna de identidad.",
    },
    "Abrir {tabela} — dados e estrutura": {
        "en-US": "Open {tabela} — data and structure",
        "es": "Abrir {tabela} — datos y estructura",
    },
    "Aceita nulo": {
        "en-US": "Nullable",
        "es": "Acepta nulo",
    },
    "As Conversas que Geram Valor (GEP-FOR-006): status, data e o formulário inteiro em JSONB, por pessoa, ano e ciclo.": {
        "en-US": "The Conversations that Generate Value (GEP-FOR-006): status, date and the whole form in JSONB, per person, year and cycle.",
        "es": "Las Conversaciones que Generan Valor (GEP-FOR-006): estado, fecha y el formulario entero en JSONB, por persona, año y ciclo.",
    },
    "Coluna": {
        "en-US": "Column",
        "es": "Columna",
    },
    "Dados": {
        "en-US": "Data",
        "es": "Datos",
    },
    "Explorar {tabela}": {
        "en-US": "Explore {tabela}",
        "es": "Explorar {tabela}",
    },
    "Não foi possível ler a tabela.": {
        "en-US": "Could not read the table.",
        "es": "No fue posible leer la tabla.",
    },
    "A Avaliação (GEP-FOR-004): risco e impacto de perda, prontidão e ação imediata, por pessoa e ano.": {
        "en-US": "The Assessment (GEP-FOR-004): risk and impact of loss, readiness and immediate action, per person and year.",
        "es": "La Evaluación (GEP-FOR-004): riesgo e impacto de pérdida, preparación y acción inmediata, por persona y año.",
    },
    "Recarregar": {
        "en-US": "Reload",
        "es": "Recargar",
    },
    "Sem linhas para mostrar.": {
        "en-US": "No rows to show.",
        "es": "Sin filas para mostrar.",
    },
    "Tabela fora do catálogo.": {
        "en-US": "Table not in the catalog.",
        "es": "Tabla fuera del catálogo.",
    },
    "ver": {
        "en-US": "show",
        "es": "ver",
    },
    "{c} colunas · {n} linhas · {o}": {
        "en-US": "{c} columns · {n} rows · {o}",
        "es": "{c} columnas · {n} filas · {o}",
    },
    "{n} de {t} linhas": {
        "en-US": "{n} of {t} rows",
        "es": "{n} de {t} filas",
    },
    'Organogramas': {
        "en-US": 'Org charts',
        "es": 'Organigramas'},
    'Cada organograma tem sua própria estrutura, seu histórico e seu espelho no banco. Um fica ativo por vez — é o que todos veem. Troque pelo seletor do cabeçalho ou aqui.': {
        "en-US": 'Each org chart has its own structure, its own history and its own mirror in the database. One is active at a time — the one everyone sees. Switch it from the header selector or here.',
        "es": 'Cada organigrama tiene su propia estructura, su historial y su espejo en la base. Uno queda activo a la vez — el que todos ven. Cámbielo por el selector del encabezado o aquí.'},
    'Nós': {
        "en-US": 'Nodes',
        "es": 'Nodos'},
    'Criado em': {
        "en-US": 'Created on',
        "es": 'Creado el'},
    'Ações': {
        "en-US": 'Actions',
        "es": 'Acciones'},
    'ativo': {
        "en-US": 'active',
        "es": 'activo'},
    'Passar a mostrar este organograma': {
        "en-US": 'Switch to this org chart',
        "es": 'Pasar a mostrar este organigrama'},
    'Ativar': {
        "en-US": 'Activate',
        "es": 'Activar'},
    'Renomear': {
        "en-US": 'Rename',
        "es": 'Renombrar'},
    'Excluir “{nome}”? A estrutura e o histórico dele saem do sistema.': {
        "en-US": 'Delete “{nome}”? Its structure and history leave the system.',
        "es": '¿Eliminar «{nome}»? Su estructura y su historial salen del sistema.'},
    'Novo organograma': {
        "en-US": 'New org chart',
        "es": 'Nuevo organigrama'},
    'Nome da nova organização': {
        "en-US": 'Name of the new organization',
        "es": 'Nombre de la nueva organización'},
    'Criar e abrir': {
        "en-US": 'Create and open',
        "es": 'Crear y abrir'},
    'O organograma novo nasce só com a raiz — do topo você monta o resto com “+ Unidade” e “Criar colaborador”.': {
        "en-US": 'A new org chart starts with just the root — from the top you build the rest with “+ Unit” and “Create collaborator”.',
        "es": 'El organigrama nuevo nace solo con la raíz — desde la cima usted arma el resto con «+ Unidad» y «Crear colaborador».'},
    'Novo nome do organograma:': {
        "en-US": 'New name for the org chart:',
        "es": 'Nuevo nombre del organigrama:'},
    'Organograma ativo': {
        "en-US": 'Active org chart',
        "es": 'Organigrama activo'},
    'Gerenciar organogramas': {
        "en-US": 'Manage org charts',
        "es": 'Gestionar organigramas'},
    'Criar, renomear, excluir': {
        "en-US": 'Create, rename, delete',
        "es": 'Crear, renombrar, eliminar'},
    'Organograma renomeado.': {
        "en-US": 'Org chart renamed.',
        "es": 'Organigrama renombrado.'},
    'Dê um nome ao novo organograma.': {
        "en-US": 'Give the new org chart a name.',
        "es": 'Dé un nombre al nuevo organigrama.'},
    'Organograma não encontrado.': {
        "en-US": 'Org chart not found.',
        "es": 'Organigrama no encontrado.'},
    'Não dá para excluir o último organograma.': {
        "en-US": "You can't delete the last org chart.",
        "es": 'No se puede eliminar el último organigrama.'},
    'Criar colaborador': {
        "en-US": 'Create collaborator',
        "es": 'Crear colaborador'},
    'Cria um colaborador sob o nó selecionado (ou a raiz) e abre a ficha': {
        "en-US": 'Creates a collaborator under the selected node (or the root) and opens the form',
        "es": 'Crea un colaborador bajo el nodo seleccionado (o la raíz) y abre la ficha'},
    'Não há onde criar: o organograma está sem raiz.': {
        "en-US": 'Nowhere to create: the org chart has no root.',
        "es": 'No hay dónde crear: el organigrama no tiene raíz.'},
    'Novo colaborador': {
        "en-US": 'New collaborator',
        "es": 'Nuevo colaborador'},
    'novo colaborador': {
        "en-US": 'new collaborator',
        "es": 'nuevo colaborador'},
    'seu escopo': {
        "en-US": 'your scope',
        "es": 'su ámbito'},
    'Tudo (sem recorte)': {
        "en-US": 'Everything (no scope)',
        "es": 'Todo (sin recorte)'},
    'Só o próprio nó': {
        "en-US": 'Only their own node',
        "es": 'Solo su propio nodo'},
    'Subárvore (gestor)': {
        "en-US": 'Subtree (manager)',
        "es": 'Subárbol (gestor)'},
    'Por vertical': {
        "en-US": 'By vertical',
        "es": 'Por vertical'},
    'Acessos por pessoa': {
        "en-US": 'Access per person',
        "es": 'Accesos por persona'},
    'Escopo': {
        "en-US": 'Scope',
        "es": 'Ámbito'},
    'você': {
        "en-US": 'you',
        "es": 'usted'},
    'Valor do escopo (opcional)': {
        "en-US": 'Scope value (optional)',
        "es": 'Valor del ámbito (opcional)'},
    'vazio = o da própria pessoa': {
        "en-US": "empty = the person's own",
        "es": 'vacío = el de la propia persona'},
    'Acesso atribuído.': {
        "en-US": 'Access assigned.',
        "es": 'Acceso asignado.'},
    'Acesso removido.': {
        "en-US": 'Access removed.',
        "es": 'Acceso eliminado.'},
    'Escolha um colaborador válido.': {
        "en-US": 'Choose a valid collaborator.',
        "es": 'Elija un colaborador válido.'},
    'acesso atribuído': {
        "en-US": 'access assigned',
        "es": 'acceso asignado'},
    'acesso removido': {
        "en-US": 'access removed',
        "es": 'acceso eliminado'},
    'Espelho automático ligado: cada mutação também desce ao banco (só quando muda de verdade).': {
        "en-US": 'Automatic mirror on: every change also goes to the database (only when it actually changed).',
        "es": 'Espejo automático activado: cada cambio también baja a la base (solo cuando cambia de verdad).'},
    'Espelho automático em dia: a última escrita no banco passou.': {
        "en-US": 'Automatic mirror up to date: the last write to the database went through.',
        "es": 'Espejo automático al día: la última escritura en la base pasó.'},
    'O espelho automático falhou na última escrita (não-fatal — a edição está salva no estado): {msg}': {
        "en-US": 'The automatic mirror failed on the last write (non-fatal — the edit is saved in the state): {msg}',
        "es": 'El espejo automático falló en la última escritura (no fatal — la edición está guardada en el estado): {msg}'},
    'Espelho automático desligado. Ligue com <code>ORG_ESPELHO=1</code> para o banco viver em dia a cada mutação.': {
        "en-US": 'Automatic mirror off. Turn it on with <code>ORG_ESPELHO=1</code> so the database stays current on every change.',
        "es": 'Espejo automático desactivado. Actívelo con <code>ORG_ESPELHO=1</code> para que la base se mantenga al día en cada cambio.'},
    'Módulos': {
        "en-US": 'Modules',
        "es": 'Módulos'},
    'Módulos visíveis': {
        "en-US": 'Visible modules',
        "es": 'Módulos visibles'},
    'Módulo indisponível para o seu acesso.': {
        "en-US": 'Module unavailable for your access.',
        "es": 'Módulo no disponible para su acceso.'},
    'Colaborador não encontrado.': {
        "en-US": 'Collaborator not found.',
        "es": 'Colaborador no encontrado.'},
    'Salvar acesso': {
        "en-US": 'Save access',
        "es": 'Guardar acceso'},
    'Remover acesso': {
        "en-US": 'Remove access',
        "es": 'Eliminar acceso'},
    'todos': {
        "en-US": 'all',
        "es": 'todos'},
    'buscar colaborador…': {
        "en-US": 'search collaborator…',
        "es": 'buscar colaborador…'},
    'Nenhum marcado = vê todos. O Administrador vê todos de qualquer forma.': {
        "en-US": 'None checked = sees all. The Administrator sees all anyway.',
        "es": 'Ninguno marcado = ve todos. El Administrador ve todos de todos modos.'},
    'Todos os colaboradores do sistema. Com login, o papel, o escopo e os módulos visíveis de cada um vêm daqui — não do seletor acima. Clique em Editar para definir. Sem nenhuma atribuição, todo login entra como Administrador — é o que deixa o primeiro admin montar isto.': {
        "en-US": "All the system's collaborators. With login, each person's role, scope and visible modules come from here — not from the selector above. Click Edit to set them. With no assignment at all, every login enters as Administrator — that's what lets the first admin set this up.",
        "es": 'Todos los colaboradores del sistema. Con inicio de sesión, el papel, el ámbito y los módulos visibles de cada uno vienen de aquí — no del selector de arriba. Haga clic en Editar para definirlos. Sin ninguna asignación, todo inicio de sesión entra como Administrador — es lo que deja al primer admin montar esto.'},
    '{n} colaborador(es) · {k} com acesso definido. Quem não tem definição herda o padrão (Administrador enquanto ninguém foi definido; Visualizador depois).': {
        "en-US": '{n} collaborator(s) · {k} with access defined. Anyone without a definition inherits the default (Administrator while no one is defined; Viewer afterwards).',
        "es": '{n} colaborador(es) · {k} con acceso definido. Quien no tiene definición hereda el valor por defecto (Administrador mientras nadie esté definido; Visualizador después).'},
    'Definir pela hierarquia': {
        "en-US": 'Set from hierarchy',
        "es": 'Definir por jerarquía'},
    'Selecionar todos os módulos': {
        "en-US": 'Select all modules',
        "es": 'Seleccionar todos los módulos'},
    'sugerido': {
        "en-US": 'suggested',
        "es": 'sugerido'},
    'sugerido pela hierarquia — clique em Editar': {
        "en-US": 'suggested from the hierarchy — click Edit',
        "es": 'sugerido por la jerarquía — haga clic en Editar'},
    'acessos pela hierarquia': {
        "en-US": 'accesses from hierarchy',
        "es": 'accesos por jerarquía'},
    'Definir o acesso de todos os colaboradores sem atribuição pela hierarquia?': {
        "en-US": 'Set the access of every collaborator without an assignment from the hierarchy?',
        "es": '¿Definir el acceso de todos los colaboradores sin asignación por la jerarquía?'},
    '{n} acesso(s) definido(s) pela hierarquia.': {
        "en-US": '{n} access(es) set from the hierarchy.',
        "es": '{n} acceso(s) definido(s) por la jerarquía.'},
    'Editar ficha completa': {
        "en-US": 'Edit full record',
        "es": 'Editar ficha completa'},
    'Perfil sem permissão de edição nesta unidade. Os campos estão em leitura.': {
        "en-US": 'Profile without edit permission on this unit. The fields are read-only.',
        "es": 'Perfil sin permiso de edición en esta unidad. Los campos están en solo lectura.'},
    'Mover reporte': {
        "en-US": 'Move reporting line',
        "es": 'Mover reporte'},
    'Vínculos no sistema': {
        "en-US": 'Links across the system',
        "es": 'Vínculos en el sistema'},
    'Data de nascimento': {
        "en-US": 'Date of birth',
        "es": 'Fecha de nacimiento'},
    'Gênero': {
        "en-US": 'Gender',
        "es": 'Género'},
    'Tipo de mão de obra': {
        "en-US": 'Labor type',
        "es": 'Tipo de mano de obra'},
    'MO (MOI/MOD)': {
        "en-US": 'MO (MOI/MOD)',
        "es": 'MO (MOI/MOD)'},
    'Categoria de nível': {
        "en-US": 'Level category',
        "es": 'Categoría de nivel'},
    'BU (unidade de negócio)': {
        "en-US": 'BU (business unit)',
        "es": 'BU (business unit)'},
    'CC_Equipe': {
        "en-US": 'CC_Equipe',
        "es": 'CC_Equipe'},
    'Níveis de centro de custo (N2 / N4 / N5)': {
        "en-US": 'Cost-center levels (N2 / N4 / N5)',
        "es": 'Niveles de centro de costo (N2 / N4 / N5)'},
    'N3 é o Centro de custo acima. As colunas financeiras (salário, custos, vendas) ficam na base bd_completo_org, só para Admin — aqui não entram (LGPD).': {
        "en-US": "N3 is the Cost center above. The financial columns (salary, costs, sales) live in the bd_completo_org base, Admin-only — they don't go here (LGPD).",
        "es": 'N3 es el Centro de costo de arriba. Las columnas financieras (salario, costos, ventas) viven en la base bd_completo_org, solo para Admin — aquí no entran (LGPD).'},
    'A planilha completa (de-para): todas as colunas por colaborador, com gestor direto e tempo de casa derivados. As colunas financeiras aparecem sempre NULL — dinheiro não é gravado (LGPD-01/02). Só Admin.': {
        "en-US": 'The complete sheet (mapping): every column per collaborator, with direct manager and tenure derived. The financial columns are always NULL — money is not stored (LGPD-01/02). Admin only.',
        "es": 'La planilla completa (de-para): todas las columnas por colaborador, con gestor directo y antigüedad derivados. Las columnas financieras aparecen siempre NULL — el dinero no se guarda (LGPD-01/02). Solo Admin.'},
    '— não declarado': {
        "en-US": '— not declared',
        "es": '— no declarado'},
    'Masculino': {
        "en-US": 'Male',
        "es": 'Masculino'},
    'Feminino': {
        "en-US": 'Female',
        "es": 'Femenino'},
    'Outro': {
        "en-US": 'Other',
        "es": 'Otro'},
    'Prefiro não informar': {
        "en-US": 'Prefer not to say',
        "es": 'Prefiero no informar'},
    'Vendável': {
        "en-US": 'Billable',
        "es": 'Vendible'},
    'Não vendável': {
        "en-US": 'Non-billable',
        "es": 'No vendible'},
    'Direto': {
        "en-US": 'Direct',
        "es": 'Directo'},
    'Indireto': {
        "en-US": 'Indirect',
        "es": 'Indirecto'},
    # ---- Login próprio (e-mail + senha) e contas de acesso ----
    "Entre com o e-mail e a senha do seu acesso.": {
        "en-US": 'Sign in with your e-mail and password.',
        "es": 'Entre con el correo y la contraseña de su acceso.'},
    "E-mail": {
        "en-US": 'E-mail',
        "es": 'Correo'},
    "Senha": {
        "en-US": 'Password',
        "es": 'Contraseña'},
    "Repita a senha": {
        "en-US": 'Repeat the password',
        "es": 'Repita la contraseña'},
    "Esqueceu a senha? Peça ao administrador do Peoples uma senha temporária.": {
        "en-US": 'Forgot your password? Ask the Peoples administrator for a temporary one.',
        "es": '¿Olvidó la contraseña? Pida al administrador de Peoples una contraseña temporal.'},
    "Primeiro acesso: ainda não há nenhum usuário. Crie o administrador inicial.": {
        "en-US": 'First access: there are no users yet. Create the initial administrator.',
        "es": 'Primer acceso: aún no hay ningún usuario. Cree el administrador inicial.'},
    "Criar administrador inicial": {
        "en-US": 'Create initial administrator',
        "es": 'Crear administrador inicial'},
    "E-mail ou senha inválidos.": {
        "en-US": 'Invalid e-mail or password.',
        "es": 'Correo o contraseña inválidos.'},
    "Muitas tentativas. Aguarde {s} segundos e tente de novo.": {
        "en-US": 'Too many attempts. Wait {s} seconds and try again.',
        "es": 'Demasiados intentos. Espere {s} segundos e intente de nuevo.'},
    "As senhas não conferem.": {
        "en-US": 'The passwords do not match.',
        "es": 'Las contraseñas no coinciden.'},
    "A senha precisa ter pelo menos 8 caracteres.": {
        "en-US": 'The password must have at least 8 characters.',
        "es": 'La contraseña debe tener al menos 8 caracteres.'},
    "A senha é longa demais (máximo 128 caracteres).": {
        "en-US": 'The password is too long (128 characters max).',
        "es": 'La contraseña es demasiado larga (máximo 128 caracteres).'},
    "A senha não pode começar nem terminar com espaço.": {
        "en-US": 'The password cannot start or end with a space.',
        "es": 'La contraseña no puede empezar ni terminar con espacio.'},
    "E-mail inválido.": {
        "en-US": 'Invalid e-mail.',
        "es": 'Correo inválido.'},
    "Já existe um usuário: peça a senha a quem administra.": {
        "en-US": 'A user already exists: ask the administrator for a password.',
        "es": 'Ya existe un usuario: pida la contraseña a quien administra.'},
    "Trocar senha": {
        "en-US": 'Change password',
        "es": 'Cambiar contraseña'},
    "Defina uma nova senha para continuar.": {
        "en-US": 'Set a new password to continue.',
        "es": 'Defina una nueva contraseña para continuar.'},
    "Senha atual": {
        "en-US": 'Current password',
        "es": 'Contraseña actual'},
    "Nova senha": {
        "en-US": 'New password',
        "es": 'Nueva contraseña'},
    "Salvar nova senha": {
        "en-US": 'Save new password',
        "es": 'Guardar nueva contraseña'},
    "Voltar ao sistema": {
        "en-US": 'Back to the system',
        "es": 'Volver al sistema'},
    "Senha atual incorreta.": {
        "en-US": 'Current password is incorrect.',
        "es": 'Contraseña actual incorrecta.'},
    "Senha alterada.": {
        "en-US": 'Password changed.',
        "es": 'Contraseña cambiada.'},
    "Senha de acesso": {
        "en-US": 'Login password',
        "es": 'Contraseña de acceso'},
    "Tem senha definida": {
        "en-US": 'Has a password',
        "es": 'Tiene contraseña definida'},
    "Sem senha — não consegue entrar": {
        "en-US": 'No password — cannot sign in',
        "es": 'Sin contraseña — no puede entrar'},
    "troca pendente no próximo login": {
        "en-US": 'change pending at next login',
        "es": 'cambio pendiente en el próximo inicio'},
    "Nova senha (mínimo {n} caracteres)": {
        "en-US": 'New password ({n} characters minimum)',
        "es": 'Nueva contraseña (mínimo {n} caracteres)'},
    "Exigir troca no primeiro acesso": {
        "en-US": 'Require change at first login',
        "es": 'Exigir cambio en el primer acceso'},
    "Definir senha": {
        "en-US": 'Set password',
        "es": 'Definir contraseña'},
    "Remover senha (bloqueia o login)": {
        "en-US": 'Remove password (blocks login)',
        "es": 'Quitar contraseña (bloquea el acceso)'},
    "Remover a senha de {email}? A pessoa deixa de conseguir entrar.": {
        "en-US": 'Remove the password of {email}? The person will no longer be able to sign in.',
        "es": '¿Quitar la contraseña de {email}? La persona ya no podrá entrar.'},
    "Senha definida para {email}.": {
        "en-US": 'Password set for {email}.',
        "es": 'Contraseña definida para {email}.'},
    "Senha removida de {email}.": {
        "en-US": 'Password removed from {email}.',
        "es": 'Contraseña quitada de {email}.'},
    "Essa conta não tem senha definida.": {
        "en-US": 'This account has no password.',
        "es": 'Esa cuenta no tiene contraseña definida.'},
    "Você não pode remover a própria senha.": {
        "en-US": 'You cannot remove your own password.',
        "es": 'No puede quitar su propia contraseña.'},
    "Este colaborador não tem e-mail; cadastre um e-mail antes de definir a senha.": {
        "en-US": 'This employee has no e-mail; add one before setting a password.',
        "es": 'Este colaborador no tiene correo; registre uno antes de definir la contraseña.'},
    "Contas de acesso": {
        "en-US": 'Login accounts',
        "es": 'Cuentas de acceso'},
    "Quem consegue entrar no sistema: e-mail + senha do próprio Peoples. Colaboradores recebem a senha pelo botão Editar da lista acima; contas fora do organograma (o operador, por exemplo) entram por aqui.": {
        "en-US": "Who can sign in: e-mail + Peoples' own password. Employees get a password through Edit in the list above; accounts outside the org chart (the operator, for instance) are created here.",
        "es": 'Quién puede entrar: correo + contraseña propia de Peoples. Los colaboradores reciben la contraseña por Editar en la lista de arriba; las cuentas fuera del organigrama (el operador, por ejemplo) se crean aquí.'},
    "Atualizada em": {
        "en-US": 'Updated on',
        "es": 'Actualizada el'},
    "Situação": {
        "en-US": 'Status',
        "es": 'Situación'},
    "fora do organograma": {
        "en-US": 'outside the org chart',
        "es": 'fuera del organigrama'},
    "Troca pendente": {
        "en-US": 'Change pending',
        "es": 'Cambio pendiente'},
    "ativa": {
        "en-US": 'active',
        "es": 'activa'},
    "Remover": {
        "en-US": 'Remove',
        "es": 'Quitar'},
    "Nenhuma conta ainda. O primeiro acesso cria o administrador inicial na tela de login.": {
        "en-US": 'No accounts yet. The first access creates the initial administrator on the login screen.',
        "es": 'Aún no hay cuentas. El primer acceso crea el administrador inicial en la pantalla de entrada.'},
    "Nova conta": {
        "en-US": 'New account',
        "es": 'Nueva cuenta'},
    "Criar conta": {
        "en-US": 'Create account',
        "es": 'Crear cuenta'},
    "Login": {
        "en-US": 'Login',
        "es": 'Acceso'},
    "sim": {
        "en-US": 'yes',
        "es": 'sí'},
    "não": {
        "en-US": 'no',
        "es": 'no'},
    "Troca de senha": {
        "en-US": 'Password change',
        "es": 'Cambio de contraseña'},
    "senha de acesso definida": {
        "en-US": 'login password set',
        "es": 'contraseña de acceso definida'},
    "senha de acesso removida": {
        "en-US": 'login password removed',
        "es": 'contraseña de acceso quitada'},
    "O resto do estado, um documento JSONB por organograma: configuração, RBAC, colapso, orientação, filtros, provisionamentos e log de acessos.": {
        "en-US": 'The rest of the state, one JSONB document per org chart: configuration, RBAC, collapse, orientation, filters, provisioning and access log.',
        "es": 'El resto del estado, un documento JSONB por organigrama: configuración, RBAC, colapso, orientación, filtros, aprovisionamientos y registro de accesos.'},
    "Credenciais do login: e-mail e hash scrypt da senha — nunca a senha. Global: vale para todos os organogramas.": {
        "en-US": 'Login credentials: e-mail and scrypt hash of the password — never the password. Global: valid for every org chart.',
        "es": 'Credenciales del acceso: correo y hash scrypt de la contraseña — nunca la contraseña. Global: vale para todos los organigramas.'},
    # ---- Skills por colaborador (.md, aderência) ----
    "Skills do cargo": {
        "en-US": 'Role Skills',
        "es": 'Skills del cargo'},
    "Baixar Skills (.md)": {
        "en-US": 'Download Skills (.md)',
        "es": 'Descargar Skills (.md)'},
    "Skills do colaborador (.md)": {
        "en-US": 'Employee Skills (.md)',
        "es": 'Skills del colaborador (.md)'},
    "Baixar Skills de todos (.zip de .md, um por colaborador)": {
        "en-US": "Download everyone's Skills (.zip of .md, one per employee)",
        "es": 'Descargar Skills de todos (.zip de .md, uno por colaborador)'},
    "Aderência": {
        "en-US": 'Fit',
        "es": 'Adherencia'},
    "Técnicas": {
        "en-US": 'Technical',
        "es": 'Técnicas'},
    "Comportamentais": {
        "en-US": 'Behavioral',
        "es": 'Conductuales'},
    "Requisitos": {
        "en-US": 'Requirements',
        "es": 'Requisitos'},
    "✓ = competência declarada no cadastro da pessoa; ○ = desejável no cargo e ainda não declarada (gap para o PDI).": {
        "en-US": "✓ = skill declared in the person's record; ○ = desired for the role and not yet declared (gap for the IDP).",
        "es": '✓ = competencia declarada en el registro de la persona; ○ = deseable en el cargo y aún no declarada (brecha para el PDI).'},
    "Cargo sem ficha Skills no recorte atual.": {
        "en-US": 'Role without a Skills sheet in the current scope.',
        "es": 'Cargo sin ficha Skills en el recorte actual.'},
    "Código": {
        "en-US": 'Code',
        "es": 'Código'},
    "Vínculo": {
        "en-US": 'Contract',
        "es": 'Vínculo'},
    "Admissão": {
        "en-US": 'Hire date',
        "es": 'Ingreso'},
    "anos de casa": {
        "en-US": 'years of tenure',
        "es": 'años en la empresa'},
    "Gestor direto": {
        "en-US": 'Direct manager',
        "es": 'Gestor directo'},
    "Liderados diretos": {
        "en-US": 'Direct reports',
        "es": 'Subordinados directos'},
    "Competências declaradas": {
        "en-US": 'Declared skills',
        "es": 'Competencias declaradas'},
    "Accountabilities": {
        "en-US": 'Accountabilities',
        "es": 'Accountabilities'},
    "Aderência ao Skills do cargo": {
        "en-US": 'Fit to the role Skills',
        "es": 'Adherencia al Skills del cargo'},
    "{k} de {n} competências técnicas desejáveis declaradas ({pct}%).": {
        "en-US": '{k} of {n} desired technical skills declared ({pct}%).',
        "es": '{k} de {n} competencias técnicas deseables declaradas ({pct}%).'},
    "Gerado em": {
        "en-US": 'Generated on',
        "es": 'Generado el'},
    "colaboradores": {
        "en-US": 'employees',
        "es": 'colaboradores'},
    "GPlanSiS|ORG · Agentes": {
        "en-US": 'GPlanSiS|ORG · Agents',
        "es": 'GPlanSiS|ORG · Agentes'},
    "GPlanSiS|ORG — os agentes de inteligência organizacional": {
        "en-US": 'GPlanSiS|ORG — the organizational intelligence agents',
        "es": 'GPlanSiS|ORG — los agentes de inteligencia organizacional'},
    "Cota de IA do mês": {
        "en-US": 'Monthly AI quota',
        "es": 'Cuota mensual de IA'},
    "Gasto este mês: US$ {gasto} de US$ {cota}.": {
        "en-US": 'Spent this month: US$ {gasto} of US$ {cota}.',
        "es": 'Gastado este mes: US$ {gasto} de US$ {cota}.'},
    "Cota mensal padrão por pessoa (US$)": {
        "en-US": 'Default monthly quota per person (US$)',
        "es": 'Cuota mensual predeterminada por persona (US$)'},
    "Salvar cota": {
        "en-US": 'Save quota',
        "es": 'Guardar cuota'},
    "cota de IA da MarIA": {
        "en-US": 'MarIA AI quota',
        "es": 'cuota de IA de MarIA'},
    "cota de IA de uma pessoa": {
        "en-US": "a person's AI quota",
        "es": 'cuota de IA de una persona'},
}


def traduzir(texto: str, idioma: str = PADRAO, **params) -> str:
    """Texto no idioma pedido, com interpolação opcional.

    Sem entrada no catálogo devolve o português — nunca vazio, nunca a chave
    crua com o sufixo de contexto.
    """
    if not texto:
        return ""
    idioma = valido(idioma)
    saida = sem_contexto(texto)
    if idioma != PADRAO:
        saida = (CATALOGO.get(texto, {}).get(idioma) or "").strip() or saida
    if params:
        try:
            saida = saida.format(**params)
        except (KeyError, IndexError, ValueError):
            # Tradução com marcador errado não pode derrubar a tela: cai no
            # português, que veio do fonte e portanto casa com os parâmetros.
            saida = sem_contexto(texto)
            try:
                saida = saida.format(**params)
            except (KeyError, IndexError, ValueError):
                pass
    return saida


def cobertura() -> dict[str, dict]:
    """Quanto de cada idioma está preenchido — usado pela tela e pelo teste."""
    total = len(CATALOGO)
    saida = {}
    for idioma in TRADUZIDOS:
        feitas = sum(1 for v in CATALOGO.values() if (v.get(idioma) or "").strip())
        saida[idioma] = {"feitas": feitas, "total": total,
                         "pct": round(100 * feitas / total) if total else 0}
    return saida


def faltando(idioma: str) -> list[str]:
    return sorted(k for k, v in CATALOGO.items()
                  if not (v.get(idioma) or "").strip())
