import tensorflow as tf
from tensorflow.keras.models import load_model
import cv2
import numpy as np
import os
import time
from django.conf import settings
from pathlib import Path
from django.core.exceptions import ValidationError

class InvoiceClassifier:
    _instance = None
    CLASS_NAMES = ['ELECTRICITY', 'WATER', 'PURCHASE']  # Fixed choices
    
    def __init__(self):
        if InvoiceClassifier._instance is not None:
            raise RuntimeError("Use get_instance() instead of direct initialization")

        model_path = Path(settings.BASE_DIR) / 'ml_model' / 'invoice_classifier.h5'
        self.last_processing_time = None
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found at {model_path}")

        try:
            self.model = load_model(model_path, compile=False)  # Disable compilation
            self.img_size = (224, 224)
            self._verify_input_shape()
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize model: {str(e)}") from e
        
        self.model_version = self._get_model_version()

    def _get_model_version(self):
        try:
            return self.model.get_layer('model_version').get_config().get('version', '1.0.0')
        except:
            return "1.0.0"

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _verify_input_shape(self):
        expected_shape = (None, 224, 224, 3)
        if self.model.input_shape != expected_shape:
            raise ValueError(f"Model expects {expected_shape} but has {self.model.input_shape}")

    def preprocess_image(self, image_path):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
            
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Failed to read image")

            img = cv2.resize(img, (self.img_size[1], self.img_size[0]))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = np.expand_dims(img, axis=0) / 255.0

            if img.shape != (1, 224, 224, 3):
                raise ValueError(f"Invalid image shape: {img.shape}")

            return img
            
        except Exception as e:
            raise RuntimeError(f"Preprocessing failed: {str(e)}") from e

    def predict_with_confidence(self, image_path):
        try:
            start_time = time.time()
            processed_img = self.preprocess_image(image_path)
            predictions = self.model.predict(processed_img, verbose=0)
            
            self.last_processing_time = time.time() - start_time
            
            class_index = np.argmax(predictions)
            confidence = float(np.max(predictions))
            prediction = self.CLASS_NAMES[class_index]
            
            if prediction not in self.CLASS_NAMES:
                raise ValueError(f"Invalid prediction: {prediction}")
                
            return prediction, confidence
            
        except Exception as e:
            self.last_processing_time = None
            raise RuntimeError(f"Prediction failed: {str(e)}") from e