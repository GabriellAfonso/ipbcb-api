from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models.profile import Profile
from apps.accounts.models.user import User


admin.site.register(Profile)


@admin.register(User)
class MyUserAdmin(BaseUserAdmin):
    list_display = ('username', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets
