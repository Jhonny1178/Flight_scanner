"""Main pipeline orchestrator for the Charter Flight Scanner.

Wires HTTPFetcher, BaseFlightParser, FlightFilter, and TelegramNotifier
via explicit Dependency Injection and coordinates multi-provider execution
across Rainbow Tours (r.pl) and TUI Poland.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure the package root is in sys.path when executed directly as a script
package_root = Path(__file__).resolve().parent
if str(package_root) not in sys.path:
    sys.path.insert(0, str(package_root))

from config.settings import Settings, load_settings
from core.fetcher import HTTPFetcher
from core.filter import FlightFilter
from notifiers.telegram_bot import TelegramNotifier
from parsers.base_parser import BaseFlightParser, SampleCharterParser
from parsers.rainbow_parser import RainbowCharterParser
from parsers.tui_parser import TUICharterParser

logger = logging.getLogger("flight_scanner")


@dataclass
class ProviderTask:
    """Encapsulates configuration and parser for a specific flight provider."""

    name: str
    parser: BaseFlightParser
    url: str
    method: str = "GET"
    params: Optional[Dict[str, Any]] = None
    json_data: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    send_cookies: bool = True


class FlightScannerEngine:
    """Core orchestration engine coordinating multi-provider extraction, filtering, and alerts."""

    def __init__(
        self,
        fetcher: HTTPFetcher,
        parser: Optional[BaseFlightParser] = None,
        flight_filter: Optional[FlightFilter] = None,
        notifier: Optional[TelegramNotifier] = None,
        api_endpoint_url: Optional[str] = None,
        providers: Optional[List[ProviderTask]] = None,
    ) -> None:
        """Injects dependencies explicitly, supporting single-parser or multi-provider execution.

        Args:
            fetcher: Configured HTTP client for raw data retrieval.
            parser: Optional single parser (maintained for backward compatibility).
            flight_filter: Business rules filter for price and route evaluation.
            notifier: Alert dispatcher for Telegram communications.
            api_endpoint_url: Optional single API endpoint URL.
            providers: Optional list of configured ProviderTask instances.
        """
        self.fetcher: HTTPFetcher = fetcher
        self.filter: FlightFilter = flight_filter or FlightFilter(price_threshold=2500.0)
        self.notifier: TelegramNotifier = notifier or TelegramNotifier(token="", chat_id="")

        self.providers: List[ProviderTask] = []
        if providers:
            self.providers.extend(providers)
        elif parser and api_endpoint_url:
            self.providers.append(
                ProviderTask(
                    name="DefaultProvider",
                    parser=parser,
                    url=api_endpoint_url,
                    method="GET",
                )
            )

        self.parser: Optional[BaseFlightParser] = parser or (
            self.providers[0].parser if self.providers else None
        )
        self.api_endpoint_url: str = api_endpoint_url or (
            self.providers[0].url if self.providers else ""
        )

    def run(self, mock_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes one end-to-end scanning cycle across all configured providers.

        Args:
            mock_payload: Optional synthetic payload for local dry-runs and tests.

        Returns:
            Dictionary containing execution metrics across providers.
        """
        logger.info(
            "Starting flight scanner execution run across %d provider(s)...",
            len(self.providers),
        )
        metrics: Dict[str, Any] = {
            "success": False,
            "providers_scanned": [p.name for p in self.providers],
            "raw_offers_count": 0,
            "parsed_offers_count": 0,
            "matching_deals_count": 0,
            "alerts_sent_count": 0,
        }

        all_parsed_offers: List[Dict[str, Any]] = []

        # Process each provider sequentially
        for provider in self.providers:
            logger.info("Scanning provider '%s' at %s...", provider.name, provider.url)

            raw_data: Optional[Dict[str, Any]] = None

            if mock_payload is not None:
                if "rainbow" in provider.name.lower() and "rainbow" in mock_payload:
                    raw_data = mock_payload["rainbow"]
                elif "tui" in provider.name.lower() and "tui" in mock_payload:
                    raw_data = mock_payload["tui"]
                else:
                    raw_data = mock_payload
            else:
                raw_data = self.fetcher.fetch_json(
                    url=provider.url,
                    method=provider.method,
                    params=provider.params,
                    json_data=provider.json_data,
                    headers=provider.headers,
                    send_cookies=provider.send_cookies,
                )

            if raw_data is None:
                logger.warning(
                    "Provider '%s' did not return valid data. Skipping provider.",
                    provider.name,
                )
                continue

            try:
                provider_offers = provider.parser.parse_offers(raw_data)
                logger.info(
                    "Provider '%s' yielded %d valid offers.",
                    provider.name,
                    len(provider_offers),
                )
                all_parsed_offers.extend(provider_offers)
            except Exception as parse_err:
                logger.error(
                    "Unexpected error parsing offers for provider '%s': %s",
                    provider.name,
                    parse_err,
                )

        metrics["parsed_offers_count"] = len(all_parsed_offers)

        if not all_parsed_offers:
            logger.info("No valid flight offers extracted from any provider.")
            metrics["success"] = True
            return metrics

        # Filter deals across all providers
        matching_deals: List[Dict[str, Any]] = self.filter.filter_deals(all_parsed_offers)
        metrics["matching_deals_count"] = len(matching_deals)

        if not matching_deals:
            logger.info(
                "None of the %d total offers matched the price threshold (<= %.2f %s).",
                len(all_parsed_offers),
                self.filter.price_threshold,
                "PLN",
            )
            metrics["success"] = True
            return metrics

        # Dispatch alert notifications
        logger.info("Found %d matching deals! Dispatching alerts...", len(matching_deals))
        if self.notifier.is_configured():
            sent_count = self.notifier.send_batch_alerts(matching_deals)
            metrics["alerts_sent_count"] = sent_count
        else:
            logger.warning(
                "Telegram notifier is not configured. Printing deals to console output:"
            )
            for deal in matching_deals:
                route_str = deal.get("route") or f"{deal.get('origin')} -> {deal.get('destination')}"
                print(
                    f"-> [DEAL] {route_str} "
                    f"| {deal.get('departure_date')} | {deal.get('price'):.2f} {deal.get('currency')} "
                    f"| {deal.get('airline_or_operator')}"
                )

        metrics["success"] = True
        logger.info("Flight scanner run finished successfully: %s", metrics)
        return metrics


