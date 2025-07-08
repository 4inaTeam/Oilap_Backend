#!/usr/bin/env bash
# build.sh

set -o errexit  # exit on error

# Install Python dependencies
pip install -r requirements.txt

# Install Tesseract OCR for production
apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-eng

# Collect static files
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate