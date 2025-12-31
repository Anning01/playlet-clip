"""Video processing service."""

from pathlib import Path
from typing import Callable

from loguru import logger

from playlet_clip.core.config import VideoSettings
from playlet_clip.core.exceptions import VideoProcessingError
from playlet_clip.models.segment import NarrationSegment
from playlet_clip.utils.ffmpeg import FFmpegWrapper


class VideoService:
    """Video processing service using FFmpeg."""

    def __init__(self, config: VideoSettings):
        """
        Initialize video service.

        Args:
            config: Video processing configuration
        """
        self.config = config
        self._ffmpeg = FFmpegWrapper()

    async def get_duration(self, video_path: Path) -> float:
        """
        Get video duration in seconds.

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds
        """
        if not video_path.exists():
            raise VideoProcessingError(f"Video file not found: {video_path}")

        return await self._ffmpeg.get_video_duration(video_path)

    async def extract_audio(
        self,
        video_path: Path,
        output_path: Path,
        sample_rate: int = 16000,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> Path:
        """
        Extract audio from video for ASR.

        Args:
            video_path: Input video path
            output_path: Output audio path
            sample_rate: Audio sample rate (16kHz for ASR)
            progress_callback: Progress callback

        Returns:
            Path to extracted audio
        """
        if not video_path.exists():
            raise VideoProcessingError(f"Video file not found: {video_path}")

        if progress_callback:
            progress_callback(10, "提取音频...")

        output_path = await self._ffmpeg.extract_audio(
            video_path=video_path,
            output_path=output_path,
            sample_rate=sample_rate,
            mono=True,
        )

        if progress_callback:
            progress_callback(100, "音频提取完成")

        logger.info(f"Audio extracted: {output_path}")
        return output_path

    async def trim(
        self,
        video_path: Path,
        start_time: float,
        duration: float,
        output_path: Path,
    ) -> Path:
        """
        Trim video segment.

        Args:
            video_path: Input video path
            start_time: Start time in seconds
            duration: Duration in seconds
            output_path: Output video path

        Returns:
            Path to trimmed video
        """
        if not video_path.exists():
            raise VideoProcessingError(f"Video file not found: {video_path}")

        return await self._ffmpeg.trim_video(
            video_path=video_path,
            output_path=output_path,
            start_time=start_time,
            duration=duration,
        )

    async def add_narration(
        self,
        video_path: Path,
        audio_path: Path,
        subtitle_path: Path,
        output_path: Path,
    ) -> Path:
        """
        Add narration audio and subtitle to video.

        The original audio is mixed with narration (not replaced),
        with reduced volume during narration.

        Args:
            video_path: Input video path
            audio_path: Narration audio path
            subtitle_path: Subtitle file path
            output_path: Output video path

        Returns:
            Path to processed video
        """
        if not video_path.exists():
            raise VideoProcessingError(f"Video file not found: {video_path}")
        if not audio_path.exists():
            raise VideoProcessingError(f"Audio file not found: {audio_path}")
        if not subtitle_path.exists():
            raise VideoProcessingError(f"Subtitle file not found: {subtitle_path}")

        return await self._ffmpeg.add_narration(
            video_path=video_path,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            blur_height=self.config.blur_height,
            blur_y=self.config.blur_y,
            blur_sigma=self.config.blur_sigma,
            subtitle_margin=self.config.subtitle_margin,
            original_volume=self.config.original_volume,
            narration_volume=self.config.narration_volume,
        )

    async def concat(
        self,
        video_paths: list[Path],
        output_path: Path,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> Path:
        """
        Concatenate multiple videos.

        Args:
            video_paths: List of video paths
            output_path: Output video path
            progress_callback: Progress callback

        Returns:
            Path to concatenated video
        """
        if not video_paths:
            raise VideoProcessingError("No videos to concatenate")

        for vp in video_paths:
            if not vp.exists():
                raise VideoProcessingError(f"Video file not found: {vp}")

        if progress_callback:
            progress_callback(10, f"合并 {len(video_paths)} 个视频片段...")

        output = await self._ffmpeg.concat_videos(video_paths, output_path)

        if progress_callback:
            progress_callback(100, "视频合并完成")

        logger.info(f"Videos concatenated: {output}")
        return output

    async def process_segment(
        self,
        source_video: Path,
        segment: NarrationSegment,
        output_path: Path,
        temp_dir: Path,
        segment_index: int,
    ) -> Path:
        """
        Process a single narration segment.

        Args:
            source_video: Source video path
            segment: Narration segment to process
            output_path: Output video path
            temp_dir: Temporary directory for intermediate files
            segment_index: Segment index for naming

        Returns:
            Path to processed segment video
        """
        temp_dir.mkdir(parents=True, exist_ok=True)

        if segment.is_narration:
            # For narration segments, audio and subtitle should already be generated
            if not segment.audio_path or not segment.audio_path.exists():
                raise VideoProcessingError(
                    f"Segment {segment_index}: audio not found at {segment.audio_path}"
                )
            if not segment.subtitle_path or not segment.subtitle_path.exists():
                raise VideoProcessingError(
                    f"Segment {segment_index}: subtitle not found at {segment.subtitle_path}"
                )

            # Trim video to segment duration
            trimmed_path = temp_dir / f"seg_{segment_index}_trimmed.mp4"
            await self.trim(
                video_path=source_video,
                start_time=segment.start_time,
                duration=segment.duration,
                output_path=trimmed_path,
            )

            # Add narration
            await self.add_narration(
                video_path=trimmed_path,
                audio_path=segment.audio_path,
                subtitle_path=segment.subtitle_path,
                output_path=output_path,
            )

            # Cleanup
            trimmed_path.unlink(missing_ok=True)

        else:
            # For video segments, just trim
            await self.trim(
                video_path=source_video,
                start_time=segment.start_time,
                duration=segment.duration,
                output_path=output_path,
            )

        return output_path

    async def process_all_segments(
        self,
        source_video: Path,
        segments: list[NarrationSegment],
        output_dir: Path,
        temp_dir: Path,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> list[Path]:
        """
        Process all segments.

        Args:
            source_video: Source video path
            segments: List of narration segments
            output_dir: Output directory for segment videos
            temp_dir: Temporary directory
            progress_callback: Progress callback

        Returns:
            List of processed segment video paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        processed_paths = []

        total = len(segments)
        for i, segment in enumerate(segments):
            if progress_callback:
                progress = int((i / total) * 100)
                progress_callback(progress, f"处理片段 {i + 1}/{total}...")

            output_path = output_dir / f"segment_{i:03d}.mp4"
            await self.process_segment(
                source_video=source_video,
                segment=segment,
                output_path=output_path,
                temp_dir=temp_dir,
                segment_index=i,
            )
            processed_paths.append(output_path)

            logger.info(f"Processed segment {i + 1}/{total}")

        if progress_callback:
            progress_callback(100, "所有片段处理完成")

        return processed_paths

    async def create_final_video(
        self,
        source_video: Path,
        segments: list[NarrationSegment],
        output_path: Path,
        temp_dir: Path,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> Path:
        """
        Create final video from segments.

        Args:
            source_video: Source video path
            segments: List of narration segments
            output_path: Final output path
            temp_dir: Temporary directory
            progress_callback: Progress callback

        Returns:
            Path to final video
        """
        temp_dir.mkdir(parents=True, exist_ok=True)
        segments_dir = temp_dir / "segments"

        # Process all segments
        if progress_callback:
            progress_callback(0, "开始处理视频片段...")

        segment_paths = await self.process_all_segments(
            source_video=source_video,
            segments=segments,
            output_dir=segments_dir,
            temp_dir=temp_dir / "processing",
            progress_callback=lambda p, m: progress_callback(p * 0.8, m)
            if progress_callback
            else None,
        )

        # Concatenate all segments
        if progress_callback:
            progress_callback(80, "合并视频片段...")

        final_path = await self.concat(segment_paths, output_path)

        # Cleanup segment files
        for sp in segment_paths:
            sp.unlink(missing_ok=True)

        if progress_callback:
            progress_callback(100, "视频制作完成")

        logger.info(f"Final video created: {final_path}")
        return final_path
