import os
import sys

import pytest
import selenium
from dotenv import load_dotenv

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
            "Create only a single webcast of this type instead of all five. "
            f"One of: {', '.join(WEBCAST_TYPES)}. Omit to create the full set."
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
    }

    for key, (env_name, default) in DEFAULT_TYPE_LABELS.items():
        config[key] = os.getenv(env_name, default)

    return config


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
