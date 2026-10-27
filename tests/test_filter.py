"""Unit tests for the FlightFilter component and long-haul filtering."""

import pytest
from flight_scanner.core.filter import FlightFilter


def test_default_price_threshold():
    flight_filter = FlightFilter()
    assert flight_filter.price_threshold == 2500.0


def test_is_long_haul_excludes_all_blacklisted_keywords():
    flight_filter = FlightFilter()
    blacklisted = [
        "Turcja", "Madera", "Egipt", "Cypr", "Grecja", "Hiszpania",
        "Wyspy Kanaryjskie", "Portugalia", "Włochy", "Albania", "Bułgaria",
        "Czarnogóra", "Chorwacja", "Tunezja", "Maroko", "Teneryfa",
        "Fuerteventura", "Lanzarote", "Gran Canaria", "Antalya", "Bodrum", "Pafos"
    ]

    for keyword in blacklisted:
        # Test in route field (case-insensitive)
        flight_route = {"route": f"Lot do {keyword.lower()} WAW", "destination": "XYZ"}
        assert flight_filter.is_long_haul(flight_route) is False, f"Expected {keyword} to be excluded"

        # Test in destination field (case-insensitive)
        flight_dest = {"route": "WAW - XYZ", "destination": keyword.upper()}
        assert flight_filter.is_long_haul(flight_dest) is False, f"Expected {keyword} to be excluded"


def test_is_long_haul_accepts_exotic_destinations():
    flight_filter = FlightFilter()
    exotic_flights = [
        {"route": "Zanzibar WAW - ZNZ", "destination": "ZNZ"},
        {"route": "Mombasa KTW - MBA", "destination": "MBA"},
        {"route": "Cancun WAW - CUN", "destination": "CUN"},
        {"route": "Bangkok WAW - BKK", "destination": "BKK"},
        {"route": "Colombo WAW - CMB", "destination": "CMB"},
    ]

    for flight in exotic_flights:
        assert flight_filter.is_long_haul(flight) is True, f"Expected {flight['route']} to be accepted as long-haul"


def test_filter_offers_integrates_price_and_long_haul():
    flight_filter = FlightFilter(price_threshold=2500.0)
    offers = [
        # 1. Qualifying long-haul below threshold
        {"offer_id": "lh-1", "price": 1800.0, "route": "Zanzibar WAW - ZNZ", "destination": "ZNZ"},
        # 2. Qualifying long-haul exactly at threshold
        {"offer_id": "lh-2", "price": 2500.0, "route": "Cancun WAW - CUN", "destination": "CUN"},
        # 3. Long-haul exceeding threshold
        {"offer_id": "lh-expensive", "price": 2500.01, "route": "Mombasa KTW - MBA", "destination": "MBA"},
        # 4. Short-haul cheap deal (excluded by keyword "Madera")
        {"offer_id": "sh-madera", "price": 750.0, "route": "Madera KTW - FNC", "destination": "FNC"},
        # 5. Short-haul cheap deal (excluded by keyword "Antalya")
        {"offer_id": "sh-antalya", "price": 450.0, "route": "Antalya WAW - AYT", "destination": "AYT"},
    ]

    matching = flight_filter.filter_offers(offers)

    # Only lh-1 and lh-2 should pass
    assert len(matching) == 2
    assert matching[0]["offer_id"] == "lh-1"
    assert matching[1]["offer_id"] == "lh-2"


def test_filter_deals_alias_works_identically():
    flight_filter = FlightFilter(price_threshold=2500.0)
    offers = [
        {"offer_id": "1", "price": 1500.0, "route": "Zanzibar", "destination": "ZNZ"},
        {"offer_id": "2", "price": 600.0, "route": "Madera", "destination": "FNC"},
    ]
    matching = flight_filter.filter_deals(offers)
    assert len(matching) == 1
    assert matching[0]["offer_id"] == "1"


def test_filter_deals_skips_missing_or_invalid_price():
    flight_filter = FlightFilter(price_threshold=2500.0)
    offers = [
        {"offer_id": "1", "route": "Zanzibar"},  # Missing price
        {"offer_id": "2", "price": "corrupted", "route": "Zanzibar"},
        {"offer_id": "3", "price": 1950.0, "route": "Zanzibar", "destination": "ZNZ"},
    ]
    matching = flight_filter.filter_deals(offers)
    assert len(matching) == 1
    assert matching[0]["offer_id"] == "3"


def test_filter_deals_with_allowed_destinations():
    flight_filter = FlightFilter(price_threshold=2500.0, allowed_destinations=["ZNZ", "CUN"])
    offers = [
        {"offer_id": "1", "price": 1800.0, "destination": "ZNZ"},
        {"offer_id": "2", "price": 2000.0, "destination": "BKK"},  # Not allowed
        {"offer_id": "3", "price": 2200.0, "destination": "CUN"},
    ]
    matching = flight_filter.filter_deals(offers)
    assert len(matching) == 2
    assert [d["offer_id"] for d in matching] == ["1", "3"]