def setup_logging(log_level: str = "INFO") -> None:
    """Configures structured console logging with timestamp and level."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_sample_mock_data() -> Dict[str, Any]:
    """Provides synthetic payloads simulating exotic long-haul and excluded short-haul offers."""
    return {
        "rainbow": {
            "Destynacje": [
                {
                    "Panstwo": "Tanzania",
                    "Nazwa": "Zanzibar",
                    "Klucz": "ZNZ",
                    "TerminWyjazdu": "2026-11-15T00:00:00Z",
                    "Cena": 1899,  # Qualifying exotic long-haul below 2500 threshold
                    "DataLayer": {
                        "brand": "Enter Air",
                        "id": 501,
                        "name": "Zanzibar WAW - ZNZ 15/11/2026",
                        "price": 1899,
                    },
                },
                {
                    "Panstwo": "Portugalia",
                    "Nazwa": "Madera",
                    "Klucz": "FNC",
                    "TerminWyjazdu": "2026-10-31T00:00:00Z",
                    "Cena": 749,  # Below 2500, but excluded as short-haul (Madera keyword)
                    "DataLayer": {
                        "brand": "Enter Air",
                        "id": 502,
                        "name": "Madera KTW - FNC 31/10/2026",
                        "price": 749,
                    },
                },
                {
                    "Panstwo": "Kenia",
                    "Nazwa": "Mombasa",
                    "Klucz": "MBA",
                    "TerminWyjazdu": "2026-11-20T00:00:00Z",
                    "Cena": 2999,  # Long-haul, but exceeds 2500 price threshold
                    "DataLayer": {
                        "brand": "Enter Air",
                        "id": 503,
                        "name": "Mombasa KTW - MBA 20/11/2026",
                        "price": 2999,
                    },
                },
            ]
        },
        "tui": {
            "offers": [
                {
                    "id": "tui-cun-001",
                    "departureAirport": "WAW",
                    "arrivalAirport": "CUN",
                    "destination": "Cancun",
                    "departureDate": "2026-11-25",
                    "price": 2199.00,  # Qualifying long-haul below 2500 threshold
                    "currency": "PLN",
                    "operator": "TUI Charter",
                    "booking_url": "https://www.tui.pl/bilety-czarterowe/cun",
                },
                {
                    "id": "tui-ayt-002",
                    "departureAirport": "WAW",
                    "arrivalAirport": "AYT",
                    "destination": "Antalya",
                    "route": "Antalya WAW - AYT",
                    "departureDate": "2026-11-10",
                    "price": 450.00,  # Below 2500, but excluded as short-haul (Antalya keyword)
                    "currency": "PLN",
                    "operator": "TUI Charter",
                    "booking_url": "https://www.tui.pl/bilety-czarterowe/ayt",
                },
            ]
        },
    }


def main() -> int:
    """CLI and workflow orchestration entrypoint."""
    cli_parser = argparse.ArgumentParser(
        description="Automated charter flight monitoring and alerting pipeline."
    )
    cli_parser.add_argument(
        "--mock",
        action="store_true",
        help="Run pipeline using synthetic mock charter offers for demonstration.",
    )
    cli_parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional custom path to .env file.",
    )
    args = cli_parser.parse_args()

    # Load configuration
    try:
        settings: Settings = load_settings(env_file=args.env_file)
    except Exception as exc:
        logging.basicConfig(level=logging.ERROR)
        logger.error("Failed to load valid configuration: %s", exc)
        return 1

    setup_logging(settings.log_level)
    logger.info(
        "Loaded settings: price_threshold=%.2f %s",
        settings.price_threshold,
        settings.currency,
    )

    # Configure provider tasks
    rainbow_provider = ProviderTask(
        name="Rainbow Tours",
        parser=RainbowCharterParser(),
        url=settings.rainbow_api_endpoint_url,
        method="GET",
        params={
            "oneWay": "false",
            "dataUrodzenia": "1996-10-26",
            "sortowanie": "cena",
        },
        headers={
            "accept": "*/*",
            "x-source": "r.pl",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
            ),
        },
        send_cookies=False,  # strictly NO cookies to avoid session invalidation
    )

    tui_provider = ProviderTask(
        name="TUI Charter",
        parser=TUICharterParser(),
        url=settings.tui_api_endpoint_url,
        method="POST",
        json_data={"filters": {"priceMax": settings.price_threshold}},
        headers={"accept": "application/json"},
        send_cookies=True,
    )

    # Explicit Dependency Injection
    with HTTPFetcher(
        timeout=settings.request_timeout_seconds,
        max_retries=settings.max_retries,
        retry_backoff_factor=settings.retry_backoff_factor,
    ) as fetcher:
        flight_filter = FlightFilter(price_threshold=settings.price_threshold)
        notifier = TelegramNotifier(
            token=settings.telegram_token,
            chat_id=settings.chat_id,
        )

        engine = FlightScannerEngine(
            fetcher=fetcher,
            flight_filter=flight_filter,
            notifier=notifier,
            providers=[rainbow_provider, tui_provider],
        )

        mock_payload = build_sample_mock_data() if args.mock else None
        metrics = engine.run(mock_payload=mock_payload)

    return 0 if metrics["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
