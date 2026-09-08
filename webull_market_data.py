"""
Polygon.io (Massive.com) NBBO connection test.

Currently used ONLY to verify the Polygon.io / Massive.com top-of-book
connection is working (auth + data availability). File name kept as
webull_market_data.py to match the existing GitHub Actions workflow --
swap the CONTENTS back to the combined Webull+depth-source version once
this is confirmed working and you decide which depth source to keep.

IMPORTANT: Polygon.io rebranded to Massive.com on 2025-10-30. Existing
api.polygon.io API keys and endpoints still work unchanged (both domains
run in parallel), but current docs/signups live at massive.com.

IMPORTANT CAVEAT ABOUT DEPTH: Polygon/Massive's own FAQ states that
individual plans do NOT provide US stock Level 2 market depth -- only
NBBO (single best bid + single best ask), same as Eulerpool's endpoint.
Genuine multi-level order book depth (Nasdaq TotalView-equivalent) is a
Business-plan add-on requiring a sales conversation and exchange
licensing, not something available via a standard API key. Treat this
script's output as a top-of-book cross-check, not full depth.

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

# api.polygon.io still works post-rebrand; api.massive.com is the new domain.
# Both are live in parallel, so either works with the same API key.
BASE_URL = "https://api.polygon.io"
URL = f"{BASE_URL}/v2/last/nbbo/{SYMBOL}"

if not POLYGON_API_KEY:
    sys.exit("Missing POLYGON_API_KEY environment variable.")


def masked(key, keep=4):
    if len(key) <= keep:
        return "*" * len(key)
    return key[:keep] + "*" * (len(key) - keep)


print("=== Polygon.io / Massive.com NBBO connection test ===")
print(f"Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
print(f"URL       : {URL}")
print(f"Token     : {masked(POLYGON_API_KEY)}")
print(f"Symbol    : {SYMBOL}")
print("NOTE      : This is top-of-book NBBO only, NOT multi-level depth.")
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
    except Exception:
        print("(Body was not valid JSON despite HTTP 200.)")
elif res.status_code == 401:
    print("VERDICT: AUTH FAILED -- POLYGON_API_KEY is missing/invalid/expired.")
elif res.status_code == 403:
    print("VERDICT: FORBIDDEN -- key is valid but your plan doesn't cover this endpoint.")
elif res.status_code == 404:
    print("VERDICT: NOT FOUND -- check the symbol is correct and supported.")
elif res.status_code == 429:
    print("VERDICT: RATE LIMITED -- too many requests, back off and retry later.")
else:
    print(f"VERDICT: UNEXPECTED STATUS {res.status_code} -- see raw body above.")
