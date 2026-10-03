# Galeria

Fotos da igreja organizadas em álbuns dentro de álbuns. Membros veem; Mídia, Liderança e
Admin montam a galeria pelo app.

## O que existe

- Álbuns em árvore, sem limite de profundidade: criar, renomear, mover, reordenar
- Capa do álbum: automática (primeira foto enviada) ou escolhida; herdada de sub-álbum
- Envio de fotos com miniatura automática e data da foto lida do EXIF
- Envio repetido não duplica a foto (`client_upload_id`)
- Editar foto, mover para outro álbum, reordenar
- Lixeira de 30 dias com restauração; depois disso a foto é apagada de vez
- Marcar membros nas fotos e filtrar fotos por pessoa
- Feed de mudanças, para o app sincronizar só o que mudou
- Página de envio em lote no Django admin

## Quem acessa

| Quem                    | O quê                                        |
|-------------------------|----------------------------------------------|
| Membro                  | ver álbuns, fotos, marcações e o feed        |
| Mídia, Liderança, Admin | tudo: criar, editar, apagar, lixeira, marcar |

## Endpoints

```
GET    api/albums/                         POST
PATCH  api/albums/{id}/                    DELETE
PUT    api/albums/order/
PUT    api/albums/{id}/cover/              DELETE
GET    api/albums/{id}/photos/
PUT    api/albums/{id}/photos/order/
GET    api/photos/?member_id=              POST
PATCH  api/photos/{id}/                    DELETE
PUT    api/photos/{id}/members/
POST   api/photos/members/
GET    api/gallery/trash/
POST   api/gallery/trash/albums/{id}/restore/
POST   api/gallery/trash/photos/{id}/restore/
GET    api/gallery/changes/?since=
GET    api/gallery/taggable-members/
GET    api/gallery/tagged-members/
```

## Atenção

- Apagar só manda para a lixeira. A exclusão de verdade é o `purge_gallery_trash`, que roda
  todo dia pelo cron do servidor, não pelo Docker.
- O Django admin não apaga álbum nem foto, de propósito.
- Restaurar não move nem renomeia nada: se o álbum pai estiver na lixeira, restaure ele
  primeiro.

Detalhes: [`specs/gallery/spec.md`](../../specs/gallery/spec.md)
