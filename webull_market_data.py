"""
Eulerpool L2 connection test.

Currently used ONLY to verify the Eulerpool Level 2 connection is working
(auth + data availability) before this is merged back with the Webull
Level 1 streaming code. File name kept as webull_market_data.py to match
the existing GitHub Actions workflow -- swap the CONTENTS back to the
combined Webull+Eulerpool version once Eulerpool L2 access is confirmed
working.

Requires:
    pip install requests

Env vars:
    EULERPOOL_API_KEY     -> your Eulerpool API token (required)
    EULERPOOL_TEST_SYMBOL -> ticker to test with (optional, default "AAPL")
"""

import os
import sys
import time

import requests

EULERPOOL_API_KEY = os.environ.get("EULERPOOL_API_KEY")
SYMBOL = os.environ.get("EULERPOOL_TEST_SYMBOL", "AAPL")
URL = f"https://api.eulerpool.com/api/1/market/l2/{SYMBOL}"

if not EULERPOOL_API_KEY:
    sys.exit("Missing EULERPOOL_API_KEY environment variable.")


def masked(key, keep=4):
    if len(key) <= keep:
        return "*" * len(key)
    return key[:keep] + "*" * (len(key) - keep)


print("=== Eulerpool L2 connection test ===")
print(f"Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
print(f"URL       : {URL}")
print(f"Token     : {masked(EULERPOOL_API_KEY)}")
print(f"Symbol    : {SYMBOL}")
print("-" * 40)

try:
    res = requests.get(
        URL,
        params={"token": EULERPOOL_API_KEY},
        headers={"Accept": "application/json"},
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
    print("VERDICT: CONNECTION OK -- Eulerpool returned data.")
    try:
        data = res.json()
        print(f"Parsed JSON: {data}")
    except Exception:
        print("(Body was not valid JSON despite HTTP 200.)")
elif res.status_code == 401:
    print("VERDICT: AUTH FAILED -- EULERPOOL_API_KEY is missing/invalid/expired.")
elif res.status_code == 403:
    print("VERDICT: FORBIDDEN -- key is valid but lacks permission for this endpoint/plan.")
elif res.status_code == 404:
    print("VERDICT: NOT CONFIGURED -- key authenticated, but no L2 data for this symbol.")
    print("         This is very likely the documented (but unexplained) Polygon.io")
    print("         dependency -- check your Eulerpool dashboard for a Polygon.io/")
    print("         data-source integration setting, or email api@eulerpool.com.")
elif res.status_code == 429:
    print("VERDICT: RATE LIMITED -- too many requests, back off and retry later.")
else:
    print(f"VERDICT: UNEXPECTED STATUS {res.status_code} -- see raw body above.")
