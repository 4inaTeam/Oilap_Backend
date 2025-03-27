from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from products.models import Product
from users.models import CustomUser, Client
from .models import Facture

@receiver(post_save, sender=Product)
def handle_facture_creation(sender, instance, created, **kwargs):  
    print(f"Signal triggered for Product ID: {instance.id}, created={created}")

    if not created:
        print(f"Product {instance.id} updated, checking status...")
    
    if instance.status == 'done':
        print(f"Product {instance.id} status is 'done', creating facture...")

        with transaction.atomic():
            Facture.objects.filter(product=instance).delete()
            
            facture = Facture.objects.create(
                product=instance,
                client=instance.client,
                employee=instance.created_by,
                accountant=CustomUser.objects.filter(role='ACCOUNTANT').first()
            )
            
            facture.save()  
            print(f"Facture created with ID: {facture.id}")

            notification_data = {
                'facture_id': facture.id,
                'client_id': facture.client.id,
                'total_amount': str(facture.total_amount),
                'due_date': facture.due_date.isoformat()
            }
            
            print("Notification data:", notification_data)
            # TODO: Integrate with Firebase Cloud Messaging
            # send_fcm_notification(notification_data)
    else:
        print(f"Product {instance.id} status is not 'done', skipping facture creation.")
