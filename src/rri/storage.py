"""UTF-8 exports with one stable schema and atomic replacement per file."""

import csv
import json
import os
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

from rri.models import Review

EXPORT_FIELDS = (
    "restaurant_url", "restaurant_name", "review_id", "text", "star_rating",
    "review_date_raw", "date_estimate", "date_accuracy", "scraped_at", "review_url",
)


def _write_atomic(destination: Path, write: Callable[[TextIO], None]) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=destination.parent,
            prefix=f".{destination.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            write(stream)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def write_json(reviews: Sequence[Review], destination: Path) -> Path:
    def write(stream: TextIO) -> None:
        json.dump([review.to_record() for review in reviews], stream, ensure_ascii=False, indent=2)
        stream.write("\n")

    return _write_atomic(destination, write)


def write_report(report: dict, destination: Path) -> Path:
    def write(stream: TextIO) -> None:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return _write_atomic(destination, write)


def write_csv(reviews: Sequence[Review], destination: Path) -> Path:
    def write(stream: TextIO) -> None:
        writer = csv.DictWriter(stream, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(review.to_record() for review in reviews)

    return _write_atomic(destination, write)
