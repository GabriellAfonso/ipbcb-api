from typing import TYPE_CHECKING

from django.apps import AppConfig

if TYPE_CHECKING:
    # Imported inside ready() at runtime: config.di imports models, which needs the registry.
    from config.di import Container


class AccountsConfig(AppConfig):
    name = "features.accounts"
    # The one wired instance. Kept so tests can override a provider where the views actually
    # resolve it: overriding ``Container.<provider>`` on the class does not reach an instance.
    container: "Container"

    def ready(self) -> None:
        import features.accounts.signals  # noqa: F401

        from config.di import Container

        container = Container()
        self.container = container
        container.init_resources()
        container.wire(
            modules=[
                "features.accounts.views.auth",
                "features.accounts.views.profile",
            ]
        )
