"""Matriz de competências do GPlanSiS|Peoples — gera o Skills (GEP-FOR-003) de
TODOS os cargos de todos os organogramas registrados.

Método (RH/DP): cada cargo é classificado em uma **família funcional** (o domínio
técnico: automação, elétrica, comercial, RH…), uma **senioridade** (aprendiz,
júnior, pleno, sênior, especialista) e um **papel** na hierarquia (execução,
liderança técnica, coordenação, gerência, diretoria). A ficha nasce do
cruzamento: a família dá o conteúdo técnico, as ferramentas, a formação, as
certificações e os KPIs; o papel dá as responsabilidades de gestão, as
competências comportamentais, a experiência exigida e o idioma; a senioridade
dá o **nível esperado de proficiência (1–5)** em cada competência técnica e a
trilha de carreira (próximo passo).

Escala de proficiência (a mesma para toda a casa):
    1 Iniciante · 2 Básico · 3 Autônomo · 4 Avançado · 5 Referência

O que sai é a camada "escrito pelo RH" do Skills (`Config.dcr_cargos`), no
formato do formulário — missão em prosa; responsabilidades, requisitos e
competências uma por linha, com um prefixo entre colchetes que diz o tipo do
item ([Técnica] [Comportamental] [Ferramenta] [Trilha] / [Formação]
[Experiência] [Certificação] [Idioma] [Disponibilidade]). O RH edita depois
pela tela, ficha a ficha; o que ele escrever vence.

    python ferramentas/gerar_skills.py            # só cargos ainda sem ficha
    python ferramentas/gerar_skills.py --forcar   # reescreve todas as fichas
    python ferramentas/gerar_skills.py --so-mostrar "Analista de Automação Pleno"

Idempotente. Roda também no servidor (com o serviço parado), sobre `dados/`.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from orga import dcr as dcrmod          # noqa: E402  (módulo puro)
from orga import organogramas           # noqa: E402

ESCALA = {1: "Iniciante", 2: "Básico", 3: "Autônomo", 4: "Avançado", 5: "Referência"}
MARCA = "Matriz de competências Peoples v1"


def sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


# =============================================================================
# FAMÍLIAS FUNCIONAIS
# =============================================================================
# Cada família: nome, domínio (o que a área entrega), competências técnicas
# (6–8, em ordem de centralidade), ferramentas, formação típica, certificações,
# KPIs e responsabilidades-núcleo (verbos no infinitivo; o papel completa).
FAMILIAS: dict[str, dict] = {
    "exec": dict(
        nome="Direção Executiva",
        dominio="a estratégia, o resultado e a cultura da organização",
        tecnicas=["Planejamento estratégico e desdobramento de metas (OKR/BSC)",
                  "Gestão econômico-financeira e leitura de P&L", "Governança corporativa e compliance",
                  "Gestão de portfólio de negócios e M&A", "Relacionamento institucional e com investidores",
                  "Gestão de riscos empresariais", "Transformação organizacional e cultura"],
        ferramentas=["BI executivo (Power BI)", "ERP (SAP)", "GPlanSiS|Peoples", "GPlanSiS|PriorIA", "Microsoft 365"],
        formacao=["Graduação em Engenharia, Administração ou Economia", "MBA ou mestrado em gestão/negócios"],
        certificacoes=["Formação em conselhos (IBGC) — desejável"],
        kpis=["EBITDA e margem", "Crescimento de receita", "NPS de clientes", "Engajamento (Peoples Trust Index)"],
        nucleo=["Definir a visão, a estratégia e as prioridades da organização e desdobrá-las em metas",
                "Responder pelo resultado econômico-financeiro consolidado",
                "Presidir os fóruns de governança e a relação com o conselho",
                "Decidir investimentos, parcerias e o portfólio de negócios",
                "Sustentar a cultura e os valores (TeamWork, Respect, Innovation, Ownership)",
                "Garantir a sucessão da liderança e o desenvolvimento dos executivos"]),
    "financeiro": dict(
        nome="Finanças, Controladoria e Fiscal",
        dominio="o resultado, o caixa, a conformidade fiscal e a informação gerencial",
        tecnicas=["Contabilidade gerencial e custos industriais", "Planejamento financeiro, orçamento e forecast",
                  "Tesouraria, fluxo de caixa e capital de giro", "Tributação (ICMS, IPI, PIS/COFINS, ISS) e obrigações acessórias",
                  "Análise de indicadores e reporte gerencial", "Controles internos, auditoria e compliance",
                  "Precificação e análise de rentabilidade por projeto"],
        ferramentas=["SAP (FI/CO)", "Excel avançado", "Power BI", "Sistemas fiscais (SPED, NF-e)", "Bancos e conciliação"],
        formacao=["Graduação em Ciências Contábeis, Administração, Economia ou Engenharia de Produção",
                  "Pós-graduação em Controladoria/Finanças — desejável a partir do pleno"],
        certificacoes=["CRC ativo (funções contábeis/fiscais)", "CPA-10/CPA-20 ou CFA — desejável em tesouraria"],
        kpis=["Acuracidade do forecast", "Prazo de fechamento mensal", "Aderência ao orçamento", "Zero autuações fiscais"],
        nucleo=["Elaborar e acompanhar orçamento, forecast e análise de desvios",
                "Apurar custos e rentabilidade por projeto, produto e unidade de negócio",
                "Garantir a conformidade fiscal e tributária e as obrigações acessórias",
                "Conduzir o fechamento contábil-gerencial e o reporte executivo",
                "Gerir caixa, pagamentos, recebimentos e relacionamento bancário",
                "Sustentar controles internos e atender auditorias"]),
    "juridico": dict(
        nome="Jurídico e Compliance",
        dominio="a segurança jurídica dos contratos, das relações e das decisões",
        tecnicas=["Direito contratual e empresarial", "Direito do trabalho e relações sindicais",
                  "LGPD e proteção de dados", "Compliance, anticorrupção e ética",
                  "Contencioso e gestão de escritórios externos", "Propriedade intelectual e contratos de tecnologia"],
        ferramentas=["Gestão de contratos (CLM)", "Bases jurídicas", "Microsoft 365", "GPlanSiS|Peoples"],
        formacao=["Graduação em Direito", "Pós-graduação em Direito Empresarial ou Trabalhista — desejável"],
        certificacoes=["OAB ativa", "Certificação em Compliance (CPC-A/LEC) — desejável"],
        kpis=["Prazo de análise contratual", "Passivo trabalhista e cível", "Conformidade LGPD", "Contratos padronizados"],
        nucleo=["Analisar, redigir e negociar contratos com clientes, fornecedores e parceiros",
                "Orientar a empresa em questões trabalhistas, cíveis e regulatórias",
                "Conduzir o programa de compliance e a governança de dados (LGPD)",
                "Gerir o contencioso e os escritórios externos",
                "Assessorar a diretoria em decisões com impacto jurídico"]),
    "cto": dict(
        nome="Direção Técnica e Tecnologia",
        dominio="a estratégia tecnológica, a arquitetura das soluções e a excelência da engenharia",
        tecnicas=["Estratégia e roadmap tecnológico", "Arquitetura de soluções de automação e digitalização industrial",
                  "Gestão de portfólio de projetos de engenharia", "Indústria 4.0, IIoT e dados industriais",
                  "Cibersegurança industrial (IEC 62443)", "Gestão de P&D e inovação", "Governança de TI e OT"],
        ferramentas=["TIA Portal / plataformas Siemens e concorrentes", "Cloud (Azure/AWS)", "Power BI", "GPlanSiS|PriorIA", "Git"],
        formacao=["Graduação em Engenharia (Controle e Automação, Elétrica, Computação)",
                  "Pós-graduação/MBA em gestão de tecnologia ou inovação"],
        certificacoes=["Certificações de plataforma (Siemens, Rockwell) — desejável", "ITIL/COBIT — desejável"],
        kpis=["Margem técnica dos projetos", "Retrabalho de engenharia", "Time-to-market de soluções", "Incidentes de segurança"],
        nucleo=["Definir a estratégia tecnológica e o roadmap de produtos e soluções",
                "Responder pela arquitetura, pelos padrões e pela qualidade da engenharia",
                "Conduzir inovação, P&D e parcerias tecnológicas",
                "Garantir cibersegurança e governança de TI/OT",
                "Desenvolver a liderança técnica e a carreira dos engenheiros"]),
    "operacoes": dict(
        nome="Operações e Gestão de Projetos",
        dominio="a entrega dos projetos no prazo, no custo e na qualidade contratados",
        tecnicas=["Gestão de projetos (escopo, prazo, custo, risco)", "Planejamento e controle (EAP, cronograma, curva S)",
                  "Gestão de contratos, aditivos e pleitos", "Gestão de equipes multidisciplinares e terceiros",
                  "Comissionamento e aceite (FAT/SAT)", "Gestão de mudanças e comunicação com o cliente",
                  "Análise de margem e resultado por projeto"],
        ferramentas=["MS Project / GPlanSiS|PriorIA", "SAP (PS)", "Power BI", "Microsoft 365", "GPlanSiS|Peoples"],
        formacao=["Graduação em Engenharia ou Administração", "Pós-graduação em Gestão de Projetos — desejável"],
        certificacoes=["PMP ou CAPM (PMI)", "Formação em metodologias ágeis (PSM/PO) — desejável"],
        kpis=["Aderência a prazo (OTD)", "Margem realizada vs. vendida", "Satisfação do cliente", "Pleitos aprovados"],
        nucleo=["Planejar, executar e controlar projetos do contrato à entrega e aceite",
                "Gerir escopo, prazo, custo, riscos e mudanças com o cliente",
                "Coordenar equipes de engenharia, montagem, comissionamento e fornecedores",
                "Responder pela margem e pelo resultado dos projetos sob sua carteira",
                "Reportar status, riscos e decisões à liderança e ao cliente"]),
    "automacao": dict(
        nome="Automação, Instrumentação e Controle",
        dominio="o controle, a supervisão e a integração de processos industriais",
        tecnicas=["Programação de CLP (Siemens S7/TIA Portal, Rockwell, Schneider)", "Sistemas SCADA/HMI (WinCC, FactoryTalk, Ignition)",
                  "Redes industriais (Profinet, Profibus, Ethernet/IP, Modbus, OPC UA)", "Instrumentação, malhas de controle e sintonia PID",
                  "Acionamentos: inversores, servoacionamentos e motion", "Segurança de máquinas (NR-12, ISO 13849, SIL)",
                  "Comissionamento, start-up e testes (FAT/SAT)", "Documentação técnica (lógica, listas de I/O, as-built)"],
        ferramentas=["TIA Portal", "WinCC / Ignition", "Studio 5000", "EPLAN (leitura)", "Wireshark / PRONETA", "Git"],
        formacao=["Técnico ou graduação em Automação Industrial, Mecatrônica, Controle e Automação ou Elétrica"],
        certificacoes=["Siemens SITRAIN (TIA Portal, Profinet) — desejável", "NR-10 e NR-12 (obrigatórias em campo)", "NR-35 quando aplicável"],
        kpis=["Horas de comissionamento vs. orçado", "Retrabalho em campo", "Não conformidades em FAT/SAT", "Reuso de padrões"],
        nucleo=["Desenvolver lógica de controle, telas de supervisão e integração de redes industriais",
                "Especificar e configurar instrumentos, acionamentos e componentes de automação",
                "Comissionar e colocar em marcha sistemas em campo, com testes documentados (FAT/SAT)",
                "Produzir e manter a documentação técnica dos sistemas (lógicas, listas, as-built)",
                "Aplicar os padrões de engenharia da casa e propor melhorias aos padrões",
                "Prestar suporte técnico a clientes e à equipe de serviços"]),
    "eletrica": dict(
        nome="Engenharia Elétrica e Painéis",
        dominio="o projeto, a fabricação e a instalação de sistemas e painéis elétricos",
        tecnicas=["Projeto elétrico industrial (unifilares, trifilares, diagramas de comando)", "Dimensionamento de painéis (NBR IEC 61439, NBR 5410, NBR 14039)",
                  "Projeto de painéis de comando, CCM e distribuição", "Coordenação e seletividade de proteções",
                  "Instalações elétricas industriais e infraestrutura", "Normas de segurança (NR-10, NBR 5410, arco elétrico)",
                  "Lista de materiais, orçamento e especificação de componentes", "Inspeção e testes de painéis"],
        ferramentas=["EPLAN Electric P8", "AutoCAD Electrical", "SEE Electrical", "Excel avançado", "SAP (MM/PS)"],
        formacao=["Técnico em Eletrotécnica ou graduação em Engenharia Elétrica"],
        certificacoes=["NR-10 (obrigatória)", "CREA/CFT ativo para responsabilidade técnica", "EPLAN certified — desejável"],
        kpis=["Erros de projeto detectados na fabricação", "Prazo de emissão de projeto", "Custo de material vs. orçado", "Não conformidades em inspeção"],
        nucleo=["Elaborar projetos elétricos e de painéis conforme normas e requisitos do cliente",
                "Dimensionar componentes, proteções e barramentos e gerar listas de materiais",
                "Acompanhar a fabricação, inspeção e testes dos painéis",
                "Dar suporte à montagem, instalação e comissionamento em campo",
                "Manter os padrões de projeto e a biblioteca de macros/símbolos"]),
    "manutencao": dict(
        nome="Manutenção Industrial",
        dominio="a disponibilidade e a confiabilidade dos ativos produtivos",
        tecnicas=["Manutenção preventiva, preditiva e corretiva", "Confiabilidade (RCM, FMEA, análise de falhas)",
                  "Manutenção elétrica e de automação", "Planejamento e controle da manutenção (PCM)",
                  "Gestão de sobressalentes e contratos de manutenção", "Segurança em intervenções (NR-10, NR-12, permissão de trabalho)"],
        ferramentas=["CMMS / SAP PM", "Analisadores de vibração e termografia", "Multímetros e instrumentos", "Excel / Power BI"],
        formacao=["Técnico em Eletromecânica/Eletrotécnica ou graduação em Engenharia (Elétrica, Mecânica)"],
        certificacoes=["NR-10 e NR-12", "Certificação em análise de vibração/termografia — desejável"],
        kpis=["Disponibilidade (OEE)", "MTBF / MTTR", "Aderência ao plano preventivo", "Custo de manutenção por ativo"],
        nucleo=["Planejar e executar o plano de manutenção preventiva e preditiva dos ativos",
                "Atender e analisar falhas, eliminando causas-raiz",
                "Gerir sobressalentes, ferramentas e contratos de terceiros",
                "Garantir a segurança das intervenções e o registro no CMMS"]),
    "mecanica": dict(
        nome="Engenharia Mecânica",
        dominio="o projeto mecânico de máquinas, estruturas e dispositivos",
        tecnicas=["Projeto mecânico 3D e detalhamento 2D", "Resistência dos materiais e dimensionamento",
                  "Processos de fabricação (usinagem, soldagem, caldeiraria)", "Tolerâncias, ajustes e GD&T",
                  "Seleção de componentes (rolamentos, transmissões, pneumática)", "Normas de segurança de máquinas (NR-12)"],
        ferramentas=["SolidWorks / Inventor", "AutoCAD", "Simulação FEA (básica)", "SAP (MM)"],
        formacao=["Técnico em Mecânica ou graduação em Engenharia Mecânica/Mecatrônica"],
        certificacoes=["CSWA/CSWP (SolidWorks) — desejável", "NR-12"],
        kpis=["Retrabalho de fabricação por erro de projeto", "Prazo de emissão", "Custo de material", "Reuso de componentes padrão"],
        nucleo=["Desenvolver projetos mecânicos e detalhamento para fabricação",
                "Dimensionar estruturas, componentes e transmissões",
                "Acompanhar fabricação, montagem e ajustes em campo",
                "Manter a biblioteca de peças e os padrões de projeto"]),
    "processos": dict(
        nome="Engenharia de Processos",
        dominio="a eficiência, a padronização e a melhoria dos processos produtivos e de engenharia",
        tecnicas=["Mapeamento e modelagem de processos (BPMN, VSM)", "Lean Manufacturing e Kaizen",
                  "Análise de dados de processo e indicadores", "Gestão da mudança e padronização (POP, instruções)",
                  "Engenharia de processos industriais (balanço, layout, capacidade)", "Ferramentas da qualidade (PDCA, A3, Ishikawa)"],
        ferramentas=["Bizagi / Visio", "Excel / Power BI", "Minitab (básico)", "GPlanSiS|PriorIA"],
        formacao=["Graduação em Engenharia de Produção, Química, Mecânica ou Processos"],
        certificacoes=["Lean Six Sigma Green Belt — desejável (Black Belt para sênior)"],
        kpis=["Ganho de produtividade", "Redução de lead time", "Processos padronizados", "Projetos de melhoria concluídos"],
        nucleo=["Mapear, analisar e redesenhar processos com foco em eficiência e qualidade",
                "Conduzir projetos de melhoria contínua com a operação",
                "Padronizar e documentar processos, instruções e indicadores",
                "Medir resultados e sustentar os ganhos"]),
    "civil": dict(
        nome="Engenharia Civil",
        dominio="a infraestrutura civil dos projetos industriais",
        tecnicas=["Projeto civil e compatibilização com elétrica/mecânica", "Orçamento e planejamento de obras",
                  "Fiscalização e gestão de empreiteiras", "Normas técnicas e segurança em obras (NR-18)"],
        ferramentas=["AutoCAD / Revit", "MS Project", "Excel", "SAP"],
        formacao=["Graduação em Engenharia Civil"], certificacoes=["CREA ativo", "NR-18/NR-35"],
        kpis=["Prazo de obra", "Custo vs. orçado", "Não conformidades", "Acidentes zero"],
        nucleo=["Desenvolver e compatibilizar projetos civis com as demais disciplinas",
                "Orçar, planejar e fiscalizar obras e empreiteiras",
                "Garantir conformidade normativa e segurança nas obras"]),
    "digital": dict(
        nome="Tecnologia, Software e Dados",
        dominio="as plataformas digitais, os dados e a infraestrutura de TI/OT",
        tecnicas=["Desenvolvimento de software (Python, JavaScript/TypeScript, SQL)", "Arquitetura de sistemas, APIs e integração (REST, MQTT, OPC UA)",
                  "Engenharia e análise de dados (SQL, modelagem, pipelines, BI)", "Cloud e DevOps (Azure/AWS, Docker, CI/CD, Git)",
                  "Infraestrutura, redes e segurança da informação", "IIoT e plataformas de dados industriais",
                  "Product management e descoberta de produto", "Machine learning aplicado (para funções de dados/IA)"],
        ferramentas=["Git/GitHub", "Docker", "PostgreSQL", "Power BI", "Python/FastAPI", "Azure/AWS", "Jira/GPlanSiS|PriorIA"],
        formacao=["Graduação em Ciência da Computação, Engenharia de Software, Sistemas de Informação ou correlatas"],
        certificacoes=["Azure/AWS Fundamentals ou Associate — desejável", "ITIL Foundation (infra/suporte)", "PSPO/CSPO (product owner)"],
        kpis=["Disponibilidade dos sistemas (SLA)", "Lead time de entrega", "Incidentes e MTTR", "Adoção das plataformas"],
        nucleo=["Desenvolver, integrar e manter sistemas, plataformas e pipelines de dados",
                "Garantir segurança, disponibilidade e desempenho da infraestrutura de TI/OT",
                "Traduzir necessidades do negócio em requisitos, backlog e soluções",
                "Documentar arquitetura, código e operação",
                "Prestar suporte e treinar usuários nas plataformas"]),
    "comercial": dict(
        nome="Comercial e Pré-vendas",
        dominio="a receita, a carteira de clientes e a qualidade das propostas",
        tecnicas=["Prospecção, qualificação e gestão de pipeline (CRM)", "Levantamento de requisitos e engenharia de proposta",
                  "Precificação, margem e negociação comercial", "Gestão de contas-chave e relacionamento executivo",
                  "Conhecimento técnico das soluções (automação, digitalização industrial)", "Contratos, condições comerciais e licitações",
                  "Forecast de vendas e análise de funil"],
        ferramentas=["CRM (HubSpot/Dynamics)", "Excel / Power BI", "Configuradores e templates de proposta", "LinkedIn Sales Navigator", "Microsoft 365"],
        formacao=["Graduação em Engenharia, Administração ou Marketing"],
        certificacoes=["Formação em vendas consultivas (SPIN/Challenger) — desejável", "Certificações de fabricante para pré-vendas"],
        kpis=["Receita e margem vendida", "Taxa de conversão do funil", "Ciclo de venda", "Acuracidade do forecast"],
        nucleo=["Prospectar, qualificar e desenvolver oportunidades no mercado-alvo",
                "Elaborar propostas técnico-comerciais com escopo, custo e margem consistentes",
                "Negociar e fechar contratos dentro da política comercial",
                "Gerir o relacionamento e a carteira de clientes após a venda",
                "Manter o CRM atualizado e alimentar o forecast"]),
    "marketing": dict(
        nome="Marketing e Comunicação",
        dominio="a marca, a geração de demanda e a comunicação interna e externa",
        tecnicas=["Estratégia de marca e posicionamento", "Marketing digital, conteúdo e inbound",
                  "Comunicação interna e endomarketing", "Design gráfico e identidade visual",
                  "Eventos, feiras e relacionamento com o mercado", "Métricas de marketing e atribuição"],
        ferramentas=["Adobe Creative Cloud / Figma", "HubSpot / RD Station", "Google Analytics", "Redes sociais", "Microsoft 365"],
        formacao=["Graduação em Marketing, Publicidade, Comunicação Social ou Design"],
        certificacoes=["Google/HubSpot Inbound — desejável"],
        kpis=["Leads qualificados (MQL/SQL)", "Alcance e engajamento", "Custo por lead", "NPS interno da comunicação"],
        nucleo=["Planejar e executar campanhas de geração de demanda e conteúdo",
                "Zelar pela identidade visual e pela consistência da marca",
                "Conduzir a comunicação interna e os rituais de cultura",
                "Organizar eventos, feiras e materiais de apoio a vendas",
                "Medir resultados e otimizar canais"]),
    "rh": dict(
        nome="Gente, Gestão e Departamento Pessoal",
        dominio="o ciclo de vida das pessoas — atração, desenvolvimento, performance, cultura e folha",
        tecnicas=["Recrutamento e seleção por competências", "Gestão de performance, feedback e Conversa de Valor",
                  "Desenvolvimento organizacional, treinamento e PDI", "Administração de pessoal, folha, ponto e legislação trabalhista (CLT, eSocial)",
                  "Cargos, carreira e estrutura organizacional (Skills)", "Clima, engajamento e cultura (Avaliação Mestre / PTI)",
                  "People Analytics e indicadores de RH", "LGPD aplicada a dados de pessoas"],
        ferramentas=["GPlanSiS|Peoples", "Sistemas de folha/ponto", "ATS (Gupy)", "Power BI", "Microsoft 365"],
        formacao=["Graduação em Psicologia, Administração, Gestão de RH ou Pedagogia"],
        certificacoes=["Analista comportamental (DISC/MBTI) — desejável", "Formação em eSocial/legislação trabalhista (DP)"],
        kpis=["Turnover e retenção", "Tempo de fechamento de vagas", "Cobertura de PDI e Conversa de Valor", "PTI (Peoples Trust Index)"],
        nucleo=["Atrair, selecionar e integrar pessoas alinhadas à cultura e aos requisitos dos cargos",
                "Conduzir o ciclo de performance: Conversa de Valor, Avaliação, PDI e sucessão",
                "Manter o organograma, as descrições de cargo (Skills) e a estrutura no Peoples",
                "Administrar folha, benefícios, ponto e obrigações legais com zero passivo",
                "Medir clima e engajamento e agir sobre os resultados",
                "Apoiar líderes em feedback, desenvolvimento de equipes e decisões sobre pessoas"]),
    "suprimentos": dict(
        nome="Suprimentos, Compras e Logística",
        dominio="o abastecimento no prazo, no custo e na qualidade especificados",
        tecnicas=["Compras técnicas e negociação com fornecedores", "Gestão de fornecedores (homologação, avaliação, SLA)",
                  "Planejamento de materiais (MRP) e follow-up (diligenciamento)", "Gestão de estoque, almoxarifado e inventário",
                  "Logística, importação e transporte", "Custos de aquisição (TCO) e saving"],
        ferramentas=["SAP (MM)", "Excel / Power BI", "Portais de fornecedores", "WMS (básico)"],
        formacao=["Técnico em Logística/Administração ou graduação em Administração, Engenharia de Produção ou Logística"],
        certificacoes=["Formação em negociação e compras (CPSM/IBS) — desejável", "Operação de empilhadeira (almoxarifado)"],
        kpis=["OTIF de fornecedores", "Saving em compras", "Acuracidade de estoque", "Ruptura de materiais em produção"],
        nucleo=["Comprar materiais e serviços no prazo, custo e especificação, seguindo a política de compras",
                "Desenvolver, homologar e avaliar fornecedores",
                "Acompanhar pedidos (diligenciamento) e garantir a entrega para a produção e os projetos",
                "Receber, armazenar, separar e inventariar materiais com rastreabilidade",
                "Manter o cadastro e os dados-mestre no ERP"]),
    "pcp": dict(
        nome="Planejamento e Controle da Produção (PCP)",
        dominio="a programação, a capacidade e o controle do que a fábrica entrega",
        tecnicas=["Planejamento mestre e programação da produção (MPS/MRP)", "Análise de capacidade e sequenciamento",
                  "Controle de ordens, apontamentos e aderência ao programa", "Gestão de prazos com projetos e comercial",
                  "Indicadores de produção (OEE, OTD, lead time)", "Planejamento de projetos (cronograma, curva S)"],
        ferramentas=["SAP (PP/PS)", "GPlanSiS|PriorIA / MS Project", "Excel / Power BI", "GPlanSiS|PCP"],
        formacao=["Graduação em Engenharia de Produção, Administração ou Logística"],
        certificacoes=["APICS CPIM — desejável", "PMI-SP/CAPM — desejável em planejamento de projetos"],
        kpis=["Aderência ao programa", "OTD", "Lead time de fabricação", "Acuracidade do plano de capacidade"],
        nucleo=["Planejar e programar a produção e os projetos conforme capacidade e prazos contratados",
                "Controlar ordens, apontamentos e desvios e replanejar",
                "Integrar comercial, suprimentos, engenharia e fábrica em torno de um plano único",
                "Publicar indicadores e cenários para decisão"]),
    "producao": dict(
        nome="Produção e Montagem",
        dominio="a montagem e a fabricação com qualidade, segurança e produtividade",
        tecnicas=["Montagem eletromecânica de painéis e máquinas", "Leitura e interpretação de projetos elétricos e mecânicos",
                  "Ferramentas, medição e testes de continuidade/isolação", "Qualidade na fonte e autoinspeção",
                  "Segurança do trabalho (NR-10, NR-12, EPI)", "Organização (5S) e melhoria contínua",
                  "Operação de máquinas e equipamentos de produção"],
        ferramentas=["Ferramentas manuais e elétricas", "Multímetro / megômetro", "Instruções de trabalho e checklists", "Apontamento no ERP"],
        formacao=["Ensino médio completo; curso técnico em Eletrotécnica/Eletromecânica — desejável"],
        certificacoes=["NR-10 (obrigatória)", "NR-12 e NR-35 quando aplicável", "Ponte rolante/empilhadeira quando aplicável"],
        kpis=["Produtividade (horas padrão vs. realizadas)", "Retrabalho", "Acidentes zero", "5S"],
        nucleo=["Executar a montagem e a fabricação conforme projeto, instruções e padrões de qualidade",
                "Realizar autoinspeção, testes e registrar apontamentos",
                "Cumprir as normas de segurança e usar os EPI corretamente",
                "Manter o posto organizado (5S) e propor melhorias"]),
    "qualidade": dict(
        nome="Qualidade, SSMA e Documentação Técnica",
        dominio="a conformidade dos produtos, dos processos e dos documentos, e a segurança das pessoas",
        tecnicas=["Sistema de gestão da qualidade (ISO 9001) e auditorias", "Inspeção, ensaios e controle de não conformidades (8D, CAPA)",
                  "Segurança e saúde ocupacional (NRs, PGR, CIPA)", "Controle de documentos e registros técnicos (GED, revisões)",
                  "Ferramentas da qualidade e análise de causa", "Metrologia e calibração"],
        ferramentas=["Sistemas de gestão da qualidade (GED)", "Excel / Power BI", "Instrumentos de medição", "Microsoft 365"],
        formacao=["Técnico em Qualidade/Segurança do Trabalho ou graduação em Engenharia"],
        certificacoes=["Auditor interno ISO 9001", "Técnico em Segurança do Trabalho (registro MTE) para SSMA", "Green Belt — desejável"],
        kpis=["Não conformidades por projeto", "Taxa de frequência de acidentes", "Documentos fora de revisão", "Resultado de auditorias"],
        nucleo=["Manter o sistema de gestão da qualidade e conduzir auditorias internas",
                "Inspecionar produtos e processos e tratar não conformidades até a causa-raiz",
                "Controlar documentos técnicos, revisões e registros com rastreabilidade",
                "Garantir o cumprimento das normas de SSMA e a cultura de segurança"]),
    "administrativo": dict(
        nome="Administrativo e Apoio Executivo",
        dominio="o suporte administrativo que faz a operação e a liderança funcionarem",
        tecnicas=["Rotinas administrativas, controles e organização de informações", "Agenda, viagens e apoio executivo",
                  "Comunicação escrita e atendimento", "Planilhas, relatórios e sistemas corporativos",
                  "Gestão de contratos e fornecedores administrativos", "Confidencialidade e LGPD"],
        ferramentas=["Microsoft 365 (Excel, Outlook, Teams)", "SAP (básico)", "GPlanSiS|Peoples"],
        formacao=["Ensino médio completo; graduação em Administração ou Secretariado — desejável"],
        certificacoes=["Excel intermediário/avançado", "Inglês para funções executivas"],
        kpis=["Prazos de rotina cumpridos", "Qualidade dos controles", "Satisfação dos clientes internos"],
        nucleo=["Executar rotinas administrativas com organização, prazo e precisão",
                "Apoiar líderes e equipes em agenda, viagens, documentos e comunicação",
                "Manter controles, planilhas e registros atualizados",
                "Atender clientes internos e externos com cordialidade e confidencialidade"]),
    "servicos": dict(
        nome="Serviços de Campo e Suporte",
        dominio="o atendimento, a assistência técnica e o suporte à produção e aos clientes",
        tecnicas=["Assistência técnica e atendimento em campo", "Diagnóstico de falhas em automação e elétrica",
                  "Gestão de chamados, SLA e contratos de serviço", "Relacionamento com o cliente e registro técnico",
                  "Segurança em campo (NR-10, NR-35)", "Suporte à produção: ferramentas, dispositivos e testes"],
        ferramentas=["Sistema de chamados", "Instrumentos de medição", "Microsoft 365", "SAP (SM)"],
        formacao=["Técnico em Automação/Eletrotécnica ou graduação em Engenharia"],
        certificacoes=["NR-10, NR-35", "CNH B (viagens)"],
        kpis=["SLA de atendimento", "Primeira visita resolutiva", "Satisfação do cliente", "Faturamento de serviços"],
        nucleo=["Atender chamados e prestar assistência técnica em campo e remota",
                "Diagnosticar e resolver falhas, registrando causa e solução",
                "Gerir contratos de serviço, SLA e agenda de atendimentos",
                "Dar suporte à produção em ferramentas, dispositivos e testes"]),
}

# Regras (regex sobre o cargo sem acento) — a PRIMEIRA que casar decide.
REGRAS: list[tuple[str, str]] = [
    (r"\b(ceo|diretor executivo|diretora?-presidente|presidente)\b", "exec"),
    (r"\b(cfo|financ|controladoria|tesouraria|fiscal)\w*", "financeiro"),
    (r"\b(clo|juridic)\w*", "juridico"),
    (r"\b(cto|diretor tecnico|diretora? de tecnologia)\b", "cto"),
    (r"\b(rh|recursos humanos|talentos|desenvolvimento organizacional|adm\.? pessoal|pessoal)\b", "rh"),
    (r"\b(manutencao)\b", "manutencao"),
    (r"\b(qualidade|seguranca do trabalho|documentacao tecnica|inspetor)\b", "qualidade"),
    (r"\b(marketing|comunicacao|designer)\b", "marketing"),
    (r"\b(comercial|vendas|pre-vendas|inside sales|sdr|contas|consultor tecnico)\b", "comercial"),
    (r"\b(suprimentos|compras|comprador|compradora|almoxarif\w*|logistica|diligenciador)\b", "suprimentos"),
    (r"\b(pcp|pcs|planejamento)\b", "pcp"),
    (r"\b(operacoes|projetos|servicos?)\b(?!.*(paineis|eletric))", "operacoes"),
    (r"\b(automacao|instrumentacao|acionamentos|controle e automacao|solucoes)\b", "automacao"),
    (r"\b(eletric\w*|paineis|instalacoes)\b", "eletrica"),
    (r"\b(mecanic\w*)\b", "mecanica"),
    (r"\b(processos)\b", "processos"),
    (r"\b(civil)\b", "civil"),
    (r"\b(industrias digitais|\bti\b|tecnologia da informacao|yot|plataform|product owner|tech lead|desenvolvedor|software|dados|ia|analytics)\b", "digital"),
    (r"\b(producao|montagem|montador|operador|turno|linha)\b", "producao"),
    (r"\b(administrativ\w*|assistant|assistente|aprendiz|estagiari\w*)\b", "administrativo"),
]
# Ajustes finos que a regra geral erraria.
EXCECOES = {
    "gerente de servicos": "servicos", "analista de servicos": "servicos",
    "analista de servicos pleno": "servicos", "assistente de servicos": "servicos",
    "analista de suporte de producao": "servicos", "supervisor de solucoes": "automacao",
    "diretor de operacoes": "operacoes", "gerente de operacoes": "operacoes",
    "coordenador de manutencao eletrica": "manutencao", "gerente de manutencao": "manutencao",
    "gerente comercial / consultor tecnico": "comercial", "analista de processos": "processos",
    "coordenadora de analytics": "digital", "analista de dados": "digital",
    "gerente de dados e ia": "digital", "diretor de tecnologia": "cto",
    "coordenador de turno": "producao", "operador lider": "producao",
    "tecnica em automacao": "automacao", "tecnico em automacao": "automacao",
}


def familia_de(cargo: str) -> str:
    c = sem_acento(cargo)
    if c in EXCECOES:
        return EXCECOES[c]
    for padrao, fam in REGRAS:
        if re.search(padrao, c):
            return fam
    return "administrativo"


# =============================================================================
# SENIORIDADE E PAPEL
# =============================================================================
def senioridade_de(cargo: str, papel: str) -> str:
    c = sem_acento(cargo)
    if papel == "diretoria":
        return "diretoria"
    if papel == "gerencia":
        return "gerencia"
    if papel in ("coordenacao", "lideranca"):
        return papel
    if re.search(r"\b(estagiari\w*|aprendiz)\b", c):
        return "aprendiz"
    if re.search(r"\b(auxiliar|assistente)\b", c) and "executive" not in c:
        return "apoio"
    if re.search(r"\b(senior|sênior)\b", c) or papel == "especialista" or "especialista" in c:
        return "senior" if "especialista" not in c and papel != "especialista" else "especialista"
    if re.search(r"\bpleno\b", c):
        return "pleno"
    return "junior"


NIVEL_BASE = {"aprendiz": 1, "apoio": 2, "junior": 2, "pleno": 3, "senior": 4, "especialista": 5,
              "lideranca": 4, "coordenacao": 4, "gerencia": 4, "diretoria": 5}
ROTULO_SENIORIDADE = {"aprendiz": "aprendiz / estágio", "apoio": "apoio operacional", "junior": "júnior",
                      "pleno": "pleno", "senior": "sênior", "especialista": "especialista",
                      "lideranca": "liderança técnica", "coordenacao": "coordenação",
                      "gerencia": "gerência", "diretoria": "diretoria"}
EXPERIENCIA = {"aprendiz": "Sem experiência prévia exigida; cursando formação na área",
               "apoio": "Até 2 anos de experiência em rotinas da área",
               "junior": "1 a 3 anos de experiência na área",
               "pleno": "3 a 6 anos de experiência na área, com autonomia em entregas completas",
               "senior": "6 anos ou mais na área, com histórico de referência técnica e mentoria",
               "especialista": "8 anos ou mais, reconhecido como referência técnica interna e externa",
               "lideranca": "5 anos ou mais na área, com experiência liderando entregas técnicas de equipe",
               "coordenacao": "5 anos ou mais na área, sendo 2 ou mais liderando pessoas",
               "gerencia": "8 anos ou mais na área, sendo 4 ou mais em gestão de equipes e resultados",
               "diretoria": "12 anos ou mais, com 6 ou mais em posições de gestão executiva"}
IDIOMA = {"aprendiz": "Inglês básico (leitura técnica) — desejável",
          "apoio": "Inglês básico — desejável", "junior": "Inglês técnico (leitura de manuais e documentação)",
          "pleno": "Inglês intermediário (leitura técnica e comunicação escrita)",
          "senior": "Inglês intermediário-avançado (reuniões técnicas com fornecedores e clientes)",
          "especialista": "Inglês avançado; espanhol — desejável",
          "lideranca": "Inglês intermediário-avançado", "coordenacao": "Inglês intermediário",
          "gerencia": "Inglês avançado (negociação e apresentações)",
          "diretoria": "Inglês fluente; espanhol — desejável"}

COMPORTAMENTAIS = {
    "base": ["Ownership: assume compromissos e responde pelo resultado do que entrega",
             "TeamWork: colabora, compartilha conhecimento e pede ajuda no tempo certo",
             "Comunicação clara e registro do que faz (rastreabilidade)",
             "Foco em segurança e qualidade na fonte",
             "Aprendizagem contínua (aprendabilidade) e abertura a feedback"],
    "pleno": ["Autonomia: planeja e conclui entregas completas sem supervisão próxima",
              "Resolução de problemas com método (causa-raiz antes da solução)",
              "Orientação ao cliente interno e externo"],
    "senior": ["Referência técnica: revisa o trabalho dos outros e eleva o padrão",
               "Mentoria de juniores e plenos", "Visão sistêmica: antecipa impactos entre disciplinas e áreas",
               "Influência sem autoridade formal"],
    "lideranca": ["Liderança técnica: define padrões, revisa e responde pela qualidade da entrega do time",
                  "Decisão técnica sob incerteza e prazo", "Desenvolvimento de pessoas pelo exemplo e pela revisão"],
    "gestao": ["Liderar (inspirar e dar exemplo), Gerenciar (expectativas claras) e Responsabilizar-se (LMA)",
               "Feedback contínuo e Conversa de Valor com cada liderado", "Gestão de conflitos e de prioridades concorrentes",
               "Desenvolvimento de sucessores e delegação com acompanhamento", "Orientação a resultados com integridade"],
    "diretoria": ["Pensamento estratégico e visão de longo prazo", "Tomada de decisão com dados e coragem",
                  "Patrocínio da cultura e dos valores TRIO", "Comunicação executiva e influência institucional"],
}

GESTAO_RESP = {
    "lideranca": ["Liderar tecnicamente a equipe: definir padrões, revisar entregas e responder pela qualidade técnica",
                  "Distribuir tarefas técnicas e apoiar a resolução dos problemas mais complexos",
                  "Desenvolver a equipe por mentoria, revisão e treinamento no posto"],
    "coordenacao": ["Coordenar a equipe no dia a dia: prioridades, alocação, prazos e qualidade das entregas",
                    "Realizar Conversas de Valor, feedback e acompanhamento de PDI dos liderados",
                    "Garantir o cumprimento de procedimentos, segurança e indicadores da área",
                    "Reportar desvios, riscos e necessidades ao gestor e propor soluções"],
    "gerencia": ["Responder pelos resultados, pelo orçamento e pelos indicadores da área",
                 "Estruturar processos, capacidade e padrões da área e integrá-la às demais",
                 "Desenvolver líderes e sucessores; conduzir ciclo de performance e decisões sobre pessoas",
                 "Representar a área junto a clientes, fornecedores e à diretoria",
                 "Gerir riscos, conformidade e melhoria contínua da área"],
    "diretoria": ["Definir a estratégia, as metas e o orçamento da diretoria alinhados ao plano da organização",
                  "Responder ao CEO e ao conselho pelos resultados e riscos sob sua responsabilidade",
                  "Desenvolver gerentes e sucessores e sustentar a cultura na diretoria",
                  "Decidir investimentos, estrutura e prioridades da área"],
}


def proximo_passo(fam: str, sen: str, papel: str) -> str:
    f = FAMILIAS[fam]["nome"]
    trilha = {"aprendiz": f"efetivação como profissional júnior em {f}",
              "apoio": f"analista/técnico júnior em {f}",
              "junior": f"nível pleno em {f} (autonomia em entregas completas)",
              "pleno": f"nível sênior em {f} (referência técnica) ou liderança técnica",
              "senior": f"especialista em {f} (trilha técnica) ou coordenação (trilha de gestão)",
              "especialista": "arquiteto/consultor principal, referência externa e mentoria da casa",
              "lideranca": f"coordenação de {f} ou especialista",
              "coordenacao": f"gerência de {f}",
              "gerencia": "gerência sênior ou diretoria",
              "diretoria": "CEO / conselho"}
    return trilha.get(sen, "")


def nivel(base: int, indice: int) -> int:
    """As competências centrais pedem o nível pleno da senioridade; as
    periféricas, um degrau abaixo. Nunca abaixo de 1 nem acima de 5."""
    n = base if indice < 4 else base - 1
    return max(1, min(5, n))


def ficha_de(cargo: str, tipo: str) -> dict:
    papel = dcrmod.papel(tipo, cargo)
    fam = familia_de(cargo)
    sen = senioridade_de(cargo, papel)
    F = FAMILIAS[fam]
    base = NIVEL_BASE[sen]
    gestao = papel in ("diretoria", "gerencia", "coordenacao", "lideranca")

    # --- missão ---
    if papel == "diretoria":
        missao = (f"Liderar {F['dominio']} no âmbito da {F['nome']}, definindo estratégia, metas e "
                  f"prioridades, respondendo pelos resultados e desenvolvendo a liderança da área. "
                  f"Sustentar a cultura e os valores da casa nas decisões e no exemplo.")
    elif papel == "gerencia":
        missao = (f"Gerir {F['dominio']}, garantindo resultados, processos e pessoas na {F['nome']}: "
                  f"planejar, organizar e desenvolver a equipe para entregar os indicadores da área "
                  f"({', '.join(F['kpis'][:3])}) com segurança, qualidade e integridade.")
    elif papel == "coordenacao":
        missao = (f"Coordenar a equipe e as entregas de {F['nome']}, assegurando {F['dominio']} no dia a dia — "
                  f"prioridades, prazos, qualidade e desenvolvimento das pessoas — e antecipando riscos ao gestor.")
    elif papel == "lideranca":
        missao = (f"Ser a referência técnica de {F['nome']}, respondendo pela qualidade e pelos padrões das "
                  f"entregas da equipe e desenvolvendo as pessoas pela revisão e pela mentoria, sem perder "
                  f"o foco em {F['dominio']}.")
    elif sen == "especialista":
        missao = (f"Ser a referência técnica da casa em {F['nome']}: resolver os problemas mais complexos, "
                  f"definir padrões, orientar as equipes e antecipar tecnologias que sustentem {F['dominio']}.")
    elif sen in ("aprendiz", "apoio"):
        missao = (f"Apoiar as rotinas e as entregas de {F['nome']}, aprendendo o método da casa e executando "
                  f"atividades definidas com qualidade, segurança e registro, sob orientação da equipe.")
    else:
        grau = {"junior": "sob orientação", "pleno": "com autonomia", "senior": "com autonomia e referência para a equipe"}[sen]
        missao = (f"Executar {grau} as entregas de {F['nome']} que sustentam {F['dominio']}, com qualidade, "
                  f"prazo, segurança e registro, contribuindo para os indicadores da área "
                  f"({', '.join(F['kpis'][:2])}).")

    # --- responsabilidades ---
    resp: list[str] = []
    if gestao:
        resp += GESTAO_RESP[papel]
    nucleo = F["nucleo"] if not gestao else F["nucleo"][:4]
    if sen in ("aprendiz", "apoio"):
        nucleo = [f"Apoiar em: {n[0].lower() + n[1:]}" for n in F["nucleo"][:4]]
    resp += nucleo
    if sen == "especialista":
        resp += ["Definir e revisar os padrões técnicos da disciplina e disseminá-los",
                 "Atuar como consultor interno nos projetos de maior complexidade e risco"]
    if sen == "senior":
        resp += ["Revisar entregas de colegas e orientar juniores e plenos"]
    resp += ["Cumprir as normas de segurança, qualidade e LGPD aplicáveis à função",
             "Registrar o trabalho nos sistemas da casa (rastreabilidade e indicadores)"]

    # --- requisitos ---
    req = [f"[Formação] {x}" for x in F["formacao"]]
    if sen == "aprendiz":
        req = ["[Formação] Cursando ensino técnico ou superior relacionado à área"]
    req.append(f"[Experiência] {EXPERIENCIA[sen]}")
    req += [f"[Certificação] {x}" for x in F["certificacoes"]]
    if gestao and papel != "lideranca":
        req.append("[Certificação] Formação em liderança (LMA — Lead, Manage, take Accountability) — programa interno")
    req.append(f"[Idioma] {IDIOMA[sen]}")
    if fam in ("automacao", "eletrica", "servicos", "operacoes", "comercial", "manutencao", "civil"):
        req.append("[Disponibilidade] Viagens e atividades em campo/cliente, conforme demanda dos projetos")
    if fam in ("automacao", "eletrica", "producao", "manutencao", "servicos"):
        req.append("[Disponibilidade] Aptidão para trabalho em ambiente industrial (NR-10/NR-12) e uso de EPI")

    # --- competências ---
    comp: list[str] = []
    for i, tecnica in enumerate(F["tecnicas"]):
        n = nivel(base, i)
        comp.append(f"[Técnica] {tecnica} — nível {n}/5 ({ESCALA[n]})")
    comp += [f"[Comportamental] {x}" for x in COMPORTAMENTAIS["base"]]
    if sen in ("pleno", "senior", "especialista", "lideranca", "coordenacao", "gerencia", "diretoria"):
        comp += [f"[Comportamental] {x}" for x in COMPORTAMENTAIS["pleno"]]
    if sen in ("senior", "especialista"):
        comp += [f"[Comportamental] {x}" for x in COMPORTAMENTAIS["senior"]]
    if papel == "lideranca":
        comp += [f"[Comportamental] {x}" for x in COMPORTAMENTAIS["lideranca"]]
    if papel in ("coordenacao", "gerencia", "diretoria"):
        comp += [f"[Comportamental] {x}" for x in COMPORTAMENTAIS["gestao"]]
    if papel == "diretoria":
        comp += [f"[Comportamental] {x}" for x in COMPORTAMENTAIS["diretoria"]]
    comp += [f"[Ferramenta] {x}" for x in F["ferramentas"]]
    comp += [f"[KPI] {x}" for x in F["kpis"]]
    comp.append(f"[Trilha] Próximo passo: {proximo_passo(fam, sen, papel)}")
    comp.append(f"[Trilha] Família {F['nome']} · senioridade {ROTULO_SENIORIDADE[sen]} · papel {dcrmod.ROTULO_PAPEL.get(papel, papel)}")

    return {"cargo": cargo, "missao": missao, "responsabilidades": "\n".join(resp),
            "requisitos": "\n".join(req), "competencias": "\n".join(comp),
            "_familia": fam, "_senioridade": sen, "_papel": papel}


# =============================================================================
# APLICAÇÃO NOS ESTADOS
# =============================================================================
def aplicar(caminho: Path, forcar: bool) -> tuple[int, int]:
    d = json.loads(caminho.read_text(encoding="utf-8"))
    cargos = {}
    for u in d["unidades"].values():
        if u.get("parent_id") and u.get("cargo"):
            cargos.setdefault(dcrmod.chave_funcao(u["cargo"]), (u["cargo"], u["tipo"]))
    cfg = d.setdefault("config", {})
    atual = {dcrmod.chave_funcao(o.get("cargo", "")): o for o in (cfg.get("dcr_cargos") or [])}
    novos = 0
    for chave, (cargo, tipo) in sorted(cargos.items()):
        if chave in atual and not forcar and dcrmod._tem_texto(atual[chave]):
            continue
        f = ficha_de(cargo, tipo)
        atual[chave] = {k: f[k] for k in ("cargo", "missao", "responsabilidades", "requisitos", "competencias")}
        novos += 1
    cfg["dcr_cargos"] = dcrmod.normalizar_overlay(list(atual.values()))
    caminho.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return novos, len(cargos)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--so-mostrar" in sys.argv:
        cargo = sys.argv[sys.argv.index("--so-mostrar") + 1]
        f = ficha_de(cargo, "celula")
        print(f"# {cargo}  [{f['_familia']} · {f['_senioridade']} · {f['_papel']}]\n")
        for k in ("missao", "responsabilidades", "requisitos", "competencias"):
            print(f"## {k}\n{f[k]}\n")
        sys.exit(0)
    forcar = "--forcar" in sys.argv
    dados = RAIZ / "dados"
    for org in organogramas.listar():
        p = organogramas.caminho_estado(org["slug"])
        if not p.exists():
            continue
        novos, total = aplicar(p, forcar)
        print(f"{org['slug']:22s} {total:3d} cargos · {novos:3d} fichas escritas -> {p.name}")
