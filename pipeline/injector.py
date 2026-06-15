"""
HallucinationInjector — Source 1 of hallucinations.

Intercepts memory writes during a specific session and corrupts target entries.
The runner calls check_and_inject() before every memory write.

Severity levels:
  subtle   — 5-10% deviation from true value (hard to catch)
  moderate — 15-20% deviation
  high     — 25-35% deviation (easy to catch early, good for establishing baseline)

Usage:
    injector = HallucinationInjector()
    injector.add_injection(
        session_id=1,
        key="3M_2022_10K_revenue",
        corrupted_value="27383",   # true: 34229
        true_value="34229",
        severity="high",
    )
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InjectionSpec:
    session_id: int
    key: str
    corrupted_value: str
    true_value: str
    severity: str   # "subtle" | "moderate" | "high"
    applied: bool = False


class HallucinationInjector:
    def __init__(self):
        self.injections: list[InjectionSpec] = []
        self.log: list[dict] = []

    def add_injection(
        self,
        session_id: int,
        key: str,
        corrupted_value: str,
        true_value: str,
        severity: str = "moderate",
    ):
        self.injections.append(InjectionSpec(
            session_id=session_id,
            key=key,
            corrupted_value=corrupted_value,
            true_value=true_value,
            severity=severity,
        ))

    def check_and_inject(
        self,
        session_id: int,
        key: str,
        value: str,
    ) -> tuple[str, bool, Optional[InjectionSpec]]:
        """
        Returns (final_value, was_injected, spec).
        Called before every memory write in runner.
        """
        for spec in self.injections:
            if spec.session_id == session_id and spec.key == key and not spec.applied:
                spec.applied = True
                self.log.append({
                    "session_id": session_id,
                    "key": key,
                    "true_value": spec.true_value,
                    "injected_value": spec.corrupted_value,
                    "severity": spec.severity,
                })
                return spec.corrupted_value, True, spec
        return value, False, None

    def summary(self) -> dict:
        return {
            "planned": len(self.injections),
            "applied": sum(1 for s in self.injections if s.applied),
            "log": self.log,
        }
