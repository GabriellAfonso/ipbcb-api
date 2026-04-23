from typing import Optional
from uuid import UUID

from features.accounts.models.user import User
from features.core.application.dtos.auth_dtos import RegisterDTO
from features.core.domain.interfaces.repositories.user_repository import UserRepository


class DjangoUserRepository(UserRepository):
    """Implementação do UserRepository usando Django ORM."""

    def create(self, data: RegisterDTO) -> User:
        if data:
            user = User.objects.create_user(
                username=data.username, password=data.password,
                first_name=data.first_name, last_name=data.last_name)
        else:
            user = User.objects.create_user(
                username=data.username, password=data.password)
        return user

    def get_by_id(self, user_id: UUID | str) -> Optional[User]:
        return User.objects.filter(id=user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return User.objects.filter(username=username).first()
