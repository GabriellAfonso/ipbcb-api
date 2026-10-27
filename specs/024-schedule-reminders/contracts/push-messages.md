# Contract: Rota push messages

Data-only FCM messages, `android.priority = HIGH`, every value a string, no notification block —
same transport as `specs/017-sunday-setlist-push/contracts/push-messages.md`. Times
`America/Sao_Paulo`.

| `type` | Extra keys | Sent when | Recipient |
|--------|-----------|-----------|-----------|
| `schedule_week` | `slots` | Monday from 08:00, once per member per Monday | users linked to a member with ≥ 1 entry Monday–Sunday |
| `schedule_eve` | `slots` (exactly one) | from 19:00 the day before an entry, once per entry | users linked to that entry's member |
| `schedule_published` | `month`, `slots` | once the month's first save + 30 min has passed, same day, once per member per month | users linked to a member with ≥ 1 entry dated today or later in that month |

Recipients must have member access and an active account. Only entries of months whose overwrite
window has closed are ever used.

```json
{ "type": "schedule_week", "slots": "[{\"date\":\"2026-10-27\",\"service\":\"Terça de Oração\",\"time\":\"19:30\"},{\"date\":\"2026-11-01\",\"service\":\"Domingo Liturgia de Adoração\",\"time\":\"19:30\"}]" }
{ "type": "schedule_eve", "slots": "[{\"date\":\"2026-10-29\",\"service\":\"Quinta de Oração\",\"time\":\"19:30\"}]", "gender": "F" }
{ "type": "schedule_published", "month": "2026-11", "slots": "[...]" }
```

- `slots`: JSON-encoded string of an array of `{date: "YYYY-MM-DD", service: <ChurchService.name>,
  time: "HH:MM"}`, ordered by date then time. Non-ASCII characters are sent as is (UTF-8).
- `month`: `YYYY-MM`.
- `gender`: `M` or `F`, the recipient member's own gender, on every type; the key is absent when
  the member has none recorded. Lets the app word "escalado"/"escalada", "o"/"a responsável".
- No member name, no id of any person.

Expected app behaviour (informative, the app owns it): show a local notification from the payload
alone, or drop it when the user switched rota reminders off.
