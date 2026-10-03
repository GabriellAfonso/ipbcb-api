# Escala

Escala mensal: qual membro serve em qual culto e em qual dia. A liderança gera uma
sugestão, ajusta e salva; os membros veem a escala do mês.

## O que existe

- Escala do mês atual, agrupada por culto
- Gerar sugestão de escala para um mês (sorteio com peso, sem salvar nada)
- Fixar um membro num dia/culto antes de gerar
- Salvar a escala, substituindo o mês inteiro
- Quem pode servir em cada culto e com que peso (cadastrado no Django admin)

## Quem acessa

| Quem             | O quê                    |
|------------------|--------------------------|
| Membro           | ver escala do mês atual  |
| Liderança, Admin | gerar e salvar           |

## Endpoints

```
GET    api/schedule/current/
POST   api/schedule/generate/
POST   api/schedule/save/
```

## Atenção

- Depois de **30 min** do primeiro salvamento, o mês trava (409). Dá para corrigir só logo
  depois de publicar.
- Itens mal formados no `save` são ignorados sem erro: a escala pode ficar salva pela
  metade e parecer que deu certo.
- Os cultos ficam em `core.ChurchService`, não aqui. Culto com `takes_rota = false` (ex.:
  Escola Bíblica) não entra na escala.
- Não apague um culto que já tem escala; desative-o.

Detalhes: [`specs/schedule/spec.md`](../../specs/schedule/spec.md)
