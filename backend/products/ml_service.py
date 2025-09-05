import os
import pickle
import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.core.cache import cache
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class EnhancedOliveOilPredictionService:
    """
    Service ML amélioré avec prédictions de coûts (électricité, eau, main-d'œuvre)
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
        """Charge les modèles ML améliorés avec prédiction de coûts"""
        try:
            # Chemin vers les modèles améliorés
            models_dir = os.path.join(settings.BASE_DIR, 'enhanced_models')

            if not os.path.exists(models_dir):
                logger.warning(
                    f"Répertoire des modèles améliorés non trouvé: {models_dir}")
                return

            # Charger le modèle de prédiction des coûts
            cost_model_path = os.path.join(
                models_dir, 'cost_prediction_model.joblib')
            if os.path.exists(cost_model_path):
                self.cost_model = joblib.load(cost_model_path)
                logger.info("✅ Modèle de prédiction des coûts chargé")
            else:
                logger.warning(
                    f"Modèle de coûts non trouvé: {cost_model_path}")

            # Charger le modèle complet (tous les targets)
            all_model_path = os.path.join(
                models_dir, 'all_targets_model.joblib')
            if os.path.exists(all_model_path):
                self.all_targets_model = joblib.load(all_model_path)
                logger.info("✅ Modèle complet chargé")

            # Charger le scaler amélioré
            scaler_path = os.path.join(models_dir, 'cost_scaler.joblib')
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
                logger.info("✅ Scaler amélioré chargé")

            # Charger les encodeurs améliorés
            encoders_path = os.path.join(models_dir, 'encoders.pkl')
            if os.path.exists(encoders_path):
                with open(encoders_path, 'rb') as f:
                    self.encoders = pickle.load(f)
                logger.info("✅ Encodeurs améliorés chargés")

            # Charger les infos du modèle amélioré
            info_path = os.path.join(models_dir, 'enhanced_model_info.pkl')
            if os.path.exists(info_path):
                with open(info_path, 'rb') as f:
                    self.model_info = pickle.load(f)
                logger.info("✅ Informations du modèle amélioré chargées")

            # Vérifier que tous les composants sont chargés
            if all([self.cost_model, self.scaler, self.encoders]):
                self.is_loaded = True
                logger.info(
                    "🎯 Service ML amélioré avec prédiction de coûts chargé avec succès")

                if self.model_info:
                    logger.info(
                        f"📊 Performance modèle coûts: R² = {self.model_info.get('cost_r2_score', 'N/A'):.3f}")
            else:
                logger.error("❌ Échec du chargement des modèles améliorés")
                self.is_loaded = False

        except Exception as e:
            logger.error(
                f"❌ Erreur lors du chargement des modèles améliorés: {e}")
            self.is_loaded = False

    def _map_quality_to_olive_type(self, quality):
        """Mappe la qualité du produit vers le type d'olive ML"""
        quality_mapping = {
            'excellente': 'Chétoui',
            'bonne': 'Oueslati',
            'moyenne': 'Chemlali',
            'mauvaise': 'Gerboui'
        }
        return quality_mapping.get(quality, 'Chemlali')

    def _map_source_to_region(self, source):
        """Mappe la source vers les régions ML - Version améliorée"""
        if not source:
            return 'Centre'

        source_lower = source.lower().strip()

        # Mapping précis pour les régions tunisiennes
        region_keywords = {
            'Sfax': ['sfax'],
            'Nord': ['tunis', 'bizerte', 'nabeul', 'ariana', 'ben arous', 'manouba', 'beja', 'jendouba', 'kef', 'siliana'],
            'Sud': ['gabes', 'medenine', 'tataouine', 'kebili', 'tozeur', 'gafsa'],
            'Centre': ['sousse', 'monastir', 'mahdia', 'kairouan', 'kasserine', 'sidi bouzid', 'zaghouan']
        }

        for region, keywords in region_keywords.items():
            if any(keyword in source_lower for keyword in keywords):
                return region

        # Région par défaut
        logger.debug(
            f"Région '{source}' non reconnue, utilisation de 'Centre' par défaut")
        return 'Centre'

    def _prepare_enhanced_features(self, source, quantity, quality):
        """Prépare les features pour le modèle amélioré"""
        try:
            # Mapper vers les catégories ML
            region = self._map_source_to_region(source)
            olive_type = self._map_quality_to_olive_type(quality)

            # Valeurs par défaut optimisées
            condition = 'Rainfed'  # Pluvial par défaut
            olive_size = 'Medium'  # Taille moyenne par défaut
            press_method = 'Méthode en continu'  # Méthode la plus efficace

            logger.debug(
                f"Mapping amélioré: {source} → {region}, {quality} → {olive_type}")

            # Encoder les variables catégorielles
            source_encoded = self.encoders['source'].transform([region])[0]
            olive_type_encoded = self.encoders['olive_type'].transform([olive_type])[
                0]
            condition_encoded = self.encoders['condition'].transform([condition])[
                0]
            size_encoded = self.encoders['size'].transform([olive_size])[0]
            press_encoded = self.encoders['press_method'].transform([press_method])[
                0]

            # Créer le vecteur de features (ordre important!)
            # ['Source_Encoded', 'Olive_Type_Encoded', 'Condition_Encoded',
            #  'Olive_Size_Encoded', 'Press_Method_Encoded', 'Quantity_Olives_Tons']
            features = np.array([[
                source_encoded,
                olive_type_encoded,
                condition_encoded,
                size_encoded,
                press_encoded,
                float(quantity) / 1000  # Convertir kg en tonnes
            ]])

            return features

        except Exception as e:
            logger.error(f"Erreur préparation features améliorées: {e}")
            logger.error(
                f"Paramètres: source={source}, quality={quality}, quantity={quantity}")
            return None

    def predict_costs_and_production(self, source, quantity, quality):
        """
        Prédiction complète: coûts + production
        Retourne un dictionnaire avec toutes les prédictions
        """
        if not self.is_loaded:
            logger.warning(
                "Modèles améliorés non chargés - prédictions ignorées")
            return None

        try:
            # Cache key pour éviter les calculs répétés
            cache_key = f"enhanced_ml_pred_{hash(f'{source}_{quantity}_{quality}')}"
            cached_result = cache.get(cache_key)

            if cached_result:
                logger.debug("Prédiction améliorée mise en cache utilisée")
                return cached_result

            # Préparer les features
            features = self._prepare_enhanced_features(
                source, quantity, quality)
            if features is None:
                return None

            # Normaliser
            features_scaled = self.scaler.transform(features)

            results = {}

            # Prédire les COÛTS (électricité, eau, main-d'œuvre)
            if self.cost_model:
                cost_predictions = self.cost_model.predict(features_scaled)[0]

                results['costs'] = {
                    'electricity_cost_tnd': float(cost_predictions[0]),
                    'water_cost_tnd': float(cost_predictions[1]),
                    'labor_cost_tnd': float(cost_predictions[2]),
                    'total_operational_cost_tnd': float(sum(cost_predictions))
                }

                logger.debug(f"Prédictions de coûts: Électricité={cost_predictions[0]:.2f}TND, "
                             f"Eau={cost_predictions[1]:.2f}TND, Main-d'œuvre={cost_predictions[2]:.2f}TND")

            # Prédire TOUS les targets (production + coûts)
            if self.all_targets_model:
                all_predictions = self.all_targets_model.predict(features_scaled)[
                    0]

                # Ordre des targets selon model_info:
                # cost_targets = ['Electricity_Cost_TND', 'Water_Cost_TND', 'Total_Labor_Cost_TND']
                # production_targets = ['Oil_Quality_Score', 'Oil_Quantity_Tons', 'Processing_Time_Hours',
                #                      'Total_Energy_Consumption_kWh', 'Water_Consumption_Liters', 'Total_Employees']

                results['production'] = {
                    # Index 3 après les 3 coûts
                    'oil_quality_score': float(all_predictions[3]),
                    'oil_quantity_tons': float(all_predictions[4]),
                    'processing_time_hours': float(all_predictions[5]),
                    'energy_consumption_kwh': float(all_predictions[6]),
                    'water_consumption_liters': float(all_predictions[7]),
                    'total_employees': int(round(all_predictions[8]))
                }

                # Conversion en litres pour compatibilité
                results['production']['oil_quantity_liters'] = results['production']['oil_quantity_tons'] * 1000

            # Informations de mapping
            results['mapping_info'] = {
                'source_region': self._map_source_to_region(source),
                'olive_type_ml': self._map_quality_to_olive_type(quality),
                'press_method': 'Méthode en continu',
                'condition': 'Rainfed'
            }

            # Métriques d'efficacité
            if 'costs' in results and 'production' in results:
                oil_volume = results['production']['oil_quantity_liters']
                if oil_volume > 0:
                    results['efficiency_metrics'] = {
                        'cost_per_liter_tnd': results['costs']['total_operational_cost_tnd'] / oil_volume,
                        'energy_per_liter_kwh': results['production']['energy_consumption_kwh'] / oil_volume,
                        'water_per_liter_ratio': results['production']['water_consumption_liters'] / oil_volume
                    }

            # Mettre en cache pour 30 minutes
            cache.set(cache_key, results, timeout=1800)

            logger.info(
                f"✅ Prédiction améliorée complète: {quantity}kg {quality} de {source}")
            logger.info(
                f"   Coût total: {results.get('costs', {}).get('total_operational_cost_tnd', 0):.2f}TND")
            logger.info(
                f"   Huile produite: {results.get('production', {}).get('oil_quantity_liters', 0):.1f}L")

            return results

        except Exception as e:
            logger.error(f"Erreur prédiction améliorée: {e}")
            logger.error(
                f"Paramètres: source={source}, quantity={quantity}, quality={quality}")
            return None

    def predict_costs_only(self, source, quantity, quality):
        """Prédiction des coûts uniquement (plus rapide)"""
        full_prediction = self.predict_costs_and_production(
            source, quantity, quality)
        return full_prediction.get('costs') if full_prediction else None

    def auto_predict(self, source, quantity, quality):
        """
        Interface compatible avec l'ancienne version pour la rétrocompatibilité
        """
        full_prediction = self.predict_costs_and_production(
            source, quantity, quality)

        if not full_prediction:
            return None

        # Format compatible avec l'ancien système
        production = full_prediction.get('production', {})
        mapping = full_prediction.get('mapping_info', {})

        return {
            'energy_kwh': production.get('energy_consumption_kwh', 0),
            'water_liters': production.get('water_consumption_liters', 0),
            'employees': production.get('total_employees', 1),
            'processing_time_hours': production.get('processing_time_hours', 1),
            'source_region': mapping.get('source_region', 'Centre'),
            'olive_type_ml': mapping.get('olive_type_ml', 'Chemlali'),

            # Nouvelles données de coûts
            'costs': full_prediction.get('costs', {}),
            'oil_quantity_liters': production.get('oil_quantity_liters', 0),
            'oil_quality_score': production.get('oil_quality_score', 7.0)
        }

    def get_model_status(self):
        """Retourne le statut des modèles chargés"""
        return {
            'service_loaded': self.is_loaded,
            'cost_model_loaded': self.cost_model is not None,
            'all_targets_model_loaded': self.all_targets_model is not None,
            'scaler_loaded': self.scaler is not None,
            'encoders_loaded': self.encoders is not None,
            'model_info': self.model_info is not None,
            'performance_metrics': self.model_info if self.model_info else {}
        }


# Instance globale du service amélioré
enhanced_ml_service = EnhancedOliveOilPredictionService()

# Garde l'ancienne interface pour compatibilité
ml_prediction_service = enhanced_ml_service
