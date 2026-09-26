from django.db.models import Prefetch, QuerySet

from features.members.dtos import (
    MemberCreateDTO,
    MemberOptionsDTO,
    MemberPatchDTO,
    MemberRecordDTO,
    MemberSummaryDTO,
    NamedRefDTO,
)
from features.members.models.member import Member, MemberStatus, Ministry, Role

# Patch fields that are plain columns on Member (ministries is M2M and handled apart). The
# names match the model attnames, so ids go straight to the FK columns: existence is checked
# by the service first, and writing ``status_id`` avoids loading the row just to assign it.
_PATCH_COLUMNS = frozenset(
    {
        "name",
        "first_name",
        "last_name",
        "birth_date",
        "gender",
        "status_id",
        "role_id",
        "baptism_date",
        "is_active",
    }
)


class MemberRosterRepositoryImpl:
    """Leader-side member persistence using Django ORM. Includes invalid profiles."""

    def exists(self, member_id: int) -> bool:
        return Member.objects.filter(pk=member_id).exists()

    def list_members(self) -> list[MemberSummaryDTO]:
        """Every member, valid or not, ordered by name, in one query.

        >>> repo.list_members()
        [MemberSummaryDTO(id=12, name='Ana Souza', ...), ...]
        """
        members = Member.objects.select_related("status").order_by("name", "id")
        return [_to_summary(member) for member in members]

    def get_record(self, member_id: int) -> MemberRecordDTO | None:
        """Full record with ministries sorted by name, or None for an unknown id.

        >>> repo.get_record(12).ministries
        [NamedRefDTO(id=2, name='Louvor'), ...]
        """
        ministries = Prefetch("ministries", queryset=Ministry.objects.order_by("name"))
        member = (
            Member.objects.select_related("status", "role")
            .prefetch_related(ministries)
            .filter(pk=member_id)
            .first()
        )
        return _to_record(member) if member else None

    def get_options(self) -> MemberOptionsDTO:
        return MemberOptionsDTO(
            statuses=_named_refs(MemberStatus.objects.order_by("name")),
            roles=_named_refs(Role.objects.order_by("name")),
            ministries=_named_refs(Ministry.objects.order_by("name")),
        )

    def find_status(self, status_id: int) -> NamedRefDTO | None:
        return _first_ref(MemberStatus.objects.filter(pk=status_id))

    def find_role(self, role_id: int) -> NamedRefDTO | None:
        return _first_ref(Role.objects.filter(pk=role_id))

    def find_ministries(self, ministry_ids: list[int]) -> list[NamedRefDTO]:
        """The existing ministries among ``ministry_ids``, in one query."""
        return _named_refs(Ministry.objects.filter(pk__in=ministry_ids).order_by("name"))

    def create(self, dto: MemberCreateDTO) -> int:
        fields = dto.model_dump(exclude={"ministry_ids"})
        member = Member.objects.create(**fields)
        member.ministries.set(dto.ministry_ids)
        return member.pk

    def update(self, member_id: int, dto: MemberPatchDTO) -> None:
        """Apply only the fields the caller sent (``dto.model_fields_set``)."""
        member = Member.objects.get(pk=member_id)
        columns = sorted(dto.model_fields_set & _PATCH_COLUMNS)
        for column in columns:
            setattr(member, column, getattr(dto, column))
        if columns:
            member.save(update_fields=columns)
        if "ministry_ids" in dto.model_fields_set:
            member.ministries.set(dto.ministry_ids or [])

    def delete(self, member_id: int) -> None:
        Member.objects.filter(pk=member_id).delete()

    def get_photo_name(self, member_id: int) -> str | None:
        name = Member.objects.filter(pk=member_id).values_list("photo", flat=True).first()
        return name or None

    def set_photo_name(self, member_id: int, name: str | None) -> None:
        # update() writes the column only: the file was already stored by MemberPhotoStorage.
        Member.objects.filter(pk=member_id).update(photo=name)


def _to_summary(member: Member) -> MemberSummaryDTO:
    return MemberSummaryDTO(
        id=member.pk,
        name=member.name,
        photo_path=member.photo.url if member.photo else None,
        status=_ref(member.status),
        is_active=member.is_active,
    )


def _to_record(member: Member) -> MemberRecordDTO:
    return MemberRecordDTO(
        id=member.pk,
        name=member.name,
        first_name=member.first_name,
        last_name=member.last_name,
        birth_date=member.birth_date,
        gender=member.gender,
        status=_ref(member.status),
        role=_ref(member.role),
        ministries=[NamedRefDTO(id=m.pk, name=m.name) for m in member.ministries.all()],
        baptism_date=member.baptism_date,
        is_active=member.is_active,
        photo_path=member.photo.url if member.photo else None,
        created_at=member.created_at,
    )


def _ref(item: MemberStatus | Role | None) -> NamedRefDTO | None:
    return NamedRefDTO(id=item.pk, name=item.name) if item else None


def _named_refs(
    items: "QuerySet[MemberStatus] | QuerySet[Role] | QuerySet[Ministry]",
) -> list[NamedRefDTO]:
    return [NamedRefDTO(id=pk, name=name) for pk, name in items.values_list("pk", "name")]


def _first_ref(items: "QuerySet[MemberStatus] | QuerySet[Role]") -> NamedRefDTO | None:
    refs = _named_refs(items)
    return refs[0] if refs else None
