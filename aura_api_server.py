#!/usr/bin/env python3
"""
API Server

Includes:
- Claim recursive-loop analysis endpoints.
- Production-ready agent cost ranking endpoints designed for browser plugin ingestion.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from agent_cost_ranker import AgentRun, now_utc, rank_agents_by_cost
from claim_loop_analyzer import run_analysis


app = FastAPI(
    title="Recursive Systems API",
    description=(
        "APIs for claim-loop analysis and ranking recursive AI agents by cost, "
        "with browser plugin integration metadata."
    ),
    version="2.0.0",
)


class AnalyzeRequest(BaseModel):
    input_csv: str = Field(..., description="Path to the input claim events CSV.")
    output_dir: str = Field("outputs", description="Directory where output reports should be written.")
    ack_hours: float = Field(168, description="Acknowledgement benchmark in hours.")


class AnalyzeResponse(BaseModel):
    summary: dict
    output_dir: str


class AgentRunInput(BaseModel):
    agent_id: str = Field(..., description="Stable unique id for an agent.")
    agent_name: str = Field(..., description="Human readable agent name.")
    provider: str = Field(..., description="Provider (OpenAI, Anthropic, etc.).")
    model: str = Field(..., description="Model name.")
    usd_cost: float = Field(..., ge=0, description="Total run cost in USD.")
    recursion_depth: int = Field(..., ge=0, description="Observed recursive depth for the run.")
    latency_ms: int = Field(..., ge=0, description="End-to-end run latency in milliseconds.")
    success: bool = Field(..., description="Whether the run returned a successful output.")
    timestamp: Optional[datetime] = Field(None, description="UTC timestamp of the run.")


class RankRequest(BaseModel):
    runs: List[AgentRunInput] = Field(..., min_length=1)
    top_k: Optional[int] = Field(10, ge=1, le=100)
    cost_weight: float = Field(0.65, ge=0, le=1)
    recursion_weight: float = Field(0.2, ge=0, le=1)
    reliability_weight: float = Field(0.15, ge=0, le=1)

    @field_validator("reliability_weight")
    @classmethod
    def validate_weights_sum(cls, _value: float, info):
        data = info.data
        c = data.get("cost_weight", 0)
        r = data.get("recursion_weight", 0)
        rr = data.get("reliability_weight", _value)
        total = c + r + rr
        if abs(total - 1.0) > 1e-6:
            raise ValueError("cost_weight + recursion_weight + reliability_weight must equal 1.0")
        return _value


class BrowserPluginConfig(BaseModel):
    plugin_name: str
    extension_type: str
    manifest_version: int
    ingest_endpoint: str
    sample_payload: Dict[str, object]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "time": now_utc().isoformat()}


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


@app.post("/agents/rank")
def rank_agents(req: RankRequest) -> Dict[str, object]:
    runs = [
        AgentRun(
            agent_id=x.agent_id,
            agent_name=x.agent_name,
            provider=x.provider,
            model=x.model,
            usd_cost=x.usd_cost,
            recursion_depth=x.recursion_depth,
            latency_ms=x.latency_ms,
            success=x.success,
            timestamp=x.timestamp or now_utc(),
        )
        for x in req.runs
    ]

    ranked = rank_agents_by_cost(
        runs=runs,
        cost_weight=req.cost_weight,
        recursion_weight=req.recursion_weight,
        reliability_weight=req.reliability_weight,
        top_k=req.top_k,
    )

    return {
        "count": len(ranked),
        "rankings": [x.__dict__ for x in ranked],
        "weights": {
            "cost_weight": req.cost_weight,
            "recursion_weight": req.recursion_weight,
            "reliability_weight": req.reliability_weight,
        },
    }


@app.get("/plugins/config", response_model=List[BrowserPluginConfig])
def plugin_config() -> List[BrowserPluginConfig]:
    sample_payload = {
        "agent_id": "agent.alpha",
        "agent_name": "Alpha Planner",
        "provider": "OpenAI",
        "model": "gpt-5.3-mini",
        "usd_cost": 0.021,
        "recursion_depth": 4,
        "latency_ms": 1240,
        "success": True,
        "timestamp": now_utc().isoformat(),
    }
    return [
        BrowserPluginConfig(
            plugin_name="Recursive Agent Cost Tracker (Chrome)",
            extension_type="chrome",
            manifest_version=3,
            ingest_endpoint="/agents/rank",
            sample_payload=sample_payload,
        ),
        BrowserPluginConfig(
            plugin_name="Recursive Agent Cost Tracker (Firefox)",
            extension_type="firefox",
            manifest_version=2,
            ingest_endpoint="/agents/rank",
            sample_payload=sample_payload,
        ),
    ]
