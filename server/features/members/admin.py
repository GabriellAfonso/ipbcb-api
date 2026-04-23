from django.contrib import admin

from features.members.models.member import Member, MemberStatus, Ministry, Role

admin.site.register([Member, MemberStatus, Role, Ministry])
