import pytest
from rest_framework.test import APIClient

from features.songs.models import Hymn


URL = "/api/hymnal/"

# hymnalAPI uses REGEXP_REPLACE (PostgreSQL-only).
# Tests marked skipif SQLite is the backend.
requires_postgres = pytest.mark.skipif(
    "django.db.backends.sqlite3"
    in __import__("django").conf.settings.DATABASES["default"]["ENGINE"],
    reason="REGEXP_REPLACE requires PostgreSQL",
)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@requires_postgres
@pytest.mark.django_db
class TestHymnalAPI:
    def test_returns_hymns(self, client: APIClient) -> None:
        Hymn.objects.create(number="1", title="Hymn One", lyrics={"verses": ["v1"]})
        Hymn.objects.create(number="2", title="Hymn Two", lyrics={"verses": ["v1"]})
        resp = client.get(URL)
        assert resp.status_code == 200
        assert len(resp.data) == 2

    def test_orders_numerically(self, client: APIClient) -> None:
        Hymn.objects.create(number="10", title="Ten", lyrics={})
        Hymn.objects.create(number="2", title="Two", lyrics={})
        Hymn.objects.create(number="110", title="Hundred Ten", lyrics={})
        resp = client.get(URL)
        numbers = [h["number"] for h in resp.data]
        assert numbers == ["2", "10", "110"]

    def test_handles_alphanumeric_suffix(self, client: APIClient) -> None:
        Hymn.objects.create(number="110", title="Base", lyrics={})
        Hymn.objects.create(number="110-A", title="Variant", lyrics={})
        Hymn.objects.create(number="111", title="Next", lyrics={})
        resp = client.get(URL)
        numbers = [h["number"] for h in resp.data]
        assert numbers == ["110", "110-A", "111"]

    def test_etag_304(self, client: APIClient) -> None:
        Hymn.objects.create(number="1", title="One", lyrics={})
        resp1 = client.get(URL)
        etag = resp1["ETag"]
        resp2 = client.get(URL, HTTP_IF_NONE_MATCH=etag)
        assert resp2.status_code == 304
