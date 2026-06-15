"""
5-Agent Pipeline using Google Gemini API.

Agent 1 — DataIntakeAgent   : reads raw filing text + calls tools, writes raw facts
Agent 2 — AnalysisAgent     : derives metrics/insights from current memory
Agent 3 — SynthesisAgent    : cross-session trend analysis (session >= 2)
Agent 4 — VerificationAgent : imperfect fact-checker (generates detectability decay)
Agent 5 — ReportingAgent    : final session output

Agents output memory writes as:
    MEMORY_WRITE | key | value

Agents request tool calls as:
    TOOL_CALL | tool_name | metric_key
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from google import genai
from google.genai import types

from pipeline.memory import MemoryStore
from pipeline.tools import ToolRegistry, ToolResult
from pipeline.injector import HallucinationInjector
from dotenv import load_dotenv

load_dotenv()

_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


@dataclass
class AgentOutput:
    agent_name: str
    session_id: int
    raw_response: str
    memory_writes: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)


def _llm(system: str, user: str) -> str:
    """Single Gemini API call. Returns text response."""
    response = _client.models.generate_content(
        model=MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.1,      # low temp for consistent, factual outputs
            max_output_tokens=1200,
        ),
    )
    return response.text


def _parse_writes(text: str) -> list[dict]:
    writes = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("MEMORY_WRITE"):
            parts = line.split("|")
            if len(parts) >= 3:
                writes.append({
                    "key": parts[1].strip(),
                    "value": "|".join(parts[2:]).strip(),
                })
    return writes


def _parse_tool_calls(text: str) -> list[dict]:
    calls = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("TOOL_CALL"):
            parts = line.split("|")
            if len(parts) >= 3:
                calls.append({
                    "tool": parts[1].strip(),
                    "key": parts[2].strip(),
                })
    return calls


# =============================================================================
# Agent 1: DataIntakeAgent
# =============================================================================

class DataIntakeAgent:
    """
    Reads raw filing text and optional tool outputs.
    Writes raw facts to memory.
    First entry point for both injection and tool-based hallucinations.
    """
    name = "DataIntakeAgent"

    SYSTEM = """You are a data intake agent for financial document analysis.

Your job: read the provided financial filing text carefully and extract ALL key facts and figures.

For every important fact, output a memory write on its own line:
MEMORY_WRITE | descriptive_key | value

Key naming convention: {company}_{doc_period}_{doc_type}_{metric}
Example: MEMORY_WRITE | 3M_2022_10K_revenue | $34,229 million

If you need to look up a specific metric from the financial data tool:
TOOL_CALL | financial_data | metric_key

Rules:
- Extract numbers precisely as written in the document
- Do not estimate or infer — only record what is explicitly stated
- Use clear, consistent key names
- Prioritize: revenue, net income, gross margin, EPS, operating income, cash flows"""

    def run(
        self,
        session_id: int,
        filing_text: str,
        company: str,
        doc_name: str,
        memory: MemoryStore,
        tools: ToolRegistry,
        injector: Optional[HallucinationInjector] = None,
    ) -> AgentOutput:

        prior = memory.to_context_string(session_id)
        user = f"""Company: {company}
Document: {doc_name}
Session: {session_id}

=== PRIOR MEMORY ===
{prior}

=== NEW FILING TEXT ===
{filing_text}

