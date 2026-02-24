from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from dependency_injector.wiring import inject, Provide
from pydantic import ValidationError  # noqa
from apps.api.auth.jwt import get_tokens_for_user
from apps.persistence.models.profile import User
from core.application.dtos.auth_dtos import LoginDTO
from apps.api.serializers.register_serializer import RegisterSerializer
from config.dependencies import Container
from core.domain.interfaces.repositories.user_repository import UserRepository


class RegisterAPI(APIView):

    @inject
    def post(self, request: Request,
             user_repo: UserRepository = Provide[Container.user_repository]) -> Response:

        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dto = serializer.create_dto()
        user: User = user_repo.create(dto)

        token_dto = get_tokens_for_user(user)

        return Response(token_dto.model_dump(), status=status.HTTP_201_CREATED)


class LoginAPI(APIView):

    @staticmethod
    def post(request: Request) -> Response:
        try:
            login_dto = LoginDTO(**request.data)
        except ValidationError as e:
            return Response(
                {"detail": e.errors()},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=login_dto.username,
                            password=login_dto.password)

        if user is None:
            return Response(
                {"detail": _("Nome de usuário ou senha inválidos.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token_dto = get_tokens_for_user(user)

        return Response(token_dto.model_dump(), status=status.HTTP_200_OK)
