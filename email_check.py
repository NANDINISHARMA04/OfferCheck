"""Checker 2: who sent the offer?

Catches three tricks:
  1. Big-company offer sent from Gmail/Yahoo.
  2. Lookalike domains: infosys-careers.com, hr-tcs.in
  3. Typo domains: inf0sys.com, wipr0.com, accentur.com
"""
import re
from difflib import SequenceMatcher

from .data import companies, load_data, is_official
from .models import Finding

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")

# Homoglyph substitutions scammers use: 0→o, 1→l, etc.
HOMOGLYPHS = str.maketrans({"0": "o", "1": "l", "3": "e", "5": "s", "4": "a", "7": "t"})


def extract_emails(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).lower() for m in EMAIL_RE.finditer(text)))


def check_email(sender: str | None, text: str, mentioned: list[str]) -> list[Finding]:
    emails = [sender.lower().strip()] if sender else []
    emails += [e for e in extract_emails(text) if e not in emails]
    findings = []
    free = set(load_data()["free_email_providers"])

    for email in emails:
        domain = email.split("@")[-1]
        owner = is_official(domain)

        if owner:
            findings.append(Finding(
                "email", f"Email domain belongs to {companies()[owner]['name']}",
                "The address uses the company's official domain. Good sign, but "
                "headers can be spoofed, so still confirm on the official careers page.",
                -15, email))
            continue

        if domain in free and mentioned:
            name = companies()[mentioned[0]]["name"]
            findings.append(Finding(
                "email", "Company offer sent from a free email account",
                f"The message claims to be from {name}, but it came from {domain}. "
                "Large companies always use their own domain for HR mail.",
                30, email))
            continue

        lookalike = find_lookalike(domain)
        if lookalike:
            key, reason = lookalike
            findings.append(Finding(
                "email", "Lookalike company domain",
                f"{domain} {reason} {companies()[key]['name']}, but it is not an official "
                f"domain (official: {', '.join(companies()[key]['domains'])}).",
                35, email))
        elif domain in free:
            findings.append(Finding(
                "email", "Sent from a free email account",
                "Recruiters at registered companies usually write from a company domain.",
                10, email))
    return findings


def find_lookalike(domain: str):
    """Return (company_key, reason) if the domain imitates a known company."""
    domain = domain.lower()
    stem = domain.split(".")[0]                       # "infosys-careers"
    normalized = stem.translate(HOMOGLYPHS)
    parts = re.split(r"[-_.]", domain.translate(HOMOGLYPHS))

    for key, info in companies().items():
        brand = key.replace(" ", "")
        if len(brand) < 3:
            continue
        # Brand appears inside another domain: infosys-careers.com, hr.tcs-jobs.in
        if any(brand == p or (len(brand) >= 4 and brand in p) for p in parts):
            return key, "uses the brand name of"
        # Character swap or typo: inf0sys, infosis, acenture
        if stem != normalized and normalized == brand:
            return key, "swaps letters for numbers to imitate"
        if len(brand) >= 5 and SequenceMatcher(None, normalized, brand).ratio() >= 0.85:
            return key, "is spelled very close to"
    return None
