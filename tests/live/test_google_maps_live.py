"""Never runs by default; requires a user-authorized --live-url."""
import json

import pytest

from rri.config import ScrapeConfig
from rri.service import scrape_and_export
from rri.sources.google_maps.adapter import GoogleMapsAdapter


@pytest.mark.live
def test_live_public_reviews(request, tmp_path):
    result = scrape_and_export(
        url=request.config.getoption("--live-url"),
        config=ScrapeConfig(limit=5, headed=True, debug=True,
                            export_dir=tmp_path / "exports", report_dir=tmp_path / "reports", debug_dir=tmp_path / "debug",
                            profile_dir=request.config.getoption("--live-profile")),
        adapter=GoogleMapsAdapter(),
    )
    records = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert 0 < len(records) <= 5
    assert len({record["review_id"] for record in records}) == len(records)
    assert all(record["text"].strip() and record["review_date_raw"] for record in records)
