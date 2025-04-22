# tickets/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from factures.models import Facture
from .models import Ticket
from .notifications import send_ticket_notification

@receiver(post_save, sender=Facture)
def create_ticket_and_notify(sender, instance, created, **kwargs):
    if not created or instance.type != 'CLIENT':
        print("Signal: Facture not created or not CLIENT type")
        return
    
    print("Creating Ticket...")
    ticket = Ticket.objects.create(
        product=instance.product,
        client=instance.client,
        facture=instance
    )
    print(f"Ticket created: {ticket}")
    send_ticket_notification(ticket)
    print("Notification sent.")