import os
import re
import numpy as np
import tensorflow as tf
import cv2
import pytesseract
from PIL import Image
from django.conf import settings

# Load and map the ML model
MODEL_PATH = settings.ML_MODEL_PATH
model = tf.keras.models.load_model(MODEL_PATH)
CLASS_INDICES = {v: k for k, v in settings.CLASSES.items()}

# Regex patterns for OCR keywords
KEYWORD_PATTERNS = {
    'water': re.compile(r'\b(eau|water)\b', re.IGNORECASE),
    'electricity': re.compile(r'\b(électricité|electricity|edf)\b', re.IGNORECASE),
    'purchase': re.compile(r'\b(achat|purchase|facture)\b', re.IGNORECASE)
}

# Regex patterns for date and amount
DATE_PATTERN = r"(\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b|\b\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\b)"
AMOUNT_PATTERN = r"(\b\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?\s?(?:€|EUR|\$)?\b)"

# Ensure Tesseract paths
os.environ['TESSDATA_PREFIX'] = r'C:\Program Files\Tesseract-OCR\tessdata'
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def classify_image(img: Image.Image):
    """
    Classify PIL image into a category with confidence score.
    If certain keywords appear via OCR, override the model prediction.
    """
    # 1) Model-based prediction
    x = img.resize((224, 224))
    x = np.array(x) / 255.0
    x = np.expand_dims(x, axis=0)
    preds = model.predict(x)[0]
    idx = int(np.argmax(preds))
    category = CLASS_INDICES[idx]
    confidence = float(preds[idx])

    # 2) Quick OCR for keyword override
    try:
        text = pytesseract.image_to_string(img, lang='fra')
        for cat, pattern in KEYWORD_PATTERNS.items():
            if pattern.search(text):
                return cat, 1.0
    except Exception:
        pass

    return category, confidence


def preprocess_for_ocr(img: Image.Image) -> np.ndarray:
    """
    Preprocess PIL image for OCR: grayscale, normalize, blur, threshold.
    """
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    norm = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    blur = cv2.medianBlur(norm, 3)
    th = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    return th


def extract_fields(img: Image.Image):
    """
    Perform OCR on invoice image and extract pay date and montant.
    Returns a tuple (pay_date, montant).
    """
    processed = preprocess_for_ocr(img)
    custom_config = r"--oem 1 --psm 6"
    text = pytesseract.image_to_string(
        processed,
        lang='fra',
        config=custom_config
    )

    dates = re.findall(DATE_PATTERN, text)
    amounts = re.findall(AMOUNT_PATTERN, text)

    pay_date = dates[-1] if dates else None
    montant = None
    if amounts:
        def to_float(s):
            clean = s.replace('€', '').replace('EUR', '')
            clean = clean.replace('.', '').replace(',', '.')
            return float(re.sub(r'[^\d\.]+' , '', clean) or 0)
        montant = max(amounts, key=to_float)

    return pay_date, montant