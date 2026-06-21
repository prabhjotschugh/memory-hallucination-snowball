import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from memory import MemoryStore
from agent import Researcher, Analyst, Writer, Reviewer
from pipeline import MemoryCurator, Pipeline
from metrics import calculate_cluster_growth, calculate_detectability

def test_pipeline_phase6_10_session_loop():
    print("\n" + "="*60)
    print("🚀 PHASE 6: 10-SESSION MULTI-TURN SNOWBALL LOOP")
    print("="*60)
    
    db_path = "memory_phase6_db.json"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    store = MemoryStore(db_path=db_path)
    curator = MemoryCurator(store)
    pipeline = Pipeline(Researcher(), Analyst(), Writer(), Reviewer(), curator)

    cluster_growth_history = []
    detectability_history = []
    injected_entry_id = None

    for session_id in range(1, 11):
        print(f"\n--- Running Session {session_id} ---")
        
        # In Session 1, we inject the hallucination ($50B instead of $85B).
        # In Sessions 2-10, the pipeline runs normally on a clean document ($100B).
        source_text = "Apple's Q1 revenue reached $85.0B." if session_id == 1 else f"Apple's Q{session_id} revenue reached $100.0B."
        analyst_context = "Calculate revenue growth from the previous quarter using Historical Memory."
        
        ground_truth = 85000000000.0 if session_id == 1 else 100000000000.0
        injection = "$50.0B" if session_id == 1 else None

        entries = pipeline.run(
            session_id=session_id,
            source_text=source_text,
            question=f"What was Apple's Q{session_id} revenue?",
            analyst_context=analyst_context,
            ground_truth=ground_truth,
            injected_researcher_override=injection
        )

        if session_id == 1:
            injected_entry_id = entries[0].entry_id # Save the ID of the injected RAW_FACT
            
        # Calculate Metrics!
        cluster_size = calculate_cluster_growth(store, injected_entry_id)
        detectability = calculate_detectability(store, injected_entry_id, ground_truth=85000000000.0) # Track against the original broken truth
        
        cluster_growth_history.append(cluster_size)
        detectability_history.append(detectability)
        
        print(f"-> Cluster Size: {cluster_size} infected entries")
        print(f"-> Detectability Decay: {detectability * 100:.1f}%")

    print("\n" + "="*60)
    print("📈 FINAL METRICS OVER 10 SESSIONS")
    print("="*60)
    print(f"Cluster Growth Array : {cluster_growth_history}")
    print(f"Detectability Array  : {[round(d, 2) for d in detectability_history]}")
    
    # Assertions to prove the paper's theory:
    # 1. Cluster size must never shrink.
    assert all(x <= y for x, y in zip(cluster_growth_history, cluster_growth_history[1:])), "Cluster size shrank!"
    # 2. It must snowball to at least 15 infected entries after 10 sessions.
    assert cluster_growth_history[-1] > 15, "Snowball failed to spread across sessions."

    print("\nSUCCESS: Phase 6 complete. The mathematical metrics confirm the snowball hypothesis.")