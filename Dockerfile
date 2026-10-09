FROM python:3.11-slim

# Build tools for dlib; libGL/glib for OpenCV and MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (required by Hugging Face Spaces)
RUN useradd -m -u 1000 appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .
RUN mkdir -p /app/data && chown appuser:appuser /app/data
USER appuser

ENV HOST=0.0.0.0 PORT=7860
EXPOSE 7860

# One worker: liveness challenges and login lockout are kept in process memory
CMD ["sh", "-c", "gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT} app:app"]
