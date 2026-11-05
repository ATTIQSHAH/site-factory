"""Run the quality gate against every site generated in the latest factory batch."""
import csv
import subprocess
import sys
from pathlib import Path


RESULTS = Path("results/websites_tab.csv")
SITES = Path("sites")


def main():
    if not RESULTS.is_file():
        raise SystemExit("Missing results/websites_tab.csv")
    with RESULTS.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    generated = [row for row in rows if row.get("fetch_status") == "ok" and row.get("batch")]
    if not generated:
        raise SystemExit("No successfully generated sites found for review")
    latest = max(int(row["batch"]) for row in generated)
    targets = [row for row in generated if int(row["batch"]) == latest]
    if not targets:
        raise SystemExit("Latest batch contains no sites to review")

    failures = []
    for row in targets:
        relative = (row.get("site_path") or "").strip("/")
        site = (SITES / relative).resolve()
        if not site.is_dir() or SITES.resolve() not in site.parents:
            failures.append(f'{row.get("Name")}: invalid or missing site path {relative}')
            continue
        report = Path("review") / f"batch-{latest}" / relative
        command = [
            sys.executable, "review_site.py",
            "--site", str(site),
            "--report-dir", str(report),
            "--business", row.get("Name", ""),
            "--phone", row.get("Phone", ""),
            "--source-website", row.get("Website", ""),
        ]
        print(f'Reviewing {row.get("Name")} ({row.get("Website")})', flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode:
            failures.append(f'{row.get("Name")}: quality review failed; see {report}/report.json')
    if failures:
        raise SystemExit("Batch blocked from publishing:\n- " + "\n- ".join(failures))
    print(f"All {len(targets)} sites in batch {latest} passed review.")


if __name__ == "__main__":
    main()
