"""Business logic module for evaluating and filtering flight deals.

Enforces pricing thresholds, target destinations, and long-haul criteria to identify
qualifying exotic charter flight opportunities while excluding short- and medium-haul routes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FlightFilter:
    """Filters flight offers based on financial thresholds, routes, and long-haul criteria."""

    EXCLUDED_KEYWORDS: List[str] = [
        "Turcja",
        "Madera",
        "Egipt",
        "Cypr",
        "Grecja",
        "Hiszpania",
        "Wyspy Kanaryjskie",
        "Portugalia",
        "Włochy",
        "Albania",
        "Bułgaria",
        "Czarnogóra",
        "Chorwacja",
        "Tunezja",
        "Maroko",
        "Teneryfa",
        "Fuerteventura",
        "Lanzarote",
        "Gran Canaria",
        "Antalya",
        "Bodrum",
        "Pafos",
    ]

    def __init__(
        self,
        price_threshold: float = 2500.0,
        allowed_destinations: Optional[List[str]] = None,
        allowed_origins: Optional[List[str]] = None,
        excluded_keywords: Optional[List[str]] = None,
    ) -> None:
        """Initializes the filter with explicit dependency-injected parameters.

        Args:
            price_threshold: Maximum acceptable ticket price (inclusive). Default is 2500.00 PLN.
            allowed_destinations: Optional list of acceptable destination airport codes/cities.
            allowed_origins: Optional list of acceptable origin airport codes/cities.
            excluded_keywords: Optional custom list of short/medium-haul keywords to exclude.
        """
        if price_threshold <= 0:
            raise ValueError(f"Price threshold must be positive, got {price_threshold}")

        self.price_threshold: float = price_threshold
        self.allowed_destinations: Optional[List[str]] = (
            [d.strip().upper() for d in allowed_destinations]
            if allowed_destinations
            else None
        )
        self.allowed_origins: Optional[List[str]] = (
            [o.strip().upper() for o in allowed_origins]
            if allowed_origins
            else None
        )
        self.excluded_keywords: List[str] = (
            list(excluded_keywords)
            if excluded_keywords is not None
            else list(self.EXCLUDED_KEYWORDS)
        )

    def is_long_haul(self, flight: Dict[str, Any]) -> bool:
        """Determines if a flight is long-haul by checking route and destination strings.

        Returns False if any excluded short/medium-haul keyword matches case-insensitively
        against the flight's route, destination, or country/city fields.

        Args:
            flight: Flight deal dictionary.

        Returns:
            bool: True if flight is long-haul, False if it matches any excluded keyword.
        """
        route = str(flight.get("route") or "").lower()
        destination = str(flight.get("destination") or "").lower()
        extra_fields = f"{flight.get('Nazwa', '')} {flight.get('Panstwo', '')}".lower()
        text_to_evaluate = f"{route} {destination} {extra_fields}"

        for keyword in self.excluded_keywords:
            if keyword.lower() in text_to_evaluate:
                logger.debug(
                    "Flight %s excluded as short/medium-haul (keyword '%s' matched in '%s')",
                    flight.get("offer_id", "unknown"),
                    keyword,
                    text_to_evaluate.strip(),
                )
                return False

        return True

    def filter_offers(self, offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters flight offers against price thresholds, long-haul criteria, and routes.

        Gracefully handles missing keys (KeyError) or corrupt price values without
        halting execution.

        Args:
            offers: Collection of normalized flight offer dictionaries.

        Returns:
            List of matching flight offers sorted by price in ascending order.
        """
        matching_deals: List[Dict[str, Any]] = []

        if not offers:
            logger.info("No offers received for filtering.")
            return matching_deals

        for index, offer in enumerate(offers):
            try:
                if not isinstance(offer, dict):
                    logger.warning(
                        "Offer at index %d is not a dictionary. Skipping.", index
                    )
                    continue

                # 1. Safely extract price
                if "price" not in offer:
                    raise KeyError("Field 'price' is required for filtering.")

                raw_price = offer["price"]
                try:
                    price = float(raw_price)
                except (ValueError, TypeError) as conv_err:
                    logger.warning(
                        "Offer %s has invalid price '%s': %s. Skipping.",
                        offer.get("offer_id", index),
                        raw_price,
                        conv_err,
                    )
                    continue

                # 2. Evaluate price threshold
                if price > self.price_threshold:
                    logger.debug(
                        "Offer %s price %.2f exceeds threshold %.2f",
                        offer.get("offer_id", index),
                        price,
                        self.price_threshold,
                    )
                    continue

                # 3. Evaluate destination exclusion (Long-haul check)
                if not self.is_long_haul(offer):
                    logger.debug(
                        "Offer %s excluded: matched short/medium-haul keyword.",
                        offer.get("offer_id", index),
                    )
                    continue

                # 4. Optional origin filter
                if self.allowed_origins:
                    origin = str(offer.get("origin", "")).strip().upper()
                    if origin not in self.allowed_origins:
                        logger.debug(
                            "Offer %s origin '%s' not in allowed list %s",
                            offer.get("offer_id", index),
                            origin,
                            self.allowed_origins,
                        )
                        continue

                # 5. Optional destination filter
                if self.allowed_destinations:
                    destination = str(offer.get("destination", "")).strip().upper()
                    if destination not in self.allowed_destinations:
                        logger.debug(
                            "Offer %s destination '%s' not in allowed list %s",
                            offer.get("offer_id", index),
                            destination,
                            self.allowed_destinations,
                        )
                        continue

                matching_deals.append(offer)

            except KeyError as key_err:
                logger.warning(
                    "Skipping offer at index %d due to missing key %s: %s",
                    index,
                    key_err,
                    offer,
                )

        # Sort cheapest flights first
        matching_deals.sort(key=lambda deal: float(deal.get("price", 0.0)))

        logger.info(
            "Filtered %d offers down to %d matching long-haul deals below %.2f threshold.",
            len(offers),
            len(matching_deals),
            self.price_threshold,
        )
        return matching_deals

    def filter_deals(self, offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Alias for filter_offers to maintain backward compatibility."""
        return self.filter_offers(offers)
