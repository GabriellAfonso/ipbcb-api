"""Bible videos domain exceptions (specs/025-bible-videos).

Their own module, like ``event_exceptions``, to keep ``core/domain/exceptions.py`` under 500
lines; that module re-exports every name here. Messages are in Portuguese: the app shows them on
the "add video" and "places" screens.
"""

from collections.abc import Collection, Mapping

from core.domain.base_exceptions import (
    ConflictError,
    NotFoundError,
    UpstreamUnavailableError,
    ValidationError,
)


def place_label(book: str, chapter: int | None) -> str:
    """How a place reads in a message.

    >>> place_label("Gn", None)
    'Gn (livro inteiro)'
    """
    return f"{book} (livro inteiro)" if chapter is None else f"{book} {chapter}"


class BibleVideoInvalidUrlError(ValidationError):
    """The link is not a YouTube video or playlist link the server understands.

    >>> raise BibleVideoInvalidUrlError("https://vimeo.com/1")
    """

    error_code: str = "BIBLE_VIDEO_INVALID_URL"

    def __init__(self, url: str) -> None:
        super().__init__(
            f"Link do YouTube inválido: {url!r}. Use um link de vídeo (youtube.com/watch?v=…, "
            "youtu.be/…, /shorts/, /live/) ou de playlist (youtube.com/playlist?list=…)."
        )
        self.url = url


class BibleVideoUnavailableError(ValidationError):
    """YouTube refused the link: private, removed, not embeddable or nonexistent.

    >>> raise BibleVideoUnavailableError("dQw4w9WgXcQ", 404)
    """

    error_code: str = "BIBLE_VIDEO_UNAVAILABLE"

    def __init__(self, youtube_id: str, status: int) -> None:
        super().__init__(
            "Não foi possível ler esse vídeo. Ele pode ser privado ou ter sido removido."
        )
        self.youtube_id = youtube_id
        self.status = status

    def extra_context(self) -> dict[str, object]:
        return {"youtube_id": self.youtube_id}


class BibleVideoLookupFailedError(UpstreamUnavailableError):
    """YouTube did not answer in time or failed; worth retrying.

    >>> raise BibleVideoLookupFailedError("ReadTimeout")
    """

    error_code: str = "BIBLE_VIDEO_LOOKUP_FAILED"

    def __init__(self, reason: str) -> None:
        super().__init__("Não foi possível consultar o YouTube agora. Tente novamente.")
        self.reason = reason


class BibleVideoExistsError(ConflictError):
    """The same video or playlist is already saved; carries it so the app can open its places.

    >>> raise BibleVideoExistsError({"id": 42, "title": "Gênesis 1"})
    """

    error_code: str = "BIBLE_VIDEO_EXISTS"

    def __init__(self, video: Mapping[str, object]) -> None:
        super().__init__(f"Esse vídeo já está cadastrado (id={video.get('id')}).")
        self.video = dict(video)

    def extra_context(self) -> dict[str, object]:
        return {"video": self.video}


class BiblePlaceInvalidError(ValidationError):
    """A place names an unknown book, a chapter out of range, repeats, or none was given.

    >>> raise BiblePlaceInvalidError("Livro desconhecido: 'Xy'; use a abreviação da Bíblia (ex.: Gn).")
    """

    error_code: str = "BIBLE_PLACE_INVALID"


class BibleVideoOrderMismatchError(ValidationError):
    """The order sent for a place is not exactly the videos of that place, each once.

    >>> raise BibleVideoOrderMismatchError("Gn 1", [3, 7], [7, 7])
    """

    error_code: str = "BIBLE_VIDEO_ORDER_MISMATCH"

    def __init__(self, place: str, expected: Collection[int], received: Collection[int]) -> None:
        super().__init__(
            f"A ordem de {place} deve ter exatamente os vídeos {sorted(expected)}, "
            f"cada um uma vez; recebido {list(received)}."
        )
        self.expected = sorted(expected)

    def extra_context(self) -> dict[str, object]:
        return {"expected_video_ids": self.expected}


class BibleVideoNotFoundError(NotFoundError):
    """No Bible video with this id.

    >>> raise BibleVideoNotFoundError(42)
    """

    error_code: str = "BIBLE_VIDEO_NOT_FOUND"

    def __init__(self, video_id: int) -> None:
        super().__init__(f"Vídeo não encontrado: id={video_id}.")
        self.video_id = video_id


class BiblePlaceNotFoundError(NotFoundError):
    """Removing a place the video is not in.

    >>> raise BiblePlaceNotFoundError(42, "Gn", 3)
    """

    error_code: str = "BIBLE_PLACE_NOT_FOUND"

    def __init__(self, video_id: int, book: str, chapter: int | None) -> None:
        super().__init__(f"O vídeo id={video_id} não está em {place_label(book, chapter)}.")
        self.video_id = video_id
