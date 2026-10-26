"""Unit tests for the resilient HTTPFetcher client."""

import json
from unittest.mock import MagicMock, patch
import requests
from flight_scanner.core.fetcher import HTTPFetcher


def test_fetch_json_success():
    fetcher = HTTPFetcher(timeout=5, max_retries=1)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"offers": [{"id": "1", "price": 200}]}

    with patch.object(fetcher.session, "get", return_value=mock_resp):
        result = fetcher.fetch_json("https://api.test/flights")
        assert result == {"offers": [{"id": "1", "price": 200}]}


def test_fetch_json_http_error():
    fetcher = HTTPFetcher(timeout=5, max_retries=1)
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch.object(fetcher.session, "get", return_value=mock_resp):
        result = fetcher.fetch_json("https://api.test/flights")
        assert result is None


def test_fetch_json_timeout():
    fetcher = HTTPFetcher(timeout=2, max_retries=1)

    with patch.object(
        fetcher.session, "get", side_effect=requests.exceptions.Timeout("Read timeout")
    ):
        result = fetcher.fetch_json("https://api.test/flights")
        assert result is None


def test_fetch_json_decode_error():
    fetcher = HTTPFetcher(timeout=5, max_retries=1)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>Invalid JSON</html>"
    mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)

    with patch.object(fetcher.session, "get", return_value=mock_resp):
        result = fetcher.fetch_json("https://api.test/flights")
        assert result is None
