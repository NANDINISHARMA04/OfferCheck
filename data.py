"""Loads companies.json once and offers small helper functions."""
import json
import re
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "companies.json"


@lru_cache(maxsize=1)
def load_data() -> dict:
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def companies() -> dict:
    return load_data()["companies"]


def official_domains() -> set[str]:
    return {d for c in companies().values() for d in c["domains"]}


def detect_companies(text: str) -> list[str]:
    """Return keys of known companies mentioned in the text."""
    lowered = text.lower()
    found = []
    for key, info in companies().items():
        names = {key, info["name"].lower()}
        if any(re.search(rf"\b{re.escape(n)}\b", lowered) for n in names):
            found.append(key)
    return found


def domain_matches(domain: str, allowed: str) -> bool:
    """True if domain is exactly `allowed` or a subdomain of it (careers.tcs.com)."""
    domain = domain.lower().strip(".")
    return domain == allowed or domain.endswith("." + allowed)


def is_official(domain: str) -> str | None:
    """Return the company key if this domain belongs to a known company."""
    for key, info in companies().items():
        if any(domain_matches(domain, d) for d in info["domains"]):
            return key
    return None
