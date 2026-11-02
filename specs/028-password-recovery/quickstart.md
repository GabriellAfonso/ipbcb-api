# Quickstart: Password recovery by e-mail

Contract: [contracts/recovery-api.md](contracts/recovery-api.md).

## Automated

From `server/`, with `.venv_windows`:

```powershell
..\.venv_windows\Scripts\python.exe -m pytest features/accounts
..\.venv_windows\Scripts\python.exe manage.py makemigrations --check --dry-run
```

## Local, end to end

Dev uses the console e-mail backend, so the code is printed by the server.

1. Register with `recovery_email`.
2. `POST api/auth/password-recovery/request/` with the address: 200, and the message with username and code appears in the console.
3. `POST api/auth/password-recovery/confirm/` with the code and a new password: 204.
4. The old password and the old refresh token are refused; the new password signs in.
5. Repeat step 2 at once: same 200, nothing printed (one per minute).

## Before going live (the user)

1. Generate the Brevo SMTP key and put `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` only in the production `.env`.
2. From the production server, confirm the SMTP port is reachable:
   `docker exec ipbcb-server-prod python -c "import socket; socket.create_connection(('smtp-relay.brevo.com', 587), 5); print('ok')"`
3. Send one real message and check it arrives and passes DKIM/DMARC.
4. Release order: submit the app with managed publishing, wait for approval, deploy the backend, publish the app at once. Registration refuses old app versions from the moment the backend is live.
5. Keep the DNS records as "DNS only".
