"""Checker 4: is the salary realistic for a fresher?

Parses amounts like "₹80,000 per month", "Rs 45000/month", "12 LPA",
"18 lakh per annum" and converts everything to yearly rupees.
"""
import re
from .models import Finding

MONTHLY_RE = re.compile(
    r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(k)?\s*(?:/-)?\s*(?:per|/|a|every)\s*(month|day|week)",
    re.IGNORECASE)
LPA_RE = re.compile(r"([\d.]+)\s*(?:lpa|lakhs?\s*(?:per annum|p\.?a\.?|per year|/year|annually))",
                    re.IGNORECASE)

# Rough ceilings for a fresher offer with no strong company signal.
UNREALISTIC_YEARLY = 3_000_000      # 30 LPA
SUSPICIOUS_YEARLY = 1_500_000       # 15 LPA
MULTIPLIER = {"month": 12, "week": 52, "day": 300}


def extract_yearly_amounts(text: str) -> list[tuple[int, str]]:
    amounts = []
    for m in MONTHLY_RE.finditer(text):
        value = float(m.group(1).replace(",", ""))
        if m.group(2):
            value *= 1000
        amounts.append((int(value * MULTIPLIER[m.group(3).lower()]), m.group(0)))
    for m in LPA_RE.finditer(text):
        try:
            amounts.append((int(float(m.group(1)) * 100_000), m.group(0)))
        except ValueError:
            pass
    return amounts


def check_salary(text: str, verified_sender: bool) -> list[Finding]:
    findings = []
    amounts = extract_yearly_amounts(text)
    if not amounts:
        return findings
    yearly, evidence = max(amounts)
    lpa = yearly / 100_000

    # Per-day/per-task earnings in a "job" offer for freshers are a pattern of task scams.
    if re.search(r"per\s*(day|week)|/\s*(day|week)", evidence, re.IGNORECASE):
        findings.append(Finding("salary", "Pays per day or week",
                                "Salaried tech roles pay monthly. Daily payouts are typical "
                                "of task-based scams.", 15, evidence))

    if yearly >= UNREALISTIC_YEARLY and not verified_sender:
        findings.append(Finding("salary", "Salary is unrealistically high",
                                f"About {lpa:.1f} LPA for a fresher from an unverified sender. "
                                "Offers that seem too good usually are.", 20, evidence))
    elif yearly >= SUSPICIOUS_YEARLY and not verified_sender:
        findings.append(Finding("salary", "Salary is higher than typical",
                                f"About {lpa:.1f} LPA. Possible at top companies, but verify "
                                "the offer on the official careers portal.", 8, evidence))
    return findings
