from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.persistence.models.songs import Category, Song, Played
from apps.persistence.models.profile import Profile
from apps.persistence.models.schedule import ScheduleType, MemberScheduleConfig, MonthlySchedule
from apps.persistence.models.hymnal import Hymn
from apps.persistence.models.member import Member,MemberStatus,Role,Ministry
from apps.persistence.models.gallery import Album, Photo
from apps.persistence.models.profile import User


models = [
    Category, Song, Played, Profile, ScheduleType,
    MemberScheduleConfig, Hymn,
    Album, Photo, Member, MemberStatus, Role, Ministry
]

for model in models:
    admin.site.register(model)

@admin.register(User)
class MyUserAdmin(BaseUserAdmin):

    list_display = ('username', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets

@admin.register(MonthlySchedule)
class MonthlyScheduleAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at",)
    fields = (
        "date",
        "schedule_type",
        "member",
        "created_at",
    )