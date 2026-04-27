#!/usr/bin/env python3
"""
Aura Claim Loop Analyzer

Purpose:
    Quantify insurance-claim administrative loops using connected-app timestamps.
    The program ingests a CSV claim-event ledger, calculates time-to-acknowledgement,
    detects recursive administration loops, and exports evidence-ready reports.

Run:
    python claim_loop_analyzer.py --input sample_claim_events.csv --output outputs --ack-hours 168

Expected input columns:
    claim_id,event_time,event_type,source_app,actor,subject,thread_id,document_type,evidence_url,notes

Event types:
    claim_submitted
    document_uploaded
    email_sent
    email_received
    acknowledgement
    duplicate_request
    status_change
    phone_call
    voicemail
    escalation
    denial
    payment
    silence_gap
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


SEND_EVENT_TYPES = {"claim_submitted", "document_uploaded", "email_sent"}
ACK_EVENT_TYPES = {"acknowledgement", "email_received", "status_change"}
LOOP_EVENT_TYPES = {"duplicate_request", "escalation", "silence_gap"}


REQUIRED_COLUMNS = [
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


@dataclass
class AckResult:
    claim_id: str
    loop_key: str
    sent_time: str
    ack_due_time: str
    ack_time: Optional[str]
    hours_to_ack: Optional[float]
    delay_hours: Optional[float]
    delay_days: Optional[float]
    status: str
    source_event_type: str
    source_app: str
    evidence_url: str


@dataclass
class LoopResult:
    claim_id: str
    loop_key: str
    loop_type: str
    original_time: Optional[str]
    loop_event_time: str
    delay_hours_since_original: Optional[float]
    delay_days_since_original: Optional[float]
    source_app: str
    evidence_url: str
    notes: str


def parse_time(value: str) -> pd.Timestamp:
    """Parse timestamps robustly and preserve timezone if provided."""
    if pd.isna(value) or not str(value).strip():
        raise ValueError("Missing event_time")
    ts = pd.to_datetime(value, utc=True, errors="raise")
    return ts


def normalize_loop_key(row: pd.Series) -> str:
    """
    Produce a matching key for sends/acks/duplicate requests.
    Prefer document_type; fall back to thread_id; fall back to subject.
    """
    for col in ("document_type", "thread_id", "subject"):
        val = str(row.get(col, "")).strip()
        if val and val.lower() != "nan":
            return val.lower()
    return "unclassified"


def load_events(input_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[REQUIRED_COLUMNS].copy()
    df["event_type"] = df["event_type"].astype(str).str.strip().str.lower()
    df["event_time_utc"] = df["event_time"].apply(parse_time)
    df["loop_key"] = df.apply(normalize_loop_key, axis=1)
    df = df.sort_values(["claim_id", "event_time_utc"]).reset_index(drop=True)
    return df


def calculate_time_to_ack(df: pd.DataFrame, ack_hours: float) -> List[AckResult]:
    results: List[AckResult] = []

    grouped = df.groupby(["claim_id", "loop_key"], dropna=False)
    for (claim_id, loop_key), group in grouped:
        group = group.sort_values("event_time_utc")
        sends = group[group["event_type"].isin(SEND_EVENT_TYPES)]

        for _, sent in sends.iterrows():
            sent_time = sent["event_time_utc"]
            ack_due = sent_time + pd.Timedelta(hours=ack_hours)

            later_acks = group[
                (group["event_time_utc"] >= sent_time)
                & (group["event_type"].isin(ACK_EVENT_TYPES))
            ]

            if not later_acks.empty:
                ack = later_acks.iloc[0]
                ack_time = ack["event_time_utc"]
                hours_to_ack = (ack_time - sent_time).total_seconds() / 3600
                delay_hours = max(0.0, hours_to_ack - ack_hours)
                delay_days = delay_hours / 24
                status = "late" if delay_hours > 0 else "on_time"
                ack_time_str = ack_time.isoformat()
            else:
                ack_time_str = None
                hours_to_ack = None
                now = df["event_time_utc"].max()
                delay_hours = max(0.0, (now - ack_due).total_seconds() / 3600)
                delay_days = delay_hours / 24
                status = "open_no_ack"

            results.append(
                AckResult(
                    claim_id=str(claim_id),
                    loop_key=str(loop_key),
                    sent_time=sent_time.isoformat(),
                    ack_due_time=ack_due.isoformat(),
                    ack_time=ack_time_str,
                    hours_to_ack=round(hours_to_ack, 2) if hours_to_ack is not None else None,
                    delay_hours=round(delay_hours, 2) if delay_hours is not None else None,
                    delay_days=round(delay_days, 2) if delay_days is not None else None,
                    status=status,
                    source_event_type=str(sent["event_type"]),
                    source_app=str(sent["source_app"]),
                    evidence_url=str(sent["evidence_url"]),
                )
            )

    return results


def detect_recursive_loops(df: pd.DataFrame) -> List[LoopResult]:
    loops: List[LoopResult] = []

    grouped = df.groupby(["claim_id", "loop_key"], dropna=False)
    for (claim_id, loop_key), group in grouped:
        group = group.sort_values("event_time_utc")
        original_send = group[group["event_type"].isin(SEND_EVENT_TYPES)]

        original_time = None
        if not original_send.empty:
            original_time = original_send.iloc[0]["event_time_utc"]

        for _, event in group.iterrows():
            event_type = event["event_type"]
            if event_type in LOOP_EVENT_TYPES:
                event_time = event["event_time_utc"]
                if original_time is not None:
                    delay_hours = (event_time - original_time).total_seconds() / 3600
                    delay_days = delay_hours / 24
                    original_time_str = original_time.isoformat()
                else:
                    delay_hours = None
                    delay_days = None
                    original_time_str = None

                loops.append(
                    LoopResult(
                        claim_id=str(claim_id),
                        loop_key=str(loop_key),
                        loop_type=str(event_type),
                        original_time=original_time_str,
                        loop_event_time=event_time.isoformat(),
                        delay_hours_since_original=round(delay_hours, 2) if delay_hours is not None else None,
                        delay_days_since_original=round(delay_days, 2) if delay_days is not None else None,
                        source_app=str(event["source_app"]),
                        evidence_url=str(event["evidence_url"]),
                        notes=str(event["notes"]),
                    )
                )

    return loops


def score_loop_severity(df_ack: pd.DataFrame, df_loops: pd.DataFrame) -> Dict[str, object]:
    duplicate_count = int((df_loops["loop_type"] == "duplicate_request").sum()) if not df_loops.empty else 0
    escalation_count = int((df_loops["loop_type"] == "escalation").sum()) if not df_loops.empty else 0
    silence_gap_count = int((df_loops["loop_type"] == "silence_gap").sum()) if not df_loops.empty else 0
    missed_ack_count = int((df_ack["status"].isin(["late", "open_no_ack"])).sum()) if not df_ack.empty else 0
    total_delay_days = float(df_ack["delay_days"].fillna(0).sum()) if not df_ack.empty else 0.0

    # Practical scoring formula:
    score = (
        duplicate_count * 2
        + missed_ack_count * 3
        + escalation_count * 2
        + silence_gap_count * 2
        + (total_delay_days / 5)
    )

    if score <= 5:
        severity = "ordinary_friction"
    elif score <= 15:
        severity = "moderate_admin_delay"
    elif score <= 30:
        severity = "material_recursive_loop"
    else:
        severity = "severe_claim_handling_breakdown"

    return {
        "duplicate_request_count": duplicate_count,
        "missed_ack_count": missed_ack_count,
        "escalation_count": escalation_count,
        "silence_gap_count": silence_gap_count,
        "total_delay_days": round(total_delay_days, 2),
        "recursive_admin_loop_score": round(score, 2),
        "severity": severity,
    }


def write_markdown_exhibit(
    out_path: Path,
    input_file: Path,
    df_ack: pd.DataFrame,
    df_loops: pd.DataFrame,
    summary: Dict[str, object],
    ack_hours: float,
) -> None:
    lines = []
    lines.append("# Insurance Claim Recursive Administration Loop Exhibit\n")
    lines.append(f"Input file: `{input_file.name}`  \n")
    lines.append(f"Acknowledgement benchmark: **{ack_hours} hours**\n")

    lines.append("## Summary\n")
    for key, value in summary.items():
        lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")
    lines.append("")

    lines.append("## Time-to-Acknowledgement Findings\n")
    if df_ack.empty:
        lines.append("No acknowledgement records calculated.\n")
    else:
        display_cols = [
            "claim_id",
            "loop_key",
            "sent_time",
            "ack_due_time",
            "ack_time",
            "hours_to_ack",
            "delay_days",
            "status",
            "source_app",
            "evidence_url",
        ]
        lines.append(df_ack[display_cols].to_markdown(index=False))
        lines.append("")

    lines.append("## Recursive Loop Findings\n")
    if df_loops.empty:
        lines.append("No duplicate request, silence gap, or escalation loop events detected.\n")
    else:
        display_cols = [
            "claim_id",
            "loop_key",
            "loop_type",
            "original_time",
            "loop_event_time",
            "delay_days_since_original",
            "source_app",
            "evidence_url",
            "notes",
        ]
        lines.append(df_loops[display_cols].to_markdown(index=False))
        lines.append("")

    lines.append("## Suggested Claim Language\n")
    lines.append(
        "> I am documenting a recurring administrative loop in the handling of this claim. "
        "The enclosed timeline shows repeated cycles of submission, non-acknowledgement, duplicate requests, "
        "unexplained handoffs, silence gaps, and delayed confirmation of receipt. I have separated ordinary "
        "review time from insurer-caused loop delay and quantified the resulting time loss and claim-processing burden."
    )
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def run_analysis(input_path: Path, output_dir: Path, ack_hours: float) -> Dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_events(input_path)
    df.to_csv(output_dir / "normalized_claim_events.csv", index=False)

    ack_results = calculate_time_to_ack(df, ack_hours)
    loop_results = detect_recursive_loops(df)

    df_ack = pd.DataFrame([asdict(x) for x in ack_results])
    df_loops = pd.DataFrame([asdict(x) for x in loop_results])

    df_ack.to_csv(output_dir / "time_to_ack_report.csv", index=False)
    df_loops.to_csv(output_dir / "recursive_loop_report.csv", index=False)

    summary = score_loop_severity(df_ack, df_loops)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_markdown_exhibit(
        output_dir / "claim_delay_exhibit.md",
        input_path,
        df_ack,
        df_loops,
        summary,
        ack_hours,
    )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Quantify insurance claim recursive administration loops.")
    parser.add_argument("--input", required=True, help="Path to claim event CSV.")
    parser.add_argument("--output", default="outputs", help="Directory for generated reports.")
    parser.add_argument(
        "--ack-hours",
        type=float,
        default=168,
        help="Acknowledgement benchmark in hours. Default 168 = 7 days.",
    )
    args = parser.parse_args()

    summary = run_analysis(Path(args.input), Path(args.output), args.ack_hours)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
