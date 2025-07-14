from firebase_service import initialize_firebase
from firebase_admin import messaging

initialize_firebase()


def send_fcm_notification(user, title, body, data=None):
    if not user.fcm_token:
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

    except Exception as e:
        print(f"Erreur d'envoi : {str(e)}")
