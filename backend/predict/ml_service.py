import os
import pickle
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum, Avg, Count
import logging
import warnings

# Suppress sklearn warnings about feature names
warnings.filterwarnings(
    "ignore", message="X does not have valid feature names")

logger = logging.getLogger(__name__)


def clean_nan_values(data):
    """
    Recursively clean NaN values from data structures
    Replace NaN with None or 0 depending on context
    """
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            cleaned[key] = clean_nan_values(value)
        return cleaned
    elif isinstance(data, list):
        return [clean_nan_values(item) for item in data]
    elif isinstance(data, (float, np.float64, np.float32)):
        if np.isnan(data) or np.isinf(data):
            return 0.0
        return float(data)
    elif isinstance(data, (int, np.int64, np.int32)):
        if np.isnan(data) or np.isinf(data):
            return 0
        return int(data)
    else:
        return data


def safe_divide(numerator, denominator, default=0.0):
    """Safely divide two numbers, handling division by zero and NaN values"""
    try:
        if denominator == 0 or np.isnan(denominator) or np.isnan(numerator):
            return default
        result = numerator / denominator
        if np.isnan(result) or np.isinf(result):
            return default
        return float(result)
    except (ZeroDivisionError, TypeError, ValueError):
        return default


def safe_mean(values, default=0.0):
    """Safely calculate mean, handling empty arrays and NaN values"""
    try:
        if len(values) == 0:
            return default
        # Remove NaN and infinite values
        clean_values = values[~(np.isnan(values) | np.isinf(values))]
        if len(clean_values) == 0:
            return default
        result = float(np.mean(clean_values))
        if np.isnan(result) or np.isinf(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


class GlobalPredictionService:
    """
    Enhanced Global ML service using the enhanced cost prediction models
    """

    def __init__(self):
        self.cost_model = None
        self.all_targets_model = None
        self.scaler = None
        self.encoders = None
        self.model_info = None
        self.is_loaded = False
        self._load_enhanced_models()

    def _load_enhanced_models(self):
        """Load the enhanced models with cost prediction"""
        try:
            # Use the enhanced models directory
            models_dir = os.path.join(settings.BASE_DIR, 'enhanced_models')

            if not os.path.exists(models_dir):
                logger.warning(
                    f"Enhanced models directory not found: {models_dir}")
                return

            # Load cost prediction model
            cost_model_path = os.path.join(
                models_dir, 'cost_prediction_model.joblib')
            if os.path.exists(cost_model_path):
                self.cost_model = joblib.load(cost_model_path)
                logger.info("✅ Cost prediction model loaded")
            else:
                logger.warning(f"Cost model not found: {cost_model_path}")

            # Load all targets model
            all_model_path = os.path.join(
                models_dir, 'all_targets_model.joblib')
            if os.path.exists(all_model_path):
                self.all_targets_model = joblib.load(all_model_path)
                logger.info("✅ All targets model loaded")

            # Load enhanced scaler
            scaler_path = os.path.join(models_dir, 'cost_scaler.joblib')
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
                logger.info("✅ Enhanced scaler loaded")

            # Load enhanced encoders
            encoders_path = os.path.join(models_dir, 'encoders.pkl')
            if os.path.exists(encoders_path):
                with open(encoders_path, 'rb') as f:
                    self.encoders = pickle.load(f)
                logger.info("✅ Enhanced encoders loaded")

            # Load enhanced model info
            info_path = os.path.join(models_dir, 'enhanced_model_info.pkl')
            if os.path.exists(info_path):
                with open(info_path, 'rb') as f:
                    self.model_info = pickle.load(f)
                logger.info("✅ Enhanced model info loaded")

            # Check if all components are loaded
            if all([self.cost_model, self.scaler, self.encoders]):
                self.is_loaded = True
                logger.info(
                    "🎯 Global Prediction Service with enhanced cost prediction loaded successfully")

                if self.model_info:
                    logger.info(
                        f"📊 Cost model performance: R² = {self.model_info.get('cost_r2_score', 'N/A'):.3f}")
            else:
                logger.error("❌ Failed to load enhanced models")
                self.is_loaded = False

        except Exception as e:
            logger.error(f"❌ Error loading enhanced models: {e}")
            self.is_loaded = False

    def _map_quality_to_olive_type(self, quality):
        """Map quality to olive type for ML - matches the training data"""
        if not quality:
            return 'Chemlali'

        quality_lower = str(quality).lower().strip()

        # Map based on the actual training data patterns
        quality_mapping = {
            'excellente': 'Chétoui',    # Best quality -> premium variety
            'excellent': 'Chétoui',
            'bonne': 'Oueslati',        # Good quality -> good variety
            'good': 'Oueslati',
            'moyenne': 'Chemlali',      # Average quality -> most common variety
            'average': 'Chemlali',
            'mauvaise': 'Gerboui',      # Poor quality -> lower grade variety
            'poor': 'Gerboui',
            'bad': 'Gerboui'
        }
        return quality_mapping.get(quality_lower, 'Chemlali')

    def _map_source_to_region(self, source):
        """Map source to ML regions - matches training data"""
        if not source:
            return 'Centre'

        source_lower = source.lower().strip()

        # Direct mapping if exact match exists in encoders
        available_regions = list(
            self.encoders['source'].classes_) if self.encoders else []

        # Try direct match first
        for region in available_regions:
            if source_lower == region.lower():
                return region

        # Fallback mapping based on keywords
        region_keywords = {
            'Sfax': ['sfax'],
            'Nord': ['tunis', 'bizerte', 'nabeul', 'ariana', 'ben arous', 'manouba',
                     'beja', 'jendouba', 'kef', 'siliana', 'nord', 'north'],
            'Sud': ['gabes', 'medenine', 'tataouine', 'kebili', 'tozeur', 'gafsa',
                    'sud', 'south'],
            'Centre': ['sousse', 'monastir', 'mahdia', 'kairouan', 'kasserine',
                       'sidi bouzid', 'zaghouan', 'centre', 'center']
        }

        for region, keywords in region_keywords.items():
            if region in available_regions and any(keyword in source_lower for keyword in keywords):
                return region

        return 'Centre'  # Default fallback

    def _get_default_mappings(self):
        """Get default values for missing categorical features"""
        defaults = {}

        if self.encoders:
            # Use the most common values from training or reasonable defaults
            defaults = {
                'condition': 'Rainfed',      # Most common condition
                'olive_size': 'Medium',      # Default size
                'press_method': 'Méthode en continu'  # Most efficient method
            }

            # Validate defaults exist in encoders, otherwise use first available
            for key, default_value in defaults.items():
                if key in self.encoders:
                    available_classes = list(self.encoders[key].classes_)
                    if default_value not in available_classes and available_classes:
                        defaults[key] = available_classes[0]
                        logger.warning(
                            f"Default {key} '{default_value}' not found, using '{available_classes[0]}'")

        return defaults

    def predict_costs_and_production(self, source, quantity, quality):
        """
        Direct cost and production prediction - matches the training script interface
        This is the main method that was missing from the original implementation

        Parameters:
        - source: Source region (string)
        - quantity: Quantity in kg (will be converted to tons)
        - quality: Quality level (string)

        Returns:
        - Dictionary with costs and production predictions
        """
        if not self.is_loaded:
            logger.error("Models not loaded for predict_costs_and_production")
            return None

        try:
            # Input validation and conversion
            if quantity is None or quantity <= 0:
                logger.error(f"Invalid quantity: {quantity}")
                return None

            # Convert kg to tons for model input (matches training data)
            quantity_tons = float(quantity) / 1000.0

            # Map inputs to model categories
            region = self._map_source_to_region(source)
            olive_type = self._map_quality_to_olive_type(quality)

            # Get default mappings
            defaults = self._get_default_mappings()
            condition = defaults.get('condition', 'Rainfed')
            olive_size = defaults.get('olive_size', 'Medium')
            press_method = defaults.get('press_method', 'Méthode en continu')

            logger.info(
                f"Mapping: source='{source}' -> region='{region}', quality='{quality}' -> olive_type='{olive_type}'")

            # Check if all mapped values exist in encoders
            required_mappings = {
                'source': region,
                'olive_type': olive_type,
                'condition': condition,
                'size': olive_size,
                'press_method': press_method
            }

            for encoder_key, mapped_value in required_mappings.items():
                if encoder_key not in self.encoders:
                    logger.error(f"Encoder '{encoder_key}' not found")
                    return None

                available_classes = list(self.encoders[encoder_key].classes_)
                if mapped_value not in available_classes:
                    logger.error(
                        f"Value '{mapped_value}' not found in encoder '{encoder_key}'. Available: {available_classes}")
                    # Try to use the first available class as fallback
                    if available_classes:
                        required_mappings[encoder_key] = available_classes[0]
                        logger.warning(
                            f"Using fallback value '{available_classes[0]}' for '{encoder_key}'")
                    else:
                        return None

            # Prepare features array (matches training script order)
            # Input features: ['Source_Encoded', 'Olive_Type_Encoded', 'Condition_Encoded',
            #                  'Olive_Size_Encoded', 'Press_Method_Encoded', 'Quantity_Olives_Tons']
            try:
                features = np.array([[
                    self.encoders['source'].transform(
                        [required_mappings['source']])[0],
                    self.encoders['olive_type'].transform(
                        [required_mappings['olive_type']])[0],
                    self.encoders['condition'].transform(
                        [required_mappings['condition']])[0],
                    self.encoders['size'].transform(
                        [required_mappings['size']])[0],
                    self.encoders['press_method'].transform(
                        [required_mappings['press_method']])[0],
                    quantity_tons
                ]])

                logger.info(f"Features array created: {features}")

            except Exception as e:
                logger.error(f"Error creating features array: {e}")
                return None

            # Scale features
            try:
                features_scaled = self.scaler.transform(features)
                logger.info(f"Features scaled successfully")
            except Exception as e:
                logger.error(f"Error scaling features: {e}")
                return None

            results = {}

            # Predict costs using cost model
            if self.cost_model:
                try:
                    cost_predictions = self.cost_model.predict(features_scaled)[
                        0]

                    # Cost targets: ['Electricity_Cost_TND', 'Water_Cost_TND', 'Total_Labor_Cost_TND']
                    results['costs'] = {
                        'electricity_cost_tnd': float(cost_predictions[0]),
                        'water_cost_tnd': float(cost_predictions[1]),
                        'labor_cost_tnd': float(cost_predictions[2]),
                        'total_operational_cost_tnd': float(sum(cost_predictions))
                    }
                    logger.info(
                        f"Cost predictions generated: {results['costs']}")
                except Exception as e:
                    logger.error(f"Error predicting costs: {e}")
                    results['costs'] = {
                        'electricity_cost_tnd': 0.0,
                        'water_cost_tnd': 0.0,
                        'labor_cost_tnd': 0.0,
                        'total_operational_cost_tnd': 0.0
                    }

            # Predict production using all targets model
            if self.all_targets_model:
                try:
                    all_predictions = self.all_targets_model.predict(features_scaled)[
                        0]

                    # All targets: cost_targets + production_targets
                    # production_targets: ['Oil_Quality_Score', 'Oil_Quantity_Tons', 'Processing_Time_Hours',
                    #                     'Total_Energy_Consumption_kWh', 'Water_Consumption_Liters', 'Total_Employees']
                    # So indices 3, 4, 5, 6, 7, 8 are the production targets

                    results['production'] = {
                        # Oil_Quality_Score
                        'oil_quality_score': float(all_predictions[3]),
                        # Oil_Quantity_Tons
                        'oil_quantity_tons': float(all_predictions[4]),
                        # Processing_Time_Hours
                        'processing_time_hours': float(all_predictions[5]),
                        # Total_Energy_Consumption_kWh
                        'energy_consumption_kwh': float(all_predictions[6]),
                        # Water_Consumption_Liters
                        'water_consumption_liters': float(all_predictions[7]),
                        # Total_Employees
                        'total_employees': int(round(all_predictions[8]))
                    }

                    # Add oil quantity in liters for compatibility
                    results['production']['oil_quantity_liters'] = results['production']['oil_quantity_tons'] * 1000

                    logger.info(
                        f"Production predictions generated: {results['production']}")
                except Exception as e:
                    logger.error(f"Error predicting production: {e}")
                    results['production'] = {
                        'oil_quality_score': 0.0,
                        'oil_quantity_tons': 0.0,
                        'processing_time_hours': 0.0,
                        'energy_consumption_kwh': 0.0,
                        'water_consumption_liters': 0.0,
                        'total_employees': 0,
                        'oil_quantity_liters': 0.0
                    }

            # Add mapping info for reference
            results['mapping_info'] = {
                'source_region': region,
                'olive_type_ml': olive_type,
                'press_method': press_method,
                'condition': condition,
                'olive_size': olive_size,
                'quantity_tons_input': quantity_tons
            }

            # Clean NaN values and return
            clean_results = clean_nan_values(results)
            logger.info("predict_costs_and_production completed successfully")
            return clean_results

        except Exception as e:
            logger.error(
                f"Error in predict_costs_and_production: {e}", exc_info=True)
            return None

    def _prepare_prediction_matrix(self, quantities_range=None, sources=None, qualities=None):
        """Prepare prediction matrix for different scenarios"""
        if not self.is_loaded:
            return None, None

        try:
            # Default parameters
            if quantities_range is None:
                quantities_range = [10, 25, 50, 100, 200, 500, 1000]  # tons

            if sources is None:
                sources = ['Nord', 'Centre', 'Sud', 'Sfax']

            if qualities is None:
                qualities = ['excellente', 'bonne', 'moyenne', 'mauvaise']

            scenarios = []
            scenario_descriptions = []

            # Get defaults
            defaults = self._get_default_mappings()

            # Create scenarios for different combinations
            for source in sources:
                for quality in qualities:
                    # Map to ML categories
                    region = self._map_source_to_region(source)
                    olive_type = self._map_quality_to_olive_type(quality)

                    # Check if mapped values exist in encoders
                    if (region in self.encoders['source'].classes_ and
                            olive_type in self.encoders['olive_type'].classes_):

                        for quantity in quantities_range:
                            # Convert kg to tons if needed
                            quantity_tons = quantity / 1000 if quantity > 100 else quantity

                            scenario = [
                                self.encoders['source'].transform([region])[0],
                                self.encoders['olive_type'].transform([olive_type])[
                                    0],
                                self.encoders['condition'].transform(
                                    [defaults['condition']])[0],
                                self.encoders['size'].transform(
                                    [defaults['olive_size']])[0],
                                self.encoders['press_method'].transform(
                                    [defaults['press_method']])[0],
                                quantity_tons
                            ]
                            scenarios.append(scenario)
                            scenario_descriptions.append({
                                'source': source,
                                'region': region,
                                'quality': quality,
                                'olive_type': olive_type,
                                'quantity_tons': quantity_tons
                            })

            return np.array(scenarios), scenario_descriptions

        except Exception as e:
            logger.error(f"Error preparing prediction matrix: {e}")
            return None, None

    def predict_energy_consumption(self, scenarios=None, quantities_range=None):
        """Enhanced energy consumption prediction"""
        if not self.is_loaded:
            return {'error': 'Enhanced models not loaded', 'success': False}

        cache_key = f"enhanced_predict_energy_{hash(str(quantities_range))}"
        cached = cache.get(cache_key)
        if cached:
            return clean_nan_values(cached)

        try:
            scenarios_matrix, descriptions = self._prepare_prediction_matrix(
                quantities_range)
            if scenarios_matrix is None:
                return {'error': 'Failed to prepare scenarios', 'success': False}

            scenarios_scaled = self.scaler.transform(scenarios_matrix)

            # Get all predictions
            all_predictions = self.all_targets_model.predict(scenarios_scaled)

            # Extract energy consumption (index 6 in all_targets: after 3 costs + quality + oil_quantity + processing_time)
            energy_predictions = all_predictions[:, 6]
            energy_predictions = np.where(
                np.isnan(energy_predictions) | np.isinf(energy_predictions),
                0,
                energy_predictions
            )

            result = {
                'predictions': {
                    'total_scenarios': len(energy_predictions),
                    'energy_kwh': {
                        'min': float(np.min(energy_predictions)) if len(energy_predictions) > 0 else 0.0,
                        'max': float(np.max(energy_predictions)) if len(energy_predictions) > 0 else 0.0,
                        'mean': safe_mean(energy_predictions, 0.0),
                        'std': float(np.std(energy_predictions)) if len(energy_predictions) > 0 else 0.0,
                        'median': float(np.median(energy_predictions)) if len(energy_predictions) > 0 else 0.0,
                        'total_estimated': float(np.sum(energy_predictions))
                    }
                },
                'by_source': {},
                'by_quality': {},
                'by_quantity': {},
                'success': True
            }

            # Analysis by source
            for source in ['Nord', 'Centre', 'Sud', 'Sfax']:
                source_mask = [d['source'] == source for d in descriptions]
                if any(source_mask):
                    source_energies = energy_predictions[source_mask]
                    if len(source_energies) > 0:
                        result['by_source'][source] = {
                            'mean_kwh': safe_mean(source_energies, 0.0),
                            'scenarios_count': len(source_energies),
                            'min_kwh': float(np.min(source_energies)),
                            'max_kwh': float(np.max(source_energies))
                        }

            # Analysis by quality
            for quality in ['excellente', 'bonne', 'moyenne', 'mauvaise']:
                quality_mask = [d['quality'] == quality for d in descriptions]
                if any(quality_mask):
                    quality_energies = energy_predictions[quality_mask]
                    if len(quality_energies) > 0:
                        result['by_quality'][quality] = {
                            'mean_kwh': safe_mean(quality_energies, 0.0),
                            'scenarios_count': len(quality_energies)
                        }

            # Analysis by quantity
            if quantities_range:
                for quantity in quantities_range:
                    quantity_tons = quantity / 1000 if quantity > 100 else quantity
                    quantity_mask = [
                        abs(d['quantity_tons'] - quantity_tons) < 0.01 for d in descriptions]
                    if any(quantity_mask):
                        quantity_energies = energy_predictions[quantity_mask]
                        if len(quantity_energies) > 0:
                            mean_energy = safe_mean(quantity_energies, 0.0)
                            result['by_quantity'][f'{quantity}_tons'] = {
                                'mean_kwh': mean_energy,
                                'kwh_per_ton': safe_divide(mean_energy, quantity_tons, 0.0)
                            }

            result = clean_nan_values(result)
            cache.set(cache_key, result, timeout=3600)
            return result

        except Exception as e:
            logger.error(f"Error in enhanced energy prediction: {e}")
            return {'error': str(e), 'success': False}

    def predict_water_consumption(self, scenarios=None, quantities_range=None):
        """Enhanced water consumption prediction"""
        if not self.is_loaded:
            return {'error': 'Enhanced models not loaded', 'success': False}

        cache_key = f"enhanced_predict_water_{hash(str(quantities_range))}"
        cached = cache.get(cache_key)
        if cached:
            return clean_nan_values(cached)

        try:
            scenarios_matrix, descriptions = self._prepare_prediction_matrix(
                quantities_range)
            if scenarios_matrix is None:
                return {'error': 'Failed to prepare scenarios', 'success': False}

            scenarios_scaled = self.scaler.transform(scenarios_matrix)

            # Get all predictions
            all_predictions = self.all_targets_model.predict(scenarios_scaled)

            # Extract water consumption (index 7 in all_targets)
            water_predictions = all_predictions[:, 7]
            water_predictions = np.where(
                np.isnan(water_predictions) | np.isinf(water_predictions),
                0,
                water_predictions
            )

            result = {
                'predictions': {
                    'total_scenarios': len(water_predictions),
                    'water_liters': {
                        'min': float(np.min(water_predictions)) if len(water_predictions) > 0 else 0.0,
                        'max': float(np.max(water_predictions)) if len(water_predictions) > 0 else 0.0,
                        'mean': safe_mean(water_predictions, 0.0),
                        'std': float(np.std(water_predictions)) if len(water_predictions) > 0 else 0.0,
                        'median': float(np.median(water_predictions)) if len(water_predictions) > 0 else 0.0,
                        'total_estimated': float(np.sum(water_predictions))
                    }
                },
                'by_source': {},
                'by_quality': {},
                'by_quantity': {},
                'success': True
            }

            # Analysis by source
            for source in ['Nord', 'Centre', 'Sud', 'Sfax']:
                source_mask = [d['source'] == source for d in descriptions]
                if any(source_mask):
                    source_water = water_predictions[source_mask]
                    if len(source_water) > 0:
                        result['by_source'][source] = {
                            'mean_liters': safe_mean(source_water, 0.0),
                            'scenarios_count': len(source_water)
                        }

            # Analysis by quantity
            if quantities_range:
                for quantity in quantities_range:
                    quantity_tons = quantity / 1000 if quantity > 100 else quantity
                    quantity_mask = [
                        abs(d['quantity_tons'] - quantity_tons) < 0.01 for d in descriptions]
                    if any(quantity_mask):
                        quantity_water = water_predictions[quantity_mask]
                        if len(quantity_water) > 0:
                            mean_water = safe_mean(quantity_water, 0.0)
                            result['by_quantity'][f'{quantity}_tons'] = {
                                'mean_liters': mean_water,
                                'liters_per_ton': safe_divide(mean_water, quantity_tons, 0.0)
                            }

            result = clean_nan_values(result)
            cache.set(cache_key, result, timeout=3600)
            return result

        except Exception as e:
            logger.error(f"Error in enhanced water prediction: {e}")
            return {'error': str(e), 'success': False}

    def predict_employee_requirements(self, scenarios=None, quantities_range=None):
        """Enhanced employee requirements prediction"""
        if not self.is_loaded:
            return {'error': 'Enhanced models not loaded', 'success': False}

        cache_key = f"enhanced_predict_employees_{hash(str(quantities_range))}"
        cached = cache.get(cache_key)
        if cached:
            return clean_nan_values(cached)

        try:
            scenarios_matrix, descriptions = self._prepare_prediction_matrix(
                quantities_range)
            if scenarios_matrix is None:
                return {'error': 'Failed to prepare scenarios', 'success': False}

            scenarios_scaled = self.scaler.transform(scenarios_matrix)

            # Get all predictions
            all_predictions = self.all_targets_model.predict(scenarios_scaled)

            # Extract employee requirements (index 8 in all_targets)
            employee_predictions = all_predictions[:, 8]
            employee_predictions = np.where(
                np.isnan(employee_predictions) | np.isinf(
                    employee_predictions),
                0,
                employee_predictions
            )

            result = {
                'predictions': {
                    'total_scenarios': len(employee_predictions),
                    'employees': {
                        'min': int(np.min(employee_predictions)) if len(employee_predictions) > 0 else 0,
                        'max': int(np.max(employee_predictions)) if len(employee_predictions) > 0 else 0,
                        'mean': safe_mean(employee_predictions, 0.0),
                        'std': float(np.std(employee_predictions)) if len(employee_predictions) > 0 else 0.0,
                        'median': float(np.median(employee_predictions)) if len(employee_predictions) > 0 else 0.0,
                        'total_estimated': int(np.sum(employee_predictions))
                    }
                },
                'by_source': {},
                'by_quantity': {},
                'efficiency_analysis': {},
                'success': True
            }

            # Analysis by source
            for source in ['Nord', 'Centre', 'Sud', 'Sfax']:
                source_mask = [d['source'] == source for d in descriptions]
                if any(source_mask):
                    source_employees = employee_predictions[source_mask]
                    if len(source_employees) > 0:
                        result['by_source'][source] = {
                            'mean_employees': safe_mean(source_employees, 0.0),
                            'scenarios_count': len(source_employees)
                        }

            # Analysis by quantity
            if quantities_range:
                for quantity in quantities_range:
                    quantity_tons = quantity / 1000 if quantity > 100 else quantity
                    quantity_mask = [
                        abs(d['quantity_tons'] - quantity_tons) < 0.01 for d in descriptions]
                    if any(quantity_mask):
                        quantity_employees = employee_predictions[quantity_mask]
                        if len(quantity_employees) > 0:
                            mean_employees = safe_mean(quantity_employees, 0.0)
                            result['by_quantity'][f'{quantity}_tons'] = {
                                'mean_employees': mean_employees,
                                'tons_per_employee': safe_divide(quantity_tons, mean_employees, 0.0),
                                'employees_per_ton': safe_divide(mean_employees, quantity_tons, 0.0)
                            }

            # Efficiency analysis
            try:
                if result['by_source']:
                    most_efficient_source = min(
                        result['by_source'].items(),
                        key=lambda x: x[1]['mean_employees'] if x[1]['mean_employees'] > 0 else float(
                            'inf')
                    )[0]

                    productivity_values = [
                        q['tons_per_employee'] for q in result['by_quantity'].values()
                        if q['tons_per_employee'] > 0 and not np.isnan(q['tons_per_employee'])
                    ]

                    avg_productivity = safe_mean(
                        np.array(productivity_values), 0.0) if productivity_values else 0.0

                    result['efficiency_analysis'] = {
                        'most_efficient_source': most_efficient_source,
                        'average_productivity': avg_productivity
                    }
            except Exception as e:
                logger.warning(f"Error in efficiency analysis: {e}")
                result['efficiency_analysis'] = {
                    'most_efficient_source': 'Unknown',
                    'average_productivity': 0.0
                }

            result = clean_nan_values(result)
            cache.set(cache_key, result, timeout=3600)
            return result

        except Exception as e:
            logger.error(f"Error in enhanced employee prediction: {e}")
            return {'error': str(e), 'success': False}

    def predict_all_targets(self, quantities_range=None):
        """Enhanced all targets prediction including costs"""
        if not self.is_loaded:
            return {'error': 'Enhanced models not loaded', 'success': False}

        cache_key = f"enhanced_predict_all_{hash(str(quantities_range))}"
        cached = cache.get(cache_key)
        if cached:
            return clean_nan_values(cached)

        try:
            scenarios_matrix, descriptions = self._prepare_prediction_matrix(
                quantities_range)
            if scenarios_matrix is None:
                return {'error': 'Failed to prepare scenarios', 'success': False}

            scenarios_scaled = self.scaler.transform(scenarios_matrix)

            # Get cost predictions
            cost_predictions = self.cost_model.predict(scenarios_scaled)
            cost_predictions = np.where(
                np.isnan(cost_predictions) | np.isinf(cost_predictions),
                0,
                cost_predictions
            )

            # Get all target predictions
            all_predictions = self.all_targets_model.predict(scenarios_scaled)
            all_predictions = np.where(
                np.isnan(all_predictions) | np.isinf(all_predictions),
                0,
                all_predictions
            )

            result = {
                'cost_targets': {
                    'electricity_cost_tnd': {
                        'min': float(np.min(cost_predictions[:, 0])),
                        'max': float(np.max(cost_predictions[:, 0])),
                        'mean': safe_mean(cost_predictions[:, 0], 0.0),
                        'total_estimated': float(np.sum(cost_predictions[:, 0]))
                    },
                    'water_cost_tnd': {
                        'min': float(np.min(cost_predictions[:, 1])),
                        'max': float(np.max(cost_predictions[:, 1])),
                        'mean': safe_mean(cost_predictions[:, 1], 0.0),
                        'total_estimated': float(np.sum(cost_predictions[:, 1]))
                    },
                    'labor_cost_tnd': {
                        'min': float(np.min(cost_predictions[:, 2])),
                        'max': float(np.max(cost_predictions[:, 2])),
                        'mean': safe_mean(cost_predictions[:, 2], 0.0),
                        'total_estimated': float(np.sum(cost_predictions[:, 2]))
                    },
                    'total_operational_cost_tnd': {
                        'min': float(np.min(np.sum(cost_predictions, axis=1))),
                        'max': float(np.max(np.sum(cost_predictions, axis=1))),
                        'mean': safe_mean(np.sum(cost_predictions, axis=1), 0.0),
                        'total_estimated': float(np.sum(cost_predictions))
                    }
                },
                'main_targets': {
                    'energy_kwh': {
                        'min': float(np.min(all_predictions[:, 6])),
                        'max': float(np.max(all_predictions[:, 6])),
                        'mean': safe_mean(all_predictions[:, 6], 0.0),
                        'total_estimated': float(np.sum(all_predictions[:, 6]))
                    },
                    'water_liters': {
                        'min': float(np.min(all_predictions[:, 7])),
                        'max': float(np.max(all_predictions[:, 7])),
                        'mean': safe_mean(all_predictions[:, 7], 0.0),
                        'total_estimated': float(np.sum(all_predictions[:, 7]))
                    },
                    'employees': {
                        'min': int(np.min(all_predictions[:, 8])),
                        'max': int(np.max(all_predictions[:, 8])),
                        'mean': safe_mean(all_predictions[:, 8], 0.0),
                        'total_estimated': int(np.sum(all_predictions[:, 8]))
                    }
                },
                'additional_targets': {
                    'oil_quality_score': {
                        'min': float(np.min(all_predictions[:, 3])),
                        'max': float(np.max(all_predictions[:, 3])),
                        'mean': safe_mean(all_predictions[:, 3], 0.0)
                    },
                    'oil_quantity_tons': {
                        'min': float(np.min(all_predictions[:, 4])),
                        'max': float(np.max(all_predictions[:, 4])),
                        'mean': safe_mean(all_predictions[:, 4], 0.0),
                        'total_estimated': float(np.sum(all_predictions[:, 4]))
                    },
                    'processing_time_hours': {
                        'min': float(np.min(all_predictions[:, 5])),
                        'max': float(np.max(all_predictions[:, 5])),
                        'mean': safe_mean(all_predictions[:, 5], 0.0),
                        'total_estimated': float(np.sum(all_predictions[:, 5]))
                    }
                },
                'scenarios_analyzed': len(scenarios_matrix),
                'success': True
            }

            # Calculate correlations between costs and production
            try:
                main_matrix = np.column_stack([
                    np.sum(cost_predictions, axis=1),  # Total cost
                    all_predictions[:, 6],  # Energy
                    all_predictions[:, 7],  # Water
                    all_predictions[:, 8]   # Employees
                ])

                correlations = np.corrcoef(main_matrix.T)
                correlations = np.where(
                    np.isnan(correlations) | np.isinf(correlations),
                    0,
                    correlations
                )

                result['correlations'] = {
                    'cost_energy': float(correlations[0, 1]),
                    'cost_water': float(correlations[0, 2]),
                    'cost_employees': float(correlations[0, 3]),
                    'energy_water': float(correlations[1, 2]),
                    'energy_employees': float(correlations[1, 3]),
                    'water_employees': float(correlations[2, 3])
                }
            except Exception as e:
                logger.warning(f"Error calculating correlations: {e}")
                result['correlations'] = {}

            result = clean_nan_values(result)
            cache.set(cache_key, result, timeout=3600)
            return result

        except Exception as e:
            logger.error(f"Error in enhanced all targets prediction: {e}")
            return {'error': str(e), 'success': False}

    def predict_quality(self, quantities_range=None):
        """Enhanced quality prediction"""
        if not self.is_loaded:
            return {'error': 'Enhanced models not loaded', 'success': False}

        cache_key = f"enhanced_predict_quality_{hash(str(quantities_range))}"
        cached = cache.get(cache_key)
        if cached:
            return clean_nan_values(cached)

        try:
            scenarios_matrix, descriptions = self._prepare_prediction_matrix(
                quantities_range)
            if scenarios_matrix is None:
                return {'error': 'Failed to prepare scenarios', 'success': False}

            scenarios_scaled = self.scaler.transform(scenarios_matrix)
            all_predictions = self.all_targets_model.predict(scenarios_scaled)

            # Extract quality scores (index 3)
            quality_predictions = all_predictions[:, 3]
            quality_predictions = np.where(
                np.isnan(quality_predictions) | np.isinf(quality_predictions),
                0,
                quality_predictions
            )

            result = {
                'quality_predictions': {
                    'min_score': float(np.min(quality_predictions)),
                    'max_score': float(np.max(quality_predictions)),
                    'mean_score': safe_mean(quality_predictions, 0.0),
                    'std_score': float(np.std(quality_predictions))
                },
                'by_olive_type': {},
                'by_source': {},
                'quality_distribution': {},
                'success': True
            }

            # Analysis by olive type
            for olive_type in ['Chemlali', 'Chétoui', 'Oueslati', 'Gerboui']:
                type_mask = [d['olive_type'] ==
                             olive_type for d in descriptions]
                if any(type_mask):
                    type_quality = quality_predictions[type_mask]
                    if len(type_quality) > 0:
                        result['by_olive_type'][olive_type] = {
                            'mean_score': safe_mean(type_quality, 0.0),
                            'scenarios_count': len(type_quality)
                        }

            # Analysis by source
            for source in ['Nord', 'Centre', 'Sud', 'Sfax']:
                source_mask = [d['source'] == source for d in descriptions]
                if any(source_mask):
                    source_quality = quality_predictions[source_mask]
                    if len(source_quality) > 0:
                        result['by_source'][source] = {
                            'mean_score': safe_mean(source_quality, 0.0),
                            'scenarios_count': len(source_quality)
                        }

            # Quality distribution
            quality_ranges = {
                'excellent': (90, 100),
                'good': (80, 90),
                'average': (70, 80),
                'poor': (0, 70)
            }

            for category, (min_score, max_score) in quality_ranges.items():
                count = np.sum((quality_predictions >= min_score)
                               & (quality_predictions < max_score))
                percentage = (count / len(quality_predictions) *
                              100) if len(quality_predictions) > 0 else 0
                result['quality_distribution'][category] = {
                    'count': int(count),
                    'percentage': round(percentage, 2)
                }

            result = clean_nan_values(result)
            cache.set(cache_key, result, timeout=3600)
            return result

        except Exception as e:
            logger.error(f"Error in enhanced quality prediction: {e}")
            return {'error': str(e), 'success': False}

    def seasonal_analysis(self):
        """Enhanced seasonal analysis"""
        if not self.is_loaded:
            return {'error': 'Enhanced models not loaded', 'success': False}

        cache_key = "enhanced_seasonal_analysis"
        cached = cache.get(cache_key)
        if cached:
            return clean_nan_values(cached)

        try:
            # Define seasonal scenarios with enhanced mapping
            seasonal_scenarios = []
            seasonal_descriptions = []

            seasons = {
                'spring': {'quality': 'bonne', 'quantity': 50},
                'summer': {'quality': 'moyenne', 'quantity': 30},
                'autumn': {'quality': 'excellente', 'quantity': 80},
                'winter': {'quality': 'mauvaise', 'quantity': 20}
            }

            sources = ['Nord', 'Centre', 'Sud', 'Sfax']
            defaults = self._get_default_mappings()

            for season, params in seasons.items():
                quality = params['quality']
                quantity = params['quantity']

                # Map to ML categories
                olive_type = self._map_quality_to_olive_type(quality)

                for source in sources:
                    region = self._map_source_to_region(source)

                    # Check if mapped values exist
                    if (region in self.encoders['source'].classes_ and
                            olive_type in self.encoders['olive_type'].classes_):

                        try:
                            scenario = [
                                self.encoders['source'].transform([region])[0],
                                self.encoders['olive_type'].transform([olive_type])[
                                    0],
                                self.encoders['condition'].transform(
                                    [defaults['condition']])[0],
                                self.encoders['size'].transform(
                                    [defaults['olive_size']])[0],
                                self.encoders['press_method'].transform(
                                    [defaults['press_method']])[0],
                                quantity
                            ]
                            seasonal_scenarios.append(scenario)
                            seasonal_descriptions.append({
                                'season': season,
                                'source': source,
                                'region': region,
                                'quality': quality,
                                'olive_type': olive_type,
                                'quantity': quantity
                            })
                        except Exception as e:
                            logger.warning(
                                f"Error creating scenario for {season}, {source}: {e}")
                            continue

            if not seasonal_scenarios:
                return {'error': 'Failed to create seasonal scenarios', 'success': False}

            scenarios_matrix = np.array(seasonal_scenarios)
            scenarios_scaled = self.scaler.transform(scenarios_matrix)

            # Get predictions
            cost_predictions = self.cost_model.predict(scenarios_scaled)
            all_predictions = self.all_targets_model.predict(scenarios_scaled)

            # Clean predictions
            cost_predictions = np.where(
                np.isnan(cost_predictions) | np.isinf(cost_predictions),
                0,
                cost_predictions
            )
            all_predictions = np.where(
                np.isnan(all_predictions) | np.isinf(all_predictions),
                0,
                all_predictions
            )

            result = {
                'seasonal_patterns': {},
                'recommendations': {},
                'efficiency_by_season': {},
                'cost_analysis': {},
                'success': True
            }

            # Analysis by season
            for season in seasons.keys():
                season_mask = [d['season'] ==
                               season for d in seasonal_descriptions]
                if any(season_mask):
                    season_costs = cost_predictions[season_mask]
                    season_all = all_predictions[season_mask]

                    if len(season_costs) > 0:
                        total_costs = np.sum(season_costs, axis=1)

                        result['seasonal_patterns'][season] = {
                            'electricity_cost_tnd': safe_mean(season_costs[:, 0], 0.0),
                            'water_cost_tnd': safe_mean(season_costs[:, 1], 0.0),
                            'labor_cost_tnd': safe_mean(season_costs[:, 2], 0.0),
                            'total_cost_tnd': safe_mean(total_costs, 0.0),
                            'energy_kwh': safe_mean(season_all[:, 6], 0.0),
                            'water_liters': safe_mean(season_all[:, 7], 0.0),
                            'employees': safe_mean(season_all[:, 8], 0.0),
                            'quality_score': safe_mean(season_all[:, 3], 0.0),
                            'oil_quantity_tons': safe_mean(season_all[:, 4], 0.0),
                            'scenarios_count': len(season_costs)
                        }

            # Generate recommendations
            if result['seasonal_patterns']:
                try:
                    best_cost_season = min(result['seasonal_patterns'].items(),
                                           key=lambda x: x[1]['total_cost_tnd'])[0]
                    best_quality_season = max(result['seasonal_patterns'].items(),
                                              key=lambda x: x[1]['quality_score'])[0]
                    best_efficiency_season = max(result['seasonal_patterns'].items(),
                                                 key=lambda x: x[1]['oil_quantity_tons'])[0]

                    result['recommendations'] = {
                        'most_cost_effective_season': best_cost_season,
                        'best_quality_season': best_quality_season,
                        'most_productive_season': best_efficiency_season,
                        'optimal_planning': f"Focus on {best_quality_season} for quality, {best_cost_season} for cost efficiency"
                    }

                    # Cost analysis by season
                    for season, data in result['seasonal_patterns'].items():
                        quantity = seasons[season]['quantity']
                        result['cost_analysis'][season] = {
                            'cost_per_ton': safe_divide(data['total_cost_tnd'], quantity, 0.0),
                            'energy_cost_per_ton': safe_divide(data['electricity_cost_tnd'], quantity, 0.0),
                            'water_cost_per_ton': safe_divide(data['water_cost_tnd'], quantity, 0.0),
                            'labor_efficiency': safe_divide(quantity, data['employees'], 0.0) if data['employees'] > 0 else 0.0
                        }

                except Exception as e:
                    logger.warning(f"Error generating recommendations: {e}")
                    result['recommendations'] = {
                        'most_cost_effective_season': 'autumn',
                        'best_quality_season': 'autumn',
                        'optimal_planning': 'Unable to generate specific recommendations'
                    }

            result = clean_nan_values(result)
            cache.set(cache_key, result, timeout=7200)
            return result

        except Exception as e:
            logger.error(f"Error in enhanced seasonal analysis: {e}")
            return {'error': str(e), 'success': False}

    def get_model_status(self):
        """Get enhanced model status"""
        available_categories = {}
        if self.encoders:
            available_categories = {
                'sources': list(self.encoders['source'].classes_),
                'olive_types': list(self.encoders['olive_type'].classes_),
                'conditions': list(self.encoders['condition'].classes_),
                'sizes': list(self.encoders['size'].classes_),
                'press_methods': list(self.encoders['press_method'].classes_)
            }

        return clean_nan_values({
            'is_loaded': self.is_loaded,
            'models_available': {
                'cost_model': self.cost_model is not None,
                'all_targets_model': self.all_targets_model is not None,
                'scaler': self.scaler is not None,
                'encoders': self.encoders is not None
            },
            'categories': available_categories,
            'model_info': self.model_info if self.model_info else {},
            'enhanced_features': {
                'cost_prediction': True,
                'multi_target_prediction': True,
                'quality_mapping': True,
                'regional_analysis': True
            }
        })


# Global instance
global_prediction_service = GlobalPredictionService()
