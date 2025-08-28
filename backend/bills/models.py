from django.db import models
from django.utils import timezone
from django.conf import settings
from users.models import CustomUser


class Bill(models.Model):
    CATEGORY_CHOICES = [
        ('water', 'Water'),
        ('electricity', 'Electricity'),
        ('purchase', 'Purchase'),
        ('bilan', 'Bilan'),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='bills'
    )
    owner = models.CharField(
        max_length=255,
        null=False,
        blank=False,
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    payment_date = models.DateField(
        default=timezone.now
    )
    consumption = models.FloatField(
        null=True,
        blank=True,
        help_text="kWh for electricity, m³ for water"
    )
    original_image = models.ImageField(
        upload_to='bills/original/'
    )
    pdf_file = models.FileField(
        upload_to='bills/pdf/',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.category} Bill - {self.payment_date}"

    def get_absolute_image_url(self):
        """
        🔧 FIX: Return absolute URL for original image
        """
        if not self.original_image:
            return None

        # Get the image URL
        image_url = str(self.original_image.url)

        # If it's already a full URL (Cloudinary), return as-is
        if image_url.startswith('http'):
            return image_url

        # For local files in production, construct absolute URL
        if hasattr(settings, 'USE_ABSOLUTE_URLS') and settings.USE_ABSOLUTE_URLS:
            base_url = getattr(settings, 'PRODUCTION_DOMAIN',
                               'https://oilap-backend-1.onrender.com')

            # Remove leading slash if present
            if image_url.startswith('/'):
                image_url = image_url[1:]

            return f"{base_url}/{image_url}"

        return self.original_image.url

    def get_absolute_pdf_url(self):
        """
        🔧 FIX: Return absolute URL for PDF file
        """
        if not self.pdf_file:
            return None

        # Get the PDF URL
        pdf_url = str(self.pdf_file.url)

        # If it's already a full URL (Cloudinary), return as-is
        if pdf_url.startswith('http'):
            return pdf_url

        # For local files in production, construct absolute URL
        if hasattr(settings, 'USE_ABSOLUTE_URLS') and settings.USE_ABSOLUTE_URLS:
            base_url = getattr(settings, 'PRODUCTION_DOMAIN',
                               'https://oilap-backend-1.onrender.com')

            # Remove leading slash if present
            if pdf_url.startswith('/'):
                pdf_url = pdf_url[1:]

            return f"{base_url}/{pdf_url}"

        return self.pdf_file.url


class Item(models.Model):
    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        related_name='items'
    )
    title = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.title} ({self.quantity} x {self.unit_price})"


class Bilan(models.Model):
    description = models.TextField()
    montant_actif = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        help_text="Montant actif du bilan"
    )
    montant_passif = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        help_text="Montant passif du bilan"
    )
    date_entree = models.DateField(
        help_text="Date d'entrée du bilan"
    )
    date_sortie = models.DateField(
        help_text="Date de sortie du bilan"
    )
    original_image = models.ImageField(
        upload_to='bilans/original/',
        blank=True,
        null=True,
        help_text="Image originale du bilan"
    )
    pdf_file = models.FileField(
        upload_to='bilans/pdf/',
        blank=True,
        null=True,
        help_text="Fichier PDF du bilan"
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='bilans_created',
        limit_choices_to={'role': 'EXPERT_COMPTABLE'}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Bilan'
        verbose_name_plural = 'Bilans'

    def __str__(self):
        return f"Bilan {self.date_entree} - {self.date_sortie}"

    def get_absolute_image_url(self):
        """
        Return absolute URL for original image
        """
        if not self.original_image:
            return None

        # Get the image URL
        image_url = str(self.original_image.url)

        # If it's already a full URL (Cloudinary), return as-is
        if image_url.startswith('http'):
            return image_url

        # For local files in production, construct absolute URL
        if hasattr(settings, 'USE_ABSOLUTE_URLS') and settings.USE_ABSOLUTE_URLS:
            base_url = getattr(settings, 'PRODUCTION_DOMAIN',
                               'https://oilap-backend-1.onrender.com')

            # Remove leading slash if present
            if image_url.startswith('/'):
                image_url = image_url[1:]

            return f"{base_url}/{image_url}"

        return self.original_image.url

    def get_absolute_pdf_url(self):
        """
        Return absolute URL for PDF file
        """
        if not self.pdf_file:
            return None

        # Get the PDF URL
        pdf_url = str(self.pdf_file.url)

        # If it's already a full URL (Cloudinary), return as-is
        if pdf_url.startswith('http'):
            return pdf_url

        # For local files in production, construct absolute URL
        if hasattr(settings, 'USE_ABSOLUTE_URLS') and settings.USE_ABSOLUTE_URLS:
            base_url = getattr(settings, 'PRODUCTION_DOMAIN',
                               'https://oilap-backend-1.onrender.com')

            # Remove leading slash if present
            if pdf_url.startswith('/'):
                pdf_url = pdf_url[1:]

            return f"{base_url}/{pdf_url}"

        return self.pdf_file.url
