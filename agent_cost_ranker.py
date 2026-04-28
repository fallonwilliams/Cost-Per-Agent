from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional


@dataclass
class AgentRun:
    agent_id: str
    agent_name: str
    provider: str
    model: str
    usd_cost: float
    recursion_depth: int
    latency_ms: int
    success: bool
    timestamp: datetime


@dataclass
class AgentRanking:
    agent_id: str
    agent_name: str
    provider: str
    model: str
    run_count: int
    total_cost_usd: float
    avg_cost_usd: float
    avg_recursion_depth: float
    p95_latency_ms: int
    failure_rate: float
    weighted_score: float


def _percentile(sorted_values: List[int], p: float) -> int:
    if not sorted_values:
        return 0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = int(round((len(sorted_values) - 1) * p))
    idx = max(0, min(len(sorted_values) - 1, idx))
    return sorted_values[idx]


def rank_agents_by_cost(
    runs: Iterable[AgentRun],
    cost_weight: float = 0.65,
    recursion_weight: float = 0.2,
    reliability_weight: float = 0.15,
    top_k: Optional[int] = None,
) -> List[AgentRanking]:
    grouped: Dict[str, List[AgentRun]] = defaultdict(list)
    for run in runs:
        grouped[run.agent_id].append(run)

    rankings: List[AgentRanking] = []
    for agent_id, entries in grouped.items():
        run_count = len(entries)
        total_cost = sum(x.usd_cost for x in entries)
        avg_cost = total_cost / run_count if run_count else 0
        avg_depth = sum(x.recursion_depth for x in entries) / run_count if run_count else 0
        latencies = sorted(x.latency_ms for x in entries)
        p95_latency = _percentile(latencies, 0.95)
        failures = sum(1 for x in entries if not x.success)
        failure_rate = failures / run_count if run_count else 0

        # Lower score is better. Cost dominates; recursion and reliability are penalties.
        weighted_score = (
            (avg_cost * cost_weight)
            + (avg_depth * recursion_weight)
            + (failure_rate * 10 * reliability_weight)
        )

        first = entries[0]
        rankings.append(
            AgentRanking(
                agent_id=agent_id,
                agent_name=first.agent_name,
                provider=first.provider,
                model=first.model,
                run_count=run_count,
                total_cost_usd=round(total_cost, 6),
                avg_cost_usd=round(avg_cost, 6),
                avg_recursion_depth=round(avg_depth, 3),
                p95_latency_ms=p95_latency,
                failure_rate=round(failure_rate, 4),
                weighted_score=round(weighted_score, 6),
            )
        )

    rankings.sort(key=lambda r: (r.weighted_score, r.avg_cost_usd, r.failure_rate, r.p95_latency_ms))
    if top_k is not None and top_k > 0:
        return rankings[:top_k]
    return rankings


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
