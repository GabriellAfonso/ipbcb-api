from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpRequest

from features.accounts.models.access_request import AccessRequest
from features.accounts.models.profile import Profile
from features.accounts.models.user import User


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    # The member link is set here or in the app's "Perfis" (spec 022). Autocomplete searches the roll by name
    # (MemberAdmin.search_fields) instead of a dropdown of every member; the one-to-one's unique
    # check turns a second link to the same member into a form error (spec 015 FR-002).
    autocomplete_fields = ["member"]
    list_display = ("name", "user", "member_access", "access_requests_blocked", "member")
    # The grant record is written by "Perfis" only; turning member_access on here records no
    # grant (specs/022-access-requests FR-017b).
    readonly_fields = ("access_granted_by", "access_granted_at")

    def save_model(self, request: HttpRequest, obj: Profile, form: Any, change: bool) -> None:
        # Turning the flag off here is a revoke: no grant record may outlive the flag.
        if not obj.member_access:
            obj.access_granted_by = None
            obj.access_granted_at = None
        super().save_model(request, obj, form, change)


@admin.register(User)
class MyUserAdmin(BaseUserAdmin):  # type: ignore[type-arg]
    # is_active is the switch that actually revokes access — SimpleJWT checks it on every
    # authenticated request. It was not in the list, so there was no way to see at a glance
    # who is blocked.
    list_display = ("username", "is_active", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    # Read-only: requests are created by the app and decided in "Perfis", where the decision
    # also sets the flag and notifies the requester (specs/022-access-requests). Editing a row
    # here would do neither.
    list_display = ("user", "type", "status", "created_at", "decided_by", "decided_at")
    list_filter = ("type", "status")
    readonly_fields = (
        "user",
        "type",
        "message",
        "status",
        "decided_by",
        "decided_at",
        "denial_reason",
        "created_at",
    )

    def has_add_permission(self, request: object) -> bool:
        return False
