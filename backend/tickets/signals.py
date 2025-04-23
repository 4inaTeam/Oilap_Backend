from django.db.models.signals import post_save
from django.dispatch import receiver
from factures.models import Facture
from .models import Ticket
from .notifications import send_email_notification, send_sms_notification


@receiver(post_save, sender=Facture)
def create_ticket_for_facture(sender, instance, created, **kwargs):
    if not created or instance.type != 'CLIENT':
        return
    
    try:
        if not instance.product or not instance.client:
            raise ValueError("Missing product or client for Facture")
            
        ticket = Ticket.objects.create(
            product=instance.product,
            client=instance.client,
            facture=instance
        )
        print(f"Successfully created Ticket {ticket.id} for Facture {instance.id}")
    except Exception as e:
        print(f"Failed to create Ticket for Facture {instance.id}: {str(e)}")

@receiver(post_save, sender=Ticket)
def handle_ticket_notifications(sender, instance, created, **kwargs):
    if not created:
        return

    send_email_notification(instance)
    
    if instance.client.tel:
        send_sms_notification(instance)