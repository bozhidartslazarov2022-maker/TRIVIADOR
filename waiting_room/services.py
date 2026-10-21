import random

from django.db import IntegrityError, transaction

from games.models import Game, Player

from .models import WaitingEntry

PLAYERS_PER_GAME = 3


class WaitingRoomError(Exception):
    """Базов клас за отказите на чакалнята."""


class AlreadyWaiting(WaitingRoomError):
    pass


class NotEligible(WaitingRoomError):
    pass


class NotEnoughWaitingPlayers(WaitingRoomError):
    pass


def _blocked_user_ids():
    """Потребители с участие в игра waiting или active."""
    return Player.objects.filter(game__status__in=Game.BLOCKING_STATUSES).values("user")


def is_eligible(user):
    return not _blocked_user_ids().filter(user=user).exists()


def eligible_entries():
    return WaitingEntry.objects.exclude(user__in=_blocked_user_ids())


def join_waiting_room(user):
    if not is_eligible(user):
        raise NotEligible("You are already a player in a waiting or active game.")
    try:
        with transaction.atomic():
            return WaitingEntry.objects.create(user=user)
    except IntegrityError:
        raise AlreadyWaiting("You are already in the waiting room.")


def leave_waiting_room(user):
    """Изтрива собствената заявка. Връща True, ако е имало такава."""
    deleted, _ = WaitingEntry.objects.filter(user=user).delete()
    return deleted > 0


@transaction.atomic
def form_game():
    """Сформира една waiting игра от трима случайни допустими чакащи.

    Всичко е в една транзакция: при грешка по средата не остават частична
    игра, участия или изгубени заявки. При <3 допустими - без промени.
    """
    entries = list(eligible_entries().select_related("user"))
    if len(entries) < PLAYERS_PER_GAME:
        raise NotEnoughWaitingPlayers(
            f"Need {PLAYERS_PER_GAME} eligible waiting players, got {len(entries)}."
        )

    chosen = random.sample(entries, PLAYERS_PER_GAME)
    colors = random.sample(Player.Color.values, PLAYERS_PER_GAME)

    game = Game.objects.create(status=Game.Status.WAITING)
    for entry, color in zip(chosen, colors):
        Player.objects.create(user=entry.user, game=game, color=color, score=0)
    WaitingEntry.objects.filter(pk__in=[entry.pk for entry in chosen]).delete()
    return game


def try_form_game():
    """Задействане на сформирането: игра или None, ако още няма трима."""
    try:
        return form_game()
    except NotEnoughWaitingPlayers:
        return None
