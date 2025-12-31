import os
import base64
from google.cloud import vision
from google.oauth2 import service_account

# Utilitaire pour extraire les infos d'une CI belge via Google Vision
# Nécessite la variable d'environnement GOOGLE_APPLICATION_CREDENTIALS ou un chemin de clé explicite

def extract_id_card_data(image_b64: str, credentials_path: str = None):
    """
    Appelle Google Vision OCR sur une image base64 et extrait nom, prénom, etc. (support multilingue)
    :param image_b64: image en base64 (data:image/jpeg;base64,....)
    :param credentials_path: chemin vers la clé de service JSON (optionnel, sinon GOOGLE_APPLICATION_CREDENTIALS)
    :return: dictionnaire avec les champs extraits
    """
    if image_b64.startswith("data:"):
        image_b64 = image_b64.split(",", 1)[1]
    image_bytes = base64.b64decode(image_b64)

    if credentials_path:
        creds = service_account.Credentials.from_service_account_file(credentials_path)
        client = vision.ImageAnnotatorClient(credentials=creds)
    else:
        client = vision.ImageAnnotatorClient()

    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    if not texts:
        return {}
    full_text = texts[0].description

    # Extraction multilingue simple (fr/nl/en)
    import re
    result = {}
    # Nom
    match = re.search(r"NOM\s*[:\-]?\s*([A-Z\- ]+)", full_text)
    if not match:
        match = re.search(r"Surname\s*[:\-]?\s*([A-Z\- ]+)", full_text)
    if match:
        result['last_name'] = match.group(1).strip()
    # Prénom
    match = re.search(r"PR[ÉE]NOM\s*[:\-]?\s*([A-Z\- ]+)", full_text)
    if not match:
        match = re.search(r"Given names?\s*[:\-]?\s*([A-Z\- ]+)", full_text, re.IGNORECASE)
    if match:
        result['first_name'] = match.group(1).strip()
    # Date de naissance
    match = re.search(r"Naissance\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", full_text)
    if not match:
        match = re.search(r"Birth\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", full_text)
    if match:
        result['birth_date'] = match.group(1)
    # Numéro document
    match = re.search(r"Document\s*[:\-]?\s*([A-Z0-9]+)", full_text)
    if match:
        result['document_number'] = match.group(1)
    # Nationalité
    match = re.search(r"Nationalit[ée]?[\s:]*([A-Z\- ]+)", full_text)
    if match:
        result['nationality'] = match.group(1)
    # Sexe
    match = re.search(r"Sexe\s*[:\-]?\s*([MF])", full_text)
    if match:
        result['sex'] = match.group(1)
    # Date d'expiration
    match = re.search(r"Valable.*?jusqu'?au?\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", full_text)
    if not match:
        match = re.search(r"Expiry\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", full_text)
    if match:
        result['expiry_date'] = match.group(1)
    # Ajoute le texte brut pour debug
    result['raw_text'] = full_text
    return result
