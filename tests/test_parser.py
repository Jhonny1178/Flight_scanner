"""Unit tests for flight parsers."""

from flight_scanner.parsers.base_parser import SampleCharterParser


def test_parser_normalizes_valid_offer():
    parser = SampleCharterParser()
    raw = {
        "offers": [
            {
                "id": "deal-101",
                "origin": "WAW",
                "destination": "AYT",
                "departure_date": "2026-07-01",
                "price": 299.99,
                "currency": "PLN",
                "operator": "SunCharter",
                "url": "https://book.now/101",
            }
        ]
    }
    parsed = parser.parse_offers(raw)
    assert len(parsed) == 1
    deal = parsed[0]
    assert deal["offer_id"] == "deal-101"
    assert deal["origin"] == "WAW"
    assert deal["destination"] == "AYT"
    assert deal["price"] == 299.99
    assert deal["currency"] == "PLN"
    assert deal["booking_url"] == "https://book.now/101"


def test_parser_skips_malformed_items():
    parser = SampleCharterParser()
    raw = {
        "offers": [
            {"id": "deal-valid", "origin": "WAW", "destination": "HER", "departure_date": "2026-06-10", "price": 400},
            {"id": "deal-missing-price", "origin": "WAW", "destination": "HER", "departure_date": "2026-06-10"},
            {"id": "deal-invalid-price", "origin": "WAW", "destination": "HER", "departure_date": "2026-06-10", "price": "free_ticket"},
            "not-a-dict",
        ]
    }
    parsed = parser.parse_offers(raw)
    assert len(parsed) == 1
    assert parsed[0]["offer_id"] == "deal-valid"


def test_parser_handles_empty_or_invalid_payload():
    parser = SampleCharterParser()
    assert parser.parse_offers({}) == []
    assert parser.parse_offers({"other_key": 123}) == []
