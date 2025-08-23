from django.db import models
from users.models import CustomUser
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Product(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('doing', 'Doing'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ]
    PAYEMENT_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]
    QUALITY_CHOICES = [
        ('excellente', 'Excellente'),
        ('bonne', 'Bonne'),
        ('moyenne', 'Moyenne'),
        ('mauvaise', 'Mauvaise'),
    ]

    QUALITY_PRICE_MAP = {
        'excellente': Decimal('15'),
        'bonne': Decimal('12'),
        'moyenne': Decimal('10'),
        'mauvaise': Decimal('8'),
    }

    OLIVE_OIL_YIELD_MAP = {
        'excellente': Decimal('0.20'),
        'bonne': Decimal('0.18'),
        'moyenne': Decimal('0.17'),
        'mauvaise': Decimal('0.15'),
    }

    WASTE_COEFFICIENTS = {
        'excellente': Decimal('0.82'),
        'bonne': Decimal('0.835'),
        'moyenne': Decimal('0.85'),
        'mauvaise': Decimal('0.875'),
    }

    WASTE_SOLD_PERCENTAGE = {
        'excellente': Decimal('0.75'),
        'bonne': Decimal('0.65'),
        'moyenne': Decimal('0.50'),
        'mauvaise': Decimal('0.30'),
    }

    WASTE_PRICE_PER_KG = {
        'excellente': Decimal('5.50'),
        'bonne': Decimal('4.80'),
        'moyenne': Decimal('4.00'),
        'mauvaise': Decimal('3.20'),
    }

    quality = models.CharField(
        max_length=10, choices=QUALITY_CHOICES, default='moyenne')
    source = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    quantity = models.PositiveIntegerField(
        default=1, help_text="Quantity in kg")

    olive_oil_volume = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text="Calculated olive oil volume in liters"
    )

    total_waste_kg = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text="Total waste in kg"
    )

    waste_vendus_kg = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text="Automatically calculated sold waste in kg"
    )

    waste_non_vendus_kg = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text="Automatically calculated unsold waste in kg"
    )

    waste_vendus_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Automatically calculated revenue from sold waste in DT"
    )

    # NOUVEAUX CHAMPS ML - Prédictions automatiques
    ml_predicted_energy_kwh = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="ML predicted energy consumption in kWh"
    )

    ml_predicted_water_liters = models.DecimalField(
        max_digits=10, decimal_places=0, null=True, blank=True,
        help_text="ML predicted water consumption in liters"
    )

    ml_predicted_employees = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="ML predicted number of employees needed"
    )

    ml_predicted_processing_time = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="ML predicted processing time in hours"
    )

    ml_prediction_generated = models.BooleanField(
        default=False,
        help_text="Whether ML predictions have been generated"
    )

    ml_prediction_timestamp = models.DateTimeField(
        null=True, blank=True,
        help_text="When ML predictions were last generated"
    )

    ml_source_region = models.CharField(
        max_length=20, blank=True, null=True,
        help_text="ML detected source region"
    )

    ml_olive_type = models.CharField(
        max_length=20, blank=True, null=True,
        help_text="ML mapped olive type"
    )

    payement = models.CharField(
        max_length=10, choices=PAYEMENT_CHOICES, default='unpaid')
    client = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='products',
        limit_choices_to={'role': 'CLIENT'}
    )
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='created_products'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending')
    estimation_time = models.PositiveIntegerField(
        default=15, help_text="Estimated processing time in minutes"
    )
    end_time = models.DateTimeField(null=True, blank=True)

    facture = models.ForeignKey(
        'factures.Facture', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='products'
    )

    def calculate_olive_oil_volume(self):
        """Calculate the expected olive oil volume based on olive quality and quantity"""
        yield_per_kg = self.OLIVE_OIL_YIELD_MAP.get(
            self.quality, Decimal('0.17'))
        return Decimal(str(self.quantity)) * yield_per_kg

    def get_oil_efficiency_percentage(self):
        """Get the oil extraction efficiency as a percentage"""
        yield_per_kg = self.OLIVE_OIL_YIELD_MAP.get(
            self.quality, Decimal('0.17'))
        return float(yield_per_kg * Decimal('100'))

    def calculate_total_waste(self):
        """Calculate total waste based on olive quality and quantity"""
        waste_coefficient = self.WASTE_COEFFICIENTS.get(
            self.quality, Decimal('0.85'))
        return Decimal(str(self.quantity)) * waste_coefficient

    def calculate_waste_vendus_automatically(self):
        """Automatically calculate how much waste is sold based on quality"""
        if not self.total_waste_kg:
            return Decimal('0')

        sold_percentage = self.WASTE_SOLD_PERCENTAGE.get(
            self.quality, Decimal('0.50'))
        return self.total_waste_kg * sold_percentage

    def calculate_waste_vendus_price_automatically(self):
        """Automatically calculate waste vendus price"""
        if not self.waste_vendus_kg:
            return Decimal('0')

        price_per_kg = self.WASTE_PRICE_PER_KG.get(
            self.quality, Decimal('4.00'))
        return self.waste_vendus_kg * price_per_kg

    def calculate_waste_non_vendus(self):
        """Calculate unsold waste"""
        if self.total_waste_kg and self.waste_vendus_kg:
            return self.total_waste_kg - self.waste_vendus_kg
        return Decimal('0')

    def get_waste_percentage(self):
        """Get waste percentage from total olives"""
        if self.quantity > 0 and self.total_waste_kg:
            percentage = (self.total_waste_kg /
                          Decimal(str(self.quantity))) * Decimal('100')
            return float(percentage)
        return 0.0

    def get_waste_vendus_percentage(self):
        """Get percentage of sold waste"""
        if self.total_waste_kg and self.total_waste_kg > 0 and self.waste_vendus_kg:
            percentage = (self.waste_vendus_kg /
                          self.total_waste_kg) * Decimal('100')
            return float(percentage)
        return 0.0

    # NOUVELLES MÉTHODES ML
    def _should_generate_ml_predictions(self):
        """Détermine si les prédictions ML doivent être générées"""
        # Générer si pas encore fait
        if not self.ml_prediction_generated:
            return True

        # Régénérer si les données clés ont changé
        return False

    def _generate_ml_predictions(self):
        """Génère automatiquement les prédictions ML - VERSION CORRIGÉE"""
        try:
            from .ml_service import ml_prediction_service

            if not ml_prediction_service.is_loaded:
                logger.warning(
                    f"Modèles ML non chargés pour le produit {self.id}")
                return False

            # Générer les prédictions - PARAMÈTRES CORRIGÉS
            ml_result = ml_prediction_service.auto_predict(
                source=self.source or "Centre",  # ✅ CORRIGÉ: source= au lieu d'origine=
                quantity=self.quantity,
                quality=self.quality
            )

            if ml_result:
                # Stocker les prédictions
                self.ml_predicted_energy_kwh = Decimal(
                    str(ml_result['energy_kwh']))
                self.ml_predicted_water_liters = Decimal(
                    str(ml_result['water_liters']))
                self.ml_predicted_employees = ml_result['employees']
                self.ml_predicted_processing_time = Decimal(
                    str(ml_result['processing_time_hours']))
                self.ml_source_region = ml_result['source_region']
                self.ml_olive_type = ml_result['olive_type_ml']
                self.ml_prediction_generated = True
                self.ml_prediction_timestamp = timezone.now()

                # Mettre à jour le temps d'estimation basé sur ML
                ml_time_minutes = float(
                    ml_result['processing_time_hours']) * 60
                self.estimation_time = max(15, int(ml_time_minutes))

                logger.info(
                    f"✅ Prédictions ML générées automatiquement pour produit {self.id}")
                return True
            else:
                logger.warning(
                    f"⚠️ Échec génération prédictions ML pour produit {self.id}")
                return False

        except Exception as e:
            logger.error(
                f"❌ Erreur génération prédictions ML pour produit {self.id}: {e}")
            return False

    def get_ml_predictions_summary(self):
        """Retourne un résumé des prédictions ML"""
        if not self.ml_prediction_generated:
            return {
                'available': False,
                'message': 'ML predictions not generated'
            }

        return {
            'available': True,
            'generated_at': self.ml_prediction_timestamp,
            'predictions': {
                'energy_kwh': float(self.ml_predicted_energy_kwh) if self.ml_predicted_energy_kwh else None,
                'water_liters': float(self.ml_predicted_water_liters) if self.ml_predicted_water_liters else None,
                'employees': self.ml_predicted_employees,
                'processing_time_hours': float(self.ml_predicted_processing_time) if self.ml_predicted_processing_time else None,
                'source_region': self.ml_source_region,
                'olive_type_mapped': self.ml_olive_type
            },
            'efficiency_metrics': {
                'energy_per_liter': (float(self.ml_predicted_energy_kwh) / float(self.olive_oil_volume)) if (self.ml_predicted_energy_kwh and self.olive_oil_volume) else None,
                'water_per_liter': (float(self.ml_predicted_water_liters) / float(self.olive_oil_volume)) if (self.ml_predicted_water_liters and self.olive_oil_volume) else None,
                'liters_per_employee': (float(self.olive_oil_volume) / self.ml_predicted_employees) if (self.olive_oil_volume and self.ml_predicted_employees) else None
            }
        }

    def save(self, *args, **kwargs):
        """Sauvegarde avec génération automatique des prédictions ML - VERSION CORRIGÉE"""
        logger.info(
            f"Sauvegarde produit {self.id if self.id else 'nouveau'} - {self.quantity}kg {self.quality} de {self.source}")

        # Calculs traditionnels (inchangés)
        base_price = self.QUALITY_PRICE_MAP.get(self.quality, Decimal('10'))
        self.price = base_price * Decimal(str(self.quantity))

        self.olive_oil_volume = self.calculate_olive_oil_volume()
        self.total_waste_kg = self.calculate_total_waste()
        self.waste_vendus_kg = self.calculate_waste_vendus_automatically()
        self.waste_vendus_price = self.calculate_waste_vendus_price_automatically()
        self.waste_non_vendus_kg = self.calculate_waste_non_vendus()

        # Génération automatique des prédictions ML
        if self._should_generate_ml_predictions():
            logger.info(
                f"🤖 Génération prédictions ML pour {self.quantity}kg {self.quality} de {self.source}")
            self._generate_ml_predictions()

        # Calcul du temps de fin
        if not self.end_time:
            start_time = self.created_at if self.created_at else timezone.now()
            self.end_time = start_time + \
                timedelta(minutes=self.estimation_time)

        logger.info(f"✅ Produit prêt: Prix={self.price}DT, Huile={self.olive_oil_volume}L, "
                    f"ML_Énergie={self.ml_predicted_energy_kwh}kWh, "
                    f"ML_Employés={self.ml_predicted_employees}")

        super().save(*args, **kwargs)

    def __str__(self):
        ml_info = f"ML:" if self.ml_prediction_generated else "ML:"
        return f"Product {self.id} - {self.get_status_display()} ({self.quantity}kg → {self.olive_oil_volume}L) {ml_info}"

    class Meta:
        ordering = ['end_time']
