from django.db import models
from users.models import CustomUser
from factures.models import Facture
from django.utils import timezone

class Ticket(models.Model):
    TICKET_TYPES = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('PUSH', 'Push Notification'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    facture = models.ForeignKey(
        Facture, on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    ticket_type = models.CharField(max_length=5, choices=TICKET_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_ticket_type_display()} ticket for {self.user.username}"