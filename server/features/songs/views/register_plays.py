from dependency_injector.wiring import Provide, inject
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.domain.access import Scope
from core.http.permissions import scope_permission
from features.songs.dtos import parse_register_plays_input
from features.songs.services.register_plays_service import RegisterPlaysService


class RegisterSundayPlaysAPI(APIView):
    """POST: create Played records for a given date.

    Requires: ``manage`` on scope ``songs`` (specs/012-feature-role-permissions).

    Expected payload:
    {
      "date": "2026-02-07",
      "plays": [
        {"song_id": 12, "position": 1, "tone": "G"},
        {"song_id": 55, "position": 2, "tone": "A#"}
      ]
    }
    """

    permission_classes = [IsAuthenticated, scope_permission(Scope.SONGS)]

    @inject
    def post(
        self,
        request: Request,
        register_service: RegisterPlaysService = Provide[Container.register_plays_service],
    ) -> Response:
        # Validation and domain exceptions bubble up to custom_exception_handler
        date_value, play_inputs = parse_register_plays_input(request.data or {})
        created = register_service.register(date_value, play_inputs)
        return Response({"created": created}, status=201)
