# Accounts — Implementation Plan

## Approach

Refactor incrementally. Each step leaves codebase working and tests passing. No big bang rewrite.

---

## Phase 1: Repository completeness

Expand `UserRepository` and create `ProfileRepository` so all ORM access has a home.

### UserRepository — add methods:
- `get_by_email(email) -> Optional[User]`
- `username_exists(username) -> bool`
- `create_google_user(email, username, first_name, last_name) -> User` (sets unusable password)
- `generate_unique_username(base) -> str` (collision logic with counter)

### ProfileRepository — new:
- `get_or_create(user) -> tuple[Profile, bool]`
- `save_photo(profile, filename, content) -> None`
- `delete_photo(profile) -> None`
- `update(profile, **fields) -> Profile`

### Interface protocol files:
- Update `repositories/interfaces.py` with both protocols
- Register both in `config/di.py`

---

## Phase 2: Service layer

Create services that own business logic. One service per use case.

### `services/register_service.py`
- `register(dto: RegisterDTO) -> TokenDTO`
- Calls UserRepository.create() + get_tokens_for_user()
- Raises `UsernameAlreadyExistsError` (move uniqueness check from serializer)

### `services/login_service.py`
- `login(dto: LoginDTO) -> TokenDTO`
- Calls django authenticate + get_tokens_for_user()
- Raises `InvalidCredentialsError`

### `services/google_auth_service.py`
- `authenticate_google(id_token: str) -> TokenDTO`
- Verify token, extract user info into `GoogleUserDTO`
- Get or create user via UserRepository
- Download photo via `AvatarDownloader` (thin interface over `requests`, CLAUDE.md §7),
  validate it, store it via ProfileRepository
- Raises: `InvalidGoogleTokenError`, `UnverifiedGoogleEmailError`; `GoogleUserCreationError`
  comes from `UserRepository.create_google_user`, which is where the `IntegrityError` it
  translates is visible — the service no longer catches anything around creation

### `services/profile_service.py`
- `get_profile(user) -> Profile`
- `update_profile(user, data) -> Profile`
- `upload_photo(user, file) -> str` (returns photo_url)
- `delete_photo(user) -> None`
- All through ProfileRepository

### DTOs — add:
- `GoogleUserDTO`: email, first_name, last_name, picture_url, email_verified

### Domain exceptions — add to `core/domain/exceptions.py`:
- `UsernameAlreadyExistsError`
- `InvalidCredentialsError`
- `InvalidGoogleTokenError`
- `UnverifiedGoogleEmailError`
- `GoogleUserCreationError`
- (`ProfileNotFoundError` was added and later removed: profiles are always `get_or_create`d,
  so nothing ever raised it)

---

## Phase 3: Thin views

Refactor views to only: parse request -> call service -> return response.

### `views/auth.py`
- `RegisterAPI.post()`: serializer validates -> DTO -> register_service.register() -> Response
- `LoginAPI.post()`: DTO -> login_service.login() -> Response
- `GoogleLoginAPI.post()`: serializer validates -> google_auth_service.authenticate_google() -> Response

### `views/profile.py`
- All methods delegate to profile_service
- No `Profile.objects` calls

### Exception handling:
- DRF exception handler maps domain exceptions to HTTP responses
- Views don't catch domain exceptions manually

### Serializer cleanup:
- Remove `User.objects.filter()` from `RegisterSerializer.validate_username()`
- Uniqueness check moves to `RegisterService` (raises domain exception)

---

## Phase 4: Cleanup

- Remove dead code (`if data:` branch in repository)
- Add missing tests for new services/repos
- Rename `invalid_credentials_error` -> `invalid_credentials_response` or remove (handled by exception handler)
- Verify signals still work correctly with new repository layer

---

## Implementation Order

| Step | What | Risk |
|------|------|------|
| 1 | Expand UserRepository + create ProfileRepository | Low — additive |
| 2 | Add domain exceptions | Low — additive |
| 3 | Create GoogleUserDTO | Low — additive |
| 4 | Create services (register, login, google_auth, profile) | Medium — new logic layer |
| 5 | Refactor views to use services | Medium — changes existing behavior path |
| 6 | Remove ORM from serializer | Low — move check to service |
| 7 | Wire everything in DI container | Low — config change |
| 8 | Add/update tests | Low |
| 9 | Cleanup dead code | Low |

Each step = one commit. Tests pass after every commit.

---

## Technical Decisions

- **Google token verification stays sync** — `google-auth` lib is sync, no benefit from async here
- **Photo download in service, not signal** — explicit > implicit, easier to test
- **Profile get_or_create stays** — dual creation path (signal + explicit) is safety net for existing users without profile
- **Signals kept for now** — profile auto-creation on user create is convenient; photo cleanup signals are simple enough. Revisit if they cause test complexity.
- **Exception handler approach** — register domain exceptions in DRF's custom exception handler (`core/http/exception_handler.py`) mapping to appropriate HTTP status codes
