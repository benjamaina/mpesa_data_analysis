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
import logging
import pandas as pd
from fastapi import HTTPException

logger = logging.getLogger(__name__)


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
    headers  = None

    try:
        with pdfplumber.open(io.BytesIO(file_bytes), password=password or "") as pdf:
            if len(pdf.pages) == 0:
                raise HTTPException(status_code=422, detail="PDF has no pages.")

            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    tables = page.extract_tables()
                except Exception as e:
                    logger.warning(f"Could not extract table from page {page_num}: {e}")
                    continue

                for table in tables:
                    if not table:
                        continue
                    if headers is None:
                        for i, row in enumerate(table):
                            row_text = " ".join(str(c) for c in row if c).lower()
                            if "receipt" in row_text or "completion time" in row_text:
                                headers = [
                                    str(c).strip() if c else f"col_{j}"
                                    for j, c in enumerate(row)
                                ]
                                all_rows.extend(table[i + 1:])
                                break
                        else:
                            all_rows.extend(table)
                    else:
                        all_rows.extend(table)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to open PDF: {e}")
        # Give a user-friendly message — don't expose internal error
        raise HTTPException(
            status_code=422,
            detail="Could not open the PDF. If it is password-protected, "
                   "make sure you entered your correct National ID number."
        )

    if not all_rows:
        raise HTTPException(
            status_code=422,
            detail="No transaction table found in the PDF. "
                   "Make sure this is a valid M-Pesa statement."
        )

    if headers is None:
        headers = [
            "Receipt No", "Completion Time", "Details",
            "Transaction Status", "Paid In", "Withdrawn", "Balance"
        ]

    try:
        n       = len(headers)
        trimmed = [row[:n] for row in all_rows if any(c for c in row)]
        df      = pd.DataFrame(trimmed, columns=headers)
    except Exception as e:
        logger.error(f"Failed to build DataFrame from PDF rows: {e}")
        raise HTTPException(
            status_code=422,
            detail="PDF was opened but the transaction table could not be read. "
                   "The statement format may not be supported."
        )

    return df


def _parse_excel(file_bytes: bytes) -> pd.DataFrame:
    """Read an Excel M-Pesa statement into a DataFrame."""
    try:
        for skip in range(7):
            try:
                df   = pd.read_excel(io.BytesIO(file_bytes), skiprows=skip)
                cols = " ".join(df.columns.astype(str)).lower()
                if "receipt" in cols or "completion" in cols or "paid in" in cols:
                    return df
            except Exception:
                continue
        # Last attempt with no skip — let it raise naturally if it fails
        return pd.read_excel(io.BytesIO(file_bytes))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read Excel file: {e}")
        raise HTTPException(
            status_code=422,
            detail="Could not read the Excel file. "
                   "Make sure it is a valid .xlsx file and not corrupted."
        )


def _parse_csv(file_bytes: bytes) -> pd.DataFrame:
    """Read a CSV M-Pesa statement into a DataFrame."""
    try:
        for skip in range(7):
            try:
                df   = pd.read_csv(io.BytesIO(file_bytes), skiprows=skip)
                cols = " ".join(df.columns.astype(str)).lower()
                if "receipt" in cols or "completion" in cols or "paid in" in cols:
                    return df
            except Exception:
                continue
        return pd.read_csv(io.BytesIO(file_bytes))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read CSV file: {e}")
        raise HTTPException(
            status_code=422,
            detail="Could not read the CSV file. "
                   "Make sure it is a valid .csv file and not corrupted."
        )


def parse_statement(
    file_bytes: bytes,
    filename:   str,
    password:   str | None = None,
) -> pd.DataFrame:
    """
    Main entry point.
    Detects file type from filename extension and returns a raw DataFrame.
    """
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty.")

    if "." not in filename:
        raise HTTPException(
            status_code=415,
            detail="File has no extension. Please upload a PDF, .xlsx, or .csv file."
        )

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