Extract all key financial facts and write them to memory."""

        response = _llm(self.SYSTEM, user)
        tool_reqs = _parse_tool_calls(response)
        tool_results: list[ToolResult] = []

        for tc in tool_reqs:
            tool = tools.get(tc["tool"])
            if tool and hasattr(tool, "query"):
                result = tool.query(tc["key"])
                tool_results.append(result)
                if result.success or result.is_hallucinated:
                    response += f"\nMEMORY_WRITE | tool_result_{tc['key']} | {result.result}"

        writes = _parse_writes(response)
        written = []
        parent_ids = memory.get_context_entry_ids(session_id)

        for w in writes:
            final_val, was_injected, spec = (
                injector.check_and_inject(session_id, w["key"], w["value"])
                if injector else (w["value"], False, None)
            )

            tool_hallucinated = any(
                r.is_hallucinated and tc["key"] in w["key"]
                for r, tc in zip(tool_results, tool_reqs)
            ) if tool_results else False

            entry = memory.write(
                key=w["key"],
                value=final_val,
                session_id=session_id,
                parent_ids=parent_ids,
                source="injected" if was_injected else ("tool" if tool_hallucinated else "agent"),
                force_contaminated=was_injected or tool_hallucinated,
                force_generation=0 if (was_injected or tool_hallucinated) else None,
            )
            written.append({"key": w["key"], "value": final_val, "entry_id": entry.entry_id})

        return AgentOutput(
            agent_name=self.name,
            session_id=session_id,
            raw_response=response,
            memory_writes=written,
            tool_calls=[{"tool": tc["tool"], "key": tc["key"]} for tc in tool_reqs],
        )


# =============================================================================
# Agent 2: AnalysisAgent
# =============================================================================

class AnalysisAgent:
    """
    Reads current session memory and derives analytical insights.
    Primary site of generation-1 contamination: if intake wrote a wrong number,
    this agent calculates growth rates, ratios, and margins using that number.
    """
    name = "AnalysisAgent"

    SYSTEM = """You are a financial analysis agent.

Your job: analyze the financial data in memory and produce derived insights.

For each derived metric or insight, output:
MEMORY_WRITE | descriptive_key | value

Examples of derived metrics to compute:
- Year-over-year revenue growth rate
- Gross margin percentage
- Operating margin
- EPS trend
- Any notable changes vs prior periods

Base all calculations strictly on what is in memory. Show your reasoning inline.
Do not invent data not present in memory."""

    def run(
        self,
        session_id: int,
        company: str,
        doc_name: str,
        memory: MemoryStore,
    ) -> AgentOutput:

        all_mem = memory.to_context_string(session_id + 1)
        user = f"""Company: {company}
Document: {doc_name}
Session: {session_id}

=== ALL MEMORY (including current session) ===
{all_mem}

Analyze the data and derive key financial metrics. Write findings to memory."""

        response = _llm(self.SYSTEM, user)
        writes = _parse_writes(response)
        parent_ids = [e.entry_id for e in memory.read_up_to_session(session_id)]
        written = []

        for w in writes:
            entry = memory.write(
                key=w["key"],
                value=w["value"],
                session_id=session_id,
                parent_ids=parent_ids,
                source="agent",
            )
            written.append({"key": w["key"], "value": w["value"], "entry_id": entry.entry_id})

        return AgentOutput(
            agent_name=self.name,
            session_id=session_id,
            raw_response=response,
            memory_writes=written,
        )


# =============================================================================
# Agent 3: SynthesisAgent
# =============================================================================

class SynthesisAgent:
    """
    Cross-session synthesis. Only runs from session 2 onwards.
    This is where contamination clusters become structurally embedded:
    narratives, trends, and projections referencing the full (potentially
    contaminated) memory across all sessions.
    """
    name = "SynthesisAgent"

    SYSTEM = """You are a synthesis agent for multi-session financial analysis.

Your job: identify trends, patterns, and trajectories across ALL sessions in memory.

For each cross-session finding, output:
MEMORY_WRITE | synthesis_key | finding

Focus on:
- Multi-period revenue/income trends
- Margin trajectory
- Forward projections based on observed trends
- Notable changes or turning points

Be explicit about which sessions you are drawing from."""

    def run(
        self,
        session_id: int,
        company: str,
        memory: MemoryStore,
    ) -> AgentOutput:

        all_mem = "\n".join(e.to_context_string() for e in memory.entries)
        user = f"""Company: {company}
Current Session: {session_id}

=== FULL MEMORY ACROSS ALL SESSIONS ===
{all_mem}

Synthesize cross-session patterns and write findings to memory."""

        response = _llm(self.SYSTEM, user)
        writes = _parse_writes(response)
        parent_ids = [e.entry_id for e in memory.entries]
        written = []

        for w in writes:
            entry = memory.write(
                key=w["key"],
                value=w["value"],
                session_id=session_id,
                parent_ids=parent_ids,
                source="agent",
            )
            written.append({"key": w["key"], "value": w["value"], "entry_id": entry.entry_id})

        return AgentOutput(
            agent_name=self.name,
            session_id=session_id,
            raw_response=response,
            memory_writes=written,
        )


# =============================================================================
# Agent 4: VerificationAgent
# =============================================================================

class VerificationAgent:
    """
    Fact-checks memory entries against ground truth.
    Intentionally imperfect — gets fooled by corroboration clusters.
    This generates the detectability decay curve.
    """
    name = "VerificationAgent"

    SYSTEM = """You are a financial fact-checking agent.

