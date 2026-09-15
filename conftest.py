import os
import sys

import pytest
import selenium
from dotenv import load_dotenv

# The five types session_test.py builds one webcast of each. These belong to the
# NON-EMBEDDED suite only: an embedded session is always 'Video only' (the app
# filters the type list down to a single option), so 03_embedded_test.py builds
# exactly one session and never sets a type.
WEBCAST_TYPES = ["VxS", "AxS", "V", "A", "AxE"]


# -----------------------------
# Command-line options
# -----------------------------
def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default="dev",
        help="Environment to run tests against: dev or prod",
    )
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help=(
            "Override the admin URL the tests hit (e.g. http://localhost:3000 for a "
            "locally-running app). Omit to use the URL for --env."
        ),
    )
    parser.addoption(
        "--webcast-type",
        action="store",
        default=None,
        choices=WEBCAST_TYPES,
        help=(
            "session_test.py only. Create a single webcast of this type instead "
            f"of all five. One of: {', '.join(WEBCAST_TYPES)}. Omit to create the "
            "full set. Has no effect on 03_embedded_test.py, where a session is "
            "always 'Video only'."
        ),
    )
    parser.addoption(
        "--embed-org",
        action="store",
        default=None,
        help=(
            "Organization the embedded-session suite works in. Omit to use "
            "whichever organization the Organizations list shows first."
        ),
    )
    parser.addoption(
        "--embed-client",
        action="store",
        default=None,
        help=(
            "Name of the embedded client to use. Reused when it already exists, "
            "created otherwise. Default: 'Automation Embedded Client'."
        ),
    )
    parser.addoption(
        "--embed-portal-id",
        action="store",
        default=None,
        help=(
            "Portal whose sessions the embedded-session suite embeds. Omit to "
            "discover it by opening TARGET_PORTAL the normal way."
        ),
    )
    parser.addoption(
        "--testrail-out",
        action="store",
        default=None,
        help=(
            "Write a {case_id: status} JSON of this run's results to this path, "
            "for uploading to TestRail. Only tests carrying a @pytest.mark.testrail "
            "marker are included."
        ),
    )


# ----------------------- ENV ------------------------

# Default webcast titles, one per type. NEW_WEBCAST_TITLE_1..5 override them.
DEFAULT_TITLES = [
    "Automated Webcast VxS - 001",
    "Automated Webcast AxS - 002",
    "Automated Webcast V - 003",
    "Automated Webcast A - 004",
    "Automated Webcast AxE - 005",
]

# The exact labels shown in the 'Webcast details' type dropdown. There is no
# separate AxE option in the app — the AxE webcast uses 'Audio only' too.
DEFAULT_TYPE_LABELS = {
    "webcast_type_1": ("WEBCAST_TYPE_VxS", "Video & slides (default)"),
    "webcast_type_2": ("WEBCAST_TYPE_AxS", "Audio & slides"),
    "webcast_type_3": ("WEBCAST_TYPE_V", "Video only"),
    "webcast_type_4": ("WEBCAST_TYPE_A", "Audio only"),
    "webcast_type_5": ("WEBCAST_TYPE_AxE", "Audio only"),
}


@pytest.fixture(scope="session")
def config(request):
    """Test configuration for the selected --env.

    dev and prod read the same settings from differently-suffixed env vars:
    prod uses the `_PROD` suffix (URL_PROD, EMAIL_PROD, ...), dev uses the bare
    names. The org-level credentials fall back to the plain ones when unset.
    """
    load_dotenv()
    suffix = "_PROD" if request.config.getoption("--env") == "prod" else ""

    def env(name):
        """Read NAME for the selected environment (NAME_PROD on prod, NAME on dev).

        Deliberately does NOT fall back to the other environment's variable — a
        missing URL_PROD must fail loudly, not quietly point a prod run at dev.
        """
        return os.getenv(f"{name}{suffix}")

    # Audio / Audio & slides webcasts take several headshots. HEADSHOT_PATHS is
    # a comma-separated list; it falls back to the single HEADSHOT_PATH.
    headshot_paths = [
        p.strip()
        for p in (os.getenv("HEADSHOT_PATHS") or os.getenv("HEADSHOT_PATH") or "").split(",")
        if p.strip()
    ]

    config = {
        # Credentials / target
        "url": env("URL"),
        "email": env("EMAIL"),
        "password": env("PASSWORD"),
        "url_org": env("URL_ORG") or env("URL"),
        "email_org": env("EMAIL_ORG") or env("EMAIL"),
        "password_org": env("PASSWORD_ORG") or env("PASSWORD"),
        # The one setting that DOES fall back across environments: prod reuses
        # the dev portal name when TARGET_PORTAL_PROD isn't set.
        "target_portal": env("TARGET_PORTAL") or os.getenv("TARGET_PORTAL"),
        "web": os.getenv("WEB", ""),

        # Local media used by the content uploads
        "slide_path": os.getenv("SLIDE_PATH"),
        "video_path": os.getenv("VIDEO_PATH"),
        "headshot_path": os.getenv("HEADSHOT_PATH"),
        "headshot_paths": headshot_paths,
        "audio_path": os.getenv("AUDIO_PATH"),

        # Webcasts to build
        "new_webcast_title": os.getenv("NEW_WEBCAST_TITLE"),
        "webcast_title": os.getenv("WEBCAST_TITLE"),
        "webcast_titles": [
            os.getenv(f"NEW_WEBCAST_TITLE_{i}", default)
            for i, default in enumerate(DEFAULT_TITLES, start=1)
        ],
        "single_webcast_type": request.config.getoption("--webcast-type"),

        # Embedded sessions (03_embedded_test.py). `embed_org` is optional —
        # left unset, the suite opens whichever organization comes first.
        # Note there is no type setting here: embedded is always 'Video only'.
        "embed_org": request.config.getoption("--embed-org") or os.getenv("EMBED_ORG"),
        "embed_client": (
            request.config.getoption("--embed-client")
            or os.getenv("EMBED_CLIENT")
            or "Automated Embedded"
        ),
        "plain_client": os.getenv("EMBED_PLAIN_CLIENT") or "Automated Plain",
        "embed_portal_id": (
            request.config.getoption("--embed-portal-id") or os.getenv("EMBED_PORTAL_ID")
        ),
    }

    for key, (env_name, default) in DEFAULT_TYPE_LABELS.items():
        config[key] = os.getenv(env_name, default)

    return config


