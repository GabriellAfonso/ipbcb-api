# Implementation Plan: Login Brute-Force Lockout

**Branch**: `008-login-brute-force-lockout` | **Date**: 2026-08-31 | **Spec**: [spec.md](spec.md)

## Summary

Add `django-axes` to count failed authentication attempts and refuse further attempts once a
`(username, address)` pair passes the limit. Both the Django admin login and `LoginAPI` route
through `django.contrib.auth.authenticate()`, so a single authentication backend covers both.

## Technical Context

**Language/Version**: Python 3.14 (pyenv), `.venv_windows`

**Primary Dependencies**: Django 6.0.3, DRF, dependency-injector, Pydantic. **One new dependency**:
`django-axes[ipware]==8.3.1` — the first release series to declare `Framework :: Django :: 6.0`.
The extra pulls `django-ipware`, and it is load-bearing rather than optional; see D-6.

**Storage**: PostgreSQL. Two new tables from the library's own migrations (`axes_accessattempt`,
`axes_accesslog`). No existing table touched.

**Testing**: pytest + DRF `APIClient` and `django.test.Client` for the admin login, mypy strict,
ruff.

**Target Platform**: Linux server behind nginx (`/ipbcb/`)

**Project Type**: Web service (REST API), single Android client

---

## Technical Decisions

### D-1 — `LoginService.login()` takes the `request`

`axes.backends.AxesStandaloneBackend.authenticate()` raises
`AxesBackendRequestParameterRequired` when it is called with `request=None`. `LoginService.login()`
calls `authenticate(username=..., password=...)` with no request, so **installing the backend
without touching the service turns every API login into a 500** — it is not possible to protect only
the admin and leave the service alone.

The signature becomes `login(dto: LoginDTO, request: HttpRequest) -> TokenDTO` and the view passes
its own request through.

This contradicts `constitution.md` ("Services never import HTTP objects"). It is taken as a
**single, named exception**, recorded in the constitution beside the rule, because:

- The alternative — a project-owned guard behind a Protocol taking a Pydantic `ClientContext` — does
  not actually remove the dependency. `AxesProxyHandler.is_allowed()` wants an `HttpRequest` too, so
  the wrapper would have to synthesise one from the DTO. That is more code standing on a more
  fragile assumption about the library's internals.
- The exception is one parameter on one method, and it is the method whose entire job is to decide
  whether a caller may authenticate.

No other service gains an HTTP parameter. `RegisterService` and `GoogleAuthService` are untouched:
neither calls `authenticate()`.

### D-2 — Attempts stored in Postgres, not in a cache

`AXES_HANDLER` stays at the library default, `axes.handlers.database.AxesDatabaseHandler`.

The counter must be shared by the four gunicorn workers and survive a restart (NFR-001, FR-008).
The only shared store this deployment already has is Postgres. `AxesCacheHandler` would be faster
and would avoid a write per failed attempt, but it needs a shared cache — and there is none:
no `CACHES` is configured, so Django falls back to the per-process `LocMemCache`, which is exactly
the defect NFR-001 exists to avoid. Adding Redis is deliberately out of scope here.

The write volume is a row per failed login on a church app with roughly 200 devices. It is not a
consideration.

### D-3 — Lockout key is the `(username, address)` pair

`AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]` — a nested list means *combination*, not
two independent keys.

The library default is `["ip_address"]`. That default is wrong for this deployment: the congregation
shares one NAT address on the church WiFi, so one member failing five times would lock everyone out
(spec, User Story 2). `["username"]` is equally wrong in the other direction — it lets anyone lock
the administrator out from anywhere (User Story 3). The pair is the compromise, with the residual
risk written down in the spec.

### D-4 — The username is normalised before it becomes a key

`AXES_USERNAME_CALLABLE` points at a project function that applies the same `strip().lower()` the
DTOs already apply.

Without it the two entry points disagree: `LoginDTO` normalises, the admin login form does not. An
attacker cycling `admin`, `Admin`, `ADMIN`, `aDmin` would get a fresh five-attempt budget for each
casing, and the same person's failures in the app and in the admin would land in different buckets.

