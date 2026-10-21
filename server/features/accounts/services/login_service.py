from django.contrib.auth import authenticate
from django.http import HttpRequest

from core.application.dtos.auth_dtos import LoginDTO, TokenDTO
from core.domain.exceptions import InvalidCredentialsError, InvalidPasswordError
from core.metrics import LOGIN_COUNTER
from features.accounts.auth.jwt import get_tokens_for_user
from features.accounts.models.user import User


class LoginService:
    """Every password check in the project, so all of them sit behind django-axes.

    The ``request`` its methods take is the constitution's single named exception to "services
    never import HTTP objects". django-axes counts and blocks failed attempts per client, and
    its backend raises ``AxesBackendRequestParameterRequired`` when ``authenticate()`` is called
    without one — so the parameter is the price of the lockout, not a convenience. See
    specs/008-login-brute-force-lockout/plan.md D-1 and specs/021-user-account research R-01.

    A locked-out caller does not reach an exception of its own: ``authenticate()`` returns None
    like any other failure, and ``AxesMiddleware`` replaces the response with the 429 from
    ``core.http.lockout``.
    """

    def login(self, dto: LoginDTO, request: HttpRequest) -> TokenDTO:
        """Exchange credentials for JWT tokens, or raise ``InvalidCredentialsError``.

        >>> service.login(LoginDTO(username="ana", password="..."), request).access
        'eyJhbGciOi...'
        """
        try:
            user = self.authenticate_credentials(dto, request)
        except InvalidCredentialsError:
            LOGIN_COUNTER.labels(result="failure", login_type="credentials").inc()
            raise
        LOGIN_COUNTER.labels(result="success", login_type="credentials").inc()
        return get_tokens_for_user(user)

    def authenticate_credentials(self, dto: LoginDTO, request: HttpRequest) -> User:
        """Return the account these credentials open, or raise ``InvalidCredentialsError``.
        Also used by the account-deletion web page, where nobody is signed in yet.

        >>> service.authenticate_credentials(LoginDTO(username="ana", password="..."), request)
        <User: ana>
        """
        user = authenticate(request=request, username=dto.username, password=dto.password)
        if not isinstance(user, User):
            raise InvalidCredentialsError()
        return user

    def verify_password(self, user: User, password: str, request: HttpRequest) -> None:
        """Confirm ``password`` is ``user``'s current one, or raise ``InvalidPasswordError``.

        Counted against the same ``(username, address)`` lockout as the login screen, so a
        stolen session cannot be used to guess the password at full speed.

        >>> service.verify_password(user, "secret1", request)
        """
        try:
            confirmed = self.authenticate_credentials(
                LoginDTO(username=user.username, password=password), request
            )
        except InvalidCredentialsError:
            raise InvalidPasswordError() from None
        if confirmed.pk != user.pk:
            raise InvalidPasswordError()
