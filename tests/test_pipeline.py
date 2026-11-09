import csv
import json
from dataclasses import replace

import pytest

from rri.cli import main
from rri.config import ScrapeConfig, load_config
from rri.errors import FailureState, ScrapeError
from rri.service import scrape_and_export
from rri.sources.base import CollectionResult


@pytest.fixture(autouse=True)
def isolate_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


class FakeAdapter:
    def __init__(self, reviews):
        self.reviews = reviews
        self.request = None

    def scrape(self, request):
        self.request = request
        return CollectionResult(self.reviews)


def test_pipeline_passes_options_and_exports_unique_reviews(review, tmp_path):
    other = replace(review, review_id="google_maps:native:second", text="Second review")
    adapter = FakeAdapter([review, review, other])
    config = ScrapeConfig(limit=2, headed=True, timeout_ms=1234, export_dir=tmp_path / "exports")
    result = scrape_and_export(url=review.restaurant_url, config=config, adapter=adapter)
    assert (adapter.request.url, adapter.request.limit, adapter.request.headed, adapter.request.timeout_ms) == (
        review.restaurant_url, 2, True, 1234,
    )
    assert result.review_count == 2
    records = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert records == [review.to_record(), other.to_record()]
    with result.csv_path.open(encoding="utf-8", newline="") as stream:
        csv_records = list(csv.DictReader(stream))
    assert len(csv_records) == 2
    assert csv_records[0]["text"] == review.text  # Multiline Unicode must survive CSV quoting.
    assert set(csv_records[0]) == set(records[0])
    assert not list(config.export_dir.glob("*.tmp"))


def test_pipeline_enforces_limit(review, tmp_path):
    adapter = FakeAdapter([review, replace(review, review_id="second")])
    result = scrape_and_export(
        url=review.restaurant_url, config=ScrapeConfig(limit=1, export_dir=tmp_path), adapter=adapter,
    )
    assert result.review_count == 1


def test_pipeline_excludes_rating_only_and_reports_counts(review, tmp_path):
    adapter = FakeAdapter([replace(review, review_id="rating-only", text="  "), review])
    result = scrape_and_export(url=review.restaurant_url, config=ScrapeConfig(export_dir=tmp_path), adapter=adapter)
    records = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert len(records) == 1 and records[0]["text"] == review.text
    assert result.rating_only_count == 1 and result.unique_count == 2


def test_rating_only_collection_creates_empty_primary_exports(review, tmp_path):
    result = scrape_and_export(
        url=review.restaurant_url, config=ScrapeConfig(export_dir=tmp_path),
        adapter=FakeAdapter([replace(review, text="")]),
    )
    assert json.loads(result.json_path.read_text(encoding="utf-8")) == []
    with result.csv_path.open(encoding="utf-8", newline="") as stream:
        assert list(csv.DictReader(stream)) == []
    assert result.review_count == 0 and result.rating_only_count == 1


@pytest.mark.parametrize("state", list(FailureState))
def test_source_failure_never_creates_exports(review, tmp_path, state):
    class FailingAdapter:
        def scrape(self, request):
            raise ScrapeError(state, "Fixture failure")

    destination = tmp_path / "exports"
    with pytest.raises(ScrapeError) as caught:
        scrape_and_export(
            url=review.restaurant_url, config=ScrapeConfig(export_dir=destination), adapter=FailingAdapter(),
        )
    assert caught.value.state is state
    assert not destination.exists()


def test_empty_result_is_reviews_not_found(review, tmp_path):
    with pytest.raises(ScrapeError) as caught:
        scrape_and_export(
            url=review.restaurant_url, config=ScrapeConfig(export_dir=tmp_path), adapter=FakeAdapter([]),
        )
    assert caught.value.state is FailureState.REVIEWS_NOT_FOUND
    assert not list(tmp_path.glob('*.json')) and not list(tmp_path.glob('*.csv'))


def test_cli_contract_reports_failure_and_writes_nothing(review, tmp_path, monkeypatch, capsys):
    from rri.sources.google_maps.adapter import GoogleMapsAdapter

    def fail(self, request):
        raise ScrapeError(FailureState.BLOCKED_CAPTCHA, "Fixture CAPTCHA; no live browser opened")

    monkeypatch.setattr(GoogleMapsAdapter, "scrape", fail)
    monkeypatch.chdir(tmp_path)
    code = main(["scrape", "--url", review.restaurant_url, "--limit", "50", "--headed"])
    captured = capsys.readouterr()
    assert code == 1
    assert "blocked_captcha:" in captured.err
    assert "Fixture CAPTCHA" in captured.err
    assert captured.out == ""
    assert not (tmp_path / "data/exports").exists()
    reports = list((tmp_path / "data/reports").glob("*.report.json"))
    assert len(reports) == 1
    assert json.loads(reports[0].read_text(encoding="utf-8"))["status"] == "BLOCKED"


@pytest.mark.parametrize("argument", ["-1", "not-a-number"])
def test_cli_rejects_invalid_limit(review, argument):
    with pytest.raises(SystemExit) as caught:
        main(["scrape", "--url", review.restaurant_url, "--limit", argument])
    assert caught.value.code == 2


def test_example_config_loads():
    from pathlib import Path

    config = load_config(Path(__file__).parents[1] / "config.example.json")
    assert config == ScrapeConfig()


def test_cli_accepts_unlimited_with_profile(review, tmp_path, monkeypatch, capsys):
    from rri.sources.google_maps.adapter import GoogleMapsAdapter
    def collect(self, request):
        assert request.limit == 0 and request.profile_dir == tmp_path / 'profile'
        return CollectionResult([review])
    monkeypatch.setattr(GoogleMapsAdapter, 'scrape', collect)
    assert main(['scrape', '--url', review.restaurant_url, '--limit', '0', '--profile-dir', str(tmp_path / 'profile')]) == 0
    output = capsys.readouterr().out
    assert 'status=PARTIAL' in output and 'Run report:' in output


@pytest.mark.parametrize("contents", ['{"limti": 50}', '{"limit": true}', '{"headed": "false"}', '[]', '{'])
def test_invalid_config_is_rejected(tmp_path, contents):
    path = tmp_path / "config.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)
