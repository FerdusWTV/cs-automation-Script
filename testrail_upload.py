"""Push a pytest run's results into TestRail.

Reads the JSON that `pytest --testrail-out=...` writes — a list of
`{"case_id": .., "status_id": ..}` — creates a run scoped to exactly those
cases, and posts every result in one call.

    python testrail_upload.py embedded_results.json --name "Embedded sessions — dev"

Credentials come from ~/.ccr/.env (TESTRAIL_URL, TESTRAIL_USER, TESTRAIL_API_KEY).
Project and suite default to Connect Studio / Admin Panel; pass --project-id or
--suite-id to target something else.

`--dry-run` prints what would be sent and touches nothing, which is the right
default habit before writing to a shared tracker.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_PROJECT_ID = 2  # Connect Studio
DEFAULT_SUITE_ID = 7    # Admin Panel

STATUS_NAMES = {1: "passed", 2: "blocked", 3: "untested", 4: "retest", 5: "failed"}


def load_credentials(env_path=None):
    """Read the TestRail credentials out of ~/.ccr/.env (or the environment)."""
    path = env_path or os.path.join(os.path.expanduser("~"), ".ccr", ".env")
    values = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")

    url = os.getenv("TESTRAIL_URL") or values.get("TESTRAIL_URL")
    user = os.getenv("TESTRAIL_USER") or values.get("TESTRAIL_USER")
    key = os.getenv("TESTRAIL_API_KEY") or values.get("TESTRAIL_API_KEY")
    if not (url and user and key):
        sys.exit(f"TESTRAIL_URL / TESTRAIL_USER / TESTRAIL_API_KEY not found in {path}")
    return url.rstrip("/"), user, key


def call(url, user, key, endpoint, payload=None):
    """One TestRail API v2 call. POSTs when `payload` is given, GETs otherwise."""
    request = urllib.request.Request(f"{url}/index.php?/api/v2/{endpoint}")
    token = base64.b64encode(f"{user}:{key}".encode()).decode()
    request.add_header("Authorization", f"Basic {token}")
    request.add_header("Content-Type", "application/json")
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        request.add_header("Content-Length", str(len(data)))
    try:
        with urllib.request.urlopen(request, data) as response:
            body = response.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        sys.exit(f"TestRail {endpoint} failed: {error.code} {error.read().decode()[:400]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", help="JSON written by pytest --testrail-out")
    parser.add_argument("--name", required=True, help="Name for the TestRail run")
    parser.add_argument("--project-id", type=int, default=DEFAULT_PROJECT_ID)
    parser.add_argument("--suite-id", type=int, default=DEFAULT_SUITE_ID)
    parser.add_argument("--comment", default="Automated: 03_embedded_test.py")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the run that would be created and exit without writing.",
    )
    args = parser.parse_args()

    with open(args.results, encoding="utf-8") as f:
        results = json.load(f)
    if not results:
        sys.exit(f"{args.results} holds no results.")

    case_ids = [r["case_id"] for r in results]
    tally = {}
    for r in results:
        tally[STATUS_NAMES.get(r["status_id"], r["status_id"])] = (
            tally.get(STATUS_NAMES.get(r["status_id"], r["status_id"]), 0) + 1
        )

    print(f"Run name : {args.name}")
    print(f"Project  : {args.project_id}   Suite: {args.suite_id}")
    print(f"Cases    : {len(case_ids)} -> {', '.join(str(c) for c in case_ids)}")
    print(f"Results  : {tally}")

    if args.dry_run:
        print("\n--dry-run: nothing was sent to TestRail.")
        return

    url, user, key = load_credentials()

    run = call(url, user, key, f"add_run/{args.project_id}", {
        "suite_id": args.suite_id,
        "name": args.name,
        "include_all": False,
        "case_ids": case_ids,
    })
    print(f"\nCreated run {run['id']}: {run['url']}")

    call(url, user, key, f"add_results_for_cases/{run['id']}", {
        "results": [
            {"case_id": r["case_id"], "status_id": r["status_id"], "comment": args.comment}
            for r in results
        ],
    })
    print(f"Posted {len(results)} results.")


if __name__ == "__main__":
    main()
