from rest_framework import serializers

from apps.songs.models.song import Played, Song
from apps.songs.models.chord_chart import ChordChart
from apps.songs.models.lyrics import Lyrics


class SongSerializer(serializers.ModelSerializer):
    class Meta:
        model = Song
        fields = ['id', 'title', 'artist']


class PlayedSerializer(serializers.ModelSerializer):
    song = SongSerializer(read_only=True)
    date = serializers.DateField(format="%d/%m/%Y")

    class Meta:
        model = Played
        fields = ['id', 'song', 'date', 'tone', 'position']


class ChordChartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChordChart
        fields = ["id", "content", "tone", "instrument", "updated_at"]


class LyricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lyrics
        fields = ["id", "content", "updated_at"]