from django.conf import settings
from django.db import models


class WaitingEntry(models.Model):
    """Текуща заявка за игра. OneToOne = най-много една заявка на потребител."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="waiting_entry",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} waiting since {self.created_at:%H:%M:%S}"
