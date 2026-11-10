"""Unit tests for TelegramNotifier."""

from unittest.mock import MagicMock, patch
import requests
from flight_scanner.notifiers.telegram_bot import TelegramNotifier


def test_telegram_is_configured():
    notifier_valid = TelegramNotifier(token="123:ABC", chat_id="456")
    assert notifier_valid.is_configured() is True

    notifier_empty = TelegramNotifier(token="", chat_id="")
    assert notifier_empty.is_configured() is False


def test_format_deal_message_basic():
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


def test_format_deal_message_with_region_asia():
    notifier = TelegramNotifier(token="test", chat_id="123")
    deal = {
        "offer_id": "asia-1",
        "origin": "WAW",
        "destination": "BKK",
        "route": "Bangkok WAW - BKK",
        "departure_date": "2026-11-15",
        "price": 850.0,
        "currency": "PLN",
        "airline_or_operator": "Enter Air",
        "booking_url": "https://r.pl/bilety-czarterowe/tajlandia/bangkok",
        "_region": "ASIA",
        "_region_cap": 1000.0,
    }
    msg = notifier.format_deal_message(deal)
    assert "🌏 Azja" in msg
    assert "1000" in msg
    assert "850.00 PLN" in msg
    assert "BKK" in msg
    assert "tajlandia/bangkok" in msg


def test_format_deal_message_with_region_africa_america():
    notifier = TelegramNotifier(token="test", chat_id="123")
    deal = {
        "offer_id": "znz-1",
        "origin": "WAW",
        "destination": "ZNZ",
        "route": "Zanzibar WAW - ZNZ",
        "departure_date": "2026-11-18",
        "price": 1350.0,
        "currency": "PLN",
        "airline_or_operator": "Rainbow (Enter Air)",
        "booking_url": "https://r.pl/bilety-czarterowe/tanzania/zanzibar",
        "_region": "AFRICA_AMERICA",
        "_region_cap": 1500.0,
    }
    msg = notifier.format_deal_message(deal)
    assert "🌍 Afryka / Ameryki" in msg
    assert "1500" in msg
    assert "1350.00 PLN" in msg
    assert "Zarezerwuj lot teraz" in msg


def test_format_deal_message_no_region_metadata():
    """Without _region/_region_cap the message still renders cleanly."""
    notifier = TelegramNotifier(token="test", chat_id="123")
    deal = {
        "offer_id": "d-2",
        "origin": "WAW",
        "destination": "ZNZ",
        "departure_date": "2026-11-20",
        "price": 1400.0,
        "currency": "PLN",
        "airline_or_operator": "Enter Air",
        "booking_url": "https://r.pl/bilety-czarterowe/szukaj?przylot=ZNZ",
    }
    msg = notifier.format_deal_message(deal)
    assert "ZNZ" in msg
    assert "1400.00 PLN" in msg
    # No region label should appear when not present
    assert "🌏" not in msg
    assert "🌍" not in msg
    assert "Limit cenowy" not in msg


def test_format_deal_message_html_escaping():
    notifier = TelegramNotifier(token="test", chat_id="123")
    deal = {
        "origin": "<WAW>",
        "destination": "BKK & More",
        "departure_date": '2026-11-15 "confirmed"',
        "price": 500.0,
        "currency": "PLN",
        "airline_or_operator": "Enter & Air",
        "booking_url": "https://r.pl/bilety?q=BKK&type=one-way",
    }
    msg = notifier.format_deal_message(deal)
    # Raw unescaped < > must not be in the main text nodes
    assert "<WAW>" not in msg
    assert "&lt;WAW&gt;" in msg


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
