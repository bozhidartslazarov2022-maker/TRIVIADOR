from unittest import mock

from django.test import TestCase

from accounts.models import User
from games.models import Game, Player
from waiting_room import services
from waiting_room.models import WaitingEntry


def make_users(count):
    return [
        User.objects.create_user(f"user{i}", f"user{i}@example.com", "S3cure-pass-phrase")
        for i in range(count)
    ]


def enqueue(users):
    for user in users:
        WaitingEntry.objects.create(user=user)


class FormGameTests(TestCase):
    def test_five_waiting_creates_game_and_two_remain(self):
        users = make_users(5)
        enqueue(users)

        game = services.form_game()

        self.assertEqual(Game.objects.count(), 1)
        self.assertEqual(game.status, Game.Status.WAITING)
        players = list(game.players.all())
        self.assertEqual(len(players), 3)
        self.assertEqual(len({p.user_id for p in players}), 3)
        self.assertEqual({p.color for p in players}, set(Player.Color.values))
        self.assertTrue(all(p.score == 0 for p in players))

        chosen_ids = {p.user_id for p in players}
        remaining_ids = set(WaitingEntry.objects.values_list("user_id", flat=True))
        self.assertEqual(len(remaining_ids), 2)
        self.assertTrue(chosen_ids.isdisjoint(remaining_ids))
        self.assertEqual(chosen_ids | remaining_ids, {u.id for u in users})
        self.assertEqual(Player.objects.count(), 3)

    def test_two_waiting_changes_nothing(self):
        users = make_users(2)
        enqueue(users)

        with self.assertRaises(services.NotEnoughWaitingPlayers):
            services.form_game()

        self.assertEqual(Game.objects.count(), 0)
        self.assertEqual(Player.objects.count(), 0)
        self.assertEqual(WaitingEntry.objects.count(), 2)

    def test_ineligible_waiting_users_are_skipped(self):
        users = make_users(4)
        enqueue(users)
        busy_game = Game.objects.create(status=Game.Status.ACTIVE)
        Player.objects.create(user=users[0], game=busy_game, color="red")

        game = services.form_game()

        self.assertEqual({p.user_id for p in game.players.all()}, {u.id for u in users[1:]})
        # Блокираният остава в чакалнята - заявката му не се губи.
        self.assertEqual(list(WaitingEntry.objects.values_list("user_id", flat=True)), [users[0].id])

    def test_only_blocked_users_leave_too_few_eligible(self):
        users = make_users(3)
        enqueue(users)
        busy_game = Game.objects.create(status=Game.Status.WAITING)
        Player.objects.create(user=users[0], game=busy_game, color="red")

        with self.assertRaises(services.NotEnoughWaitingPlayers):
            services.form_game()
        self.assertEqual(Game.objects.count(), 1)  # само busy_game
        self.assertEqual(WaitingEntry.objects.count(), 3)

    def test_completed_game_does_not_block(self):
        users = make_users(3)
        enqueue(users)
        old_game = Game.objects.create(status=Game.Status.COMPLETED)
        Player.objects.create(user=users[0], game=old_game, color="red", score=5)

        game = services.form_game()

        self.assertEqual(game.players.count(), 3)
        self.assertEqual(Game.objects.count(), 2)  # старата игра се запазва
        self.assertEqual(WaitingEntry.objects.count(), 0)

    def test_failure_midway_rolls_everything_back(self):
        users = make_users(3)
        enqueue(users)
        real_create = Player.objects.create
        calls = []

        def fail_on_second_player(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise RuntimeError("boom")
            return real_create(**kwargs)

        with mock.patch("waiting_room.services.Player.objects.create", side_effect=fail_on_second_player):
            with self.assertRaises(RuntimeError):
                services.form_game()

        self.assertEqual(len(calls), 2)  # първото участие е било създадено преди грешката
        self.assertEqual(Game.objects.count(), 0)
        self.assertEqual(Player.objects.count(), 0)
        self.assertEqual(WaitingEntry.objects.count(), 3)
