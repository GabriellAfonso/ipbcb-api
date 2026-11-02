# Research: Password recovery by e-mail

The input settled the product decisions (`TODO/specify_password_recovery_backend.md`). These are the technical ones.

## R-01: Attempts per address without a counter table

- **Decision**: `EmailCode.failed_attempts` lives on each pending row. A wrong recovery code increments every live row of that address under `select_for_update`; at 5 all of them are deleted.
- **Rationale**: A request replaces the codes of every account of the address, so all live rows of one address are always from one request and carry the same count. That makes the row count equal the address count, and starting over on a new request falls out of it. The confirmation purpose uses the same code, scoped to the account.
- **Alternatives**: A separate per-address counter table has its own lifetime to manage, and resetting it on request duplicates what the rows already give.

## R-02: The failure must commit

- **Decision**: The service decides inside `transaction.atomic()`, returns an outcome, and raises `InvalidEmailCodeError` only after the block has closed.
- **Rationale**: Raising inside the block would roll back the attempt it just counted, leaving guesses unlimited with every test still passing on the happy path.

## R-03: Per-address send limit

- **Decision**: One `EmailSendLedger` row per address, holding the recent send moments in a JSON list. `get_or_create` followed by `select_for_update` serialises concurrent requests. The limit itself is a pure function (`send_wait_seconds`).
- **Rationale**: The limits are rolling, so a window counter is not enough: it allows 9 messages in 9 minutes across a window boundary. Counting rows of a log cannot be locked when no row exists yet, so a burst could pass the check together. DRF throttles are per process (no shared cache in production), so they cannot enforce this.
- **Alternatives**: DRF throttle keyed on the address; rejected for the reason above.

## R-04: Anonymous addresses are not stored readable

- **Decision**: The ledger key is a keyed hash of the address (`salted_hmac`). Every request writes the ledger whether or not the address matches.
- **Rationale**: Anyone can post any address; the table must not become a list of what they typed. Writing in both cases also keeps the two paths doing similar database work. Message delivery, the part that would really differ in time, is out of the request (R-06).

## R-05: Per-client limit keeps the public answer

- **Decision**: `PasswordRecoveryRequestAPI` overrides `check_throttles` to record that the budget is spent instead of raising, and answers the same 200 without calling the service. Scope `recovery_request`, `20/hour`.
- **Rationale**: The input says the public response stays the same when a limit is hit. 20/hour leaves room for the congregation behind one church NAT address, where the per-address limits already protect each mailbox.
- **Alternatives**: A plain 429. It reveals nothing about accounts, but contradicts the input and would make the app show an error for a request that was simply dropped.

## R-06: Sending in a background thread

- **Decision**: `transaction.on_commit` calls `BackgroundEmailSender.send`, which starts a daemon thread running Django's `EmailMessage.send`. The message is fully built before the thread starts, so the thread never touches the database. `EMAIL_TIMEOUT = 10` bounds it.
- **Rationale**: Decided in the input. A daemon thread does not hold a worker's graceful shutdown; a message lost on restart is the accepted cost. Failures log the exception **type** only: `SMTPRecipientsRefused` carries the address in its text and args, so neither the message nor `exc_info` may be logged.

## R-07: Clearing the lockout

- **Decision**: `AxesLockoutResetter.reset(username)` calls `axes.utils.reset(username=normalize_username(username))`, after the transaction.
- **Rationale**: axes stores attempts under the normalised username (`axes_lockout_username`), and legacy usernames may not be normalised. `reset` with only a username deletes the rows of every client address, which is what is wanted: the person may be locked from several. The call is wrapped so services do not import the library (CLAUDE.md section 7).

## R-08: Where the code hash comes from

- **Decision**: `salted_hmac(salt, f"{purpose}:{address}:{code}", algorithm="sha256")`, compared with `constant_time_compare`.
- **Rationale**: Six digits are one million values, so an unkeyed hash falls instantly if the table leaks; the key is `SECRET_KEY`, which lives outside the database. Binding the purpose and address means a code of one purpose cannot be replayed for the other. Rotating `SECRET_KEY` only voids codes that last 15 minutes anyway.

## R-09: E-mail settings do not stop the boot

- **Decision**: `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` are read with an empty default, in `base.py`.
- **Rationale**: A missing key costs the recovery messages, and each failure is logged at error level (and reaches Sentry). Requiring it at import would take the whole API down for a mail setting, the same reasoning as `FCM_SERVICE_ACCOUNT_JSON_BASE64`. The go-live steps name the key explicitly.

## R-10: Recovery e-mail read-only in the Django admin

- **Decision**: `recovery_email` and `recovery_email_confirmed_at` are read-only in `ProfileAdmin`.
- **Rationale**: An edit there would skip normalisation, keep a stale confirmation and leave pending codes alive. The manual route for a signed-out person is `manage.py changepassword`, as decided.

## R-11: Normaliser placement

- **Decision**: `core/application/email_address.py`, beside `username.py`.
- **Rationale**: `RegisterDTO` lives in `core/application/dtos` and normalises in a validator, like the username, and `core` may not import from `features`.
