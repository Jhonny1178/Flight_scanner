"""Resilient HTTP client wrapper for fetching flight API payloads.

Provides configurable timeout, retry logic with exponential backoff, and robust
exception handling for network and JSON decoding failures.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)


class HTTPFetcher:
    """Robust HTTP client with built-in retry mechanism and error handling."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
        "(CharterFlightScanner/1.0)"
    )

    def __init__(
        self,
        timeout: int = 15,
        max_retries: int = 3,
        retry_backoff_factor: float = 1.0,
        user_agent: Optional[str] = None,
    ) -> None:
        """Initializes the HTTP fetcher with custom timeout and retry parameters.

        Args:
            timeout: Request timeout in seconds.
            max_retries: Total number of retry attempts on network/server errors.
            retry_backoff_factor: Factor for exponential backoff between retries.
            user_agent: Custom User-Agent string for HTTP headers.
        """
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self.retry_backoff_factor: float = retry_backoff_factor
        self.user_agent: str = user_agent or self.DEFAULT_USER_AGENT

        self.session: requests.Session = self._create_configured_session()

    def _create_configured_session(self) -> requests.Session:
        """Configures a requests.Session with connection pooling and retry adapters."""
        session = requests.Session()

        retries = Retry(
            total=self.max_retries,
            backoff_factor=self.retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({"User-Agent": self.user_agent})

        return session

    def fetch_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Performs a GET request and parses the JSON response body.

        Catches RequestException and JSONDecodeError cleanly without crashing,
        logging failure context to assist operational observability.

        Args:
            url: The HTTP/HTTPS endpoint to query.
            params: Optional query parameters.
            headers: Optional additional request headers.

        Returns:
            Decoded JSON dictionary if successful, or None if the request failed.
        """
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        logger.debug("Requesting URL: %s with params: %s", url, params)

        try:
            response = self.session.get(
                url=url,
                params=params,
                headers=req_headers,
                timeout=self.timeout,
            )

            # Check HTTP status code
            if response.status_code >= 400:
                logger.error(
                    "HTTP %d error when fetching %s. Response preview: %s",
                    response.status_code,
                    url,
                    response.text[:300],
                )
                return None

            # Attempt JSON decoding
            data = response.json()
            if not isinstance(data, dict):
                logger.warning(
                    "Unexpected JSON root type from %s: expected dict, received %s",
                    url,
                    type(data).__name__,
                )
                return {"results": data} if isinstance(data, list) else None

            logger.info("Successfully fetched and decoded JSON from %s", url)
            return data

        except requests.exceptions.Timeout as timeout_err:
            logger.error(
                "Request timeout (%ds) exceeded for URL %s: %s",
                self.timeout,
                url,
                timeout_err,
            )
            return None

        except requests.exceptions.ConnectionError as conn_err:
            logger.error(
                "Connection failed when reaching %s: %s",
                url,
                conn_err,
            )
            return None

        except json.JSONDecodeError as json_err:
            logger.error(
                "Failed to decode JSON from %s: %s. Raw response content: %s",
                url,
                json_err,
                response.text[:300] if "response" in locals() else "<no response>",
            )
            return None

        except requests.exceptions.RequestException as req_err:
            logger.error(
                "Generic requests failure when requesting %s: %s",
                url,
                req_err,
            )
            return None

    def close(self) -> None:
        """Closes the underlying requests session."""
        self.session.close()

    def __enter__(self) -> HTTPFetcher:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
