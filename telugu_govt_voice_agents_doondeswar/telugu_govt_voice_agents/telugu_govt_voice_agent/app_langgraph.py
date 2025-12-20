from flask import Flask, render_template, request, jsonify
import json
import os
from langgraph_workflow import run_agent

app = Flask(__name__)

SESSION_MEMORY_PATH = "session_memory.json"

def load_session_state():
    if not os.path.exists(SESSION_MEMORY_PATH):
        return None
    try:
        with open(SESSION_MEMORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def save_session_state(state):
    serializable_state = state.copy()
    if "history" in serializable_state:
        history = []
        for msg in serializable_state["history"]:
            if isinstance(msg, dict):
                history.append(msg)
            else:
                history.append({
                    "role": getattr(msg, "type", "unknown"),
                    "content": getattr(msg, "content", str(msg))
                })
        serializable_state["history"] = history
    
    with open(SESSION_MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(serializable_state, f, ensure_ascii=False, indent=2)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/agent", methods=["POST"])
def agent():
    user_text = request.json.get("text", "")
    fresh = bool(request.json.get("fresh", False))
    
    if not user_text.strip():
        return jsonify({"response": "దయచేసి ఏదైనా చెప్పండి."})
    
    current_state = None if fresh else load_session_state()
    
    result = run_agent(user_text, current_state)
    
    save_session_state(result)
    
    response_data = {
        "response": result.get("response", ""),
        "intent": result.get("intent", ""),
        "slots": result.get("slots", {}),
        "missing_slots": result.get("missing_slots", []),
        "eligible_schemes": result.get("eligible_schemes", []),
        "needs_confirmation": result.get("needs_confirmation", False),
        "pending_conflicts": result.get("pending_conflicts", {})
    }
    
    return jsonify(response_data)

@app.route("/get_profile")
def get_profile():
    state = load_session_state()
    if state:
        return jsonify({
            "slots": state.get("slots", {}),
            "eligible_schemes": state.get("eligible_schemes", []),
            "conversation_turns": len(state.get("history", [])) // 2
        })
    return jsonify({"slots": {}, "eligible_schemes": [], "conversation_turns": 0})

@app.route("/reset")
def reset():
    if os.path.exists(SESSION_MEMORY_PATH):
        os.remove(SESSION_MEMORY_PATH)
    return jsonify({"status": "reset", "message": "సెషన్ రీసెట్ చేయబడింది"})

@app.route("/history")
def history():
    state = load_session_state()
    if state:
        return jsonify({"history": state.get("history", [])})
    return jsonify({"history": []})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
