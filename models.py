"""Shared data types used by every checker.

Each checker returns a list of Finding objects. The scorer combines them
into one risk score. Keeping one common format means you can add a new
checker later without touching the others.
"""
from dataclasses import dataclass, field, asdict


@dataclass
class Finding:
    check: str          # which checker produced it, e.g. "email"
    title: str          # short human-readable title
    detail: str         # explanation shown to the student
    weight: int         # how much risk it adds (negative = makes it look safer)
    evidence: str = ""  # the exact text that triggered it

    def to_dict(self):
        return asdict(self)


@dataclass
class Report:
    risk_score: int
    verdict: str
    summary: str
    findings: list = field(default_factory=list)
    extracted: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "risk_score": self.risk_score,
            "verdict": self.verdict,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "extracted": self.extracted,
        }
