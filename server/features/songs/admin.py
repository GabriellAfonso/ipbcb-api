from django.contrib import admin

from features.songs.models.chord_chart import ChordChart
from features.songs.models.hymnal import Hymn
from features.songs.models.lyrics import Lyrics
from features.songs.models.song import Category, Played, Song

admin.site.register([Category, Song, Played, Hymn, ChordChart, Lyrics])
