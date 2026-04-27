"""
Connected App Connector Template

Use this file as the bridge between Aura / Gmail / Outlook / claim portals
and the normalized claim_events CSV expected by claim_loop_analyzer.py.

Do not hard-code secrets. Use environment variables or a secret manager.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Iterable, Dict


NORMALIZED_COLUMNS = [
    "claim_id",
    "event_time",
    "event_type",
    "source_app",
    "actor",
    "subject",
    "thread_id",
    "document_type",
    "evidence_url",
    "notes",
]


def write_events_csv(events: Iterable[Dict[str, str]], output_path: str) -> None:
    path = Path(output_path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NORMALIZED_COLUMNS)
        writer.writeheader()
        for event in events:
            writer.writerow({col: event.get(col, "") for col in NORMALIZED_COLUMNS})


def example_gmail_mapper(raw_message: dict, claim_id: str) -> dict:
    """
    Map a Gmail-like message object into the normalized event schema.

    Replace this with your real Gmail API fields:
      - message id
      - internalDate
      - threadId
      - headers
      - snippet
    """
    return {
        "claim_id": claim_id,
        "event_time": raw_message.get("event_time", ""),
        "event_type": raw_message.get("event_type", "email_sent"),
        "source_app": "gmail",
        "actor": raw_message.get("actor", ""),
        "subject": raw_message.get("subject", ""),
        "thread_id": raw_message.get("thread_id", ""),
        "document_type": raw_message.get("document_type", ""),
        "evidence_url": raw_message.get("evidence_url", ""),
        "notes": raw_message.get("notes", ""),
    }


def example_outlook_mapper(raw_message: dict, claim_id: str) -> dict:
    """
    Map an Outlook / Microsoft Graph message into the normalized event schema.
    """
    return {
        "claim_id": claim_id,
        "event_time": raw_message.get("sentDateTime") or raw_message.get("receivedDateTime", ""),
        "event_type": raw_message.get("event_type", "email_sent"),
        "source_app": "outlook",
        "actor": raw_message.get("from", {}).get("emailAddress", {}).get("address", ""),
        "subject": raw_message.get("subject", ""),
        "thread_id": raw_message.get("conversationId", ""),
        "document_type": raw_message.get("document_type", ""),
        "evidence_url": raw_message.get("webLink", ""),
        "notes": raw_message.get("bodyPreview", ""),
    }


if __name__ == "__main__":
    demo_events = [
        {
            "claim_id": "CLAIM-001",
            "event_time": "2026-04-03T09:12:00-04:00",
            "event_type": "claim_submitted",
            "source_app": "gmail",
            "actor": "claimant",
            "subject": "Initial claim package",
            "thread_id": "thread-001",
            "document_type": "initial_claim_package",
            "evidence_url": "secure://gmail/thread-001",
            "notes": "Initial submission sent to insurer.",
        }
    ]
    write_events_csv(demo_events, "connected_app_events.csv")
    print("Wrote connected_app_events.csv")
