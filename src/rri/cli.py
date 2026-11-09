"""The rri entry point; command parsing stays separate from scraping."""

import argparse
import sys
import logging
import time
import json
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path

from rri.config import load_config
from rri.errors import ScrapeError
from rri.service import scrape_and_export
from rri.sources.google_maps.adapter import GoogleMapsAdapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rri", description="Local restaurant review collection.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scrape = subparsers.add_parser(
        "scrape", help="Collect public text reviews from one Google Maps restaurant.",
    )
    scrape.add_argument("--url", required=True, help="Public Google Maps restaurant URL.")
    scrape.add_argument("--limit", type=int, default=None, help="Maximum text reviews; 0 removes the artificial limit (default: 50).")
    scrape.add_argument("--profile-dir", type=Path, help="Dedicated persistent RRI browser profile; omit for anonymous access.")
    scrape.add_argument(
        "--headed", action=argparse.BooleanOptionalAction, default=None,
        help="Show Chromium (default); --no-headed runs headless.",
    )
    scrape.add_argument("--config", type=Path, help="Optional JSON configuration file.")
    scrape.add_argument("--debug", action=argparse.BooleanOptionalAction, default=None,
                        help="Save a redacted screenshot and diagnostic HTML under data/debug/.")
    for name, help_text in (
        ("timeout-ms", "Per-operation timeout in milliseconds (default: 30000)."),
        ("collection-timeout-ms", "Overall browser collection budget (default: 180000)."),
        ("max-scroll-iterations", "Maximum review-container scrolls (default: 100)."),
        ("max-idle-iterations", "Stop after this many scrolls without new IDs (default: 5)."),
        ("scroll-wait-ms", "Wait for each scroll's DOM updates (default: 1500)."),
    ):
        scrape.add_argument(f"--{name}", type=int, default=None, help=help_text)
    login = subparsers.add_parser("login", help="Open an isolated visible profile for manual sign-in and verify Reviews access.")
    login.add_argument("--url", required=True)
    login.add_argument("--profile-dir", type=Path, default=Path("data/browser-profile"))
    login.add_argument("--login-timeout-ms", type=int, default=600_000)
    login.add_argument("--timeout-ms", type=int, default=30_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    started = time.monotonic()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger(__name__)
    try:
        if args.command == "login":
            from rri.sources.base import ScrapeRequest
            from rri.sources.google_maps.login import manual_login
            from rri.storage import write_report
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            path = Path('data/reports') / f'login-{stamp}.report.json'
            try:
                report = manual_login(ScrapeRequest(url=args.url, profile_dir=args.profile_dir,
                                                    timeout_ms=args.timeout_ms, headed=True),
                                      login_timeout_ms=args.login_timeout_ms)
            except ScrapeError as exc:
                try:
                    exc.report_path = write_report({'source_url': args.url, 'status': 'BLOCKED',
                                                    'failure_state': exc.state.value, 'stop_reason': exc.access_kind or exc.state.value,
                                                    'authentication': 'not_observed', 'failure_message': str(exc), **exc.report}, path)
                except OSError:
                    logger.warning('Could not write login report; preserving original failure')
                raise
            write_report(report, path)
            print(json.dumps(report, indent=2))
            print(f'Login report: {path}')
            return 0
        config = load_config(args.config)
        overrides = {
            name: getattr(args, name) for name in (
                "limit", "headed", "debug", "timeout_ms", "collection_timeout_ms",
                "max_scroll_iterations", "max_idle_iterations", "scroll_wait_ms", "profile_dir",
            )
            if getattr(args, name) is not None
        }
        config = replace(config, **overrides)
        result = scrape_and_export(url=args.url, config=config, adapter=GoogleMapsAdapter())
    except ValueError as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        print('Cancelled; the isolated profile remains local. No login was automated.', file=sys.stderr)
        return 130
    except ScrapeError as exc:
        print(f"{exc.state.value}: {exc}", file=sys.stderr)
        if exc.report_path:
            print(f"Run report: {exc.report_path}", file=sys.stderr)
        logger.error("Final status=%s elapsed=%.2fs", exc.state.value, time.monotonic() - started)
        return 1
    except OSError as exc:
        print(f"export_failed: {exc}", file=sys.stderr)
        logger.error("Final status=export_failed elapsed=%.2fs", time.monotonic() - started)
        return 1
    print(f"Exported {result.review_count} text reviews; rating-only={result.rating_only_count}; "
          f"total unique encountered={result.unique_count}; stop={result.stop_reason}; "
          f"newest_selected={result.newest_selected}; status={result.status}.\nJSON: {result.json_path}\nCSV: {result.csv_path}\n"
          f"All records: {result.all_json_path}, {result.all_csv_path}\nRun report: {result.report_path}")
    status = result.status
    logger.info("Final status=%s stop=%s elapsed=%.2fs", status, result.stop_reason, time.monotonic() - started)
    return 0
