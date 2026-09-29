from datetime import date

# Base classes and the gallery's exceptions live in their own modules (500-line rule);
# this module stays the one import path for every domain exception (CLAUDE.md §2).
from core.domain.base_exceptions import (
    DomainError as DomainError,
    NotFoundError as NotFoundError,
    ConflictError as ConflictError,
    ValidationError as ValidationError,
    AuthenticationError as AuthenticationError,
    PermissionDeniedError as PermissionDeniedError,
)
from core.domain.gallery_exceptions import (
    AlbumNotFoundError as AlbumNotFoundError,
    PhotoNotFoundError as PhotoNotFoundError,
    AlbumCycleError as AlbumCycleError,
    DuplicateAlbumNameError as DuplicateAlbumNameError,
    OrderMismatchError as OrderMismatchError,
    NoPhotoAcceptedError as NoPhotoAcceptedError,
    ImageProcessingError as ImageProcessingError,
    ImageTooLargeError as ImageTooLargeError,
    TrashEntryNotFoundError as TrashEntryNotFoundError,
    TrashedParentError as TrashedParentError,
    AlbumRestoreNameConflictError as AlbumRestoreNameConflictError,
    PhotoTagReferenceError as PhotoTagReferenceError,
    TagBulkLimitError as TagBulkLimitError,
    TagListOverlapError as TagListOverlapError,
    InvalidClientUploadIdError as InvalidClientUploadIdError,
    ClientUploadNeedsOneFileError as ClientUploadNeedsOneFileError,
    UploadedPhotoTrashedError as UploadedPhotoTrashedError,
    ClientUploadIdTakenError as ClientUploadIdTakenError,
)


class BibleVersionNotFound(NotFoundError):
    """Raised when a requested Bible version does not exist."""

    def __init__(self, version: str) -> None:
        super().__init__(f"Bible version not found: '{version}'")
        self.version = version

    def extra_context(self) -> dict[str, object]:
        return {"version": self.version}


class UsernameAlreadyExistsError(ConflictError):
    def __init__(self, username: str) -> None:
        super().__init__(f"Username already exists: '{username}'")
        self.username = username

    def extra_context(self) -> dict[str, object]:
        return {"username": self.username}


class InvalidCredentialsError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Invalid username or password")


class InvalidRefreshTokenError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Refresh token is invalid, expired or revoked")


class InvalidGoogleTokenError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Invalid Google token")


class UnverifiedGoogleEmailError(ValidationError):
    def __init__(self) -> None:
        super().__init__("Google account has no verified email")


class GoogleUserCreationError(DomainError):
    def __init__(self, email: str) -> None:
        super().__init__("Erro ao criar usuário.")
        self.email = email

    def extra_context(self) -> dict[str, object]:
        return {"email": self.email}


class ProfileNotFoundError(NotFoundError):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"Profile not found for user: '{user_id}'")
        self.user_id = user_id

    def extra_context(self) -> dict[str, object]:
        return {"user_id": self.user_id}


class MemberNotFoundError(NotFoundError):
    """No member with this id. Carries only the id: member data never goes into errors."""

    def __init__(self, member_id: int) -> None:
        super().__init__(f"Membro não encontrado: id={member_id}.")
        self.member_id = member_id

    def extra_context(self) -> dict[str, object]:
        return {"member_id": self.member_id}


class ChordChartNotFoundError(NotFoundError):
    def __init__(self, pk: int) -> None:
        super().__init__(f"Chord chart not found: id={pk}")
        self.pk = pk

    def extra_context(self) -> dict[str, object]:
        return {"pk": self.pk}


class LyricsNotFoundError(NotFoundError):
    def __init__(self, pk: int) -> None:
        super().__init__(f"Lyrics not found: id={pk}")
        self.pk = pk

    def extra_context(self) -> dict[str, object]:
        return {"pk": self.pk}


