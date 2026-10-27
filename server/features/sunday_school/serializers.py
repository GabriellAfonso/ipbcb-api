"""OpenAPI-only shapes of the Sunday school endpoints (specs/026-sunday-school contracts/api.md).

Bodies are validated by the Pydantic DTOs and ``content_schema``; these serializers only describe
them to drf-spectacular, so the generated Android client gets typed models. Keep them in sync
with ``dtos.py`` and ``content_schema.py``.
"""

from typing import Any

from drf_spectacular.utils import PolymorphicProxySerializer
from rest_framework import serializers

from features.sunday_school.domain.icons import LessonIcon
from features.sunday_school.domain.lesson_status import LessonStatus

# Blocks have fields named ``label`` and ``style``, which DRF's ``Field`` also declares as plain
# attributes. The serializer metaclass moves declared fields out of the class body, so the clash
# exists only for mypy; the wire names come from the content schema and cannot change.

_ICONS = [icon.value for icon in LessonIcon]
_STATUSES = [status.value for status in LessonStatus]


def _icon() -> serializers.ChoiceField:
    return serializers.ChoiceField(choices=_ICONS, allow_null=True, required=False)


def _optional_text() -> serializers.CharField:
    return serializers.CharField(allow_null=True, required=False)


class SundaySchoolVerseSpanSerializer(serializers.Serializer[Any]):
    start = serializers.IntegerField()
    end = serializers.IntegerField()


class SundaySchoolBibleReferenceSerializer(serializers.Serializer[Any]):
    book = serializers.CharField(help_text="Bible domain abbrev, e.g. 'Dn'.")
    chapter = serializers.IntegerField()
    verses = SundaySchoolVerseSpanSerializer(many=True, help_text="Empty means the whole chapter.")


class SundaySchoolProofTextSerializer(serializers.Serializer[Any]):
    printed = serializers.CharField()
    reference = SundaySchoolBibleReferenceSerializer(allow_null=True)


class SundaySchoolParagraphBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["paragraph"])
    text = serializers.CharField()
    proof_texts = SundaySchoolProofTextSerializer(many=True, required=False)


class SundaySchoolListItemSerializer(serializers.Serializer[Any]):
    text = serializers.CharField()
    proof_texts = SundaySchoolProofTextSerializer(many=True, required=False)


class SundaySchoolListBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["list"])
    style = serializers.ChoiceField(choices=["bullet", "numbered", "roman"])  # type: ignore[assignment]
    items = SundaySchoolListItemSerializer(many=True)


class SundaySchoolKeyVerseBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["key_verse"])
    label = _optional_text()  # type: ignore[assignment]
    text = serializers.CharField()
    proof = SundaySchoolProofTextSerializer()


class SundaySchoolCardSerializer(serializers.Serializer[Any]):
    icon = _icon()
    label = _optional_text()  # type: ignore[assignment]
    title = serializers.CharField()
    text = _optional_text()
    proof_texts = SundaySchoolProofTextSerializer(many=True, required=False)


class SundaySchoolCardsBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["cards"])
    items = SundaySchoolCardSerializer(many=True)


class SundaySchoolComparisonItemSerializer(serializers.Serializer[Any]):
    label = serializers.CharField()  # type: ignore[assignment]
    title = serializers.CharField()
    text = _optional_text()
    highlight = serializers.BooleanField()


class SundaySchoolComparisonBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["comparison"])
    items = SundaySchoolComparisonItemSerializer(many=True, help_text="Exactly 2.")


class SundaySchoolStepSerializer(serializers.Serializer[Any]):
    label = _optional_text()  # type: ignore[assignment]
    title = serializers.CharField()
    text = _optional_text()


class SundaySchoolStepsBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["steps"])
    items = SundaySchoolStepSerializer(many=True)


class SundaySchoolTableBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["table"])
    header = serializers.ListField(child=serializers.CharField())
    rows = serializers.ListField(
        child=serializers.ListField(child=serializers.CharField(allow_blank=True)),
        help_text="Each row as wide as the header.",
    )


class SundaySchoolStatSerializer(serializers.Serializer[Any]):
    value = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]


class SundaySchoolStatsBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["stats"])
    items = SundaySchoolStatSerializer(many=True)


