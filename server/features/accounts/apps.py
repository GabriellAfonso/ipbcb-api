from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "features.accounts"

    def ready(self) -> None:
        import features.accounts.signals  # noqa: F401

        from config.di import Container

        container = Container()
        container.init_resources()
        container.wire(packages=["features.accounts"])
