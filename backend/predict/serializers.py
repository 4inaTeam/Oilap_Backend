from rest_framework import serializers


class PredictionRequestSerializer(serializers.Serializer):
    """
    Base serializer for prediction requests
    """
    quantities = serializers.CharField(
        required=False,
        help_text="Comma-separated list of quantities in tons (e.g., '10,25,50')"
    )
    use_real_data = serializers.BooleanField(
        default=False,
        help_text="If true, use quantities from existing products"
    )
    sources = serializers.CharField(
        required=False,
        help_text="Comma-separated list of sources to include in analysis"
    )

    def validate_quantities(self, value):
        """Validate quantities format"""
        if value:
            try:
                quantities = [float(q.strip()) for q in value.split(',')]
                if any(q <= 0 for q in quantities):
                    raise serializers.ValidationError(
                        "All quantities must be positive numbers"
                    )
                if len(quantities) > 20:
                    raise serializers.ValidationError(
                        "Maximum 20 quantities allowed"
                    )
                return quantities
            except (ValueError, AttributeError):
                raise serializers.ValidationError(
                    "Invalid quantities format. Use comma-separated numbers."
                )
        return None


class EnergyPredictionResponseSerializer(serializers.Serializer):
    """
    Serializer for energy prediction responses
    """
    predictions = serializers.DictField()
    by_source = serializers.DictField()
    by_quantity = serializers.DictField()
    success = serializers.BooleanField()
    metadata = serializers.DictField(required=False)
    real_data_comparison = serializers.DictField(required=False)


class WaterPredictionResponseSerializer(serializers.Serializer):
    """
    Serializer for water prediction responses
    """
    predictions = serializers.DictField()
    by_condition = serializers.DictField()
    by_quantity = serializers.DictField()
    success = serializers.BooleanField()
    metadata = serializers.DictField(required=False)
    real_data_comparison = serializers.DictField(required=False)


class EmployeePredictionResponseSerializer(serializers.Serializer):
    """
    Serializer for employee prediction responses
    """
    predictions = serializers.DictField()
    by_source = serializers.DictField()
    by_quantity = serializers.DictField()
    efficiency_analysis = serializers.DictField()
    success = serializers.BooleanField()
    metadata = serializers.DictField(required=False)
    real_data_comparison = serializers.DictField(required=False)


class AllTargetsPredictionResponseSerializer(serializers.Serializer):
    """
    Serializer for all targets prediction responses
    """
    main_targets = serializers.DictField()
    additional_targets = serializers.DictField()
    correlations = serializers.DictField()
    scenarios_analyzed = serializers.IntegerField()
    success = serializers.BooleanField()
    metadata = serializers.DictField(required=False)
    real_data_comparison = serializers.DictField(required=False)


class QualityPredictionResponseSerializer(serializers.Serializer):
    """
    Serializer for quality prediction responses
    """
    quality_predictions = serializers.DictField()
    by_olive_type = serializers.DictField()
    by_source = serializers.DictField()
    quality_distribution = serializers.DictField()
    success = serializers.BooleanField()
    metadata = serializers.DictField(required=False)
    real_data_comparison = serializers.DictField(required=False)


class SeasonalAnalysisResponseSerializer(serializers.Serializer):
    """
    Serializer for seasonal analysis responses
    """
    seasonal_patterns = serializers.DictField()
    recommendations = serializers.DictField()
    efficiency_by_season = serializers.DictField()
    success = serializers.BooleanField()
    metadata = serializers.DictField(required=False)
    real_seasonal_data = serializers.DictField(required=False)


class PredictionStatusResponseSerializer(serializers.Serializer):
    """
    Serializer for prediction service status
    """
    is_loaded = serializers.BooleanField()
    models_available = serializers.DictField()
    categories = serializers.DictField()
    model_info = serializers.DictField()
    timestamp = serializers.DateTimeField()
    user = serializers.CharField()
    cache_info = serializers.DictField()
