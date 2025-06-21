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
    # Add product reference to track which product triggered the notification
    product = models.ForeignKey(
        'products.Product', on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    ticket_type = models.CharField(max_length=5, choices=TICKET_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_ticket_type_display()} ticket for {self.user.username}"


class Notification(models.Model):
    """Model to store notifications for users"""
    NOTIFICATION_TYPES = [
        ('product_ready', 'Product Ready'),  # Changed from 'facture' to 'product_ready'
        ('facture', 'Facture'),
        ('system', 'System'),
        ('reminder', 'Reminder'),
        ('test', 'Test'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    body = models.TextField()
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='system')
    data = models.JSONField(default=dict, blank=True)  # Store additional data as JSON
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Optional relations
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, null=True, blank=True)
        
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    @classmethod
    def create_product_ready_notification(cls, user, product, facture):
        """Create a notification when a product is ready and added to facture"""
        return cls.objects.create(
            user=user,
            title="Your Product is Ready!",
            body=f"Your product (Quality: {product.get_quality_display()}) is ready and added to facture {facture.facture_number}. Amount: {facture.final_total} TND. Please visit the accounting office to pay.",
            type='product_ready',
            facture=facture,
            product=product,
            data={
                'product_id': str(product.id),
                'facture_id': str(facture.id),
                'facture_number': facture.facture_number,
                'product_quality': product.quality,
                'product_price': str(product.price),
                'total_amount': str(facture.final_total),
                'route': '/facture_detail'
            }
        )

    @classmethod
    def create_facture_notification(cls, user, facture):
        """Create a notification for a new facture (kept for backward compatibility)"""
        return cls.objects.create(
            user=user,
            title="New Facture Created",
            body=f"Facture {facture.facture_number} - {facture.final_total} TND",
            type='facture',
            facture=facture,
            data={
                'facture_id': str(facture.id),
                'facture_number': facture.facture_number,
                'amount': str(facture.final_total),
                'route': '/facture_detail'
            }
        )
