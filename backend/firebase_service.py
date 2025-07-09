import firebase_admin
from firebase_admin import credentials, messaging
import os
import json


def initialize_firebase():
    cred = credentials.Certificate("backend/ooillab-ce5bd-firebase-adminsdk-fbsvc-2292b47a83")
    firebase_admin.initialize_app(cred)
    # Check if we're in a production environment (like Render)
    firebase_creds = os.getenv('FIREBASE_CREDENTIALS_JSON')

    if firebase_creds:
        # Parse the JSON string from environment variable
        cred_dict = json.loads(firebase_creds)
        cred = credentials.Certificate(cred_dict)
    else:
        # Fallback to local file for development
        cred = credentials.Certificate(
            "backend/oilap-8a178-firebase-adminsdk-fbsvc-0b05532864.json")

    firebase_admin.initialize_app(cred)