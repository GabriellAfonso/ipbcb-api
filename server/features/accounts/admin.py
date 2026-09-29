from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from features.accounts.models.profile import Profile
from features.accounts.models.user import User


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    # The member link is set here and nowhere else. Autocomplete searches the roll by name
    # (MemberAdmin.search_fields) instead of a dropdown of every member; the one-to-one's unique
    # check turns a second link to the same member into a form error (spec 015 FR-002).
    autocomplete_fields = ["member"]
    list_display = ("name", "user", "is_member", "member")


@admin.register(User)
class MyUserAdmin(BaseUserAdmin):  # type: ignore[type-arg]
    # is_active is the switch that actually revokes access — SimpleJWT checks it on every
    # authenticated request. It was not in the list, so there was no way to see at a glance
    # who is blocked.
    list_display = ("username", "is_active", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets
