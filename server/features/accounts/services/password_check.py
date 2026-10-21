"""The password check the account services receive from the view (specs/021-user-account R-02).

The check itself needs the HTTP request for the django-axes lockout, which services may not
see; the services still decide *when* it runs. The view builds it as
``lambda raw: login_service.verify_password(user, raw, request._request)``.
"""

from collections.abc import Callable

# Raises InvalidPasswordError when the password is not the account's; returns None otherwise.
PasswordCheck = Callable[[str], None]
