"""
Webull OpenAPI (Level 1: tick/quote/snapshot stream) + Eulerpool (Level 2 top-of-book)
market data example.

Requires:
    pip install webull-openapi-python-sdk requests python-dotenv

Credentials (set as environment variables, never hardcode):
    WEBULL_APP_KEY       -> Webull App Key
    WEBULL_APP_SECRET    -> Webull App Secret
    WEBULL_REGION        -> "us" (or "au", "hk" etc.)
    WEBULL_ENV           -> "prod" or "sandbox"
    EULERPOOL_API_KEY    -> Eulerpool API token (from your Eulerpool dashboard)

    On Linux/macOS:
        export WEBULL_APP_KEY="your_app_key"
        export WEBULL_APP_SECRET="your_app_secret"
        export WEBULL_REGION="us"
        export WEBULL_ENV="prod"
        export EULERPOOL_API_KEY="ep_live_xxx"

    On Windows (PowerShell):
        $env:WEBULL_APP_KEY="your_app_key"
        $env:WEBULL_APP_SECRET="your_app_secret"
        $env:WEBULL_REGION="us"
        $env:WEBULL_ENV="prod"
        $env:EULERPOOL_API_KEY="ep_live_xxx"

IMPORTANT CAVEAT ABOUT EULERPOOL "LEVEL 2":
    Eulerpool's own API reference for GET /api/1/market/l2/{ticker} describes it as
    returning the "top-of-book Level 2 snapshot (bids/asks)" -- i.e. ONE best bid and
    ONE best ask, not a multi-level depth ladder like Webull's `depth=10` call below.
    Their docs also state this endpoint "Requires Polygon.io API key", but do not
    document how/where that second key is supplied (no header or query param is
    listed). So:
      - Treat the Eulerpool numbers here as a top-of-book cross-check, NOT full depth.
      - If you get a 401/403 from Eulerpool even with a valid EULERPOOL_API_KEY, it is
        likely because of that undocumented Polygon.io dependency -- contact
        api@eulerpool.com to ask how to supply/enable it.
    Webull remains the only source in this script that returns genuine multi-level
    order book depth (see fetch_webull_order_book_depth below).
"""

import os
import sys
import threading
import time

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads a local ".env" file, if present, into os.environ
except ImportError:
    pass  # dotenv is optional; env vars can also be set directly in the shell

import requests

from webull.core.client import ApiClient
from webull.data.common.category import Category
from webull.data.common.subscribe_type import SubscribeType
from webull.data.data_client import DataClient
from webull.data.data_streaming_client import DataStreamingClient

# ---- 1. Load credentials from environment -------------------------------

APP_KEY = os.environ.get("WEBULL_APP_KEY")
APP_SECRET = os.environ.get("WEBULL_APP_SECRET")
REGION = os.environ.get("WEBULL_REGION", "us")
ENV = os.environ.get("WEBULL_ENV", "prod")  # "prod" or "sandbox"
EULERPOOL_API_KEY = os.environ.get("EULERPOOL_API_KEY")

if not APP_KEY or not APP_SECRET:
    sys.exit(
        "Missing credentials. Set WEBULL_APP_KEY and WEBULL_APP_SECRET "
        "as environment variables before running this script."
    )

if not EULERPOOL_API_KEY:
    print(
        "WARNING: EULERPOOL_API_KEY is not set. The Eulerpool top-of-book "
        "check will be skipped.",
        file=sys.stderr,
    )

# Endpoints differ between production and the sandbox/test environment.
HTTP_ENDPOINTS = {
    "prod": "api.webull.com",
    "sandbox": "api.sandbox.webull.com",
}
MQTT_ENDPOINTS = {
    "prod": "data-api.webull.com",
    "sandbox": "data-api.sandbox.webull.com",
}

HTTP_HOST = HTTP_ENDPOINTS[ENV]
MQTT_HOST = MQTT_ENDPOINTS[ENV]

EULERPOOL_BASE_URL = "https://api.eulerpool.com/api/1"

SYMBOLS = ["AAPL"]  # change to whatever tickers you want


# ---- 2. Webull: multi-level order book depth (genuine Level 2 depth) ----

