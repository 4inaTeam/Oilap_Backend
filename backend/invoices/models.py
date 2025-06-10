from django.db import models

class Invoice (models.Model):
    filename = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    confidence = models.FloatField()
    pay_date = models.CharField(max_length=100, null =True, blank=True)
    montant = models.CharField(max_length= 100, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.filenmame}"

