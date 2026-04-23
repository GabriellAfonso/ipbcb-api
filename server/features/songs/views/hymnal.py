from django.db.models import Func, IntegerField, Value
from django.db.models.functions import Cast, NullIf
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from features.songs.models.hymnal import Hymn
from features.core.http.utils import _not_modified_or_response


class hymnalAPI(APIView):
    def get(self, request: Request) -> Response:
        qs = (
            Hymn.objects.annotate(
                number_int=Cast(
                    NullIf(
                        Func(
                            "number",
                            Value("[^0-9].*"),
                            Value(""),
                            function="REGEXP_REPLACE",
                        ),
                        Value(""),
                    ),
                    IntegerField(),
                )
            )
            .order_by("number_int", "number")
            .values("number", "title", "lyrics")
        )

        result = list(qs)
        return _not_modified_or_response(request, result)
