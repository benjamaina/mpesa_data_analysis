"""
main.py
-------
FastAPI application entry point.

Upload flow:
  1. POST /upload              → parse file once, store in session, get session_id back
  2. GET  /transactions        → paginate through transactions using session_id
  3. POST /analyze             → full stats (file re-uploaded, no session needed)
  4. POST /charts/{chart_name} → PNG chart   (file re-uploaded, no session needed)
  5. GET  /charts              → list chart names
  6. DELETE /session/{id}      → explicitly clear a session
"""

import io
import math
import logging
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.services.parser  import parse_statement
from app.services.cleaner    import clean_statement
from app.services.categorizer import categorize_statement, get_category_summary
from app.services.analyzer    import run_full_analysis
from app.services.visualizer  import render_chart, CHART_REGISTRY
from .services.sessions   import store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE     = 200


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitize(obj):
    """Recursively replace NaN/Inf with None so JSONResponse never crashes."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(i) for i in obj]
    return obj


def _run_pipeline(file_bytes: bytes, filename: str, password: str):
    raw_df         = parse_statement(file_bytes, filename, password or None)
    clean_df       = clean_statement(raw_df)
    categorized_df = categorize_statement(clean_df)
    return categorized_df


def _require_session(session_id: str):
    """Look up session or raise a clean 404."""
    session = store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found or has expired (30 min TTL). "
                   "Please upload your statement again."
        )
    return session


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="M-Pesa Statement Analyzer",
    description="Upload your M-Pesa PDF or Excel statement and get spending insights.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handlers ─────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def custom_http_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP {exc.status_code} on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": "An unexpected error occurred. Please try again."},
    )


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "status":          "ok",
        "message":         "M-Pesa Analyzer is online ✅",
        "active_sessions": store.active_count,
    }


# ── Upload (parse once, store in session) ─────────────────────────────────────

@app.post("/upload", tags=["Statement"])
async def upload_statement(
    file:     UploadFile = File(..., description="M-Pesa statement — PDF, Excel, or CSV"),
    password: str        = Form("",  description="PDF password (National ID). Leave blank for Excel/CSV."),
):
    """
    Upload your M-Pesa statement.

    Parses the file **once**, stores it in a session (30 min TTL),
    and returns a `session_id`. Use that session_id with
    `GET /transactions` to page through the data.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    logger.info(f"Upload: {file.filename} ({len(file_bytes):,} bytes)")

    df         = _run_pipeline(file_bytes, file.filename, password)
    session_id = store.save(df, file.filename)

    return JSONResponse(content=_sanitize({
        "status":             "success",
        "session_id":         session_id,
        "total_transactions": len(df),
        "filename":           file.filename,
        "category_summary":   get_category_summary(df),
        "hint":               f"Use GET /transactions?session_id={session_id}&page=1 to browse transactions",
    }))


# ── Paginated transactions ────────────────────────────────────────────────────

@app.get("/transactions", tags=["Statement"])
async def get_transactions(
    session_id: str = Query(..., description="session_id returned by POST /upload"),
    page:       int = Query(1,   ge=1,          description="Page number (starts at 1)"),
    page_size:  int = Query(DEFAULT_PAGE_SIZE,
                            ge=1, le=MAX_PAGE_SIZE,
                            description=f"Rows per page (max {MAX_PAGE_SIZE})"),
    category:   str = Query("",  description="Filter by category name (optional)"),
    tx_type:    str = Query("",  description="Filter by CREDIT or DEBIT (optional)"),
):
    """
    Paginate through transactions for an uploaded statement.

    - Use `session_id` from POST /upload
    - Optionally filter by `category` or `tx_type`
    - Returns `total_pages` so your frontend knows when to stop
    """
    session = _require_session(session_id)
    df      = session.df.copy()

    # ── Optional filters ──────────────────────────────────────────────────────
    if category:
        df = df[df["category"].str.lower() == category.lower()]
        if df.empty:
            return JSONResponse(content={
                "status": "success", "page": page, "page_size": page_size,
                "total_transactions": 0, "total_pages": 0, "transactions": [],
                "filters_applied": {"category": category},
            })

    if tx_type.upper() in ("CREDIT", "DEBIT"):
        df = df[df["transaction_type"] == tx_type.upper()]

    # ── Pagination ────────────────────────────────────────────────────────────
    total        = len(df)
    total_pages  = max(1, math.ceil(total / page_size))

    if page > total_pages:
        raise HTTPException(
            status_code=400,
            detail=f"Page {page} does not exist. This statement has {total_pages} page(s)."
        )

    start  = (page - 1) * page_size
    end    = start + page_size
    slice_ = df.iloc[start:end].copy()
    slice_["date"] = slice_["date"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return JSONResponse(content=_sanitize({
        "status":             "success",
        "session_id":         session_id,
        "page":               page,
        "page_size":          page_size,
        "total_transactions": total,
        "total_pages":        total_pages,
        "has_next":           page < total_pages,
        "has_prev":           page > 1,
        "transactions":       slice_.to_dict(orient="records"),
        "filters_applied": {
            "category": category or None,
            "tx_type":  tx_type.upper() or None,
        },
    }))


# ── Session management ────────────────────────────────────────────────────────

@app.delete("/session/{session_id}", tags=["Statement"])
async def delete_session(session_id: str):
    """Explicitly clear a session before it expires."""
    _require_session(session_id)   # raises 404 if already gone
    store.delete(session_id)
    return {"status": "success", "detail": f"Session {session_id} deleted."}


# ── Analysis ──────────────────────────────────────────────────────────────────

@app.post("/analyze", tags=["Analysis"])
async def analyze_statement(
    file:     UploadFile = File(...),
    password: str        = Form(""),
):
    """Full analysis stats. Re-upload your file here — no session needed."""
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    df       = _run_pipeline(file_bytes, file.filename, password)
    analysis = run_full_analysis(df)

    return JSONResponse(content=_sanitize({"status": "success", "analysis": analysis}))


# ── Charts ────────────────────────────────────────────────────────────────────

@app.get("/charts", tags=["Charts"])
async def list_charts():
    return {
        "available_charts": list(CHART_REGISTRY.keys()),
        "usage": "POST /charts/{chart_name} with your statement file",
    }


@app.post(
    "/charts/{chart_name}",
    tags=["Charts"],
    response_class=StreamingResponse,
    responses={200: {"content": {"image/png": {}}}},
)
async def get_chart(
    chart_name: str,
    file:       UploadFile = File(...),
    password:   str        = Form(""),
):
    """
    Upload your statement and get back a PNG chart.

    Available: **monthly_flow**, **spending_category**,
    **balance_trend**, **spending_day**
    """
    if chart_name not in CHART_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Chart '{chart_name}' not found. Available: {list(CHART_REGISTRY.keys())}"
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    df        = _run_pipeline(file_bytes, file.filename, password)
    analysis  = run_full_analysis(df)
    png_bytes = render_chart(chart_name, analysis)

    return StreamingResponse(
        io.BytesIO(png_bytes),
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename={chart_name}.png"},
    )