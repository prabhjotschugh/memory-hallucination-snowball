from typing import List, Set
from memory import MemoryStore, MemoryEntry
from checker import check_numeric_contamination

def _get_all_descendants(store: MemoryStore, target_entry_id: str) -> List[MemoryEntry]:
    """
    Finds all entries in the MemoryStore that trace their lineage back to the target_entry_id.
    """
    descendants = []
    
    # We iterate over all entries and use the built-in trace_lineage to see if the target is an ancestor
    for entry_id, entry in store.entries.items():
        if entry_id == target_entry_id:
            continue
            
        lineage = store.trace_lineage(entry_id)
        ancestor_ids = {a.entry_id for a in lineage}
        
        if target_entry_id in ancestor_ids:
            descendants.append(entry)
            
    return descendants

def calculate_cluster_growth(store: MemoryStore, injected_entry_id: str) -> int:
    """
    Metric 1: Cluster Growth Rate
    Returns the total number of memory entries that were spawned by (derived from) the injected error.
    """
    descendants = _get_all_descendants(store, injected_entry_id)
    return len(descendants)

def calculate_detectability(store: MemoryStore, injected_entry_id: str, ground_truth: float) -> float:
    """
    Metric 2: Detectability Decay
    Evaluates all descendants of the injected error.
    Returns the fraction (0.0 to 1.0) of these descendants that are STILL correctly 
    caught/flagged by the Tier A mathematical checker.
    """
    descendants = _get_all_descendants(store, injected_entry_id)
    
    if not descendants:
        return 0.0
        
    caught_count = 0
    for entry in descendants:
        # We use the mathematical checker just like the Curator does.
        # If the check fails (returns True for contamination), then the error is STILL DETECTABLE.
        # If the check passes (returns False), the error has become INVISIBLE to the math checker (e.g. buried in narrative).
        is_detectable_contamination = check_numeric_contamination(entry.content, ground_truth)
        if is_detectable_contamination:
            caught_count += 1
            
    return caught_count / len(descendants)