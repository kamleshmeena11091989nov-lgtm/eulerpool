"""
Polygon.io (Massive.com) previous-close (EOD) connection test.

Uses the free "Stocks Basic" ($0/mo) tier -- end-of-day data only, no
real-time or 15-min-delayed quotes/trades entitlement required. This is
a deliberate downgrade from the earlier NBBO version of this script,
which needs the $199/mo Stocks Advanced plan.

File name kept as webull_market_data.py to match the existing GitHub
Actions workflow.

IMPORTANT: Polygon.io rebranded to Massive.com on 2025-10-30. Existing
api.polygon.io API keys and endpoints still work unchanged.

WHAT YOU GET ON THIS FREE TIER: the previous completed trading day's
open/high/low/close/volume for a ticker. NOT real-time, NOT intraday,
NOT bid/ask, and NOT order book depth of any kind -- just yesterday's
daily bar. If you need same-day or intraday prices, that requires at
least the $29/mo Starter plan (15-min delayed); real-time bid/ask needs
the $199/mo Advanced plan (see earlier version of this script).

Requires:
    pip install requests

Env vars:
    POLYGON_API_KEY     -> your Polygon.io / Massive.com API key (required)
    POLYGON_TEST_SYMBOL -> ticker to test with (optional, default "AAPL")
"""

import os
import sys
import time

import requests

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")
SYMBOL = os.environ.get("POLYGON_TEST_SYMBOL", "AAPL")

BASE_URL = "https://api.polygon.io"
URL = f"{BASE_URL}/v2/aggs/ticker/{SYMBOL}/prev"

if not POLYGON_API_KEY:
    sys.exit("Missing POLYGON_API_KEY environment variable.")


def masked(key, keep=4):
    if len(key) <= keep:
        return "*" * len(key)
    return key[:keep] + "*" * (len(key) - keep)


print("=== Polygon.io / Massive.com previous-close (EOD) test ===")
print(f"Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
print(f"URL       : {URL}")
print(f"Token     : {masked(POLYGON_API_KEY)}")
print(f"Symbol    : {SYMBOL}")
print("NOTE      : Free tier -- previous day's OHLC only, not real-time.")
print("-" * 40)

try:
    res = requests.get(
        URL,
        headers={
            "Authorization": f"Bearer {POLYGON_API_KEY}",
            "Accept": "application/json",
        },
        timeout=10,
    )
except Exception as exc:
    print(f"REQUEST FAILED (network/connection error): {exc}")
    sys.exit(1)

print(f"HTTP status : {res.status_code}")
print("Response headers:")
for k, v in res.headers.items():
    print(f"  {k}: {v}")
print(f"Raw body    : {res.text}")
print("-" * 40)

# Verdict
if res.status_code == 200:
    print("VERDICT: CONNECTION OK -- Polygon/Massive returned data.")
    try:
        data = res.json()
        print(f"Parsed JSON: {data}")
        results = data.get("results") or []
        if results:
            bar = results[0]
            print(
                f"Previous close for {SYMBOL}: "
                f"open={bar.get('o')} high={bar.get('h')} "
                f"low={bar.get('l')} close={bar.get('c')} "
                f"volume={bar.get('v')}"
            )
    except Exception:
        print("(Body was not valid JSON despite HTTP 200.)")
elif res.status_code == 401:
    print("VERDICT: AUTH FAILED -- POLYGON_API_KEY is missing/invalid/expired.")
elif res.status_code == 403:
    print("VERDICT: FORBIDDEN -- key is valid but your plan doesn't cover this endpoint.")
    print("         This endpoint should be free-tier eligible -- if you still see")
    print("         this, double check the key is active and unrestricted.")
elif res.status_code == 404:
    print("VERDICT: NOT FOUND -- check the symbol is correct and supported.")
elif res.status_code == 429:
    print("VERDICT: RATE LIMITED -- free tier is 5 calls/minute, back off and retry.")
else:
    print(f"VERDICT: UNEXPECTED STATUS {res.status_code} -- see raw body above.")
