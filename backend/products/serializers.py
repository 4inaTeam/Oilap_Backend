from rest_framework import serializers
from .models import Product
from users.models import CustomUser
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ProductSerializer(serializers.ModelSerializer):
    # Champs existants - NOMS CORRIGÉS pour Flutter
    client_name = serializers.CharField(
        source='client.username', read_only=True)
    client_cin = serializers.CharField(
        source='client.cin', read_only=True)
    client = serializers.SlugRelatedField(
        queryset=CustomUser.objects.filter(role='CLIENT'),
        slug_field='id',
        required=True
    )
    created_by = serializers.SlugRelatedField(
        slug_field='username', read_only=True)
    end_time = serializers.DateTimeField(read_only=True)

    # Calculs traditionnels (existants)
    olive_oil_volume = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True)
    oil_efficiency_percentage = serializers.SerializerMethodField()

    total_waste_kg = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True)
    waste_vendus_kg = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True)
    waste_non_vendus_kg = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True)
    waste_vendus_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True)

    waste_percentage = serializers.SerializerMethodField()
    waste_vendus_percentage = serializers.SerializerMethodField()
    waste_price_per_kg = serializers.SerializerMethodField()
    waste_sold_percentage_rule = serializers.SerializerMethodField()

    # NOUVEAUX CHAMPS ML (automatiques)
    ml_predictions = serializers.SerializerMethodField()
    ml_efficiency_metrics = serializers.SerializerMethodField()
    has_ml_predictions = serializers.BooleanField(
        source='ml_prediction_generated', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'quality', 'source', 'price', 'quantity',
            'olive_oil_volume', 'oil_efficiency_percentage',
            'total_waste_kg', 'waste_vendus_kg', 'waste_non_vendus_kg',
            'waste_vendus_price', 'waste_percentage', 'waste_vendus_percentage',
            'waste_price_per_kg', 'waste_sold_percentage_rule',
            'client', 'client_name', 'client_cin', 'status', 'created_by',
            'created_at', 'estimation_time', 'end_time', 'payement',

            'ml_predicted_energy_kwh', 'ml_predicted_water_liters',
            'ml_predicted_employees', 'ml_predicted_processing_time',
            'ml_prediction_generated', 'ml_prediction_timestamp',
            'ml_source_region', 'ml_olive_type',
            'ml_predictions', 'ml_efficiency_metrics', 'has_ml_predictions'
        ]

        read_only_fields = [
            'created_by', 'created_at', 'client_name', 'client_cin', 'end_time',
            'olive_oil_volume', 'oil_efficiency_percentage',
            'total_waste_kg', 'waste_vendus_kg', 'waste_non_vendus_kg',
            'waste_vendus_price', 'waste_percentage', 'waste_vendus_percentage',
            'waste_price_per_kg', 'waste_sold_percentage_rule',
            'ml_predicted_energy_kwh', 'ml_predicted_water_liters',
            'ml_predicted_employees', 'ml_predicted_processing_time',
            'ml_prediction_generated', 'ml_prediction_timestamp',
            'ml_source_region', 'ml_olive_type'
        ]

    def to_representation(self, instance):
        """Custom representation to ensure client field contains CIN"""
        data = super().to_representation(instance)

        if instance.client:
            data['client'] = instance.client.cin or instance.client.username or str(
                instance.client.id)

            data['client_details'] = {
                'cin': instance.client.cin or instance.client.username or str(instance.client.id),
                'username': instance.client.username,
                'id': instance.client.id
            }
        else:
            data['client'] = ''
            data['client_details'] = None

        return data

    def get_oil_efficiency_percentage(self, obj):
        return obj.get_oil_efficiency_percentage()

    def get_waste_percentage(self, obj):
        return obj.get_waste_percentage()

    def get_waste_vendus_percentage(self, obj):
        return obj.get_waste_vendus_percentage()

    def get_waste_price_per_kg(self, obj):
        """Show the price per kg used for this quality"""
        return float(obj.WASTE_PRICE_PER_KG.get(obj.quality, Decimal('4.00')))

    def get_waste_sold_percentage_rule(self, obj):
        """Show the percentage rule used for this quality"""
        percentage = obj.WASTE_SOLD_PERCENTAGE.get(
            obj.quality, Decimal('0.50'))
        return float(percentage * 100)

    # NOUVELLES MÉTHODES ML
    def get_ml_predictions(self, obj):
        """Returns structured ML predictions"""
        if not obj.ml_prediction_generated:
            return {
                'available': False,
                'message': 'ML predictions not generated'
            }

        return {
            'available': True,
            'generated_at': obj.ml_prediction_timestamp,
            'predictions': {
                'energy_kwh': float(obj.ml_predicted_energy_kwh) if obj.ml_predicted_energy_kwh else None,
                'water_liters': float(obj.ml_predicted_water_liters) if obj.ml_predicted_water_liters else None,
                'employees': obj.ml_predicted_employees,
                'processing_time_hours': float(obj.ml_predicted_processing_time) if obj.ml_predicted_processing_time else None,
                'source_region_detected': obj.ml_source_region,
                'olive_type_mapped': obj.ml_olive_type
            }
        }

    def get_ml_efficiency_metrics(self, obj):
        """Calculates ML vs traditional efficiency metrics"""
        if not obj.ml_prediction_generated or not obj.olive_oil_volume:
            return None

        oil_volume = float(obj.olive_oil_volume)
        metrics = {}

        # Energy efficiency
        if obj.ml_predicted_energy_kwh:
            metrics['energy_efficiency'] = {
                'kwh_per_liter_oil': float(obj.ml_predicted_energy_kwh) / oil_volume,
                'kwh_per_kg_olives': float(obj.ml_predicted_energy_kwh) / obj.quantity
            }

        # Water efficiency
        if obj.ml_predicted_water_liters:
            metrics['water_efficiency'] = {
                'liters_water_per_liter_oil': float(obj.ml_predicted_water_liters) / oil_volume,
                'liters_water_per_kg_olives': float(obj.ml_predicted_water_liters) / obj.quantity
            }

        # Labor productivity
        if obj.ml_predicted_employees:
            metrics['labor_efficiency'] = {
                'liters_oil_per_employee': oil_volume / obj.ml_predicted_employees,
                'kg_olives_per_employee': obj.quantity / obj.ml_predicted_employees
            }

        # Time efficiency
        if obj.ml_predicted_processing_time:
            metrics['time_efficiency'] = {
                'liters_oil_per_hour': oil_volume / float(obj.ml_predicted_processing_time),
                'kg_olives_per_hour': obj.quantity / float(obj.ml_predicted_processing_time)
            }

        return metrics

    # Validations existantes (inchangées)
    def validate_client(self, value):
        if value.role != 'CLIENT':
            raise serializers.ValidationError(
                "The client must have the 'CLIENT' role.")
        return value

    def validate_estimation_time(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Estimation time must be greater than 0 minutes.")
        return value

    def create(self, validated_data):
        """Création avec prédictions ML automatiques"""
        validated_data['created_by'] = self.context['request'].user
        if 'estimation_time' not in validated_data:
            validated_data['estimation_time'] = validated_data.get(
                'quantity', 1) * 30

        logger.info(
            "Creating product with automatic calculations + ML predictions")

        # Le produit sera créé avec prédictions ML automatiques dans save()
        product = super().create(validated_data)

        # Log du résultat
        if product.ml_prediction_generated:
            logger.info(f"✅ Product {product.id} created with ML: "
                        f"Energy={product.ml_predicted_energy_kwh}kWh, "
                        f"Employees={product.ml_predicted_employees}")
        else:
            logger.warning(
                f"⚠️ Product {product.id} created without ML predictions")

        return product

    def update(self, instance, validated_data):
        """Mise à jour avec régénération ML automatique si nécessaire"""
        logger.info(
            f"Updating product {instance.id} - ML will be regenerated if needed")

        old_status = instance.status
        new_status = validated_data.get('status', old_status)

        # Logique existante pour estimation_time et end_time
        if 'estimation_time' in validated_data and validated_data['estimation_time'] != instance.estimation_time:
            instance.end_time = None
            logger.info(
                f"Estimation time changed, resetting end_time for product {instance.id}")

        if old_status != 'done' and new_status == 'done':
            validated_data['end_time'] = timezone.now()
            logger.info(
                f"Status changed to 'done', setting end_time to now for product {instance.id}")

        # Vérifier si les champs affectant ML ont changé
        ml_affecting_fields = ['source', 'quantity', 'quality']
        ml_fields_changed = any(
            field in validated_data and validated_data[field] != getattr(
                instance, field)
            for field in ml_affecting_fields
        )

        # Mise à jour
        updated_instance = super().update(instance, validated_data)

        # Log des résultats (existants)
        logger.info(
            f"Product {updated_instance.id} updated with automatic calculations:")
        logger.info(f"  Quality: {updated_instance.quality}")
        logger.info(f"  Quantity: {updated_instance.quantity}kg")
        logger.info(f"  Source: {updated_instance.source}")

        # Log ML
        if ml_fields_changed and updated_instance.ml_prediction_generated:
            logger.info(f"🤖 ML predictions updated: "
                        f"Energy={updated_instance.ml_predicted_energy_kwh}kWh, "
                        f"Employees={updated_instance.ml_predicted_employees}")

        return updated_instance


class ProductSummarySerializer(serializers.ModelSerializer):
    """Serializer simplifié avec résumé ML"""
    client_name = serializers.CharField(
        source='client.username', read_only=True)
    client_cin = serializers.CharField(
        source='client.cin', read_only=True)
    waste_vendus_percentage = serializers.SerializerMethodField()
    total_revenue = serializers.SerializerMethodField()

    # NOUVEAU : Résumé ML
    ml_summary = serializers.SerializerMethodField()
    has_ml_predictions = serializers.BooleanField(
        source='ml_prediction_generated', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'quality', 'quantity', 'price', 'status', 'source',  # ✅ 'source' inclus
            'client_name', 'client_cin', 'total_waste_kg', 'waste_vendus_kg',
            'waste_vendus_price', 'waste_vendus_percentage', 'total_revenue',
            'created_at', 'end_time',
            # Nouveaux champs ML
            'has_ml_predictions', 'ml_summary'
        ]

    def get_waste_vendus_percentage(self, obj):
        return obj.get_waste_vendus_percentage()

    def get_total_revenue(self, obj):
        """Total revenue from olive oil + waste"""
        oil_revenue = obj.price or Decimal('0')
        waste_revenue = obj.waste_vendus_price or Decimal('0')
        return float(oil_revenue + waste_revenue)

    def get_ml_summary(self, obj):
        """Compact ML predictions summary"""
        if not obj.ml_prediction_generated:
            return {'available': False}

        return {
            'available': True,
            'energy_kwh': float(obj.ml_predicted_energy_kwh) if obj.ml_predicted_energy_kwh else None,
            'employees': obj.ml_predicted_employees,
            'processing_hours': float(obj.ml_predicted_processing_time) if obj.ml_predicted_processing_time else None,
            'region': obj.ml_source_region
        }


class ProductCreateSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour création avec ML automatique"""

    class Meta:
        model = Product
        fields = ['source', 'quantity', 'quality',
                  'client']  # ✅ 'source' (pas 'origine')

    def validate_client(self, value):
        """Validation du client"""
        if hasattr(value, 'role') and value.role != 'CLIENT':
            raise serializers.ValidationError(
                "Selected user is not a client")
        return value

    def create(self, validated_data):
        """Création avec ML automatique"""
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user

        # Le produit sera créé avec toutes les prédictions automatiques
        product = Product.objects.create(**validated_data)

        logger.info(f"Product {product.id} created with automatic ML: "
                    f"{product.quantity}kg {product.quality} from {product.source}")

        return product


class ProductMLStatusSerializer(serializers.ModelSerializer):
    """Serializer pour le statut ML des produits"""

    ml_predictions = serializers.SerializerMethodField()
    traditional_calculations = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'quality', 'source', 'quantity', 'status',
            'ml_prediction_generated', 'ml_prediction_timestamp',
            'ml_predictions', 'traditional_calculations'
        ]

    def get_ml_predictions(self, obj):
        """ML predictions for status"""
        if not obj.ml_prediction_generated:
            return None

        return {
            'energy_kwh': float(obj.ml_predicted_energy_kwh) if obj.ml_predicted_energy_kwh else None,
            'water_liters': float(obj.ml_predicted_water_liters) if obj.ml_predicted_water_liters else None,
            'employees': obj.ml_predicted_employees,
            'processing_time_hours': float(obj.ml_predicted_processing_time) if obj.ml_predicted_processing_time else None,
            'region': obj.ml_source_region,
            'generated_at': obj.ml_prediction_timestamp
        }

    def get_traditional_calculations(self, obj):
        """Calculs traditionnels pour comparaison"""
        return {
            'oil_volume_liters': float(obj.olive_oil_volume) if obj.olive_oil_volume else None,
            'extraction_efficiency_percent': obj.get_oil_efficiency_percentage(),
            'waste_sold_kg': float(obj.waste_vendus_kg) if obj.waste_vendus_kg else None,
            'waste_revenue_dt': float(obj.waste_vendus_price) if obj.waste_vendus_price else None,
            'total_revenue_dt': float(obj.price) if obj.price else None
        }
