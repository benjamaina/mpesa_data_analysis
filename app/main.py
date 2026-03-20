"""
main.py
-------
FastAPI application entry point.

Endpoints:
  GET  /                          → health check
  POST /upload                    → parse + clean + categorize → JSON
  POST /analyze                   → full analysis stats → JSON (no charts)
  POST /charts/{chart_name}       → upload file, get back a PNG image directly
  GET  /charts                    → list available chart names
"""

import math
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import io

from app.services.parser      import parse_statement
from app.services.cleaner     import clean_statement
from app.services.categorizer import categorize_statement, get_category_summary
from app.services.analyzer    import run_full_analysis
from app.services.visualizer  import render_chart, CHART_REGISTRY


def _sanitize(obj):
    """Replace NaN/Inf with None so JSONResponse never crashes."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(i) for i in obj]
    return obj


def _run_pipeline(file_bytes: bytes, filename: str, password: str):
    """Shared parse → clean → categorize pipeline."""
    raw_df         = parse_statement(file_bytes, filename, password or None)
    clean_df       = clean_statement(raw_df)
    categorized_df = categorize_statement(clean_df)
    return categorized_df


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


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {"message": "M-Pesa Analyzer is online ✅"}


# ── Upload & parse ─────────────────────────────────────────────────────────────

@app.post("/upload", tags=["Statement"])
async def upload_statement(
    file: UploadFile = File(..., description="M-Pesa statement — PDF, Excel, or CSV"),
    password: str    = Form("",  description="PDF password (National ID). Leave blank for Excel/CSV."),
):
    """
    Upload your M-Pesa statement.
    Returns all cleaned & categorised transactions as JSON.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    df = _run_pipeline(file_bytes, file.filename, password)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return JSONResponse(content=_sanitize({
        "status":             "success",
        "total_transactions": len(df),
        "columns":            list(df.columns),
        "transactions":       df.to_dict(orient="records"),
        "category_summary":   get_category_summary(df),
    }))


# ── Analysis (stats only, no charts) ─────────────────────────────────────────

@app.post("/analyze", tags=["Analysis"])
async def analyze_statement(
    file: UploadFile = File(...),
    password: str    = Form(""),
):
    """
    Full analysis of your M-Pesa statement — stats only.
    For charts, use POST /charts/{chart_name} instead.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    df       = _run_pipeline(file_bytes, file.filename, password)
    analysis = run_full_analysis(df)

    return JSONResponse(content=_sanitize({"status": "success", "analysis": analysis}))


# ── Charts ────────────────────────────────────────────────────────────────────

@app.get("/charts", tags=["Charts"])
async def list_charts():
    """List all available chart names you can request."""
    return {
        "available_charts": list(CHART_REGISTRY.keys()),
        "usage": "POST /charts/{chart_name} with your statement file",
    }


@app.post("/charts/{chart_name}", tags=["Charts"],
          response_class=StreamingResponse,
          responses={200: {"content": {"image/png": {}}}})
async def get_chart(
    chart_name: str,
    file: UploadFile = File(..., description="M-Pesa statement — PDF, Excel, or CSV"),
    password: str    = Form("", description="PDF password (National ID). Leave blank for Excel/CSV."),
):
    """
    Upload your statement and get back a single PNG chart directly.

    Available chart names:
    - **monthly_flow**      — Money In vs Out per month
    - **spending_category** — Spending share by category (donut)
    - **balance_trend**     — Balance over time
    - **spending_day**      — Average spending by day of week
    """
    if chart_name not in CHART_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Chart '{chart_name}' not found. "
                   f"Available: {list(CHART_REGISTRY.keys())}"
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    df       = _run_pipeline(file_bytes, file.filename, password)
    analysis = run_full_analysis(df)

    try:
        png_bytes = render_chart(chart_name, analysis)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chart generation failed: {e}")

    return StreamingResponse(
        io.BytesIO(png_bytes),
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename={chart_name}.png"},
    )