class SundaySchoolTimelineEventSerializer(serializers.Serializer[Any]):
    when = serializers.CharField()
    text = serializers.CharField()


class SundaySchoolTimelineBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["timeline"])
    events = SundaySchoolTimelineEventSerializer(many=True)


class SundaySchoolBookFactsBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["book_facts"])
    book = serializers.CharField(help_text="Bible abbrev; derived numbers are in `books`.")
    author = _optional_text()
    date = _optional_text()
    style = _optional_text()  # type: ignore[assignment]
    reading_time = _optional_text()


LESSON_BLOCK_SCHEMA = PolymorphicProxySerializer(
    component_name="SundaySchoolBlock",
    serializers={
        "paragraph": SundaySchoolParagraphBlockSerializer,
        "list": SundaySchoolListBlockSerializer,
        "key_verse": SundaySchoolKeyVerseBlockSerializer,
        "cards": SundaySchoolCardsBlockSerializer,
        "comparison": SundaySchoolComparisonBlockSerializer,
        "steps": SundaySchoolStepsBlockSerializer,
        "table": SundaySchoolTableBlockSerializer,
        "stats": SundaySchoolStatsBlockSerializer,
        "timeline": SundaySchoolTimelineBlockSerializer,
        "book_facts": SundaySchoolBookFactsBlockSerializer,
    },
    resource_type_field_name="type",
    many=True,
)


class SundaySchoolSectionSerializer(serializers.Serializer[Any]):
    title = serializers.CharField()
    icon = _icon()
    blocks = LESSON_BLOCK_SCHEMA


class SundaySchoolLessonContentSerializer(serializers.Serializer[Any]):
    sections = SundaySchoolSectionSerializer(many=True)


class SundaySchoolYearSerializer(serializers.Serializer[Any]):
    year = serializers.IntegerField()
    theme = serializers.CharField(allow_blank=True)


class SundaySchoolYearAdminSerializer(SundaySchoolYearSerializer):
    lesson_count = serializers.IntegerField()
    published_count = serializers.IntegerField()


class SundaySchoolYearThemeSerializer(serializers.Serializer[Any]):
    theme = serializers.CharField(allow_blank=True, max_length=200)


class SundaySchoolLessonSummarySerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    title = serializers.CharField()
    date = serializers.DateField(allow_null=True)
    teacher = serializers.CharField(allow_blank=True)
    position = serializers.IntegerField()


class SundaySchoolBookFactsSerializer(serializers.Serializer[Any]):
    name = serializers.CharField()
    position = serializers.IntegerField(help_text="Number of the book in the Bible, from 1.")
    chapters = serializers.IntegerField()
    verses = serializers.IntegerField()


class SundaySchoolLessonSerializer(SundaySchoolLessonSummarySerializer):
    status = serializers.ChoiceField(choices=_STATUSES)
    year = SundaySchoolYearSerializer()
    content = SundaySchoolLessonContentSerializer()
    books = serializers.DictField(child=SundaySchoolBookFactsSerializer())


class SundaySchoolIndexSerializer(serializers.Serializer[Any]):
    years = SundaySchoolYearSerializer(many=True)
    default_year = serializers.IntegerField(allow_null=True)
    year = SundaySchoolYearSerializer(allow_null=True)
    lessons = SundaySchoolLessonSummarySerializer(many=True)


class SundaySchoolLessonCreateSerializer(serializers.Serializer[Any]):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    title = serializers.CharField(max_length=200)
    date = serializers.DateField(allow_null=True, required=False)
    teacher = serializers.CharField(allow_blank=True, required=False, max_length=120)
    status = serializers.ChoiceField(choices=_STATUSES)
    content = SundaySchoolLessonContentSerializer()


class SundaySchoolLessonPatchSerializer(SundaySchoolLessonCreateSerializer):
    """Every field optional; only ``date`` accepts null."""

    year = serializers.IntegerField(min_value=2000, max_value=2100, required=False)
    title = serializers.CharField(max_length=200, required=False)
    status = serializers.ChoiceField(choices=_STATUSES, required=False)
    content = SundaySchoolLessonContentSerializer(required=False)


class SundaySchoolLessonOrderSerializer(serializers.Serializer[Any]):
    year = serializers.IntegerField()
    lesson_ids = serializers.ListField(child=serializers.IntegerField())
