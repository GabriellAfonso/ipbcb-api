from dependency_injector import containers, providers

from features.accounts.repositories.user_repository import DjangoUserRepository


class Container(containers.DeclarativeContainer):

    wiring_config = containers.WiringConfiguration(
        packages=["features.accounts"]
    )

    user_repository = providers.Factory(DjangoUserRepository)
