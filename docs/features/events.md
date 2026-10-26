# Eventos

Eventos da igreja (congressos, acampamentos, cultos especiais) no carrossel de destaques da tela
inicial e numa tela de detalhe. Criados e geridos pelo próprio app, na área de gestão.

## O que existe

- Lista pública dos eventos ativos, do mais próximo para o mais distante (o app mostra os 3
  primeiros); evento sem horário vem antes dos com horário no mesmo dia
- Detalhe de um evento
- Na gestão: listar todos (inclusive passados, filtro `status=active|past|all`), criar, editar,
  excluir
- Cada evento tem título, data de início, data de término opcional (evento de vários dias),
  horário, local e descrição opcionais, imagem 3:2 obrigatória e visibilidade (`public` ou
  `members`)
- Evento fica ativo até o fim do último dia, no horário de São Paulo. Depois some da lista
  pública sozinho, sem tarefa agendada. Continua guardado e visível na gestão

## Quem acessa

| Quem                      | O quê                                                  |
|---------------------------|--------------------------------------------------------|
| Qualquer um, sem login    | eventos públicos ativos e suas imagens                 |
| Membro                    | também os eventos `members`                            |
| Admin, Liderança, Mídia   | gestão completa, inclusive excluir (`owner` em `events`) |

## Endpoints

```
GET    api/events/
GET    api/events/{id}/
GET    api/admin/events/?status=active|past|all
POST   api/admin/events/            (multipart)
GET    api/admin/events/{id}/
PATCH  api/admin/events/{id}/       (multipart, imagem opcional)
DELETE api/admin/events/{id}/
```

## Atenção

- A imagem precisa ser 3:2 (margem de 2%), pelo menos 600×400, até 10 MB, JPEG/PNG/WEBP. O
  servidor converte para JPEG de no máximo 1800×1200 e não guarda o original.
- Imagem de evento público abre **sem login** — é a única pasta de mídia assim. Imagem de evento
  de membros responde `404` para quem não é membro.
- Evento de membros nunca aparece para quem não é membro, nem como aviso: o detalhe responde
  `404`, igual a um id que não existe. Ter papel na gestão não muda isso nos endpoints públicos.
- Token inválido ou vencido nos endpoints públicos dá `401` (o app renova e tenta de novo).
- Para limpar um campo opcional no `PATCH`, mande o campo vazio (`end_date=""`).
- Excluir é definitivo: some o evento e a imagem.

Detalhes: [`specs/events/spec.md`](../../specs/events/spec.md)
