"""FFmpeg command wrapper utilities."""

import asyncio
import json
import shutil
from pathlib import Path

from loguru import logger

from playlet_clip.core.exceptions import VideoProcessingError


class FFmpegWrapper:
    """Wrapper for FFmpeg commands."""

    def __init__(self):
        """Initialize FFmpeg wrapper."""
        self.ffmpeg_path = shutil.which("ffmpeg")
        self.ffprobe_path = shutil.which("ffprobe")

        if not self.ffmpeg_path:
            raise VideoProcessingError("FFmpeg not found in PATH")
        if not self.ffprobe_path:
            raise VideoProcessingError("FFprobe not found in PATH")

    async def get_video_duration(self, video_path: Path) -> float:
        """
        Get video duration in seconds.

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds
        """
        cmd = [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(video_path),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise VideoProcessingError(f"FFprobe failed: {stderr.decode()}")

            data = json.loads(stdout.decode())
            return float(data["format"]["duration"])
        except (json.JSONDecodeError, KeyError) as e:
            raise VideoProcessingError(f"Failed to parse video duration: {e}")

    async def extract_audio(
        self,
        video_path: Path,
        output_path: Path,
        sample_rate: int = 16000,
        mono: bool = True,
    ) -> Path:
        """
        Extract audio from video.

        Args:
            video_path: Input video path
            output_path: Output audio path
            sample_rate: Audio sample rate
            mono: Whether to convert to mono

        Returns:
            Output audio path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
        ]

        if mono:
            cmd.extend(["-ac", "1"])

        cmd.append(str(output_path))

        await self._run_command(cmd, "Audio extraction")
        return output_path

    async def trim_video(
        self,
        video_path: Path,
        output_path: Path,
        start_time: float,
        duration: float,
    ) -> Path:
        """
        Trim video segment.

        Args:
            video_path: Input video path
            output_path: Output video path
            start_time: Start time in seconds
            duration: Duration in seconds

        Returns:
            Output video path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Re-encode to ensure consistent timestamps for concatenation
        # Using -c copy can cause timestamp issues when concatenating
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-ss",
            str(start_time),
            "-i",
            str(video_path),
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-ar",
            "24000",  # Consistent sample rate for all segments
            "-ac",
            "2",  # Stereo
            "-b:a",
            "128k",
            str(output_path),
        ]

        await self._run_command(cmd, "Video trimming")
        return output_path

    async def add_narration(
        self,
        video_path: Path,
        audio_path: Path,
        subtitle_path: Path,
        output_path: Path,
        blur_height: int = 185,
        blur_y: int = 1413,
        blur_sigma: int = 20,
        subtitle_margin: int = 65,
        original_volume: float = 0.3,
        narration_volume: float = 1.0,
    ) -> Path:
        """
        Add narration audio and subtitle to video with blur effect.

        The original audio is mixed with the narration audio (not replaced).
        Original audio volume is reduced during narration to make it clearer.

        Args:
            video_path: Input video path
            audio_path: Narration audio path
            subtitle_path: Subtitle file path
            output_path: Output video path
            blur_height: Blur region height
            blur_y: Blur region Y position
            blur_sigma: Gaussian blur sigma
            subtitle_margin: Subtitle vertical margin
            original_volume: Original audio volume (0.0-1.0), default 0.3 to reduce background
            narration_volume: Narration audio volume (0.0-1.0), default 1.0

        Returns:
            Output video path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Escape subtitle path for FFmpeg filter (handle special characters)
        subtitle_path_escaped = str(subtitle_path).replace("\\", "/").replace(":", "\\:")

        # Build filter complex:
        # 1. Video: blur effect + subtitles
        # 2. Audio: mix original (reduced volume) + narration
        # Note: Using Noto Sans CJK SC font for Chinese character support
        filter_complex = (
            # Video processing
            f"[0:v]crop=iw:{blur_height}:0:{blur_y},gblur=sigma={blur_sigma}[blur];"
            f"[0:v][blur]overlay=0:{blur_y},"
            f"subtitles='{subtitle_path_escaped}':force_style='FontName=Noto Sans CJK SC,MarginV={subtitle_margin}'[vout];"
            # Audio processing: adjust volumes and mix
            f"[0:a]volume={original_volume}[a0];"
            f"[1:a]volume={narration_volume}[a1];"
            f"[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0[aout]"
        )

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            "-ar",
            "24000",
            "-ac",
            "2",
            str(output_path),
        ]

        await self._run_command(cmd, "Adding narration")
        return output_path

    async def concat_videos(
        self,
        video_paths: list[Path],
        output_path: Path,
    ) -> Path:
        """
        Concatenate multiple videos.

        Args:
            video_paths: List of video paths to concatenate
            output_path: Output video path

        Returns:
            Output video path
        """
        if not video_paths:
            raise VideoProcessingError("No videos to concatenate")

        if len(video_paths) == 1:
            shutil.copy(video_paths[0], output_path)
            return output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use filter_complex concat for better timestamp handling
        # This re-encodes but ensures proper audio/video sync
        n = len(video_paths)

        # Build input arguments
        input_args = []
        for vp in video_paths:
            input_args.extend(["-i", str(vp)])

        # Build filter_complex string
        # Format: [0:v][0:a][1:v][1:a]...concat=n=N:v=1:a=1[outv][outa]
        filter_inputs = "".join(f"[{i}:v][{i}:a]" for i in range(n))
        filter_complex = f"{filter_inputs}concat=n={n}:v=1:a=1[outv][outa]"

        cmd = [
            self.ffmpeg_path,
            "-y",
            *input_args,
            "-filter_complex",
            filter_complex,
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "24000",  # Consistent sample rate
            "-ac",
            "2",  # Stereo
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        await self._run_command(cmd, "Video concatenation")
        return output_path

    async def _run_command(self, cmd: list[str], operation: str) -> None:
        """Run FFmpeg command."""
        logger.debug(f"Running {operation}: {' '.join(cmd)}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"{operation} failed: {error_msg}")
            raise VideoProcessingError(f"{operation} failed: {error_msg}")

        logger.debug(f"{operation} completed successfully")
