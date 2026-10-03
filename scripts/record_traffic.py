"""Save a read-only GitHub traffic snapshot locally; never manufacture missing metrics."""

import argparse
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="KuoFengYuan/RAGGlass", help="GitHub owner/repository")
    parser.add_argument("--note", default="", help="Local note about a post or experiment")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("Use a GitHub owner/repository, not a URL.")
    if not shutil.which("gh"):
        parser.error("Install the GitHub CLI and authenticate with gh auth login.")

    paths = {
        "repository": f"repos/{args.repo}",
        "views": f"repos/{args.repo}/traffic/views",
        "clones": f"repos/{args.repo}/traffic/clones",
        "referrers": f"repos/{args.repo}/traffic/popular/referrers",
        "paths": f"repos/{args.repo}/traffic/popular/paths",
    }

    def fetch(item):
        name, endpoint = item
        try:
            result = subprocess.run(
                ["gh", "api", endpoint], capture_output=True, text=True, timeout=30, check=True
            )
            data = json.loads(result.stdout)
            if name == "repository":
                data = {
                    key: data[key]
                    for key in ("full_name", "stargazers_count", "forks_count", "open_issues_count")
                }
            return name, data, None
        except (subprocess.SubprocessError, ValueError, KeyError) as exc:
            return name, None, type(exc).__name__

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(fetch, paths.items()))
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "repository": args.repo,
        "note": args.note,
        "traffic_window_days": 14,
        "metrics": {name: data for name, data, _ in results},
        "errors": {name: error for name, _, error in results if error},
    }
    destination = ROOT / ".data" / "traffic"
    destination.mkdir(parents=True, exist_ok=True)
    filename = destination / f"{datetime.now(UTC):%Y-%m-%dT%H-%M-%S-%fZ}.json"
    filename.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Snapshot saved to {filename.relative_to(ROOT)}")
    repository = report["metrics"]["repository"]
    for label, value in (
        ("Stars (current total)", repository["stargazers_count"] if repository else None),
        ("Unique visitors (14 days)", (report["metrics"]["views"] or {}).get("uniques")),
        ("Full clones (14 days)", (report["metrics"]["clones"] or {}).get("count")),
    ):
        print(f"{label}: {value if value is not None else 'unavailable'}")
    if report["errors"]:
        print("Some metrics are unavailable. Check gh authentication and repository push access.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
