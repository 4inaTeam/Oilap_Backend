import firebase_admin
from firebase_admin import credentials, messaging

def initialize_firebase():
    cred = credentials.Certificate("backend/oilap-8a178-firebase-adminsdk-fbsvc-0b05532864.json")
    firebase_admin.initialize_app(cred)