"""Push registration token of one app installation (specs/017-sunday-setlist-push).

In ``core`` because two features use it: ``accounts`` registers and removes tokens, ``songs``
sends to them. A token is a credential to a device, so it is never logged, never shown in the
Django admin, and ``__str__`` leaves it out.
"""

from django.conf import settings
from django.db import models

TOKEN_MAX_LENGTH = 512


class DeviceToken(models.Model):
    token = models.CharField(max_length=TOKEN_MAX_LENGTH)
    # One phone, one owner: registering a token another account holds moves it, so pushes for
    # the previous account stop reaching a phone it signed out of.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_tokens"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "device token"
        verbose_name_plural = "device tokens"
        constraints = [models.UniqueConstraint(fields=["token"], name="device_token_unique")]

    def __str__(self) -> str:
        return f"device token of {self.user_id}"
