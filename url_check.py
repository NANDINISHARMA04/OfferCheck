"""Checker 3: links inside the offer.

Offline checks: shorteners, suspicious TLDs, raw IP links, plain http,
lookalike domains.
Online check (optional): domain age via the public RDAP service.
A website created a few weeks ago that claims to be a big company's
careers portal is a strong scam signal.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

from .data import companies, load_data, is_official
from .email_check import find_lookalike
from .models import Finding

BARE_TLDS = r"com|in|net|org|xyz|top|online|site|info|live|co\.in|ly|me|io|co|gl|at|gd|cc|link|click|shop|work"
URL_RE = re.compile(
    rf"\b((?:https?://|www\.)[^\s<>\"')\]]+|(?:[a-z0-9-]+\.)+(?:{BARE_TLDS})\b(?:/[^\s<>\"')\]]*)?)",
    re.IGNORECASE)
EMAIL_SPAN_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

_age_cache: dict[str, int | None] = {}


def extract_urls(text: str) -> list[str]:
    # Blank out email addresses first so "hr.infosys@gmail.com" isn't read as a link.
    text = EMAIL_SPAN_RE.sub(" ", text)
    urls = []
    for m in URL_RE.finditer(text):
        urls.append(m.group(1).rstrip(".,;:!"))
    return list(dict.fromkeys(urls))


def host_of(url: str) -> str:
    if not url.lower().startswith(("http://", "https://")):
        url = "http://" + url
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def check_urls(text: str, online: bool = False) -> list[Finding]:
    data = load_data()
    findings = []
    for url in extract_urls(text):
        host = host_of(url)
        if not host:
            continue
        if is_official(host):
            continue

        if host in data["url_shorteners"]:
            findings.append(Finding("link", "Shortened link hides the real website",
                                    "Short links hide where they lead. Expand it with a link "
                                    "checker before opening.", 12, url))
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
            findings.append(Finding("link", "Link points to a raw IP address",
                                    "Legitimate career portals use domain names.", 20, url))
        tld = host.rsplit(".", 1)[-1]
        if tld in data["suspicious_tlds"]:
            findings.append(Finding("link", f"Uses a cheap .{tld} domain",
                                    f".{tld} domains are cheap and frequently used for scams.",
                                    12, url))
        if url.lower().startswith("http://"):
            findings.append(Finding("link", "Website is not secure (http)",
                                    "Application forms asking for personal data should use https.",
                                    5, url))
        look = find_lookalike(host)
        if look:
            key, reason = look
            findings.append(Finding("link", "Lookalike careers website",
                                    f"{host} {reason} {companies()[key]['name']} but is not "
                                    "their official site.", 30, url))

        if online:
            age = domain_age_days(host)
            if age is not None and age < 180:
                findings.append(Finding("link", "Website was created very recently",
                                        f"{host} was registered about {age} days ago. "
                                        "New domains are a strong scam signal.",
                                        25 if age < 60 else 15, url))
    return findings


def registrable_domain(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in {"co.in", "org.in", "net.in", "co.uk"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def domain_age_days(host: str, timeout: float = 4.0) -> int | None:
    """Look up the registration date via RDAP. Returns None if unavailable."""
    domain = registrable_domain(host)
    if domain in _age_cache:
        return _age_cache[domain]
    age = None
    try:
        req = urllib.request.Request(f"https://rdap.org/domain/{domain}",
                                     headers={"Accept": "application/rdap+json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.load(resp)
        for event in payload.get("events", []):
            if event.get("eventAction") == "registration":
                created = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - created).days
                break
    except Exception:
        age = None   # offline, rate-limited or unknown TLD: skip quietly
    _age_cache[domain] = age
    return age