You will be given:
1. All current memory entries (key: value pairs)
2. Ground truth values

For each memory entry, determine if it is CORRECT or INCORRECT.

Output ONLY a JSON array, no other text:
[
  {"key": "...", "verdict": "CORRECT", "reason": "..."},
  {"key": "...", "verdict": "INCORRECT", "reason": "..."}
]

Rules:
- If a derived metric (growth rate, ratio) is based on a wrong base figure, mark it INCORRECT
- If you cannot verify a qualitative entry, mark it CORRECT
- Be strict with numerical entries"""

    def run(
        self,
        session_id: int,
        memory: MemoryStore,
        ground_truth: dict,
    ) -> dict:
        if not memory.entries:
            return {
                "session_id": session_id,
                "entries_checked": 0,
                "contaminated_entries": 0,
                "true_positives": 0,
                "false_negatives": 0,
                "detection_rate": 1.0,
                "flags": [],
            }

        entries_text = "\n".join(f"{e.key}: {e.value}" for e in memory.entries)
        gt_text = json.dumps(ground_truth, indent=2)

        user = f"""Memory entries:
{entries_text}

Ground truth:
{gt_text}

Check each entry and output your JSON verdict array."""

        response = _llm(self.SYSTEM, user)

        try:
            clean = re.sub(r"```json|```", "", response).strip()
            verdicts = json.loads(clean)
        except Exception:
            verdicts = []

        contaminated = [e for e in memory.entries if e.is_contaminated]
        flagged_keys = {v["key"] for v in verdicts if v.get("verdict") == "INCORRECT"}

        true_positives = sum(1 for e in contaminated if e.key in flagged_keys)
        false_negatives = len(contaminated) - true_positives
        detection_rate = true_positives / len(contaminated) if contaminated else 1.0

        return {
            "session_id": session_id,
            "entries_checked": len(memory.entries),
            "contaminated_entries": len(contaminated),
            "true_positives": true_positives,
            "false_negatives": false_negatives,
            "detection_rate": round(detection_rate, 4),
            "flags": [v for v in verdicts if v.get("verdict") == "INCORRECT"],
        }


# =============================================================================
# Agent 5: ReportingAgent
# =============================================================================

class ReportingAgent:
    """
    Produces the final output for a session.
    Output quality degrades as memory becomes more contaminated.
    The report itself is written back to memory, joining the corroboration cluster.
    """
    name = "ReportingAgent"

    SYSTEM = """You are a financial reporting agent.

Produce a concise, structured investment summary for this session.

Write your final summary to memory using EXACTLY this format:
MEMORY_WRITE | session_N_report | <your summary here>
(replace N with the session number)

The summary should include:
- Key financial metrics for this period
- Trends vs prior periods
- Investment recommendation (Buy/Hold/Sell) with brief rationale"""

    def run(
        self,
        session_id: int,
        company: str,
        memory: MemoryStore,
    ) -> AgentOutput:

        all_mem = "\n".join(e.to_context_string() for e in memory.entries)

        user = f"""Company: {company}
Session: {session_id}

=== FULL MEMORY ===
{all_mem}

Produce your session {session_id} investment summary."""

        response = _llm(self.SYSTEM, user)
        writes = _parse_writes(response)
        parent_ids = [e.entry_id for e in memory.entries]
        written = []

        for w in writes:
            entry = memory.write(
                key=w["key"],
                value=w["value"],
                session_id=session_id,
                parent_ids=parent_ids,
                source="agent",
            )
            written.append({"key": w["key"], "value": w["value"], "entry_id": entry.entry_id})

        return AgentOutput(
            agent_name=self.name,
            session_id=session_id,
            raw_response=response,
            memory_writes=written,
        )
