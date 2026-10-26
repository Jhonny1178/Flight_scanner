"""Main pipeline orchestrator for the Charter Flight Scanner.

Wires HTTPFetcher, BaseFlightParser, FlightFilter, and TelegramNotifier
via explicit Dependency Injection and coordinates end-to-end execution.
"""

from __future__ import annotations

import argparse
import logging
import sys
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

logger = logging.getLogger("flight_scanner")


class FlightScannerEngine:
    """Core orchestration engine coordinating extraction, filtering, and alerts."""

    def __init__(
        self,
        fetcher: HTTPFetcher,
        parser: BaseFlightParser,
        flight_filter: FlightFilter,
        notifier: TelegramNotifier,
        api_endpoint_url: str,
    ) -> None:
        """Injects all external dependencies explicitly.

        Args:
            fetcher: Configured HTTP client for raw data retrieval.
            parser: Concrete flight offer parser implementing BaseFlightParser.
            flight_filter: Business rules filter for price and route evaluation.
            notifier: Alert dispatcher for Telegram communications.
            api_endpoint_url: Target API endpoint URL.
        """
        self.fetcher: HTTPFetcher = fetcher
        self.parser: BaseFlightParser = parser
        self.filter: FlightFilter = flight_filter
        self.notifier: TelegramNotifier = notifier
        self.api_endpoint_url: str = api_endpoint_url

    def run(self, mock_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes one end-to-end scanning cycle.

        Args:
            mock_payload: Optional synthetic payload for local dry-runs and tests.

        Returns:
            Dictionary containing execution metrics (offers_found, matching_deals, alerts_sent).
        """
        logger.info("Starting flight scanner execution run...")
        metrics: Dict[str, Any] = {
            "success": False,
            "raw_offers_count": 0,
            "parsed_offers_count": 0,
            "matching_deals_count": 0,
            "alerts_sent_count": 0,
        }

        # Step 1: Retrieve raw flight data
        raw_data: Optional[Dict[str, Any]] = None
        if mock_payload is not None:
            logger.info("Using provided mock payload for execution run.")
            raw_data = mock_payload
        else:
            logger.info("Fetching data from endpoint: %s", self.api_endpoint_url)
            raw_data = self.fetcher.fetch_json(self.api_endpoint_url)

        if raw_data is None:
            logger.error(
                "Failed to fetch flight data from %s. Pipeline exiting gracefully.",
                self.api_endpoint_url,
            )
            return metrics

        # Step 2: Parse raw offers into normalized schema
        parsed_offers: List[Dict[str, Any]] = self.parser.parse_offers(raw_data)
        metrics["parsed_offers_count"] = len(parsed_offers)

        if not parsed_offers:
            logger.info("No valid flight offers extracted from payload.")
            metrics["success"] = True
            return metrics

        # Step 3: Apply business filtering logic
        matching_deals: List[Dict[str, Any]] = self.filter.filter_deals(parsed_offers)
        metrics["matching_deals_count"] = len(matching_deals)

        if not matching_deals:
            logger.info(
                "None of the %d offers matched the price threshold (<= %.2f).",
                len(parsed_offers),
                self.filter.price_threshold,
            )
            metrics["success"] = True
            return metrics

        # Step 4: Dispatch alert notifications
        logger.info("Found %d matching deals! Dispatching alerts...", len(matching_deals))
        if self.notifier.is_configured():
            sent_count = self.notifier.send_batch_alerts(matching_deals)
            metrics["alerts_sent_count"] = sent_count
        else:
            logger.warning(
                "Telegram notifier is not configured. Printing deals to console output:"
            )
            for deal in matching_deals:
                print(
                    f"-> [DEAL] {deal.get('origin')} -> {deal.get('destination')} "
                    f"| {deal.get('departure_date')} | {deal.get('price')} {deal.get('currency')} "
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
    """Provides a synthetic payload simulating typical last-minute charter flight deals."""
    return {
        "status": "success",
        "offers": [
            {
                "id": "ch-waw-her-001",
                "origin": "WAW",
                "destination": "HER",
                "departure_date": "2026-06-15",
                "return_date": "2026-06-22",
                "price": 349.00,
                "currency": "PLN",
                "operator": "Rainbow Tours Charter",
                "booking_url": "https://example.com/book/ch-001",
            },
            {
                "id": "ch-ktw-ayf-002",
                "origin": "KTW",
                "destination": "AYT",
                "departure_date": "2026-06-18",
                "return_date": "2026-06-25",
                "price": 420.00,
                "currency": "PLN",
                "operator": "TUI Charter",
                "booking_url": "https://example.com/book/ch-002",
            },
            {
                "id": "ch-waw-pfo-003",
                "origin": "WAW",
                "destination": "PFO",
                "departure_date": "2026-06-20",
                "return_date": None,
                "price": 890.00,  # Above typical 500 PLN threshold
                "currency": "PLN",
                "operator": "Enter Air",
                "booking_url": "https://example.com/book/ch-003",
            },
            {
                "id": "corrupted-deal",
                # Missing price and destination to test resilience
                "origin": "KRK",
            },
        ],
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
        "Loaded settings: price_threshold=%.2f %s, endpoint=%s",
        settings.price_threshold,
        settings.currency,
        settings.api_endpoint_url,
    )

    # Explicit Dependency Injection
    with HTTPFetcher(
        timeout=settings.request_timeout_seconds,
        max_retries=settings.max_retries,
        retry_backoff_factor=settings.retry_backoff_factor,
    ) as fetcher:
        parser = SampleCharterParser()
        flight_filter = FlightFilter(price_threshold=settings.price_threshold)
        notifier = TelegramNotifier(
            token=settings.telegram_token,
            chat_id=settings.chat_id,
        )

        engine = FlightScannerEngine(
            fetcher=fetcher,
            parser=parser,
            flight_filter=flight_filter,
            notifier=notifier,
            api_endpoint_url=settings.api_endpoint_url,
        )

        mock_payload = build_sample_mock_data() if args.mock else None
        metrics = engine.run(mock_payload=mock_payload)

    return 0 if metrics["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
