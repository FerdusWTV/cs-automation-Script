# ConnectStudio E2E Suite — Commands

All commands are for **Windows PowerShell** and assume the repo root is
`C:\Users\User\selenium_project`. The pytest commands must be run from
`PyTestBasics/` (that's where `conftest.py`, which defines `--env`, lives).

---

## 1. Virtual environment

```powershell
# Activate the venv (run from repo root)
.\venv\Scripts\Activate.ps1

# From inside PyTestBasics/ the path is one level up
..\venv\Scripts\Activate.ps1

# Deactivate when done
deactivate

# (First-time setup only) install dependencies into the venv
.\venv\Scripts\python -m pip install -r requirements.txt
```

> If you activate the venv first, you can just call `pytest` / `python` directly.
> If you **don't** activate it, prefix every call with `..\venv\Scripts\` (as shown below)
> so the venv's interpreter and packages are used instead of any global install.

---

## 2. Commands

```powershell
# Move into the test folder first (required for --env to be recognized)
cd PyTestBasics
```

```powershell
# Run the full suite against PROD
..\venv\Scripts\pytest -v --env=prod --html=report.html --self-contained-html
```

```powershell
# Run the full suite against DEV (default env)
..\venv\Scripts\pytest -v --env=dev --html=report.html --self-contained-html
```

```powershell
# Create only ONE webcast type instead of all five (PROD example)
..\venv\Scripts\pytest -v --env=prod --webcast-type=VxS --html=report.html --self-contained-html
```

```powershell
# Run just the cleanup test by name
..\venv\Scripts\pytest -v --env=prod -k "cleanup"
```

```powershell
# Stop at the first failure, and show live print/debug output
..\venv\Scripts\pytest -v --env=prod -x -s
```

```powershell
# Standalone cleanup (delete leftover "Automated Webcast *" data, no test run)
..\venv\Scripts\python cleanup_webcasts.py
```

---

## 3. Definitions

### Command parts
| Part | Definition |
|------|------------|
| `.\venv\Scripts\Activate.ps1` | Activates the project virtualenv in the current PowerShell session, so `python`/`pytest` resolve to the venv's copies. |
| `..\venv\Scripts\pytest` | Runs `pytest` from the venv (one level up in `venv\`) without needing to activate it first — guarantees the correct interpreter and installed deps. |
| `-v` | **Verbose** — prints each test name with its PASS/FAIL, instead of just dots. |
| `--env=prod` \| `--env=dev` | **Custom option** (defined in `conftest.py`). Selects which credentials/URLs load from `.env`: `*_PROD` keys for prod, plain keys for dev. Default is `dev`. |
| `--webcast-type=<TYPE>` | **Custom option**. Restricts the run to a single webcast type instead of all five. |
| `--html=report.html` | Writes a **pytest-html** report to `report.html` in the current folder. |
| `--self-contained-html` | Inlines all CSS/JS/images into that one HTML file so it can be shared/opened anywhere. |
| `-k "expr"` | Runs only tests whose name matches the expression (e.g. `-k "cleanup"`). |
| `-s` | Disables output capture — shows `print()`/debug output live in the console. |
| `-x` | Stops at the **first** failure instead of running the whole suite. |
| `--maxfail=N` | Stops after N failures. |
| `deactivate` | Exits the activated venv. |

### `--webcast-type` values
| Value | Meaning | Underlying webcast type |
|-------|---------|-------------------------|
| `VxS` | Video & slides | `Video & slides (default)` |
| `AxS` | Audio & slides | `Audio & slides` |
| `V`   | Video only     | `Video only` |
| `A`   | Audio only     | `Audio only` |
| `AxE` | Audio-only edge-case webcast | `Audio only` |

### Prerequisites
- **`.env`** in `PyTestBasics/` with prod keys: `URL_PROD`, `EMAIL_PROD`, `PASSWORD_PROD`,
  `TARGET_PORTAL`, and asset paths `SLIDE_PATH`, `VIDEO_PATH`, `HEADSHOT_PATH`, `AUDIO_PATH`.
  (Org overrides `*_ORG_PROD` fall back to the plain prod values if unset.)
- **Virtualenv** at `..\venv\` with `selenium`, `pytest`, `pytest-html`, `python-dotenv`.
- **Chrome + matching chromedriver**; the suite runs headless (`--headless=new`, 1920×1080).

### What a run does
- **`test_00_cleanup` runs first** — deletes leftover `Automated Webcast *` entries on the
  target env (its own short-lived headless browser) so the run starts clean.
- Then logs in, opens the target portal, and creates the webcast(s).
- Results are written to **`report.html`** (self-contained, shareable).

> ⚠️ `--env=prod` hits **real production** (`connectstudio-admin.world-television.com`)
> with real logins and creates real webcasts. Only run it when you intend to exercise prod.
