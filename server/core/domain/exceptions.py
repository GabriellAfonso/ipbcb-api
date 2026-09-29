from datetime import date


class DomainError(Exception):
    """Base exception for all domain errors.

    Every subclass inherits ``error_code`` for machine-readable identification
    and can override ``extra_context()`` to attach domain data to error responses.

    >>> raise DomainError("something broke")
    """

    error_code: str = "DOMAIN_ERROR"

    def extra_context(self) -> dict[str, object]:
        """Return additional domain data to include in the error response."""
        return {}


class NotFoundError(DomainError):
    """Raised when a requested entity does not exist."""

    error_code: str = "NOT_FOUND"


class ConflictError(DomainError):
    """Raised when an operation conflicts with existing state."""

    error_code: str = "CONFLICT"


class ValidationError(DomainError):
    """Raised when input validation fails at the domain level."""

    error_code: str = "VALIDATION_ERROR"


class AuthenticationError(DomainError):
    """Raised when authentication fails."""

    error_code: str = "AUTHENTICATION_FAILED"


class PermissionDeniedError(DomainError):
    """Raised when an authenticated caller lacks the permission an operation requires.

    Same ``error_code`` DRF's own ``PermissionDenied`` produces, so clients see one code for
    a denial whether it came from a permission class or from a service.

    >>> raise PermissionDeniedError("Leaders only: 'members'")
    """

    error_code: str = "PERMISSION_DENIED"


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


class AlbumNotFoundError(NotFoundError):
    """No gallery album with this id, in the route or referenced from a body.

    >>> raise AlbumNotFoundError(7)
    """

    def __init__(self, album_id: int) -> None:
        super().__init__(f"Album not found: id={album_id}")
        self.album_id = album_id

    def extra_context(self) -> dict[str, object]:
        return {"album_id": self.album_id}


class PhotoNotFoundError(NotFoundError):
    """No gallery photo with this id.

    >>> raise PhotoNotFoundError(12)
    """

    def __init__(self, photo_id: int) -> None:
        super().__init__(f"Photo not found: id={photo_id}")
        self.photo_id = photo_id

    def extra_context(self) -> dict[str, object]:
        return {"photo_id": self.photo_id}


class AlbumCycleError(ValidationError):
    """Moving an album under itself or one of its descendants.

    ``chain`` runs from the requested parent up to the album being moved. Portuguese because a
    normal move in the app reaches it (specs/013-gallery-write-api FR-006).

    >>> raise AlbumCycleError(3, 9, [9, 5, 3])
    """

    def __init__(self, album_id: int, parent_id: int, chain: list[int]) -> None:
        super().__init__(
            f"Não é possível mover o álbum {album_id} para dentro do álbum {parent_id}: "
            f"{parent_id} está dentro de {album_id}."
        )
        self.album_id = album_id
        self.parent_id = parent_id
        self.chain = chain

    def extra_context(self) -> dict[str, object]:
        return {"album_id": self.album_id, "parent_id": self.parent_id, "chain": self.chain}


class DuplicateAlbumNameError(ValidationError):
    """An album with this name already exists under the same parent (roots included).

    `400`, not `409`: the spec treats it as invalid input (specs/013-gallery-write-api FR-005).

    >>> raise DuplicateAlbumNameError("Retiros", None)
    """

    def __init__(self, name: str, parent_id: int | None) -> None:
        super().__init__(f"Já existe um álbum chamado '{name}' neste local.")
        self.name = name
        self.parent_id = parent_id

    def extra_context(self) -> dict[str, object]:
        return {"name": self.name, "parent_id": self.parent_id}


class OrderMismatchError(ValidationError):
    """A full-order request does not list every current sibling exactly once.

    English: only a client bug reaches it, never a normal action in the app.

    >>> raise OrderMismatchError(missing=[4], unexpected=[8], repeated=[])
    """

    def __init__(self, missing: list[int], unexpected: list[int], repeated: list[int]) -> None:
        super().__init__(
            "Order must list every sibling exactly once: "
            f"missing {missing}, unexpected {unexpected}, repeated {repeated}."
        )
        self.missing = missing
        self.unexpected = unexpected
        self.repeated = repeated

    def extra_context(self) -> dict[str, object]:
        return {"missing": self.missing, "unexpected": self.unexpected, "repeated": self.repeated}


class NoPhotoAcceptedError(ValidationError):
    """Every file of an upload was rejected. The canonical 400 carries the per-file reasons in
    ``rejected`` (specs/013-gallery-write-api, clarification Q1).

    >>> raise NoPhotoAcceptedError([{"filename": "a.txt", "reason": "Formato inválido"}])
    """

    def __init__(self, rejected: list[dict[str, str]]) -> None:
        super().__init__("Nenhuma imagem foi aceita.")
        self.rejected = rejected

    def extra_context(self) -> dict[str, object]:
        return {"rejected": self.rejected}


class ImageProcessingError(ValidationError):
    """A file that passed format validation could not be turned into a thumbnail or cover.

    >>> raise ImageProcessingError("IMG_0042.jpg")
    """

    def __init__(self, filename: str) -> None:
        super().__init__(f"Não foi possível processar a imagem '{filename}'. Envie outro arquivo.")
        self.filename = filename


class ImageTooLargeError(ValidationError):
    """An image over the pixel limit, refused before it is decoded for a derivative.

    A 10 MB file can still decode to hundreds of MB of pixels (clarification Q3).

    >>> raise ImageTooLargeError(9000, 8000, 50_000_000)
    """

    def __init__(self, width: int, height: int, max_pixels: int) -> None:
        super().__init__(
            f"Imagem grande demais: {width}x{height} pixels. "
            f"O máximo é {max_pixels // 1_000_000} megapixels."
        )
        self.width = width
        self.height = height
        self.max_pixels = max_pixels
