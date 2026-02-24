from django.contrib import admin
from apps.persistence.models.songs import Category, Song, Played
from apps.persistence.models.profile import Profile
from apps.persistence.models.schedule import ScheduleType, MemberScheduleConfig, MonthlySchedule
from apps.persistence.models.hymnal import Hymn
from apps.persistence.models.member import Member,MemberStatus,Role,Ministry
from apps.persistence.models.gallery import Album, Photo


models = [
    Category, Song, Played, Profile, ScheduleType,
    MemberScheduleConfig, MonthlySchedule, Hymn,
    Album, Photo, Member, MemberStatus, Role, Ministry
]

for model in models:
    admin.site.register(model)