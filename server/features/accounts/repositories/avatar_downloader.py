import logging

import requests

from features.accounts.repositories.interfaces import AvatarDownloader

logger = logging.getLogger(__name__)

# Login waits on this download, so a slow avatar host must not hold the user for long.
_DOWNLOAD_TIMEOUT_SECONDS = 5


class HttpAvatarDownloader(AvatarDownloader):
    """``AvatarDownloader`` over ``requests``. The only place in accounts that imports it."""

    def download(self, url: str) -> bytes | None:
        """Return the body of a 200 answer, or None for anything else.

        >>> HttpAvatarDownloader().download("https://lh3.googleusercontent.com/a/x=s400-c")
        b'\\xff\\xd8...'
        """
        try:
            response = requests.get(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            logger.warning("avatar_download_failed", extra={"reason": type(exc).__name__})
            return None
        if response.status_code != 200:
            logger.warning(
                "avatar_download_failed", extra={"reason": f"status {response.status_code}"}
            )
            return None
        return response.content
