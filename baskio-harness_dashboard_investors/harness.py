#!/usr/bin/env python
"""Baskio dashboard harness — keeps the dashboard generated, always.

Runs build.run_once() on a fixed interval, forever. Each iteration is
independent: if Supabase is unreachable or the new data fails the quality
gate, the last known-good dashboard is left untouched and the failure is
recorded in CHANGELOG.md / harness.log — the loop just tries again next
interval instead of crashing or serving a broken page.

This is the "always generate + improvement loop" piece: every run either
promotes a validated, better-documented version of the dashboard, or leaves
things exactly as they were and tells you why.

Usage:
    python harness.py --interval-minutes 60      # loop forever, hourly
    python harness.py --once                      # single run, then exit
    python harness.py --interval-minutes 30 --max-failures 5
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import run_once, log  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval-minutes", type=float, default=60.0,
                     help="Minutes between builds when looping (default: 60)")
    ap.add_argument("--once", action="store_true", help="Run a single build and exit")
    ap.add_argument("--dsn", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-failures", type=int, default=0,
                     help="Stop the loop after this many consecutive failures (0 = never stop)")
    args = ap.parse_args()

    if args.once:
        ok = run_once(dsn=args.dsn, dry_run=args.dry_run)
        sys.exit(0 if ok or args.dry_run else 1)

    log(f"Harness starting — loop every {args.interval_minutes} min. Ctrl+C to stop.")
    consecutive_failures = 0
    while True:
        ok = run_once(dsn=args.dsn, dry_run=args.dry_run)
        consecutive_failures = 0 if ok else consecutive_failures + 1

        if args.max_failures and consecutive_failures >= args.max_failures:
            log(f"Stopping: {consecutive_failures} consecutive failed/rejected builds "
                f"(--max-failures={args.max_failures}).")
            sys.exit(1)

        # Back off a bit longer after a failure so a broken data source doesn't
        # get hammered every interval; still bounded so it keeps retrying.
        wait_s = args.interval_minutes * 60
        if not ok:
            wait_s = min(wait_s, max(wait_s / 2, 300))
            log(f"Last build did not promote. Retrying in {wait_s/60:.1f} min instead of "
                f"the full {args.interval_minutes} min interval.")
        try:
            time.sleep(wait_s)
        except KeyboardInterrupt:
            log("Harness stopped by user.")
            break


if __name__ == "__main__":
    main()
