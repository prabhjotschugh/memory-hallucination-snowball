import sys
import os

# Add src to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from memory import MemoryEntry, MemoryStore, StateTag, VerificationStatus

def test_lineage_vs_contamination_isolation():
    # Use a temporary db file for the test so we don't pollute the real one
    test_db_path = "test_memory_db.json"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        
    store = MemoryStore(db_path=test_db_path)
    
    print("\n--- Starting Phase 1 Test: Lineage vs Contamination Isolation ---")
    
    # Create entry A (Contaminated)
    entry_a = MemoryEntry(
        entry_id="A",
        session_id=1,
        agent_source="Researcher",
        content="Revenue is $50M (wrong)",
        state_tag=StateTag.RAW_FACT,
        parent_ids=[],
        ground_truth_checkable=True,
        is_contaminated=True, # explicitly marked contaminated
        verification_status=VerificationStatus.FLAGGED_CONTAMINATED
    )
    store.write(entry_a)
    print(f"Created Entry A (Agent: {entry_a.agent_source}): is_contaminated={entry_a.is_contaminated}, content='{entry_a.content}'")
    
    # Create entry B (derived from A, but marked clean because checker hasn't flagged it)
    entry_b = MemoryEntry(
        entry_id="B",
        session_id=2,
        agent_source="Analyst",
        content="Revenue was $50M last quarter",
        state_tag=StateTag.DERIVED,
        parent_ids=["A"],
        ground_truth_checkable=True,
        is_contaminated=False, # explicitly marked clean
        verification_status=VerificationStatus.UNVERIFIED
    )
    store.write(entry_b)
    print(f"Created Entry B (Agent: {entry_b.agent_source}, Parent: A): is_contaminated={entry_b.is_contaminated}, content='{entry_b.content}'")
    
    # Create entry C (derived from B, marked clean)
    entry_c = MemoryEntry(
        entry_id="C",
        session_id=3,
        agent_source="Writer",
        content="Our $50M revenue gives us momentum.",
        state_tag=StateTag.NARRATIVE,
        parent_ids=["B"],
        ground_truth_checkable=False,
        is_contaminated=False, # explicitly marked clean
        verification_status=VerificationStatus.UNVERIFIED
    )
    store.write(entry_c)
    print(f"Created Entry C (Agent: {entry_c.agent_source}, Parent: B): is_contaminated={entry_c.is_contaminated}, content='{entry_c.content}'")
    
    print("\n--- Running Checks ---")
    
    # TEST 1: Retrieve and confirm B and C did not auto-inherit contamination
    retrieved_b = store.get_by_id("B")
    retrieved_c = store.get_by_id("C")
    
    print(f"Checking B: Inherited contamination? {retrieved_b.is_contaminated}")
    print(f"Checking C: Inherited contamination? {retrieved_c.is_contaminated}")
    
    assert retrieved_b.is_contaminated is False, "BUG REAPPEARED: Entry B auto-inherited contamination from A"
    assert retrieved_c.is_contaminated is False, "BUG REAPPEARED: Entry C auto-inherited contamination"
    print("SUCCESS: V1 bug avoided. Contamination is not auto-inherited.")
    
    # TEST 2: Confirm we can still trace lineage C -> B -> A
    lineage_c = store.trace_lineage("C")
    ancestor_ids = {entry.entry_id for entry in lineage_c}
    
    print(f"Lineage trace for C found ancestors: {ancestor_ids}")
    
    assert "B" in ancestor_ids, "Lineage trace failed to find parent B"
    assert "A" in ancestor_ids, "Lineage trace failed to find grandparent A"
    
    # Ensure C's lineage specifically contains exactly A and B
    assert len(lineage_c) == 2, f"Expected 2 ancestors, got {len(lineage_c)}"
    print("SUCCESS: Lineage tracing works independently of contamination flags.")
    print("--- Test Complete ---\n")