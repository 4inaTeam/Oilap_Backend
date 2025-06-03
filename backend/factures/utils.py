import re
from PIL import Image
import pytesseract

KEYWORDS = {
    'ELECTRICITY': ['kwh', 'edm', 'électricité', 'volt', 'énergie'],
    'WATER': ['eau', 'm³', 'hydraulique', 'aqua', 'pompage'],
    'PURCHASE': ['achat', 'fournisseur', 'commande', 'matériel', 'olives']
}

def classify_facture_type(text):
    text = text.lower()
    
    if re.search(r'\bkwh\b|\bvolt\b|\bénergie\b', text):
        return 'ELECTRICITY'
    if re.search(r'\beau\b|\bm³\b|\bhydraulique\b', text):
        return 'WATER'
    if re.search(r'\bachat\b|\bfournisseur\b|\bolives\b', text):
        return 'PURCHASE'

    scores = {k: sum(1 for word in KEYWORDS[k] if word in text) for k in KEYWORDS}
    best_match = max(scores, key=scores.get)
    return best_match if scores[best_match] > 0 else 'PURCHASE'

def extract_text_from_image(image_path):
    try:
        return pytesseract.image_to_string(Image.open(image_path), lang='fra')
    except Exception as e:
        print(f"Erreur OCR : {e}")
        return ""