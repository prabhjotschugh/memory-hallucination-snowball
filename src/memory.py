import json
import os
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
    def __init__(self, db_path: str = "memory_db.json"):
        self.db_path = db_path
        self.entries: Dict[str, MemoryEntry] = {}
        self._load_from_disk()
        
    def _load_from_disk(self):
        """Loads entries from the JSON file if it exists."""
        if os.path.exists(self.db_path):
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry_id, entry_dict in data.items():
                    self.entries[entry_id] = MemoryEntry(**entry_dict)

    def _save_to_disk(self):
        """Saves the current state of entries to the JSON file."""
        data_to_save = {
            entry_id: entry.model_dump(mode="json") 
            for entry_id, entry in self.entries.items()
        }
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4)
            
    def write(self, entry: MemoryEntry):
        """Writes an entry and immediately saves to disk."""
        self.entries[entry.entry_id] = entry
        self._save_to_disk()
        
    def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        return self.entries.get(entry_id)
        
    def get_by_session(self, session_id: int) -> List[MemoryEntry]:
        return [e for e in self.entries.values() if e.session_id == session_id]
        
    def retrieve_memory(self, up_to_session_id: int) -> List[MemoryEntry]:
        """
        Retrieves all prior memory entries up to (but not including) the current session.
        Currently implements 'Shared Blackboard' (Condition 1) - unfiltered retrieval.
        """
        return [e for e in self.entries.values() if e.session_id < up_to_session_id]
        
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
