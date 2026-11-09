"""Import local extension JSON without launching a browser or changing the scraper."""

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from rri.models import DateAccuracy, Review
from rri.storage import write_csv, write_json


def load_extension_json(source: Path) -> list[Review]:
    records = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(records, list):
        raise ValueError("Extension JSON must contain an array of reviews")
    reviews: dict[tuple[str, str], Review] = {}
    for index, record in enumerate(records, 1):
        try:
            estimate = record["date_estimate"]
            exact = record["date_is_exact"]
            if type(exact) is not bool or (exact and not estimate):
                raise ValueError("date_is_exact must be boolean and exact dates need an estimate")
            accuracy = DateAccuracy.UNKNOWN if estimate is None else (
                DateAccuracy.EXACT if exact else DateAccuracy.ESTIMATED
            )
            for alias, primary in (("star_rating", "rating"), ("review_date_raw", "date_raw")):
                if alias in record and record[alias] != record[primary]:
                    raise ValueError(f"Conflicting fields: {alias}, {primary}")
            if "date_accuracy" in record and record["date_accuracy"] != accuracy.value:
                raise ValueError("Conflicting date accuracy")
            review = Review(
                restaurant_url=record["restaurant_url"], restaurant_name=record["restaurant_name"],
                review_id=record["review_id"], text=record["text"], star_rating=record["rating"],
                review_date_raw=record["date_raw"], date_estimate=date.fromisoformat(estimate) if estimate else None,
                date_accuracy=accuracy, scraped_at=datetime.fromisoformat(record["scraped_at"].replace("Z", "+00:00")),
            )
            key = (review.restaurant_url, review.review_id)
            previous = reviews.get(key)
            if previous is None or len(review.text) > len(previous.text):
                reviews[key] = review
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"Invalid extension record {index}: {exc}") from exc
    return list(reviews.values())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-prefix", type=Path, default=Path("data/exports/extension-import"))
    args = parser.parse_args(argv)
    try:
        reviews = load_extension_json(args.source)
        json_path = write_json(reviews, Path(str(args.output_prefix) + ".json"))
        csv_path = write_csv(reviews, Path(str(args.output_prefix) + ".csv"))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    print(f"Imported {len(reviews)} unique reviews ({sum(bool(r.text) for r in reviews)} with text)")
    print(json_path)
    print(csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
