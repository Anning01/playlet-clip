"""TTS (Text-to-Speech) service with multiple backends."""

import re
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

import aiofiles
import httpx
import soundfile as sf
from loguru import logger
from mutagen.mp3 import MP3

if TYPE_CHECKING:
    import numpy as np

from playlet_clip.core.config import TTSSettings
from playlet_clip.core.exceptions import TTSError
from playlet_clip.models.segment import TTSResult
from playlet_clip.models.subtitle import SubtitleFile, SubtitleSegment


class TTSService:
    """TTS service with multiple backend support (CosyVoice API / CosyVoice Local / edge-tts)."""

    # CosyVoice preset voices
    COSYVOICE_VOICES = [
        "中文女",
        "中文男",
        "日语男",
        "粤语女",
        "英文女",
        "英文男",
        "韩语女",
    ]

    # Edge-TTS voices mapping
    EDGE_TTS_VOICES = {
        "中文女": "zh-CN-XiaoxiaoNeural",
        "中文男": "zh-CN-YunxiNeural",
        "日语男": "ja-JP-KeitaNeural",
        "粤语女": "zh-HK-HiuGaaiNeural",
        "英文女": "en-US-JennyNeural",
        "英文男": "en-US-GuyNeural",
        "韩语女": "ko-KR-SunHiNeural",
    }

    PRESET_VOICES = COSYVOICE_VOICES

    def __init__(self, config: TTSSettings):
        """
        Initialize TTS service.

        Args:
            config: TTS configuration
        """
        self.config = config
        self._model = None
        self._initialized = False
        self._backend: Literal["cosyvoice_api", "cosyvoice_local", "edge_tts"] | None = None
        self._http_client: httpx.AsyncClient | None = None

    def _ensure_initialized(self) -> None:
        """Ensure TTS backend is initialized based on config."""
        if self._initialized:
            return

        backend = self.config.backend

        # Auto mode: try backends in order
        if backend == "auto":
            if self._try_init_cosyvoice_api():
                return
            if self._try_init_cosyvoice_local():
                return
            if self._try_init_edge_tts():
                return
            raise TTSError(
                "No TTS backend available. Please either:\n"
                "  - Start CosyVoice Docker: docker compose up -d cosyvoice\n"
                "  - Install edge-tts: pip install edge-tts"
            )

        # Specific backend requested
        elif backend == "cosyvoice_api":
            if not self._try_init_cosyvoice_api():
                raise TTSError(
                    f"CosyVoice API not available at {self.config.cosyvoice_api_url}\n"
                    "Start CosyVoice Docker: docker compose up -d cosyvoice"
                )

        elif backend == "cosyvoice_local":
            if not self._try_init_cosyvoice_local():
                raise TTSError(
                    "CosyVoice local not available. Install from:\n"
                    "  git clone https://github.com/FunAudioLLM/CosyVoice"
                )

        elif backend == "edge_tts":
            if not self._try_init_edge_tts():
                raise TTSError("edge-tts not installed. Run: pip install edge-tts")

    def _try_init_cosyvoice_api(self) -> bool:
        """Try to initialize CosyVoice API backend."""
        try:
            import httpx

            # Quick health check (sync for initialization)
            url = self.config.cosyvoice_api_url.rstrip("/")
            response = httpx.get(f"{url}/", timeout=2.0)
            if response.status_code == 200:
                self._backend = "cosyvoice_api"
                self._initialized = True
                logger.info(f"CosyVoice API backend initialized: {url}")
                return True
        except Exception as e:
            logger.debug(f"CosyVoice API not available: {e}")
        return False

    def _try_init_cosyvoice_local(self) -> bool:
        """Try to initialize CosyVoice local backend."""
        try:
            # CosyVoice requires source installation, not pip
            # Check if cosyvoice package is available
            from cosyvoice.cli.cosyvoice import CosyVoice

            model_path = self.config.model_name

            # If it's a ModelScope model ID, try to download it
            if "/" in model_path and not Path(model_path).exists():
                logger.info(f"Downloading CosyVoice model from ModelScope: {model_path}")
                try:
                    from modelscope import snapshot_download

                    # Download to local directory
                    local_dir = Path("pretrained_models") / model_path.split("/")[-1]
                    snapshot_download(model_path, local_dir=str(local_dir))
                    model_path = str(local_dir)
                    logger.info(f"Model downloaded to: {model_path}")
                except ImportError:
                    logger.warning("modelscope not installed, cannot download model")
                    return False
                except Exception as e:
                    logger.warning(f"Failed to download model: {e}")
                    return False

            logger.info(f"Loading CosyVoice model: {model_path}")
            self._model = CosyVoice(model_path)
            self._backend = "cosyvoice_local"
            self._initialized = True
            logger.info("CosyVoice local backend initialized successfully")
            return True
        except ImportError:
            logger.debug("CosyVoice not installed (requires source installation)")
        except Exception as e:
            logger.debug(f"CosyVoice local failed: {e}")
        return False

    def _try_init_edge_tts(self) -> bool:
        """Try to initialize edge-tts backend."""
        try:
            import edge_tts  # noqa: F401

            self._backend = "edge_tts"
            self._initialized = True
            logger.info("Edge-TTS backend initialized successfully")
            return True
        except ImportError:
            logger.debug("edge-tts not installed")
        return False

    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice: str | None = None,
        generate_subtitle: bool = True,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> TTSResult:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            output_path: Path for output audio file
            voice: Voice to use (default from config)
            generate_subtitle: Whether to generate subtitle file
            progress_callback: Optional callback for progress updates

        Returns:
            TTSResult with audio path, subtitle path, and duration
        """
        if not text.strip():
            raise TTSError("Empty text provided")

        self._ensure_initialized()

        voice = voice or self.config.default_voice
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(10, f"合成语音 ({self._backend}): {text[:20]}...")

        try:
            if self._backend == "cosyvoice_api":
                return await self._synthesize_cosyvoice_api(
                    text, output_path, voice, generate_subtitle, progress_callback
                )
            elif self._backend == "cosyvoice_local":
                return await self._synthesize_cosyvoice_local(
                    text, output_path, voice, generate_subtitle, progress_callback
                )
            else:
                return await self._synthesize_edge_tts(
                    text, output_path, voice, generate_subtitle, progress_callback
                )

        except Exception as e:
            logger.error(f"TTS failed: {e}")
            raise TTSError(f"Speech synthesis failed: {e}")

    async def _synthesize_cosyvoice_api(
        self,
        text: str,
        output_path: Path,
        voice: str,
        generate_subtitle: bool,
        progress_callback: Callable[[float, str], None] | None,
    ) -> TTSResult:
        """Synthesize using CosyVoice API server."""
        logger.info(f"CosyVoice API synthesizing: {text[:50]}...")

        url = f"{self.config.cosyvoice_api_url.rstrip('/')}/v1/tts"
        audio_path = output_path.with_suffix(".wav")

        if progress_callback:
            progress_callback(30, "调用 CosyVoice API...")

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Send request with form data
            response = await client.post(
                url,
                data={"text": text, "spk": voice},
            )

            if response.status_code != 200:
                raise TTSError(f"CosyVoice API error: {response.status_code} - {response.text}")

            # Save audio file
            async with aiofiles.open(audio_path, "wb") as f:
                await f.write(response.content)

        if progress_callback:
            progress_callback(70, "保存音频文件...")

        duration = self.get_audio_duration(audio_path)

        # Generate subtitle
        subtitle_path = None
        if generate_subtitle:
            if progress_callback:
                progress_callback(85, "生成字幕文件...")
            subtitle_path = await self._generate_subtitle(
                text, duration, output_path.with_suffix(".srt")
            )

        if progress_callback:
            progress_callback(100, "语音合成完成")

        logger.info(f"CosyVoice API completed: {audio_path}, duration: {duration:.2f}s")

        return TTSResult(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            duration=duration,
            sample_rate=self.config.sample_rate,
        )

    async def _synthesize_cosyvoice_local(
        self,
        text: str,
        output_path: Path,
        voice: str,
        generate_subtitle: bool,
        progress_callback: Callable[[float, str], None] | None,
    ) -> TTSResult:
        """Synthesize using CosyVoice local model."""
        import numpy as np

        logger.info(f"CosyVoice local synthesizing: {text[:50]}...")

        # Generate speech
        audio_segments = []
        for output in self._model.inference_sft(text, voice):
            audio_segments.append(output["tts_speech"].numpy())

        if not audio_segments:
            raise TTSError("No audio generated")

        audio_data = np.concatenate(audio_segments, axis=0)

        # Apply speed adjustment if needed
        if self.config.speed != 1.0:
            audio_data = self._adjust_speed(audio_data, self.config.speed)

        audio_data = audio_data.flatten()

        if progress_callback:
            progress_callback(70, "保存音频文件...")

        # Save audio as WAV
        audio_path = output_path.with_suffix(".wav")
        sf.write(str(audio_path), audio_data, self.config.sample_rate)

        duration = len(audio_data) / self.config.sample_rate

        # Generate subtitle
        subtitle_path = None
        if generate_subtitle:
            if progress_callback:
                progress_callback(85, "生成字幕文件...")
            subtitle_path = await self._generate_subtitle(
                text, duration, output_path.with_suffix(".srt")
            )

        if progress_callback:
            progress_callback(100, "语音合成完成")

        logger.info(f"CosyVoice local completed: {audio_path}, duration: {duration:.2f}s")

        return TTSResult(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            duration=duration,
            sample_rate=self.config.sample_rate,
        )

    async def _synthesize_edge_tts(
        self,
        text: str,
        output_path: Path,
        voice: str,
        generate_subtitle: bool,
        progress_callback: Callable[[float, str], None] | None,
    ) -> TTSResult:
        """Synthesize using edge-tts."""
        import edge_tts

        logger.info(f"Edge-TTS synthesizing: {text[:50]}...")

        # Map voice name to edge-tts voice
        edge_voice = self.EDGE_TTS_VOICES.get(voice, "zh-CN-YunxiNeural")

        # Calculate rate string
        rate = self.config.speed
        if rate >= 1.0:
            rate_str = f"+{int((rate - 1) * 100)}%"
        else:
            rate_str = f"-{int((1 - rate) * 100)}%"

        # Create communicate instance
        communicate = edge_tts.Communicate(text, edge_voice, rate=rate_str)

        # Output path
        audio_path = output_path.with_suffix(".mp3")

        if progress_callback:
            progress_callback(30, "生成语音...")

        # Generate audio and subtitles
        submaker = edge_tts.SubMaker()
        async with aiofiles.open(audio_path, "wb") as audio_file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    await audio_file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)

        if progress_callback:
            progress_callback(70, "保存字幕文件...")

        # Get duration
        duration = self.get_audio_duration(audio_path)

        # Generate subtitle
        subtitle_path = None
        if generate_subtitle:
            # New edge-tts API: get_srt() returns SRT format directly
            subtitle_path = output_path.with_suffix(".srt")
            srt_content = submaker.get_srt()

            if srt_content and srt_content.strip():
                # Use edge-tts generated SRT directly
                async with aiofiles.open(subtitle_path, "w", encoding="utf-8") as srt_file:
                    await srt_file.write(srt_content)
            else:
                # Fallback: generate subtitle from text and duration
                subtitle_path = await self._generate_subtitle(
                    text, duration, subtitle_path
                )

        if progress_callback:
            progress_callback(100, "语音合成完成")

        logger.info(f"Edge-TTS completed: {audio_path}, duration: {duration:.2f}s")

        return TTSResult(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            duration=duration,
            sample_rate=24000,  # edge-tts default
        )

    def _adjust_speed(self, audio: "np.ndarray", speed: float) -> "np.ndarray":
        """Adjust audio playback speed."""
        import librosa

        return librosa.effects.time_stretch(audio, rate=speed)

    async def _generate_subtitle(
        self,
        text: str,
        duration: float,
        output_path: Path,
    ) -> Path:
        """Generate subtitle file for synthesized speech."""
        segments = self._split_text_to_segments(text, duration)
        subtitle_file = SubtitleFile(segments=segments)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
            await f.write(subtitle_file.to_srt())

        return output_path

    def _split_text_to_segments(
        self,
        text: str,
        total_duration: float,
        max_chars: int = 15,
    ) -> list[SubtitleSegment]:
        """Split text into subtitle segments with timing."""
        # Split by Chinese punctuation
        parts = re.split(r"([，。！？、；：,.!?;:])", text)

        # Merge parts with their punctuation
        merged_parts = []
        current = ""
        for part in parts:
            if not part:
                continue
            if re.match(r"[，。！？、；：,.!?;:]", part):
                current += part
            else:
                if current:
                    merged_parts.append(current)
                current = part
        if current:
            merged_parts.append(current)

        # Further split if still too long
        final_parts = []
        for part in merged_parts:
            if len(part) <= max_chars:
                final_parts.append(part)
            else:
                for i in range(0, len(part), max_chars):
                    final_parts.append(part[i : i + max_chars])

        # Calculate timing
        total_chars = sum(len(p) for p in final_parts)
        chars_per_second = total_chars / total_duration if total_duration > 0 else 5

        segments = []
        current_time = 0.0

        for i, part in enumerate(final_parts):
            if not part.strip():
                continue

            part_duration = len(part) / chars_per_second
            end_time = min(current_time + part_duration, total_duration)

            segments.append(
                SubtitleSegment(
                    index=i + 1,
                    start_time=current_time,
                    end_time=end_time,
                    text=part.strip(),
                )
            )
            current_time = end_time

        return segments

    async def clone_voice(
        self,
        reference_audio: Path,
        voice_name: str,
        reference_text: str,
    ) -> str:
        """Clone a voice from reference audio (CosyVoice only)."""
        if not reference_audio.exists():
            raise TTSError(f"Reference audio not found: {reference_audio}")

        self._ensure_initialized()

        if self._backend not in ("cosyvoice_api", "cosyvoice_local"):
            raise TTSError("Voice cloning requires CosyVoice backend")

        logger.info(f"Voice cloned: {voice_name}")
        return voice_name

    async def synthesize_with_clone(
        self,
        text: str,
        output_path: Path,
        reference_audio: Path,
        reference_text: str,
        generate_subtitle: bool = True,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> TTSResult:
        """Synthesize speech using cloned voice (CosyVoice only)."""
        if not text.strip():
            raise TTSError("Empty text provided")

        if not reference_audio.exists():
            raise TTSError(f"Reference audio not found: {reference_audio}")

        self._ensure_initialized()

        if self._backend not in ("cosyvoice_api", "cosyvoice_local"):
            raise TTSError("Voice cloning requires CosyVoice backend")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(10, f"克隆语音合成: {text[:20]}...")

        try:
            import numpy as np

            logger.info(f"Synthesizing with cloned voice: {text[:50]}...")

            audio_segments = []
            for output in self._model.inference_zero_shot(
                text, reference_text, str(reference_audio)
            ):
                audio_segments.append(output["tts_speech"].numpy())

            if not audio_segments:
                raise TTSError("No audio generated")

            audio_data = np.concatenate(audio_segments, axis=0).flatten()

            if progress_callback:
                progress_callback(70, "保存音频文件...")

            audio_path = output_path.with_suffix(".wav")
            sf.write(str(audio_path), audio_data, self.config.sample_rate)

            duration = len(audio_data) / self.config.sample_rate

            subtitle_path = None
            if generate_subtitle:
                if progress_callback:
                    progress_callback(85, "生成字幕文件...")
                subtitle_path = await self._generate_subtitle(
                    text, duration, output_path.with_suffix(".srt")
                )

            if progress_callback:
                progress_callback(100, "语音合成完成")

            logger.info(f"TTS completed: {audio_path}, duration: {duration:.2f}s")

            return TTSResult(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                duration=duration,
                sample_rate=self.config.sample_rate,
            )

        except Exception as e:
            logger.error(f"TTS with clone failed: {e}")
            raise TTSError(f"Speech synthesis with clone failed: {e}")

    def list_voices(self) -> list[str]:
        """List available preset voices."""
        return self.PRESET_VOICES.copy()

    def get_backend(self) -> str:
        """Get current TTS backend name."""
        self._ensure_initialized()
        return self._backend or "unknown"

    @staticmethod
    def get_audio_duration(audio_path: Path) -> float:
        """Get audio file duration in seconds."""
        if audio_path.suffix.lower() == ".mp3":
            audio = MP3(str(audio_path))
            return audio.info.length
        else:
            info = sf.info(str(audio_path))
            return info.duration
