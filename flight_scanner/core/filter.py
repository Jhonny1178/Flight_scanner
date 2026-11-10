"""Business logic module for evaluating and filtering flight deals.

Enforces pricing thresholds, target destinations, regional price caps, and last-minute
time windows to identify qualifying exotic charter flight opportunities while strictly
excluding short- and medium-haul routes.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_DAYS_AHEAD: int = 21
ASIA_PRICE_CAP: float = 1000.0
AFRICA_AMERICA_PRICE_CAP: float = 1500.0


class FlightFilter:
    """Filters flight offers based on regional pricing caps, routes, and last-minute windows."""

    MAX_DAYS_AHEAD: int = MAX_DAYS_AHEAD
    ASIA_PRICE_CAP: float = ASIA_PRICE_CAP
    AFRICA_AMERICA_PRICE_CAP: float = AFRICA_AMERICA_PRICE_CAP

    EXCLUDED_KEYWORDS: List[str] = [
        # Turkey & North Cyprus
        "Turcja", "Turkey", "Antalya", "Bodrum", "Dalaman", "Izmir", "Alanya",
        "Stambuł", "Istanbul", "AYT", "BJV", "DLM", "ADB", "GZP", "IST", "SAW",
        # Egypt
        "Egipt", "Egypt", "Hurghada", "Sharm el Sheikh", "Marsa Alam", "Kair",
        "Cairo", "HRG", "SSH", "RMF", "CAI",
        # Tunisia
        "Tunezja", "Tunisia", "Djerba", "Enfidha", "Monastir", "Tunis", "DJE",
        "NBE", "MIR", "TUN",
        # Morocco
        "Maroko", "Morocco", "Agadir", "Marrakesz", "Marrakech", "Casablanca",
        "AGA", "RAK", "CMN",
        # Canary Islands & Spain
        "Hiszpania", "Spain", "Wyspy Kanaryjskie", "Canary Islands", "Teneryfa",
        "Tenerife", "Fuerteventura", "Lanzarote", "Gran Canaria", "La Palma",
        "TFS", "TFN", "FUE", "ACE", "LPA", "SPC", "Majorka", "Mallorca", "Ibiza",
        "Menorca", "Malaga", "Málaga", "Alicante", "Barcelona", "Madryt", "Madrid",
        "Girona", "Sewilla", "Sevilla", "Walencja", "Valencia", "PMI", "IBZ",
        "MAH", "AGP", "ALC", "BCN", "MAD", "GRO", "SVQ", "VLC",
        # Portugal & Madeira & Azores
        "Portugalia", "Portugal", "Madera", "Madeira", "Faro", "Lizbona",
        "Lisbon", "Porto", "Azory", "Azores", "FNC", "FAO", "LIS", "OPO",
        # Greece & Greek Islands
        "Grecja", "Greece", "Kreta", "Crete", "Rodos", "Rhodes", "Zakynthos",
        "Korfu", "Corfu", "Kos", "Santorini", "Mykonos", "Ateny", "Athens",
        "Saloniki", "Thessaloniki", "Heraklion", "Chania", "HER", "CHQ", "RHO",
        "ZTH", "CFU", "KGS", "JTR", "JMK", "ATH", "SKG",
        # Cyprus
        "Cypr", "Cyprus", "Pafos", "Paphos", "Larnaka", "Larnaca", "PFO", "LCA",
        # Italy & Italian Islands
        "Włochy", "Italy", "Sycylia", "Sicily", "Sardynia", "Sardinia", "Rzym",
        "Rome", "Mediolan", "Milan", "Wenecja", "Venice", "Neapol", "Naples",
        "Palermo", "Katania", "Catania", "Bari", "Bergamo", "Bolonia", "Bologna",
        "CTA", "PMO", "NAP", "FCO", "CIA", "MXP", "BGY", "VCE", "BLQ", "BRI",
        # Balkans & Southeastern Europe
        "Albania", "Tirana", "TIA", "Bułgaria", "Bulgaria", "Burgas", "Warna",
        "Varna", "BOJ", "VAR", "Czarnogóra", "Montenegro", "Podgorica", "Tivat",
        "TGD", "TIV", "Chorwacja", "Croatia", "Split", "Dubrownik", "Dubrovnik",
        "Zadar", "Pula", "Zagrzeb", "Zagreb", "SPU", "DBV", "ZAD", "PUY", "ZAG",
        "Malta", "MLA", "Macedonia", "Skopje", "Ochryda", "Ohrid", "SKP", "OHD",
        "Serbia", "Belgrad", "Belgrade", "BEG", "Bośnia", "Bosnia", "Sarajewo",
        "Sarajevo", "SJJ", "Słowenia", "Slovenia", "Lublana", "Ljubljana", "LJU",
        # Central, Western & Northern Europe
        "Francja", "France", "Paryż", "Paris", "Nicea", "Nice", "Marsylia",
        "Marseille", "Korsyka", "Corsica", "CDG", "ORY", "NCE", "MRS",
        "Niemcy", "Germany", "Berlin", "Frankfurt", "Monachium", "Munich", "BER",
        "FRA", "MUC", "Wielka Brytania", "United Kingdom", "Londyn", "London",
        "LHR", "LGW", "STN", "LTN", "Irlandia", "Ireland", "Dublin", "DUB",
        "Austria", "Wiedeń", "Vienna", "VIE", "Szwajcaria", "Switzerland",
        "Zurych", "Zurich", "Genewa", "Geneva", "ZRH", "GVA", "Holandia",
        "Netherlands", "Amsterdam", "AMS", "Belgia", "Belgium", "Bruksela",
        "Brussels", "BRU", "CRL", "Czechy", "Czech Republic", "Praga", "Prague",
        "PRG", "Słowacja", "Slovakia", "Bratysława", "Bratislava", "BTS",
        "Węgry", "Hungary", "Budapeszt", "Budapest", "BUD", "Rumunia", "Romania",
        "Bukareszt", "Bucharest", "OTP", "Dania", "Denmark", "Kopenhaga",
        "Copenhagen", "CPH", "Szwecja", "Sweden", "Sztokholm", "Stockholm",
        "ARN", "Norwegia", "Norway", "Oslo", "OSL", "Finlandia", "Finland",
        "Helsinki", "HEL", "Islandia", "Iceland", "Reykjavik", "KEF",
        # Caucasus & Near East short-haul
        "Gruzja", "Georgia", "Kutaisi", "Tbilisi", "Batumi", "KUT", "TBS", "BUS",
        "Izrael", "Israel", "Tel Awiw", "Tel Aviv", "Eilat", "TLV", "Jordania",
        "Jordan", "Amman", "Akaba", "Aqaba", "AMM", "AQJ",
    ]

    ASIA_KEYWORDS: List[str] = [
        "tajlandia", "thailand", "bangkok", "bkk", "dmk", "phuket", "hkt",
        "krabi", "kbv", "pattaya", "utp", "samui", "koh samui", "usm",
        "chiang mai", "cnx", "wietnam", "vietnam", "phu quoc", "phú quốc", "pqc",
        "ho chi minh", "sajgon", "saigon", "sgn", "hanoi", "han", "da nang",
        "danang", "dad", "nha trang", "cam ranh", "cxr", "sri lanka", "srilanka",
        "cejlon", "ceylon", "colombo", "cmb", "malediwy", "maldives", "male",
        "malé", "mle", "indonezja", "indonesia", "bali", "denpasar", "dps",
        "dżakarta", "jakarta", "cgk", "malezja", "malaysia", "kuala lumpur", "kul",
        "langkawi", "lgk", "penang", "pen", "singapur", "singapore", "sin",
        "filipiny", "philippines", "manila", "mnl", "cebu", "ceb", "boracay",
        "indie", "india", "goa", "goi", "gox", "delhi", "del", "mumbaj",
        "mumbai", "bombaj", "bom", "zjednoczone emiraty arabskie", "emiraty",
        "dubaj", "dubai", "dxb", "dwc", "abu dhabi", "abu zabi", "auh",
        "szardża", "sharjah", "shj", "ras al khaimah", "rkt", "oman", "maskat",
        "muscat", "mct", "salalah", "sll", "katar", "qatar", "doha", "doh",
        "japonia", "japan", "tokio", "tokyo", "nrt", "hnd", "osaka", "kix",
        "chiny", "china", "pekin", "beijing", "pek", "szanghaj", "shanghai",
        "pvg", "korea", "seul", "seoul", "icn", "kambodża", "cambodia",
        "phnom penh", "pnh", "siem reap", "sai", "rep", "laos", "vientiane",
        "vte", "nepal", "katmandu", "kathmandu", "ktm", "tajwan", "taiwan",
        "tajpej", "taipei", "tpe", "azja", "asia",
    ]

    AFRICA_AMERICA_KEYWORDS: List[str] = [
        # Africa
        "tanzania", "zanzibar", "znz", "dar es salaam", "dar", "kilimanjaro",
        "jro", "kenia", "kenya", "mombasa", "mba", "nairobi", "nbo",
        "madagaskar", "madagascar", "nosy be", "nos", "antananarywa",
        "antananarivo", "tnr", "mauritius", "port louis", "mru", "seszele",
        "seychelles", "mahe", "mahé", "sez", "wyspy zielonego przylądka",
        "republika zielonego przylądka", "cape verde", "cabo verde", "sal", "sid",
        "boa vista", "bvc", "rpa", "południowa afryka", "south africa",
        "kapsztad", "cape town", "cpt", "johannesburg", "jnb", "namibia",
        "windhuk", "windhoek", "wdh", "senegal", "dakar", "dss", "gambia",
        "bandżul", "banjul", "bjl", "afryka", "africa",
        # Americas & Caribbean
        "dominikana", "dominican republic", "dominican", "punta cana", "puj",
        "puerto plata", "pop", "santo domingo", "sdq", "la romana", "lrm",
        "samana", "azs", "meksyk", "mexico", "cancun", "cancún", "cun",
        "cozumel", "czm", "mexico city", "mex", "kolumbia", "colombia",
        "bogota", "bogotá", "bog", "cartagena", "ctg", "medellin", "medellín",
        "mde", "kuba", "cuba", "varadero", "vra", "hawana", "havana", "hav",
        "cayo coco", "ccc", "santa clara", "snu", "holguin", "hog", "jamajka",
        "jamaica", "montego bay", "mbj", "kingston", "kin", "brazylia", "brazil",
        "rio de janeiro", "gig", "sao paulo", "são paulo", "gru", "fortaleza",
        "for", "salvador", "ssa", "natal", "nat", "wenezuela", "venezuela",
        "margarita", "porlamar", "pmv", "caracas", "ccs", "kostaryka",
        "costa rica", "san jose", "san josé", "sjo", "liberia", "lir",
        "panama", "panamá", "pty", "stany zjednoczone", "usa", "miami", "mia",
        "nowy jork", "new york", "jfk", "ewr", "orlando", "mco", "los angeles",
        "lax", "kanada", "canada", "toronto", "yyz", "montreal", "montréal",
        "yul", "peru", "lima", "lim", "argentyna", "argentina", "buenos aires",
        "eze", "chile", "santiago", "scl", "karaiby", "caribbean", "curacao",
        "curaçao", "cur", "aruba", "aua", "sint maarten", "saint martin", "sxm",
        "gwadelupa", "guadeloupe", "ptp", "martynika", "martinique", "fdf",
        "barbados", "bgi", "bahamy", "bahamas", "nas", "ameryka", "america",
        "americas",
    ]

    def __init__(
        self,
        price_threshold: float = 2500.0,
        allowed_destinations: Optional[List[str]] = None,
        allowed_origins: Optional[List[str]] = None,
        excluded_keywords: Optional[List[str]] = None,
        max_days_ahead: int = MAX_DAYS_AHEAD,
        asia_price_cap: float = ASIA_PRICE_CAP,
        africa_america_price_cap: float = AFRICA_AMERICA_PRICE_CAP,
    ) -> None:
        """Initializes the filter with explicit dependency-injected parameters.

        Args:
            price_threshold: Global maximum acceptable price cap fallback.
            allowed_destinations: Optional list of acceptable destination airport codes/cities.
            allowed_origins: Optional list of acceptable origin airport codes/cities.
            excluded_keywords: Optional custom list of short/medium-haul keywords to exclude.
            max_days_ahead: Maximum allowed days ahead for last-minute booking window.
            asia_price_cap: Specific maximum price for Asian destinations (<= 1000.00 PLN).
            africa_america_price_cap: Specific maximum price for African & American destinations (<= 1500.00 PLN).
        """
        if price_threshold <= 0:
            raise ValueError(f"Price threshold must be positive, got {price_threshold}")
        if max_days_ahead <= 0:
            raise ValueError(f"max_days_ahead must be positive, got {max_days_ahead}")
        if asia_price_cap <= 0:
            raise ValueError(f"asia_price_cap must be positive, got {asia_price_cap}")
        if africa_america_price_cap <= 0:
            raise ValueError(f"africa_america_price_cap must be positive, got {africa_america_price_cap}")

        self.price_threshold: float = price_threshold
        self.max_days_ahead: int = max_days_ahead
        self.asia_price_cap: float = asia_price_cap
        self.africa_america_price_cap: float = africa_america_price_cap
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

    def is_last_minute(self, flight: Dict[str, Any]) -> bool:
        """Evaluates whether a flight falls within the last-minute time window.

        Args:
            flight: Flight offer dictionary.

        Returns:
            bool: True if departure date is a placeholder (e.g. 'Terminy na stronie')
                  or if 0 <= difference_in_days <= MAX_DAYS_AHEAD. False otherwise.
        """
        raw_dep = (
            flight.get("departure_date")
            or flight.get("departureDate")
            or flight.get("TerminWyjazdu")
        )
        if not raw_dep or not isinstance(raw_dep, str):
            # Placeholder or unspecified departure date -> True
            return True

        dep_str = raw_dep.strip()
        date_part = dep_str.split("T")[0].strip()

        try:
            dep_date = datetime.strptime(date_part, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            # Non-standard or placeholder date string (e.g. "Terminy na stronie")
            return True

        today = datetime.now().date()
        difference_in_days = (dep_date - today).days

        return 0 <= difference_in_days <= self.max_days_ahead

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
        extra_fields = " ".join([
            str(flight.get("Nazwa") or ""),
            str(flight.get("Panstwo") or ""),
            str(flight.get("destination_name") or ""),
            str(flight.get("country") or ""),
            str(flight.get("city") or ""),
        ]).lower()
        text_to_evaluate = f"{route} {destination} {extra_fields}"

        for keyword in self.excluded_keywords:
            kw_clean = keyword.strip().lower()
            if not kw_clean:
                continue
            # Use word boundary matching for exact tokens and short keywords
            pattern = rf"\b{re.escape(kw_clean)}\b"
            if re.search(pattern, text_to_evaluate):
                logger.debug(
                    "Flight %s excluded as short/medium-haul (keyword '%s' matched in '%s')",
                    flight.get("offer_id", "unknown"),
                    keyword,
                    text_to_evaluate.strip(),
                )
                return False

        return True

    def get_destination_region(self, flight: Dict[str, Any]) -> Optional[str]:
        """Identifies whether destination belongs to 'ASIA' or 'AFRICA_AMERICA'.

        Args:
            flight: Flight deal dictionary.

        Returns:
            'ASIA', 'AFRICA_AMERICA', or None if not recognized as an exotic destination.
        """
        text_to_eval = " ".join([
            str(flight.get("destination") or ""),
            str(flight.get("route") or ""),
            str(flight.get("Panstwo") or ""),
            str(flight.get("Nazwa") or ""),
            str(flight.get("PanstwoUrl") or ""),
            str(flight.get("NazwaUrl") or ""),
            str(flight.get("country") or ""),
            str(flight.get("city") or ""),
            str(flight.get("destination_name") or ""),
        ]).lower()

        # Check Asia keywords
        for kw in self.ASIA_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", text_to_eval):
                return "ASIA"

        # Check Africa & America keywords
        for kw in self.AFRICA_AMERICA_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", text_to_eval):
                return "AFRICA_AMERICA"

        return None

    def get_regional_price_cap(self, flight: Dict[str, Any]) -> Optional[float]:
        """Returns the specific regional price cap for a flight offer.

        Args:
            flight: Flight offer dictionary.

        Returns:
            1000.0 for Asia, 1500.0 for Africa & Americas, or None if unrecognized.
        """
        region = self.get_destination_region(flight)
        if region == "ASIA":
            return self.asia_price_cap
        elif region == "AFRICA_AMERICA":
            return self.africa_america_price_cap
        return None

    def get_region_label(self, flight: Dict[str, Any]) -> str:
        """Returns a human-readable region label for the flight destination.

        Args:
            flight: Flight offer dictionary.

        Returns:
            One of: '🌏 Azja', '🌍 Afryka / Ameryki', or '❓ Nieznany region'.
        """
        region = self.get_destination_region(flight)
        if region == "ASIA":
            return "🌏 Azja"
        elif region == "AFRICA_AMERICA":
            return "🌍 Afryka / Ameryki"
        return "❓ Nieznany region"

    def filter_offers(self, offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters flight offers against regional price caps, last-minute, and long-haul criteria.

        A flight is accepted ONLY if:
        1. is_long_haul() == True
        2. is_last_minute() == True
        3. Its price fits the specific regional cap (Asia <= 1000.00, Africa/Americas <= 1500.00).

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

                # 2. Evaluate destination exclusion (Long-haul check)
                if not self.is_long_haul(offer):
                    logger.debug(
                        "Offer %s excluded: matched short/medium-haul keyword.",
                        offer.get("offer_id", index),
                    )
                    continue

                # 3. Evaluate last-minute window check
                if not self.is_last_minute(offer):
                    logger.debug(
                        "Offer %s excluded: departure date not in last-minute window (<= %d days).",
                        offer.get("offer_id", index),
                        self.max_days_ahead,
                    )
                    continue

                # 4. Regional price cap evaluation (Asia <= 1000, Africa/Americas <= 1500)
                region_cap = self.get_regional_price_cap(offer)
                if region_cap is None:
                    logger.debug(
                        "Offer %s excluded: not recognized as exotic Asia or Africa/America destination.",
                        offer.get("offer_id", index),
                    )
                    continue

                # Resolve region string for metadata stamping
                region = self.get_destination_region(offer)

                effective_cap = (
                    min(region_cap, self.price_threshold)
                    if self.price_threshold is not None
                    else region_cap
                )

                if price > effective_cap:
                    logger.debug(
                        "Offer %s price %.2f exceeds regional cap %.2f",
                        offer.get("offer_id", index),
                        price,
                        effective_cap,
                    )
                    continue

                # 5. Optional origin filter
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

                # 6. Optional destination filter
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

                # Stamp the matched offer with region metadata for downstream formatting
                enriched_offer = dict(offer)
                enriched_offer["_region"] = region
                enriched_offer["_region_cap"] = region_cap
                matching_deals.append(enriched_offer)

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
            "Filtered %d offers down to %d matching exotic last-minute deals.",
            len(offers),
            len(matching_deals),
        )
        return matching_deals

    def filter_deals(self, offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Alias for filter_offers to maintain backward compatibility."""
        return self.filter_offers(offers)
