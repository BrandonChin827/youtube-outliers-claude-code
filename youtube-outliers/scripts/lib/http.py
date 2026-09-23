"""Retrying GET and the ScrapeCreators query helper. Stdlib only (urllib)."""

import json
import sys
import time
import urllib.error
import urllib.request

SC_BASE = "https://api.scrapecreators.com"
TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2.0


def request(url, headers, retries=MAX_RETRIES):
    """GET with retry. Returns parsed JSON or None.

    Retries on 429 (exponential backoff) and transient network errors.
    Gives up immediately on other 4xx.
    """
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                sys.stderr.write(f"[outliers] HTTP {e.code} for {url.split('?')[0]}\n")
                return None
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (2 ** attempt) if e.code == 429 else RETRY_DELAY)
        except (urllib.error.URLError, OSError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
    return None


def sc_get(path, params, api_key):
    """ScrapeCreators GET. Returns parsed JSON or None."""
    qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
    headers = {"x-api-key": api_key, "User-Agent": "youtube-outliers/1.0"}
    return request(f"{SC_BASE}{path}?{qs}", headers)
