"""SRT file parsing and generation utilities."""

import re
from pathlib import Path

from playlet_clip.models.subtitle import SubtitleFile, SubtitleSegment


class SRTParser:
    """Parser for SRT subtitle files."""

    # Regex patterns for SRT parsing
    TIME_PATTERN = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
    )

    @classmethod
    def parse_file(cls, file_path: Path, encoding: str = "utf-8") -> SubtitleFile:
        """
        Parse an SRT file.

        Args:
            file_path: Path to SRT file
            encoding: File encoding

        Returns:
            SubtitleFile containing parsed segments
        """
        with open(file_path, "r", encoding=encoding) as f:
            content = f.read()
        return cls.parse_string(content)

    @classmethod
    def parse_string(cls, content: str) -> SubtitleFile:
        """
        Parse SRT format string.

        Args:
            content: SRT format string

        Returns:
            SubtitleFile containing parsed segments
        """
        segments = []

        # Remove BOM if present
        content = content.lstrip("\ufeff")

        # Split by double newlines (subtitle blocks)
        blocks = re.split(r"\n\s*\n", content.strip())

        for block in blocks:
            segment = cls._parse_block(block)
            if segment:
                segments.append(segment)

        # Re-index segments
        for i, seg in enumerate(segments, 1):
            seg.index = i

        return SubtitleFile(segments=segments)

    @classmethod
    def _parse_block(cls, block: str) -> SubtitleSegment | None:
        """Parse a single subtitle block."""
        lines = block.strip().split("\n")
        if len(lines) < 2:
            return None

        # Find time line
        time_line_idx = -1
        for i, line in enumerate(lines):
            if cls.TIME_PATTERN.search(line):
                time_line_idx = i
                break

        if time_line_idx == -1:
            return None

        # Parse time
        match = cls.TIME_PATTERN.search(lines[time_line_idx])
        if not match:
            return None

        start_time = (
            int(match.group(1)) * 3600
            + int(match.group(2)) * 60
            + int(match.group(3))
            + int(match.group(4)) / 1000
        )
        end_time = (
            int(match.group(5)) * 3600
            + int(match.group(6)) * 60
            + int(match.group(7))
            + int(match.group(8)) / 1000
        )

        # Get text (all lines after time line)
        text_lines = lines[time_line_idx + 1 :]
        text = "\n".join(line.strip() for line in text_lines if line.strip())

        if not text:
            return None

        # Get index (line before time line, if exists)
        try:
            index = int(lines[time_line_idx - 1].strip()) if time_line_idx > 0 else 1
        except ValueError:
            index = 1

        return SubtitleSegment(
            index=index,
            start_time=start_time,
            end_time=end_time,
            text=text,
        )

    @classmethod
    def save_file(
        cls,
        subtitle_file: SubtitleFile,
        file_path: Path,
        encoding: str = "utf-8",
    ) -> None:
        """
        Save SubtitleFile to SRT file.

        Args:
            subtitle_file: SubtitleFile to save
            file_path: Output path
            encoding: File encoding
        """
        content = cls.generate_string(subtitle_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)

    @classmethod
    def generate_string(cls, subtitle_file: SubtitleFile) -> str:
        """
        Generate SRT format string.

        Args:
            subtitle_file: SubtitleFile to convert

        Returns:
            SRT format string
        """
        blocks = []
        for seg in subtitle_file.segments:
            blocks.append(seg.to_srt_block())
        return "\n".join(blocks)

    @classmethod
    def split_long_segments(
        cls,
        subtitle_file: SubtitleFile,
        max_chars: int = 15,
    ) -> SubtitleFile:
        """
        Split subtitle segments that are too long.

        Args:
            subtitle_file: Original SubtitleFile
            max_chars: Maximum characters per segment

        Returns:
            New SubtitleFile with split segments
        """
        new_segments = []

        for seg in subtitle_file.segments:
            if len(seg.text) <= max_chars:
                new_segments.append(seg)
            else:
                # Split by Chinese punctuation or max_chars
                split_segs = cls._split_segment(seg, max_chars)
                new_segments.extend(split_segs)

        # Re-index
        for i, seg in enumerate(new_segments, 1):
            seg.index = i

        return SubtitleFile(segments=new_segments)

    @classmethod
    def _split_segment(
        cls,
        segment: SubtitleSegment,
        max_chars: int,
    ) -> list[SubtitleSegment]:
        """Split a single segment into multiple segments."""
        text = segment.text
        duration = segment.duration
        chars_per_second = len(text) / duration if duration > 0 else 5

        # Split by Chinese punctuation first
        parts = re.split(r"([，。！？、；：])", text)
        merged_parts = []
        current = ""

        for part in parts:
            if not part:
                continue
            if len(current) + len(part) <= max_chars:
                current += part
            else:
                if current:
                    merged_parts.append(current)
                current = part

        if current:
            merged_parts.append(current)

        # Create new segments with distributed time
        segments = []
        current_time = segment.start_time

        for i, part in enumerate(merged_parts):
            part_duration = len(part) / chars_per_second
            end_time = min(current_time + part_duration, segment.end_time)

            segments.append(
                SubtitleSegment(
                    index=segment.index + i,
                    start_time=current_time,
                    end_time=end_time,
                    text=part,
                )
            )
            current_time = end_time

        return segments if segments else [segment]
