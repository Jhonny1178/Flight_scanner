"""Unit tests for Rainbow Tours (r.pl) charter flight parser."""

from flight_scanner.parsers.rainbow_parser import RainbowCharterParser


def test_rainbow_parser_extracts_exact_fields():
    parser = RainbowCharterParser()
    raw_payload = {
        "Destynacje": [
            {
                "Panstwo": "Portugalia",
                "Nazwa": "Madera",
                "Klucz": "FNC",
                "TerminWyjazdu": "2026-10-31T00:00:00Z",
                "Cena": 749,
                "DataLayer": {
                    "brand": "Enter Air",
                    "name": "Madera KTW - FNC 31/10/2026",
                    "id": 269934,
                },
            }
        ]
    }

    offers = parser.parse_offers(raw_payload)
    assert len(offers) == 1
    offer = offers[0]

    # Verify exact requested values
    assert offer["price"] == 749.0
    assert offer["operator"] == "Rainbow (Enter Air)" or offer["airline_or_operator"] == "Rainbow (Enter Air)"
    assert offer["route"] == "Madera KTW - FNC"
    assert offer["departure_date"] == "2026-10-31"
    assert offer["booking_url"] == "https://r.pl/bilety-czarterowe/szukaj"
    assert offer["origin"] == "KTW"
    assert offer["destination"] == "FNC"


def test_rainbow_parser_fallback_route_when_datalayer_name_missing():
    parser = RainbowCharterParser()
    raw_payload = {
        "Destynacje": [
            {
                "Panstwo": "Hiszpania",
                "Nazwa": "Gran Canaria",
                "Klucz": "LPA",
                "TerminWyjazdu": "2026-11-03T00:00:00Z",
                "Cena": 899,
                # No DataLayer
            }
        ]
    }

    offers = parser.parse_offers(raw_payload)
    assert len(offers) == 1
    offer = offers[0]

    assert offer["price"] == 899.0
    assert offer["airline_or_operator"] == "Rainbow"
    assert offer["route"] == "Gran Canaria (LPA)"
    assert offer["destination"] == "LPA"
    assert offer["departure_date"] == "2026-11-03"


def test_rainbow_parser_skips_missing_mandatory_fields():
    parser = RainbowCharterParser()
    raw_payload = {
        "Destynacje": [
            {
                # Valid
                "Nazwa": "Djerba",
                "Klucz": "DJE",
                "TerminWyjazdu": "2026-10-29T00:00:00Z",
                "Cena": 650,
            },
            {
                # Missing Cena
                "Nazwa": "Agadir",
                "Klucz": "AGA",
                "TerminWyjazdu": "2026-10-30T00:00:00Z",
            },
            {
                # Missing TerminWyjazdu
                "Nazwa": "Mombasa",
                "Klucz": "MBA",
                "Cena": 999,
            },
            "not-a-dict",
        ]
    }

    offers = parser.parse_offers(raw_payload)
    assert len(offers) == 1
    assert offers[0]["destination"] == "DJE"
    assert offers[0]["price"] == 650.0


def test_rainbow_parser_handles_empty_or_non_dict_payload():
    parser = RainbowCharterParser()
    assert parser.parse_offers({}) == []
    assert parser.parse_offers({"Destynacje": "not-a-list"}) == []
