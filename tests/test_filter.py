"""Unit tests for the FlightFilter component, regional pricing, and last-minute filtering."""

from datetime import datetime, timedelta
import pytest
from flight_scanner.core.filter import (
    FlightFilter,
    MAX_DAYS_AHEAD,
    ASIA_PRICE_CAP,
    AFRICA_AMERICA_PRICE_CAP,
)


def test_default_constants_and_configuration():
    flight_filter = FlightFilter()
    assert flight_filter.price_threshold == 2500.0
    assert flight_filter.max_days_ahead == MAX_DAYS_AHEAD == 21
    assert flight_filter.asia_price_cap == ASIA_PRICE_CAP == 1000.0
    assert flight_filter.africa_america_price_cap == AFRICA_AMERICA_PRICE_CAP == 1500.0


def test_is_long_haul_excludes_all_blacklisted_keywords():
    flight_filter = FlightFilter()
    blacklisted = [
        "Turcja", "Madera", "Egipt", "Cypr", "Grecja", "Hiszpania",
        "Wyspy Kanaryjskie", "Portugalia", "Włochy", "Albania", "Bułgaria",
        "Czarnogóra", "Chorwacja", "Tunezja", "Maroko", "Teneryfa",
        "Fuerteventura", "Lanzarote", "Gran Canaria", "Antalya", "Bodrum", "Pafos",
        "Hurghada", "Marsa Alam", "Djerba", "Agadir", "Kreta", "Rodos", "Zakynthos",
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
        {"route": "Phuket WAW - HKT", "destination": "HKT"},
        {"route": "Phu Quoc WAW - PQC", "destination": "PQC"},
        {"route": "Punta Cana WAW - PUJ", "destination": "PUJ"},
        {"route": "Bogota WAW - BOG", "destination": "BOG"},
    ]

    for flight in exotic_flights:
        assert flight_filter.is_long_haul(flight) is True, f"Expected {flight['route']} to be accepted as long-haul"


def test_is_last_minute_evaluations():
    flight_filter = FlightFilter()
    now = datetime.now()

    # a) Placeholder strings -> True
    assert flight_filter.is_last_minute({"departure_date": "Terminy na stronie"}) is True
    assert flight_filter.is_last_minute({"departure_date": "terminy na stronie"}) is True
    assert flight_filter.is_last_minute({"departure_date": "Sprawdź daty"}) is True
    assert flight_filter.is_last_minute({"departure_date": None}) is True
    assert flight_filter.is_last_minute({}) is True

    # b & c) Real date strings ("YYYY-MM-DD")
    # Departing today (difference = 0) -> True
    today_str = now.strftime("%Y-%m-%d")
    assert flight_filter.is_last_minute({"departure_date": today_str}) is True

    # Departing in 10 days -> True
    in_10_days = (now + timedelta(days=10)).strftime("%Y-%m-%d")
    assert flight_filter.is_last_minute({"departure_date": in_10_days}) is True

    # Departing in exactly 21 days -> True (MAX_DAYS_AHEAD inclusive boundary)
    in_21_days = (now + timedelta(days=21)).strftime("%Y-%m-%d")
    assert flight_filter.is_last_minute({"departure_date": in_21_days}) is True

    # Departing in 22 days -> False (exceeds MAX_DAYS_AHEAD)
    in_22_days = (now + timedelta(days=22)).strftime("%Y-%m-%d")
    assert flight_filter.is_last_minute({"departure_date": in_22_days}) is False

    # Departing 40 days in future -> False
    in_40_days = (now + timedelta(days=40)).strftime("%Y-%m-%d")
    assert flight_filter.is_last_minute({"departure_date": in_40_days}) is False

    # Departing in the past (yesterday) -> False
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    assert flight_filter.is_last_minute({"departure_date": yesterday}) is False


def test_regional_destination_detection_and_price_caps():
    flight_filter = FlightFilter()

    # Asia (cap <= 1000.0)
    asia_cases = [
        {"route": "Bangkok WAW - BKK", "destination": "BKK"},
        {"route": "Phuket WAW - HKT", "destination": "HKT"},
        {"route": "WAW - PQC", "destination": "Phu Quoc"},
        {"route": "Colombo WAW - CMB", "destination": "CMB", "Panstwo": "Sri Lanka"},
        {"route": "WAW - MLE", "destination": "Malediwy"},
        {"route": "WAW - DPS", "destination": "Bali"},
    ]
    for case in asia_cases:
        assert flight_filter.get_destination_region(case) == "ASIA"
        assert flight_filter.get_regional_price_cap(case) == 1000.0

    # Africa & Americas (cap <= 1500.0)
    africa_america_cases = [
        {"route": "Zanzibar WAW - ZNZ", "destination": "ZNZ"},
        {"route": "Mombasa KTW - MBA", "destination": "MBA", "Panstwo": "Kenia"},
        {"route": "Cancun WAW - CUN", "destination": "CUN", "Panstwo": "Meksyk"},
        {"route": "Punta Cana WAW - PUJ", "destination": "PUJ", "Panstwo": "Dominikana"},
        {"route": "Bogota WAW - BOG", "destination": "BOG", "Panstwo": "Kolumbia"},
        {"route": "Varadero WAW - VRA", "destination": "VRA", "Panstwo": "Kuba"},
    ]
    for case in africa_america_cases:
        assert flight_filter.get_destination_region(case) == "AFRICA_AMERICA"
        assert flight_filter.get_regional_price_cap(case) == 1500.0


