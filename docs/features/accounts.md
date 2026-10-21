# Contas

Quem é o usuário e como ele entra no app: cadastro, login, perfil, troca de senha, exclusão
da conta e celulares registrados para receber notificações.

## O que existe

- Cadastro com usuário e senha (mínimo 6 caracteres, sem regra de complexidade)
- Login com usuário e senha, com bloqueio de 30 min após 5 erros
- Login com Google (cria a conta no primeiro acesso e baixa a foto do Google)
- Renovar e encerrar sessão (JWT: access + refresh)
- Meu perfil: nome, foto, se é membro, cargos, permissões, usuário, se a conta tem senha e
  desde quando está no app
- Trocar o próprio nome; enviar e remover a própria foto
- Trocar a senha (derruba as outras sessões; quem trocou continua logado)
- Excluir a própria conta: no app (com a senha, ou com o Google se a conta não tem senha) e
  pela página web `conta/excluir/` (exigência da Google Play)
- Registrar e remover o celular para notificações push (FCM)
- Acesso de membro (`member_access`, antigo `is_member`): libera rol, aniversários, escala,
  galeria e eventos de membros. Admin e Liderança têm acesso sempre, mesmo sem a marcação
- Pedidos à liderança: "Pedir acesso" e "Solicitar correção" dos dados do rol (1 pedido por
  dia, 1 pendente por tipo); liderança recebe push e responde em "Perfis"
- "Perfis" (contas do app, diferente de "Membros" = rol): aprovar/negar pedidos, revogar
  acesso, bloquear pedidos, vincular a conta a um membro do rol

## Quem acessa

| Quem          | O quê                                                   |
|---------------|---------------------------------------------------------|
| Qualquer um   | cadastro, login, renovar, sair, página de exclusão      |
| Logado        | próprio perfil, foto, senha, exclusão e celulares       |
| Admin, Liderança | "Perfis": pedidos, revogar acesso, bloquear, vincular ao rol |
| Django admin  | cargos, acesso de membro, vínculo com membro            |

## Endpoints

```
POST   api/auth/register/
POST   api/auth/login/
POST   api/auth/google/
POST   api/auth/refresh/
POST   api/auth/logout/
GET    api/me/profile/                    PATCH
POST   api/me/profile/photo/              DELETE
POST   api/me/password/
POST   api/me/delete/
POST   api/me/devices/
POST   api/me/devices/unregister/
POST   api/me/access-requests/
GET    api/admin/profiles/?status=pending|all
GET    api/admin/profiles/{user_id}/      PATCH
POST   api/admin/profiles/{user_id}/revoke-access/
POST   api/admin/profiles/requests/{id}/approve/
POST   api/admin/profiles/requests/{id}/deny/
GET    conta/excluir/                     POST   (página HTML, não é API)
```

## Atenção

- Cargos (Admin, Liderança, Mídia) só mudam pelo **Django admin**. Acesso de membro e vínculo
  conta ↔ membro mudam pelo Django admin ou por "Perfis".
- `GET api/me/profile/` manda `is_member` **e** `member_access` (mesmo valor) por compatibilidade
  com versões antigas do app. Remover `is_member` numa feature futura.
- Nenhum endpoint de pedidos ou "Perfis" lê, mostra ou aceita e-mail (o login Google vincula
  contas pelo e-mail).
- Sair (`logout`) invalida só o refresh; o access continua valendo até expirar (até 60 min).
  Para derrubar todas as sessões de alguém, troque a senha da pessoa.
- O app precisa chamar `devices/unregister/` **antes** do `logout`.
- Trocar a senha mata **na hora** o access usado na chamada: o app precisa guardar o par de
  tokens que vem na resposta.
- Excluir a conta é imediato e sem volta. Some: conta, perfil, foto, celulares e sessões.
  Fica: o cadastro no rol de membros e o que a pessoa publicou (sem autor). Superusuário não
  pode se excluir.
- Botão do Google na página web: o domínio precisa estar em "Authorized JavaScript origins"
  do client `GOOGLE_CLIENT_ID` no Google Cloud Console.

Detalhes: [`specs/accounts/spec.md`](../../specs/accounts/spec.md)
