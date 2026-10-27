from pathlib import Path

from dependency_injector import containers, providers
from django.conf import settings

from features.accounts.repositories.access_request_repository import (
    AccessRequestRepositoryImpl,
)
from features.accounts.repositories.avatar_downloader import HttpAvatarDownloader
from features.accounts.repositories.managed_account_repository import (
    ManagedAccountRepositoryImpl,
)
from features.accounts.repositories.profile_repository import ProfileRepositoryImpl
from features.accounts.repositories.refresh_token_repository import RefreshTokenRepositoryImpl
from features.accounts.repositories.user_repository import UserRepositoryImpl
from features.accounts.services.access_request_service import AccessRequestService
from features.accounts.services.account_deletion_service import AccountDeletionService
from features.accounts.services.google_auth_service import GoogleAuthService
from features.accounts.services.login_service import LoginService
from features.accounts.services.password_change_service import PasswordChangeService
from features.accounts.services.profile_management_service import (
    ProfileManagementService,
)
from features.accounts.services.profile_service import ProfileService
from features.accounts.services.refresh_service import RefreshService
from features.accounts.services.register_service import RegisterService
from core.application.access_service import AccessService
from core.application.device_token_service import DeviceTokenService
from core.application.push_service import PushService
from core.application.worship_access_service import WorshipAccessService
from core.push.factory import build_push_sender
from core.repositories.access_repository import RoleGrantRepositoryImpl
from core.repositories.device_token_repository import DeviceTokenRepositoryImpl
from core.repositories.member_account_repository import MemberAccountRepositoryImpl
from core.repositories.worship_repository import WorshipMembershipRepositoryImpl
from core.time.clock import SystemClock
from features.bible.repositories import BibleRepositoryImpl
from features.bible.repositories.progress_repository import BibleProgressRepositoryImpl
from features.bible.repositories.video_repository import BibleVideoRepositoryImpl
from features.bible.repositories.youtube_oembed import HttpYouTubeOEmbedClient
from features.bible.services import BibleService
from features.bible.services.progress_service import BibleProgressService
from features.bible.services.video_service import BibleVideoService
from features.doctrine.repositories import DoctrineRepositoryImpl
from features.doctrine.services import DoctrineService
from core.files.imaging.pillow_image_processor import PillowImageProcessor
from features.events.repositories.event_image_lookup import EventImageLookupImpl
from features.events.repositories.event_image_storage import DefaultStorageEventImageStorage
from features.events.repositories.event_repository import EventRepositoryImpl
from features.events.services.event_image_preparer import EventImagePreparer
from features.events.services.event_service import EventService
from features.events.services.event_write_service import EventWriteService
from features.gallery.repositories.album_repository import AlbumRepositoryImpl
from features.gallery.repositories.gallery_file_storage import DefaultStorageGalleryFileStorage
from features.gallery.repositories.deletion_mark_repository import DeletionMarkRepositoryImpl
from features.gallery.repositories.gallery_repository import GalleryRepositoryImpl
from features.gallery.repositories.photo_tag_repository import PhotoTagRepositoryImpl
from features.gallery.repositories.trash_repository import TrashRepositoryImpl
from features.gallery.repositories.trashed_file_lookup import GalleryTrashedFileLookup
from features.gallery.services.album_cover_service import AlbumCoverService
from features.gallery.services.album_service import AlbumService
from features.gallery.services.cover_change_tracker import CoverChangeTracker
from features.gallery.services.gallery_change_feed_service import GalleryChangeFeedService
from features.gallery.services.gallery_purge_service import GalleryPurgeService
from features.gallery.services.gallery_service import GalleryService
from features.gallery.services.gallery_trash_service import GalleryTrashService
from features.gallery.services.photo_tag_service import PhotoTagService
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
from features.songs.repositories.setlist_repository import SetlistRepositoryImpl
from features.songs.repositories.song_repository import SongRepositoryImpl
from features.songs.services.hymnal_history_config_service import HymnalHistoryConfigService
from features.songs.services.hymnal_history_ingest_service import HymnalHistoryIngestService
from features.songs.services.hymnal_history_report_service import HymnalHistoryReportService
from features.songs.services.hymnal_service import HymnalService
from features.songs.services.register_plays_service import RegisterPlaysService
from features.songs.services.setlist_purge_service import SetlistPurgeService
from features.songs.services.setlist_reminder_service import SetlistReminderService
from features.songs.services.setlist_service import SetlistService
from features.schedule.repositories.reminder_repository import RotaReminderRepositoryImpl
from features.schedule.repositories.schedule_repository import ScheduleRepositoryImpl
from features.schedule.services.schedule_reminder_service import ScheduleReminderService
from features.schedule.services.schedule_service import ScheduleService
from features.songs.services.song_service import SongService


