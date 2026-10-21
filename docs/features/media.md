# Arquivos de mídia

Entrega das imagens enviadas (fotos de perfil, galeria, fotos de membros, eventos) somente para
quem tem permissão. A única exceção pública é a imagem de evento público.

## O que existe

- Toda URL `/ipbcb/media/...` passa por checagem de login e permissão (em `events/`, o login é
  opcional)
- Regra por pasta:

| Pasta       | Quem lê                                                    |
|-------------|------------------------------------------------------------|
| `profiles/` | membros; o dono sempre lê a própria foto                   |
| `gallery/`  | membros; arquivo de item na lixeira, só quem gerencia galeria |
| `members/`  | Liderança e Admin                                          |
| `events/`   | evento público: qualquer um, mesmo sem login; evento de membros: só membros |

- Bloqueio de caminhos maliciosos (`..`, `%`, `\`)
- Tipo do arquivo fixo por extensão (só imagens)

## Endpoints

```
GET    media/{caminho}
```

## Atenção

- Pasta nova sem regra fica **bloqueada para todos**. Quem criar um lugar novo de upload
  precisa adicionar a regra em `server/features/media/domain/media_rules.py`.
- Ter a URL não basta: a requisição precisa levar o JWT — menos para imagem de evento público.
- Imagem de evento de membros, ou arquivo em `events/` sem evento, responde `404` para quem não
  pode ver, igual a um arquivo que não existe.

Detalhes: [`specs/media/spec.md`](../../specs/media/spec.md)
