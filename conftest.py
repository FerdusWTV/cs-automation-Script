import selenium
import pytest
import os
from dotenv import load_dotenv

# -----------------------------
# addoption for changing env in the terminal
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
        choices=["VxS", "AxS", "V", "A", "AxE"],
        help=(
            "Create only a single webcast of this type instead of all five. "
            "One of: VxS, AxS, V, A, AxE. Omit to create the full set."
        ),
    )


# ----------------------- ENV ------------------------
@pytest.fixture(scope="session")
def config(request):
    load_dotenv()
    selected_env = request.config.getoption("--env")
    # Audio / Audio & slides webcasts take several headshots. HEADSHOT_PATHS is a
    # comma-separated list; it falls back to the single HEADSHOT_PATH.
    headshot_paths = [
        p.strip() for p in (os.getenv("HEADSHOT_PATHS") or os.getenv("HEADSHOT_PATH") or "").split(",")
        if p.strip()
    ]
    single_webcast_type = request.config.getoption("--webcast-type")

    if selected_env == "prod":
        return {
            "url": os.getenv("URL_PROD"),
            "email": os.getenv("EMAIL_PROD"),
            "password": os.getenv("PASSWORD_PROD"),
            "url_org": os.getenv("URL_ORG_PROD") or os.getenv("URL_PROD"),
            "email_org": os.getenv("EMAIL_ORG_PROD") or os.getenv("EMAIL_PROD"),
            "password_org": os.getenv("PASSWORD_ORG_PROD") or os.getenv("PASSWORD_PROD"),
            "target_portal": os.getenv("TARGET_PORTAL_PROD") or os.getenv("TARGET_PORTAL"),
            "new_webcast_title": os.getenv("NEW_WEBCAST_TITLE"),
            "webcast_title": os.getenv("WEBCAST_TITLE"),
            "web": os.getenv("WEB", ""),
            "slide_path": os.getenv("SLIDE_PATH"),
            "video_path": os.getenv("VIDEO_PATH"),
            "headshot_path": os.getenv("HEADSHOT_PATH"),
            "headshot_paths": headshot_paths,
            "audio_path": os.getenv("AUDIO_PATH"),
            "webcast_titles": [
                os.getenv("NEW_WEBCAST_TITLE_1", "Automated Webcast VxS - 001"),
                os.getenv("NEW_WEBCAST_TITLE_2", "Automated Webcast AxS - 002"),
                os.getenv("NEW_WEBCAST_TITLE_3", "Automated Webcast V - 003"),
                os.getenv("NEW_WEBCAST_TITLE_4", "Automated Webcast A - 004"),
                os.getenv("NEW_WEBCAST_TITLE_5", "Automated Webcast AxE - 005"),
            ],
            "webcast_type_1": os.getenv("WEBCAST_TYPE_VxS", "Video & slides (default)"),
            "webcast_type_2": os.getenv("WEBCAST_TYPE_AxS", "Audio & slides"),
            "webcast_type_3": os.getenv("WEBCAST_TYPE_V", "Video only"),
            "webcast_type_4": os.getenv("WEBCAST_TYPE_A", "Audio only"),
            "webcast_type_5": os.getenv("WEBCAST_TYPE_AxE", "Audio only"),
            "single_webcast_type": single_webcast_type,
        }

    return {
        "url": os.getenv("URL"),
        "email": os.getenv("EMAIL"),
        "password": os.getenv("PASSWORD"),
        "url_org": os.getenv("URL_ORG") or os.getenv("URL"),
        "email_org": os.getenv("EMAIL_ORG") or os.getenv("EMAIL"),
        "password_org": os.getenv("PASSWORD_ORG") or os.getenv("PASSWORD"),
        "target_portal": os.getenv("TARGET_PORTAL"),
        "new_webcast_title": os.getenv("NEW_WEBCAST_TITLE"),
        "webcast_title": os.getenv("WEBCAST_TITLE"),
        "web": os.getenv("WEB", ""),
        "slide_path": os.getenv("SLIDE_PATH"),
        "video_path": os.getenv("VIDEO_PATH"),
        "headshot_path": os.getenv("HEADSHOT_PATH"),
        "headshot_paths": headshot_paths,
        "audio_path": os.getenv("AUDIO_PATH"),
        "webcast_titles": [
            os.getenv("NEW_WEBCAST_TITLE_1", "Automated Webcast VxS - 001"),
            os.getenv("NEW_WEBCAST_TITLE_2", "Automated Webcast AxS - 002"),
            os.getenv("NEW_WEBCAST_TITLE_3", "Automated Webcast V - 003"),
            os.getenv("NEW_WEBCAST_TITLE_4", "Automated Webcast A - 004"),
            os.getenv("NEW_WEBCAST_TITLE_5", "Automated Webcast AxE - 005"),
        ],
        "webcast_type_1": os.getenv("WEBCAST_TYPE_VxS", "Video & slides (default)"),
        "webcast_type_2": os.getenv("WEBCAST_TYPE_AxS", "Audio & slides"),
        "webcast_type_3": os.getenv("WEBCAST_TYPE_V", "Video only"),
        "webcast_type_4": os.getenv("WEBCAST_TYPE_A", "Audio only"),
        "webcast_type_5": os.getenv("WEBCAST_TYPE_AxE", "Audio only"),
        "single_webcast_type": single_webcast_type,
    }


# -----------------------------
# Show Selenium version in console
# -----------------------------
def pytest_report_header(config):
    return f"Selenium Version: {selenium.__version__}"


# -----------------------------
# Add Selenium version to HTML report Environment
# -----------------------------
def pytest_configure(config):
    if hasattr(config, "_metadata") and config._metadata is not None:
        config._metadata["Selenium Version"] = selenium.__version__


# -----------------------------
# Add Selenium version to HTML report summary
# -----------------------------
# `optionalhook=True` lets these register even when pytest-html isn't installed;
# without it pluggy raises PluginValidationError ("unknown hook") at collection.
@pytest.hookimpl(optionalhook=True)
def pytest_html_results_summary(prefix, summary, postfix):
    prefix.extend([f"Selenium Version: {selenium.__version__}"])

# -----------------------------
# Optional: Customize HTML report title
# -----------------------------
@pytest.hookimpl(optionalhook=True)
def pytest_html_report_title(report):
    report.title = "Automation Test Report"
