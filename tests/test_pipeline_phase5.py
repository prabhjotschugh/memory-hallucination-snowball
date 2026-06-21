import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from memory import MemoryStore, VerificationStatus
from agent import Researcher, Analyst, Writer, Reviewer
from pipeline import MemoryCurator, Pipeline
from checker import check_numeric_contamination

def test_pipeline_phase5_cross_session_snowball():
    print("\n--- Starting Phase 5 Test: Cross-Session Memory Snowball ---")
    
    # Use the main memory_db.json file for this test so the user can easily open it and look at it!
    db_path = "memory_phase5_db.json"
    if os.path.exists(db_path):
        os.remove(db_path) # Clear it out before the test starts so it's fresh
        
    store = MemoryStore(db_path=db_path)
    curator = MemoryCurator(store)
    pipeline = Pipeline(Researcher(), Analyst(), Writer(), Reviewer(), curator)

    # ==========================================
    # SESSION 1: Q1 Earnings (Inject Error Here)
    # ==========================================
    print("\n[SESSION 1: Processing Q1 Earnings]")
    q1_data = {
        "source": "Apple's Q1 revenue reached $85.0B.",
        "question": "What was Apple's Q1 revenue?",
        "analyst_context": "Previous quarter was $80.0B.",
        "ground_truth": 85000000000.0,
        "wrong_injection": "$50.0B" # Force hallucination in Q1
    }
    
    entries_s1 = pipeline.run(
        session_id=1,
        source_text=q1_data["source"],
        question=q1_data["question"],
        analyst_context=q1_data["analyst_context"],
        ground_truth=q1_data["ground_truth"],
        injected_researcher_override=q1_data["wrong_injection"]
    )
    
    print(f"Session 1 (Injected) Raw Output: {entries_s1[0].content.strip()}")
    print(f"Session 1 Final Narrative: {entries_s1[2].content.strip()}")
    assert entries_s1[0].is_contaminated is True, "S1 injection failed"
    
    # ==========================================
    # SESSION 2: Q2 Earnings (Clean Doc, Bad Memory)
    # ==========================================
    print("\n[SESSION 2: Processing Q2 Earnings]")
    print("* The source document is perfectly clean.")
    print("* But the Analyst will read Session 1's bad memory ($50B) to calculate growth.")
    
    q2_data = {
        "source": "Apple's Q2 revenue reached $100.0B.",
        "question": "What was Apple's Q2 revenue?",
        "analyst_context": "Calculate the revenue growth from Q1 to Q2. Use Historical Memory to find Q1's revenue.",
        "ground_truth": 100000000000.0, 
    }
    
    # The true mathematical YoY growth from Q1($85B) to Q2($100B) should be ~17.6%.
    # If the snowball happens, it will calculate growth from the hallucinated Q1($50B) to Q2($100B) = 100%.
    
    entries_s2 = pipeline.run(
        session_id=2,
        source_text=q2_data["source"],
        question=q2_data["question"],
        analyst_context=q2_data["analyst_context"],
        ground_truth=q2_data["ground_truth"],
        injected_researcher_override=None # NO injection in S2!
    )
    
    raw_s2, derived_s2, narrative_s2 = entries_s2
    
    print(f"Session 2 Researcher Output (Clean) : {raw_s2.content.strip()}")
    print(f"Session 2 Analyst Output (Snowball) : {derived_s2.content.strip()}")
    print(f"Session 2 Reviewer Output (Snowball): {narrative_s2.content.strip()}")
    
    # 1. Did the Researcher get the raw fact right? (It should, the doc is clean)
    assert raw_s2.is_contaminated is False, "S2 Researcher hallucinated on a clean document"
    
    # 2. Did the Analyst calculate the WRONG growth?
    # True growth (100 vs 85) = ~17.6% (0.176). Snowball growth (100 vs 50) = 100% (1.0).
    # We check if 0.176 is in the derived string. It shouldn't be.
    # We check if 1.0 or 100% is in the derived string. It should be.
    true_growth_present = not check_numeric_contamination(derived_s2.content, 0.176, tolerance=0.05)
    snowball_growth_present = not check_numeric_contamination(derived_s2.content, 1.0, tolerance=0.05)
    
    print(f"\n[Validation]")
    print(f"Did Analyst calculate true growth (~17.6%)? {true_growth_present}")
    print(f"Did Analyst calculate snowball growth (100%)? {snowball_growth_present}")
    
    assert snowball_growth_present is True, "The hallucination did not snowball across sessions as expected."
    
    print("\nSUCCESS: Phase 5 complete. The cross-session hallucination snowball is alive and measurable.")
    print("--- Test Complete ---\n")