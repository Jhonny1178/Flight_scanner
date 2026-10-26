"""Unit tests for settings and environment loading."""

import pytest
from flight_scanner.config.settings import Settings, load_settings


def test_settings_validation_success():
    settings = Settings(
        telegram_token="token_123",
        chat_id="chat_456",
        price_threshold=450.0,
        api_endpoint_url="https://api.example.com/flights",
    )
    settings.validate()
    assert settings.is_telegram_configured() is True
    assert settings.price_threshold == 450.0


def test_settings_validation_invalid_price():
    settings = Settings(
        telegram_token="",
        chat_id="",
        price_threshold=-10.0,
        api_endpoint_url="https://api.example.com/flights",
    )
    with pytest.raises(ValueError, match="PRICE_THRESHOLD must be greater than 0"):
        settings.validate()


def test_settings_validation_invalid_timeout():
    settings = Settings(
        telegram_token="",
        chat_id="",
        price_threshold=500.0,
        api_endpoint_url="https://api.example.com/flights",
        request_timeout_seconds=0,
    )
    with pytest.raises(ValueError, match="REQUEST_TIMEOUT_SECONDS must be positive"):
        settings.validate()


def test_load_settings_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "mock_bot_token")
    monkeypatch.setenv("CHAT_ID", "999888")
    monkeypatch.setenv("PRICE_THRESHOLD", "350.50")
    monkeypatch.setenv("API_ENDPOINT_URL", "https://api.flights.mock/deals")

    settings = load_settings()
    assert settings.telegram_token == "mock_bot_token"
    assert settings.chat_id == "999888"
    assert settings.price_threshold == 350.50
    assert settings.api_endpoint_url == "https://api.flights.mock/deals"
