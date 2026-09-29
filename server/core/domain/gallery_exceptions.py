"""Gallery domain exceptions (features 013–016).

Moved out of ``core/domain/exceptions.py`` to keep it under 500 lines; that module
re-exports every name here, so ``from core.domain.exceptions import …`` keeps working
(specs/015-gallery-member-tags research R-10).
"""

from core.domain.base_exceptions import ConflictError, NotFoundError, ValidationError


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


class TrashEntryNotFoundError(NotFoundError):
    """A restore for an item that is not the root of a deletion batch in the trash: live,
    purged, unknown, or trashed only as part of another item's batch.

    English: the app lists restorable entries, so only a client bug reaches it.

    >>> raise TrashEntryNotFoundError("album", 9)
    """

    def __init__(self, kind: str, item_id: int) -> None:
        super().__init__(
            f"No trash entry for {kind} {item_id}; only the item a delete was made on can be "
            "restored, while it is in the trash."
        )
        self.kind = kind
        self.item_id = item_id

    def extra_context(self) -> dict[str, object]:
        return {"kind": self.kind, "id": self.item_id}


class TrashedParentError(ValidationError):
    """Restoring an album whose parent, or a photo whose album, is itself in the trash. The owner
    restores the parent first; nothing is moved automatically (spec 014 FR-022).

    >>> raise TrashedParentError("photo", 301, 7)
    """

    def __init__(self, kind: str, item_id: int, parent_album_id: int) -> None:
        noun = "o álbum" if kind == "album" else "a foto"
        super().__init__(
            f"Não é possível restaurar {noun} {item_id}: o álbum {parent_album_id}, onde "
            f"{'ele' if kind == 'album' else 'ela'} ficava, está na lixeira. "
            f"Restaure o álbum {parent_album_id} primeiro."
        )
        self.kind = kind
        self.item_id = item_id
        self.parent_album_id = parent_album_id

    def extra_context(self) -> dict[str, object]:
        return {"kind": self.kind, "id": self.item_id, "trashed_parent_id": self.parent_album_id}


class AlbumRestoreNameConflictError(ValidationError):
    """Restoring an album while a live sibling holds its name (a trashed album never keeps its
    name). The owner renames the sibling first; no name is invented (spec 014 FR-021).

    >>> raise AlbumRestoreNameConflictError(7, "Culto", 12)
    """

    def __init__(self, album_id: int, name: str, sibling_id: int) -> None:
        super().__init__(
            f"Não é possível restaurar o álbum {album_id} ('{name}'): o álbum {sibling_id} já "
            "usa esse nome no mesmo lugar. Renomeie-o antes."
        )
        self.album_id = album_id
        self.name = name
        self.sibling_id = sibling_id

    def extra_context(self) -> dict[str, object]:
        return {
            "album_id": self.album_id,
            "name": self.name,
            "conflicting_album_id": self.sibling_id,
        }


class PhotoTagReferenceError(NotFoundError):
    """A tag write names photos or members that do not exist. A trashed photo counts as missing,
    as everywhere outside the trash, so a caller with ``manage`` cannot tell what is in the trash
    (specs/015-gallery-member-tags research R-04). Every offending id is listed at once, so the
    app can fix them all.

    >>> raise PhotoTagReferenceError(missing_photo_ids=[301], missing_member_ids=[99])
    """

    def __init__(self, missing_photo_ids: list[int], missing_member_ids: list[int]) -> None:
        self.missing_photo_ids = sorted(missing_photo_ids)
        self.missing_member_ids = sorted(missing_member_ids)
        super().__init__(
            "Não foi possível marcar as pessoas: fotos não encontradas "
            f"{self.missing_photo_ids}, membros não encontrados {self.missing_member_ids}."
        )

    def extra_context(self) -> dict[str, object]:
        return {
            "missing_photo_ids": self.missing_photo_ids,
            "missing_member_ids": self.missing_member_ids,
        }


