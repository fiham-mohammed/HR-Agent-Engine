# ZeloraTech HR Automation Multi-Agent Engine

A multi-agent task routing and memory engine for HR automation. A central **Orchestrator Agent** (powered by **Langgraph**) routes natural language requests to specialised sub-agents — **Scheduling**, **Leave**, **Compliance**, and **Clarification**.

Implements a **Two-Tier Memory System** (Short-Term session history + Long-Term fact consolidation) and a tamper-proof **Append-Only SQLite Audit Trail** enforced at the database trigger level.

---

## Quick Start on Windows

Double-click:

```text
start_server.bat
```

This creates/reuses `.venv`, installs required modules, and starts the server.

Alternative one-command setup:

```bash
python setup.py
```

This will:
1. Create a Python virtual environment (`.venv/`)
2. Install all dependencies from `requirements.txt`
3. Copy `.env.example` → `.env` (if not already present)
4. Initialise the SQLite database schema and triggers
5. Run the full test suite to verify the setup

Then start the server:

```bash
python run.py
```

`run.py` also has a safety auto-installer. If an important module such as `uvicorn` is missing, it installs packages from `requirements.txt` using the same Python interpreter before starting the server.

Open **http://127.0.0.1:8000/docs** for interactive Swagger UI.

---

## Manual Setup

### Prerequisites
- Python 3.11 or higher

### Steps

```bash
# 1. Create and activate virtual environment
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env if you want to use a real LLM (openai or gemini)

# 4. Run tests
pytest test_main.py -v

# 5. Start server
python run.py
```

---

## Directory Structure

```
hr_agent_engine/
├── .env                  # Active environment config (gitignore this)
├── .env.example          # Template — copy to .env
├── requirements.txt      # Python dependencies
├── README.md             # This file
├── setup.py              # Auto-install and validation script
├── run.py                # Server launcher
├── main.py               # FastAPI application and all 5 endpoints
├── test_main.py          # Pytest suite (11 tests)
├── database/
│   ├── __init__.py       # Auto-calls init_db() on import
│   ├── db.py             # SQLite connection factory + schema init
│   ├── memory_store.py   # STM/LTM queries and LTM consolidation
│   └── audit_logger.py   # Append-only audit log helpers
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py   # Langgraph StateGraph workflow
│   ├── router.py         # Intent classifier wrapper
│   ├── scheduling.py     # Scheduling sub-agent stub
│   ├── leave.py          # Leave sub-agent stub
│   ├── compliance.py     # Compliance sub-agent stub
│   └── clarification.py  # Clarification fallback agent
├── schemas/
│   └── models.py         # Pydantic request/response models
└── utils/
    ├── llm.py            # Unified LLM provider (OpenAI / Gemini / mock)
    └── logger.py         # Global logging helper
```

---

## REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/request` | Route a natural language HR request through the pipeline |
| `GET` | `/api/v1/audit` | Retrieve append-only audit log entries |
| `GET` | `/api/v1/memory` | Retrieve user memories (filter by type) |
| `POST` | `/api/v1/memory` | Manually insert a memory record |
| `GET` | `/` | Friendly homepage / status message |
| `GET` | `/api/v1/health` | Server + database health check |

### Example: POST /api/v1/request

```json
{
  "user_id": "usr_001",
  "session_id": "sess_abc",
  "text": "Please schedule a meeting with Alice tomorrow at 10am."
}
```

Response:

```json
{
  "request_id": "req_a1b2c3d4",
  "intent": "Scheduling",
  "confidence": 0.86,
  "response": "Scheduling Agent: I have processed your request ...",
  "execution_time_ms": 12.4,
  "status": "SUCCESS"
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `8000` | Server port |
| `DATABASE_URL` | `sqlite:///hr_automation.db` | SQLite DB path (relative = next to run.py) |
| `LLM_PROVIDER` | `mock` | `mock`, `openai`, or `gemini` |
| `OPENAI_API_KEY` | _(empty)_ | Required when `LLM_PROVIDER=openai` |
| `GEMINI_API_KEY` | _(empty)_ | Required when `LLM_PROVIDER=gemini` |
| `LTM_SIGNIFICANCE_THRESHOLD` | `7` | Min score (1–10) to promote a fact to LTM |

---

## Architecture

### Langgraph Pipeline

```
START
  └─► retrieve_memory   (fetch STM + LTM, build context string)
        └─► router       (classify intent + confidence score)
              ├─► scheduling   (confidence ≥ 0.70, intent = Scheduling)
              ├─► leave        (confidence ≥ 0.70, intent = Leave)
              ├─► compliance   (confidence ≥ 0.70, intent = Compliance)
              └─► clarification (confidence < 0.70 or unknown intent)
                    └─► save_memory   (STM write + optional LTM promotion)
                          └─► write_audit   (append-only audit entry)
                                └─► END
```

### Two-Tier Memory

- **STM** — last 5 interactions in the current session, always written, injected into agent prompts.
- **LTM** — significant facts extracted by the LLM significance scorer (score ≥ 7/10). Stored permanently per user across sessions.

### Append-Only Audit Log

Two SQLite `BEFORE UPDATE` and `BEFORE DELETE` triggers raise `FAIL` on any modification attempt, enforcing immutability at the database level.

---

## Bug Fixes Applied

1. **Hardcoded Windows absolute path** (`C:/Users/ASUS/...`) in `db.py` and `test_main.py` replaced with a portable relative `sqlite:///hr_automation.db` path.
2. **`os.makedirs('')` crash** — when `DATABASE_URL` resolves to a file in the current directory, `os.path.dirname()` returns `''`. Added a guard: `if parent_dir: os.makedirs(parent_dir, exist_ok=True)`.
3. **Retry loop slept on final attempt** — `time.sleep(delay)` was called even when `attempt == max_retries - 1`, adding unnecessary latency before re-raising. Fixed by checking `attempt < max_retries - 1` before sleeping.
4. **Redundant significance threshold check** — `save_memory_node` previously checked `sig_score >= 7` before calling `consolidate_to_ltm()`, which already enforces the threshold internally. Removed the duplicate check.
5. **STM ordering** — `get_short_term_memories` used `ORDER BY DESC` + Python list reverse. Replaced with a SQL subquery that restores chronological order directly.
