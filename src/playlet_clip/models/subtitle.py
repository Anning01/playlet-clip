"""Subtitle data structures."""

from pydantic import BaseModel, Field


class SubtitleSegment(BaseModel):
    """A single subtitle segment with timing information."""

    index: int = Field(description="Subtitle index (1-based)")
    start_time: float = Field(ge=0, description="Start time in seconds")
    end_time: float = Field(ge=0, description="End time in seconds")
    text: str = Field(description="Subtitle text content")

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self.end_time - self.start_time

    def to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def to_srt_block(self) -> str:
        """Convert to SRT format block."""
        start = self.to_srt_time(self.start_time)
        end = self.to_srt_time(self.end_time)
        return f"{self.index}\n{start} --> {end}\n{self.text}\n"

    @classmethod
    def from_srt_time(cls, time_str: str) -> float:
        """Parse SRT time format to seconds."""
        # Handle both comma and dot as millisecond separator
        time_str = time_str.replace(",", ".")
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds


class SubtitleFile(BaseModel):
    """Collection of subtitle segments."""

    segments: list[SubtitleSegment] = Field(default_factory=list)

    @property
    def total_duration(self) -> float:
        """Total duration covered by subtitles."""
        if not self.segments:
            return 0.0
        return max(seg.end_time for seg in self.segments)

    def to_srt(self) -> str:
        """Convert to SRT format string."""
        return "\n".join(seg.to_srt_block() for seg in self.segments)

    @classmethod
    def from_srt(cls, srt_content: str) -> "SubtitleFile":
        """Parse SRT format string."""
        segments = []
        blocks = srt_content.strip().split("\n\n")

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue

            try:
                index = int(lines[0])
                time_parts = lines[1].split(" --> ")
                start_time = SubtitleSegment.from_srt_time(time_parts[0].strip())
                end_time = SubtitleSegment.from_srt_time(time_parts[1].strip())
                text = "\n".join(lines[2:])

                segments.append(
                    SubtitleSegment(
                        index=index,
                        start_time=start_time,
                        end_time=end_time,
                        text=text,
                    )
                )
            except (ValueError, IndexError):
                continue

        return cls(segments=segments)
