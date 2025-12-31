FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime

LABEL maintainer="anning <anningforchina@gmail.com>"
LABEL description="Playlet-Clip: AI-powered short drama auto-editing tool"

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies and Chinese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    sox \
    libsox-dev \
    fonts-noto-cjk \
    fontconfig \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files (including README.md for hatchling build)
COPY pyproject.toml README.md ./
COPY src/ src/
COPY scripts/ scripts/

# Install dependencies
RUN uv pip install --system -e .

# Create directories
RUN mkdir -p /app/config /app/data/input /app/data/output /app/data/temp /app/models

# Copy config
COPY config/ config/

# Expose Gradio port
EXPOSE 7860

# Set default environment variables (use edge_tts by default for fast startup)
# To use CosyVoice, set PLAYLET__TTS__BACKEND=cosyvoice_local and mount the model
ENV PLAYLET__UI_HOST=0.0.0.0 \
    PLAYLET__UI_PORT=7860 \
    PLAYLET__TTS__BACKEND=edge_tts \
    PLAYLET__PATHS__INPUT_DIR=/app/data/input \
    PLAYLET__PATHS__OUTPUT_DIR=/app/data/output \
    PLAYLET__PATHS__TEMP_DIR=/app/data/temp \
    PLAYLET__PATHS__MODELS_DIR=/app/models \
    PLAYLET__PATHS__CONFIG_DIR=/app/config

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# Run the application
CMD ["python", "-m", "playlet_clip.main"]
