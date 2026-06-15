"""
PipelineRunner — orchestrates the 5-agent pipeline across N sessions.

After each session, collects:
  - contamination cluster size
  - detection rate (from VerificationAgent)
  - entries written

These per-session metrics give us the two key paper curves:
  1. Detectability decay curve (detection_rate vs session)
  2. Cluster growth rate curve (cluster_size vs session)
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from pipeline.memory import MemoryStore
from pipeline.tools import ToolRegistry
from pipeline.injector import HallucinationInjector
from pipeline.agents import (
    DataIntakeAgent,
    AnalysisAgent,
    SynthesisAgent,
    VerificationAgent,
    ReportingAgent,
    AgentOutput,
)


@dataclass
class SessionConfig:
    session_id: int
    filing_text: str    # actual text from FinanceBench evidence field
    company: str
    doc_name: str


@dataclass
class SessionResult:
    session_id: int
    cluster_size: int
    detection_rate: float
    entries_written: int
    contaminated_entries: int
    verification: dict
    agent_outputs: list = field(default_factory=list)


class PipelineRunner:
    def __init__(
        self,
        ground_truth: dict,
        tools: ToolRegistry,
        injector: Optional[HallucinationInjector] = None,
        experiment_name: str = "experiment",
        point_of_no_return_threshold: float = 0.20,
    ):
        self.ground_truth = ground_truth
        self.tools = tools
        self.injector = injector
        self.experiment_name = experiment_name
        self.ponr_threshold = point_of_no_return_threshold

        self.memory = MemoryStore()
        self.results: list[SessionResult] = []

        self.intake = DataIntakeAgent()
        self.analysis = AnalysisAgent()
        self.synthesis = SynthesisAgent()
        self.verification = VerificationAgent()
        self.reporting = ReportingAgent()

    def run_session(self, cfg: SessionConfig) -> SessionResult:
        sid = cfg.session_id
        sep = "=" * 60
        print(f"\n{sep}\nSESSION {sid} | {self.experiment_name} | {cfg.company} | {cfg.doc_name}\n{sep}")

        entries_before = len(self.memory)

        # --- Agent 1: Data Intake ---
        print("  [1/5] DataIntakeAgent...")
        intake_out = self.intake.run(
            session_id=sid,
            filing_text=cfg.filing_text,
            company=cfg.company,
            doc_name=cfg.doc_name,
            memory=self.memory,
            tools=self.tools,
            injector=self.injector,
        )
        print(f"        {len(intake_out.memory_writes)} entries written")

        # --- Agent 2: Analysis ---
        print("  [2/5] AnalysisAgent...")
        analysis_out = self.analysis.run(
            session_id=sid,
            company=cfg.company,
            doc_name=cfg.doc_name,
            memory=self.memory,
        )
        print(f"        {len(analysis_out.memory_writes)} entries written")

        # --- Agent 3: Synthesis (session >= 2) ---
        if sid >= 2:
            print("  [3/5] SynthesisAgent...")
            synthesis_out = self.synthesis.run(
                session_id=sid,
                company=cfg.company,
                memory=self.memory,
            )
            print(f"        {len(synthesis_out.memory_writes)} entries written")
        else:
            synthesis_out = None
            print("  [3/5] SynthesisAgent skipped (need >= 2 sessions)")

        # --- Agent 4: Verification ---
        print("  [4/5] VerificationAgent...")
        verif = self.verification.run(
            session_id=sid,
            memory=self.memory,
            ground_truth=self.ground_truth,
        )
        dr = verif["detection_rate"]
        print(f"        detection rate: {dr:.1%} ({verif['true_positives']}/{verif['contaminated_entries']} caught)")

        # --- Agent 5: Reporting ---
        print("  [5/5] ReportingAgent...")
        report_out = self.reporting.run(
            session_id=sid,
            company=cfg.company,
            memory=self.memory,
        )
        print(f"        {len(report_out.memory_writes)} entries written")

        # collect metrics
        cluster_size = self.memory.contamination_cluster_size(sid)
        entries_written = len(self.memory) - entries_before

        result = SessionResult(
            session_id=sid,
            cluster_size=cluster_size,
            detection_rate=dr,
            entries_written=entries_written,
            contaminated_entries=verif["contaminated_entries"],
            verification=verif,
            agent_outputs=[intake_out, analysis_out, synthesis_out, report_out],
        )
        self.results.append(result)

        print(f"\n  METRICS | cluster_size={cluster_size} | detection_rate={dr:.1%} | total_entries={len(self.memory)}")
        return result

    def run(self, sessions: list[SessionConfig]) -> list[SessionResult]:
        for cfg in sessions:
            self.run_session(cfg)
        return self.results

    def find_point_of_no_return(self) -> Optional[int]:
        """First session where detection_rate <= threshold with contamination present."""
        for r in self.results:
            if r.contaminated_entries > 0 and r.detection_rate <= self.ponr_threshold:
                return r.session_id
        return None

    def get_metrics(self) -> dict:
        return {
            "experiment": self.experiment_name,
            "total_sessions": len(self.results),
            "detectability_decay": [
                {"session": r.session_id, "detection_rate": r.detection_rate}
                for r in self.results
            ],
            "cluster_growth": [
                {"session": r.session_id, "cluster_size": r.cluster_size}
                for r in self.results
            ],
            "point_of_no_return": self.find_point_of_no_return(),
            "injector": self.injector.summary() if self.injector else None,
        }

    def save(self, output_dir: str = "results") -> dict:
        os.makedirs(output_dir, exist_ok=True)
        name = self.experiment_name.replace(" ", "_")

        metrics = self.get_metrics()
        with open(f"{output_dir}/{name}_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

        self.memory.save(f"{output_dir}/{name}_memory.json")

        print(f"\nResults saved to {output_dir}/{name}_*.json")
        return metrics
