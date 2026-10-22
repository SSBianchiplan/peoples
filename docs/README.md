# Documentos

Tudo o que é documento vive aqui. Código mora em `orga/`, o que o navegador
recebe mora em `web/`, e dado fica em `dados/` e `planilhas/` — a separação
existe para que uma busca por "onde está a SPEC" não passe por `orga/main.py`,
e para que ninguém mova por engano um arquivo que o código lê por caminho
absoluto.

| Caminho | O que é |
|---|---|
| `panorama.html` | **manual de uso**, com prints das telas e o resultado do último check global. Servido pelo próprio app em `/panorama`, e é o destino do botão *Manual* na barra. **Não acompanha o repositório público** (os prints vêm da base de trabalho); sem ele, a rota responde 404 |
| `DECISOES.md` | o documento técnico original: por que cada parte é como é |
| `cgv-manual.html`, `greyos.html`, `MarIA_Historia.html`, `CGV/Valores_GPlanSiS.html` | páginas servidas pelas rotas `/cgv/interativo`, `/greyos`, `/maria/historia` e `/cgv/trio`. O manual em PDF e os formulários `.xlsx` da Conversa de Valor são documentos internos e não acompanham o repositório público |
| `spec/` | a **SPEC-GPLANSIS-ORG-001 v1.1.0** e a implementação de referência original, de onde este sistema saiu |
| `apresentacao/` | a lâmina **Estrutura GPlanSiS|Peoples 2026**, que a vista *Estrutura* transcreve. Fora do versionamento |

O `README.md` da raiz continua sendo a porta de entrada: ele explica as decisões
de projeto. Este diretório guarda o que se **consulta**; o README é o que se
**lê uma vez**.

## Por que o manual é servido por rota, e não aberto do disco

`docs/panorama.html` é um arquivo comum, e abrir com duplo clique funciona. Mas
o botão da barra aponta para `/panorama`, que o `orga/main.py` serve, por dois
motivos:

- quem usa o sistema de outra máquina não tem o arquivo;
- `ORG_EXIGIR_LOGIN` protege por middleware, então a rota nasce atrás da mesma
  porta que o resto sem ninguém precisar lembrar de pedir. Um arquivo solto no
  disco não tem porta nenhuma.

O manual é **autocontido**: os prints estão embutidos como `data:` URI. Ele abre
sem servidor, sem rede e sem pasta de imagens ao lado.

## Ao atualizar o manual

Os números do panorama (contagens, tempos, estado do ledger) são de uma
verificação datada, e a data está no carimbo do cabeçalho. Ao refazer o check,
troque a data junto com os números — panorama sem data é panorama que envelhece
sem avisar.