def fetch_webull_order_book_depth():
    """
    Pulls a one-off snapshot of multi-level bid/ask depth via Webull's HTTP API.
    Requires the OpenAPI Advanced Quotes subscription (purchased separately at
    the Webull developer portal) for real depth beyond top-of-book.

    Note: the depth/quotes endpoint lives under `market_data.get_quotes`,
    not a separate `quote` client -- there is no `get_order_book` method
    in the SDK.
    """
    api_client = ApiClient(APP_KEY, APP_SECRET, REGION)
    api_client.add_endpoint(REGION, HTTP_HOST)

    data_client = DataClient(api_client)

    for symbol in SYMBOLS:
        try:
            res = data_client.market_data.get_quotes(
                symbol=symbol,
                category=Category.US_STOCK.name,
                depth=10,  # Level 2, 10 price levels (US stocks support up to 50)
            )
            if res.status_code == 200:
                print(f"[Webull][{symbol}] order book depth (multi-level):")
                print(res.json())
            else:
                print(f"[Webull][{symbol}] depth request failed: HTTP {res.status_code} - {res.text}")
        except Exception as exc:
            print(f"[Webull][{symbol}] depth request failed: {exc}")


# ---- 3. Eulerpool: top-of-book "Level 2" snapshot (NOT full depth) ------

def fetch_eulerpool_top_of_book():
    """
    Pulls a one-off top-of-book snapshot (single best bid + single best ask)
    from Eulerpool's GET /api/1/market/l2/{ticker} endpoint.

    This is NOT a multi-level order book despite the endpoint's name -- see
    the module docstring for details, including the undocumented Polygon.io
    key requirement Eulerpool's own docs mention.
    """
    if not EULERPOOL_API_KEY:
        return

    for symbol in SYMBOLS:
        url = f"{EULERPOOL_BASE_URL}/market/l2/{symbol}"
        try:
            res = requests.get(
                url,
                params={"token": EULERPOOL_API_KEY},
                headers={"Accept": "application/json"},
                timeout=10,
            )
            if res.status_code == 200:
                data = res.json()
                print(f"[Eulerpool][{symbol}] top-of-book snapshot (NOT full depth):")
                print(data)
            elif res.status_code in (401, 403):
                print(
                    f"[Eulerpool][{symbol}] auth failed: HTTP {res.status_code} - {res.text}\n"
                    "  -> This endpoint reportedly also requires a Polygon.io API key "
                    "per Eulerpool's docs; the exact mechanism isn't documented. "
                    "Contact api@eulerpool.com if this persists."
                )
            else:
                print(f"[Eulerpool][{symbol}] request failed: HTTP {res.status_code} - {res.text}")
        except Exception as exc:
            print(f"[Eulerpool][{symbol}] request failed: {exc}")


# ---- 4. Real-time streaming: tick + quote + snapshot via MQTT (Level 1) -

def stream_realtime_data(duration_seconds=60):
    """
    Opens a live MQTT stream and prints tick / quote / snapshot events
    as they arrive, for `duration_seconds`. This is Level 1 data (trades +
    best bid/ask + OHLC snapshot), sourced from Webull.

    Note: DataStreamingClient does not expose a plain `connect()` you call
    yourself -- the documented entry point is `connect_and_loop_forever()`,
    which blocks the calling thread until the connection ends. To cap the
    stream at `duration_seconds`, we schedule `disconnect()` on a background
    timer; calling disconnect() causes connect_and_loop_forever() to return.
    """
    session_id = f"session_{int(time.time())}"

    streaming_client = DataStreamingClient(
        APP_KEY,
        APP_SECRET,
        REGION,
        session_id,
        http_host=HTTP_HOST,
        mqtt_host=MQTT_HOST,
    )

    def on_connect(client, api_client, session_id):
        print("Connected, session:", session_id)
        client.subscribe(
            SYMBOLS,
            Category.US_STOCK.name,
            [
                SubscribeType.TICK.name,      # raw tick-by-tick trades
                SubscribeType.QUOTE.name,     # best bid/ask (level 1)
                SubscribeType.SNAPSHOT.name,  # OHLC + volume snapshot
            ],
        )

    def on_subscribe(client, api_client, session_id):
        print("Subscribed successfully.")

    def on_message(client, topic, quotes):
        print(f"[Webull][{topic}] {quotes}")

    streaming_client.on_connect_success = on_connect
    streaming_client.on_subscribe_success = on_subscribe
    streaming_client.on_quotes_message = on_message

    timer = threading.Timer(duration_seconds, streaming_client.disconnect)
    timer.daemon = True
    timer.start()

    print(f"Streaming for {duration_seconds}s... Ctrl+C to stop early.")
    try:
        streaming_client.connect_and_loop_forever()
    except KeyboardInterrupt:
        streaming_client.disconnect()
    finally:
        timer.cancel()
        print("Stream closed.")


if __name__ == "__main__":
    print("=== Webull: multi-level order book depth (Level 2, real depth) ===")
    fetch_webull_order_book_depth()

    print("\n=== Eulerpool: top-of-book snapshot (labeled 'Level 2' by Eulerpool, but NOT full depth) ===")
    fetch_eulerpool_top_of_book()

    print("\n=== Webull: real-time tick/quote/snapshot stream (Level 1) ===")
    stream_realtime_data(duration_seconds=60)
