import json
from datetime import date
from pathlib import Path

import pytest

from rri.dates import parse_review_date
from rri.models import DateAccuracy

CASES = json.loads((Path(__file__).parent / "fixtures/date_cases.json").read_text(encoding="utf-8"))


@pytest.fixture(params=CASES, ids=lambda case: f"{case['reference']}:{case['text']!r}")
def date_case(request):
    return request.param


def test_parse_date_fixture(date_case):
    result = parse_review_date(date_case["text"], reference_date=date.fromisoformat(date_case["reference"]))
    expected = date.fromisoformat(date_case["date"]) if date_case["date"] else None
    assert result.date_estimate == expected
    assert result.accuracy is DateAccuracy(date_case["accuracy"])


def test_reference_date_is_explicit():
    with pytest.raises(TypeError):
        parse_review_date("a week ago")


def test_invalid_input_is_rejected():
    with pytest.raises(ValueError, match="string"):
        parse_review_date(None, reference_date=date(2026, 11, 9))
