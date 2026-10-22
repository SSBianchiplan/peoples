"""
GPlanSiS|Peoples - configuracao do sistema, permissoes e cadastro de centros de custo.

SPEC 12.1 (SEC-01..04) prescreve OIDC + RBAC. Enquanto a autenticacao e debito
declarado (DT-02), o modelo de papeis existe e e aplicado de verdade: o perfil
vigente vive no estado do servidor e toda rota de mutacao passa pela guarda.
Trocar o seletor de perfil por um `sub` de JWT e uma linha em `perfil_vigente`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import cargos
from . import cgv
from . import dcr
from . import dominio
from . import idiomas
from . import gptw
from . import onebyone
from . import provisionamento
from . import talentos


# ---------------------------------------------------------------------------
# PERFIS  (SEC-02)
# ---------------------------------------------------------------------------
VIEWER, EDITOR, ADMIN = "org.viewer", "org.editor", "org.admin"

PERFIS = {
    VIEWER: {"rotulo": "Visualizador", "nivel": 0,
             "descricao": "Lê o organograma, filtra e exporta. Não altera nada."},
    EDITOR: {"rotulo": "Editor", "nivel": 1,
             "descricao": "Altera unidades dentro da subárvore de escopo (SEC-03)."},
    ADMIN: {"rotulo": "Administrador", "nivel": 2,
            "descricao": "Irrestrito, incluindo configuração e carga de dados."},
}

# Tipos de escopo do RBAC por pessoa (Fase D). O escopo diz ONDE o papel vale:
# tudo (sem recorte), só o próprio nó, a subárvore abaixo dele (gestor), ou por
# vertical / departamento. A resolução para um conjunto de ids é feita no `main`,
# que tem a árvore; aqui fica só o vocabulário e a normalização.
ESCOPO_TIPOS = ("tudo", "proprio", "subarvore", "vertical", "departamento")

# Módulos do sistema (as abas do cabeçalho) que a visibilidade por pessoa liga
# ou desliga. As chaves batem com as vistas de `/vistas/{chave}`; os rótulos
# saem do catálogo de idiomas na tela. `[]` na atribuição = vê todos.
MODULOS_CHAVES = ("canvas", "estrutura", "tabela", "tempo", "dcr", "cgv",
                  "talentos", "gptw", "onebyone", "configuracoes")


def normalizar_acessos(acessos: dict | None) -> dict:
    """Sanea a atribuição de acessos: papel válido, tipo de escopo válido, texto
    cortado. Entrada torta não derruba a config — vira o registro possível."""
    saneado: dict = {}
    if not isinstance(acessos, dict):
        return saneado
    for ref, a in acessos.items():
        if not ref or not isinstance(a, dict):
            continue
        papel = a.get("papel") if a.get("papel") in PERFIS else VIEWER
        esc = a.get("escopo") if isinstance(a.get("escopo"), dict) else {}
        tipo = esc.get("tipo") if esc.get("tipo") in ESCOPO_TIPOS else "tudo"
        valor = str(esc.get("valor") or "")[:80]
        # Módulos visíveis: só chaves válidas, na ordem canônica. Lista vazia =
        # vê todos os módulos (o padrão, e o que menos surpreende).
        mods = a.get("modulos") if isinstance(a.get("modulos"), list) else []
        modulos = [m for m in MODULOS_CHAVES if m in set(mods)]
        # `ver_tudo` desacopla a LEITURA da edição: com escopo estreito, a pessoa
        # edita só o seu, mas pode VER o organograma inteiro se esta flag estiver
        # ligada. Padrão desligado — leitura segue o escopo.
        # `ver_1a1_rh`: concessão de RH/compliance para LER os 1:1 de todos (sigilo
        # do One-on-One). Explícita e auditável — não herda de escopo nem de ser o
        # gestor de gestor. Admin/superadmin já vê tudo por outra via.
        saneado[str(ref)] = {"papel": papel,
                             "escopo": {"tipo": tipo, "valor": valor},
                             "modulos": modulos,
                             "ver_tudo": bool(a.get("ver_tudo")),
                             "ver_1a1_rh": bool(a.get("ver_1a1_rh"))}
    return saneado


# ---------------------------------------------------------------------------
# CAMPOS DO CARD  (o que aparece no canvas)
# ---------------------------------------------------------------------------
CAMPOS_CARD = {
    "codigo": ("Código da unidade", True),
    "centro_custo": ("Centro de custo", True),
    "nome": ("Nome / pessoa", True),          # fixo: sem ele o card não existe
    "responsavel": ("Responsável", True),
    "cargo": ("Cargo / função", True),
    "area": ("Departamento", True),
    "email": ("E-mail corporativo", False),
    "vertical": ("Vertical (CC N2)", False),
    "cc_negocio": ("N5 e vertical de negócio", True),
    "accountabilities": ("Accountabilities", True),
    "competencias": ("Competências", True),
}
CAMPOS_FIXOS = {"nome"}
CAMPOS_PADRAO = dominio.CAMPOS_PADRAO

# Campo de card novo, ligado por padrao, nao pode nascer desligado so porque a
# configuracao gravada e anterior a ele: "ausente da lista" e indistinguivel de
# "o operador desligou". A versao resolve — cada degrau liga apenas o que
# aquele degrau introduziu, uma unica vez.
VERSAO_CAMPOS = 2
CAMPOS_POR_VERSAO = {2: {"cc_negocio"}}

# Faixas dos tokens de layout — SPEC 9.6.
LIMITES_TOKENS = {
    "card_w": (140, 320), "gap_h": (16, 48), "gap_v": (56, 160),
    "max_itens": (2, 12), "profundidade_aberta": (0, 9),
}

TEMAS = {
    "claro": "Claro",
    "escuro": "Escuro",
    "auto": "Seguir o sistema",
}

# ---------------------------------------------------------------------------
# CORES DO CANVAS
# ---------------------------------------------------------------------------
# O SVG carrega o proprio <style> (INT-07), entao o tema precisa chegar la
# dentro. Na tela isso vira variavel CSS e a troca e instantanea, sem
# round-trip. No arquivo exportado vira valor literal: papel nao tem tema, e
# variavel CSS em SVG solto nao e universalmente suportada (Inkscape).
#
# Tons escuros derivados de #2D3336 e #000000 — dentro da paleta institucional.
CORES_CANVAS = {
    "claro": {
        "card": "#FFFFFF", "borda": "#D9DBDC",
        "card_raiz": "#2D3336", "borda_raiz": "#2D3336",
        "nome": "#2D3336", "corpo": "#4A5053", "cod": "#4A5053",
        "nome_raiz": "#FFFFFF", "corpo_raiz": "#C9CDCF", "cod_raiz": "#9AA0A3",
        "pes": "#2D3336", "pes_raiz": "#F6A709",
        "regua": "#E7E9EA", "regua_raiz": "#4A5053",
        "fio": "#7D8286", "trilho": "#B9BDBF", "mk": "#7D8286",
        "alca_fundo": "#FFFFFF", "alca_borda": "#7D8286", "alca_texto": "#2D3336",
        "alca_hover": "#FDF0E7", "alca_hover_txt": "#B4460F",
        "titulo": "#2D3336", "sub": "#4A5053", "data": "#7D8286",
        "regua_topo": "#D9DBDC", "hover": "#7D8286",
        # A cota N0 e texto de 9,5px: #EB6A20 sobre o palco claro da 2,71:1.
        "cota_base": "#B4460F", "passagem_op": ".42",
    },
    "escuro": {
        # 3,0:1 contra o palco (#171B1D): no escuro o card so se separa do
        # fundo pela borda, entao ela e objeto grafico, nao enfeite (RNF-07).
        "card": "#262C2F", "borda": "#5F676A",
        # A raiz se distingue pelo preenchimento quase preto, nao pela borda:
        # borda laranja aqui colidiria com a cor de selecao e o clique na raiz
        # nao teria retorno visual.
        "card_raiz": "#0E1112", "borda_raiz": "#5F676A",
        "nome": "#F1F3F3", "corpo": "#B6BCBE", "cod": "#9AA0A3",
        "nome_raiz": "#FFFFFF", "corpo_raiz": "#B6BCBE", "cod_raiz": "#7D8286",
        "pes": "#F1F3F3", "pes_raiz": "#F6A709",
        "regua": "#3D4548", "regua_raiz": "#3D4548",
        "fio": "#7D8286", "trilho": "#5F676A", "mk": "#7D8286",
        "alca_fundo": "#2D3336", "alca_borda": "#7D8286", "alca_texto": "#F1F3F3",
        "alca_hover": "#3A2A20", "alca_hover_txt": "#F0854A",
        "titulo": "#F1F3F3", "sub": "#B6BCBE", "data": "#7D8286",
        "regua_topo": "#3D4548", "hover": "#B6BCBE",
        "cota_base": "#F0854A", "passagem_op": ".55",
    },
}


# A fita do card e a codificacao visual do nivel, e o nivel e configuravel
# (cargos.py). Cada token de cor entra no mapa de tema com o seu par: no escuro
# o grafite da diretoria sumiria dentro do card (1,1:1), entao a ordem inverte
# e o nivel mais senior passa a ser o tom mais claro. Todos >= 3:1 no escuro.
for _token, _par in cargos.CORES_NIVEL.items():
    CORES_CANVAS["claro"][f"cor_{_token}"] = _par["claro"]
    CORES_CANVAS["escuro"][f"cor_{_token}"] = _par["escuro"]


def cores_canvas(exportando: bool) -> dict:
    """Mapa usado pelo template: literais no arquivo, variaveis na tela."""
    if exportando:
        return CORES_CANVAS["claro"]
    return {chave: f"var(--k-{chave})" for chave in CORES_CANVAS["claro"]}


# Os campos EFÊMEROS de sessão: quem é a pessoa e o que ela pode, resolvidos POR
# REQUISIÇÃO a partir do cookie (main.resolver_sessao/acesso_vigente). NUNCA são
# persistidos no estado.json compartilhado nem carregados dele — senão a sessão de
# uma pessoa (ou um "preview" de perfil de dev) viraria estado durável e vazaria
# para todos, podendo trancar a instância. `acessos` NÃO é de sessão: é atribuição
# compartilhada, e persiste.
CAMPOS_SESSAO = ("perfil", "escopo_id", "escopo_tipo", "escopo_valor",
                 "modulos_visiveis", "ver_tudo", "ver_1a1_rh", "usuario_id")


@dataclass
class Config:
    titulo: str = "Organograma"
    tenant: str = "GPlanSiS|Peoples"
    perfil: str = ADMIN
    escopo_id: str | None = None          # SEC-03 (legado): subárvore do editor
    # RBAC por pessoa (Fase D). `acessos` é a atribuição PERSISTIDA que o Admin
    # faz: {id_do_nó: {"papel": "org.editor", "escopo": {"tipo": ..., "valor": ...}}}.
    # `perfil`, `escopo_tipo`, `escopo_valor`, `modulos_visiveis` e `usuario_id`
    # são o que VALE NA SESSÃO — resolvidos POR REQUISIÇÃO a partir do cookie
    # (`acessos[usuario_id]`); são efêmeros (ver CAMPOS_SESSAO). Sem cookie
    # (dev/testes) valem os campos em memória deste Config global. Tipos de escopo:
    # tudo | proprio | subarvore | vertical | departamento.
    escopo_tipo: str = ""
    escopo_valor: str = ""
    # Módulos que a pessoa da sessão vê (resolvido no login a partir de
    # acessos[ref]["modulos"]). `[]` = vê todos. Admin sempre vê todos.
    modulos_visiveis: list = field(default_factory=list)
    # Flag de LEITURA por pessoa: `True` = vê o organograma inteiro mesmo com
    # escopo de edição estreito. Resolvida por requisição, efêmera como o resto.
    ver_tudo: bool = False
    # Concessão de RH/compliance para ler os 1:1 sigilosos do One-on-One (LGPD).
    # Resolvida por requisição a partir de acessos[uid]["ver_1a1_rh"]; efêmera.
    ver_1a1_rh: bool = False
    acessos: dict = field(default_factory=dict)
    campos: list[str] = field(default_factory=lambda: sorted(CAMPOS_PADRAO))
    orientacao_padrao: str = "invertida"
    tema: str = "claro"
    idioma: str = idiomas.PADRAO
    usuario_id: str | None = None   # qual unidade é a pessoa logada
    maria_modelo: str = ""          # sobrepõe MARIA_MODEL; a chave fica no ambiente
    maria_cota_usd: float = 20.0    # cota mensal padrão de IA por pessoa (US$); ver ia_cota
    profundidade_aberta: int = 1
    # O passo a passo de boas-vindas. Ligado por padrão: quem já sabe usar
    # desliga uma vez e nunca mais vê; quem não sabe não descobre um recurso que
    # nasce desligado. O custo do padrão errado é assimétrico.
    helper: bool = True
    # Colunas marcadas na Tabela. Vazio significa "o padrão", e não "nenhuma":
    # com lista vazia querendo dizer nenhuma, um estado gravado antes desta
    # opção abriria a grade sem coluna alguma.
    colunas_tabela: list[str] = field(default_factory=list)
    card_w: int = 236
    gap_h: int = 26
    gap_v: int = 76
    max_itens: int = 6
    # Maior ORG-#### já emitido, inclusive por quem saiu. É a memória que
    # impede o código de um demitido de ser reciclado para quem entrou depois:
    # o código virou chave de pareamento da planilha, e uma planilha guardada
    # do mês passado casaria a linha de um com a ficha do outro. Contar os
    # códigos em uso não serviria — quem saiu não está mais lá para ser contado.
    piso_codigo: int = 0
    versao_campos: int = VERSAO_CAMPOS
    centros_custo: list[dict] = field(default_factory=list)
    niveis: list[dict] = field(default_factory=cargos.niveis_padrao)
    regras_cargo: list[dict] = field(default_factory=cargos.regras_padrao)
    catalogo_cargos: list[dict] = field(default_factory=list)
    # Skills: a camada que o RH escreve sobre cada cargo — missão, responsabilidades,
    # requisitos e competências do GEP-FOR-003. Vive na configuração, e não na
    # unidade, porque descreve o CARGO e não a pessoa: gravá-la em cada unidade
    # faria doze "Analista de Projetos" carregarem doze cópias do mesmo texto,
    # que divergiriam na primeira edição feita pelo card errado.
    dcr_cargos: list[dict] = field(default_factory=list)
    # Conversa de Valor: o acompanhamento das Conversas que Geram Valor — status, data e nota
    # por pessoa, ANO e ciclo. Vive aqui pela mesma razão do Skills (editável, no
    # Desfazer, testável sem banco), mas é a camada VIVA: o histórico durável
    # atravessa anos no Postgres (org.cgv_registro). Sem banco, o histórico é o
    # que este overlay carregar; com banco, o banco preenche os anos anteriores.
    cgv_registros: list[dict] = field(default_factory=list)
    # Avaliação (GEP-FOR-004): a leitura de sucessão que o RH escreve
    # sobre cada pessoa — risco e impacto de perda (o 9-box), prontidão, ação
    # imediata e o texto rico. Vive aqui pela mesma razão da Conversa de Valor: é a camada
    # editável, no Desfazer, testável sem banco; o durável atravessa anos no
    # Postgres (org.mapa_talento). Um registro por (matrícula, ano).
    mapa_talentos: list[dict] = field(default_factory=list)
    # Peoples Place to Work: as respostas ANÔNIMAS da pesquisa de clima. Vivem aqui
    # (dev/testes sem banco) e espelham em org.gptw_resposta. Nenhuma carrega
    # identidade — o vínculo com o sistema é pelos estratos, nunca por quem
    # respondeu. Em produção o store é o Postgres; este overlay é o de trabalho.
    gptw_respostas: list[dict] = field(default_factory=list)
    # A programação da Avaliação Mestre: a janela do ciclo e a intenção de notificar por
    # e-mail. Salva de verdade; o disparo do e-mail é passo à parte, a configurar.
    gptw_programacao: dict = field(default_factory=dict)
    software_por_area: list[dict] = field(
        default_factory=provisionamento.catalogo_padrao)
    # One-on-One: 1:1 (FUP), rocks, issues, objetivos do trimestre, missões, pulso e
    # ciclo de vida — um item por `id`, com sigilo por pessoa (participantes por
    # matrícula). Camada VIVA (editável, no Desfazer, testável sem banco); o durável
    # espelha em org.onebyone_item. LGPD: só participantes e RH leem (ver onebyone).
    onebyone: list[dict] = field(default_factory=list)

    @classmethod
    def de_dict(cls, d: dict | None) -> "Config":
        if not d:
            return cls()
        campos = cls.__dataclass_fields__
        # Campos de sessão são efêmeros: mesmo que um estado.json antigo os traga
        # (bug anterior, quando o login os gravava), NÃO os carregamos — a sessão
        # nasce dos defaults e é resolvida por requisição.
        cfg = cls(**{k: v for k, v in d.items()
                     if k in campos and k not in CAMPOS_SESSAO})
        cfg.versao_campos = int(d.get("versao_campos", 0))
        cfg.migrar_campos()
        cfg.sanear()
        return cfg

    def migrar_campos(self) -> None:
        """Liga campos novos uma unica vez, na carga.

        Fazer isso no `sanear` reverteria o primeiro desmarque do operador: ele
        tira o campo, o saneamento o devolve. Migracao e assunto de carga.
        """
        marcados = set(self.campos)
        for versao, novos in CAMPOS_POR_VERSAO.items():
            if self.versao_campos < versao:
                marcados |= novos
        self.versao_campos = VERSAO_CAMPOS
        self.campos = sorted(marcados)

    def sanear(self) -> None:
        if self.perfil not in PERFIS:
            self.perfil = ADMIN
        if self.escopo_tipo and self.escopo_tipo not in ESCOPO_TIPOS:
            self.escopo_tipo = ""
        self.acessos = normalizar_acessos(self.acessos)
        if self.orientacao_padrao not in ("invertida", "vertical", "lateral"):
            self.orientacao_padrao = "invertida"
        if self.tema not in TEMAS:
            self.tema = "claro"
        self.idioma = idiomas.valido(self.idioma)
        self.campos = sorted(set(self.campos) & set(CAMPOS_CARD) | CAMPOS_FIXOS)
        self.niveis = cargos.normalizar_niveis(self.niveis)
        self.regras_cargo = cargos.normalizar_regras(
            self.regras_cargo, {n["codigo"] for n in self.niveis})
        self.software_por_area = provisionamento.normalizar(
            self.software_por_area)
        self.dcr_cargos = dcr.normalizar_overlay(self.dcr_cargos)
        self.cgv_registros = cgv.normalizar_overlay(self.cgv_registros)
        self.mapa_talentos = talentos.normalizar_overlay(self.mapa_talentos)
        self.gptw_respostas = gptw.normalizar_overlay(self.gptw_respostas)
        self.gptw_programacao = gptw.normalizar_programacao(self.gptw_programacao)
        self.onebyone = onebyone.normalizar_overlay(self.onebyone)
        for nome, (minimo, maximo) in LIMITES_TOKENS.items():
            setattr(self, nome, max(minimo, min(maximo, int(getattr(self, nome)))))

    def para_dict(self) -> dict:
        return asdict(self)

    def para_persistir(self) -> dict:
        """O que vai ao estado.json durável: tudo, MENOS os campos efêmeros de
        sessão (CAMPOS_SESSAO). Assim nenhuma identidade/perfil de sessão — venha
        do login, do seletor de dev ou de onde for — vira estado compartilhado."""
        return {k: v for k, v in self.para_dict().items()
                if k not in CAMPOS_SESSAO}

    # --- niveis -----------------------------------------------------------
    @property
    def rotulos_nivel(self) -> dict[str, str]:
        return {n["codigo"]: n["rotulo"] for n in self.niveis if n.get("ativo", True)}

    @property
    def cores_nivel(self) -> dict[str, str]:
        """codigo do nivel -> token de cor (resolvido por tema no CSS)."""
        return {n["codigo"]: n["cor"] for n in self.niveis}

    @property
    def indice_cargos(self) -> dict[str, str]:
        return cargos.indexar(self.catalogo_cargos)

    # --- permissoes -------------------------------------------------------
    @property
    def nivel(self) -> int:
        return PERFIS[self.perfil]["nivel"]

    def pode(self, exigido: int) -> bool:
        return self.nivel >= exigido

    def dentro_do_escopo(self, uid: str | None, descendentes_do_escopo) -> bool:
        """SEC-03: editor só muta o que descende da sua unidade de escopo."""
        if self.nivel >= PERFIS[ADMIN]["nivel"] or not self.escopo_id or uid is None:
            return True
        return uid == self.escopo_id or uid in descendentes_do_escopo


# O cadastro de centros de custo vive em centros.py: ele tem modelo proprio
# (LogicalCC, N2, N3, Departamento, N5, Vertical, Tipo) e tabela de referencia.
