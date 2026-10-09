FROM python:3.11-slim

# libGL/glib are needed by OpenCV and MediaPipe. No compiler: dlib comes as a prebuilt wheel,
# because compiling it needs several GB of RAM and fails on small build machines.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (required by Hugging Face Spaces)
RUN useradd -m -u 1000 appuser
WORKDIR /app

COPY requirements.txt .
RUN grep -viE '^(cmake|dlib|face_recognition)' requirements.txt > requirements-docker.txt \
    && pip install --no-cache-dir -r requirements-docker.txt \
    && pip install --no-cache-dir dlib-bin \
    && pip install --no-cache-dir --no-deps face_recognition \
    && pip install --no-cache-dir face_recognition_models Click Pillow

COPY --chown=appuser:appuser . .
RUN mkdir -p /app/data && chown appuser:appuser /app/data
USER appuser

ENV HOST=0.0.0.0 PORT=7860
EXPOSE 7860

# One worker: liveness challenges and login lockout are kept in process memory
CMD ["sh", "-c", "gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT} app:app"]
