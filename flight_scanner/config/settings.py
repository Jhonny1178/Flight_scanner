"""Application configuration loader for the Flight Scanner system.

Loads and validates required environment variables with explicit typing
and fallback defaults to avoid hardcoded credentials or thresholds.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv

    # Look for .env in current directory or project root
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables."""

    telegram_token: str
    chat_id: str
    price_threshold: float
    api_endpoint_url: str
    request_timeout_seconds: int = 15
    max_retries: int = 3
    retry_backoff_factor: float = 1.0
    currency: str = "PLN"
    log_level: str = "INFO"

    def is_telegram_configured(self) -> bool:
        """Checks if Telegram bot credentials are fully provided."""
        return bool(self.telegram_token.strip() and self.chat_id.strip())

    def validate(self) -> None:
        """Validates critical numerical boundaries and configuration consistency.

        Raises:
            ValueError: If values are invalid (e.g., negative price threshold).
        """
        if self.price_threshold <= 0:
            raise ValueError(
                f"PRICE_THRESHOLD must be greater than 0, got {self.price_threshold}"
            )
        if self.request_timeout_seconds <= 0:
            raise ValueError(
                f"REQUEST_TIMEOUT_SECONDS must be positive, got {self.request_timeout_seconds}"
            )
        if self.max_retries < 0:
            raise ValueError(
                f"MAX_RETRIES cannot be negative, got {self.max_retries}"
            )
        if not self.api_endpoint_url:
            raise ValueError("API_ENDPOINT_URL must not be empty.")


def load_settings(env_file: Optional[Path] = None) -> Settings:
    """Loads configuration from environment variables with strong typing.

    Args:
        env_file: Optional custom path to a .env file.

    Returns:
        Settings: Fully validated application settings instance.

    Raises:
        ValueError: If environment variables contain unparseable values.
    """
    if env_file and env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=env_file, override=True)
        except ImportError:
            logger.warning(
                "python-dotenv not installed, reading from os.environ directly."
            )

    telegram_token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat_id = os.getenv("CHAT_ID", "").strip()

    price_threshold_raw = os.getenv("PRICE_THRESHOLD", "500.0").strip()
    try:
        price_threshold = float(price_threshold_raw)
    except ValueError as err:
        raise ValueError(
            f"Invalid float for PRICE_THRESHOLD: '{price_threshold_raw}'"
        ) from err

    api_endpoint_url = os.getenv(
        "API_ENDPOINT_URL",
        "https://api.example.com/charter-flights",
    ).strip()

    timeout_raw = os.getenv("REQUEST_TIMEOUT_SECONDS", "15").strip()
    try:
        request_timeout_seconds = int(timeout_raw)
    except ValueError as err:
        raise ValueError(
            f"Invalid integer for REQUEST_TIMEOUT_SECONDS: '{timeout_raw}'"
        ) from err

    retries_raw = os.getenv("MAX_RETRIES", "3").strip()
    try:
        max_retries = int(retries_raw)
    except ValueError as err:
        raise ValueError(
            f"Invalid integer for MAX_RETRIES: '{retries_raw}'"
        ) from err

    backoff_raw = os.getenv("RETRY_BACKOFF_FACTOR", "1.0").strip()
    try:
        retry_backoff_factor = float(backoff_raw)
    except ValueError as err:
        raise ValueError(
            f"Invalid float for RETRY_BACKOFF_FACTOR: '{backoff_raw}'"
        ) from err

    currency = os.getenv("CURRENCY", "PLN").strip().upper()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()

    settings = Settings(
        telegram_token=telegram_token,
        chat_id=chat_id,
        price_threshold=price_threshold,
        api_endpoint_url=api_endpoint_url,
        request_timeout_seconds=request_timeout_seconds,
        max_retries=max_retries,
        retry_backoff_factor=retry_backoff_factor,
        currency=currency,
        log_level=log_level,
    )

    settings.validate()
    return settings
