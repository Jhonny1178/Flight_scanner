"""Parser for Rainbow Tours (r.pl) charter flight search API.

Normalizes responses from https://r.pl/api/czartery/wyszukiwanie/v4.1/wyszukaj
into standardized flight offer dictionaries adhering to BaseFlightParser.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .base_parser import BaseFlightParser

logger = logging.getLogger(__name__)


class RainbowCharterParser(BaseFlightParser):
    """Parser implementation for Rainbow Tours (r.pl) charter API payloads."""

    BOOKING_SEARCH_URL = "https://r.pl/bilety-czarterowe/szukaj"
    IATA_PAIR_REGEX = re.compile(r"\b([A-Z]{3})\s*-\s*([A-Z]{3})\b")
    DATE_SUFFIX_REGEX = re.compile(r"\s+\d{1,2}/\d{1,2}/\d{4}$")

    def parse_offers(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parses the 'Destynacje' array from Rainbow API into normalized offers.

        Args:
            raw_json: Decoded JSON response from the Rainbow charter endpoint.

        Returns:
            List of normalized flight offer dictionaries.
        """
        parsed_offers: List[Dict[str, Any]] = []

        if not isinstance(raw_json, dict):
            logger.error(
                "Rainbow parser expected dict, got %s", type(raw_json).__name__
            )
            return parsed_offers

        destinations = raw_json.get("Destynacje", [])
        if not isinstance(destinations, list):
            logger.warning(
                "Rainbow payload 'Destynacje' is not a list. Found keys: %s",
                list(raw_json.keys()),
            )
            return parsed_offers

        for index, item in enumerate(destinations):
            if not isinstance(item, dict):
                logger.warning("Skipping non-dict destination item at index %d", index)
                continue

            try:
                # 1. Price extraction (comes directly as number from 'Cena')
                raw_price = item.get("Cena")
                if raw_price is None:
                    raise KeyError("Missing required 'Cena' field in Rainbow offer")

                price = float(raw_price)

                # 2. Departure date extraction from 'TerminWyjazdu' formatted to YYYY-MM-DD
                termin = item.get("TerminWyjazdu")
                if not termin or not isinstance(termin, str):
                    raise KeyError(
                        "Missing or invalid 'TerminWyjazdu' field in Rainbow offer"
                    )

                departure_date = termin.split("T")[0].strip()

                # 3. Route construction: use DataLayer.name if available, else Nazwa + Klucz
                data_layer = item.get("DataLayer")
                data_layer_dict = data_layer if isinstance(data_layer, dict) else {}

                nazwa = str(item.get("Nazwa") or "").strip()
                klucz = str(item.get("Klucz") or "").strip().upper()

                dl_name = str(data_layer_dict.get("name") or "").strip()
                if dl_name:
                    # Clean trailing date suffix if present (e.g. ' 31/10/2026')
                    route = self.DATE_SUFFIX_REGEX.sub("", dl_name).strip()
                elif nazwa and klucz:
                    route = f"{nazwa} ({klucz})"
                elif nazwa:
                    route = nazwa
                elif klucz:
                    route = klucz
                else:
                    route = "Rainbow Charter"

                # Extract origin and destination from route or Klucz
                origin = "PL"
                destination = klucz or nazwa or "Unknown"

                # Check if route contains IATA airport pair like "KTW - FNC"
                iata_match = self.IATA_PAIR_REGEX.search(route)
                if iata_match:
                    origin = iata_match.group(1).upper()
                    destination = iata_match.group(2).upper()

                # 4. Operator: "Rainbow" or "Rainbow ({brand})"
                brand = str(data_layer_dict.get("brand") or "").strip()
                operator = f"Rainbow ({brand})" if brand else "Rainbow"

                # 5. Identifier & URL
                dl_id = data_layer_dict.get("id")
                offer_id = (
                    f"rainbow_{dl_id}"
                    if dl_id is not None
                    else f"rainbow_{destination}_{departure_date}_{int(price)}"
                )

                offer: Dict[str, Any] = {
                    "offer_id": str(offer_id),
                    "origin": origin,
                    "destination": destination,
                    "route": route,
                    "departure_date": departure_date,
                    "return_date": None,
                    "price": price,
                    "currency": "PLN",
                    "operator": operator,
                    "airline_or_operator": operator,
                    "url": self.BOOKING_SEARCH_URL,
                    "booking_url": self.BOOKING_SEARCH_URL,
                }
                parsed_offers.append(offer)

            except KeyError as key_err:
                logger.warning(
                    "Rainbow offer at index %d missing mandatory field %s. Skipping.",
                    index,
                    key_err,
                )
            except (ValueError, TypeError) as val_err:
                logger.warning(
                    "Rainbow offer at index %d has invalid data types: %s. Skipping.",
                    index,
                    val_err,
                )

        logger.info(
            "Parsed %d valid offers from Rainbow Destynacje (total %d raw items).",
            len(parsed_offers),
            len(destinations),
        )
        return parsed_offers
