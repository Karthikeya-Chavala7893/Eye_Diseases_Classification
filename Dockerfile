FROM python:3.11-slim

WORKDIR /app

# Install curl for container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies with PyTorch CPU
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend application source
COPY backend/ ./backend/

WORKDIR /app/backend

# Create models cache directory
RUN mkdir -p models

# Default environment configuration for Hugging Face Spaces
ENV PORT=7860 \
    FLASK_ENV=production \
    TORCH_DEVICE=cpu \
    LOCAL_MODEL_ID=models/ensemble_classifier.pth \
    HF_MODEL_REPO=Karthikeya-Chavala7893/visionai-retinal-ensemble \
    MODEL_LOAD_TIMEOUT_SECONDS=180 \
    ALLOWED_ORIGINS=*

EXPOSE 7860

# Start Gunicorn server binding to port 7860
CMD ["gunicorn", "app:app", "--workers", "1", "--threads", "4", "--timeout", "180", "--bind", "0.0.0.0:7860"]
