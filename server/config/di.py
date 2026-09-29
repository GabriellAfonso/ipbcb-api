from pathlib import Path

from dependency_injector import containers, providers
from django.conf import settings

from features.accounts.repositories.profile_repository import ProfileRepositoryImpl
from features.accounts.repositories.user_repository import UserRepositoryImpl
from features.accounts.services.google_auth_service import GoogleAuthService
from features.accounts.services.login_service import LoginService
from features.accounts.services.profile_service import ProfileService
from features.accounts.services.refresh_service import RefreshService
from features.accounts.services.register_service import RegisterService
from core.application.access_service import AccessService
from core.repositories.access_repository import RoleGrantRepositoryImpl
from core.time.clock import SystemClock
from features.bible.repositories import BibleRepositoryImpl
from features.bible.services import BibleService
from features.gallery.repositories.gallery_repository import GalleryRepositoryImpl
from features.gallery.services.gallery_service import GalleryService
from features.media.repositories.filesystem_media_repository import FileSystemMediaRepository
from features.media.services.media_access_service import MediaAccessService
from features.members.repositories.member_change_log_repository import (
    MemberChangeLogRepositoryImpl,
)
from features.members.repositories.member_photo_storage import DefaultStorageMemberPhotoStorage
from features.members.repositories.member_repository import MemberRepositoryImpl
from features.members.repositories.member_roster_repository import MemberRosterRepositoryImpl
from features.members.services.member_change_log_service import MemberChangeLogService
from features.members.services.member_photo_service import MemberPhotoService
from features.members.services.member_roster_service import MemberRosterService
from features.members.services.member_service import MemberService
from features.songs.repositories.hymnal_history_repository import HymnalHistoryRepositoryImpl
from features.songs.repositories.hymnal_repository import HymnalRepositoryImpl
from features.songs.repositories.song_repository import SongRepositoryImpl
from features.songs.services.hymnal_history_config_service import HymnalHistoryConfigService
from features.songs.services.hymnal_history_ingest_service import HymnalHistoryIngestService
from features.songs.services.hymnal_history_report_service import HymnalHistoryReportService
from features.songs.services.hymnal_service import HymnalService
from features.songs.services.register_plays_service import RegisterPlaysService
from features.schedule.repositories.schedule_repository import ScheduleRepositoryImpl
from features.schedule.services.schedule_service import ScheduleService
from features.songs.services.song_service import SongService


def _media_root() -> Path:
    """Read at every provision, not at import, so ``override_settings(MEDIA_ROOT=...)``
    reaches the repository in tests."""
    return Path(settings.MEDIA_ROOT)


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "core.http.permissions",
            "features.accounts.views.auth",
            "features.accounts.views.profile",
            "features.bible.views",
            "features.gallery.views.gallery",
            "features.gallery.views.upload",
            "features.media.views.media_file",
            "features.songs.views.hymnal",
            "features.songs.views.hymnal_history",
            "features.songs.views.register_plays",
            "features.songs.views.songs",
            "features.members.views.birthdays",
            "features.members.views.members",
            "features.members.views.admin_members",
            "features.members.views.admin_member_photo",
            "features.members.views.admin_member_history",
            "features.schedule.views.schedule",
        ]
    )

    role_grant_repository = providers.Factory(RoleGrantRepositoryImpl)
    access_service = providers.Factory(AccessService, role_grant_repository=role_grant_repository)

    user_repository = providers.Factory(UserRepositoryImpl)
    profile_repository = providers.Factory(ProfileRepositoryImpl)

    register_service = providers.Factory(RegisterService, user_repository=user_repository)
    login_service = providers.Factory(LoginService)
    refresh_service = providers.Factory(RefreshService, user_repository=user_repository)
    google_auth_service = providers.Factory(
        GoogleAuthService,
        user_repository=user_repository,
        profile_repository=profile_repository,
    )
    profile_service = providers.Factory(ProfileService, profile_repository=profile_repository)

    bible_repository = providers.Singleton(BibleRepositoryImpl)
    bible_service = providers.Factory(BibleService, bible_repository=bible_repository)

    gallery_repository = providers.Factory(GalleryRepositoryImpl)
    gallery_service = providers.Factory(GalleryService, repository=gallery_repository)

    clock = providers.Singleton(SystemClock)

    song_repository = providers.Factory(SongRepositoryImpl)
    hymnal_repository = providers.Factory(HymnalRepositoryImpl)
    hymnal_history_repository = providers.Factory(HymnalHistoryRepositoryImpl)

    song_service = providers.Factory(SongService, repository=song_repository)
    register_plays_service = providers.Factory(RegisterPlaysService, repository=song_repository)
    hymnal_service = providers.Factory(HymnalService, repository=hymnal_repository)

    hymnal_history_ingest_service = providers.Factory(
        HymnalHistoryIngestService,
        repository=hymnal_history_repository,
        clock=clock,
    )
    hymnal_history_report_service = providers.Factory(
        HymnalHistoryReportService,
        repository=hymnal_history_repository,
    )
    hymnal_history_config_service = providers.Factory(
        HymnalHistoryConfigService,
        repository=hymnal_history_repository,
    )

    member_repository = providers.Factory(MemberRepositoryImpl)
    member_service = providers.Factory(MemberService, repository=member_repository)

    member_roster_repository = providers.Factory(MemberRosterRepositoryImpl)
    member_change_log_repository = providers.Factory(MemberChangeLogRepositoryImpl)
    member_photo_storage = providers.Factory(DefaultStorageMemberPhotoStorage)
    member_roster_service = providers.Factory(
        MemberRosterService,
        roster_repository=member_roster_repository,
        change_log_repository=member_change_log_repository,
        photo_storage=member_photo_storage,
        clock=clock,
    )
    member_photo_service = providers.Factory(
        MemberPhotoService,
        roster_repository=member_roster_repository,
        change_log_repository=member_change_log_repository,
        photo_storage=member_photo_storage,
    )
    member_change_log_service = providers.Factory(
        MemberChangeLogService,
        change_log_repository=member_change_log_repository,
        roster_repository=member_roster_repository,
    )

    schedule_repository = providers.Factory(ScheduleRepositoryImpl)
    schedule_service = providers.Factory(ScheduleService, repository=schedule_repository)

    media_file_repository = providers.Factory(
        FileSystemMediaRepository, root=providers.Callable(_media_root)
    )
    media_access_service = providers.Factory(MediaAccessService, repository=media_file_repository)
