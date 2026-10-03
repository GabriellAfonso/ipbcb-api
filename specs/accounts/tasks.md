# Accounts — Tasks

## Phase 1: Repository completeness

- [x] Add `get_by_email()`, `username_exists()`, `create_google_user()`, `generate_unique_username()` to UserRepository interface + implementation
- [x] Create `ProfileRepository` interface (protocol) + `ProfileRepositoryImpl` implementation
- [x] Register `ProfileRepository` in `config/di.py`
- [x] Tests for new repository methods

## Phase 2: Service layer

- [x] Add domain exceptions: `UsernameAlreadyExistsError`, `InvalidCredentialsError`, `InvalidGoogleTokenError`, `UnverifiedGoogleEmailError`, `GoogleUserCreationError`, `ProfileNotFoundError`
- [x] Create `GoogleUserDTO` (Pydantic)
- [x] Create `RegisterService` — register(dto) -> TokenDTO
- [x] Create `LoginService` — login(dto) -> TokenDTO
- [x] Create `GoogleAuthService` — authenticate_google(id_token) -> TokenDTO
- [x] Create `ProfileService` — get, update, upload_photo, delete_photo
- [x] Register all services in `config/di.py`
- [x] Tests for all services

## Phase 3: Thin views

- [x] Refactor `RegisterAPI` to use `RegisterService`
- [x] Refactor `LoginAPI` to use `LoginService`
- [x] Refactor `GoogleLoginAPI` to use `GoogleAuthService`
- [x] Refactor `ProfilePhotoAPIView` to use `ProfileService`
- [x] Refactor `MeProfileAPIView` to use `ProfileService`
- [x] Uniqueness check kept in serializer (400 UX) + service as safety net (409)
- [x] Map domain exceptions to HTTP responses in DRF exception handler
- [x] Update/add integration tests for refactored views

## Phase 4: Cleanup

- [x] Remove dead `if data:` branch in `UserRepositoryImpl.create()`
- [x] Remove direct ORM imports from views
- [x] Remove unused `ProfilePhotoSerializer`
- [x] Fix type hints in `GoogleAuthService` (`object` -> `User`)
- [x] Verify signals still work with new layer (97 tests pass)
- [x] Review naming — `invalid_credentials_error` variable removed in view refactor

## Phase 5: Leftover deviations

- [x] `MeProfileAPIView.patch` writes through `ProfileService.update_profile()`, not
      `ProfileSerializer.save()`
- [x] Google avatar download behind `AvatarDownloader` / `HttpAvatarDownloader`
- [x] `except Exception` on Google user creation replaced by the repository translating
      `IntegrityError` into `GoogleUserCreationError` (chained)
- [x] `ProfileNotFoundError` removed: nothing raised it
