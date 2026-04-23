from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from features.accounts.models.profile import Profile
from features.accounts.models.user import User


admin.site.register(Profile)


@admin.register(User)
class MyUserAdmin(BaseUserAdmin):  # type: ignore[type-arg]
    list_display = ("username", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets
