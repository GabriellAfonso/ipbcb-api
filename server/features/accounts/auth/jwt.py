from django.contrib.auth.base_user import AbstractBaseUser
from rest_framework_simplejwt.tokens import RefreshToken
from features.core.application.dtos.auth_dtos import TokenDTO


def get_tokens_for_user(user: AbstractBaseUser) -> TokenDTO:
    refresh = RefreshToken.for_user(user)

    return TokenDTO(
        access=str(refresh.access_token),
        refresh=str(refresh),
    )