# -----------------------------
# TestRail result capture
# -----------------------------
# A test states which TestRail case it covers with `@pytest.mark.testrail(588)`.
# With --testrail-out, the run's outcomes are collected into a JSON file that
# the upload script turns into add_results_for_cases calls. Tests without the
# marker are ignored entirely, so the file never invents coverage.

# TestRail status ids.
TESTRAIL_PASSED = 1
TESTRAIL_BLOCKED = 2
TESTRAIL_FAILED = 5

_testrail_results = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Record each marked test's outcome against its TestRail case id.

    Only the `call` phase is recorded for passes, but a setup error still has to
    count as a failure — a test whose fixtures blew up did not verify anything.
    A skip becomes 'blocked': the case was not executed, which is what TestRail's
    blocked status means, and is honest about coverage in a way 'passed' is not.
    """
    outcome = yield
    report = outcome.get_result()

    marker = item.get_closest_marker("testrail")
    if marker is None or not marker.args:
        return

    if report.failed:
        status = TESTRAIL_FAILED
    elif report.skipped:
        status = TESTRAIL_BLOCKED
    elif report.when == "call" and report.passed:
        status = TESTRAIL_PASSED
    else:
        return  # a passing setup/teardown phase says nothing on its own

    for case_id in marker.args:
        # Never let a later phase downgrade a recorded failure to a pass.
        if _testrail_results.get(case_id) in (TESTRAIL_FAILED,):
            continue
        _testrail_results[case_id] = status


def pytest_sessionfinish(session, exitstatus):
    """Write the collected case results when --testrail-out was given."""
    import json

    path = session.config.getoption("--testrail-out")
    if not path or not _testrail_results:
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            [{"case_id": cid, "status_id": sid} for cid, sid in sorted(_testrail_results.items())],
            f,
            indent=2,
        )
    print(f"\nTestRail results for {len(_testrail_results)} cases written to {path}")


# -----------------------------
# Report decoration
# -----------------------------
def pytest_report_header(config):
    """Show the Selenium version in the console header."""
    return f"Selenium Version: {selenium.__version__}"


def pytest_configure(config):
    """Add the Selenium version to the HTML report's Environment table.

    Also force UTF-8 on the console streams. The flows print emoji status
    markers; under `-s` those go straight to a cp1252 Windows console and every
    test dies with UnicodeEncodeError before its assertions are ever reached.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass  # not a reconfigurable text stream (e.g. pytest's capture buffer)

    config.addinivalue_line(
        "markers",
        "testrail(*case_ids): TestRail case(s) in project 2 / suite 7 this test covers.",
    )

    if hasattr(config, "_metadata") and config._metadata is not None:
        config._metadata["Selenium Version"] = selenium.__version__


# `optionalhook=True` lets these register even when pytest-html isn't installed;
# without it pluggy raises PluginValidationError ("unknown hook") at collection.
@pytest.hookimpl(optionalhook=True)
def pytest_html_results_summary(prefix, summary, postfix):
    prefix.extend([f"Selenium Version: {selenium.__version__}"])


@pytest.hookimpl(optionalhook=True)
def pytest_html_report_title(report):
    report.title = "Automation Test Report"
