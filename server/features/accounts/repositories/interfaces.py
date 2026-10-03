from typing import IO, Optional, Protocol

from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from core.application.dtos.auth_dtos import RegisterDTO
from uuid import UUID


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
