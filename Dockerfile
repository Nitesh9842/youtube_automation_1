FROM python:3.11-slim

# Install system dependencies (FFmpeg is required for video editing)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p downloads user_tokens

# Set environment
ENV ENVIRONMENT=production
ENV PORT=5000

# Expose port
EXPOSE 5000

# Run with Gunicorn
CMD ["sh", "-c", "gunicorn wsgi:app --bind 0.0.0.0:${PORT} --workers 2 --timeout 120"]
