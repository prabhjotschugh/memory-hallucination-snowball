import uuid
from typing import Dict, Any, Tuple
from memory import MemoryStore, MemoryEntry, StateTag, VerificationStatus
from checker import check_numeric_contamination

class MemoryCurator:
    """
    The Memory-Curator acts as the write-time contamination gate.
    It takes the outputs from the pipeline, checks them against ground truth,
    and saves them to the MemoryStore with proper lineage.
    """
    def __init__(self, store: MemoryStore):
        self.store = store

    def commit_pipeline_run(
        self, 
        session_id: int, 
        raw_fact: str, 
        derived_insight: str, 
        final_narrative: str, 
        ground_truth: float,
        injection_metadata: Dict[str, Any] = None,
        prior_memories: list = None
    ) -> Tuple[MemoryEntry, MemoryEntry, MemoryEntry]:
        """
        Commits the 3 stages of the pipeline to memory, running the contamination gate on each.
        Returns the 3 created memory entries.
        """
        # 1. Curator Check & Commit: RAW FACT
        is_raw_contam = check_numeric_contamination(raw_fact, ground_truth)
        raw_status = VerificationStatus.FLAGGED_CONTAMINATED if is_raw_contam else VerificationStatus.VERIFIED
        
        entry_raw = MemoryEntry(
            entry_id=str(uuid.uuid4()),
            session_id=session_id,
            agent_source="Researcher",
            content=raw_fact,
            state_tag=StateTag.RAW_FACT,
            parent_ids=[],
            ground_truth_checkable=True,
            is_contaminated=is_raw_contam,
            verification_status=raw_status,
            injection_metadata=injection_metadata
        )
        self.store.write(entry_raw)

        # 2. Curator Check & Commit: DERIVED
        # If the analyst derives a metric (like 6.25% growth), it no longer matches the $85B ground truth directly.
        # So we MUST separate Tier A checkability from structural contamination.
        
        # Determine if the derived metric STILL contains the ground truth (usually False)
        matches_gt_derived = not check_numeric_contamination(derived_insight, ground_truth)
        
        # A derived metric is contaminated if its parent was contaminated (the snowball effect).
        # It also inherits contamination from any prior historical memories it used.
        is_prior_contam = any(m.is_contaminated for m in prior_memories) if prior_memories else False
        is_derived_contam = is_raw_contam or is_prior_contam
        
        derived_status = VerificationStatus.FLAGGED_CONTAMINATED if is_derived_contam else (VerificationStatus.VERIFIED if matches_gt_derived else VerificationStatus.UNVERIFIED)
        
        derived_parent_ids = [entry_raw.entry_id]
        if prior_memories:
            derived_parent_ids.extend([m.entry_id for m in prior_memories])

        entry_derived = MemoryEntry(
            entry_id=str(uuid.uuid4()),
            session_id=session_id,
            agent_source="Analyst",
            content=derived_insight,
            state_tag=StateTag.DERIVED,
            parent_ids=derived_parent_ids,
            ground_truth_checkable=matches_gt_derived,
            is_contaminated=is_derived_contam,
            verification_status=derived_status,
            injection_metadata=injection_metadata
        )
        self.store.write(entry_derived)

        # 3. Curator Check & Commit: NARRATIVE
        matches_gt_narrative = not check_numeric_contamination(final_narrative, ground_truth)
        
        # Narrative is contaminated if it was built on contaminated derived insight
        is_narrative_contam = is_derived_contam
        
        narrative_status = VerificationStatus.FLAGGED_CONTAMINATED if is_narrative_contam else (VerificationStatus.VERIFIED if matches_gt_narrative else VerificationStatus.UNVERIFIED)
        
        entry_narrative = MemoryEntry(
            entry_id=str(uuid.uuid4()),
            session_id=session_id,
            agent_source="Writer/Reviewer",
            content=final_narrative,
            state_tag=StateTag.NARRATIVE,
            parent_ids=[entry_derived.entry_id],
            ground_truth_checkable=matches_gt_narrative,
            is_contaminated=is_narrative_contam, 
            verification_status=narrative_status,
            injection_metadata=injection_metadata
        )
        self.store.write(entry_narrative)

        return entry_raw, entry_derived, entry_narrative

class Pipeline:
    """
    Orchestrates the 5-agent sequential handoff for a single session.
    """
    def __init__(self, researcher, analyst, writer, reviewer, curator: MemoryCurator):
        self.researcher = researcher
        self.analyst = analyst
        self.writer = writer
        self.reviewer = reviewer
        self.curator = curator

    def run(
        self, 
        session_id: int, 
        source_text: str, 
        question: str, 
        analyst_context: str, 
        ground_truth: float,
        injected_researcher_override: str = None
    ) -> Tuple[MemoryEntry, MemoryEntry, MemoryEntry]:
        
        # Pull Historical Memory
        prior_memories = self.curator.store.retrieve_memory(session_id)
        memory_context = "\n".join([f"- {m.content}" for m in prior_memories]) if prior_memories else ""
        
        # 1. Researcher Stage
        raw_fact = self.researcher.extract_figure(source_text, question, memory_context)
        
        # [INJECTION POINT for experimental control]
        if injected_researcher_override is not None:
            raw_fact = injected_researcher_override
            injection_meta = {"type": "manual_override", "original": raw_fact, "injected": injected_researcher_override, "session": session_id}
        else:
            injection_meta = None

        # 2. Analyst Stage
        derived_insight = self.analyst.derive_insight(raw_fact, analyst_context, memory_context)

        # 3. Writer Stage
        draft_narrative = self.writer.draft_narrative(derived_insight)

        # 4. Reviewer Stage
        final_narrative = self.reviewer.review(draft_narrative)

        # 5. Memory-Curator Stage
        entries = self.curator.commit_pipeline_run(
            session_id=session_id,
            raw_fact=raw_fact,
            derived_insight=derived_insight,
            final_narrative=final_narrative,
            ground_truth=ground_truth,
            injection_metadata=injection_meta,
            prior_memories=prior_memories
        )

        return entries