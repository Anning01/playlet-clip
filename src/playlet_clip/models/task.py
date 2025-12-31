"""Task and progress data structures."""

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task processing status."""

    PENDING = "pending"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    GENERATING_NARRATION = "generating_narration"
    SYNTHESIZING_SPEECH = "synthesizing_speech"
    PROCESSING_VIDEO = "processing_video"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskProgress(BaseModel):
    """Task progress information."""

    status: TaskStatus = Field(default=TaskStatus.PENDING)
    progress: float = Field(default=0.0, ge=0, le=100, description="Progress percentage")
    message: str = Field(default="", description="Status message")
    current_step: int = Field(default=0, ge=0, description="Current step number")
    total_steps: int = Field(default=0, ge=0, description="Total number of steps")
    started_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)

    def update(
        self,
        status: TaskStatus | None = None,
        progress: float | None = None,
        message: str | None = None,
        current_step: int | None = None,
        total_steps: int | None = None,
    ) -> "TaskProgress":
        """Update progress and return new instance."""
        return TaskProgress(
            status=status if status is not None else self.status,
            progress=progress if progress is not None else self.progress,
            message=message if message is not None else self.message,
            current_step=current_step if current_step is not None else self.current_step,
            total_steps=total_steps if total_steps is not None else self.total_steps,
            started_at=self.started_at,
            updated_at=datetime.now(),
        )


class ProcessResult(BaseModel):
    """Result of video processing."""

    success: bool = Field(description="Whether processing succeeded")
    output_path: Path | None = Field(default=None, description="Output video path")
    error_message: str | None = Field(default=None, description="Error message if failed")
    duration: float = Field(default=0.0, description="Processing duration in seconds")
    segments_count: int = Field(default=0, description="Number of segments processed")

    # Intermediate results
    subtitles_path: Path | None = Field(default=None, description="Extracted subtitles path")
    narration_json_path: Path | None = Field(default=None, description="Generated narration JSON")
