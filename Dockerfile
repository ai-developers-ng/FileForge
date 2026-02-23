FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# ── FileForge defaults (all overridable via docker run -e or .env) ────────────
# Concurrency
ENV WORKER_COUNT=2
ENV GUNICORN_WORKERS=1
ENV GUNICORN_THREADS=8
# OCR quality
ENV OCR_DPI=300
# OCR parallelism (Phase 3)
ENV OCR_PAGE_WORKERS=2
ENV OCR_BATCH_SIZE=10
# File handling
ENV MAX_FILE_MB=50
# Cleanup
ENV CLEANUP_TTL_HOURS=24
ENV CLEANUP_INTERVAL_MINUTES=30

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-spa \
    tesseract-ocr-ita \
    tesseract-ocr-por \
    tesseract-ocr-nld \
    tesseract-ocr-rus \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    tesseract-ocr-jpn \
    tesseract-ocr-kor \
    tesseract-ocr-ara \
    tesseract-ocr-hin \
    tesseract-ocr-tur \
    # ImageMagick + Ghostscript (required for PDF/PS/EPS support)
    imagemagick \
    libmagickwand-dev \
    ghostscript \
    # LaTeX for PDF generation (without old pandoc)
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-fonts-recommended \
    lmodern \
    # FFmpeg
    ffmpeg \
    # Poppler (for PDF to image)
    poppler-utils \
    # Build tools for Python packages
    gcc \
    libffi-dev \
    # Magic byte detection
    libmagic1 \
    # For downloading pandoc
    wget \
    # For health check
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install newer Pandoc from GitHub (compatible with pypandoc 1.16.x)
RUN wget -q https://github.com/jgm/pandoc/releases/download/3.6.1/pandoc-3.6.1-1-amd64.deb \
    && dpkg -i pandoc-3.6.1-1-amd64.deb \
    && rm pandoc-3.6.1-1-amd64.deb \
    && apt-get clean

# Configure ImageMagick policy to allow PDF operations
RUN sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml || true

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/results

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/ || exit 1

# Run with gunicorn for production
# Worker/thread counts are read from env vars (GUNICORN_WORKERS, GUNICORN_THREADS)
# Configure in .env or via docker run -e GUNICORN_WORKERS=1 -e GUNICORN_THREADS=8
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:5001 --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --timeout 300 --max-requests 1000 --max-requests-jitter 100 --worker-class gthread app:app"]