The normalisation currently lives duplicated in `RegisterDTO` and `LoginDTO`. It is extracted to
`core/application/username.py` and imported by all three callers rather than written a fourth time.
It stays separate from `features/accounts/validators.py`, which owns the *character-set* rule —
`core/` may not import from `features/`.

### D-5 — The lockout response is the project's canonical envelope

`AXES_LOCKOUT_CALLABLE` points at a project function returning the same
`{"error_code", "detail"}` body the rest of the API returns, with `cooloff_seconds` attached.

The library default renders an HTML page (or a JSON body of its own shape only when the request
carries `X-Requested-With: XMLHttpRequest`, which the Android client does not send). The only client
is the Android app and it parses the canonical envelope. The admin gets the same JSON — the admin is
used by two people and a readable 429 is enough.

`_build_canonical` in `core/http/exceptions.py` is renamed to `build_canonical_error` and made part
of that module's public surface, so the lockout response is built by the same function as every
other error instead of a second copy of the shape.

### D-6 — The client address is the rightmost `X-Forwarded-For` entry

```
AXES_IPWARE_PROXY_ORDER = "right-most"
AXES_IPWARE_META_PRECEDENCE_ORDER = ("HTTP_X_FORWARDED_FOR", "REMOTE_ADDR")
```

The library default is `("REMOTE_ADDR",)`, which behind nginx is the proxy's address for every
client on earth — the whole internet would share one lockout bucket, and D-3's pair key would
collapse back into a username-only key. Reading `X-Forwarded-For` naively is the opposite failure:
the client writes its own key and rotates it.

`right-most` resolves both. nginx appends the real peer address to whatever the client sent, so the
rightmost entry is the only one a client cannot write; a spoofed prefix is ignored. It is also
correct if nginx is configured to overwrite the header rather than append, where there is a single
entry. `REMOTE_ADDR` stays as the fallback so dev and the test suite, which send no
`X-Forwarded-For`, still resolve an address.

**`AXES_IPWARE_PROXY_COUNT` is deliberately not set.** It is not the equivalent of DRF's
`NUM_PROXIES`, despite the name: ipware reads it as "the header must contain exactly this many
proxy hops" and returns `None` when it does not. Setting it to `1` returns `None` for the ordinary
production request — a single-entry `X-Forwarded-For` — which would key every locked attempt under
the same empty address. Verified against `axes.helpers.get_client_ip_address` under this project's
settings before the value was chosen; `test_lockout_ip.py` pins the outcome.

The `[ipware]` extra is **required**, not optional. `django-axes` imports `ipware` in a `try`
block and silently falls back to `request.META["REMOTE_ADDR"]` when it is absent — every
`AXES_IPWARE_*` setting above becomes dead configuration with no warning. `requirements.txt`
therefore pins `django-axes[ipware]`.

The extra's own packages are pinned too: `django-ipware==7.0.1` and `python-ipware==3.0.0`. The
extra leaves them unbounded, and `django-ipware` 8.0.0 / `python-ipware` 4.x switch to a "modern"
engine by default that skips a non-public right-most entry and walks left to the first public
address — the part of the header the client wrote. With `X-Forwarded-For: 1.1.1.1, 203.0.113.7`
it returns the spoofed `1.1.1.1`. That broke `test_lockout_ip.py` and the request-log IP test in
CI the day 8.0.0 was released. Upgrading is a separate decision: it means either opting back into
`IPWARE_ALGORITHM = "legacy"` or accepting the weaker guarantee.

### D-8 — Reset-on-success reaches the admin, not the API, and that is left as it is

`AXES_RESET_ON_SUCCESS = True` is honoured through the library's receiver for Django's
`user_logged_in` signal. That signal is sent by `django.contrib.auth.login()`. `LoginAPI` never
calls it — it authenticates and hands back JWTs without creating a session — so a successful API
login leaves the failure count where it was. Found by test, not by reading: the behaviour is two
libraries deep and nothing warns about it.

Left as it is for now. `AXES_COOLOFF_TIME` doubles as the counter's window (the database handler
purges attempts older than it on every failure), so a partial count drains by itself within 30
minutes; the worst case is a member who mistyped four times earlier in the same half hour being
locked by a fifth mistake instead of starting fresh.

