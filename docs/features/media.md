# Arquivos de mídia

Entrega das imagens enviadas (fotos de perfil, galeria, fotos de membros) somente para quem
tem permissão. Nenhum arquivo é público.

## O que existe

- Toda URL `/ipbcb/media/...` passa por checagem de login e permissão
- Regra por pasta:

| Pasta       | Quem lê                                                    |
|-------------|------------------------------------------------------------|
| `profiles/` | membros; o dono sempre lê a própria foto                   |
| `gallery/`  | membros; arquivo de item na lixeira, só quem gerencia galeria |
| `members/`  | Liderança e Admin                                          |

- Bloqueio de caminhos maliciosos (`..`, `%`, `\`)
- Tipo do arquivo fixo por extensão (só imagens)

## Endpoints

```
GET    media/{caminho}
```

## Atenção

- Pasta nova sem regra fica **bloqueada para todos**. Quem criar um lugar novo de upload
  precisa adicionar a regra em `server/features/media/domain/media_rules.py`.
- Ter a URL não basta: a requisição precisa levar o JWT.

Detalhes: [`specs/media/spec.md`](../../specs/media/spec.md)
