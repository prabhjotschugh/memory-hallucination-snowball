from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class StateTag(str, Enum):
    RAW_FACT = "RAW_FACT"
    DERIVED = "DERIVED"
    NARRATIVE = "NARRATIVE"

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FLAGGED_CONTAMINATED = "FLAGGED_CONTAMINATED"

class MemoryEntry(BaseModel):
    entry_id: str
    session_id: int
    agent_source: str
    content: str
    state_tag: StateTag
    parent_ids: List[str] = Field(default_factory=list)
    ground_truth_checkable: bool
    is_contaminated: bool
    verification_status: VerificationStatus
    injection_metadata: Optional[Dict[str, Any]] = None

class MemoryStore:
    def __init__(self):
        self.entries: Dict[str, MemoryEntry] = {}
        
    def write(self, entry: MemoryEntry):
        self.entries[entry.entry_id] = entry
        
    def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        return self.entries.get(entry_id)
        
    def get_by_session(self, session_id: int) -> List[MemoryEntry]:
        return [e for e in self.entries.values() if e.session_id == session_id]
        
    def trace_lineage(self, entry_id: str) -> List[MemoryEntry]:
        """
        Returns all ancestor entries of the given entry_id.
        """
        entry = self.get_by_id(entry_id)
        if not entry:
            return []
            
        lineage = []
        queue = list(entry.parent_ids)
        visited = set()
        
        while queue:
            current_id = queue.pop(0)
            if current_id not in visited:
                visited.add(current_id)
                current_entry = self.get_by_id(current_id)
                if current_entry:
                    lineage.append(current_entry)
                    queue.extend(current_entry.parent_ids)
                    
        return lineage
