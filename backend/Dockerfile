FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # PostgreSQL client
    libpq-dev \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    # Image processing libraries
    libjpeg-dev \
    libpng-dev \
    # Build tools
    gcc \
    g++ \
    # Poppler utilities (for PDF processing)
    poppler-utils \
    # curl for healthcheck
    curl \
    # netcat for database wait script
    netcat-openbsd \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Set tesseract data path
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata/

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p /app/media \
    && mkdir -p /app/templatefiles \
    && mkdir -p /app/firebase \
    && mkdir -p /app/ml_model

# Set proper permissions
RUN chmod +x /app

# Fix the Tesseract path for Linux container
RUN sed -i "s|pytesseract.pytesseract.tesseract_cmd = r'C:\\\\Program Files\\\\Tesseract-OCR\\\\tesseract.exe'|# pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'|g" /app/backend/settings.py
RUN sed -i "s|os.environ\['TESSDATA_PREFIX'\] = r'C:\\\\Program Files\\\\Tesseract-OCR\\\\tessdata'|# os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/5/tessdata/'|g" /app/backend/settings.py

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

# Health check (removed curl requirement since API needs auth)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); result = s.connect_ex(('localhost', 8000)); s.close(); exit(result)"

# Run the application
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]