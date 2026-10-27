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


def test_fetch_json_get_with_params_and_headers():
    fetcher = HTTPFetcher(timeout=5, max_retries=1)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"Destynacje": []}

    params = {"oneWay": "false", "dataUrodzenia": "1996-10-26", "sortowanie": "cena"}
    headers = {"x-source": "r.pl", "user-agent": "CustomUA"}

    with patch.object(fetcher.session, "get", return_value=mock_resp) as mock_get:
        result = fetcher.get_json("https://r.pl/api/czartery", params=params, headers=headers)
        assert result == {"Destynacje": []}
        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == params
        assert kwargs["headers"]["x-source"] == "r.pl"
        assert kwargs["headers"]["user-agent"] == "CustomUA"


def test_fetch_json_post_method():
    fetcher = HTTPFetcher(timeout=5, max_retries=1)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"offers": [{"flightId": "tui-1"}]}

    payload = {"filters": {"maxPrice": 400}}

    with patch.object(fetcher.session, "post", return_value=mock_resp) as mock_post:
        result = fetcher.post_json("https://tui.pl/api", json_data=payload)
        assert result == {"offers": [{"flightId": "tui-1"}]}
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == payload


def test_fetch_json_send_cookies_disabled():
    fetcher = HTTPFetcher(timeout=5, max_retries=1)
    fetcher.session.cookies.set("session_id", "secret_cookie")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}

    with patch.object(fetcher.session, "get", return_value=mock_resp):
        result = fetcher.fetch_json("https://r.pl/api", method="GET", send_cookies=False)
        assert result == {"ok": True}
        # Verify cookies were cleared
        assert len(fetcher.session.cookies) == 0


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
