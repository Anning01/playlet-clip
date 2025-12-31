"""Pytest configuration and shared fixtures."""

import asyncio
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from playlet_clip.core.config import (
    ASRSettings,
    LLMSettings,
    PathSettings,
    Settings,
    TTSSettings,
    VideoSettings,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temporary directories."""
    return Settings(
        llm=LLMSettings(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
        ),
        asr=ASRSettings(
            device="cpu",  # Use CPU for testing
        ),
        tts=TTSSettings(
            backend="edge_tts",  # Use edge_tts for testing (no GPU required)
            device="cpu",
        ),
        video=VideoSettings(),
        paths=PathSettings(
            base_dir=temp_dir,
            input_dir=temp_dir / "input",
            output_dir=temp_dir / "output",
            temp_dir=temp_dir / "temp",
        ),
        debug=True,
    )


@pytest.fixture
def sample_video_path() -> Path | None:
    """Get sample video path for testing.

    Place a test video at data/input/test.mp4 for integration tests.
    Returns None if no test video exists.
    """
    project_root = Path(__file__).parent.parent
    test_video = project_root / "data" / "input" / "test.mp4"
    if test_video.exists():
        return test_video
    return None


@pytest.fixture
def sample_audio_path() -> Path | None:
    """Get sample audio path for testing.

    Place a test audio at data/input/test.wav for ASR tests.
    Returns None if no test audio exists.
    """
    project_root = Path(__file__).parent.parent
    test_audio = project_root / "data" / "input" / "test.wav"
    if test_audio.exists():
        return test_audio
    return None


@pytest.fixture
def sample_srt_content() -> str:
    """Sample SRT content for testing."""
    return """1
00:00:00,000 --> 00:00:03,000
这是第一句字幕

2
00:00:03,000 --> 00:00:06,000
这是第二句字幕

3
00:00:06,000 --> 00:00:10,000
这是第三句字幕
"""


@pytest.fixture
def sample_subtitles() -> list[dict]:
    """Sample subtitle segments for testing."""
    return [
        {"index": 1, "start_time": 0.0, "end_time": 3.0, "text": "这是第一句字幕"},
        {"index": 2, "start_time": 3.0, "end_time": 6.0, "text": "这是第二句字幕"},
        {"index": 3, "start_time": 6.0, "end_time": 10.0, "text": "这是第三句字幕"},
    ]
