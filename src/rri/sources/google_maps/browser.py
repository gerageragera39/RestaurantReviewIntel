"""Isolated browser lifecycle. Persistent profiles contain secrets; never inspect them."""

import json
import logging
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)
_MARKER = ".rri-profile.json"


def prepare_profile(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.exists() and not path.is_dir():
        raise ValueError("profile-dir must be a directory")
    marker = path / _MARKER
    if path.exists() and any(path.iterdir()) and not marker.is_file():
        raise ValueError("Refusing an existing non-RRI profile. Choose a new isolated directory; never use your regular Chrome profile.")
    if marker.is_file():
        try:
            if json.loads(marker.read_text(encoding="utf-8")) != {"application": "rri", "version": 1}:
                raise ValueError("Invalid RRI profile marker")
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Cannot validate the isolated RRI profile") from exc
    path.mkdir(parents=True, exist_ok=True)
    # Also protect arbitrary custom profile locations inside a repository.
    (path / ".gitignore").write_text("*\n", encoding="utf-8")
    marker.write_text(json.dumps({"application": "rri", "version": 1}) + "\n", encoding="utf-8")
    return path


@contextmanager
def browser_session(playwright, request, timeout):
    browser = context = None
    try:
        options = {"viewport": {"width": 1440, "height": 1000}, "locale": "en-US", "timezone_id": "UTC"}
        if request.profile_dir is not None:
            profile = prepare_profile(request.profile_dir)
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile), headless=not request.headed, timeout=timeout, **options,
            )
        else:
            browser = playwright.chromium.launch(headless=not request.headed, timeout=timeout)
            context = browser.new_context(**options)
        yield context
    finally:
        for resource in (context, browser):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    logger.warning("Browser resource already closed during cleanup")
