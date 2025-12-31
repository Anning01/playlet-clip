"""LLM (Large Language Model) service for narration generation."""

import json
import re
from pathlib import Path
from typing import Callable

from loguru import logger
from openai import AsyncOpenAI

from playlet_clip.core.config import LLMSettings
from playlet_clip.core.exceptions import LLMError, ValidationError
from playlet_clip.models.segment import NarrationSegment
from playlet_clip.models.subtitle import SubtitleFile


class LLMService:
    """LLM service for generating narration scripts."""

    DEFAULT_PROMPT_TEMPLATE = """# 影视剪辑文案助手

你来充当一位有编剧写作编辑专家。

## 任务

根据内容中的srt字幕告诉你要生成的剪辑的内容，你的任务是根据这个内容和我指定的风格构建出一套影视解说内容，能让读者快速获得文章的要点或精髓，让文章引人入胜；能让读者了解全文中的重要信息、分析和论点；帮助读者记住影视内容的要点。

## 背景介绍

srt是一个字幕文件，其中包含段落坐标，段落内容，时间起始与结尾。

## 输出示例

[
    {
        "type": "解说",
        "content": "注意看，这个叫xx的人：",
        "time": "00:00:00,000 --> 00:00:03,319"
    },
    {
        "type": "video",
        "time": "00:00:05,560 --> 00:00:10,319"
    }
    ...
]
### 示例值说明

- type：分解说和视频片段内容，解说要求内容要和原字幕时间内容大概意思对应。

- content：内容，你根据风格编写的内容。

- time：时间段，要求大致估算解说需要的时间，解说尽量放在没有字幕出现的时间段上，解说的时间段和video的时间段间隔不要太近，以免出现重复的视频内容。（解说每秒5个字）


## 1.要求

- 解说只讲解关键有趣的部分，主要还是以视频片段为主。

- 要给解说留出语音的时间，防止和视频片段重合。

- 称号主角为这个男人，女主为这个女人，其他配角起一些好记有梗的名字，如：韩梅梅，李雷，小白菜等...

- 结尾片段要视频原片的结尾（大概取视频尾部10 ~ 30秒 ）

- 时间段要涵盖整个视频

- 解说尽量放在没有字幕出现的时间段上，给没有人物说话的时候解说最合适。

## 2. 限制：

- 你只需要返回我输出示例格式要求，不需要做任何解释。
"""

    def __init__(self, config: LLMSettings):
        """
        Initialize LLM service.

        Args:
            config: LLM configuration
        """
        self.config = config
        self._client: AsyncOpenAI | None = None

    def _ensure_client(self) -> AsyncOpenAI:
        """Ensure OpenAI client is initialized."""
        if self._client is None:
            if not self.config.api_key:
                raise LLMError("OpenAI API key not configured")

            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
        return self._client

    async def generate_narration(
        self,
        subtitles: SubtitleFile,
        video_duration: float,
        style: str,
        prompt_template: str | None = None,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> list[NarrationSegment]:
        """
        Generate narration script from subtitles.

        Args:
            subtitles: Transcribed subtitles
            video_duration: Video duration in seconds
            style: Narration style description
            prompt_template: Custom prompt template (optional)
            progress_callback: Optional callback for progress updates

        Returns:
            List of NarrationSegment
        """
        client = self._ensure_client()
        prompt = prompt_template or self.DEFAULT_PROMPT_TEMPLATE

        if progress_callback:
            progress_callback(10, "准备生成解说文案...")

        # Format video duration
        duration_str = self._format_duration(video_duration)

        # Build SRT content
        srt_content = subtitles.to_srt()

        # Build messages
        messages = [
            {
                "role": "system",
                "content": f"{prompt}\n\n视频总长度：{duration_str}\n\n字幕内容：\n{srt_content}",
            },
            {
                "role": "user",
                "content": f"请根据以上字幕内容，按照{style}生成解说文案。",
            },
        ]

        # Try generation with retries
        for attempt in range(self.config.max_retries):
            try:
                if progress_callback:
                    progress = 20 + (attempt * 60 // self.config.max_retries)
                    progress_callback(progress, f"生成解说文案... (尝试 {attempt + 1})")

                logger.info(f"Generating narration, attempt {attempt + 1}")

                response = await client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                )

                content = response.choices[0].message.content
                if not content:
                    raise LLMError("Empty response from LLM")
                logger.info(f"LLM response: {content}")

                # Parse and validate response
                segments = self._parse_response(content)
                self._validate_segments(segments, video_duration)

                if progress_callback:
                    progress_callback(100, "解说文案生成完成")

                logger.info(f"Narration generated: {len(segments)} segments")
                return segments

            except ValidationError as e:
                logger.warning(f"Validation failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    # Add error feedback for next attempt
                    messages.append(
                        {
                            "role": "assistant",
                            "content": content,
                        }
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": f"格式验证失败：{e}。请重新生成，确保JSON格式正确。",
                        }
                    )
                else:
                    raise LLMError(f"Failed after {self.config.max_retries} attempts: {e}")

            except Exception as e:
                logger.error(f"LLM request failed: {e}")
                if attempt >= self.config.max_retries - 1:
                    raise LLMError(f"LLM request failed: {e}")

        raise LLMError("Failed to generate narration")

    def _parse_response(self, content: str) -> list[NarrationSegment]:
        """Parse LLM response to narration segments."""
        # Extract JSON from response
        json_match = re.search(r"\[[\s\S]*\]", content)
        if not json_match:
            raise ValidationError("No valid JSON array found in response")

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")

        if not isinstance(data, list):
            raise ValidationError("Response must be a JSON array")

        segments = []
        for item in data:
            if not isinstance(item, dict):
                raise ValidationError("Each item must be an object")

            segment = NarrationSegment.from_llm_response(item)
            segments.append(segment)

        return segments

    def _validate_segments(
        self,
        segments: list[NarrationSegment],
        video_duration: float,
    ) -> None:
        """Validate narration segments."""
        if not segments:
            raise ValidationError("No segments generated")

        prev_end = 0.0

        for i, seg in enumerate(segments):
            # Validate type
            if seg.type not in ("解说", "video"):
                raise ValidationError(f"Segment {i}: invalid type '{seg.type}'")

            # Validate content for narration
            if seg.is_narration and not seg.content:
                raise ValidationError(f"Segment {i}: narration missing content")

            # Validate time format
            if seg.start_time < 0 or seg.end_time < 0:
                raise ValidationError(f"Segment {i}: invalid time values")

            if seg.end_time <= seg.start_time:
                raise ValidationError(f"Segment {i}: end time must be after start time")

            # Validate time sequence
            if seg.start_time < prev_end - 0.5:  # Allow 0.5s overlap tolerance
                raise ValidationError(
                    f"Segment {i}: start time {seg.start_time:.2f} "
                    f"overlaps with previous end {prev_end:.2f}"
                )

            # Validate within video duration
            if seg.end_time > video_duration + 1:  # Allow 1s tolerance
                raise ValidationError(
                    f"Segment {i}: end time {seg.end_time:.2f} "
                    f"exceeds video duration {video_duration:.2f}"
                )

            prev_end = seg.end_time

    def fill_gaps(
        self,
        segments: list[NarrationSegment],
        video_duration: float,
        min_gap: float = 0.5,
    ) -> list[NarrationSegment]:
        """
        Fill gaps between segments with video segments.

        Args:
            segments: List of narration segments
            video_duration: Total video duration
            min_gap: Minimum gap to fill (in seconds)

        Returns:
            List of segments with gaps filled
        """
        if not segments:
            return segments

        # Sort by start time
        sorted_segments = sorted(segments, key=lambda s: s.start_time)
        filled_segments = []
        prev_end = 0.0

        for seg in sorted_segments:
            # Check for gap before this segment
            gap = seg.start_time - prev_end
            if gap > min_gap:
                # Add a video segment to fill the gap
                gap_segment = NarrationSegment(
                    type="video",
                    start_time=prev_end,
                    end_time=seg.start_time,
                )
                filled_segments.append(gap_segment)
                logger.info(f"Filled gap: {prev_end:.2f}s - {seg.start_time:.2f}s")

            filled_segments.append(seg)
            prev_end = seg.end_time

        # Check for gap at the end
        if video_duration - prev_end > min_gap:
            end_segment = NarrationSegment(
                type="video",
                start_time=prev_end,
                end_time=video_duration,
            )
            filled_segments.append(end_segment)
            logger.info(f"Filled end gap: {prev_end:.2f}s - {video_duration:.2f}s")

        return filled_segments

    def _format_duration(self, seconds: float) -> str:
        """Format duration to HH:MM:SS,mmm."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    async def generate_narration_from_srt_file(
        self,
        srt_path: Path,
        video_duration: float,
        style: str,
        prompt_template: str | None = None,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> list[NarrationSegment]:
        """
        Generate narration from SRT file.

        Args:
            srt_path: Path to SRT file
            video_duration: Video duration in seconds
            style: Narration style description
            prompt_template: Custom prompt template
            progress_callback: Progress callback

        Returns:
            List of NarrationSegment
        """
        from playlet_clip.utils.srt import SRTParser

        if not srt_path.exists():
            raise LLMError(f"SRT file not found: {srt_path}")

        subtitles = SRTParser.parse_file(srt_path)

        return await self.generate_narration(
            subtitles=subtitles,
            video_duration=video_duration,
            style=style,
            prompt_template=prompt_template,
            progress_callback=progress_callback,
        )

    async def save_narration_json(
        self,
        segments: list[NarrationSegment],
        output_path: Path,
    ) -> Path:
        """
        Save narration segments to JSON file.

        Args:
            segments: List of narration segments
            output_path: Output file path

        Returns:
            Path to saved file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = [
            {
                "type": seg.type,
                "content": seg.content,
                "time": seg.time_str,
            }
            for seg in segments
        ]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Narration saved to: {output_path}")
        return output_path
