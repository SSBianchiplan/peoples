"""
GPlanSiS|Peoples — o pacote da aplicação.

Um nível só, de propósito. Os vinte e um módulos daqui são pares, não camadas:
`dominio` é o modelo e o motor de layout, `main` é o app, e os outros dezenove
respondem cada um por um assunto do negócio — centros de custo, cargos, carga
da planilha, idiomas, o assistente, o papel. Agrupá-los em subpastas por
"função técnica" criaria uma hierarquia que o sistema não tem e obrigaria a
escolher, para cada módulo novo, uma gaveta que não muda nada.

O que mora fora daqui é **conteúdo**, não código:

    web/        templates, marca e o htmx vendorizado
    docs/       a SPEC e o manual servido em /panorama
    dados/      estado.json — derivado da planilha, fora do versionamento
    planilhas/  Organograma.xlsx — dado pessoal, fora do versionamento
    testes/     a suíte

Dentro do pacote os imports são relativos (`from . import dominio`). Não é
estilo: import absoluto aqui casaria com um módulo de mesmo nome instalado no
ambiente, e `pdf`, `social` e `banco` são nomes que qualquer venv pode ter.
"""
