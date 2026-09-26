# Membros — decisões da conversa (rascunho pré-spec)

Registro das decisões tomadas antes de escrever `spec.md`. Não é spec: serve para conferir
o que foi combinado. Quando a spec existir, este arquivo pode ser apagado.

Objetivo da feature: tela no app Android para a liderança ver e editar os dados dos membros.

---

## 1. Quem é "líder"

- **Decidido:** líder = `Profile.is_admin`, por enquanto.
- **Decidido:** a checagem fica numa permission class própria (ex.: `IsChurchLeader`) que
  hoje delega para `is_admin`. Se a regra mudar, muda num lugar só.
- Líder pode **ver e editar** todos os membros.

---

## 2. Campo `is_active`

- **Decidido:** `is_active` significa **perfil válido**. Mantém o nome; o significado vai
  num comentário no model (sem rename, sem migration).
- **Conferido:** nem backend nem app Android documentavam o significado do campo.
- **Comportamento atual a preservar:** listagem de membros e aniversários só retornam
  registros com esse campo `True` (`member_repository.py:16` e `:29`).

---

## 3. Situação no rol

- **Decidido:** `status` (FK para `MemberStatus`) indica se o membro é comungante ou não.
  Já existe no model, sem uso no código hoje. Nenhum campo novo para isso.

---

## 4. Foto do membro

- **Decidido:** campo `photo` no próprio `Member`, independente de `Profile.photo`.
  Motivo: é dado visível só para a liderança.
- **Decidido:** upload feito pelo líder.
- **Segurança:**
  - Não servir por URL pública do `MEDIA` (hoje `config/urls.py:30` serve media direto).
    Entregar por endpoint autenticado que checa a permissão de líder e responde com
    `X-Accel-Redirect` para o nginx.
  - Path com UUID, sem nome do membro.

---

## 5. Novos campos

- **Decidido:** o único campo novo é `photo` (seção 4).
- Descartados por agora: contato, endereço, datas eclesiásticas, estado civil, `notes`,
  contato de emergência, vínculos familiares.

---

## 6. Histórico de edição

- **Decidido:** tabela própria `MemberChangeLog` (não `django-simple-history`).
- **Colunas:** `editor` (quem editou), `member`, `field`, `old_value`, `new_value`, `changed_at`.
- **Decidido:** guarda valor antigo **e** novo — para ler "fulano mudou campo X de A para B".
- **Gravação:** feita pelo service, na mesma `transaction.atomic` da edição. Não usar
  signals (não sabem quem é o editor e furam a camada de service).
- **Decidido:** ao apagar um membro, **todo** o histórico dele é apagado junto
  (FK `CASCADE`). Sem anonimização: exclusão é rara, não justifica o sistema.
- **Decidido:** troca de foto entra no histórico.
- **Decidido:** leituras (quem visualizou a ficha) **não** são registradas.

- **Decidido:** troca de foto registra só o marcador "foto alterada" (sem path antigo/novo).

- **Decidido:** o arquivo da foto antiga é apagado do storage na troca e na exclusão do
  membro. O arquivo só deve ser apagado depois que a transação de banco confirmar
  (`transaction.on_commit`), para não perder a foto se a gravação falhar.

---

## 7. Segurança (dados sensíveis — LGPD art. 11)

- **Decidido:** reforçar segurança; dado de membresia religiosa é dado pessoal sensível.
- Todos os endpoints de membros exigem `IsAuthenticated` + permissão de líder.
- Serializers com campos explícitos (nada de `fields = "__all__"`).
- Logs JSON (feature 002) nunca levam dado de membro — só `member_id`.
- Atualizar `constitution.md`: a premissa "sem dados sensíveis" não vale mais para este
  domínio. O schema OpenAPI público continua aceito (não expõe dados).

---

## 8. Endpoints

Todos exigem `IsAuthenticated` + líder (`is_admin`). Prefixo `/admin/` porque
`/api/members/` já existe e atende membros comuns (só id e nome).

| Método | Rota | O que faz |
|---|---|---|
| GET | `/api/admin/members/` | lista completa (id, nome, foto, status, `is_active`); sem paginação nem busca — o app baixa tudo e filtra no celular |
| POST | `/api/admin/members/` | cria membro |
| GET | `/api/admin/members/{id}/` | ficha completa |
| PATCH | `/api/admin/members/{id}/` | edita campos; grava histórico |
| DELETE | `/api/admin/members/{id}/` | apaga membro, histórico e foto |
| PUT | `/api/admin/members/{id}/photo/` | envia/troca foto; histórico "foto alterada" |
| DELETE | `/api/admin/members/{id}/photo/` | remove foto; histórico |
| GET | `/api/admin/members/{id}/history/` | histórico de edições |
| GET | `/api/admin/members/options/` | status, cargos e ministérios para os seletores |

- **Decidido:** ministérios (vários por membro) viram uma única linha no histórico,
  ex.: `ministries: "A, B" → "A, C"`.

- **Decidido:** proteção contra exclusão acidental fica **só no app**: diálogo avisando
  que histórico e foto também são apagados, e o líder digita o nome do membro para
  confirmar. Backend não muda (sem lixeira/soft delete).
