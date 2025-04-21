# tickets/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from factures.models import Facture
from .models import Ticket
from .notifications import send_ticket_notification

@receiver(post_save, sender=Facture)
def create_ticket_and_notify(sender, instance, created, **kwargs):
    if not created or instance.type != 'CLIENT':
        return
    
    # Create the ticket and pass the instance to the notification
    ticket = Ticket.objects.create(
        product=instance.product,
        client=instance.client,
        facture=instance
    )
    send_ticket_notification(ticket)  # Pass the ticket instance, not instance.tickets