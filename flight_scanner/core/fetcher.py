"""Resilient HTTP client wrapper for fetching flight API payloads.

Provides configurable timeout, retry logic with exponential backoff, support
for GET and POST methods with query parameters and JSON payloads, cookie
control, and robust exception handling.
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
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        send_cookies: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Executes an HTTP request (GET or POST) and parses the JSON response body.

        Catches RequestException and JSONDecodeError cleanly without crashing,
        logging failure context to assist operational observability.

        Args:
            url: The HTTP/HTTPS endpoint to query.
            method: HTTP method ('GET' or 'POST'). Defaults to 'GET'.
            params: Optional query parameters passed to the request URL.
            json_data: Optional JSON serializable dictionary for POST request body.
            data: Optional raw payload for POST request body.
            headers: Optional additional request headers (e.g. x-source, custom user-agent).
            send_cookies: If False, strips and clears cookies before/after request.

        Returns:
            Decoded JSON dictionary if successful, or None if the request failed.
        """
        http_method = method.strip().upper()
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        if not send_cookies:
            self.session.cookies.clear()

        logger.debug(
            "Executing %s request to %s with params: %s, has_json: %s, send_cookies: %s",
            http_method,
            url,
            params,
            bool(json_data),
            send_cookies,
        )

        try:
            if http_method == "POST":
                response = self.session.post(
                    url=url,
                    params=params,
                    json=json_data,
                    data=data,
                    headers=req_headers,
                    timeout=self.timeout,
                )
            else:
                response = self.session.get(
                    url=url,
                    params=params,
                    headers=req_headers,
                    timeout=self.timeout,
                )

            if not send_cookies:
                self.session.cookies.clear()

            # Check HTTP status code
            if response.status_code >= 400:
                logger.error(
                    "HTTP %d error when fetching %s via %s. Response preview: %s",
                    response.status_code,
                    url,
                    http_method,
                    response.text[:300],
                )
                return None

            # Attempt JSON decoding
            body = response.json()
            if not isinstance(body, dict):
                logger.warning(
                    "Unexpected JSON root type from %s: expected dict, received %s",
                    url,
                    type(body).__name__,
                )
                return {"results": body} if isinstance(body, list) else None

            logger.info("Successfully fetched and decoded JSON from %s", url)
            return body

        except requests.exceptions.Timeout as timeout_err:
            logger.error(
                "Request timeout (%ds) exceeded for %s %s: %s",
                self.timeout,
                http_method,
                url,
                timeout_err,
            )
            return None

        except requests.exceptions.ConnectionError as conn_err:
            logger.error(
                "Connection failed when reaching %s %s: %s",
                http_method,
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
                "Generic requests failure when requesting %s %s: %s",
                http_method,
                url,
                req_err,
            )
            return None

    def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        send_cookies: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Convenience wrapper for GET requests with query parameters."""
        return self.fetch_json(
            url=url,
            method="GET",
            params=params,
            headers=headers,
            send_cookies=send_cookies,
        )

    def post_json(
        self,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        send_cookies: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Convenience wrapper for POST requests with JSON payload."""
        return self.fetch_json(
            url=url,
            method="POST",
            params=params,
            json_data=json_data,
            headers=headers,
            send_cookies=send_cookies,
        )

    def close(self) -> None:
        """Closes the underlying requests session."""
        self.session.close()

    def __enter__(self) -> HTTPFetcher:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
