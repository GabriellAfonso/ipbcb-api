from typing import Optional
from uuid import UUID

from django.db import IntegrityError, transaction

from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from core.application.dtos.auth_dtos import RegisterDTO
from core.domain.exceptions import GoogleUserCreationError
from features.accounts.repositories.interfaces import UserRepository


class UserRepositoryImpl(UserRepository):
    """Implementação do UserRepository usando Django ORM."""

    def create(self, data: RegisterDTO) -> User:
        # Together: an account must never exist without the address it can recover through. The
        # post_save signal creates the profile, so it is there to update. On the profile, never
        # User.email: Google sign-in finds accounts by that one (constitution).
        with transaction.atomic():
            user = User.objects.create_user(
                username=data.username,
                password=data.password,
                first_name=data.first_name,
                last_name=data.last_name,
            )
            Profile.objects.filter(user=user).update(recovery_email=data.recovery_email)
        return user

    def create_google_user(
        self, email: str, username: str, first_name: str, last_name: str
    ) -> User:
        """Create a Google user with an unusable password.

        A clash on a unique column (two first logins racing for the same e-mail or
        username) raises ``GoogleUserCreationError``, chained to the ``IntegrityError``.
        Only that error is translated: anything else is a bug and propagates unchanged.

        >>> repo.create_google_user("ana@gmail.com", "ana", "Ana", "Souza").has_usable_password()
        False
        """
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
                user.set_unusable_password()
                user.save(update_fields=["password"])
        except IntegrityError as exc:
            raise GoogleUserCreationError(email) from exc
        return user

    def get_by_id(self, user_id: UUID | str) -> Optional[User]:
        return User.objects.filter(id=user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return User.objects.filter(username=username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return User.objects.filter(email=email).first()

    def recovery_accounts(self, address: str) -> list[User]:
        """Who a recovery request for ``address`` reaches. The password check runs here, not in
        SQL: what makes a hash unusable belongs to Django.

        >>> repo.recovery_accounts("ana@example.com")
        [<User: ana>]
        """
        matches = User.objects.filter(profile__recovery_email=address, is_active=True)
        return [user for user in matches if user.has_usable_password()]

    def get_recovery_account(self, user_id: UUID, address: str) -> Optional[User]:
        """>>> repo.get_recovery_account(user.pk, "ana@example.com")
        <User: ana>
        """
        user = User.objects.filter(
            pk=user_id, profile__recovery_email=address, is_active=True
        ).first()
        return user if user and user.has_usable_password() else None

    def username_exists(self, username: str) -> bool:
        return User.objects.filter(username=username).exists()

    def set_password(self, user: User, raw_password: str) -> None:
        """>>> repo.set_password(user, "nova-senha")"""
        user.set_password(raw_password)
        user.save(update_fields=["password"])

    def delete(self, user: User) -> None:
        """Profile and device tokens cascade; the profile's ``post_delete`` signal removes the
        photo file; authored content keeps its row with the author cleared.

        >>> repo.delete(user)
        """
        user.delete()

    def generate_unique_username(self, base: str) -> str:
        username = base
        counter = 1
        while self.username_exists(username):
            username = f"{base}{counter}"
            counter += 1
        return username
