"""ASR (Automatic Speech Recognition) service using FunASR."""

from pathlib import Path
from typing import Callable

from loguru import logger

from playlet_clip.core.config import ASRSettings
from playlet_clip.core.exceptions import ASRError
from playlet_clip.models.subtitle import SubtitleFile, SubtitleSegment


class ASRService:
    """ASR service based on FunASR."""

    def __init__(self, config: ASRSettings):
        """
        Initialize ASR service.

        Args:
            config: ASR configuration
        """
        self.config = config
        self._model = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Ensure model is loaded."""
        if self._initialized:
            return

        try:
            from funasr import AutoModel

            logger.info(f"Loading ASR model: {self.config.model_name}")
            logger.info(f"Device: {self.config.device}")

            self._model = AutoModel(
                model=self.config.model_name,
                vad_model=self.config.vad_model,
                punc_model=self.config.punc_model,
                device=self.config.device,
            )

            self._initialized = True
            logger.info("ASR model loaded successfully")

        except ImportError as e:
            raise ASRError(f"FunASR not installed: {e}")
        except Exception as e:
            raise ASRError(f"Failed to load ASR model: {e}")

    async def transcribe(
        self,
        audio_path: Path,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> SubtitleFile:
        """
        Transcribe audio to subtitles.

        Args:
            audio_path: Path to audio file (WAV format, 16kHz recommended)
            progress_callback: Optional callback for progress updates

        Returns:
            SubtitleFile with transcribed segments
        """
        if not audio_path.exists():
            raise ASRError(f"Audio file not found: {audio_path}")

        self._ensure_initialized()

        if progress_callback:
            progress_callback(10, "开始语音识别...")

        try:
            logger.info(f"Transcribing: {audio_path}")

            # Run ASR inference
            result = self._model.generate(
                input=str(audio_path),
                batch_size_s=self.config.batch_size * 300,  # seconds per batch
                hotword="",
            )

            if progress_callback:
                progress_callback(80, "解析识别结果...")

            # Parse results to subtitle segments
            segments = self._parse_result(result)

            if progress_callback:
                progress_callback(100, "语音识别完成")

            logger.info(f"Transcription completed: {len(segments)} segments")
            return SubtitleFile(segments=segments)

        except Exception as e:
            logger.error(f"ASR failed: {e}")
            raise ASRError(f"Transcription failed: {e}")

    def _parse_result(self, result: list) -> list[SubtitleSegment]:
        """
        Parse FunASR result to subtitle segments.

        Args:
            result: FunASR output

        Returns:
            List of SubtitleSegment
        """
        segments = []

        if not result:
            return segments

        # FunASR returns a list of results
        for item in result:
            if not isinstance(item, dict):
                continue

            # Get text and timestamps
            text = item.get("text", "")
            timestamp = item.get("timestamp", [])

            if not text:
                continue

            # If we have word-level timestamps
            if timestamp and isinstance(timestamp, list) and len(timestamp) > 0:
                segments.extend(self._parse_timestamps(text, timestamp))
            else:
                # No timestamps, create single segment
                # Try to get sentence info
                sentence_info = item.get("sentence_info", [])
                if sentence_info:
                    segments.extend(self._parse_sentence_info(sentence_info))
                else:
                    # Fallback: single segment with estimated timing
                    segments.append(
                        SubtitleSegment(
                            index=len(segments) + 1,
                            start_time=0,
                            end_time=len(text) / 5,  # ~5 chars per second
                            text=text,
                        )
                    )

        return segments

    def _parse_timestamps(
        self,
        text: str,
        timestamp: list,
    ) -> list[SubtitleSegment]:
        """Parse word-level timestamps to sentence segments."""
        segments = []

        # Group by sentences (split by punctuation)
        current_text = ""
        current_start = None
        current_end = None

        chars = list(text)
        timestamp_idx = 0

        for char in chars:
            if timestamp_idx < len(timestamp):
                ts = timestamp[timestamp_idx]
                start_ms = ts[0] if isinstance(ts, (list, tuple)) else ts
                end_ms = ts[1] if isinstance(ts, (list, tuple)) and len(ts) > 1 else start_ms + 100

                if current_start is None:
                    current_start = start_ms / 1000

                current_end = end_ms / 1000
                timestamp_idx += 1

            current_text += char

            # Split on sentence-ending punctuation
            if char in "。！？.!?":
                if current_text.strip() and current_start is not None:
                    segments.append(
                        SubtitleSegment(
                            index=len(segments) + 1,
                            start_time=current_start,
                            end_time=current_end or current_start + 1,
                            text=current_text.strip(),
                        )
                    )
                current_text = ""
                current_start = None
                current_end = None

        # Handle remaining text
        if current_text.strip() and current_start is not None:
            segments.append(
                SubtitleSegment(
                    index=len(segments) + 1,
                    start_time=current_start,
                    end_time=current_end or current_start + 1,
                    text=current_text.strip(),
                )
            )

        return segments

    def _parse_sentence_info(self, sentence_info: list) -> list[SubtitleSegment]:
        """Parse sentence_info from FunASR result."""
        segments = []

        for i, sent in enumerate(sentence_info):
            text = sent.get("text", "")
            start = sent.get("start", 0) / 1000  # Convert ms to seconds
            end = sent.get("end", 0) / 1000

            if text.strip():
                segments.append(
                    SubtitleSegment(
                        index=i + 1,
                        start_time=start,
                        end_time=end,
                        text=text.strip(),
                    )
                )

        return segments

    async def transcribe_to_srt(
        self,
        audio_path: Path,
        output_path: Path,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> Path:
        """
        Transcribe audio and save to SRT file.

        Args:
            audio_path: Path to audio file
            output_path: Path for output SRT file
            progress_callback: Optional callback for progress updates

        Returns:
            Path to saved SRT file
        """
        subtitle_file = await self.transcribe(audio_path, progress_callback)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(subtitle_file.to_srt())

        logger.info(f"SRT saved to: {output_path}")
        return output_path
