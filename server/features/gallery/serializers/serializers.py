from rest_framework import serializers

from features.gallery.models.gallery import Photo


class PhotoListSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    album_id = serializers.IntegerField(source="album.id")
    album_name = serializers.CharField(source="album.name")

    class Meta:
        model = Photo
        fields = [
            "id",
            "name",
            "description",
            "album_id",
            "album_name",
            "image_url",
            "date_taken",
            "uploaded_at",
        ]

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None
