from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from dependency_injector.wiring import inject, Provide
from pydantic import ValidationError  # noqa

from features.accounts.auth.jwt import get_tokens_for_user
from features.accounts.models.user import User
from features.accounts.serializers.serializers import (
    GoogleLoginSerializer,
    LoginSerializer,
    RegisterSerializer,
    TokenSerializer,
)
from config.di import Container
from features.core.application.dtos.auth_dtos import LoginDTO
from features.accounts.repositories.interfaces import UserRepository

import logging
import requests as http_requests
from django.core.files.base import ContentFile
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings

logger = logging.getLogger(__name__)


class RegisterAPI(APIView):
    serializer_class = RegisterSerializer

    @inject
    def post(
        self, request: Request, user_repo: UserRepository = Provide[Container.user_repository]
    ) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dto = serializer.create_dto()
        user: User = user_repo.create(dto)

        token_dto = get_tokens_for_user(user)

        return Response(token_dto.model_dump(), status=status.HTTP_201_CREATED)


class LoginAPI(APIView):
    @extend_schema(request=LoginSerializer, responses={200: TokenSerializer, 401: None})
    def post(self, request: Request) -> Response:
        invalid_credentials_error = Response(
            {"detail": _("Nome de usuário ou senha inválidos.")},
            status=status.HTTP_401_UNAUTHORIZED,
        )

        try:
            login_dto = LoginDTO(**request.data)
        except ValidationError:
            return invalid_credentials_error

        user = authenticate(username=login_dto.username, password=login_dto.password)

        if user is None:
            return invalid_credentials_error

        token_dto = get_tokens_for_user(user)
        return Response(token_dto.model_dump(), status=status.HTTP_200_OK)


class GoogleLoginAPI(APIView):
    @extend_schema(
        request=GoogleLoginSerializer, responses={200: TokenSerializer, 400: None, 401: None}
    )
    def post(self, request: Request) -> Response:
        token = request.data.get("id_token")
        if not token:
            return Response(
                {"detail": "id_token é obrigatório."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            idinfo = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
        except ValueError:
            return Response(
                {"detail": "Token do Google inválido."}, status=status.HTTP_401_UNAUTHORIZED
            )

        email = idinfo.get("email", "")
        if not email:
            return Response(
                {"detail": "Conta Google sem email verificado."}, status=status.HTTP_400_BAD_REQUEST
            )

        first_name = idinfo.get("given_name", "")
        last_name = idinfo.get("family_name", "")
        photo_url = idinfo.get("picture")

        user = User.objects.filter(email=email).first()
        if not user:
            username = email.split("@")[0]
            base = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
                user.set_unusable_password()
                user.save()
            except Exception:
                return Response(
                    {"detail": "Erro ao criar usuário."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        if photo_url:
            photo_url = photo_url.split("=s")[0] + "=s400-c"
            try:
                profile = getattr(user, "profile", None)
                if profile and not profile.photo:
                    img_response = http_requests.get(photo_url, timeout=5)
                    if img_response.status_code == 200:
                        ext = photo_url.split("?")[0].split(".")[-1] or "jpg"
                        filename = f"google_{user.username}.{ext}"
                        profile.photo.save(filename, ContentFile(img_response.content), save=True)
            except (OSError, ValueError, http_requests.RequestException) as exc:
                logger.warning("Failed to save Google profile photo: %s", exc)

        token_dto = get_tokens_for_user(user)
        return Response(token_dto.model_dump(), status=status.HTTP_200_OK)
