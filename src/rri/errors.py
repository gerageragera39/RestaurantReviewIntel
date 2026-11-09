"""Expected scraping failures; callers can branch on state without parsing prose."""

from enum import StrEnum


class FailureState(StrEnum):
    INACCESSIBLE_PAGE = "inaccessible_page"
    CONSENT_REQUIRED = "consent_required"
    REVIEWS_NOT_FOUND = "reviews_not_found"
    BLOCKED_CAPTCHA = "blocked_captcha"
    TIMEOUT = "timeout"
    EXTRACTION_FAILED = "extraction_failed"


class ScrapeError(Exception):
    def __init__(self, state: FailureState, message: str, *, access_kind: str | None = None,
                 evidence: str | None = None) -> None:
        self.state = state
        self.access_kind = access_kind
        self.evidence = evidence
        self.report: dict = {}
        self.report_path = None
        super().__init__(message)
