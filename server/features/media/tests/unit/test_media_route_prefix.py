from pytest_django.fixtures import SettingsWrapper

from features.media.urls import media_route_prefix


def test_production_strips_the_script_name(settings: SettingsWrapper) -> None:
    settings.FORCE_SCRIPT_NAME = "/ipbcb"
    settings.MEDIA_URL = "/ipbcb/media/"
    assert media_route_prefix() == "media/"


def test_development_keeps_the_whole_media_url(settings: SettingsWrapper) -> None:
    settings.FORCE_SCRIPT_NAME = None
    settings.MEDIA_URL = "/ipbcb/media/"
    assert media_route_prefix() == "ipbcb/media/"
