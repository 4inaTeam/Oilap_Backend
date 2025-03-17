from django.db.models.signals import post_save
from django.dispatch import receiver
from products.models import Product
from .models import Invoice

@receiver(post_save, sender=Product)
def create_invoice(sender, instance, created, **kwargs):
    if instance.status == 'done' and not hasattr(instance, 'invoice'):
        # Get comptable user
        comptable = CustomUser.objects.filter(role='ACCOUNTANT').first()
        
        Invoice.objects.create(
            product=instance,
            client=instance.client,
            comptable=comptable,
            total_price=instance.price * instance.quantity
        )