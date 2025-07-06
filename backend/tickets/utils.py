import requests
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from twilio.rest import Client
from firebase_admin import messaging
import logging
from firebase_admin import firestore

logger = logging.getLogger(__name__)


def send_email_notification(user, facture):
    try:
        subject = f"New Facture Created: {facture.facture_number}"
        message = f"Hello {user.username},\n\nVeuiller régler la facture Réf : {facture.facture_number} au bureau de comptabilité dans les 10 minutes\n\nMontant: {facture.final_total} TND"

        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )
        logger.info(
            f"✅ Email sent to {user.email} for facture {facture.facture_number}")
        return True
    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return False


def send_sms_notification(user, facture):
    try:
        if not user.tel:
            logger.warning(f"No phone number for user {user.id}")
            return False

        client = Client(settings.TWILIO_ACCOUNT_SID,
                        settings.TWILIO_AUTH_TOKEN)
        message_body = f"New facture {facture.facture_number} created. Amount: {facture.final_total} TND. Please pay at the accounting office within 10 minutes."

        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=f"+216{user.tel}"
        )
        logger.info(
            f"✅ SMS sent to +216{user.tel} for facture {facture.facture_number}")
        return True
    except Exception as e:
        logger.error(f"Error sending SMS to +216{user.tel}: {str(e)}")
        return False


def send_push_notification(user, facture):
    """Send push notification when facture is created"""
    try:
        # Check if user can receive notifications
        if not user.can_receive_notifications():
            logger.warning(f"User {user.id} cannot receive notifications")
            return False

        # Create FCM message
        message = messaging.Message(
            notification=messaging.Notification(
                title="New Facture Created",
                body=f"Facture {facture.facture_number} - {facture.final_total} TND",
            ),
            token=user.fcm_token,
            data={
                "type": "facture",
                "id": str(facture.id),
                "facture_id": str(facture.id),
                "facture_number": facture.facture_number,
                "amount": str(facture.final_total),
                "route": "/facture_detail",
                "timestamp": str(facture.created_at.isoformat()) if hasattr(facture, 'created_at') else "",
            },
        )

        # Send to FCM
        response = messaging.send(message)
        logger.info(f"✅ FCM sent to user {user.id}, message_id={response}")

        # Log to Firestore (optional - you can remove this if you don't want Firestore logging)
        try:
            db = firestore.client()
            doc_ref = db.collection('notifications').document()
            doc_ref.set({
                'user_id': str(user.id),
                'user_email': user.email,
                'facture_id': str(facture.id),
                'facture_number': facture.facture_number,
                'title': "New Facture Created",
                'body': f"Facture {facture.facture_number} - {facture.final_total} TND",
                'fcm_token': user.fcm_token,
                'sent_at': firestore.SERVER_TIMESTAMP,
                'status': 'success',
                'message_id': response,
                'ticket_type': 'PUSH',
            })
            logger.info(
                f"✅ Logged notification to Firestore for user {user.id}")
        except Exception as firestore_error:
            logger.error(f"Error logging to Firestore: {str(firestore_error)}")
            # Don't fail the whole function if Firestore logging fails

        return True

    except Exception as e:
        logger.error(
            f"Error sending push notification to user {user.id}: {str(e)}")

        # Log error to Firestore (optional)
        try:
            db = firestore.client()
            db.collection('notification_errors').document().set({
                'error': str(e),
                'user_id': str(user.id),
                'facture_id': str(facture.id),
                'fcm_token': user.fcm_token,
                'timestamp': firestore.SERVER_TIMESTAMP,
            })
        except Exception as firestore_error:
            logger.error(
                f"Error logging error to Firestore: {str(firestore_error)}")

        return False


def create_test_notification(user, title="Test Notification", body="This is a test notification"):
    """Helper function to create test notifications"""
    try:
        from .models import Notification

        notification = Notification.objects.create(
            user=user,
            title=title,
            body=body,
            type='test',
            data={
                'test': True,
                # ✅ Fixed timezone usage
                'timestamp': str(timezone.now().isoformat())
            }
        )
        logger.info(f"Created test notification for user {user.id}")
        return notification
    except Exception as e:
        logger.error(f"Error creating test notification: {str(e)}")
        return None


