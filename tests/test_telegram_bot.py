"""Unit tests for TelegramNotifier."""

from unittest.mock import MagicMock, patch
import requests
from flight_scanner.notifiers.telegram_bot import TelegramNotifier


def test_telegram_is_configured():
    notifier_valid = TelegramNotifier(token="123:ABC", chat_id="456")
    assert notifier_valid.is_configured() is True

    notifier_empty = TelegramNotifier(token="", chat_id="")
    assert notifier_empty.is_configured() is False


def test_format_deal_message():
    notifier = TelegramNotifier(token="test", chat_id="123")
    deal = {
        "offer_id": "d-1",
        "origin": "WAW",
        "destination": "HER",
        "departure_date": "2026-06-15",
        "return_date": "2026-06-22",
        "price": 299.0,
        "currency": "PLN",
        "airline_or_operator": "Rainbow",
        "booking_url": "https://example.com/deal",
    }
    msg = notifier.format_deal_message(deal)
    assert "WAW" in msg
    assert "HER" in msg
    assert "299.00 PLN" in msg
    assert "Rainbow" in msg
    assert "https://example.com/deal" in msg


def test_send_message_success():
    notifier = TelegramNotifier(token="123:ABC", chat_id="456")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}

    with patch.object(notifier.session, "post", return_value=mock_resp):
        success = notifier.send_message("Test message")
        assert success is True


def test_send_message_network_error():
    notifier = TelegramNotifier(token="123:ABC", chat_id="456")

    with patch.object(
        notifier.session, "post", side_effect=requests.exceptions.ConnectionError("DNS failure")
    ):
        success = notifier.send_message("Test message")
        assert success is False
