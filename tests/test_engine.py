"""End-to-end unit tests for FlightScannerEngine orchestration."""

from unittest.mock import MagicMock
from flight_scanner.main import FlightScannerEngine, ProviderTask
from flight_scanner.core.filter import FlightFilter
from flight_scanner.parsers.base_parser import SampleCharterParser
from flight_scanner.parsers.rainbow_parser import RainbowCharterParser
from flight_scanner.parsers.tui_parser import TUICharterParser


def test_engine_single_parser_orchestration():
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_json.return_value = {
        "offers": [
            {
                "id": "deal-1",
                "origin": "WAW",
                "destination": "AYT",
                "departure_date": "2026-06-15",
                "price": 350.0,
                "currency": "PLN",
                "operator": "Charter",
                "url": "https://example.com/1",
            },
            {
                "id": "deal-2",
                "origin": "WAW",
                "destination": "BCN",
                "departure_date": "2026-06-15",
                "price": 850.0,  # Exceeds threshold
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

    def mock_fetch_side_effect(url, **kwargs):
        if "r.pl" in url:
            return {
                "Destynacje": [
                    {
                        "Nazwa": "Zanzibar",
                        "Klucz": "ZNZ",
                        "TerminWyjazdu": "2026-10-31T00:00:00Z",
                        "Cena": 1450,  # Below 2500
                        "DataLayer": {
                            "brand": "Enter Air",
                            "name": "Zanzibar KTW - ZNZ 31/10/2026",
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
                        "arrivalAirport": "CUN",
                        "departureDate": "2026-06-15",
                        "price": 1820.0,  # Below 2500
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
