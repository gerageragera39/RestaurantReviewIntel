"""Orchestrate one source, deduplication, and local exports."""

from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
import logging

from rri.config import ScrapeConfig
from rri.deduplication import deduplicate_reviews
from rri.errors import FailureState, ScrapeError
from rri.sources.base import ScrapeRequest, SourceAdapter
from rri.storage import write_csv, write_json, write_report


@dataclass(frozen=True, slots=True)
class ScrapeResult:
    review_count: int
    json_path: Path
    csv_path: Path
    rating_only_count: int
    unique_count: int
    stop_reason: str
    newest_selected: bool
    report_path: Path
    status: str
    all_json_path: Path
    all_csv_path: Path


def scrape_and_export(*, url: str, config: ScrapeConfig, adapter: SourceAdapter) -> ScrapeResult:
    request_options = {field.name: getattr(config, field.name) for field in fields(ScrapeRequest) if field.name != "url"}
    request = ScrapeRequest(url=url, **request_options)
    stem = datetime.now(timezone.utc).strftime("reviews-%Y%m%dT%H%M%S%fZ")
    report_path = config.report_dir / f"{stem}.report.json"
    try:
        batch = adapter.scrape(request)
        if not batch.reviews and not batch.rating_only_count and not batch.rating_only_reviews:
            raise ScrapeError(FailureState.REVIEWS_NOT_FOUND, "No reviews were returned by the source.")
    except ScrapeError as exc:
        report = {"schema_version": 1, "source_url": url,
                  "status": "BLOCKED" if exc.state in {FailureState.INACCESSIBLE_PAGE, FailureState.BLOCKED_CAPTCHA, FailureState.CONSENT_REQUIRED} else "PARTIAL",
                  "stop_reason": exc.access_kind or exc.state.value,
                  "full_reviews_opened": False, "displayed_review_count": None,
                  "unique_reviews": 0, "with_full_text": 0, "rating_only_reviews": 0,
                  "with_raw_dates": 0, "with_normalized_dates": 0, "newest_selected": False,
                  "authentication": "not_observed", "session_mode": "persistent_profile" if config.profile_dir else "anonymous",
                  "failure_state": exc.state.value, "failure_message": str(exc), **exc.report,
                  "review_exports_written": False}
        try:
            exc.report_path = write_report(report, report_path)
        except OSError:
            logging.getLogger(__name__).warning('Could not write run report; preserving original source failure')
        raise
    unique = deduplicate_reviews(batch.reviews)
    # Defensive filtering also protects exports from future provider adapters.
    rating_only_count = batch.rating_only_count + sum(not review.text.strip() for review in unique)
    reviews = [review for review in unique if review.text.strip()]
    if config.limit:
        reviews = reviews[:config.limit]
    if not reviews and not rating_only_count:
        raise ScrapeError(FailureState.REVIEWS_NOT_FOUND, "No reviews were returned by the source.")
    # Failures from the adapter happen before any export is created.
    json_path = write_json(reviews, config.export_dir / f"{stem}.json")
    csv_path = write_csv(reviews, config.export_dir / f"{stem}.csv")
    allowed_ids = {r.review_id for r in reviews + [r for r in unique if not r.text.strip()] + batch.rating_only_reviews}
    all_records = deduplicate_reviews([r for r in batch.records if r.review_id in allowed_ids])
    all_json_path = write_json(all_records, config.export_dir / f"{stem}-all.json")
    all_csv_path = write_csv(all_records, config.export_dir / f"{stem}-all.csv")
    summary = batch.summary()
    encountered_records = deduplicate_reviews(batch.records)
    # Keep the report consistent when enforcing limits/filtering on a future adapter.
    if len(reviews) != len(batch.reviews):
        summary['status'] = 'PARTIAL'
    summary.update(schema_version=1, source_url=url, session_mode='persistent_profile' if config.profile_dir else 'anonymous',
                   text_reviews_exported=len(reviews), all_reviews_exported=len(all_records), review_exports_written=True,
                   unique_reviews=len(unique) + batch.rating_only_count,
                   with_full_text=sum(bool(r.text.strip()) for r in encountered_records),
                   rating_only_reviews=rating_only_count,
                   with_raw_dates=sum(bool(r.review_date_raw.strip()) for r in encountered_records),
                   with_normalized_dates=sum(r.date_estimate is not None for r in encountered_records),
                   json_path=str(json_path), csv_path=str(csv_path),
                   all_json_path=str(all_json_path), all_csv_path=str(all_csv_path))
    write_report(summary, report_path)
    logging.getLogger(__name__).info("Export JSON=%s CSV=%s", json_path, csv_path)
    return ScrapeResult(len(reviews), json_path, csv_path, rating_only_count,
                        len(unique) + batch.rating_only_count, batch.stop_reason, batch.newest_selected,
                        report_path, summary['status'], all_json_path, all_csv_path)
