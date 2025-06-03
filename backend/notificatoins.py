from firebase_service import initialize_firebase
from firebase_admin import messaging

initialize_firebase()

def send_fcm_notification(user, title, body, data=None):
    if not user.fcm_token:
        print("Aucun token FCM enregistré pour cet utilisateur")
        return
    
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=user.fcm_token,
        data=data or {}
    )
    
    try:
        messaging.send(message)
        print("Notification envoyée avec succès")
    except Exception as e:
        print(f"Erreur d'envoi : {str(e)}")