from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."


class JoinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            services.join_waiting_room(request.user)
        except services.WaitingRoomError as exc:
            raise Conflict(str(exc))

        # Задействане: след всяко записване опитваме да сформираме игра.
        game = services.try_form_game()
        in_game = game is not None and game.players.filter(user=request.user).exists()
        return Response(
            {"status": "matched" if in_game else "waiting", "game_id": game.id if in_game else None},
            status=status.HTTP_201_CREATED,
        )


class LeaveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        services.leave_waiting_room(request.user)  # без значение дали е чакал
        return Response(status=status.HTTP_204_NO_CONTENT)
