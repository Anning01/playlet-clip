FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime

LABEL maintainer="anning <anningforchina@gmail.com>"
LABEL description="Playlet-Clip: AI-powered short drama auto-editing tool"

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    sox \
    libsox-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files (including README.md for hatchling build)
COPY pyproject.toml README.md ./
COPY src/ src/
COPY scripts/ scripts/

# Install dependencies
RUN uv pip install --system -e .

# Install CosyVoice dependencies - models will be downloaded on first run
RUN mkdir -p third_party && \
    git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git third_party/CosyVoice && \
    cd third_party/CosyVoice && \
    pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ && \
    pip install modelscope -i https://mirrors.aliyun.com/pypi/simple/

# Create directories
RUN mkdir -p /app/config /app/data/input /app/data/output /app/data/temp /app/models

# Copy config
COPY config/ config/

# Set CosyVoice Python path
ENV PYTHONPATH="/app/third_party/CosyVoice:/app/third_party/CosyVoice/third_party/Matcha-TTS:${PYTHONPATH}"

# Expose Gradio port
EXPOSE 7860

# Set default environment variables
ENV PLAYLET__UI_HOST=0.0.0.0 \
    PLAYLET__UI_PORT=7860 \
    PLAYLET__PATHS__INPUT_DIR=/app/data/input \
    PLAYLET__PATHS__OUTPUT_DIR=/app/data/output \
    PLAYLET__PATHS__TEMP_DIR=/app/data/temp \
    PLAYLET__PATHS__MODELS_DIR=/app/models \
    PLAYLET__PATHS__CONFIG_DIR=/app/config \
    PLAYLET__TTS__BACKEND=cosyvoice_local \
    PLAYLET__TTS__MODEL_NAME=/app/pretrained_models/CosyVoice-300M-SFT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# Run the application
CMD ["python", "-m", "playlet_clip.main"]
