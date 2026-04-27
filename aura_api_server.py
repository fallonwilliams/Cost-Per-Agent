#!/usr/bin/env python3
"""
Aura Claim API Server

A lightweight FastAPI wrapper around the claim loop analyzer.

Run:
    uvicorn aura_api_server:app --reload

Example:
    POST /analyze
    {
      "input_csv": "sample_claim_events.csv",
      "output_dir": "outputs",
      "ack_hours": 168
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from claim_loop_analyzer import run_analysis


app = FastAPI(
    title="Aura Claim Loop API",
    description="API for calculating insurance claim time-to-ack and recursive administration loops.",
    version="1.0.0",
)


class AnalyzeRequest(BaseModel):
    input_csv: str = Field(..., description="Path to the input claim events CSV.")
    output_dir: str = Field("outputs", description="Directory where output reports should be written.")
    ack_hours: float = Field(168, description="Acknowledgement benchmark in hours.")


class AnalyzeResponse(BaseModel):
    summary: dict
    output_dir: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_claim(req: AnalyzeRequest) -> AnalyzeResponse:
    input_path = Path(req.input_csv)
    if not input_path.exists():
        raise HTTPException(status_code=404, detail=f"Input CSV not found: {input_path}")

    output_path = Path(req.output_dir)
    try:
        summary = run_analysis(input_path, output_path, req.ack_hours)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return AnalyzeResponse(summary=summary, output_dir=str(output_path.resolve()))