def test_filter_offers_integrates_regional_caps_and_last_minute():
    flight_filter = FlightFilter()
    now = datetime.now()
    valid_date = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    too_far_date = (now + timedelta(days=30)).strftime("%Y-%m-%d")

    offers = [
        # 1. Qualifying Asia deal below 1000 cap within last minute
        {
            "offer_id": "asia-bkk-ok",
            "price": 950.0,
            "route": "Bangkok WAW - BKK",
            "destination": "BKK",
            "departure_date": valid_date,
        },
        # 2. Qualifying Asia deal at exact 1000 cap
        {
            "offer_id": "asia-hkt-cap",
            "price": 1000.0,
            "route": "Phuket WAW - HKT",
            "destination": "HKT",
            "departure_date": "Terminy na stronie",
        },
        # 3. Asia deal exceeding 1000 cap
        {
            "offer_id": "asia-expensive",
            "price": 1000.50,
            "route": "Phu Quoc WAW - PQC",
            "destination": "PQC",
            "departure_date": valid_date,
        },
        # 4. Qualifying Africa/America deal below 1500 cap
        {
            "offer_id": "africa-znz-ok",
            "price": 1350.0,
            "route": "Zanzibar WAW - ZNZ",
            "destination": "ZNZ",
            "departure_date": valid_date,
        },
        # 5. Qualifying Africa/America deal at exact 1500 cap
        {
            "offer_id": "america-cun-cap",
            "price": 1500.0,
            "route": "Cancun WAW - CUN",
            "destination": "CUN",
            "departure_date": valid_date,
        },
        # 6. Africa/America deal exceeding 1500 cap
        {
            "offer_id": "africa-expensive",
            "price": 1501.0,
            "route": "Mombasa KTW - MBA",
            "destination": "MBA",
            "departure_date": valid_date,
        },
        # 7. Good price but rejected by last-minute window (> 21 days)
        {
            "offer_id": "asia-not-last-minute",
            "price": 800.0,
            "route": "Bangkok WAW - BKK",
            "destination": "BKK",
            "departure_date": too_far_date,
        },
        # 8. Short-haul cheap deal (excluded by keyword "Madera")
        {
            "offer_id": "sh-madera",
            "price": 450.0,
            "route": "Madera KTW - FNC",
            "destination": "FNC",
            "departure_date": valid_date,
        },
        # 9. Short-haul cheap deal (excluded by keyword "Antalya")
        {
            "offer_id": "sh-antalya",
            "price": 350.0,
            "route": "Antalya WAW - AYT",
            "destination": "AYT",
            "departure_date": valid_date,
        },
    ]

    matching = flight_filter.filter_offers(offers)

    matched_ids = [deal["offer_id"] for deal in matching]
    assert matched_ids == ["asia-bkk-ok", "asia-hkt-cap", "africa-znz-ok", "america-cun-cap"]
    assert len(matching) == 4
    # Ensure sorted by price ascending
    assert matching[0]["price"] <= matching[1]["price"] <= matching[2]["price"] <= matching[3]["price"]


def test_filter_deals_alias_works_identically():
    flight_filter = FlightFilter()
    now = datetime.now()
    valid_date = (now + timedelta(days=5)).strftime("%Y-%m-%d")

    offers = [
        {"offer_id": "1", "price": 1400.0, "route": "Zanzibar WAW - ZNZ", "destination": "ZNZ", "departure_date": valid_date},
        {"offer_id": "2", "price": 600.0, "route": "Madera KTW - FNC", "destination": "FNC", "departure_date": valid_date},
    ]
    matching = flight_filter.filter_deals(offers)
    assert len(matching) == 1
    assert matching[0]["offer_id"] == "1"


def test_filter_deals_skips_missing_or_invalid_price():
    flight_filter = FlightFilter()
    now = datetime.now()
    valid_date = (now + timedelta(days=5)).strftime("%Y-%m-%d")

    offers = [
        {"offer_id": "1", "route": "Zanzibar WAW - ZNZ", "destination": "ZNZ", "departure_date": valid_date},  # Missing price
        {"offer_id": "2", "price": "corrupted", "route": "Zanzibar WAW - ZNZ", "destination": "ZNZ", "departure_date": valid_date},
        {"offer_id": "3", "price": 1450.0, "route": "Zanzibar WAW - ZNZ", "destination": "ZNZ", "departure_date": valid_date},
    ]
    matching = flight_filter.filter_deals(offers)
    assert len(matching) == 1
    assert matching[0]["offer_id"] == "3"


def test_filter_deals_with_allowed_destinations():
    flight_filter = FlightFilter(allowed_destinations=["ZNZ", "CUN"])
    now = datetime.now()
    valid_date = (now + timedelta(days=5)).strftime("%Y-%m-%d")

    offers = [
        {"offer_id": "1", "price": 1400.0, "route": "Zanzibar WAW - ZNZ", "destination": "ZNZ", "departure_date": valid_date},
        {"offer_id": "2", "price": 950.0, "route": "Bangkok WAW - BKK", "destination": "BKK", "departure_date": valid_date},  # Not in allowed_destinations
        {"offer_id": "3", "price": 1450.0, "route": "Cancun WAW - CUN", "destination": "CUN", "departure_date": valid_date},
    ]
    matching = flight_filter.filter_deals(offers)
    assert len(matching) == 2
    assert [d["offer_id"] for d in matching] == ["1", "3"]
