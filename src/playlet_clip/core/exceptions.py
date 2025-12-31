"""Custom exceptions for playlet-clip."""


class PlayletClipError(Exception):
    """Base exception for playlet-clip."""

    pass


class ConfigError(PlayletClipError):
    """Configuration related errors."""

    pass


class ASRError(PlayletClipError):
    """ASR (Automatic Speech Recognition) related errors."""

    pass


class TTSError(PlayletClipError):
    """TTS (Text-to-Speech) related errors."""

    pass


class LLMError(PlayletClipError):
    """LLM (Large Language Model) related errors."""

    pass


class VideoProcessingError(PlayletClipError):
    """Video processing related errors."""

    pass


class ValidationError(PlayletClipError):
    """Data validation errors."""

    pass
