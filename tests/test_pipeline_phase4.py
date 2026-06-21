import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from memory import MemoryStore, VerificationStatus
from agent import Researcher, Analyst, Writer, Reviewer
from pipeline import MemoryCurator, Pipeline

def test_pipeline_phase4():
    print("\n--- Starting Phase 4 Test: Full 5-Agent Pipeline ---")
    
    # Initialize infrastructure
    store = MemoryStore()
    curator = MemoryCurator(store)
    
    # Initialize agents
    researcher = Researcher()
    analyst = Analyst()
    writer = Writer()
    reviewer = Reviewer()
    
    pipeline = Pipeline(researcher, analyst, writer, reviewer, curator)
    
    session_data = {
        "source": "Apple's Q3 revenue reached $85.0B, driven by strong iPhone sales.",
        "question": "What was Apple's Q3 revenue?",
        "analyst_context": "Last year's Q3 revenue was $80.0B.",
        "ground_truth": 85000000000.0,
        "wrong_injection": "$50.0B" # Force a hallucination
    }

    # ==========================================
    # TEST A: Clean Pipeline Run
    # ==========================================
    print("\n[TEST A: Clean Pipeline Run]")
    entries_clean = pipeline.run(
        session_id=1,
        source_text=session_data["source"],
        question=session_data["question"],
        analyst_context=session_data["analyst_context"],
        ground_truth=session_data["ground_truth"],
        injected_researcher_override=None
    )
    
    raw_clean, derived_clean, narrative_clean = entries_clean
    
    print(f"Researcher Output : {raw_clean.content.strip()}")
    print(f"Analyst Output    : {derived_clean.content.strip()}")
    print(f"Reviewer Output   : {narrative_clean.content.strip()}")
    
    print(f"\nCurator Status (Raw)      : is_contaminated={raw_clean.is_contaminated}, status={raw_clean.verification_status.name}")
    print(f"Curator Status (Narrative): is_contaminated={narrative_clean.is_contaminated}, status={narrative_clean.verification_status.name}")

    assert raw_clean.is_contaminated is False, "Clean pipeline falsely flagged as contaminated at Raw stage"
    assert narrative_clean.is_contaminated is False, "Clean pipeline falsely flagged as contaminated at Narrative stage"
    # The narrative usually drops the absolute raw figure in favor of the derived percentage, so it's UNVERIFIED by Tier A
    assert narrative_clean.verification_status in [VerificationStatus.VERIFIED, VerificationStatus.UNVERIFIED], "Clean narrative was incorrectly FLAGGED"

    # ==========================================
    # TEST B: Snowball Injection Pipeline Run
    # ==========================================
    print("\n[TEST B: Snowball Injection Pipeline Run]")
    entries_snowball = pipeline.run(
        session_id=2,
        source_text=session_data["source"],
        question=session_data["question"],
        analyst_context=session_data["analyst_context"],
        ground_truth=session_data["ground_truth"],
        injected_researcher_override=session_data["wrong_injection"]
    )
    
    raw_snow, derived_snow, narrative_snow = entries_snowball
    
    print(f"Researcher Output (INJECTED) : {raw_snow.content.strip()}")
    print(f"Analyst Output (SNOWBALLED)  : {derived_snow.content.strip()}")
    print(f"Reviewer Output (SNOWBALLED) : {narrative_snow.content.strip()}")
    
    print(f"\nCurator Status (Raw)      : is_contaminated={raw_snow.is_contaminated}, status={raw_snow.verification_status.name}")
    print(f"Curator Status (Narrative): is_contaminated={narrative_snow.is_contaminated}, status={narrative_snow.verification_status.name}")

    assert raw_snow.is_contaminated is True, "Injected error was not flagged as contaminated at Raw stage"
    assert raw_snow.verification_status == VerificationStatus.FLAGGED_CONTAMINATED, "Injected raw fact was not FLAGGED"
    
    # The snowball test: did the analyst and writer carry the wrong number forward? 
    # If they did, the curator should catch it because it doesn't match $85B!
    assert narrative_snow.is_contaminated is True, "Snowballed error escaped the contamination checker at Narrative stage"
    assert narrative_snow.verification_status == VerificationStatus.FLAGGED_CONTAMINATED, "Snowballed narrative was not FLAGGED"

    print("\nSUCCESS: Phase 4 complete. Pipeline orchestrates agents and Curator correctly evaluates & stores the cascade.")
    print("--- Test Complete ---\n")