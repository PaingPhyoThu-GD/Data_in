"""
Privacy sanitizer and User-Agent parser for zero-PII, GDPR-compliant telemetry.
"""

from __future__ import annotations
import hashlib
import hmac
import re
from datetime import datetime
from urllib.parse import urlparse


def truncate_ip(ip: str) -> str:
    """
    Truncate IP address to remove personal identifier.
    - IPv4: Zeroes the last octet (e.g., 192.168.1.45 -> 192.168.1.0/24)
    - IPv6: Retains the first 3 groups (e.g., 2001:db8:85a3:8d3:: -> 2001:db8:85a3::/48)
    """
    if not ip or not isinstance(ip, str):
        return "0.0.0.0"

    ip = ip.strip()

    # IPv4 check
    if "." in ip and ":" not in ip:
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0"
        return "0.0.0.0"

    # IPv6 check
    if ":" in ip:
        parts = ip.split(":")
        if len(parts) >= 3:
            return f"{parts[0]}:{parts[1]}:{parts[2]}::/48"
        return "::/48"

    return "0.0.0.0"


def generate_visitor_hash(
    ip: str,
    user_agent: str,
    site_id: str = "default",
    date_str: str | None = None,
) -> str:
    """
    Generate a cookieless, non-reversible visitor hash.
    Uses daily rotating salt so cross-day tracking is mathematically impossible.
    Complies with GDPR and ePrivacy without cookie consent banners.
    """
    if date_str is None:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    masked_ip = truncate_ip(ip)
    daily_salt = hashlib.sha256(f"salt_{date_str}_{site_id}".encode("utf-8")).hexdigest()
    raw_identifier = f"{masked_ip}::{user_agent.strip()}::{site_id}".encode("utf-8")

    visitor_hash = hmac.new(
        daily_salt.encode("utf-8"),
        raw_identifier,
        hashlib.sha256,
    ).hexdigest()[:16]

    return f"vh_{visitor_hash}"


def extract_referrer_domain(referrer: str) -> str:
    """
    Extract clean referrer domain or return 'direct' if empty.
    """
    if not referrer or not isinstance(referrer, str):
        return "direct"

    referrer = referrer.strip()
    if not referrer or referrer.lower() in ("direct", "none", "unknown"):
        return "direct"

    try:
        parsed = urlparse(referrer if "://" in referrer else f"https://{referrer}")
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc if netloc else "direct"
    except Exception:
        return "direct"


def parse_user_agent(ua: str) -> tuple[str, str, str]:
    """
    Lightweight, zero-dependency User-Agent heuristic parser.
    Returns: (browser, os, device_type)
    """
    if not ua or not isinstance(ua, str):
        return ("Unknown", "Unknown", "desktop")

    ua_lower = ua.lower()

    # Device type
    if any(bot in ua_lower for bot in ("bot", "spider", "crawler", "archiver", "curl", "wget", "headless")):
        device_type = "bot"
    elif any(tab in ua_lower for tab in ("tablet", "ipad", "playbook", "silk")):
        device_type = "tablet"
    elif any(mob in ua_lower for mob in ("mobile", "iphone", "android", "phone")):
        device_type = "mobile"
    else:
        device_type = "desktop"

    # Operating System
    if "windows" in ua_lower:
        os = "Windows"
    elif "macintosh" in ua_lower or "mac os" in ua_lower:
        os = "macOS"
    elif "iphone" in ua_lower or "ipad" in ua_lower or "ios" in ua_lower:
        os = "iOS"
    elif "android" in ua_lower:
        os = "Android"
    elif "linux" in ua_lower:
        os = "Linux"
    elif "crkey" in ua_lower or "chromecast" in ua_lower:
        os = "ChromeOS"
    else:
        os = "Unknown"

    # Browser
    if "edg/" in ua_lower or "edge/" in ua_lower:
        browser = "Edge"
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "chrome/" in ua_lower:
        browser = "Chrome"
    elif "firefox/" in ua_lower:
        browser = "Firefox"
    elif "safari/" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "curl" in ua_lower:
        browser = "cURL"
    else:
        browser = "Other"

    return (browser, os, device_type)
