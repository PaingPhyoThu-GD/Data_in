"""
Network fetcher for public YouTube channel pages.
"""

from __future__ import annotations
import re
import urllib.error
import urllib.parse
import urllib.request


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Standard cookies to bypass regional consent dialogs
CONSENT_COOKIE = "SOCS=CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg; CONSENT=YES+cb"


def normalize_channel_url(query: str) -> str:
    """
    Normalizes a channel handle, ID, or URL into a canonical /videos URL.
    Examples:
        "@veritasium" -> "https://www.youtube.com/@veritasium/videos"
        "veritasium" -> "https://www.youtube.com/@veritasium/videos"
        "https://www.youtube.com/@veritasium" -> "https://www.youtube.com/@veritasium/videos"
        "https://www.youtube.com/channel/UC..." -> "https://www.youtube.com/channel/UC.../videos"
    """
    q = query.strip()
    if not q:
        raise ValueError("Channel query cannot be empty.")

    # Already full URL
    if q.startswith("http://") or q.startswith("https://"):
        parsed = urllib.parse.urlparse(q)
        path = parsed.path.rstrip("/")
        if not path.endswith("/videos") and not path.endswith("/shorts") and not path.endswith("/featured"):
            path = f"{path}/videos"
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

    # Starts with @
    if q.startswith("@"):
        return f"https://www.youtube.com/{q}/videos"

    # Channel ID (starts with UC and roughly 24 chars)
    if q.startswith("UC") and len(q) >= 20:
        return f"https://www.youtube.com/channel/{q}/videos"

    # Plain username / handle without @
    return f"https://www.youtube.com/@{q}/videos"


def fetch_channel_html(query_or_url: str, timeout: int = 15) -> str:
    """
    Fetches the public YouTube channel HTML page.
    """
    target_url = normalize_channel_url(query_or_url)

    req = urllib.request.Request(
        target_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": CONSENT_COOKIE,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"YouTube channel not found (404) for query '{query_or_url}'. Please check handle/URL.")
        raise RuntimeError(f"HTTP error {e.code} while fetching YouTube channel: {e.reason}")
    except urllib.error.URLError as e:
        raise ConnectionError(f"Network error connecting to YouTube: {e.reason}")
    except TimeoutError:
        raise TimeoutError(f"Request timed out after {timeout} seconds fetching YouTube channel.")

