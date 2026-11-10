"""Unit tests for TUI Charter parser and dynamic deep links."""

from flight_scanner.parsers.tui_parser import TUICharterParser


def test_tui_parser_generates_dynamic_deep_link():
    parser = TUICharterParser()
    raw = {
        "offers": [
            {
                "id": "tui-1",
                "departureAirport": "WAW",
                "arrivalAirport": "CUN",
                "airportCode": "CUN",
                "departureDate": "2026-11-20",
                "price": 2100.0,
                "currency": "PLN",
                "operator": "TUI Charter",
            }
        ]
    }

    offers = parser.parse_offers(raw)
    assert len(offers) == 1
    offer = offers[0]
    assert offer["url"] == "https://www.tui.pl/bilety-lotnicze?q=CUN"
    assert offer["booking_url"] == "https://www.tui.pl/bilety-lotnicze?q=CUN"
    assert offer["origin"] == "WAW"
    assert offer["destination"] == "CUN"


def test_tui_parser_fallback_airport_code():
    parser = TUICharterParser()
    raw = {
        "offers": [
            {
                "id": "tui-2",
                "departureAirport": "WAW",
                "arrivalAirport": "ZNZ",
                "departureDate": "2026-11-22",
                "price": 2300.0,
            }
        ]
    }

    offers = parser.parse_offers(raw)
    assert len(offers) == 1
    assert offers[0]["url"] == "https://www.tui.pl/bilety-lotnicze?q=ZNZ"
    assert offers[0]["booking_url"] == "https://www.tui.pl/bilety-lotnicze?q=ZNZ"
