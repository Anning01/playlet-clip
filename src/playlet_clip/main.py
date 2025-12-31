"""Main entry point for playlet-clip."""

import sys
from pathlib import Path

from loguru import logger

from playlet_clip.core.config import get_settings


def setup_cosyvoice_path() -> None:
    """Setup PYTHONPATH for CosyVoice if installed locally."""
    # Check if CosyVoice is installed in third_party
    project_root = Path(__file__).parent.parent.parent.parent
    cosyvoice_dir = project_root / "third_party" / "CosyVoice"

    if cosyvoice_dir.exists():
        paths_to_add = [
            str(cosyvoice_dir),
            str(cosyvoice_dir / "third_party" / "Matcha-TTS"),
        ]

        for path in paths_to_add:
            if path not in sys.path:
                sys.path.insert(0, path)

        logger.debug(f"CosyVoice path configured: {cosyvoice_dir}")


def setup_logging(debug: bool = False) -> None:
    """Setup logging configuration."""
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, format=log_format, level=level, colorize=True)


def main() -> None:
    """Main entry point."""
    # Setup CosyVoice path if installed locally
    setup_cosyvoice_path()

    # Load settings
    settings = get_settings()

    # Setup logging
    setup_logging(settings.debug)

    logger.info("Starting Playlet-Clip v2.0")
    logger.info(f"Debug mode: {settings.debug}")

    # Ensure directories exist
    settings.paths.ensure_dirs()

    # Launch UI
    from playlet_clip.ui import launch_app

    launch_app(
        settings=settings,
        share=settings.ui_share,
        server_name=settings.ui_host,
        server_port=settings.ui_port,
    )


if __name__ == "__main__":
    main()
