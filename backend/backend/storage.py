import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import HttpResponse, Http404
from django.views.generic import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import requests
import logging

logger = logging.getLogger(__name__)


class HybridMediaView(View):
    """
    A view that serves media files from both local storage and Cloudinary.
    This handles the case where some files might be stored locally and others on Cloudinary.
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, path):
        """
        Serve media files from local storage first, then try Cloudinary
        """
        logger.info(f"Serving media file: {path}")

        # Try local storage first
        local_path = os.path.join(settings.MEDIA_ROOT, path)
        if os.path.exists(local_path):
            logger.info(f"Found file locally: {local_path}")
            return self.serve_local_file(local_path)

        # Try Cloudinary if local file doesn't exist
        if hasattr(settings, 'CLOUDINARY_STORAGE') and settings.CLOUDINARY_STORAGE.get('CLOUD_NAME'):
            logger.info(f"Trying Cloudinary for: {path}")
            return self.serve_cloudinary_file(path)

        logger.warning(f"File not found: {path}")
        raise Http404("Media file not found")

    def serve_local_file(self, file_path):
        """Serve a file from local storage"""
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # Determine content type
            content_type = self.get_content_type(file_path)

            response = HttpResponse(file_content, content_type=content_type)
            response['Content-Length'] = len(file_content)
            response['Cache-Control'] = 'public, max-age=3600'

            return response
        except Exception as e:
            logger.error(f"Error serving local file {file_path}: {e}")
            raise Http404("Error serving media file")

    def serve_cloudinary_file(self, path):
        """Serve a file from Cloudinary"""
        try:
            cloud_name = settings.CLOUDINARY_STORAGE.get('CLOUD_NAME')
            # Construct Cloudinary URL
            cloudinary_url = f"https://res.cloudinary.com/{cloud_name}/image/upload/{path}"

            # Fetch from Cloudinary
            response = requests.get(cloudinary_url, timeout=10)

            if response.status_code == 200:
                logger.info(f"Successfully fetched from Cloudinary: {path}")

                django_response = HttpResponse(
                    response.content,
                    content_type=response.headers.get(
                        'content-type', 'application/octet-stream')
                )
                django_response['Content-Length'] = len(response.content)
                django_response['Cache-Control'] = 'public, max-age=3600'
                django_response['X-Served-By'] = 'Cloudinary'

                return django_response
            else:
                logger.warning(
                    f"Cloudinary returned {response.status_code} for: {path}")
                raise Http404("File not found on Cloudinary")

        except requests.RequestException as e:
            logger.error(f"Error fetching from Cloudinary {path}: {e}")
            raise Http404("Error fetching from Cloudinary")
        except Exception as e:
            logger.error(
                f"Unexpected error serving Cloudinary file {path}: {e}")
            raise Http404("Error serving media file")

    def get_content_type(self, file_path):
        """Determine content type based on file extension"""
        import mimetypes
        content_type, _ = mimetypes.guess_type(file_path)

        if content_type is None:
            if file_path.lower().endswith('.pdf'):
                content_type = 'application/pdf'
            elif file_path.lower().endswith(('.jpg', '.jpeg')):
                content_type = 'image/jpeg'
            elif file_path.lower().endswith('.png'):
                content_type = 'image/png'
            else:
                content_type = 'application/octet-stream'

        return content_type


def ensure_media_directory():
    """Ensure media directory exists and is writable"""
    if not os.path.exists(settings.MEDIA_ROOT):
        try:
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            logger.info(f"Created media directory: {settings.MEDIA_ROOT}")
        except OSError as e:
            logger.error(
                f"Failed to create media directory {settings.MEDIA_ROOT}: {e}")

    # Test write permissions
    test_file = os.path.join(settings.MEDIA_ROOT, '.write_test')
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logger.info(f"Media directory is writable: {settings.MEDIA_ROOT}")
    except OSError as e:
        logger.warning(
            f"Media directory is not writable {settings.MEDIA_ROOT}: {e}")


def get_file_url(file_field):
    """
    Get the correct URL for a file, whether it's stored locally or on Cloudinary
    """
    if not file_field:
        return None

    # If it's already a full URL (Cloudinary), return as-is
    if hasattr(file_field, 'url') and file_field.url.startswith('http'):
        return file_field.url

    # For local files, construct the URL
    if hasattr(file_field, 'url'):
        return file_field.url

    # Fallback
    return f"{settings.MEDIA_URL}{file_field}"


def migrate_local_to_cloudinary():
    """
    Utility function to migrate existing local files to Cloudinary
    This can be run as a management command
    """
    if not os.path.exists(settings.MEDIA_ROOT):
        logger.info("No local media directory found")
        return

    try:
        import cloudinary.uploader

        migrated_count = 0
        error_count = 0

        for root, dirs, files in os.walk(settings.MEDIA_ROOT):
            for file in files:
                if file.startswith('.'):  # Skip hidden files
                    continue

                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(
                    local_path, settings.MEDIA_ROOT)

                try:
                    # Upload to Cloudinary
                    result = cloudinary.uploader.upload(
                        local_path,
                        public_id=relative_path.replace(
                            '\\', '/'),  # Use forward slashes
                        overwrite=True
                    )

                    logger.info(
                        f"Migrated {relative_path} to Cloudinary: {result['secure_url']}")
                    migrated_count += 1

                except Exception as e:
                    logger.error(f"Failed to migrate {relative_path}: {e}")
                    error_count += 1

        logger.info(
            f"Migration complete: {migrated_count} files migrated, {error_count} errors")

    except ImportError:
        logger.error("Cloudinary library not available for migration")
    except Exception as e:
        logger.error(f"Migration failed: {e}")


# Add this to your Django app's ready() method or management command
def setup_media_handling():
    """Setup media handling on Django startup"""
    ensure_media_directory()

    logger.info("Media handling setup complete")
    logger.info(f"Local media root: {settings.MEDIA_ROOT}")
    logger.info(
        f"Cloudinary configured: {bool(getattr(settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME'))}")
