"""Web server. Run:  uvicorn app.main:app --reload
Then open http://127.0.0.1:8000
API docs (auto-generated): http://127.0.0.1:8000/docs
"""
import time
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from .analyzer import analyze
from .analyzer.llm_check import llm_enabled
from .extract import ExtractionError, extract_text

STATIC = Path(__file__).resolve().parent / "static"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()          # create tables on startup
    yield


app = FastAPI(title="Offer Check: fake job & internship detector", version="1.0.0",
              lifespan=lifespan)


# ---------- simple in-memory rate limiter (sliding window) ----------
WINDOW_SECONDS, MAX_REQUESTS = 60, 20
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    if len(q) >= MAX_REQUESTS:
        raise HTTPException(429, "Too many checks. Wait a minute and try again.")
    q.append(now)


# ---------- request models ----------
class AnalyzeIn(BaseModel):
    text: str = Field(..., min_length=10, max_length=20_000)
    sender: str | None = Field(None, max_length=200)
    check_domain_age: bool = False


class ReportIn(BaseModel):
    kind: str = Field(..., pattern="^(email|domain)$")
    value: str = Field(..., min_length=3, max_length=200)
    company_claimed: str | None = Field(None, max_length=100)
    note: str | None = Field(None, max_length=500)


def run_analysis(text: str, sender: str | None, online: bool) -> dict:
    report = analyze(text, sender=sender or None, online=online,
                     community_lookup=db.report_counts)
    db.log_analysis(report.risk_score, report.verdict)
    out = report.to_dict()
    out["ai_used"] = llm_enabled()
    return out


# ---------- app pages (PWA) ----------
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/sw.js")
def service_worker():
    # Served from the root so it can control the whole app.
    return FileResponse(STATIC / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


@app.post("/share-target")
async def share_target(text: str | None = Form(None), title: str | None = Form(None),
                       url: str | None = Form(None)):
    """Fallback when the service worker isn't active yet: pass shared text via the URL."""
    from urllib.parse import quote
    shared = "\n".join(x for x in (title, text, url) if x)[:4000]
    return RedirectResponse(f"/?text={quote(shared)}" if shared else "/", status_code=303)


# ---------- API ----------

@app.post("/api/analyze")
def analyze_text(body: AnalyzeIn, request: Request):
    rate_limit(request)
    return run_analysis(body.text, body.sender, body.check_domain_age)


@app.post("/api/analyze-file")
async def analyze_file(request: Request, file: UploadFile = File(...),
                       sender: str | None = Form(None), check_domain_age: bool = Form(False)):
    rate_limit(request)
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 5 MB.")
    try:
        text = extract_text(file.filename or "", data)
    except ExtractionError as e:
        raise HTTPException(422, str(e))
    result = run_analysis(text, sender, check_domain_age)
    result["extracted_text"] = text[:3000]
    return result


@app.post("/api/reports", status_code=201)
def report_scam(body: ReportIn, request: Request):
    rate_limit(request)
    value = body.value.lower().strip()
    if body.kind == "email" and "@" not in value:
        raise HTTPException(422, "Enter a full email address.")
    if body.kind == "domain":
        value = value.removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/")[0]
    report_id = db.add_report(body.kind, value, body.company_claimed, body.note)
    return {"id": report_id, "value": value}


@app.get("/api/stats")
def get_stats():
    return db.stats()


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_enabled": llm_enabled()}
