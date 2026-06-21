import sys
import os

# Add src to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from checker import check_numeric_contamination, parse_number, extract_numbers

def test_number_parser():
    print("\n--- Testing Parser Scaling ---")
    
    val1 = parse_number("$71.2B")
    print(f"Parsing '$71.2B' -> {val1}")
    assert val1 == 71200000000.0, "Failed billions scaling"
    
    val2 = parse_number("$50M")
    print(f"Parsing '$50M'   -> {val2}")
    assert val2 == 50000000.0, "Failed millions scaling"
    
    val3 = parse_number("5.4%")
    print(f"Parsing '5.4%'   -> {val3}")
    assert val3 == 0.054, "Failed percentage scaling"
    
    val4 = parse_number("1,000")
    print(f"Parsing '1,000'  -> {val4}")
    assert val4 == 1000.0, "Failed comma stripping"
    
    val5 = parse_number("-2.1 percent")
    print(f"Parsing '-2.1 percent' -> {val5}")
    assert val5 == -0.021, "Failed negative percent"
    
    print("SUCCESS: Number parsing and scaling works correctly.")

def test_numeric_contamination_checker():
    print("\n--- Starting Phase 2 Test: Contamination Checker ---")
    
    ground_truth = 71200000000.0 # $71.2 Billion
    print(f"Target Ground Truth: {ground_truth} ($71.2 Billion)")
    
    # Test 1: Exact Match (Formatted differently but same scale)
    text_exact = "The total revenue was $71.2B this year."
    print(f"\n[Test 1: Exact Match]")
    print(f"Agent wrote: '{text_exact}'")
    is_contam_exact = check_numeric_contamination(text_exact, ground_truth)
    print(f"Result: Contaminated? {is_contam_exact}")
    assert is_contam_exact is False, "Exact match falsely flagged as contaminated"
    
    # Test 2: Within 2% Tolerance (71B is ~0.28% off from 71.2B)
    text_tol = "We hit roughly $71B in revenue."
    print(f"\n[Test 2: Within 2% Tolerance]")
    print(f"Agent wrote: '{text_tol}'")
    is_contam_tol = check_numeric_contamination(text_tol, ground_truth)
    print(f"Result: Contaminated? {is_contam_tol}")
    assert is_contam_tol is False, "Value within tolerance falsely flagged as contaminated"
    
    # Test 3: Outside Tolerance (50M is wildly off from 71.2B)
    text_wrong = "Revenue dropped to $50M due to market conditions."
    print(f"\n[Test 3: Outside Tolerance / Wrong]")
    print(f"Agent wrote: '{text_wrong}'")
    is_contam_wrong = check_numeric_contamination(text_wrong, ground_truth)
    print(f"Result: Contaminated? {is_contam_wrong}")
    assert is_contam_wrong is True, "Wrong value failed to be flagged as contaminated"
    
    # Test 4: Missing Number entirely
    text_missing = "Revenue was strong but we aren't releasing figures."
    print(f"\n[Test 4: Missing Number]")
    print(f"Agent wrote: '{text_missing}'")
    is_contam_missing = check_numeric_contamination(text_missing, ground_truth)
    print(f"Result: Contaminated? {is_contam_missing}")
    assert is_contam_missing is True, "Missing value failed to be flagged as contaminated"

    # Test 5: Multiple numbers in text
    text_multi = "Expenses were $50M, but revenue was $71B."
    print(f"\n[Test 5: Multiple Numbers in Text]")
    print(f"Agent wrote: '{text_multi}'")
    is_contam_multi = check_numeric_contamination(text_multi, ground_truth)
    print(f"Result: Contaminated? {is_contam_multi}")
    assert is_contam_multi is False, "Failed to find correct value when multiple numbers exist"

    print("\nSUCCESS: Contamination checker correctly evaluates Tier A numeric logic.")
    print("--- Test Complete ---\n")
