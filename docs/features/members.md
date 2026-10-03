# Membros

Cadastro de membros da igreja. Membro comum vê nomes e aniversários; Admin e Liderança
gerenciam o cadastro completo, com histórico de alterações.

## O que existe

- Lista de membros ativos (só nome)
- Aniversariantes por mês ou faixa de meses
- Gestão do cadastro: listar, criar, editar, apagar
- Foto do membro: enviar, trocar, remover (arquivo com acesso protegido)
- Histórico de alterações por campo, com quem editou e quando
- Data de nascimento parcial (dia/mês sem ano, ou só ano)
- Status, cargo e ministérios do membro (cadastrados só no Django admin)
- Opções para o formulário do app: status, cargos, ministérios

## Quem acessa

| Quem      | O quê                                      |
|-----------|--------------------------------------------|
| Membro    | lista + aniversários                       |
| Liderança | gestão completa, menos apagar              |
| Admin     | tudo                                       |
| Mídia     | só nomes, para marcar pessoas nas fotos    |

## Endpoints

```
GET    api/members/
GET    api/members/birthdays/?month=7   ou   ?month=1-6
GET    api/admin/members/                 POST
GET    api/admin/members/{id}/            PATCH   DELETE
PUT    api/admin/members/{id}/photo/      DELETE
GET    api/admin/members/{id}/history/
GET    api/admin/members/options/
```

## Atenção

- O ministério **"Louvor"** é buscado pelo nome na setlist de domingo. Renomear ou apagar
  desliga a setlist.
- Editar membro pelo **Django admin** não grava histórico e pula validações de data.
  O caminho certo é a API.
- `is_active` significa "perfil válido": inativos somem da lista e dos aniversários,
  mas continuam na gestão.

Detalhes: [`specs/members/spec.md`](../../specs/members/spec.md)
