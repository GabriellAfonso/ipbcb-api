from unittest.mock import Mock

from features.gallery.serializers.serializers import PhotoListSerializer


class TestPhotoListSerializer:
    def test_image_url_returns_absolute_uri(self) -> None:
        photo = Mock()
        photo.image = Mock()
        photo.image.url = "/ipbcb/media/gallery/culto/photo.jpg"

        request = Mock()
        request.build_absolute_uri.return_value = (
            "http://testserver/ipbcb/media/gallery/culto/photo.jpg"
        )

        s = PhotoListSerializer(context={"request": request})
        result = s.get_image_url(photo)

        assert result == "http://testserver/ipbcb/media/gallery/culto/photo.jpg"
        request.build_absolute_uri.assert_called_once_with(photo.image.url)

    def test_image_url_returns_none_when_no_image(self) -> None:
        photo = Mock()
        photo.image = None

        s = PhotoListSerializer(context={"request": Mock()})
        assert s.get_image_url(photo) is None

    def test_image_url_returns_none_when_no_request(self) -> None:
        photo = Mock()
        photo.image = Mock()
        photo.image.url = "/media/test.jpg"

        s = PhotoListSerializer(context={})
        assert s.get_image_url(photo) is None

    def test_image_url_falsy_image(self) -> None:
        photo = Mock()
        photo.image = ""

        s = PhotoListSerializer(context={"request": Mock()})
        assert s.get_image_url(photo) is None
