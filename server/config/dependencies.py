from dependency_injector import containers, providers

from apps.accounts.repositories.user_repository import DjangoUserRepository


class Container(containers.DeclarativeContainer):

    wiring_config = containers.WiringConfiguration(
        packages=["apps.accounts"]
    )

    user_repository = providers.Factory(DjangoUserRepository)
