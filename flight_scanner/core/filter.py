"""Business logic module for evaluating and filtering flight deals.

Enforces pricing thresholds, target destinations, and sanity criteria to identify
qualifying last-minute charter flight opportunities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FlightFilter:
    """Filters flight offers based on financial thresholds and route preferences."""

    def __init__(
        self,
        price_threshold: float,
        allowed_destinations: Optional[List[str]] = None,
        allowed_origins: Optional[List[str]] = None,
    ) -> None:
        """Initializes the filter with explicit dependency-injected parameters.

        Args:
            price_threshold: Maximum acceptable ticket price (inclusive).
            allowed_destinations: Optional list of acceptable destination airport codes/cities.
            allowed_origins: Optional list of acceptable origin airport codes/cities.
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

    def filter_deals(self, offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters a collection of flight offers against business criteria.

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

                # Safely extract price
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

                # Evaluate price threshold
                if price > self.price_threshold:
                    logger.debug(
                        "Offer %s price %.2f exceeds threshold %.2f",
                        offer.get("offer_id", index),
                        price,
                        self.price_threshold,
                    )
                    continue

                # Optional origin filter
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

                # Optional destination filter
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
            "Filtered %d offers down to %d matching deals below %.2f threshold.",
            len(offers),
            len(matching_deals),
            self.price_threshold,
        )
        return matching_deals
