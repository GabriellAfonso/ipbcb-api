# Doutrina

Símbolos de fé de Westminster (Breve Catecismo, Catecismo Maior e Confissão de Fé) como dado
estruturado, para o app mostrar em Estudos → Doutrina e guardar para ler sem internet.

## O que existe

- Lista dos documentos, na ordem Breve, Maior, Confissão, com a quantidade de perguntas ou capítulos
- Documento completo:
  - Catecismos: perguntas e respostas, cada uma com seus textos de prova
  - Confissão: capítulos com título e parágrafos numerados
- Cada texto de prova tem a referência como foi impressa e, quando ela é inequívoca, a forma
  estruturada (livro, capítulo, versículos) para o app abrir a Bíblia

## Quem acessa

| Quem        | O quê |
|-------------|-------|
| Qualquer um | tudo  |

## Endpoints

```
GET    api/doctrine/
GET    api/doctrine/{slug}/
```

## Atenção

- Cada documento é uma linha da tabela `DoctrineStandard`; as perguntas ou capítulos ficam num
  único JSON. Ninguém edita: não há endpoint de escrita e o modelo não aparece no admin.
- A carga vem de uma data migration (`0002_load_westminster_standards`) que lê os arquivos
  congelados em `server/features/doctrine/migrations/data/`. Corrigir um texto ou acrescentar um
  documento é uma **nova** data migration; os arquivos de uma migration aplicada nunca mudam.
- O `migrate` falha (e nada é carregado) se um arquivo estiver inválido (numeração com buraco,
  texto vazio, slug diferente do nome do arquivo). Os testes conferem também as contagens
  107 / 196 / 33 e se cada referência existe em todas as versões da Bíblia.
- `edition` e `year` existem mas estão vazios (`null`): só serão preenchidos com dados do site da
  IPB.
- O livro da referência estruturada usa a abreviação do domínio Bíblia: 1 Timóteo é `1Tn`, mesmo
  quando o texto impresso diz `1Tm`.
- O app revalida com `ETag`: uma correção chega ao celular sem nova versão do app.

Detalhes: [`specs/doctrine/spec.md`](../../specs/doctrine/spec.md)