class TagBulkLimitError(ValidationError):
    """A bulk tag write over more photos than one request may change (spec 015 FR-017).

    >>> raise TagBulkLimitError(201, 200)
    """

    def __init__(self, photo_count: int, limit: int) -> None:
        super().__init__(
            f"Selecione no máximo {limit} fotos por vez; foram enviadas {photo_count}."
        )
        self.photo_count = photo_count
        self.limit = limit

    def extra_context(self) -> dict[str, object]:
        return {"photo_count": self.photo_count, "limit": self.limit}


class TagListOverlapError(ValidationError):
    """The same member asked to be both added and removed in one bulk request. Neither list
    wins; the system never guesses which was meant (spec 015 FR-018).

    >>> raise TagListOverlapError([12])
    """

    def __init__(self, member_ids: list[int]) -> None:
        self.member_ids = sorted(member_ids)
        super().__init__(
            f"Os membros {self.member_ids} estão ao mesmo tempo em 'add_member_ids' e "
            "'remove_member_ids'; envie cada um em uma lista só."
        )

    def extra_context(self) -> dict[str, object]:
        return {"member_ids": self.member_ids}


class InvalidClientUploadIdError(ValidationError):
    """A ``client_upload_id`` that is empty, too long or has a character outside the allowed set.

    English: only a client bug reaches it (specs/016-photo-upload-idempotency R-05). The caller
    passes the value already cut to the length limit, so a huge field is never echoed back.

    >>> raise InvalidClientUploadIdError("id com espaço", "got ' ' at position 2", "1-64 …")
    """

    def __init__(self, client_upload_id: str, problem: str, expected: str) -> None:
        super().__init__(f"Field 'client_upload_id' must be {expected}; {problem}.")
        self.client_upload_id = client_upload_id
        self.expected = expected

    def extra_context(self) -> dict[str, object]:
        return {"client_upload_id": self.client_upload_id, "expected": self.expected}


class ClientUploadNeedsOneFileError(ValidationError):
    """A ``client_upload_id`` sent with more or fewer than one file: one id names one photo
    (specs/016-photo-upload-idempotency FR-003).

    >>> raise ClientUploadNeedsOneFileError(3)
    """

    def __init__(self, file_count: int) -> None:
        super().__init__(
            "Field 'client_upload_id' identifies one photo; send exactly one file in 'image', "
            f"got {file_count}."
        )
        self.file_count = file_count

    def extra_context(self) -> dict[str, object]:
        return {"file_count": self.file_count}


class UploadedPhotoTrashedError(ConflictError):
    """A retried upload whose photo was stored and then sent to the trash. Portuguese: the app
    shows it to the user and drops the queued item. Carries only the id the app sent, never the
    photo's, so a caller with ``manage`` learns nothing else about the trash
    (specs/016-photo-upload-idempotency FR-010).

    >>> raise UploadedPhotoTrashedError("3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90")
    """

    def __init__(self, client_upload_id: str) -> None:
        super().__init__("Esta foto já foi enviada e depois apagada; ela está na lixeira.")
        self.client_upload_id = client_upload_id

    def extra_context(self) -> dict[str, object]:
        return {"client_upload_id": self.client_upload_id}


class ClientUploadIdTakenError(ConflictError):
    """The insert of an uploaded photo hit the ``client_upload_id`` unique constraint: a
    concurrent request with the same id stored its photo first. Raised by the repository so the
    service never sees ``IntegrityError``; the service answers it as a repeat, so it never reaches
    HTTP (specs/016-photo-upload-idempotency R-04).

    >>> raise ClientUploadIdTakenError("3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90")
    """

    def __init__(self, client_upload_id: str) -> None:
        super().__init__(f"A photo already carries client_upload_id {client_upload_id!r}.")
        self.client_upload_id = client_upload_id

    def extra_context(self) -> dict[str, object]:
        return {"client_upload_id": self.client_upload_id}
