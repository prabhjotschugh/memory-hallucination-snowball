import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from agent import Researcher
from checker import check_numeric_contamination

def test_researcher_agent_and_checker():
    print("\n--- Starting Phase 3 Test: Agent & Checker Integration ---")
    
    agent = Researcher()
    
    test_cases = [
        {
            "source": "In Q1 2026, Apple reported a record revenue of $90.5 billion. Cost of goods sold was $40B.",
            "question": "What was Apple's Q1 2026 revenue?",
            "ground_truth": 90500000000.0,
            "wrong_injection": "Revenue was $50 billion."
        },
        {
            "source": "Microsoft's cloud division saw a 22.4% year-over-year growth in 2025.",
            "question": "What was the YoY growth for Microsoft's cloud division?",
            "ground_truth": 0.224,
            "wrong_injection": "It grew by 15.0%."
        },
        {
            "source": "Tesla delivered 1,800,000 vehicles worldwide last year.",
            "question": "How many vehicles did Tesla deliver?",
            "ground_truth": 1800000.0,
            "wrong_injection": "They delivered 500,000 vehicles."
        },
        {
            "source": "Nvidia's gross margin expanded to 74.5% driven by data center sales.",
            "question": "What was Nvidia's gross margin?",
            "ground_truth": 0.745,
            "wrong_injection": "Margin was 60.0%."
        },
        {
            "source": "Amazon's operating income increased to $15.3 billion.",
            "question": "What was Amazon's operating income?",
            "ground_truth": 15300000000.0,
            "wrong_injection": "Operating income was $10B."
        }
    ]
    
    for i, tc in enumerate(test_cases, 1):
        print(f"\n[Scenario {i}]")
        print(f"Source: {tc['source']}")
        print(f"Question: {tc['question']}")
        print(f"Ground Truth: {tc['ground_truth']}")
        
        # 1. Ask the Agent
        agent_answer = agent.extract_figure(tc['source'], tc['question'])
        print(f"--> Agent replied: '{agent_answer.strip()}'")
        
        # 2. Check the real agent output (Should NOT be contaminated)
        is_contam_real = check_numeric_contamination(agent_answer, tc['ground_truth'])
        print(f"--> Checker result (Real Agent): Contaminated? {is_contam_real}")
        assert is_contam_real is False, f"Agent's correct answer was falsely flagged. Answer: {agent_answer}"
        
        # 3. Inject a hallucination (Should BE contaminated)
        print(f"--> Simulating Error Injection: '{tc['wrong_injection']}'")
        is_contam_fake = check_numeric_contamination(tc['wrong_injection'], tc['ground_truth'])
        print(f"--> Checker result (Injected Error): Contaminated? {is_contam_fake}")
        assert is_contam_fake is True, "Injected error failed to be flagged as contaminated."

    print("\nSUCCESS: Phase 3 complete. Agent extracts data and Checker correctly evaluates it.")
    print("--- Test Complete ---\n")