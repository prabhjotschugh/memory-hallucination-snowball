"""
MemoryStore — flat key-value episodic memory with session tagging and lineage tracking.

Every entry written to memory is tagged with:
- session_id      : which session wrote it
- parent_ids      : which prior memory entry_ids were in context when this was written
                    (this is how we build the contamination family tree automatically)
- is_contaminated : ground truth label
- generation      : hops from root hallucination (0=injected/tool-fail, 1=child, 2=grandchild)
- source          : "agent" | "tool" | "injected"

No summarization. No compression. Raw entries only.
This gives us full observability for lineage tracking.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class MemoryEntry:
    key: str
    value: str
    session_id: int
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_ids: list[str] = field(default_factory=list)
    is_contaminated: bool = False
    generation: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "agent"  # "agent" | "tool" | "injected"

    def to_context_string(self) -> str:
        return f"[Session {self.session_id}] {self.key}: {self.value}"


class MemoryStore:
    def __init__(self):
        self.entries: list[MemoryEntry] = []
        self._contamination_roots: list[str] = []

    def write(
        self,
        key: str,
        value: str,
        session_id: int,
        parent_ids: list[str] = None,
        source: str = "agent",
        force_contaminated: bool = False,
        force_generation: int = None,
    ) -> MemoryEntry:
        parent_ids = parent_ids or []

        # infer contamination from parents automatically
        is_contaminated = force_contaminated
        generation = 0

        if not force_contaminated and parent_ids:
            parent_entries = [e for e in self.entries if e.entry_id in parent_ids]
            contaminated_parents = [e for e in parent_entries if e.is_contaminated]
            if contaminated_parents:
                is_contaminated = True
                generation = max(e.generation for e in contaminated_parents) + 1

        if force_generation is not None:
            generation = force_generation

        entry = MemoryEntry(
            key=key,
            value=value,
            session_id=session_id,
            parent_ids=parent_ids,
            is_contaminated=is_contaminated,
            generation=generation,
            source=source,
        )
        self.entries.append(entry)

        if force_contaminated and generation == 0:
            self._contamination_roots.append(entry.entry_id)

        return entry

    def read_prior_to_session(self, session_id: int) -> list[MemoryEntry]:
        """All entries from sessions before session_id."""
        return [e for e in self.entries if e.session_id < session_id]

    def read_up_to_session(self, session_id: int) -> list[MemoryEntry]:
        """All entries from sessions up to and including session_id."""
        return [e for e in self.entries if e.session_id <= session_id]

    def to_context_string(self, session_id: int) -> str:
        """Format prior memory as context string for agent prompt."""
        prior = self.read_prior_to_session(session_id)
        if not prior:
            return "No prior memory."
        return "\n".join(e.to_context_string() for e in prior)

    def get_context_entry_ids(self, session_id: int) -> list[str]:
        """entry_ids that are in context going into session_id."""
        return [e.entry_id for e in self.read_prior_to_session(session_id)]

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    def contamination_cluster_size(self, after_session: int) -> int:
        return sum(
            1 for e in self.entries
            if e.is_contaminated and e.session_id <= after_session
        )

    def cluster_by_generation(self, after_session: int) -> dict[int, int]:
        result: dict[int, int] = {}
        for e in self.entries:
            if e.is_contaminated and e.session_id <= after_session:
                result[e.generation] = result.get(e.generation, 0) + 1
        return result

    def get_lineage_graph(self) -> dict[str, list[str]]:
        """Maps each contaminated entry_id to its children."""
        children: dict[str, list[str]] = {}
        for entry in self.entries:
            if entry.is_contaminated:
                for pid in entry.parent_ids:
                    children.setdefault(pid, []).append(entry.entry_id)
        return children

    def export(self) -> list[dict]:
        return [asdict(e) for e in self.entries]

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.export(), f, indent=2)

    def __len__(self):
        return len(self.entries)

    def __repr__(self):
        total = len(self.entries)
        contaminated = sum(1 for e in self.entries if e.is_contaminated)
        return f"MemoryStore({total} entries, {contaminated} contaminated)"
