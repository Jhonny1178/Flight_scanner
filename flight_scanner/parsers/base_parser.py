"""Abstract base class and contract definitions for charter flight parsers.

Defines the parsing interface to convert heterogeneous third-party API payloads
into standardized flight offer dictionaries.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseFlightParser(ABC):
    """Abstract interface for all flight offer parsers.

    Subclasses must implement `parse_offers` to transform raw provider-specific
    JSON payloads into a standardized list of flight offer dictionaries.
    """

    @abstractmethod
    def parse_offers(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parses a raw JSON dictionary from an external API into normalized offers.

        Each returned dictionary must adhere to the standardized schema:
            - offer_id (str): Unique identifier of the deal
            - origin (str): Departure airport code or city (e.g. 'WAW')
            - destination (str): Arrival airport code or city (e.g. 'HER')
            - departure_date (str): ISO format date or 'YYYY-MM-DD'
            - return_date (Optional[str]): Return flight date if round-trip
            - price (float): Numeric total price per passenger
            - currency (str): Currency code (e.g. 'PLN', 'EUR')
            - airline_or_operator (str): Charter operator or airline
            - booking_url (str): Direct link to complete the booking

        Args:
            raw_json: Decoded JSON response payload from the charter API.

        Returns:
            List of standardized flight offer dictionaries.
        """
        pass


class SampleCharterParser(BaseFlightParser):
    """Reference charter parser implementation with robust exception handling.

    Demonstrates extraction from a common nested charter API schema
    (e.g., offers list with inbound/outbound legs, pricing, and deeplinks).
    Catches KeyError or malformed items gracefully without interrupting the pipeline.
    """

    def parse_offers(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extracts and normalizes flight deals from a raw JSON payload.

        Args:
            raw_json: API response payload.

        Returns:
            List of valid normalized flight offer dictionaries.
        """
        parsed_offers: List[Dict[str, Any]] = []

        if not isinstance(raw_json, dict):
            logger.error(
                "Expected raw_json to be a dict, got %s", type(raw_json).__name__
            )
            return parsed_offers

        # Handle different top-level keys commonly used by flight providers
        raw_offers = raw_json.get("offers") or raw_json.get("data") or raw_json.get("results") or []

        if not isinstance(raw_offers, list):
            logger.warning(
                "Payload does not contain an offers list. Top-level keys: %s",
                list(raw_json.keys()),
            )
            return parsed_offers

        for index, item in enumerate(raw_offers):
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict offer item at index %d", index)
                continue

            try:
                # Extract mandatory fields with explicit type conversion & validation
                offer_id = str(
                    item.get("id")
                    or item.get("offer_id")
                    or f"offer_{index}"
                )
                origin = str(
                    item.get("origin")
                    or item.get("departure_city")
                    or item["departureAirport"]
                ).strip()
                destination = str(
                    item.get("destination")
                    or item.get("arrival_city")
                    or item["arrivalAirport"]
                ).strip()
                departure_date = str(
                    item.get("departure_date")
                    or item.get("outbound_date")
                    or item["departureDate"]
                ).strip()

                raw_price = item.get("price") or item.get("amount") or item.get("total_price")
                if raw_price is None:
                    raise KeyError("Missing price field")

                price = float(raw_price)
                currency = str(
                    item.get("currency")
                    or item.get("currency_code")
                    or "PLN"
                ).strip().upper()

                # Optional metadata
                return_date: Optional[str] = (
                    str(item.get("return_date") or item.get("inbound_date")).strip()
                    if item.get("return_date") or item.get("inbound_date")
                    else None
                )
                operator = str(
                    item.get("operator")
                    or item.get("airline")
                    or item.get("tour_operator")
                    or "Charter"
                ).strip()
                booking_url = str(
                    item.get("url")
                    or item.get("booking_url")
                    or item.get("link")
                    or "#"
                ).strip()

                offer = {
                    "offer_id": offer_id,
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "return_date": return_date,
                    "price": price,
                    "currency": currency,
                    "airline_or_operator": operator,
                    "booking_url": booking_url,
                }
                parsed_offers.append(offer)

            except KeyError as key_err:
                logger.warning(
                    "Offer at index %d missing mandatory key %s: %s. Skipping.",
                    index,
                    key_err,
                    item,
                )
            except (ValueError, TypeError) as val_err:
                logger.warning(
                    "Offer at index %d has invalid data types (%s). Skipping. Item: %s",
                    index,
                    val_err,
                    item,
                )

        logger.info(
            "Parsed %d valid offers out of %d raw items.",
            len(parsed_offers),
            len(raw_offers),
        )
        return parsed_offers
