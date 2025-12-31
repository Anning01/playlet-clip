"""Main processing pipeline for playlet-clip."""

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from loguru import logger

from playlet_clip.core.config import Settings
from playlet_clip.core.exceptions import PlayletClipError
from playlet_clip.models.segment import NarrationSegment
from playlet_clip.models.task import ProcessResult, TaskProgress, TaskStatus
from playlet_clip.services.asr import ASRService
from playlet_clip.services.llm import LLMService
from playlet_clip.services.tts import TTSService
from playlet_clip.services.video import VideoService


class PlayletPipeline:
    """Main processing pipeline that orchestrates all services."""

    def __init__(self, settings: Settings):
        """
        Initialize pipeline with settings.

        Args:
            settings: Application settings
        """
        self.settings = settings

        # Initialize services
        self.asr = ASRService(settings.asr)
        self.tts = TTSService(settings.tts)
        self.llm = LLMService(settings.llm)
        self.video = VideoService(settings.video)

        # Load default prompt template
        self._default_prompt_template = self._load_default_prompt()

        # Ensure directories exist
        settings.paths.ensure_dirs()

    def _load_default_prompt(self) -> str | None:
        """Load default prompt template from config/prompts/narrator.txt."""
        prompt_path = self.settings.paths.config_dir / "prompts" / "narrator.txt"
        if prompt_path.exists():
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    logger.info(f"Loaded prompt template from {prompt_path}")
                    return content
            except Exception as e:
                logger.warning(f"Failed to load prompt template: {e}")
        return None

    async def process(
        self,
        video_path: Path,
        style: str,
        output_path: Path | None = None,
        progress_callback: Callable[[TaskProgress], None] | None = None,
    ) -> ProcessResult:
        """
        Process a video with full pipeline.

        Args:
            video_path: Input video path
            style: Narration style name or description
            output_path: Output video path (optional, auto-generated if not provided)
            progress_callback: Callback for progress updates

        Returns:
            ProcessResult with output path and metadata
        """
        start_time = time.time()
        temp_dir = self.settings.paths.temp_dir / f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Determine output path
        if output_path is None:
            output_path = (
                self.settings.paths.output_dir
                / f"{video_path.stem}_{style}_{datetime.now().strftime('%H%M%S')}.mp4"
            )

        progress = TaskProgress(
            status=TaskStatus.PENDING,
            started_at=datetime.now(),
            total_steps=6,
        )

        def update_progress(status: TaskStatus, step: int, pct: float, msg: str):
            nonlocal progress
            progress = progress.update(
                status=status,
                current_step=step,
                progress=pct,
                message=msg,
            )
            if progress_callback:
                progress_callback(progress)
            logger.info(f"[Step {step}/6] {msg} ({pct:.0f}%)")

        try:
            # Step 1: Extract audio
            update_progress(TaskStatus.EXTRACTING_AUDIO, 1, 0, "提取音频中...")
            audio_path = temp_dir / "audio.wav"
            await self.video.extract_audio(
                video_path=video_path,
                output_path=audio_path,
                progress_callback=lambda p, m: update_progress(
                    TaskStatus.EXTRACTING_AUDIO, 1, p * 0.15, m
                ),
            )

            # Step 2: ASR - Transcribe audio
            update_progress(TaskStatus.TRANSCRIBING, 2, 15, "语音识别中...")
            subtitles = await self.asr.transcribe(
                audio_path=audio_path,
                progress_callback=lambda p, m: update_progress(
                    TaskStatus.TRANSCRIBING, 2, 15 + p * 0.15, m
                ),
            )

            # Save subtitles
            srt_path = temp_dir / "subtitles.srt"
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(subtitles.to_srt())
            logger.info(f"Subtitles saved: {srt_path}")

            # Step 3: Get video duration and generate narration
            update_progress(TaskStatus.GENERATING_NARRATION, 3, 30, "生成解说文案中...")
            video_duration = await self.video.get_duration(video_path)

            # Find style description and prompt template
            style_desc = style
            style_prompt_template = None
            for s in self.settings.styles:
                if s.name == style:
                    style_desc = f"{s.name}：{s.description}"
                    style_prompt_template = s.prompt_template
                    break

            # Use style-specific prompt, or default prompt, or LLM's built-in prompt
            prompt_template = style_prompt_template or self._default_prompt_template

            segments = await self.llm.generate_narration(
                subtitles=subtitles,
                video_duration=video_duration,
                style=style_desc,
                prompt_template=prompt_template,
                progress_callback=lambda p, m: update_progress(
                    TaskStatus.GENERATING_NARRATION, 3, 30 + p * 0.15, m
                ),
            )

            # Fill gaps between segments with video segments
            segments = self.llm.fill_gaps(segments, video_duration)
            logger.info(f"Total segments after gap filling: {len(segments)}")

            # Save narration JSON
            narration_path = temp_dir / "narration.json"
            await self.llm.save_narration_json(segments, narration_path)

            # Step 4: TTS - Synthesize narration audio
            update_progress(TaskStatus.SYNTHESIZING_SPEECH, 4, 45, "合成解说语音中...")
            await self._synthesize_narration_audio(
                segments=segments,
                temp_dir=temp_dir,
                progress_callback=lambda p, m: update_progress(
                    TaskStatus.SYNTHESIZING_SPEECH, 4, 45 + p * 0.2, m
                ),
            )

            # Step 5: Process video segments
            update_progress(TaskStatus.PROCESSING_VIDEO, 5, 65, "处理视频片段中...")
            final_video = await self.video.create_final_video(
                source_video=video_path,
                segments=segments,
                output_path=output_path,
                temp_dir=temp_dir,
                progress_callback=lambda p, m: update_progress(
                    TaskStatus.PROCESSING_VIDEO, 5, 65 + p * 0.3, m
                ),
            )

            # Step 6: Complete
            update_progress(TaskStatus.COMPLETED, 6, 100, "处理完成!")

            duration = time.time() - start_time

            return ProcessResult(
                success=True,
                output_path=final_video,
                duration=duration,
                segments_count=len(segments),
                subtitles_path=srt_path,
                narration_json_path=narration_path,
            )

        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            update_progress(TaskStatus.FAILED, progress.current_step, progress.progress, str(e))

            return ProcessResult(
                success=False,
                error_message=str(e),
                duration=time.time() - start_time,
            )

        finally:
            # Cleanup temp directory (optional)
            if self.settings.debug:
                logger.info(f"Debug mode: keeping temp dir {temp_dir}")
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def _synthesize_narration_audio(
        self,
        segments: list[NarrationSegment],
        temp_dir: Path,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> None:
        """Synthesize audio for narration segments."""
        narration_segments = [s for s in segments if s.is_narration]
        total = len(narration_segments)

        if total == 0:
            if progress_callback:
                progress_callback(100, "无需合成解说语音")
            return

        audio_dir = temp_dir / "tts"
        audio_dir.mkdir(exist_ok=True)

        for i, segment in enumerate(narration_segments):
            if progress_callback:
                pct = int((i / total) * 100)
                progress_callback(pct, f"合成语音 {i + 1}/{total}...")

            # Generate audio
            output_base = audio_dir / f"narration_{i:03d}"
            result = await self.tts.synthesize(
                text=segment.content,
                output_path=output_base,
                generate_subtitle=True,
            )

            # Update segment with generated paths
            segment.audio_path = result.audio_path
            segment.subtitle_path = result.subtitle_path

            # Update segment duration based on actual audio
            if result.duration > 0:
                # Adjust end time if audio is longer than planned
                actual_end = segment.start_time + result.duration
                if actual_end > segment.end_time:
                    logger.warning(
                        f"Segment {i}: audio duration ({result.duration:.2f}s) "
                        f"exceeds planned ({segment.duration:.2f}s)"
                    )
                    segment.end_time = actual_end

            logger.info(f"TTS completed for segment {i}: {result.audio_path}")

        if progress_callback:
            progress_callback(100, "解说语音合成完成")

    async def process_with_existing_subtitles(
        self,
        video_path: Path,
        srt_path: Path,
        style: str,
        output_path: Path | None = None,
        progress_callback: Callable[[TaskProgress], None] | None = None,
    ) -> ProcessResult:
        """
        Process video with existing SRT subtitles (skip ASR).

        Args:
            video_path: Input video path
            srt_path: Existing SRT subtitle path
            style: Narration style
            output_path: Output video path
            progress_callback: Progress callback

        Returns:
            ProcessResult
        """
        from playlet_clip.utils.srt import SRTParser

        start_time = time.time()
        temp_dir = self.settings.paths.temp_dir / f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        if output_path is None:
            output_path = (
                self.settings.paths.output_dir
                / f"{video_path.stem}_{style}_{datetime.now().strftime('%H%M%S')}.mp4"
            )

        progress = TaskProgress(
            status=TaskStatus.PENDING,
            started_at=datetime.now(),
            total_steps=5,
        )

        def update_progress(status: TaskStatus, step: int, pct: float, msg: str):
            nonlocal progress
            progress = progress.update(
                status=status,
                current_step=step,
                progress=pct,
                message=msg,
            )
            if progress_callback:
                progress_callback(progress)

        try:
            # Load subtitles
            update_progress(TaskStatus.TRANSCRIBING, 1, 0, "加载字幕文件...")
            subtitles = SRTParser.parse_file(srt_path)
            update_progress(TaskStatus.TRANSCRIBING, 1, 10, "字幕加载完成")

            # Generate narration
            update_progress(TaskStatus.GENERATING_NARRATION, 2, 10, "生成解说文案...")
            video_duration = await self.video.get_duration(video_path)

            # Find style description and prompt template
            style_desc = style
            style_prompt_template = None
            for s in self.settings.styles:
                if s.name == style:
                    style_desc = f"{s.name}：{s.description}"
                    style_prompt_template = s.prompt_template
                    break

            # Use style-specific prompt, or default prompt, or LLM's built-in prompt
            prompt_template = style_prompt_template or self._default_prompt_template

            segments = await self.llm.generate_narration(
                subtitles=subtitles,
                video_duration=video_duration,
                style=style_desc,
                prompt_template=prompt_template,
                progress_callback=lambda p, m: update_progress(
                    TaskStatus.GENERATING_NARRATION, 2, 10 + p * 0.2, m
                ),
            )

            # Fill gaps between segments with video segments
            segments = self.llm.fill_gaps(segments, video_duration)
            logger.info(f"Total segments after gap filling: {len(segments)}")

            # Save narration
            narration_path = temp_dir / "narration.json"
            await self.llm.save_narration_json(segments, narration_path)

            # TTS
            update_progress(TaskStatus.SYNTHESIZING_SPEECH, 3, 30, "合成解说语音...")
            await self._synthesize_narration_audio(
                segments=segments,
                temp_dir=temp_dir,
                progress_callback=lambda p, m: update_progress(
                    TaskStatus.SYNTHESIZING_SPEECH, 3, 30 + p * 0.3, m
                ),
            )

            # Video processing
            update_progress(TaskStatus.PROCESSING_VIDEO, 4, 60, "处理视频...")
            final_video = await self.video.create_final_video(
                source_video=video_path,
                segments=segments,
                output_path=output_path,
                temp_dir=temp_dir,
                progress_callback=lambda p, m: update_progress(
                    TaskStatus.PROCESSING_VIDEO, 4, 60 + p * 0.35, m
                ),
            )

            update_progress(TaskStatus.COMPLETED, 5, 100, "处理完成!")

            return ProcessResult(
                success=True,
                output_path=final_video,
                duration=time.time() - start_time,
                segments_count=len(segments),
                subtitles_path=srt_path,
                narration_json_path=narration_path,
            )

        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            update_progress(TaskStatus.FAILED, progress.current_step, progress.progress, str(e))

            return ProcessResult(
                success=False,
                error_message=str(e),
                duration=time.time() - start_time,
            )

        finally:
            if not self.settings.debug:
                shutil.rmtree(temp_dir, ignore_errors=True)
