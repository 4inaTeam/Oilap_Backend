# Create: bills/management/commands/debug_media.py

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from bills.models import Bill
import requests


class Command(BaseCommand):
    help = 'Debug media file configuration and accessibility'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-files',
            action='store_true',
            help='Check if bill files are accessible',
        )
        parser.add_argument(
            '--fix-paths',
            action='store_true',
            help='Fix file paths in database',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== MEDIA DEBUG REPORT ==='))

        # 1. Configuration Check
        self.stdout.write('\n1. Configuration:')
        self.stdout.write(f'   MEDIA_ROOT: {settings.MEDIA_ROOT}')
        self.stdout.write(f'   MEDIA_URL: {settings.MEDIA_URL}')
        self.stdout.write(
            f'   DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}')

        # Check if media directory exists
        media_exists = os.path.exists(settings.MEDIA_ROOT)
        self.stdout.write(f'   Media directory exists: {media_exists}')

        if media_exists:
            try:
                file_count = sum([len(files)
                                 for r, d, files in os.walk(settings.MEDIA_ROOT)])
                self.stdout.write(f'   Local media files count: {file_count}')
            except Exception as e:
                self.stdout.write(f'   Error counting files: {e}')

        # 2. Cloudinary Check
        self.stdout.write('\n2. Cloudinary Configuration:')
        cloudinary_config = getattr(settings, 'CLOUDINARY_STORAGE', {})
        self.stdout.write(
            f'   Cloud Name: {cloudinary_config.get("CLOUD_NAME", "Not set")}')
        self.stdout.write(
            f'   API Key: {"Set" if cloudinary_config.get("API_KEY") else "Not set"}')
        self.stdout.write(
            f'   API Secret: {"Set" if cloudinary_config.get("API_SECRET") else "Not set"}')

        # 3. Database File Analysis
        self.stdout.write('\n3. Database Analysis:')
        bills = Bill.objects.all()
        total_bills = bills.count()
        bills_with_pdf = bills.exclude(pdf_file='').exclude(
            pdf_file__isnull=True).count()
        bills_with_image = bills.exclude(original_image='').exclude(
            original_image__isnull=True).count()

        self.stdout.write(f'   Total bills: {total_bills}')
        self.stdout.write(f'   Bills with PDF: {bills_with_pdf}')
        self.stdout.write(f'   Bills with images: {bills_with_image}')

        # 4. File Accessibility Check
        if options['check_files']:
            self.stdout.write('\n4. File Accessibility Check:')
            self.check_file_accessibility()

        # 5. Fix file paths
        if options['fix_paths']:
            self.stdout.write('\n5. Fixing File Paths:')
            self.fix_file_paths()

        # 6. Sample File URLs
        self.stdout.write('\n6. Sample File URLs:')
        sample_bills = Bill.objects.filter(
            original_image__isnull=False
        ).exclude(original_image='')[:3]

        for bill in sample_bills:
            self.stdout.write(f'   Bill {bill.id}:')
            self.stdout.write(f'     Image: {bill.original_image}')
            if bill.pdf_file:
                self.stdout.write(f'     PDF: {bill.pdf_file}')

        self.stdout.write(self.style.SUCCESS('\n=== DEBUG COMPLETE ==='))

    def check_file_accessibility(self):
        """Check if files are accessible via HTTP"""
        base_url = 'http://localhost:8000' if settings.DEBUG else 'https://your-app.onrender.com'

        sample_bills = Bill.objects.filter(
            original_image__isnull=False
        ).exclude(original_image='')[:5]

        accessible_count = 0
        total_checked = 0

        for bill in sample_bills:
            if bill.original_image:
                # Construct URL
                if bill.original_image.startswith('http'):
                    url = bill.original_image
                else:
                    url = f"{base_url}{settings.MEDIA_URL}{bill.original_image.lstrip('/')}"

                try:
                    response = requests.head(url, timeout=5)
                    if response.status_code == 200:
                        accessible_count += 1
                        self.stdout.write(f'   ✓ {url}')
                    else:
                        self.stdout.write(
                            f'   ✗ {url} (Status: {response.status_code})')
                except Exception as e:
                    self.stdout.write(f'   ✗ {url} (Error: {e})')
                total_checked += 1

        self.stdout.write(
            f'   Accessibility: {accessible_count}/{total_checked} files accessible')

    def fix_file_paths(self):
        """Fix common file path issues"""
        bills = Bill.objects.all()
        fixed_count = 0

        for bill in bills:
            updated = False

            # Fix original_image paths
            if bill.original_image:
                old_path = bill.original_image
                new_path = old_path

                # Remove duplicate slashes
                new_path = new_path.replace('//', '/')

                # Ensure no leading slash for relative paths
                if new_path.startswith('/') and not new_path.startswith('http'):
                    new_path = new_path.lstrip('/')

                if new_path != old_path:
                    bill.original_image = new_path
                    updated = True

            # Fix pdf_file paths
            if bill.pdf_file:
                old_path = bill.pdf_file
                new_path = old_path

                # Remove duplicate slashes
                new_path = new_path.replace('//', '/')

                # Ensure no leading slash for relative paths
                if new_path.startswith('/') and not new_path.startswith('http'):
                    new_path = new_path.lstrip('/')

                if new_path != old_path:
                    bill.pdf_file = new_path
                    updated = True

            if updated:
                bill.save()
                fixed_count += 1
                self.stdout.write(f'   Fixed paths for bill {bill.id}')

        self.stdout.write(f'   Fixed {fixed_count} bills')
