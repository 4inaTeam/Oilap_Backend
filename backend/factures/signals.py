from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from products.models import Product
from users.models import CustomUser, Client
from .models import Facture
# factures/signals.py
@receiver(post_save, sender=Product)
def handle_facture_creation(sender, instance, created, **kwargs):  
    if instance.status == 'done':
        print(f"Product {instance.id} status is 'done', creating CLIENT facture...")
        
        with transaction.atomic():
            # Delete existing factures for this product
            Facture.objects.filter(product=instance).delete()
            
            # Create new CLIENT-type facture
            Facture.objects.create(
                type='CLIENT',  # Explicitly set type
                product=instance,
                client=instance.client,
                employee=instance.created_by,
                accountant=CustomUser.objects.filter(role='ACCOUNTANT').first()
            )
            
            print(f"CLIENT-type facture created for product {instance.id}")