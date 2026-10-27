# ✈️ Automated Charter Flight Scanner

An automated, resilient low-cost and last-minute charter flight monitoring and alerting pipeline supporting multi-provider querying across **Rainbow Tours (r.pl)** and **TUI Poland**. Designed following Senior Data Engineering best practices: explicit Dependency Injection, strict typing, zero hardcoding, and failure tolerance.

---

## 📁 Repository Structure

```text
flight_scanner/
├── config/
│   ├── __init__.py
│   └── settings.py          # Strongly typed environment configuration & validation
├── parsers/
│   ├── __init__.py
│   ├── base_parser.py       # Abstract base parser interface (BaseFlightParser)
│   ├── rainbow_parser.py    # Rainbow Tours (r.pl) charter API parser
│   └── tui_parser.py        # TUI Poland charter API parser
├── core/
│   ├── __init__.py
│   ├── fetcher.py           # Resilient HTTP client (GET/POST, params, cookie controls, retries)
│   └── filter.py            # Business logic: price threshold & route filtering
├── notifiers/
│   ├── __init__.py
│   └── telegram_bot.py      # Telegram Bot API client with HTML formatting & error handling
├── main.py                  # Main pipeline orchestrator using explicit Dependency Injection
├── requirements.txt         # Project dependencies
├── .env.example             # Configuration template
└── .github/
    └── workflows/
        └── cron_scraper.yml # GitHub Actions workflow running on a 3-hour cron schedule
```

---

## 🛠️ Architecture & Core Principles

1. **Multi-Provider Explicit Dependency Injection**:
   The central pipeline engine (`FlightScannerEngine` in `main.py`) coordinates provider tasks (`ProviderTask`) injecting dedicated parsers (`RainbowCharterParser`, `TUICharterParser`) and `HTTPFetcher`, `FlightFilter`, and `TelegramNotifier`.
2. **Strict Type Annotations**:
   Every class, function, and method signature has explicit Python type annotations (`typing`, `Optional`, `Dict`, `List`, etc.).
3. **Zero Hardcoded Values**:
   Credentials, API endpoints, timeouts, retry counts, and pricing thresholds are loaded from environment variables via `config/settings.py`.
4. **Resilience & Cookie Isolation**:
   - Rainbow API requires strictly NO cookies; `HTTPFetcher` supports `send_cookies=False` to prevent session invalidation.
   - Malformed API items (`KeyError`, invalid price types) are skipped per item with warnings.
   - Network timeouts, connection errors, and `json.JSONDecodeError` are handled cleanly without crashing the scanner run.

---

## 🚀 Quickstart

### 1. Installation

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and fill in your details:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `TELEGRAM_TOKEN` | Bot API token from `@BotFather` | Required for Telegram alerts |
| `CHAT_ID` | Telegram User ID or Channel ID | Required for Telegram alerts |
| `PRICE_THRESHOLD` | Maximum deal price to trigger alert | `2500.0` |
| `CURRENCY` | Currency code | `PLN` |
| `RAINBOW_API_ENDPOINT_URL` | Rainbow Tours charter API endpoint | `https://r.pl/api/czartery/wyszukiwanie/v4.1/wyszukaj` |
| `TUI_API_ENDPOINT_URL` | TUI charter API endpoint | `https://www.tui.pl/api/flight/search` |
| `REQUEST_TIMEOUT_SECONDS` | HTTP timeout in seconds | `15` |
| `MAX_RETRIES` | Number of HTTP retries with exponential backoff | `3` |
| `LOG_LEVEL` | Console log verbosity (`INFO`, `DEBUG`, etc.) | `INFO` |

### 3. Running Locally

#### Run with Synthetic Demo Data (`--mock` flag):
Tests Rainbow and TUI parsers, filtering logic, and notifications immediately:

```bash
python flight_scanner/main.py --mock
```

#### Run against live API endpoints:
```bash
python flight_scanner/main.py
```

### 4. Running Unit Tests

Run the test suite using `pytest`:

```bash
pytest -v
```

---

## ⏱️ GitHub Actions Cron Automation

The workflow `.github/workflows/cron_scraper.yml` automatically executes the scraper every 3 hours:

- **Schedule**: `cron: '0 */3 * * *'` (every 3 hours at minute 0).
- **Manual Trigger**: Supports `workflow_dispatch` for immediate execution via the GitHub Web UI.
