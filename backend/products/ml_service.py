# products/ml_service.py - VERSION CORRIGÉE

import os
import pickle
import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class AutomaticOliveOilPredictionService:
    """
    Service ML automatique pour prédictions lors de la sauvegarde des produits
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.encoders = None
        self.model_info = None
        self.is_loaded = False
        self._load_models()

    def _load_models(self):
        """Charge les modèles ML automatiquement"""
        try:
            # Chemin vers les modèles
            models_dir = os.path.join(settings.BASE_DIR, 'ml_models')

            # Charger le modèle principal (plus rapide pour l'automatisation)
            model_path = os.path.join(models_dir, 'best_main_model.joblib')
            self.model = joblib.load(model_path)

            # Charger le scaler
            scaler_path = os.path.join(models_dir, 'scaler.joblib')
            self.scaler = joblib.load(scaler_path)

            # Charger les encodeurs
            encoders_path = os.path.join(models_dir, 'label_encoders.pkl')
            with open(encoders_path, 'rb') as f:
                self.encoders = pickle.load(f)

            # Charger les infos du modèle
            info_path = os.path.join(models_dir, 'model_info.pkl')
            with open(info_path, 'rb') as f:
                self.model_info = pickle.load(f)

            self.is_loaded = True
            logger.info(
                "✅ Modèles ML chargés automatiquement pour prédictions auto")

        except Exception as e:
            logger.error(f"❌ Erreur chargement modèles ML: {e}")
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
        """Mappe la source vers les régions ML - FONCTION CORRIGÉE"""
        if not source:
            return 'Centre'  # Défaut

        source_lower = source.lower().strip()

        # Mapping robuste pour les villes/régions tunisiennes
        if any(keyword in source_lower for keyword in ['sfax']):
            return 'Sfax'
        elif any(keyword in source_lower for keyword in ['tunis', 'bizerte', 'nabeul', 'ariana', 'ben arous', 'manouba']):
            return 'Nord'
        elif any(keyword in source_lower for keyword in ['gabes', 'medenine', 'tataouine', 'kebili', 'tozeur', 'gafsa']):
            return 'Sud'
        elif any(keyword in source_lower for keyword in ['sousse', 'monastir', 'mahdia', 'kairouan', 'kasserine', 'sidi bouzid']):
            return 'Centre'
        else:
            # Pour toute autre région non reconnue
            logger.warning(
                f"Région '{source}' non reconnue, utilisation de 'Centre' par défaut")
            return 'Centre'

    def _prepare_features(self, source, quantity, quality):
        """Prépare les features pour la prédiction - FONCTION CORRIGÉE"""
        try:
            # Mapper vers les catégories ML
            region = self._map_source_to_region(source)
            olive_type = self._map_quality_to_olive_type(quality)

            # Valeurs par défaut pour les autres features
            condition = 'Rainfed'  # Pluvial par défaut
            olive_size = 'Medium'  # Taille moyenne par défaut
            press_method = 'Méthode en continu'  # Méthode la plus moderne

            logger.debug(
                f"Mapping ML: {source} → {region}, {quality} → {olive_type}")

            # Encoder les variables catégorielles
            source_encoded = self.encoders['source'].transform([region])[0]
            olive_type_encoded = self.encoders['olive_type'].transform([olive_type])[
                0]
            condition_encoded = self.encoders['condition'].transform([condition])[
                0]
            size_encoded = self.encoders['size'].transform([olive_size])[0]
            press_encoded = self.encoders['press_method'].transform([press_method])[
                0]

            # Créer le vecteur de features
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
            logger.error(f"Erreur préparation features: {e}")
            logger.error(
                f"Source: {source}, Quality: {quality}, Quantity: {quantity}")
            return None

    # PARAMÈTRE CORRIGÉ: source au lieu d'origine
    def auto_predict(self, source, quantity, quality):
        """
        Prédiction automatique silencieuse
        Retourne None en cas d'erreur pour ne pas bloquer la sauvegarde du produit
        """
        if not self.is_loaded:
            logger.warning("Modèles ML non chargés - prédictions ignorées")
            return None

        try:
            # Créer une clé de cache pour éviter les calculs répétés
            cache_key = f"ml_auto_pred_{hash(f'{source}_{quantity}_{quality}')}"
            cached_result = cache.get(cache_key)

            if cached_result:
                logger.debug("Prédiction ML mise en cache utilisée")
                return cached_result

            # Préparer les features
            features = self._prepare_features(source, quantity, quality)
            if features is None:
                return None

            # Normaliser
            features_scaled = self.scaler.transform(features)

            # Prédire
            predictions = self.model.predict(features_scaled)[0]

            # Créer le résultat
            result = {
                'energy_kwh': float(predictions[0]),
                'water_liters': float(predictions[1]),
                'employees': int(round(predictions[2])),
                'processing_time_hours': self._estimate_processing_time(quantity, quality),
                'source_region': self._map_source_to_region(source),
                'olive_type_ml': self._map_quality_to_olive_type(quality)
            }

            # Mettre en cache pour 30 minutes
            cache.set(cache_key, result, timeout=1800)

            logger.info(f"✅ Prédiction ML auto: {quantity}kg {quality} de {source} → "
                        f"Région: {result['source_region']}, "
                        f"Énergie: {result['energy_kwh']:.1f}kWh, "
                        f"Eau: {result['water_liters']:.0f}L, "
                        f"Employés: {result['employees']}")

            return result

        except Exception as e:
            logger.error(f"Erreur prédiction ML automatique: {e}")
            logger.error(
                f"Paramètres: source={source}, quantity={quantity}, quality={quality}")
            return None

    def _estimate_processing_time(self, quantity_kg, quality):
        """Estime le temps de traitement"""
        # Temps de base : 0.5h par tonne
        base_time = (quantity_kg / 1000) * 0.5

        # Facteur qualité
        quality_factors = {
            'excellente': 1.2,
            'bonne': 1.1,
            'moyenne': 1.0,
            'mauvaise': 0.9
        }

        factor = quality_factors.get(quality, 1.0)
        return base_time * factor


# Instance globale du service
ml_prediction_service = AutomaticOliveOilPredictionService()
