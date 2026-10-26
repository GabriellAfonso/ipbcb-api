import pytest
from rest_framework.test import APIClient

BIBLE_LIST_URL = "/api/bible/"
BIBLE_DETAIL_URL = "/api/bible/{name}/"


class TestBibleListView:
    """Integration tests — run against real JSON files (ARA, NAA)."""

    def test_returns_200_without_auth(self) -> None:
        resp = APIClient().get(BIBLE_LIST_URL)
        assert resp.status_code == 200

    def test_returns_sorted_versions(self) -> None:
        resp = APIClient().get(BIBLE_LIST_URL)
        versions = resp.data["versions"]
        assert versions == sorted(versions)
        assert len(versions) >= 1

    def test_response_has_versions_key(self) -> None:
        resp = APIClient().get(BIBLE_LIST_URL)
        assert "versions" in resp.data


class TestBibleDetailView:
    """Integration tests — run against real JSON files."""

    def test_returns_200_for_existing_version(self) -> None:
        versions = APIClient().get(BIBLE_LIST_URL).data["versions"]
        resp = APIClient().get(BIBLE_DETAIL_URL.format(name=versions[0]))
        assert resp.status_code == 200

    def test_returns_list_of_books(self) -> None:
        versions = APIClient().get(BIBLE_LIST_URL).data["versions"]
        resp = APIClient().get(BIBLE_DETAIL_URL.format(name=versions[0]))
        assert isinstance(resp.data, list)
        assert len(resp.data) > 0

    def test_book_has_expected_fields(self) -> None:
        versions = APIClient().get(BIBLE_LIST_URL).data["versions"]
        resp = APIClient().get(BIBLE_DETAIL_URL.format(name=versions[0]))
        book = resp.data[0]
        assert "abbrev" in book
        assert "name" in book
        assert "chapters" in book
        assert "headings" in book

    @pytest.mark.parametrize(
        ("version", "title"),
        [("ARA", "A formação do homem"), ("NAA", "A formação do homem")],
    )
    def test_genesis_2_heading_is_served(self, version: str, title: str) -> None:
        resp = APIClient().get(BIBLE_DETAIL_URL.format(name=version))
        genesis_2 = resp.data[0]["headings"][1]
        assert genesis_2[0] == {"verse": 4, "level": 1, "title": title}

    def test_unknown_version_returns_404(self) -> None:
        resp = APIClient().get(BIBLE_DETAIL_URL.format(name="NONEXISTENT"))
        assert resp.status_code == 404
        assert resp.data["error_code"] == "NOT_FOUND"
        assert "not found" in resp.data["detail"].lower()
