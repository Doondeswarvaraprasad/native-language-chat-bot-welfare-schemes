from typing import TypedDict, List, Dict, Optional

class AgentState(TypedDict):
    user_text: str
    intent: str
    slots: Dict[str, Optional[str]]
    missing_slots: List[str]
    eligible_schemes: List[str]
    response: str
    history: List[Dict[str, str]]
    needs_confirmation: bool
    pending_conflicts: Dict[str, any]
    pending_updates: Dict[str, any]
    iteration_count: int
    next_action: str
    last_question_slot: Optional[str]
    last_referenced_scheme_id: Optional[str]
    last_referenced_scheme_name: Optional[str]
    pending_followup: Optional[str]
