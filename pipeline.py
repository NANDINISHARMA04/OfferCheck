"""The agent pipeline: run every checker, combine evidence, score.

Flow:
  offer text ──► detect companies ──► email check ──► link check
             ──► text rules ──► salary check ──► (optional) LLM
             ──► scorer ──► Report
"""
from .data import detect_companies, companies
from .email_check import check_email, extract_emails
from .llm_check import check_with_llm
from .models import Finding, Report
from .salary_check import check_salary
from .text_rules import check_text
from .url_check import check_urls, extract_urls, host_of

LOW, HIGH = 25, 60


def analyze(text: str, sender: str | None = None, online: bool = False,
            use_llm: bool = True, community_lookup=None) -> Report:
    """community_lookup: optional function(emails, domains) -> {value: report_count}."""
    text = (text or "").strip()
    mentioned = detect_companies(text)

    findings: list[Finding] = []
    findings += check_email(sender, text, mentioned)
    verified = any(f.check == "email" and f.weight < 0 for f in findings)
    findings += check_urls(text, online=online)
    findings += check_text(text)
    findings += check_salary(text, verified_sender=verified)
    if community_lookup:
        findings += check_community(text, sender, community_lookup)

    summary = None
    if use_llm:
        ai_findings, summary = check_with_llm(text, findings)
        findings += ai_findings

    score = score_findings(findings, verified)
    verdict = verdict_for(score)
    findings.sort(key=lambda f: f.weight, reverse=True)

    return Report(
        risk_score=score,
        verdict=verdict,
        summary=summary or default_summary(score, findings),
        findings=findings,
        extracted={
            "companies_mentioned": [companies()[k]["name"] for k in mentioned],
            "emails": ([sender.lower()] if sender else []) + extract_emails(text),
            "links": extract_urls(text),
            "verified_sender": verified,
        },
    )


def check_community(text, sender, lookup) -> list[Finding]:
    emails = ([sender.lower()] if sender else []) + extract_emails(text)
    domains = {e.split("@")[-1] for e in emails} | {host_of(u) for u in extract_urls(text)}
    found = []
    for value, n in lookup(emails, sorted(domains)).items():
        found.append(Finding("community", "Reported as a scam by other students",
                             f"{value} has been reported {n} time{'s' if n > 1 else ''} "
                             "by students who received fake offers.",
                             min(40, 25 + 5 * n), value))
    return found


def score_findings(findings: list[Finding], verified: bool) -> int:
    score = sum(f.weight for f in findings)
    titles = {f.title for f in findings}

    # Combination rule: a payment request from an unverified sender is almost
    # always a scam, no matter how professional the rest of the letter looks.
    if "Asks you to pay money" in titles and not verified:
        score = max(score, 75)
    # A payment request even from an official-looking address is still a red flag
    # (spoofed headers, compromised accounts).
    elif "Asks you to pay money" in titles:
        score = max(score, 50)
    return max(0, min(100, score))


def verdict_for(score: int) -> str:
    if score >= HIGH:
        return "Likely scam"
    if score >= LOW:
        return "Suspicious"
    return "No major red flags"


def default_summary(score: int, findings: list[Finding]) -> str:
    risky = [f for f in findings if f.weight > 0]
    if not risky:
        return ("We didn't find common scam patterns. Still confirm the offer on the "
                "company's official careers page or with your placement cell before sharing documents.")
    top = ", ".join(f.title[0].lower() + f.title[1:] for f in risky[:3])
    if score >= HIGH:
        return (f"This offer shows strong scam signs: {top}. Do not pay any money or share "
                "documents. Report it to your placement cell and at cybercrime.gov.in.")
    return (f"Some warning signs found: {top}. Verify directly with the company through "
            "its official website before you reply.")
