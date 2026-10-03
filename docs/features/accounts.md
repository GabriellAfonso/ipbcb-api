# Contas

Quem é o usuário e como ele entra no app: cadastro, login, perfil e celulares registrados
para receber notificações.

## O que existe

- Cadastro com usuário e senha (mínimo 6 caracteres, sem regra de complexidade)
- Login com usuário e senha, com bloqueio de 30 min após 5 erros
- Login com Google (cria a conta no primeiro acesso e baixa a foto do Google)
- Renovar e encerrar sessão (JWT: access + refresh)
- Meu perfil: nome, foto, se é membro, cargos e permissões
- Trocar o próprio nome; enviar e remover a própria foto
- Registrar e remover o celular para notificações push (FCM)

## Quem acessa

| Quem          | O quê                                  |
|---------------|----------------------------------------|
| Qualquer um   | cadastro, login, renovar, sair         |
| Logado        | próprio perfil, foto e celulares       |
| Django admin  | cargos, "é membro", vínculo com membro |

## Endpoints

```
POST   api/auth/register/
POST   api/auth/login/
POST   api/auth/google/
POST   api/auth/refresh/
POST   api/auth/logout/
GET    api/me/profile/                    PATCH
POST   api/me/profile/photo/              DELETE
POST   api/me/devices/
POST   api/me/devices/unregister/
```

## Atenção

- Cargos (Admin, Liderança, Mídia), "é membro" e o vínculo conta ↔ membro só mudam pelo
  **Django admin**. Nenhum endpoint altera isso.
- Sair (`logout`) invalida só o refresh; o access continua valendo até expirar (até 60 min).
  Para derrubar todas as sessões de alguém, troque a senha da pessoa.
- O app precisa chamar `devices/unregister/` **antes** do `logout`.

Detalhes: [`specs/accounts/spec.md`](../../specs/accounts/spec.md)
