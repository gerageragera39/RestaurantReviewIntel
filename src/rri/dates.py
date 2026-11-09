"""Conservative English/German date parsing, independent of the host locale."""

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

from rri.models import DateAccuracy

_MONTHS = {
    name.casefold(): index
    for index, names in enumerate(
        (
            ("January", "Jan"), ("February", "Feb"), ("March", "Mar"),
            ("April", "Apr"), ("May",), ("June", "Jun"), ("July", "Jul"),
            ("August", "Aug"), ("September", "Sep", "Sept"), ("October", "Oct"),
            ("November", "Nov"), ("December", "Dec"),
        ),
        start=1,
    )
    for name in names
}
_RELATIVE = re.compile(r"(a|an|\d+) (minute|hour|day|week|month|year)s? ago")
_GERMAN_RELATIVE = re.compile(
    r"vor (einem|einer|ein|\d+) (minute[n]?|stunde[n]?|tag(?:en|e)?|woche[n]?|monat(?:en|e)?|jahr(?:en|e)?)"
)
_GERMAN_UNITS = {
    "minute": "minute", "minuten": "minute", "stunde": "hour", "stunden": "hour",
    "tag": "day", "tage": "day", "tagen": "day", "woche": "week", "wochen": "week",
    "monat": "month", "monate": "month", "monaten": "month",
    "jahr": "year", "jahre": "year", "jahren": "year",
}
_MONTHS.update({name: month for month, names in enumerate((
    ("januar",), ("februar",), ("märz", "mär"), ("april",), ("mai",), ("juni",),
    ("juli",), ("august",), ("september",), ("oktober", "okt"), ("november",), ("dezember", "dez"),
), 1) for name in names})


@dataclass(frozen=True, slots=True)
class ParsedReviewDate:
    date_estimate: date | None
    accuracy: DateAccuracy


def _months_before(reference: date, months: int) -> date:
    month_index = reference.year * 12 + reference.month - 1 - months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(reference.day, calendar.monthrange(year, month)[1]))


def parse_review_date(text: str, *, reference_date: date) -> ParsedReviewDate:
    """Keep unrecognized, impossible, and future dates unknown.

    Relative labels are approximate observations, never exact publication dates.
    The caller supplies the date in the browser's display timezone, not an
    implicit local clock. The original label is stored separately on Review.
    """
    if not isinstance(text, str):
        raise ValueError("date text must be a string")
    if type(reference_date) is not date:
        raise ValueError("reference_date must be a date")
    normalized = " ".join(text.casefold().split())
    unknown = ParsedReviewDate(None, DateAccuracy.UNKNOWN)
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
            result = date.fromisoformat(normalized)
            accuracy = DateAccuracy.EXACT
        elif match := re.fullmatch(r"([a-z]+) (\d{1,2}), (\d{4})", normalized):
            month_name, day, year = match.groups()
            result = date(int(year), _MONTHS[month_name], int(day))
            accuracy = DateAccuracy.EXACT
        elif match := re.fullmatch(r"(\d{1,2})\.? ([a-zäöü]+)\.? (\d{4})", normalized):
            day, month_name, year = match.groups()
            result = date(int(year), _MONTHS[month_name], int(day))
            accuracy = DateAccuracy.EXACT
        elif re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", normalized):
            day, month, year = map(int, normalized.split("."))
            result = date(year, month, day)
            accuracy = DateAccuracy.EXACT
        elif normalized in {"today", "yesterday", "heute", "gestern"}:
            result = reference_date - timedelta(days=int(normalized in {"yesterday", "gestern"}))
            accuracy = DateAccuracy.ESTIMATED
        elif (match := _RELATIVE.fullmatch(normalized)) or (match := _GERMAN_RELATIVE.fullmatch(normalized)):
            count_text, unit = match.groups()
            count = 1 if count_text in {"a", "an", "einem", "einer", "ein"} else int(count_text)
            unit = _GERMAN_UNITS.get(unit, unit)
            if unit in {"minute", "hour"}:
                # A date-only reference cannot resolve a midnight boundary.
                return unknown
            if unit in {"month", "year"}:
                result = _months_before(reference_date, count * (12 if unit == "year" else 1))
            else:
                result = reference_date - timedelta(days=count * (7 if unit == "week" else 1))
            accuracy = DateAccuracy.ESTIMATED
        else:
            return unknown
    except (ValueError, OverflowError, KeyError):
        return unknown
    return ParsedReviewDate(result, accuracy) if result <= reference_date else unknown