class SongsNotFoundError(NotFoundError):
    """Raised when one or more songs are not found."""

    def __init__(self, missing_ids: list[int]) -> None:
        super().__init__(f"Some songs were not found: {missing_ids}")
        self.missing_ids = missing_ids

    def extra_context(self) -> dict[str, object]:
        return {"missing_song_ids": self.missing_ids}


class ServiceInUseError(ConflictError):
    """Raised when deleting a church service that rota history still references.

    Rota rows record what actually happened, so the service must be deactivated
    rather than deleted.
    """

    def __init__(self, service_id: int, service_name: str, rota_entries: int) -> None:
        super().__init__(
            f"Service '{service_name}' cannot be deleted: "
            f"{rota_entries} rota entries reference it. Deactivate it instead."
        )
        self.service_id = service_id
        self.service_name = service_name
        self.rota_entries = rota_entries

    def extra_context(self) -> dict[str, object]:
        return {"service_id": self.service_id, "rota_entries": self.rota_entries}


class ServiceWindowNotFoundError(NotFoundError):
    def __init__(self, window_id: int) -> None:
        super().__init__(f"Service window not found: id={window_id}")
        self.window_id = window_id

    def extra_context(self) -> dict[str, object]:
        return {"window_id": self.window_id}


class BatchTooLargeError(ValidationError):
    """Raised when an ingest batch exceeds the configured maximum size."""

    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(f"Batch of {size} events exceeds max_batch_size of {max_size}.")
        self.size = size
        self.max_size = max_size

    def extra_context(self) -> dict[str, object]:
        return {"size": self.size, "max_size": self.max_size}


class ReportRangeError(ValidationError):
    """Raised when a reporting date range is inverted or wider than allowed."""

    def __init__(self, from_date: date, to_date: date, reason: str) -> None:
        super().__init__(f"Invalid report range {from_date} to {to_date}: {reason}")
        self.from_date = from_date
        self.to_date = to_date
        self.reason = reason

    def extra_context(self) -> dict[str, object]:
        return {
            "from": self.from_date.isoformat(),
            "to": self.to_date.isoformat(),
            "reason": self.reason,
        }


class ScheduleOverwriteError(ValidationError):
    """Raised when trying to overwrite a schedule past the allowed window."""

    def __init__(self, month: int, year: int) -> None:
        super().__init__(
            f"A escala de {month:02d}/{year} foi criada há mais de 30 minutos. "
            "Por segurança, não é mais possível sobrescrevê-la."
        )
        self.month = month
        self.year = year


class MediaAccessDeniedError(PermissionDeniedError):
    """Raised when the caller is not in the audience of the requested media folder.

    >>> raise MediaAccessDeniedError("members")
    """

    def __init__(self, folder: str) -> None:
        super().__init__(f"Sem permissão para acessar a pasta de mídia: '{folder}'")
        self.folder = folder


class MediaNotFoundError(NotFoundError):
    """Base of every media 404. All subclasses share one message on purpose: a rejected path,
    an unruled folder and a missing file must produce identical responses, so a caller probing
    paths cannot tell them apart. The subclass exists for the decision log and for tests.

    >>> raise MediaFileNotFoundError("gallery/retiro/IMG_0042.jpg")
    """

    def __init__(self, requested_path: str) -> None:
        super().__init__(f"Arquivo não encontrado: {requested_path!r}")
        self.requested_path = requested_path


class MediaPathRejectedError(MediaNotFoundError):
    """Raised when a requested media path fails validation (traversal, encoding, separators)."""


class MediaFolderNotRuledError(MediaNotFoundError):
    """Raised when the first path segment has no access rule — default deny."""


class MediaFileNotFoundError(MediaNotFoundError):
    """Raised when an allowed path names no regular file inside MEDIA_ROOT."""


class MediaFileTrashedError(MediaFileNotFoundError):
    """A gallery file whose photo or album is in the trash, asked for by a caller without
    ``owner`` on ``gallery``. Same message and status as a missing file, so a member cannot
    tell a deleted photo from one that never existed (specs/014-gallery-trash-sync FR-024).

    >>> raise MediaFileTrashedError("gallery/7/9b1e.jpg")
    """
