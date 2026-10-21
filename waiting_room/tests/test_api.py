from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from games.models import Game, Player
from waiting_room.models import WaitingEntry

JOIN = "/api/waiting-room/join/"
LEAVE = "/api/waiting-room/leave/"


def make_user(name):
    return User.objects.create_user(name, f"{name}@example.com", "S3cure-pass-phrase")


class WaitingRoomApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user("alice")
        self.client.force_authenticate(self.user)

    def test_anonymous_is_denied(self):
        anonymous = APIClient()
        self.assertIn(anonymous.post(JOIN).status_code, (401, 403))
        self.assertIn(anonymous.post(LEAVE).status_code, (401, 403))

    def test_join_creates_single_entry(self):
        response = self.client.post(JOIN)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, {"status": "waiting", "game_id": None})
        self.assertEqual(WaitingEntry.objects.filter(user=self.user).count(), 1)

    def test_second_join_is_rejected_without_changes(self):
        self.client.post(JOIN)
        entry = WaitingEntry.objects.get()
        response = self.client.post(JOIN)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(WaitingEntry.objects.count(), 1)
        self.assertEqual(WaitingEntry.objects.get().created_at, entry.created_at)

    def test_user_in_waiting_or_active_game_cannot_join(self):
        for status in (Game.Status.WAITING, Game.Status.ACTIVE):
            with self.subTest(status=status):
                game = Game.objects.create(status=status)
                player = Player.objects.create(user=self.user, game=game, color="red")
                self.assertEqual(self.client.post(JOIN).status_code, 409)
                self.assertFalse(WaitingEntry.objects.exists())
                player.delete()

    def test_user_with_only_completed_game_can_join(self):
        game = Game.objects.create(status=Game.Status.COMPLETED)
        Player.objects.create(user=self.user, game=game, color="red")
        self.assertEqual(self.client.post(JOIN).status_code, 201)

    def test_leave_removes_own_entry_only(self):
        other = make_user("bob")
        WaitingEntry.objects.create(user=other)
        self.client.post(JOIN)

        self.assertEqual(self.client.post(LEAVE).status_code, 204)
        self.assertFalse(WaitingEntry.objects.filter(user=self.user).exists())
        self.assertTrue(WaitingEntry.objects.filter(user=other).exists())

    def test_leave_when_not_waiting_changes_nothing(self):
        WaitingEntry.objects.create(user=make_user("bob"))
        self.assertEqual(self.client.post(LEAVE).status_code, 204)
        self.assertEqual(WaitingEntry.objects.count(), 1)

    def test_third_join_forms_a_game(self):
        for name in ("bob", "carol"):
            other = APIClient()
            other.force_authenticate(make_user(name))
            self.assertEqual(other.post(JOIN).data["status"], "waiting")

        response = self.client.post(JOIN)

        self.assertEqual(response.data["status"], "matched")
        game = Game.objects.get(pk=response.data["game_id"])
        self.assertEqual(game.status, Game.Status.WAITING)
        self.assertEqual(game.players.count(), 3)
        self.assertFalse(WaitingEntry.objects.exists())
