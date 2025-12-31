"""Time calculation utilities."""

from datetime import timedelta


class TimeUtils:
    """Utility class for time calculations."""

    @staticmethod
    def seconds_to_srt(seconds: float) -> str:
        """
        Convert seconds to SRT time format.

        Args:
            seconds: Time in seconds

        Returns:
            Time string in format "HH:MM:SS,mmm"
        """
        if seconds < 0:
            seconds = 0

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def srt_to_seconds(time_str: str) -> float:
        """
        Convert SRT time format to seconds.

        Args:
            time_str: Time string in format "HH:MM:SS,mmm" or "HH:MM:SS.mmm"

        Returns:
            Time in seconds
        """
        time_str = time_str.strip().replace(",", ".")
        parts = time_str.split(":")

        if len(parts) != 3:
            return 0.0

        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except (ValueError, IndexError):
            return 0.0

    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format duration for display.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string like "1h 23m 45s" or "23m 45s" or "45s"
        """
        td = timedelta(seconds=int(seconds))
        hours, remainder = divmod(td.seconds, 3600)
        minutes, secs = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    @staticmethod
    def calculate_time_difference(start: str, end: str) -> float:
        """
        Calculate time difference between two SRT time strings.

        Args:
            start: Start time in SRT format
            end: End time in SRT format

        Returns:
            Difference in seconds
        """
        start_seconds = TimeUtils.srt_to_seconds(start)
        end_seconds = TimeUtils.srt_to_seconds(end)
        return max(0, end_seconds - start_seconds)

    @staticmethod
    def add_seconds(time_str: str, seconds: float) -> str:
        """
        Add seconds to an SRT time string.

        Args:
            time_str: Time string in SRT format
            seconds: Seconds to add

        Returns:
            New time string in SRT format
        """
        base_seconds = TimeUtils.srt_to_seconds(time_str)
        new_seconds = max(0, base_seconds + seconds)
        return TimeUtils.seconds_to_srt(new_seconds)

    @staticmethod
    def estimate_speech_duration(text: str, chars_per_second: float = 5.0) -> float:
        """
        Estimate speech duration for given text.

        Args:
            text: Text to speak
            chars_per_second: Characters per second (default 5 for Chinese)

        Returns:
            Estimated duration in seconds
        """
        # Remove whitespace and punctuation for more accurate estimate
        clean_text = "".join(c for c in text if c.isalnum() or "\u4e00" <= c <= "\u9fff")
        return len(clean_text) / chars_per_second

    @staticmethod
    def parse_time_range(time_range: str) -> tuple[float, float]:
        """
        Parse SRT time range string.

        Args:
            time_range: Time range string like "00:00:00,000 --> 00:00:03,000"

        Returns:
            Tuple of (start_seconds, end_seconds)
        """
        parts = time_range.split(" --> ")
        if len(parts) != 2:
            return 0.0, 0.0

        start = TimeUtils.srt_to_seconds(parts[0])
        end = TimeUtils.srt_to_seconds(parts[1])
        return start, end
