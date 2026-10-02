"""Checker 5 (optional): an LLM second opinion.

Rules catch known patterns. The LLM catches new wording the rules miss
and writes a plain-language explanation. It only runs if an API key is
set, and its influence on the score is capped, so the rules stay the
backbone and the system still works offline.
"""
import json
import os
import re
import urllib.request

from .models import Finding

API_URL = "https://api.anthropic.com/v1/messages"
MAX_LLM_WEIGHT = 30   # LLM can add at most this much risk in total

PROMPT = """You are a fraud analyst protecting Indian college students from fake job and
internship offers. Analyse the offer below. Rule-based checks already found:
{rule_titles}

Return ONLY a JSON object, no markdown, in this exact shape:
{{"extra_red_flags": [{{"title": "...", "detail": "...", "severity": 1-5, "evidence": "short quote"}}],
  "plain_summary": "2-3 simple sentences a student can understand"}}

Only list red flags NOT already covered above. Do not invent facts. If the offer looks
genuine, return an empty list.

OFFER:
\"\"\"{offer}\"\"\""""


def llm_enabled() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def check_with_llm(text: str, existing: list[Finding], timeout: float = 25.0):
    """Returns (findings, summary). Returns ([], None) if disabled or on error."""
    if not llm_enabled():
        return [], None
    titles = "\n".join(f"- {f.title}" for f in existing) or "- (none)"
    body = {
        "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"),
        "max_tokens": 800,
        "messages": [{"role": "user",
                      "content": PROMPT.format(rule_titles=titles, offer=text[:6000])}],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        raw = "".join(b.get("text", "") for b in data.get("content", []))
        parsed = parse_json(raw)
    except Exception:
        return [], None

    findings, budget = [], MAX_LLM_WEIGHT
    for flag in parsed.get("extra_red_flags", [])[:5]:
        severity = max(1, min(5, int(flag.get("severity", 1))))
        weight = min(severity * 5, budget)
        if weight <= 0:
            break
        budget -= weight
        findings.append(Finding("ai", str(flag.get("title", "AI flagged an issue"))[:120],
                                str(flag.get("detail", ""))[:400], weight,
                                str(flag.get("evidence", ""))[:200]))
    return findings, parsed.get("plain_summary")


def parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    return json.loads(cleaned[start:end + 1]) if start != -1 else {}