def _media_root() -> Path:
    """Read at every provision, not at import, so ``override_settings(MEDIA_ROOT=...)``
    reaches the repository in tests."""
    return Path(settings.MEDIA_ROOT)


def _push_credentials() -> str:
    """Read when the sender is first built, not at import: settings are not loaded yet then."""
    return str(settings.FCM_SERVICE_ACCOUNT_JSON_BASE64)


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "core.http.permissions",
            "features.accounts.views.access_requests",
            "features.accounts.views.account",
            "features.accounts.views.admin_profiles",
            "features.accounts.views.account_deletion_page",
            "features.accounts.views.auth",
            "features.accounts.views.devices",
            "features.accounts.views.profile",
            "features.bible.views",
            "features.bible.views.progress",
            "features.bible.views.videos",
            "features.doctrine.views",
            "features.events.views.admin_events",
            "features.events.views.public_events",
            "features.gallery.admin",
            "features.gallery.management.commands.fill_gallery_file_sizes",
            "features.gallery.management.commands.generate_photo_thumbnails",
            "features.gallery.management.commands.purge_gallery_trash",
            "features.songs.management.commands.send_setlist_reminders",
            "features.songs.management.commands.purge_expired_setlists",
            "features.schedule.management.commands.send_schedule_reminders",
            "features.gallery.views.albums",
            "features.gallery.views.album_cover",
            "features.gallery.views.changes",
            "features.gallery.signals",
            "features.gallery.views.gallery",
            "features.gallery.views.tags",
            "features.gallery.views.trash",
            "features.gallery.views.upload",
            "features.media.views.media_file",
            "features.songs.views.hymnal",
            "features.songs.views.hymnal_history",
            "features.songs.views.register_plays",
            "features.songs.views.setlists",
            "features.songs.views.songs",
            "features.members.views.birthdays",
            "features.members.views.members",
            "features.members.views.own_member",
            "features.members.views.admin_members",
            "features.members.views.admin_member_photo",
            "features.members.views.admin_member_history",
            "features.schedule.views.schedule",
        ]
    )

    role_grant_repository = providers.Factory(RoleGrantRepositoryImpl)
    access_service = providers.Factory(AccessService, role_grant_repository=role_grant_repository)

    # Worship ministry and push (specs/017-sunday-setlist-push). The sender is a Singleton so the
    # OAuth token (valid 1 h) and the HTTP connection are reused across sends.
    worship_membership_repository = providers.Factory(WorshipMembershipRepositoryImpl)
    worship_access_service = providers.Factory(
        WorshipAccessService,
        membership_repository=worship_membership_repository,
        access_service=access_service,
    )
    device_token_repository = providers.Factory(DeviceTokenRepositoryImpl)
    push_sender = providers.Singleton(
        build_push_sender, encoded_credentials=providers.Callable(_push_credentials)
    )
    push_service = providers.Factory(
        PushService, token_repository=device_token_repository, sender=push_sender
    )
    device_token_service = providers.Factory(
        DeviceTokenService, token_repository=device_token_repository
    )

    user_repository = providers.Factory(UserRepositoryImpl)
    profile_repository = providers.Factory(ProfileRepositoryImpl)
    avatar_downloader = providers.Factory(HttpAvatarDownloader)

    register_service = providers.Factory(RegisterService, user_repository=user_repository)
    login_service = providers.Factory(LoginService)
    refresh_service = providers.Factory(RefreshService, user_repository=user_repository)
    google_auth_service = providers.Factory(
        GoogleAuthService,
        user_repository=user_repository,
        profile_repository=profile_repository,
        avatar_downloader=avatar_downloader,
    )
    profile_service = providers.Factory(ProfileService, profile_repository=profile_repository)

    # Account self-service (specs/021-user-account).
    refresh_token_repository = providers.Factory(RefreshTokenRepositoryImpl)
    password_change_service = providers.Factory(
        PasswordChangeService,
        user_repository=user_repository,
        refresh_token_repository=refresh_token_repository,
    )
    account_deletion_service = providers.Factory(
        AccountDeletionService,
        user_repository=user_repository,
        refresh_token_repository=refresh_token_repository,
        google_resolver=google_auth_service,
    )

    bible_repository = providers.Singleton(BibleRepositoryImpl)
    bible_service = providers.Factory(BibleService, bible_repository=bible_repository)

    doctrine_repository = providers.Singleton(DoctrineRepositoryImpl)
    doctrine_service = providers.Factory(DoctrineService, doctrine_repository=doctrine_repository)

    clock = providers.Singleton(SystemClock)

    # Bible videos and reading progress (specs/025-bible-videos). The canon is read once from
    # the translations the Bible repository already loaded.
    bible_canon = bible_repository.provided.canon.call()
    bible_video_repository = providers.Factory(BibleVideoRepositoryImpl)
    youtube_metadata_client = providers.Factory(HttpYouTubeOEmbedClient)
    bible_video_service = providers.Factory(
        BibleVideoService,
        repository=bible_video_repository,
        youtube=youtube_metadata_client,
        canon=bible_canon,
    )
    bible_progress_repository = providers.Factory(BibleProgressRepositoryImpl)
    bible_progress_service = providers.Factory(
        BibleProgressService, repository=bible_progress_repository, canon=bible_canon, clock=clock
    )

    # Member access and access requests (specs/022-access-requests).
    access_request_repository = providers.Factory(AccessRequestRepositoryImpl)
    managed_account_repository = providers.Factory(ManagedAccountRepositoryImpl)
    access_request_service = providers.Factory(
        AccessRequestService,
        request_repository=access_request_repository,
        account_repository=managed_account_repository,
        role_directory=access_service,
        push_notifier=push_service,
        clock=clock,
    )
    profile_management_service = providers.Factory(
        ProfileManagementService,
        request_repository=access_request_repository,
        account_repository=managed_account_repository,
        push_notifier=push_service,
        clock=clock,
    )

    gallery_repository = providers.Factory(GalleryRepositoryImpl, clock=clock)
    album_repository = providers.Factory(AlbumRepositoryImpl, clock=clock)
    gallery_file_storage = providers.Factory(DefaultStorageGalleryFileStorage)
    image_processor = providers.Singleton(PillowImageProcessor)
    cover_change_tracker = providers.Factory(CoverChangeTracker, album_repository=album_repository)
    album_service = providers.Factory(
        AlbumService,
        album_repository=album_repository,
        file_storage=gallery_file_storage,
        cover_tracker=cover_change_tracker,
    )
    album_cover_service = providers.Factory(
        AlbumCoverService,
        album_repository=album_repository,
        file_storage=gallery_file_storage,
        image_processor=image_processor,
        cover_tracker=cover_change_tracker,
    )
    gallery_service = providers.Factory(
        GalleryService,
        repository=gallery_repository,
        album_repository=album_repository,
        file_storage=gallery_file_storage,
        image_processor=image_processor,
        cover_service=album_cover_service,
    )
    trash_repository = providers.Factory(TrashRepositoryImpl, clock=clock)
    deletion_mark_repository = providers.Factory(DeletionMarkRepositoryImpl, clock=clock)
    gallery_trash_service = providers.Factory(
        GalleryTrashService,
        album_repository=album_repository,
        gallery_repository=gallery_repository,
        trash_repository=trash_repository,
        mark_repository=deletion_mark_repository,
        cover_tracker=cover_change_tracker,
        album_service=album_service,
        file_storage=gallery_file_storage,
    )
    gallery_purge_service = providers.Factory(
        GalleryPurgeService,
        trash_repository=trash_repository,
        mark_repository=deletion_mark_repository,
        file_storage=gallery_file_storage,
        clock=clock,
    )
    gallery_change_feed_service = providers.Factory(
        GalleryChangeFeedService,
        album_service=album_service,
        album_repository=album_repository,
        gallery_repository=gallery_repository,
        mark_repository=deletion_mark_repository,
        clock=clock,
    )

    # Church events (specs/020-church-events). Shares the image processor with the gallery.
    event_repository = providers.Factory(EventRepositoryImpl)
    event_image_storage = providers.Factory(DefaultStorageEventImageStorage)
    event_image_preparer = providers.Factory(EventImagePreparer, image_processor=image_processor)
    event_service = providers.Factory(
        EventService, repository=event_repository, image_storage=event_image_storage, clock=clock
    )
    event_write_service = providers.Factory(
        EventWriteService,
        repository=event_repository,
        image_storage=event_image_storage,
        image_preparer=event_image_preparer,
    )

    song_repository = providers.Factory(SongRepositoryImpl)
    hymnal_repository = providers.Factory(HymnalRepositoryImpl)
    hymnal_history_repository = providers.Factory(HymnalHistoryRepositoryImpl)

    song_service = providers.Factory(SongService, repository=song_repository)
    register_plays_service = providers.Factory(RegisterPlaysService, repository=song_repository)
    hymnal_service = providers.Factory(HymnalService, repository=hymnal_repository)

    setlist_repository = providers.Factory(SetlistRepositoryImpl)
    setlist_service = providers.Factory(
        SetlistService,
        setlist_repository=setlist_repository,
        song_repository=song_repository,
        worship_access_service=worship_access_service,
        push_service=push_service,
        clock=clock,
    )
    setlist_reminder_service = providers.Factory(
        SetlistReminderService,
        setlist_repository=setlist_repository,
        worship_access_service=worship_access_service,
        push_service=push_service,
        clock=clock,
    )
    setlist_purge_service = providers.Factory(
        SetlistPurgeService, setlist_repository=setlist_repository, clock=clock
    )

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

    # The members feature implements the gallery's MemberDirectory port with its repository;
    # wired here so neither feature imports the other (specs/015-gallery-member-tags R-03).
    photo_tag_repository = providers.Factory(PhotoTagRepositoryImpl, clock=clock)
    photo_tag_service = providers.Factory(
        PhotoTagService,
        tag_repository=photo_tag_repository,
        member_directory=member_repository,
        gallery_repository=gallery_repository,
    )

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
    # Rota reminders by push (specs/024-schedule-reminders).
    rota_reminder_repository = providers.Factory(RotaReminderRepositoryImpl)
    member_account_repository = providers.Factory(MemberAccountRepositoryImpl)
    schedule_reminder_service = providers.Factory(
        ScheduleReminderService,
        reminder_repository=rota_reminder_repository,
        member_account_repository=member_account_repository,
        push_service=push_service,
        clock=clock,
    )

    media_file_repository = providers.Factory(
        FileSystemMediaRepository, root=providers.Callable(_media_root)
    )
    # The gallery and events implement the media check's ports; wired here so no feature imports
    # another (specs/014-gallery-trash-sync research R-05, specs/020-church-events R-05).
    gallery_trashed_file_lookup = providers.Factory(GalleryTrashedFileLookup)
    event_image_lookup = providers.Factory(EventImageLookupImpl)
    media_access_service = providers.Factory(
        MediaAccessService,
        repository=media_file_repository,
        trashed_lookup=gallery_trashed_file_lookup,
        event_image_lookup=event_image_lookup,
    )
