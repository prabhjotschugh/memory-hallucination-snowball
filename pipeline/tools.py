"""
Tools available to agents during a session.

Two hallucination sources in this framework:
  Source 1 — Injected hallucinations (injector.py intercepts memory writes)
  Source 2 — Tool calling failures (this file — tools return wrong data)

Tool failure modes:
  NONE          — tool works correctly (baseline)
  WRONG_VALUE   — tool returns plausible but numerically incorrect value
  STALE_DATA    — tool returns data from a prior period as if current
  PARTIAL       — tool returns incomplete data, agent must estimate (confabulation)
  TIMEOUT       — tool times out, agent gets no data and may hallucinate a fill-in
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class FailureMode(Enum):
    NONE = "none"
    WRONG_VALUE = "wrong_value"
    STALE_DATA = "stale_data"
    PARTIAL = "partial"
    TIMEOUT = "timeout"


@dataclass
class ToolResult:
    tool_name: str
    query: str
    result: Any
    success: bool
    failure_mode: FailureMode = FailureMode.NONE
    is_hallucinated: bool = False  # ground truth: did this tool lie?


class FinancialDataTool:
    """
    Simulates a financial data API.
    Ground truth comes from FinanceBench answers loaded at experiment time.
    Failure modes corrupt the output in controlled ways.

    ground_truth format:
        { "metric_key": value_or_string, ... }
    e.g. { "3M_2022_10K_revenue": "34229", "3M_2022_10K_net_income": "5777" }
    """

    def __init__(
        self,
        ground_truth: dict[str, Any],
        failure_mode: FailureMode = FailureMode.NONE,
        failure_rate: float = 0.0,
    ):
        self.ground_truth = ground_truth
        self.failure_mode = failure_mode
        self.failure_rate = failure_rate

    def _should_fail(self) -> bool:
        if self.failure_mode == FailureMode.NONE:
            return False
        if self.failure_rate >= 1.0:
            return True
        return random.random() < self.failure_rate

    def query(self, metric_key: str) -> ToolResult:
        true_value = self.ground_truth.get(metric_key)

        if true_value is None:
            return ToolResult(
                tool_name="financial_data",
                query=metric_key,
                result=f"No data found for {metric_key}",
                success=False,
            )

        if not self._should_fail():
            return ToolResult(
                tool_name="financial_data",
                query=metric_key,
                result=true_value,
                success=True,
            )

        # apply failure mode
        if self.failure_mode == FailureMode.WRONG_VALUE:
            try:
                numeric = float(str(true_value).replace(",", "").replace("$", "").replace("%", ""))
                direction = random.choice([-1, 1])
                magnitude = random.uniform(0.15, 0.30)
                corrupted = round(numeric * (1 + direction * magnitude), 2)
                return ToolResult(
                    tool_name="financial_data",
                    query=metric_key,
                    result=str(corrupted),
                    success=True,
                    failure_mode=FailureMode.WRONG_VALUE,
                    is_hallucinated=True,
                )
            except ValueError:
                # non-numeric — corrupt by appending wrong qualifier
                return ToolResult(
                    tool_name="financial_data",
                    query=metric_key,
                    result=f"{true_value} (adjusted)",
                    success=True,
                    failure_mode=FailureMode.WRONG_VALUE,
                    is_hallucinated=True,
                )

        elif self.failure_mode == FailureMode.STALE_DATA:
            # try to find a prior period entry
            parts = metric_key.rsplit("_", 1)
            stale_key = metric_key + "_prior"
            stale_value = self.ground_truth.get(stale_key, true_value)
            return ToolResult(
                tool_name="financial_data",
                query=metric_key,
                result=stale_value,
                success=True,
                failure_mode=FailureMode.STALE_DATA,
                is_hallucinated=stale_value != true_value,
            )

        elif self.failure_mode == FailureMode.PARTIAL:
            return ToolResult(
                tool_name="financial_data",
                query=metric_key,
                result="[DATA UNAVAILABLE — please estimate from context]",
                success=False,
                failure_mode=FailureMode.PARTIAL,
                is_hallucinated=False,
            )

        elif self.failure_mode == FailureMode.TIMEOUT:
            return ToolResult(
                tool_name="financial_data",
                query=metric_key,
                result="[TIMEOUT — connection lost]",
                success=False,
                failure_mode=FailureMode.TIMEOUT,
                is_hallucinated=False,
            )

        return ToolResult(
            tool_name="financial_data",
            query=metric_key,
            result=true_value,
            success=True,
        )


class ToolRegistry:
    """Registry of tools available to agents in a session."""

    def __init__(self):
        self._tools: dict[str, Any] = {}

    def register(self, name: str, tool: Any):
        self._tools[name] = tool

    def get(self, name: str) -> Optional[Any]:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def describe(self) -> str:
        return "Available tools: " + ", ".join(self.list_tools())
