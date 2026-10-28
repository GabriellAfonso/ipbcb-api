"""OpenAPI-only response shapes (specs/019-doctrine-documents research R-07).

The views build their bodies from the Pydantic DTOs; these serializers only describe that body
to drf-spectacular, so the generated Android client gets typed models. Keep them in sync with
``features/doctrine/dtos.py``.
"""

from drf_spectacular.utils import PolymorphicProxySerializer
from rest_framework import serializers


class VerseSpanSerializer(serializers.Serializer[object]):
    start = serializers.IntegerField()
    end = serializers.IntegerField()


class BibleReferenceSerializer(serializers.Serializer[object]):
    book = serializers.CharField(help_text="Bible domain abbrev, e.g. '1Tn'.")
    chapter = serializers.IntegerField()
    verses = VerseSpanSerializer(many=True, help_text="Empty means the whole chapter.")


class ProofTextSerializer(serializers.Serializer[object]):
    printed = serializers.CharField(help_text="Exactly as published.")
    reference = BibleReferenceSerializer(allow_null=True, help_text="Null when not interpreted.")


class CatechismQuestionSerializer(serializers.Serializer[object]):
    number = serializers.IntegerField()
    question = serializers.CharField()
    answer = serializers.CharField()
    proof_texts = ProofTextSerializer(many=True)


class ParagraphListSerializer(serializers.Serializer[object]):
    heading = serializers.CharField()
    items = serializers.ListField(child=serializers.CharField())


class ConfessionParagraphSerializer(serializers.Serializer[object]):
    number = serializers.IntegerField()
    text = serializers.CharField()
    lists = ParagraphListSerializer(many=True, required=False, help_text="Only in 1.2.")
    text_after = serializers.CharField(required=False, help_text="Only in 1.2.")


class ConfessionChapterSerializer(serializers.Serializer[object]):
    number = serializers.IntegerField()
    title = serializers.CharField()
    paragraphs = ConfessionParagraphSerializer(many=True)


class DocumentSourceSerializer(serializers.Serializer[object]):
    """``edition`` and ``year``, shared by the list entry and both document shapes."""

    edition = serializers.CharField(
        allow_null=True, help_text="Source of the text; null if unknown."
    )
    year = serializers.IntegerField(allow_null=True, help_text="e.g. 1647; null if unknown.")


class CatechismDocumentSerializer(DocumentSourceSerializer):
    slug = serializers.CharField()
    title = serializers.CharField()
    kind = serializers.ChoiceField(choices=["catechism"])
    position = serializers.IntegerField()
    questions = CatechismQuestionSerializer(many=True)


class ConfessionDocumentSerializer(DocumentSourceSerializer):
    slug = serializers.CharField()
    title = serializers.CharField()
    kind = serializers.ChoiceField(choices=["confession"])
    position = serializers.IntegerField()
    chapters = ConfessionChapterSerializer(many=True)


class DoctrineDocumentSummarySerializer(DocumentSourceSerializer):
    slug = serializers.CharField()
    title = serializers.CharField()
    kind = serializers.ChoiceField(choices=["catechism", "confession"])
    item_count = serializers.IntegerField(help_text="Questions, or chapters for a confession.")


class DoctrineDocumentListSerializer(serializers.Serializer[object]):
    documents = DoctrineDocumentSummarySerializer(many=True)


DOCTRINE_DOCUMENT_SCHEMA = PolymorphicProxySerializer(
    component_name="DoctrineDocument",
    serializers={
        "catechism": CatechismDocumentSerializer,
        "confession": ConfessionDocumentSerializer,
    },
    resource_type_field_name="kind",
)
