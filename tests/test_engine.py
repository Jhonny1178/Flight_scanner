"""End-to-end unit tests for FlightScannerEngine orchestration."""

from unittest.mock import MagicMock
from flight_scanner.main import FlightScannerEngine
from flight_scanner.core.filter import FlightFilter
from flight_scanner.parsers.base_parser import SampleCharterParser


def test_engine_end_to_end_orchestration():
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

    mock_fetcher.fetch_json.assert_called_once_with("https://api.test/offers")
    mock_notifier.send_batch_alerts.assert_called_once()