Making it work would mean sending `user_logged_in` from the view after a successful login. That is
not free: the same signal drives `django.contrib.auth.models.update_last_login`, so it would start
writing `User.last_login` on every API login — a behaviour change outside this feature — and the
library's receiver reads `request.axes_*` attributes that only exist once its own middleware has
annotated the request. Recorded as `tasks.md` T-906 rather than done quietly here.

### D-7 — Disabled in the test settings, switched on per test

`AXES_ENABLED = False` in `config/settings/test.py`.

The existing suite logs in repeatedly with wrong passwords by design (`test_login_api.py`), and
tests must stay independent (CLAUDE.md §10, F.I.R.S.T). Leaving it on would make one test's
failures lock another test out. `@override_settings(AXES_ENABLED=True)` switches it on for the
tests that exercise the lockout itself. The flag is read at call time by the library's `toggleable`
decorator and by its middleware, so the override works.

---

## Configuration

Settings live in `base.py`, so dev and test inherit the same behaviour and only the on/off flag
differs by environment.

| Setting | Value | Why |
|---|---|---|
| `AXES_FAILURE_LIMIT` | `5` | Library default is `3`. The Nth failure is itself refused, so this is four informative 401s before the fifth attempt is turned away (FR-002). |
| `AXES_COOLOFF_TIME` | `timedelta(minutes=30)` | Library default is `None`, meaning **lockout forever** until an admin clears it. That default would turn a mistyped password into a support call. |
| `AXES_RESET_ON_SUCCESS` | `True` | FR-005 — **admin only**, see D-8. Library default `False` keeps counting across successful logins. |
| `AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT` | `True` (default, left alone) | FR-004. |
| `AXES_LOCKOUT_PARAMETERS` | `[["username", "ip_address"]]` | D-3. |
| `AXES_USERNAME_CALLABLE` | project function | D-4. |
| `AXES_LOCKOUT_CALLABLE` | project function | D-5. |
| `AXES_IPWARE_PROXY_ORDER` / `AXES_IPWARE_META_PRECEDENCE_ORDER` | `right-most` / XFF then `REMOTE_ADDR` | D-6. `AXES_IPWARE_PROXY_COUNT` stays unset on purpose. |
| `AXES_HTTP_RESPONSE_CODE` | `429` (default, left alone) | FR-009. |
| `AXES_ENABLE_ADMIN` | `True` (default, left alone) | FR-010 — attempts are listed and deletable in the Django admin. |

`AUTHENTICATION_BACKENDS` becomes explicit for the first time:

```python
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",   # must be first — it only monitors and blocks
    "django.contrib.auth.backends.ModelBackend",
]
```

`AxesStandaloneBackend` (not `AxesBackend`) is used so `ModelBackend` remains the single place that
actually authenticates and runs permission checks.

`axes.middleware.AxesMiddleware` goes immediately before `PrometheusAfterMiddleware`: it must sit
inside `AuthenticationMiddleware` to see the flag the backend sets on the request, and the
Prometheus pair must stay outermost so the metrics still count the 429s.

---

## Implementation Order

1. Specs — this plan, the feature spec, the constitution exception, the accounts spec. Nothing is
   coded before they are written (CLAUDE.md §6.2).
2. `requirements.txt`, then `pip install`.
3. `core/application/username.py` + point both DTOs at it. Pure move, no behaviour change.
4. `core/http/exceptions.py`: rename `_build_canonical` to `build_canonical_error`.
5. `core/http/lockout.py`: the two axes callables.
6. `config/settings/base.py` and `test.py`.
7. `LoginService` signature and `LoginAPI`; fix the existing login tests for the new parameter.
8. New tests: unit for both callables and the normaliser, integration for the API lockout and the
   admin lockout.
9. `manage.py migrate` — the library's own migrations, nothing hand-written.

## Rollback

Remove the package, the settings block, the middleware entry, `AUTHENTICATION_BACKENDS`, and the
`request` parameter. The two axes tables can be dropped; nothing in this project's schema references
them.
