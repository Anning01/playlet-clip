"""Configuration management using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM (ChatGPT) configuration."""

    model_config = SettingsConfigDict(env_prefix="OPENAI_")

    api_key: str = Field(default="", description="OpenAI API key")
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL",
    )
    model: str = Field(default="gpt-4o", description="Model name")
    temperature: float = Field(default=0.3, ge=0, le=2, description="Sampling temperature")
    max_retries: int = Field(default=10, ge=1, description="Max retries for validation failures")


class ASRSettings(BaseSettings):
    """ASR (FunASR) configuration."""

    model_config = SettingsConfigDict(env_prefix="ASR_")

    model_name: str = Field(
        default="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        description="FunASR model name",
    )
    vad_model: str = Field(
        default="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        description="VAD model name",
    )
    punc_model: str = Field(
        default="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        description="Punctuation model name",
    )
    device: Literal["cuda", "cpu"] = Field(default="cuda", description="Device for inference")
    batch_size: int = Field(default=1, ge=1, description="Batch size for inference")


class TTSSettings(BaseSettings):
    """TTS (CosyVoice / edge-tts) configuration."""

    model_config = SettingsConfigDict(env_prefix="TTS_")

    # Backend selection: "auto", "cosyvoice_api", "cosyvoice_local", "edge_tts"
    backend: Literal["auto", "cosyvoice_api", "cosyvoice_local", "edge_tts"] = Field(
        default="auto",
        description="TTS backend: auto (try cosyvoice_api -> edge_tts), cosyvoice_api, cosyvoice_local, edge_tts",
    )

    # CosyVoice API settings (for Docker deployment)
    cosyvoice_api_url: str = Field(
        default="http://cosyvoice:8080",
        description="CosyVoice API server URL",
    )

    # CosyVoice local settings
    model_name: str = Field(
        default="iic/CosyVoice-300M-SFT",
        description="CosyVoice model name (for local mode)",
    )
    device: Literal["cuda", "cpu"] = Field(default="cuda", description="Device for inference")

    # Common settings
    default_voice: str = Field(default="中文女", description="Default voice")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed")
    sample_rate: int = Field(default=22050, description="Audio sample rate")


class VideoSettings(BaseSettings):
    """Video processing configuration."""

    model_config = SettingsConfigDict(env_prefix="VIDEO_")

    blur_height: int = Field(default=185, ge=0, description="Blur region height in pixels")
    blur_y: int = Field(default=1413, ge=0, description="Blur region Y position in pixels")
    subtitle_margin: int = Field(default=65, ge=0, description="Subtitle vertical margin")
    blur_sigma: int = Field(default=20, ge=1, description="Gaussian blur sigma")
    video_codec: str = Field(default="libx264", description="Video codec")
    audio_codec: str = Field(default="aac", description="Audio codec")
    preset: str = Field(default="fast", description="FFmpeg encoding preset")
    
    # Audio mixing settings for narration
    original_volume: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Original audio volume during narration (0.0-1.0)"
    )
    narration_volume: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Narration audio volume (0.0-2.0)"
    )


class PathSettings(BaseSettings):
    """Path configuration."""

    model_config = SettingsConfigDict(env_prefix="PATH_")

    base_dir: Path = Field(default=Path("."), description="Base directory")
    input_dir: Path = Field(default=Path("data/input"), description="Input directory")
    output_dir: Path = Field(default=Path("data/output"), description="Output directory")
    temp_dir: Path = Field(default=Path("data/temp"), description="Temp directory")
    models_dir: Path = Field(default=Path("models"), description="Models directory")
    config_dir: Path = Field(default=Path("config"), description="Config directory")

    def ensure_dirs(self) -> None:
        """Create directories if they don't exist."""
        for dir_path in [self.input_dir, self.output_dir, self.temp_dir, self.models_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


class StyleConfig(BaseSettings):
    """Narration style configuration."""

    name: str = Field(description="Style name")
    description: str = Field(description="Style description")
    prompt_template: str | None = Field(default=None, description="Custom prompt template")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="PLAYLET_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Sub-configurations
    llm: LLMSettings = Field(default_factory=LLMSettings)
    asr: ASRSettings = Field(default_factory=ASRSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    paths: PathSettings = Field(default_factory=PathSettings)

    # Style configurations
    styles: list[StyleConfig] = Field(
        default=[
            StyleConfig(
                name="讽刺风格",
                description="通过讽刺和夸张的手法来评论剧中的不合理或过于狗血的情节，让观众在笑声中进行思考。",
            ),
            StyleConfig(
                name="温情风格",
                description="以温和、感性的语气解读剧情，引发观众共鸣。",
            ),
            StyleConfig(
                name="悬疑风格",
                description="以悬疑、紧张的语气解读剧情，制造悬念感。",
            ),
        ],
        description="Available narration styles",
    )

    # UI settings
    ui_host: str = Field(default="0.0.0.0", description="Gradio UI host")
    ui_port: int = Field(default=7860, ge=1, le=65535, description="Gradio UI port")
    ui_share: bool = Field(default=False, description="Enable Gradio share link")

    # Debug settings
    debug: bool = Field(default=False, description="Enable debug mode")

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Settings":
        """Load settings from YAML file."""
        if not yaml_path.exists():
            return cls()

        with open(yaml_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f) or {}

        return cls(**config_dict)

    def to_yaml(self, yaml_path: Path) -> None:
        """Save settings to YAML file."""
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(
                self.model_dump(mode="json"),
                f,
                default_flow_style=False,
                allow_unicode=True,
            )

    @field_validator("styles", mode="before")
    @classmethod
    def validate_styles(cls, v):
        """Convert dict styles to StyleConfig objects."""
        if isinstance(v, list):
            return [StyleConfig(**item) if isinstance(item, dict) else item for item in v]
        return v


@lru_cache()
def get_settings(config_path: str | None = None) -> Settings:
    """Get cached settings instance."""
    if config_path:
        return Settings.from_yaml(Path(config_path))

    # Try default config paths
    default_paths = [
        Path("config/config.yaml"),
        Path("config.yaml"),
        Path.home() / ".config" / "playlet-clip" / "config.yaml",
    ]

    for path in default_paths:
        if path.exists():
            return Settings.from_yaml(path)

    return Settings()
