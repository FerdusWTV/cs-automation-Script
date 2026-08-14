# ConnectStudio E2E Automation Suite

Selenium + pytest end-to-end tests for the **ConnectStudio admin** app.

Two independent suites live here:

| File | What it does |
|------|--------------|
| `session_test.py` | **Webcast suite** — logs in, opens a portal, then creates/activates/configures webcasts (all 5 types, or one). |
| `portal_test.py` | **Portal CRUD suite** — create → read → clone → delete a portal, verifying it never touches pre-existing portals. |
| `cleanup_webcasts.py` | Standalone script — deletes leftover `Automated Webcast *` entries. Not a test. |

> ⚠️ These tests drive a **real** application with **real** logins and create **real** data.
> `--env=prod` hits production. Read [Safety](#10-safety-notes) before your first prod run.

---

## Table of contents

1. [How the webcast suite works](#1-how-the-webcast-suite-works)
2. [Prerequisites](#2-prerequisites)
3. [First-time setup](#3-first-time-setup)
4. [Configuring `.env`](#4-configuring-env)
5. [Running the tests](#5-running-the-tests)
6. [Command-line options](#6-command-line-options)
7. [Test assets (slides, video, headshots, audio)](#7-test-assets)
8. [Reports and failure diagnostics](#8-reports-and-failure-diagnostics)
9. [Troubleshooting](#9-troubleshooting)
10. [Safety notes](#10-safety-notes)
11. [CI / Jenkins](#11-ci--jenkins)
12. [Extending the suite](#12-extending-the-suite)

---

## 1. How the webcast suite works

`session_test.py` runs four tests, in order (pytest runs them top-to-bottom, and they
share one browser via the session-scoped `driver` fixture — so **don't reorder them**):

| Test | What happens |
|------|--------------|
| `test_00_cleanup` | Opens its **own short-lived headless browser**, logs in, and deletes every webcast whose name starts with `Automated Webcast`. This makes every run start clean. It uses a separate browser so the main `driver` is still logged-out for `test_01_login`. |
| `test_01_login` | Logs into the admin URL with the org credentials and asserts the header says `Welcome`. |
| `test_02_open_target_portal` | Searches for `TARGET_PORTAL` on the dashboard and clicks **Edit** to open it. |
| `test_03_create_all_webcasts` | The main flow. For each webcast type, runs the full 5-step sequence below. |

### The per-webcast sequence

For each webcast, `test_03` does:

1. **Create** (`_navigate_and_create_webcast`) — Sessions → New webcast → title →
   date/time/duration → signal → Create.
2. **Activate + Manage** (`_activate_and_manage_webcast`) — finds the webcast by title,
   flips the Activate toggle, opens its Manage page.
3. **Set type** (`_set_webcast_type`) — picks the webcast type from the *Webcast details*
   dropdown.
4. **Upload content** (`_upload_content`) — uploads the files that type requires (see below).
5. **Configure layout** (`_configure_layout_and_go_back`) — sets preview title/description,
   flips the logo / Q&A / slider-list toggles, saves, and clicks Back.

### The five webcast types

| Key | Type label in the UI | Files uploaded (in order) |
|-----|----------------------|----------------------------|
| `VxS` | Video & slides (default) | slide (Preview), slide (Live), video (Preview) |
| `AxS` | Audio & slides | slide (Preview), **headshots** (Preview), audio (Preview), slide (Live) |
| `V`   | Video only | video (Preview) |
| `A`   | Audio only | **headshots** (Preview), audio (Preview) |
| `AxE` | Audio & slides (edge case) | slide, **headshots**, audio, slide (Live) — plus an extra layout toggle |

This mapping lives in `CONTENT_SPECS` in `session_test.py`. "Preview" / "Live" refers to the
status dropdown on the Manage page — the suite switches status when the spec calls for it.

### Multi-headshot upload

The **Audio** (`A`) and **Audio & slides** (`AxS`, `AxE`) types show a headshot dropzone
that accepts **several images**. Set `HEADSHOT_PATHS` in `.env` to a comma-separated list
and all of them are attached before Save:

```dotenv
HEADSHOT_PATHS=C:\...\headshot-1.jpg,C:\...\headshot-2.jpg,C:\...\headshot-3.jpg
```

If the input carries the HTML `multiple` attribute, all files go in one `send_keys`;
otherwise they're attached one at a time so the dropzone appends them.
If `HEADSHOT_PATHS` is unset, the suite falls back to the single `HEADSHOT_PATH`.

---

## 2. Prerequisites

- **Python 3.9+**
- **Google Chrome** (recent version)
- **chromedriver** — optional. Selenium Manager downloads a matching driver
  automatically; only set `DRIVER` in `.env` if you want to pin a specific one.
  Linux build, if you need it:
  `https://storage.googleapis.com/chrome-for-testing-public/142.0.7444.175/linux64/chromedriver-linux64.zip`
- **Access to the ConnectStudio admin app** (dev and/or prod credentials).
- **Local test asset files** — a PDF, an MP4, some JPGs, an M4A (see [§7](#7-test-assets)).

Python packages: `selenium`, `pytest`, `pytest-html`, `python-dotenv`.

---

## 3. First-time setup

All commands are **Windows PowerShell**, run from the repo root
(`C:\Users\User\selenium_project`) unless noted.

```powershell
# 1. Create a virtualenv at the repo root
python -m venv venv

# 2. Activate it
.\venv\Scripts\Activate.ps1

# 3. Install the dependencies
python -m pip install selenium pytest pytest-html python-dotenv

# 4. Move into the test folder and create your .env from the template
cd PyTestBasics
Copy-Item .env.example .env

# 5. Edit .env with real URLs, credentials, and asset paths
notepad .env
```

Then verify the setup with a quick login-only run:

```powershell
pytest -v -s --env=dev -k "login"
```

> **Activating vs. not activating the venv.** If you activate it (step 2), just call
> `pytest`. If you don't, prefix every call with `..\venv\Scripts\` from inside
> `PyTestBasics/` — e.g. `..\venv\Scripts\pytest -v --env=dev` — so the venv's
> interpreter and packages are used instead of a global install.
>
> **Always run pytest from inside `PyTestBasics/`.** That's where `conftest.py` lives,
> and it's what defines `--env`, `--webcast-type`, and `--base-url`. Running from the
> repo root gives you `unrecognized arguments: --env`.

---

## 4. Configuring `.env`

`.env` lives in `PyTestBasics/` and is **git-ignored** — never commit real credentials.
`.env.example` is the committed template; copy it and fill it in.

### Login and environment

| Variable | Used when | Purpose |
|----------|-----------|---------|
| `URL`, `EMAIL`, `PASSWORD` | `--env=dev` (default) | Dev admin login. |
| `URL_ORG`, `EMAIL_ORG`, `PASSWORD_ORG` | `--env=dev` | Org-admin account used for login + cleanup. Falls back to `URL`/`EMAIL`/`PASSWORD` if unset. |
| `URL_PROD`, `EMAIL_PROD`, `PASSWORD_PROD` | `--env=prod` | Prod admin login. |
| `URL_ORG_PROD`, `EMAIL_ORG_PROD`, `PASSWORD_ORG_PROD` | `--env=prod` | Optional prod org overrides; fall back to the `*_PROD` values. |
| `TARGET_PORTAL` | always | Name of the portal on the dashboard that holds the sessions (e.g. `General Information`). |
| `TARGET_PORTAL_PROD` | `--env=prod` | Optional prod override; falls back to `TARGET_PORTAL`. |
| `DRIVER` | optional | Explicit chromedriver path. Leave unset to let Selenium Manager resolve it. |

### Webcast titles

`NEW_WEBCAST_TITLE_1` … `_5` name the five webcasts.
**Keep the `Automated Webcast` prefix** — `test_00_cleanup` and `cleanup_webcasts.py`
only delete names starting with that prefix. Rename them and cleanup stops finding them.

### Webcast types

`WEBCAST_TYPE_VxS`, `_AxS`, `_V`, `_A`, `_AxE` must match the **exact option labels** in
the *Webcast details* type dropdown. Valid values:
`Video & slides (default)`, `Video only`, `Audio & slides`, `Audio only`.
(There's no separate "AxE" type in the app — `AxE` is a second audio webcast that also
flips an extra layout toggle.)

### Asset paths

| Variable | Format | Notes |
|----------|--------|-------|
| `SLIDE_PATH` | PDF | |
| `VIDEO_PATH` | MP4 | |
| `HEADSHOT_PATH` | JPG/PNG | Single-image fallback. |
| `HEADSHOT_PATHS` | comma-separated JPG/PNG list | Multi-headshot upload. Overrides `HEADSHOT_PATH` when set. |
| `AUDIO_PATH` | M4A | |

Use **absolute paths**. Both `C:/forward/slashes` and `C:\back\slashes` work, and paths
containing spaces are fine with no quoting. In `HEADSHOT_PATHS`, whitespace around each
comma is stripped, so spacing is up to you — but a filename containing a comma will break
the list, so rename such files.

---

## 5. Running the tests

Run all of these from `PyTestBasics/`.

```powershell
# Full webcast suite against DEV (default env)
pytest -v --env=dev --html=report.html --self-contained-html

# Full webcast suite against PROD
pytest -v --env=prod --html=report.html --self-contained-html

# Only ONE webcast type instead of all five
pytest -v --env=dev --webcast-type=AxS --html=report.html --self-contained-html

# Live console output (see the ✅ progress prints as they happen)
pytest -v -s --env=dev

# Stop at the first failure
pytest -v -s --env=dev -x

# Just the cleanup test
pytest -v --env=prod -k "cleanup"

# Portal CRUD suite
pytest -v -s portal_test.py --env=dev --html=report.html --self-contained-html

# Portal CRUD against a locally-running app
pytest -v -s portal_test.py --base-url=http://localhost:3000

# Standalone cleanup (no test run) — deletes leftover "Automated Webcast *"
python cleanup_webcasts.py
```

**Runtime expectations.** A full 5-webcast run takes a while — audio and video saves are
processed server-side and can each take well over 30 seconds (the suite allows up to 180s
per media save). Use `--webcast-type` while developing to iterate on one type.

**Watching it run.** The webcast suite runs in a **visible** browser by default. To run it
headless, uncomment `options.add_argument("--headless=new")` in `session_test.py`'s
`driver` fixture. (`test_00_cleanup` and `cleanup_webcasts.py` are always headless.)

---

## 6. Command-line options

### Custom options (defined in `conftest.py`)

| Option | Default | Meaning |
|--------|---------|---------|
| `--env=dev\|prod` | `dev` | Which credential set loads from `.env`: `*_PROD` keys for prod, plain keys for dev. |
| `--webcast-type=<KEY>` | *(all five)* | Restrict the run to one webcast: `VxS`, `AxS`, `V`, `A`, or `AxE`. |
| `--base-url=<URL>` | *(from `--env`)* | Override the admin URL — used by `portal_test.py`, e.g. a local `http://localhost:3000`. |

### Environment-variable options (`portal_test.py` only)

| Variable | Meaning |
|----------|---------|
| `HEADLESS=1` | Run the portal suite headless. Default is a visible browser. |
| `PORTAL_CLIENT`, `PORTAL_ORG` | Which client/org to create the portal under. |
| `PORTAL_LOGO_PATH` | Header-menu logo image. Must be **under 200 KB**. Falls back to `HEADSHOT_PATH`. |

### Standard pytest flags worth knowing

| Flag | Meaning |
|------|---------|
| `-v` | Verbose — prints each test name with PASS/FAIL instead of dots. |
| `-s` | Disables output capture — shows `print()` output live. **Very useful here**, since the suite narrates its progress. |
| `-x` | Stop at the first failure. |
| `--maxfail=N` | Stop after N failures. |
| `-k "expr"` | Run only tests whose name matches, e.g. `-k "cleanup"`. |
| `-rA` | Print a short summary of every test at the end. |
| `--html=report.html --self-contained-html` | Write a single shareable HTML report. |
| `--junitxml=report.xml` | Machine-readable report for CI. |

---

## 7. Test assets

The suite uploads real local files. Keep them somewhere stable (e.g. a `Test_Photos/`,
`Test_Slides/` folder) and point `.env` at them.

| Asset | Format | Guidance |
|-------|--------|----------|
| Slide | PDF | A few pages is plenty; large decks slow the upload. |
| Video | MP4 | Keep it short — the save is server-side and slow. |
| Headshot(s) | JPG / PNG | Small files. Provide 2–3 for the multi-headshot types. |
| Audio | M4A | Keep it short, same reason as video. |
| Portal logo | JPG / PNG | **Under 200 KB** — the app rejects larger files. |

These files are **not** in the repo. Each person running the suite supplies their own and
sets their own paths in their own `.env`.

---

## 8. Reports and failure diagnostics

**HTML report.** `--html=report.html --self-contained-html` writes a single self-contained
`report.html` in `PyTestBasics/` — everything inlined, so you can email it or attach it to
a ticket. The report title is set to "Automation Test Report" and includes the Selenium
version (see the `pytest_html_*` hooks in `conftest.py`).

**Automatic failure artifacts.** Every action that expects a SweetAlert confirmation popup
goes through `_wait_for_swal`. When the popup doesn't arrive in time — or arrives with
unexpected text — it writes:

- `failure_<label>.png` — a screenshot at the moment of failure
- `failure_<label>.html` — the full page source

The `<label>` names the step, so `failure_audio_save.png` means the audio Save never
confirmed. **Open these first** when a run fails — they usually show the problem
immediately (a validation error, an unexpected modal, a stuck spinner).

---

## 9. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `unrecognized arguments: --env` | You ran pytest from the repo root. `cd PyTestBasics` first. |
| `No path configured for 'headshot'` | `HEADSHOT_PATHS` / `HEADSHOT_PATH` missing or empty in `.env`. |
| Login test fails, no `Welcome` | Wrong credentials, wrong `--env`, or the app is down. Check `URL_ORG` / `URL_ORG_PROD`. |
| `No unactivated webcast '<title>' found` | A previous run left an already-activated webcast with the same title. Run `python cleanup_webcasts.py`, or `pytest -k "cleanup"`. |
| `No confirmation popup after <step>` | The action didn't complete. Open `failure_<step>.png` / `.html`. Media saves on a slow connection can genuinely exceed the timeout. |
| Webcast type doesn't stick | `WEBCAST_TYPE_*` doesn't exactly match a dropdown label. The type is an antd Select — typed text is discarded; the label must match so the option can be clicked. |
| Only the last headshot uploaded | The dropzone replaces rather than appends and lacks the `multiple` attribute. Check the input in DevTools. |
| Portal logo upload rejected | Logo is over 200 KB. |
| `SessionNotCreatedException` / driver version mismatch | Chrome updated. Clear the `DRIVER` line in `.env` so Selenium Manager fetches a matching driver. |
| Element click intercepted | A toast covered the element. The suite works around this with `execute_script` clicks — if you add a new step, do the same. |
| Suite leaves stale webcasts behind after a crash | `python cleanup_webcasts.py` (note: it's hardcoded to the **prod** credentials). |

### Known quirks this suite works around

These are deliberate, not accidents — keep them in mind when editing:

- **Activate is a toggle.** Clicking it on an already-activated webcast *deactivates* it.
  The code only clicks switches whose `aria-checked` is `false`.
- **antd Selects don't accept typed text.** The value must be picked by clicking the
  option in the opened dropdown.
- **The status dropdown needs a native click to open** but a JS click to select the
  option (a toast can intercept the native one).
- **SweetAlert popups auto-dismiss.** `_wait_for_swal` must be called *immediately* after
  the triggering click — inserting a `sleep` before it can miss the popup entirely.
- **The Content panel closes on every status switch** and must be re-opened.

---

## 10. Safety notes

- **`--env=prod` hits real production.** It logs in with real credentials and creates real
  webcasts on a real portal. Only run it when you intend to exercise prod.
- **`test_00_cleanup` deletes data.** It removes *every* webcast whose name starts with
  `Automated Webcast` on the target portal — including ones you created by hand, if you
  named them that way. Don't use that prefix for anything you want to keep.
- **`cleanup_webcasts.py` is hardcoded to the prod credentials** (`URL_PROD` /
  `EMAIL_PROD` / `PASSWORD_PROD`), regardless of any `--env` flag. It ignores `--env`
  because it's a plain script, not a pytest test.
- **Never commit `.env`.** It's git-ignored; keep it that way. Share `.env.example` instead.

---

## 11. CI / Jenkins

pytest exits with a **non-zero code** when a test fails, which is all Jenkins needs to
fail the build — no extra wiring required.

```groovy
stage('Run Selenium Tests') {
    steps {
        sh '''
        source venv/bin/activate
        pytest --maxfail=1 --disable-warnings -v \
               --html=report.html --self-contained-html \
               --junitxml=report.xml
        '''
    }
    post {
        always {
            archiveArtifacts artifacts: 'report.html,failure_*.png,failure_*.html', fingerprint: true
            junit 'report.xml'
        }
        failure {
            echo "❌ Tests failed — check report.html or the console output."
        }
    }
}
```

| Goal | How |
|------|-----|
| Fail the build on test failure | Nothing extra — pytest's exit code does it. |
| Stop at the first failure | `--maxfail=1` |
| See exactly where it failed | `-v -rA` — prints file, line, and the assertion error. |
| Save reports | `--html=report.html --self-contained-html --junitxml=report.xml` |
| Keep failure screenshots | Archive `failure_*.png` / `failure_*.html`. |

For headless CI, uncomment the `--headless=new` line in `session_test.py`'s `driver`
fixture (or set `HEADLESS=1` for `portal_test.py`).

---

## 12. Extending the suite

**Adding a new webcast type.** Add its entry to `CONTENT_SPECS` in `session_test.py` as an
ordered list of `(status, file_key)` tuples, add a `WEBCAST_TYPE_*` variable to `.env`,
add the type to the `webcasts` list in `test_03_create_all_webcasts`, and add its key to
the `--webcast-type` `choices` in `conftest.py`.

**Adding a new file type to upload.** Add entries to all four dicts near the top of the
upload section: `_FILE_INPUT` (the XPath, matched on the input's `accept` attribute),
`_FILE_PATH_KEY`, `_FILE_SETTLE` (seconds to let the dropzone read the file), and
`_FILE_SAVE_TIMEOUT` (how long Save may take server-side). Add `_FILE_PATHS_KEY` too if it
should accept multiple files.

**House style for new steps.**

- Use `driver.execute_script("arguments[0].click();", el)` rather than `el.click()` —
  toasts intercept native clicks. The exceptions are documented in the code (the antd
  status dropdown genuinely needs a native mousedown to open).
- Call `_wait_for_swal(driver, "<label>", expect="success")` immediately after any action
  that shows a confirmation popup — you get free screenshot/page-source diagnostics.
- Locate elements with `wait.until(EC.presence_of_element_located(...))`, not bare
  `find_element`.

**Related files.** `command.md` is a quick command cheat-sheet covering the same ground as
[§5](#5-running-the-tests) and [§6](#6-command-line-options).
