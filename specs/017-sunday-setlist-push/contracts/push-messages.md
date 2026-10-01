# Contract: Push messages

Data-only FCM messages, `android.priority = HIGH`. Every value is a string (FCM data payload
rule). No notification block: the app decides how to show them.

| `type` | `date` | Sent when | Recipients |
|--------|--------|-----------|------------|
| `setlist_saved` | the setlist's Sunday | after every successful `PUT api/setlists/{date}/` | every registered device of every worship member, author included |
| `confirm_plays` | today (the setlist's Sunday) | once per window 21:00, 21:30 … 23:30 `America/Sao_Paulo`, while no plays are registered for the date | every registered device of users with `manage` on `songs` who are worship members |

```json
{ "type": "setlist_saved", "date": "2026-10-04" }
```

Expected app behaviour (informative, the app owns it):
- `setlist_saved` → `GET api/setlists/current/` (or by date when the user can), show the setlist.
- `confirm_plays` → open the register-played screen for `date`, pre-filled from
  `GET api/setlists/{date}/`.

Delivery is best effort. The app falls back to `GET api/setlists/current/` on start and resume.

Payload carries no song, member or user data.
