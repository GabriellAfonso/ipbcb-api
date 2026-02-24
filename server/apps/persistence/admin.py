from django.contrib import admin
from apps.persistence.models.songs import Category, Song, Played
from apps.persistence.models.profile import Profile
from apps.persistence.models.schedule import ScheduleType, MemberScheduleConfig, MonthlySchedule
from apps.persistence.models.hymnal import Hymn
from apps.persistence.models.member import Member
from apps.persistence.models.gallery import Album, Photo

admin.site.register(Category)
admin.site.register(Song)
admin.site.register(Played)

admin.site.register(Member)
admin.site.register(Profile)
admin.site.register(ScheduleType)
admin.site.register(MemberScheduleConfig)
admin.site.register(MonthlySchedule)

admin.site.register(Hymn)
admin.site.register(Album)
admin.site.register(Photo)
