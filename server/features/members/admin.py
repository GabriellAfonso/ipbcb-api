from django.contrib import admin

from features.members.models.member import Member, MemberStatus, Ministry, Role


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    # The profile form's member autocomplete searches through this (specs/015-gallery-member-tags
    # FR-002); Django requires search_fields on the target admin for it.
    search_fields = ["name"]
    ordering = ["name", "id"]


admin.site.register([MemberStatus, Role, Ministry])
