from datetime import datetime
from typing import IO, Optional, Protocol

from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from core.application.dtos.auth_dtos import RegisterDTO
from uuid import UUID

from features.accounts.domain.access_requests import AccessRequestType
from features.accounts.dtos import (
    AccessDecisionDTO,
    AccessGrantDTO,
    AccessRequestCreateDTO,
    AccessRequestRecordDTO,
    AccountAccessFlagsDTO,
    ManagedAccountDTO,
    ManagedAccountPatchDTO,
)


class UserRepository(Protocol):
    """Contrato para operações de usuário que os Use Cases devem depender."""

    def create(self, data: RegisterDTO) -> User:
        """Cria e retorna um usuário a partir de RegisterDTO."""
        ...

    def create_google_user(
        self, email: str, username: str, first_name: str, last_name: str
    ) -> User:
        """Cria usuário Google (senha inutilizável)."""
        ...

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Retorna usuário por id ou None."""
        ...

    def get_by_username(self, username: str) -> Optional[User]:
        """Retorna usuário por username ou None."""
        ...

    def get_by_email(self, email: str) -> Optional[User]:
        """Retorna usuário por email ou None."""
        ...

    def username_exists(self, username: str) -> bool:
        """Verifica se username já existe."""
        ...

    def generate_unique_username(self, base: str) -> str:
        """Gera username único a partir de base, adicionando sufixo numérico se necessário."""
        ...

    def set_password(self, user: User, raw_password: str) -> None:
        """Hash and store a new password. Every token carrying the old hash stops working."""
        ...

    def delete(self, user: User) -> None:
        """Delete the account; the database cascades and SET_NULLs do the rest
        (specs/021-user-account, references table)."""
        ...


class RefreshTokenRepository(Protocol):
    """The record of issued refresh tokens (SimpleJWT ``token_blacklist``)."""

    def revoke_all(self, user_id: UUID) -> int:
        """Blacklist every refresh token of the user not blacklisted yet; return how many."""
        ...


class AvatarDownloader(Protocol):
    """Fetches a remote avatar image, so services never call an HTTP client directly
    (CLAUDE.md §7: third-party libraries sit behind a project-owned interface)."""

    def download(self, url: str) -> bytes | None:
        """Return the image bytes, or None when the remote did not deliver them (network
        error, timeout, non-200). The bytes are untrusted: the caller validates them."""
        ...


class ProfileRepository(Protocol):
    """Contrato para operações de perfil."""

    def get_or_create(self, user: User) -> tuple[Profile, bool]:
        """Retorna (profile, created)."""
        ...

    def save_photo(self, profile: Profile, extension: str, upload: IO[bytes]) -> None:
        """Salva foto no perfil. A extensão vem do formato detectado, não do nome enviado."""
        ...

    def delete_photo(self, profile: Profile) -> None:
        """Remove foto do perfil."""
        ...

    def update(self, profile: Profile, **fields: object) -> Profile:
        """Atualiza campos do perfil."""
        ...


class AccessRequestRepository(Protocol):
    """Persistence of access requests (specs/022-access-requests). The only ORM access to them."""

    def latest_created_at(self, user_id: UUID) -> datetime | None:
        """When the account last made a request of any type and status, or None."""
        ...

    def pending_types(self, user_id: UUID) -> set[AccessRequestType]:
        """Types the account has a pending request of."""
        ...

    def create(self, user_id: UUID, request: AccessRequestCreateDTO) -> AccessRequestRecordDTO:
        """Insert a pending request; ``AccessRequestPendingError`` when one of the same type is
        already pending (the store's unique constraint)."""
        ...

    def get(self, request_id: int) -> AccessRequestRecordDTO | None:
        """One request, or None."""
        ...

    def pending_id(self, user_id: UUID, kind: AccessRequestType) -> int | None:
        """The id of the account's pending request of ``kind``, or None."""
        ...

    def decide(self, request_id: int, decision: AccessDecisionDTO) -> AccessRequestRecordDTO:
        """Move a pending request to ``decision.status``; ``AccessRequestNotPendingError`` when it
        is no longer pending, ``AccessRequestNotFoundError`` when it does not exist."""
        ...

    def list_for_user(self, user_id: UUID) -> list[AccessRequestRecordDTO]:
        """The account's requests, newest first."""
        ...


class ManagedAccountRepository(Protocol):
    """App accounts as "Perfis" reads and changes them. Reaches the roll only by string lookups."""

    def access_flags(self, user_id: UUID) -> AccountAccessFlagsDTO:
        """The profile's stored flags; both False for an account without a profile row."""
        ...

    def list_accounts(self, pending_only: bool) -> list[ManagedAccountDTO]:
        """Active accounts with their pending requests: those with a pending request, oldest
        pending first, or every one by name."""
        ...

    def get_account(self, user_id: UUID) -> ManagedAccountDTO | None:
        """One active account with its pending requests, or None."""
        ...

    def grant_member_access(self, user_id: UUID, grant: AccessGrantDTO) -> None:
        """Set the member-access flag and record who set it and when."""
        ...

    def revoke_member_access(self, user_id: UUID) -> None:
        """Clear the member-access flag and its grant record."""
        ...

    def update(self, user_id: UUID, patch: ManagedAccountPatchDTO) -> None:
        """Apply the fields set in ``patch``; ``RollMemberNotFoundError`` for an unknown member,
        ``RollMemberAlreadyLinkedError`` for one linked to another account."""
        ...
