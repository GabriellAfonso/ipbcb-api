# Bíblia

Texto da Bíblia em várias versões, servido para o app guardar e ler sem internet.

## O que existe

- Lista das versões disponíveis (ex.: ARA, NAA)
- Bíblia completa de uma versão: livros, capítulos e versículos

## Quem acessa

| Quem        | O quê |
|-------------|-------|
| Qualquer um | tudo  |

## Endpoints

```
GET    api/bible/
GET    api/bible/{versão}/
```

## Atenção

- Não tem banco de dados: cada versão é um arquivo `server/features/bible/data/{VERSÃO}.json`.
  Para adicionar uma versão, basta colocar o arquivo e reiniciar o servidor.
- O nome da versão diferencia maiúsculas: `ARA` existe, `ara` dá 404.

Detalhes: [`specs/bible/spec.md`](../../specs/bible/spec.md)
