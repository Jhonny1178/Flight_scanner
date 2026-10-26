"""Telegram Bot API notification client.

Formats deal alerts with structured HTML formatting and delivers messages
to specified Telegram channels or private chats via HTTPS.
"""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram alert dispatcher with error handling and HTML formatting."""

    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"
    TELEGRAM_MAX_MESSAGE_LENGTH = 4096

    def __init__(
        self,
        token: str,
        chat_id: str,
        timeout: int = 10,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initializes the Telegram notifier.

        Args:
            token: Telegram Bot API secret authentication token.
            chat_id: Target chat or channel identifier.
            timeout: HTTP request timeout in seconds.
            session: Optional pre-configured requests.Session (for dependency injection).
        """
        self.token: str = token.strip()
        self.chat_id: str = chat_id.strip()
        self.timeout: int = timeout
        self.session: requests.Session = session or requests.Session()

    def is_configured(self) -> bool:
        """Returns True if bot token and chat_id are present."""
        return bool(self.token and self.chat_id)

    def format_deal_message(self, deal: Dict[str, Any]) -> str:
        """Formats a single flight deal dictionary into a Telegram HTML message.

        Safely escapes user-controlled strings to prevent HTML tag injection.

        Args:
            deal: Flight offer dictionary.

        Returns:
            HTML formatted string ready for Telegram dispatch.
        """
        origin = html.escape(str(deal.get("origin", "N/A")))
        destination = html.escape(str(deal.get("destination", "N/A")))
        departure_date = html.escape(str(deal.get("departure_date", "N/A")))
        return_date = deal.get("return_date")
        price = deal.get("price", 0.0)
        currency = html.escape(str(deal.get("currency", "PLN")))
        operator = html.escape(str(deal.get("airline_or_operator", "Charter")))
        booking_url = str(deal.get("booking_url", "")).strip()

        lines = [
            "✈️ <b>LAST-MINUTE CHARTER DEAL FOUND!</b>",
            "─────────────────────────────",
            f"📍 <b>Route:</b> {origin} ➔ <b>{destination}</b>",
            f"📅 <b>Departure:</b> {departure_date}",
        ]

        if return_date:
            lines.append(f"🔙 <b>Return:</b> {html.escape(str(return_date))}")

        lines.extend([
            f"💰 <b>Price:</b> <code>{price:.2f} {currency}</code>",
            f"🏢 <b>Operator:</b> {operator}",
        ])

        if booking_url and booking_url != "#":
            safe_url = html.escape(booking_url, quote=True)
            lines.append(f"🔗 <a href=\"{safe_url}\"><b>Book Flight Now</b></a>")

        lines.append("─────────────────────────────")
        return "\n".join(lines)

    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = False,
    ) -> bool:
        """Dispatches a raw text message to the configured Telegram chat.

        Args:
            text: Message body text (up to 4096 characters).
            parse_mode: Parsing mode, defaults to 'HTML'.
            disable_web_page_preview: Whether to suppress URL previews.

        Returns:
            True if message was sent successfully, False otherwise.
        """
        if not self.is_configured():
            logger.warning(
                "Telegram notifier is not fully configured (token or chat_id missing). Skipping send."
            )
            return False

        url = self.BASE_URL.format(token=self.token)
        payload = {
            "chat_id": self.chat_id,
            "text": text[: self.TELEGRAM_MAX_MESSAGE_LENGTH],
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.info("Telegram message successfully sent to chat %s", self.chat_id)
                    return True
                logger.error("Telegram API returned ok=False: %s", data)
                return False

            logger.error(
                "Telegram API error HTTP %d: %s",
                response.status_code,
                response.text[:300],
            )
            return False

        except requests.exceptions.RequestException as req_err:
            logger.error(
                "Network exception occurred while dispatching Telegram alert: %s",
                req_err,
            )
            return False

    def send_deal_alert(self, deal: Dict[str, Any]) -> bool:
        """Formats and sends an alert for a single flight deal.

        Args:
            deal: Flight offer dictionary.

        Returns:
            True if message was sent successfully, False otherwise.
        """
        message = self.format_deal_message(deal)
        return self.send_message(message)

    def send_batch_alerts(self, deals: List[Dict[str, Any]]) -> int:
        """Sends alert notifications for multiple flight deals.

        Args:
            deals: List of flight offer dictionaries.

        Returns:
            Count of successfully dispatched messages.
        """
        success_count = 0
        for deal in deals:
            if self.send_deal_alert(deal):
                success_count += 1
        logger.info(
            "Dispatched %d/%d Telegram deal alerts successfully.",
            success_count,
            len(deals),
        )
        return success_count
