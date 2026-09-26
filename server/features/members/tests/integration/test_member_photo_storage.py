import re
from pathlib import Path

from features.members.repositories.member_photo_storage import DefaultStorageMemberPhotoStorage
from features.members.tests.images import image_upload


class TestDefaultStorageMemberPhotoStorage:
    def test_saves_under_random_name_without_upload_name(self, media_root: Path) -> None:
        name = DefaultStorageMemberPhotoStorage().save("png", image_upload("PNG", "ana-souza.png"))

        assert re.fullmatch(r"members/[0-9a-f]{32}\.png", name)
        assert (media_root / name).is_file()

    def test_delete_removes_the_file(self, media_root: Path) -> None:
        storage = DefaultStorageMemberPhotoStorage()
        name = storage.save("jpg", image_upload())

        storage.delete(name)

        assert not (media_root / name).exists()

    def test_delete_of_missing_file_does_not_raise(self, media_root: Path) -> None:
        DefaultStorageMemberPhotoStorage().delete("members/gone.jpg")
