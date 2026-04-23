from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'features.accounts'

    def ready(self) -> None:
        import features.accounts.signals as _

        from config.dependencies import Container
        container = Container()
        container.init_resources()
        container.wire(packages=["features.accounts"])
