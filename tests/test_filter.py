"""Unit tests for the FlightFilter component."""

from flight_scanner.core.filter import FlightFilter


def test_filter_deals_by_price_threshold():
    flight_filter = FlightFilter(price_threshold=500.0)
    offers = [
        {"offer_id": "1", "price": 300.0, "origin": "WAW", "destination": "HER"},
        {"offer_id": "2", "price": 500.0, "origin": "WAW", "destination": "AYT"},
        {"offer_id": "3", "price": 500.01, "origin": "WAW", "destination": "CHQ"},
        {"offer_id": "4", "price": 850.0, "origin": "WAW", "destination": "RHO"},
    ]
    matching = flight_filter.filter_deals(offers)
    assert len(matching) == 2
    # Sorted by price ascending
    assert matching[0]["offer_id"] == "1"
    assert matching[1]["offer_id"] == "2"


def test_filter_deals_skips_missing_or_invalid_price():
    flight_filter = FlightFilter(price_threshold=600.0)
    offers = [
        {"offer_id": "1", "origin": "WAW"},  # Missing price
        {"offer_id": "2", "price": "corrupted"},
        {"offer_id": "3", "price": 250.0},
    ]
    matching = flight_filter.filter_deals(offers)
    assert len(matching) == 1
    assert matching[0]["offer_id"] == "3"


def test_filter_deals_with_allowed_destinations():
    flight_filter = FlightFilter(price_threshold=500.0, allowed_destinations=["HER", "AYT"])
    offers = [
        {"offer_id": "1", "price": 300.0, "destination": "HER"},
        {"offer_id": "2", "price": 350.0, "destination": "BCN"},  # Not allowed
        {"offer_id": "3", "price": 400.0, "destination": "AYT"},
    ]
    matching = flight_filter.filter_deals(offers)
    assert len(matching) == 2
    assert [d["offer_id"] for d in matching] == ["1", "3"]
