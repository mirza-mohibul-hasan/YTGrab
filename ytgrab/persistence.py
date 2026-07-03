from __future__ import annotations

import json
import os
from dataclasses import asdict

from ytgrab.models import DownloadItem, DownloadStatus


def default_queue_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".ytgrab", "queue.json")


def save_queue(items: list[DownloadItem], path: str | None = None) -> None:
    path = path or default_queue_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = []
    for item in items:
        data = asdict(item)
        data["status"] = item.status.value
        payload.append(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_queue(path: str | None = None) -> list[DownloadItem]:
    path = path or default_queue_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    items = []
    for data in payload:
        try:
            data["status"] = DownloadStatus(data["status"])
            items.append(DownloadItem(**data))
        except (KeyError, ValueError, TypeError):
            continue
    return items
