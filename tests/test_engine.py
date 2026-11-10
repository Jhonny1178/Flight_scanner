"""End-to-end unit tests for FlightScannerEngine orchestration."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock
from flight_scanner.main import FlightScannerEngine, ProviderTask
from flight_scanner.core.filter import FlightFilter
from flight_scanner.parsers.base_parser import SampleCharterParser
from flight_scanner.parsers.rainbow_parser import RainbowCharterParser
from flight_scanner.parsers.tui_parser import TUICharterParser


def test_engine_single_parser_orchestration():
    mock_fetcher = MagicMock()
    now = datetime.now()
    valid_date = (now + timedelta(days=7)).strftime("%Y-%m-%d")

    mock_fetcher.fetch_json.return_value = {
        "offers": [
            {
                "id": "deal-1",
                "origin": "WAW",
                "destination": "BKK",
                "departure_date": valid_date,
                "price": 450.0,
                "currency": "PLN",
                "operator": "Charter",
                "url": "https://example.com/1",
            },
            {
                "id": "deal-2",
                "origin": "WAW",
                "destination": "BKK",
                "departure_date": valid_date,
                "price": 850.0,  # Exceeds custom filter threshold 500.0
                "currency": "PLN",
                "operator": "Charter",
                "url": "https://example.com/2",
            },
        ]
    }

    mock_notifier = MagicMock()
    mock_notifier.is_configured.return_value = True
    mock_notifier.send_batch_alerts.return_value = 1

    engine = FlightScannerEngine(
        fetcher=mock_fetcher,
        parser=SampleCharterParser(),
        flight_filter=FlightFilter(price_threshold=500.0),
        notifier=mock_notifier,
        api_endpoint_url="https://api.test/offers",
    )

    metrics = engine.run()
    assert metrics["success"] is True
    assert metrics["parsed_offers_count"] == 2
    assert metrics["matching_deals_count"] == 1
    assert metrics["alerts_sent_count"] == 1

    assert mock_fetcher.fetch_json.call_count == 1
    call_kwargs = mock_fetcher.fetch_json.call_args[1]
    assert call_kwargs["url"] == "https://api.test/offers"
    mock_notifier.send_batch_alerts.assert_called_once()


def test_engine_multi_provider_rainbow_and_tui():
    mock_fetcher = MagicMock()
    now = datetime.now()
    valid_date_rainbow = (now + timedelta(days=5)).strftime("%Y-%m-%dT00:00:00Z")
    valid_date_tui = (now + timedelta(days=10)).strftime("%Y-%m-%d")

    def mock_fetch_side_effect(url, **kwargs):
        if "r.pl" in url:
            return {
                "Destynacje": [
                    {
                        "Nazwa": "Zanzibar",
                        "Klucz": "ZNZ",
                        "TerminWyjazdu": valid_date_rainbow,
                        "Cena": 1450,  # Below 1500 Africa cap
                        "DataLayer": {
                            "brand": "Enter Air",
                            "name": "Zanzibar KTW - ZNZ",
                            "id": 1,
                        },
                    }
                ]
            }
        elif "tui" in url:
            return {
                "offers": [
                    {
                        "id": "tui-1",
                        "departureAirport": "WAW",
                        "arrivalAirport": "BKK",
                        "destination": "Bangkok",
                        "departureDate": valid_date_tui,
                        "price": 890.0,  # Below 1000 Asia cap
                        "currency": "PLN",
                        "operator": "TUI Charter",
                    }
                ]
            }
        return None

    mock_fetcher.fetch_json.side_effect = mock_fetch_side_effect

    mock_notifier = MagicMock()
    mock_notifier.is_configured.return_value = True
    mock_notifier.send_batch_alerts.return_value = 2

    rainbow_task = ProviderTask(
        name="Rainbow Tours",
        parser=RainbowCharterParser(),
        url="https://r.pl/api/czartery/wyszukiwanie/v4.1/wyszukaj",
        method="GET",
        params={
            "oneWay": "true",
            "dataUrodzenia": "1996-10-26",
            "sortowanie": "cena",
        },
        send_cookies=False,
    )
    tui_task = ProviderTask(
        name="TUI Charter",
        parser=TUICharterParser(),
        url="https://www.tui.pl/api/flight/search",
        method="POST",
        send_cookies=True,
    )

    engine = FlightScannerEngine(
        fetcher=mock_fetcher,
        flight_filter=FlightFilter(price_threshold=2500.0),
        notifier=mock_notifier,
        providers=[rainbow_task, tui_task],
    )

    metrics = engine.run()
    assert metrics["success"] is True
    assert metrics["parsed_offers_count"] == 2
    assert metrics["matching_deals_count"] == 2
    assert metrics["alerts_sent_count"] == 2
    assert mock_fetcher.fetch_json.call_count == 2