def send_email_notification_for_product(user, product, facture):
    """Send email notification when product is ready"""
    try:
        subject = f"Your Product is Ready - Facture {facture.facture_number}"
        message = f"""Hello {user.username},

Great news! Your product is ready for pickup.

Product Details:
- Quality: {product.get_quality_display()}
- Price: {product.price} TND

This product has been added to facture {facture.facture_number}.
Total amount to pay: {facture.final_total} TND

Please visit the accounting office within 10 minutes to complete your payment.

Thank you!"""

        from django.core.mail import send_mail
        from django.conf import settings

        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )
        logger.info(
            f"✅ Product ready email sent to {user.email} for product {product.id}")
        return True
    except Exception as e:
        logger.error(
            f"Error sending product ready email to {user.email}: {str(e)}")
        return False


def send_sms_notification_for_product(user, product, facture):
    """Send SMS notification when product is ready"""
    try:
        if not user.tel:
            logger.warning(f"No phone number for user {user.id}")
            return False

        from twilio.rest import Client
        from django.conf import settings

        client = Client(settings.TWILIO_ACCOUNT_SID,
                        settings.TWILIO_AUTH_TOKEN)
        message_body = f"Your product (Quality: {product.get_quality_display()}) is ready! Added to facture {facture.facture_number}. Total: {facture.final_total} TND. Please visit accounting office within 10 minutes."

        message = client.messages.create(
            body=message_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=f"+216{user.tel}"
        )
        logger.info(
            f"✅ Product ready SMS sent to +216{user.tel} for product {product.id}")
        return True
    except Exception as e:
        logger.error(
            f"Error sending product ready SMS to +216{user.tel}: {str(e)}")
        return False


def send_push_notification_for_product(user, product, facture):
    """Send push notification when product is ready"""
    try:
        if not user.can_receive_notifications():
            logger.warning(f"User {user.id} cannot receive notifications")
            return False

        from firebase_admin import messaging, firestore

        # Create FCM message
        message = messaging.Message(
            notification=messaging.Notification(
                title="Your Product is Ready! 🎉",
                body=f"Quality: {product.get_quality_display()} • Facture: {facture.facture_number} • {facture.final_total} TND",
            ),
            token=user.fcm_token,
            data={
                "type": "product_ready",
                "product_id": str(product.id),
                "facture_id": str(facture.id),
                "facture_number": facture.facture_number,
                "product_quality": product.quality,
                "product_price": str(product.price),
                "total_amount": str(facture.final_total),
                "route": "/facture_detail",
                # ✅ Fixed timezone usage
                "timestamp": str(timezone.now().isoformat()),
            },
        )

        # Send to FCM
        response = messaging.send(message)
        logger.info(
            f"✅ Product ready FCM sent to user {user.id}, message_id={response}")

        # Log to Firestore (optional)
        try:
            db = firestore.client()
            doc_ref = db.collection('notifications').document()
            doc_ref.set({
                'user_id': str(user.id),
                'user_email': user.email,
                'product_id': str(product.id),
                'facture_id': str(facture.id),
                'facture_number': facture.facture_number,
                'title': "Your Product is Ready! 🎉",
                'body': f"Quality: {product.get_quality_display()} • Facture: {facture.facture_number} • {facture.final_total} TND",
                'fcm_token': user.fcm_token,
                'sent_at': firestore.SERVER_TIMESTAMP,
                'status': 'success',
                'message_id': response,
                'ticket_type': 'PUSH',
                'notification_type': 'product_ready',
            })
            logger.info(
                f"✅ Logged product ready notification to Firestore for user {user.id}")
        except Exception as firestore_error:
            logger.error(f"Error logging to Firestore: {str(firestore_error)}")

        return True

    except Exception as e:
        logger.error(
            f"Error sending product ready push notification to user {user.id}: {str(e)}")

        # Log error to Firestore (optional)
        try:
            db = firestore.client()
            db.collection('notification_errors').document().set({
                'error': str(e),
                'user_id': str(user.id),
                'product_id': str(product.id),
                'facture_id': str(facture.id),
                'fcm_token': user.fcm_token,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'notification_type': 'product_ready',
            })
        except Exception as firestore_error:
            logger.error(
                f"Error logging error to Firestore: {str(firestore_error)}")

        return False
