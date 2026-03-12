from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'apps.accounts'

    def ready(self) -> None:
        import apps.accounts.signals as _

        from config.dependencies import Container
        container = Container()
        container.init_resources()
        container.wire(packages=["apps.accounts"])
