M-Pesa Statement Analyzer
Overview
A FastAPI backend that parses, cleans, categorizes, and visualizes M-Pesa statements. Supports PDF (password-protected), Excel (.xlsx), and CSV formats.

Project Structure
benjamaina-mpesa_data_analysis/
├── requirements.txt
├── dummy_statement.csv
├── dummy_statement.xlsx
└── app/
    ├── __init__.py
    ├── main.py              # FastAPI app, all endpoints
    ├── session_store.py     # In-memory session management
    └── services/
        ├── __init__.py
        ├── parser.py        # Reads PDF / Excel / CSV → raw DataFrame
        ├── cleaner.py       # Normalizes columns, types, dates
        ├── categorizer.py   # Labels each transaction by category
        ├── analyzer.py      # Computes summary statistics
        └── visualizer.py    # Generates PNG charts
    └── test/
        ├── __init__.py
        └── dummydata.py     # Fake statement generator

Requirements

Python 3.12+
pip packages listed in requirements.txt

Additional package needed for PDF support (not in requirements.txt yet):
pdfplumber==0.11.4

Setup
bash# 1. Clone the repo
git clone https://github.com/benjamaina/mpesa-data-analysis.git
cd mpesa-data-analysis

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
pip install pdfplumber           # for PDF support

# 4. Run the server
uvicorn app.main:app --reload
Server starts at http://localhost:8000
Interactive API docs at http://localhost:8000/docs

Generating Test Data
If you don't have a real M-Pesa statement, generate fake data:
bashpython app/test/dummydata.py
```

This creates `dummy_statement.csv` and `dummy_statement.xlsx` in the project root with 250 realistic transactions spanning July 2024 – March 2025.

---

## API Endpoints

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check, shows active session count |

### Statement
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Upload statement, returns `session_id` |
| GET | `/transactions` | Paginated transactions using `session_id` |
| DELETE | `/session/{session_id}` | Clear a session manually |

### Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/analyze` | Full stats — overview, monthly, top transactions, spending breakdown |

### Charts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/charts` | List available chart names |
| POST | `/charts/{chart_name}` | Returns a PNG image directly |

---

## How to Use

### Step 1 — Upload your statement
```
POST /upload
  file:     your_statement.csv  (or .xlsx or .pdf)
  password: your_national_id    (PDF only, leave blank for CSV/Excel)
Response:
json{
  "status": "success",
  "session_id": "9ac47793-0447-4617-888e-07173d33a926",
  "total_transactions": 250,
  "filename": "dummy_statement.csv",
  "category_summary": { ... }
}
```

### Step 2 — Browse transactions (paginated)
```
GET /transactions?session_id=9ac47793-0447-4617-888e-07173d33a926&page=1&page_size=50
```
Optional filters:
```
&category=Airtime
&category=Pay Bill
&tx_type=DEBIT
&tx_type=CREDIT
```
Response includes `total_pages`, `has_next`, `has_prev` for navigation.

### Step 3 — Get full analysis
```
POST /analyze
  file: your_statement.csv
```

### Step 4 — Get a chart
```
POST /charts/monthly_flow
POST /charts/spending_category
POST /charts/balance_trend
POST /charts/spending_day
  file: your_statement.csv
```
Returns a PNG image directly — open in browser or save to disk.

### Step 5 — Clean up
```
DELETE /session/9ac47793-0447-4617-888e-07173d33a926
Sessions auto-expire after 30 minutes if not deleted manually.

Transaction Categories
The categorizer assigns one of these labels to every transaction based on the Details text:
CategoryExamplesAirtimeBuy Airtime for 0712345678Fuliza / LoansFuliza M-PESA Loan Disbursement, RepaymentPay BillKPLC, NHIF, KRA, Zuku, DSTV, Nairobi WaterBuy Goods (Till)Buy Goods QUICKMART TILL 345678Withdraw (Agent)Withdraw Cash from Agent John GitongaDeposit (Agent)Deposit from Agent Purity NjorogeBank TransferReceived from EQUITY BANK TransferSend MoneySent to John Kamau 0712345678Receive MoneyReceived from Grace Akinyi 0740439777OtherAnything that doesn't match the above
To add a new category, edit CATEGORY_RULES in app/services/categorizer.py.

Notes
Session storage is in-memory only. Sessions do not survive a server restart. If you run multiple uvicorn workers (--workers 4), sessions will not be shared across workers. For production use, replace session_store.py with a Redis backend.
PDF parsing uses pdfplumber which works well for text-based Safaricom PDFs. If your PDF is scanned (image-based), extraction will fail — OCR support would need to be added separately.
Scaling — this app is currently single-worker. For high traffic, the natural upgrade path is: Redis for sessions → Celery for async chart generation → object storage for caching charts.

Known Limitations

Sessions lost on server restart
PDF OCR not supported
Charts re-generated on every request (not cached)
No authentication — anyone with the session_id can access that session's data


License
MIT