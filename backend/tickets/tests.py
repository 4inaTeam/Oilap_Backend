def test_email_configuration():
    """Test function to verify email setup"""
    from django.core.mail import send_mail
    from django.conf import settings
    
    try:
        send_mail(
            'Test Email',
            'This is a test email to verify configuration.',
            settings.DEFAULT_FROM_EMAIL,
            ['test@example.com'],
            fail_silently=False,
        )
        print("Email configuration test passed!")
        return True
    except Exception as e:
        print(f"Email configuration test failed: {e}")
        return False