"""Parser for TUI Poland charter flight search API.

Normalizes responses from TUI charter API into standardized flight offer
dictionaries adhering to BaseFlightParser.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base_parser import BaseFlightParser

logger = logging.getLogger(__name__)


class TUICharterParser(BaseFlightParser):
    """Parser implementation for TUI charter flights API."""

    DEFAULT_BOOKING_URL = "https://www.tui.pl/bilety-czarterowe"

    def parse_offers(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parses TUI flight offers from raw JSON payload.

        Handles both top-level list containers ('offers', 'flights', 'data', 'results').
        """
        parsed_offers: List[Dict[str, Any]] = []

        if not isinstance(raw_json, dict):
            logger.error("TUI parser expected dict, got %s", type(raw_json).__name__)
            return parsed_offers

        raw_offers = (
            raw_json.get("offers")
            or raw_json.get("flights")
            or raw_json.get("data")
            or raw_json.get("results")
            or []
        )

        if not isinstance(raw_offers, list):
            logger.warning(
                "TUI payload contains no list of offers. Available keys: %s",
                list(raw_json.keys()),
            )
            return parsed_offers

        for index, item in enumerate(raw_offers):
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict TUI item at index %d", index)
                continue

            try:
                offer_id = str(
                    item.get("id")
                    or item.get("flightId")
                    or item.get("offer_id")
                    or f"tui_{index}"
                )
                origin = str(
                    item.get("origin")
                    or item.get("departureAirport")
                    or item.get("departure_city")
                    or "WAW"
                ).strip().upper()
                destination = str(
                    item.get("destination")
                    or item.get("arrivalAirport")
                    or item.get("arrival_city")
                ).strip().upper()

                departure_date_raw = str(
                    item.get("departure_date")
                    or item.get("departureDate")
                    or item.get("outbound_date")
                ).strip()
                departure_date = departure_date_raw.split("T")[0]

                raw_price = (
                    item.get("price")
                    or item.get("amount")
                    or item.get("total_price")
                )
                if raw_price is None:
                    raise KeyError("Missing price in TUI offer")

                price = float(raw_price)
                currency = str(
                    item.get("currency")
                    or item.get("currency_code")
                    or "PLN"
                ).strip().upper()

                return_date_raw = item.get("return_date") or item.get("returnDate") or item.get("inbound_date")
                return_date = str(return_date_raw).split("T")[0] if return_date_raw else None

                operator = str(
                    item.get("operator")
                    or item.get("airline")
                    or "TUI Charter"
                ).strip()

                booking_url = str(
                    item.get("booking_url")
                    or item.get("url")
                    or item.get("link")
                    or self.DEFAULT_BOOKING_URL
                ).strip()

                route = f"{origin} - {destination}"

                offer = {
                    "offer_id": offer_id,
                    "origin": origin,
                    "destination": destination,
                    "route": route,
                    "departure_date": departure_date,
                    "return_date": return_date,
                    "price": price,
                    "currency": currency,
                    "operator": operator,
                    "airline_or_operator": operator,
                    "url": booking_url,
                    "booking_url": booking_url,
                }
                parsed_offers.append(offer)

            except KeyError as key_err:
                logger.warning(
                    "TUI offer at index %d missing mandatory key %s. Skipping.",
                    index,
                    key_err,
                )
            except (ValueError, TypeError) as val_err:
                logger.warning(
                    "TUI offer at index %d has invalid data types (%s). Skipping.",
                    index,
                    val_err,
                )

        logger.info(
            "Parsed %d valid offers out of %d raw TUI items.",
            len(parsed_offers),
            len(raw_offers),
        )
        return parsed_offers
