from langgraph.graph import StateGraph, END
from langgraph_state import AgentState
from langgraph_nodes import (
    input_node,
    intent_slot_extraction_node,
    correction_handler_node,
    planner_node,
    knowledge_answer_node,
    clarification_node,
    eligibility_check_node,
    response_generation_node
)


def route_from_planner(state: AgentState) -> str:
    """Route based on planner's decision"""
    action = state.get("next_action", "knowledge")
    if action == "end":
        return "end"
    if action == "clarification":
        return "clarification"
    if action == "eligibility":
        return "eligibility_check"
    return "knowledge_answer"


def create_workflow() -> StateGraph:
    """Create the complete workflow graph"""
    workflow = StateGraph(AgentState)
    
    # Add all nodes
    workflow.add_node("input", input_node)
    workflow.add_node("intent_slot", intent_slot_extraction_node)
    workflow.add_node("correction_handler", correction_handler_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("knowledge_answer", knowledge_answer_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("eligibility_check", eligibility_check_node)
    workflow.add_node("response_generation", response_generation_node)
    
    # Set entry point
    workflow.set_entry_point("input")
    
    # Linear flow through intent detection and correction
    workflow.add_edge("input", "intent_slot")
    workflow.add_edge("intent_slot", "correction_handler")
    workflow.add_edge("correction_handler", "planner")
    
    # Conditional routing from planner
    workflow.add_conditional_edges(
        "planner",
        route_from_planner,
        {
            "knowledge_answer": "knowledge_answer",
            "clarification": "clarification",
            "eligibility_check": "eligibility_check",
            "end": END,
        },
    )
    
    # Terminal nodes
    workflow.add_edge("knowledge_answer", END)
    workflow.add_edge("clarification", END)
    workflow.add_edge("eligibility_check", "response_generation")
    workflow.add_edge("response_generation", END)
    
    return workflow.compile()


def run_agent(user_text: str, current_state: dict = None) -> dict:
    """Run the agent workflow with user input"""
    if current_state is None:
        current_state = {
            "user_text": user_text,
            "intent": "",
            "slots": {},
            "missing_slots": [],
            "eligible_schemes": [],
            "response": "",
            "history": [],
            "needs_confirmation": False,
            "pending_conflicts": {},
            "pending_updates": {},
            "iteration_count": 0,
            "next_action": "",
            "last_question_slot": None,
            "last_referenced_scheme_id": None,
            "last_referenced_scheme_name": None,
            "pending_followup": None,
        }
    else:
        # Preserve state across turns
        preserved_slots = current_state.get("slots", {}).copy()
        preserved_history = current_state.get("history", []).copy()
        
        current_state["user_text"] = user_text
        current_state["slots"] = preserved_slots
        current_state["history"] = preserved_history
        current_state["iteration_count"] = current_state.get("iteration_count", 0) + 1
        current_state["needs_confirmation"] = current_state.get("needs_confirmation", False)
        current_state["pending_conflicts"] = current_state.get("pending_conflicts", {})
        current_state["pending_updates"] = current_state.get("pending_updates", {})
        current_state["next_action"] = current_state.get("next_action", "")
        current_state["last_question_slot"] = current_state.get("last_question_slot", None)
        current_state["last_referenced_scheme_id"] = current_state.get("last_referenced_scheme_id", None)
        current_state["last_referenced_scheme_name"] = current_state.get("last_referenced_scheme_name", None)
        current_state["pending_followup"] = current_state.get("pending_followup", None)
    
    # Create and invoke workflow
    app = create_workflow()
    result = app.invoke(current_state)
    
    # Debug logging
    try:
        print(f"[LangGraph] intent={result.get('intent')} next_action={result.get('next_action')} slots={result.get('slots')} eligible={len(result.get('eligible_schemes', []))}")
    except Exception:
        pass
    
    # Update history
    if "history" not in result:
        result["history"] = []
    
    result["history"].append({
        "role": "assistant",
        "content": result.get("response", "")
    })
    
    # Keep history manageable
    if len(result["history"]) > 20:
        result["history"] = result["history"][-20:]
    
    return result