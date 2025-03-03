from django.db import models
from clients.models import Client  # Import Client from the clients app
from users.models import CustomUser  # Import CustomUser from the users app

class Product(models.Model):
    name = models.CharField(max_length=100)
    quality = models.TextField(blank=True, null=True)  # <-- Field is named 'quality'
    price = models.DecimalField(max_digits=10, decimal_places=2)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='products')
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='products')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name