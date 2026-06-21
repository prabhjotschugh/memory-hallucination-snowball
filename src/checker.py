import re
from typing import List

# Regexes adapted from hallucination-snowball predecessor
_DOL = re.compile(
    r"\$\s?[\d,]+(?:\.\d+)?\s*"
    r"(?:million|billion|mn|bn|m|b|MM|thousand|k|trillion|T)?"
    r"(?:\s(?:million|billion|mn|bn|thousand|k|trillion))?",
    re.IGNORECASE,
)
_PCT = re.compile(
    r"(?<!\w)[\-\+]?\d+(?:\.\d+)?\s*(?:%|percent|percentage\s+points?|bps)",
    re.IGNORECASE,
)
_NUM = re.compile(
    r"(?<!\$)(?<!\w)[\d,]{5,}(?:\.\d+)?(?!\s*(?:%|percent))",
)

def parse_number(s: str) -> float:
    """
    Parse a string to float, handling magnitude suffixes securely.
    e.g., "$71.2B" -> 71200000000.0, "5.4%" -> 0.054
    """
    s_lower = s.lower()
    
    # Check for percentage first
    is_percent = any(p in s_lower for p in ["%", "percent", "bps"])
    
    # Strip everything except numbers, decimal points, and minus signs
    cleaned = re.sub(r"[^0-9.\-]", "", s)
    if not cleaned or cleaned in ["-", "."]:
        return 0.0
        
    try:
        val = float(cleaned)
    except ValueError:
        return 0.0

    # Handle percentages
    if is_percent:
        if "bps" in s_lower:
            return round(val / 10000.0, 6)
        return round(val / 100.0, 6)

    # Handle magnitudes (upgrading from V1 to use absolute scale)
    if any(m in s_lower for m in ["trillion", "t"]):
        val *= 1e12
    elif any(m in s_lower for m in ["billion", "bn", "b"]):
        val *= 1e9
    elif any(m in s_lower for m in ["million", "mn", "m", "mm"]):
        val *= 1e6
    elif any(m in s_lower for m in ["thousand", "k"]):
        val *= 1e3
        
    return val

def extract_numbers(text: str) -> List[float]:
    """
    Extract all numeric values from text using standard regexes and scale them.
    """
    matches = []
    matches.extend(_DOL.findall(text))
    matches.extend(_PCT.findall(text))
    matches.extend(_NUM.findall(text))
    
    return [parse_number(m) for m in matches]

def check_numeric_contamination(extracted_text: str, ground_truth_val: float, tolerance: float = 0.02) -> bool:
    """
    Returns True if the text is contaminated (fails to match ground truth within tolerance).
    Returns False if the ground truth is correctly preserved.
    """
    if ground_truth_val == 0.0:
        # Edge case: handling absolute zero GT
        # We assume if the GT is exactly zero, we must find an exact zero in the text.
        nums = extract_numbers(extracted_text)
        if not nums:
            return True
        for n in nums:
            if n == 0.0:
                return False
        return True

    extracted_vals = extract_numbers(extracted_text)
    
    # If no numbers found, it's definitively lost/contaminated
    if not extracted_vals:
        return True
        
    for val in extracted_vals:
        dev = abs(val - ground_truth_val) / abs(ground_truth_val)
        if dev <= tolerance:
            # We found a matching number within tolerance. Not contaminated.
            return False
            
    # No extracted number matched within tolerance -> Contaminated
    return True
