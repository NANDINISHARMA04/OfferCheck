# Offer Check: Fake Job & Internship Scam Detector

An AI-assisted tool that tells Indian students whether a job or internship offer is real or a scam, and **explains exactly why**, with evidence from the offer itself.

Paste an email, upload an offer letter PDF or a WhatsApp screenshot, and get a risk score (0–100), a verdict, and every warning sign highlighted.

## Features

- **Sender verification:** catches big-company offers sent from Gmail/Yahoo, lookalike domains (`infosys-careers.com`) and typo domains (`inf0sys.com`, `acenture.com`)
- **Link analysis:** shortened links, cheap TLDs (`.xyz`, `.top`), raw IP links, non-https forms, fake careers portals, and optional **domain age lookup** via RDAP
- **Context-aware text rules:** detects fee/deposit requests, UPI payments, urgency pressure, "no interview" selection, task-based earning scams, OTP/PIN requests, without flagging normal phrases like "salary payment"
- **Salary realism check:** parses "₹85,000 per month", "12 LPA", "18 lakh per annum" and flags unrealistic or per-day pay
- **Community reports:** students report scam emails/websites; every future check warns others (SQLite)
- **AI second opinion (optional):** an LLM catches new scam wording the rules miss and writes a plain-language summary. Its score impact is capped, so the system stays explainable and works without an API key
- **File upload:** PDF text extraction and screenshot OCR
- **Installable mobile app (PWA):** home-screen icon, works like a native app, Hindi / English toggle, light and dark mode, check history saved on the phone
- **Share to app:** on Android, share a WhatsApp message or screenshot straight to Offer Check and it checks it automatically (Web Share Target API)
- **Privacy:** offer text is never stored, only the score and verdict for statistics
- **Rate limiting:** sliding-window limiter per IP

## How it works

```
             ┌──────────────── analyze(text, sender) ────────────────┐
offer text ─►│ detect companies → email check → link check           │
             │ → text rules → salary check → community DB → (LLM)    │──► risk score + verdict
             │ each checker returns Findings(title, detail, weight,  │    + evidence list
             │ evidence) → scorer sums weights + combination rules   │
             └───────────────────────────────────────────────────────┘
```

**Scoring:** every finding has a weight (negative weights mean "looks legitimate"). Weights are summed and clamped to 0–100. One **combination rule** overrides the sum: a payment request from an unverified sender is always at least 75, because that pattern is almost never legitimate. Verdicts: below 25 "No major red flags", 25–59 "Suspicious", 60+ "Likely scam".

**Why rules + AI instead of only AI:** rules are fast, free, testable and explainable. The LLM adds coverage for new wording. Capping its weight means one bad AI answer can't flip a verdict.

## Project structure

```
app/
  analyzer/
    models.py        Finding and Report data types
    data.py          loads company list, detects company names
    email_check.py   sender domain, lookalike and typo detection
    url_check.py     link checks + RDAP domain age
    text_rules.py    red-flag phrase rules (regex with context)
    salary_check.py  salary parsing and realism check
    llm_check.py     optional AI second opinion
    pipeline.py      runs all checkers and scores the result
  data/companies.json  official company domains, free email providers, risky TLDs
  db.py              SQLite: community reports and anonymous stats
  extract.py         PDF / image → text
  main.py            FastAPI server and API routes
  static/index.html          the app interface (Hindi/English, light/dark)
  static/manifest.webmanifest  PWA settings: name, icons, share target
  static/sw.js               service worker: offline + receiving shares
  static/icons/              app icons
tests/               15 unit tests
samples/             example scam and genuine offers
cli.py               check a file from the terminal
```

## Run it locally

```bash
# 1. Create a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 2. Install
pip install -r requirements.txt

# 3. Start the server
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Interactive API docs are at http://127.0.0.1:8000/docs.

**Quick test without the server:**

```bash
python cli.py samples/fake_gmail_fee.txt
python cli.py samples/genuine.txt --sender campus.hiring@accenture.com
```

**Run tests:** `python -m unittest discover tests`

**Turn on the AI second opinion (optional):** copy `.env.example` to `.env`, add your Anthropic API key, then set it in your terminal before starting (`set ANTHROPIC_API_KEY=...` on Windows, `export ANTHROPIC_API_KEY=...` on Mac/Linux).

**Screenshot OCR (optional):** `pip install pytesseract pillow` and install Tesseract (Windows installer: github.com/UB-Mannheim/tesseract/wiki).

## Install it as a phone app

A PWA can only be installed from an **https** address, so deploy first (see below), then open the link on your phone:

- **Android (Chrome):** menu ⋮ → *Install app* / *Add to Home screen*. After installing, "Offer Check" appears in the phone's Share menu, so you can share a WhatsApp message or screenshot directly to it.
- **iPhone (Safari):** Share → *Add to Home Screen*. (iOS doesn't support receiving shares from other apps, so use Paste or Screenshot inside the app.)

How it works: `manifest.webmanifest` describes the app (name, icons, share target), and `sw.js` is a service worker that caches the app so it opens offline and receives shared content. History is stored only in the phone's localStorage, never on the server.

## API

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/analyze` | `{text, sender?, check_domain_age?}` → report |
| POST | `/api/analyze-file` | multipart file upload → report |
| POST | `/api/reports` | `{kind: email/domain, value, company_claimed?, note?}` |
| GET | `/api/stats` | offers checked, scams flagged, most reported |
| GET | `/api/health` | status and whether AI is enabled |

## Deploy (free)

On Render: New → Web Service → connect the GitHub repo. Build command `pip install -r requirements.txt`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Note that free instances reset local files, so for permanent community reports switch SQLite to a hosted PostgreSQL later.

## Roadmap

- [ ] Move community reports to PostgreSQL and add moderation (stop fake reports)
- [ ] Expand `companies.json` to 200+ companies
- [ ] Evaluation set of 100 labelled real/fake offers; publish precision and recall
- [ ] WhatsApp bot so students can forward offers directly
- [ ] Browser extension that checks Gmail offers in place
- [ ] Hindi / Hinglish rule support

## Limitations

This tool gives a risk estimate, not a guarantee. Email headers can be spoofed, and a "No major red flags" result still means you should verify through the official careers page or your placement cell.
