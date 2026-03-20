"""
parser.py
---------
Accepts an uploaded M-Pesa statement (PDF or Excel/CSV) and returns
a raw pandas DataFrame with the transaction table.

Supported formats:
  - PDF  (.pdf)  — password-protected Safaricom statement
  - Excel (.xlsx / .xls)
  - CSV   (.csv)
"""

import io
import pandas as pd
from fastapi import HTTPException

# Optional PDF dependencies — only imported when a PDF is uploaded
def _parse_pdf(file_bytes: bytes, password: str | None) -> pd.DataFrame:
    """Extract the transaction table from a Safaricom PDF statement."""
    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="pdfplumber is not installed. Run: pip install pdfplumber"
        )

    all_rows = []
    headers = None

    with pdfplumber.open(io.BytesIO(file_bytes), password=password or "") as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                # First row that looks like M-Pesa headers becomes the header
                if headers is None:
                    # Detect header row by looking for known column names
                    for i, row in enumerate(table):
                        row_text = " ".join(str(c) for c in row if c).lower()
                        if "receipt" in row_text or "completion time" in row_text:
                            headers = [str(c).strip() if c else f"col_{j}"
                                       for j, c in enumerate(row)]
                            all_rows.extend(table[i + 1:])
                            break
                    else:
                        all_rows.extend(table)
                else:
                    all_rows.extend(table)

    if not all_rows:
        raise HTTPException(
            status_code=422,
            detail="No transaction table found in the PDF. "
                   "Make sure this is a valid M-Pesa statement."
        )

    if headers is None:
        # Fallback: use standard M-Pesa column names
        headers = [
            "Receipt No", "Completion Time", "Details",
            "Transaction Status", "Paid In", "Withdrawn", "Balance"
        ]

    # Trim rows to match header length
    n = len(headers)
    trimmed = [row[:n] for row in all_rows if any(c for c in row)]
    df = pd.DataFrame(trimmed, columns=headers)
    return df


def _parse_excel(file_bytes: bytes) -> pd.DataFrame:
    """Read an Excel M-Pesa statement into a DataFrame."""
    try:
        # Try reading; M-Pesa Excel exports sometimes have a few header rows to skip
        for skip in range(0, 7):
            df = pd.read_excel(io.BytesIO(file_bytes), skiprows=skip)
            cols = " ".join(df.columns.astype(str)).lower()
            if "receipt" in cols or "completion" in cols or "paid in" in cols:
                return df
        # If we never matched, just return as-is
        return pd.read_excel(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to read Excel file: {e}")


def _parse_csv(file_bytes: bytes) -> pd.DataFrame:
    """Read a CSV M-Pesa statement into a DataFrame."""
    try:
        for skip in range(0, 7):
            df = pd.read_csv(io.BytesIO(file_bytes), skiprows=skip)
            cols = " ".join(df.columns.astype(str)).lower()
            if "receipt" in cols or "completion" in cols or "paid in" in cols:
                return df
        return pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to read CSV file: {e}")


def parse_statement(
    file_bytes: bytes,
    filename: str,
    password: str | None = None
) -> pd.DataFrame:
    """
    Main entry point.
    Detects file type from filename extension and returns a raw DataFrame.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        filename:   Original filename (used to detect extension).
        password:   PDF password (National ID number). Ignored for Excel/CSV.

    Returns:
        pd.DataFrame with raw transaction rows.
    """
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        return _parse_pdf(file_bytes, password)
    elif ext in ("xlsx", "xls"):
        return _parse_excel(file_bytes)
    elif ext == "csv":
        return _parse_csv(file_bytes)
    else:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '.{ext}'. "
                   "Please upload a PDF, Excel (.xlsx), or CSV file."
        )