"""Checker 1: red-flag phrases in the offer text.

Improvement over the simple keyword list from Step 2: we use regular
expressions with context. For example "pay" alone is NOT flagged
(real offers mention "salary payment"), but "pay ... registration fee"
or "deposit Rs 2000" IS flagged.
"""
import re
from .models import Finding

# Each rule: (title, regex, weight, explanation)
RULES = [
    (
        "Asks you to pay money",
        r"\b(pay|deposit|transfer|send)\b[^.\n]{0,60}\b(fee|fees|deposit|charges?|amount|rs\.?|inr|₹)"
        r"|\b(registration|training|security|joining|processing|verification|kit|laptop|refundable)\s+(fee|fees|deposit|charges?|amount)",
        35,
        "Genuine companies never ask candidates to pay for registration, training, "
        "laptops or verification. This is the most common fresher scam.",
    ),
    (
        "Payment through UPI / personal account",
        r"\b(upi|gpay|google pay|phonepe|paytm)\b|@(ok\w+|ybl|ibl|axl|paytm)\b",
        20,
        "Company payments never go to a personal UPI ID or wallet.",
    ),
    (
        "Pressure to act immediately",
        r"\b(urgent(ly)?|immediately|within\s+\d+\s+(hours?|hrs?)|today itself|last chance|"
        r"limited seats?|offer (will )?expires?|asap)\b",
        12,
        "Scammers create urgency so you don't have time to verify.",
    ),
    (
        "Selected without a proper interview",
        r"\b(no interview|without (any )?interview|direct (selection|joining)|"
        r"selected based on (your )?(resume|profile)|shortlisted from (naukri|linkedin|indeed))\b",
        20,
        "Real fresher hiring has an assessment or interview round.",
    ),
    (
        "Communication moved to WhatsApp / Telegram",
        r"\b(whatsapp|telegram)\b",
        10,
        "Official HR processes run on company email and portals, not chat apps.",
    ),
    (
        "Task-based / like-and-earn work",
        r"\b(like (and|&) (share|subscribe)|rate (hotels|products)|youtube (likes|videos)|"
        r"prepaid task|daily (income|earning)|earn (rs\.?|₹)\s*\d+\s*(per|/)\s*(day|task))\b",
        30,
        "'Earn per task' jobs are a well-known scam pattern that ends in deposits.",
    ),
    (
        "Vague work-from-home earning offer",
        r"\b(part[- ]time job|work from home|wfh)\b[^\n]{0,80}\b(earn|income|salary)\b",
        10,
        "Vague home-based jobs promising easy earnings are often the first step of a task scam.",
    ),
    (
        "Asks for sensitive documents or bank details early",
        r"\b(otp|cvv|atm pin|net ?banking password|bank (login|password))\b",
        30,
        "No employer needs your OTP, PIN or banking password.",
    ),
    (
        "Guaranteed job promise",
        r"\b(100% (job|placement) guarantee|guaranteed (job|placement|selection))\b",
        15,
        "Guaranteed jobs, especially tied to a fee, are a classic trap.",
    ),
]

# Signals that a message looks like a normal corporate process.
SAFE_RULES = [
    (
        "Mentions a formal assessment process",
        r"\b(online assessment|coding (round|test)|technical interview|hr interview|assessment link)\b",
        -8,
        "Mentions a normal selection process.",
    ),
]


def check_text(text: str) -> list[Finding]:
    findings = []
    lowered = text.lower()
    for title, pattern, weight, detail in RULES + SAFE_RULES:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            findings.append(
                Finding(
                    check="text",
                    title=title,
                    detail=detail,
                    weight=weight,
                    evidence=_snippet(text, match.start(), match.end()),
                )
            )
    return findings


def _snippet(text: str, start: int, end: int, pad: int = 30) -> str:
    """Return the matched text with a little context around it."""
    s = max(0, start - pad)
    e = min(len(text), end + pad)
    prefix = "…" if s > 0 else ""
    suffix = "…" if e < len(text) else ""
    return prefix + text[s:e].strip().replace("\n", " ") + suffix
