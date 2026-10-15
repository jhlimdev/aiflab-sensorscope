"""Replay numeric CSV rows into an instance started with FP_SIMULATOR=false."""

import argparse
import csv
import json
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=float, default=1)
    args = parser.parse_args()
    if args.interval < 0:
        parser.error("--interval must be non-negative")
    with open(args.csv_file, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            payload = {"machine_id": row["machine_id"]}
            payload.update(
                {metric: float(row[metric]) for metric in ("temperature", "vibration", "current")}
            )
            request = urllib.request.Request(
                args.url.rstrip("/") + "/api/readings",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    result = json.load(response)
                print(f"{result['machine_id']}: {result['status']} {result['anomalies']}")
            except urllib.error.HTTPError as exc:
                parser.exit(1, f"HTTP {exc.code}: {exc.read().decode()}\n")
            except urllib.error.URLError as exc:
                parser.exit(1, f"Cannot reach server: {exc.reason}\n")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
