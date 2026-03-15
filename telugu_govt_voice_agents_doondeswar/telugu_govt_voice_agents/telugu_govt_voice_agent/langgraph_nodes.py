import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from groq import Groq
from dotenv import load_dotenv
from langgraph_state import AgentState
from tools.eligibility_engine import check_eligibility
import re
from tools.scheme_details_tool import get_scheme_details

load_dotenv()
client = Groq(api_key="*******")

try:
    with open("data/schemes_master.json", encoding="utf-8") as _f:
        _SCHEMES_MASTER = json.load(_f)
except Exception:
    _SCHEMES_MASTER = {"AP": [], "TS": []}

_SCHEME_NAME_TO_ID: Dict[str, str] = {}
for _state_key in ["AP", "TS"]:
    for _s in _SCHEMES_MASTER.get(_state_key, []) or []:
        name = (_s.get("scheme_name_te") or "").strip()
        sid = (_s.get("scheme_id") or "").strip()
        if name and sid and name not in _SCHEME_NAME_TO_ID:
            _SCHEME_NAME_TO_ID[name] = sid

REQUIRED_SLOTS = ["age", "income", "occupation", "state"]
FINAL_INTENTS = [
    "greeting",
    "scheme_info",
    "scheme_search",
    "scheme_list",
    "scheme_criteria",
    "eligibility_check",
    "apply",
    "time_query",
    "name_query",
    "unknown",
]


def _next_question_for_missing(missing_slots) -> str:
    if not missing_slots:
        return ""
    slot = missing_slots[0]
    if slot == "age":
        return "మీ వయసు ఎంత?"
    if slot == "income":
        return "మీ వార్షిక ఆదాయం సుమారు ఎంత?"
    if slot == "occupation":
        return "మీ వృత్తి ఏమిటి? ఉదాహరణకు రైతు / కూలీ / ఉద్యోగి / డ్రైవర్ / నేత కార్మికుడు."
    if slot == "state":
        return "మీరు ఏ రాష్ట్రానికి చెందినవారు? తెలంగాణా లేదా ఆంధ్రప్రదేశ్?"
    return "దయచేసి మరికొన్ని వివరాలు చెప్పండి."


def _parse_json_lenient(text: str) -> Dict[str, Any]:
    json_text = _extract_first_json_object(text)
    if not json_text:
        return {}
    repaired = re.sub(r",\s*([}\]])", r"\1", json_text)
    try:
        parsed = json.loads(repaired)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _extract_first_json_object(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):]
    if cleaned.startswith("```"):
        cleaned = cleaned[len("```"):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-len("```")]
    cleaned = cleaned.strip()
    
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    
    start = cleaned.find("{")
    if start == -1:
        return ""
    depth = 0
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : i + 1]
    return ""


def _normalize_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    
    if key == "state":
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"ts", "telangana", "తెలంగాణ", "తెలంగాణా", "తెలగాణ"}:
                return "TS"
            if v in {"ap", "andhra", "andhra pradesh", "ఆంధ్ర", "ఆంధ్రప్రదేశ్", "ఆంధ్రప్రదేశ", "ఆంధ్రా", "ఆంధ్ర ప్రదేశ్"}:
                return "AP"
        return value
    
    if key in {"age", "income"}:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            v = value.strip().lower()
            m = re.search(r"(\d+)", v)
            if not m:
                return value
            n = int(m.group(1))
            if "లక్ష" in v or "lakh" in v:
                return n * 100000
            return n
    return value


def _is_affirmative_followup(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if any(x in t for x in [
        "కావాలి",
        "కోవాలి",
        "తెలుసుకోవాలి",
        "చెప్పు",
        "చెప్పండి",
        "వివరాలు",
        "ok",
        "ఓకే",
        "సరే",
        "yes",
        "అవును",
    ]):
        return True
    return False


def _is_confirmation_response(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(x in t for x in [
        "అవును",
        "సరే",
        "ok",
        "okay",
        "yes",
        "correct",
        "ఒప్పు",
        "నిజం",
    ])


def _conflict_prompt_te(conflicts: Dict[str, Any]) -> str:
    parts: List[str] = []
    for field, vals in (conflicts or {}).items():
        frm = vals.get("from")
        to = vals.get("to")
        if field == "age":
            parts.append(f"మీ వయసు విషయంలో గందరగోళం ఉంది. ముందు {frm} అన్నారు, ఇప్పుడు {to} చెప్పారు. {to} సరేనా? (అవును/కాదు)")
        elif field == "income":
            parts.append(f"మీ ఆదాయం విషయంలో మార్పు కనిపిస్తోంది. ముందు {frm}, ఇప్పుడు {to}. {to} సరేనా? (అవును/కాదు)")
        elif field == "occupation":
            parts.append(f"మీ వృత్తి విషయంలో మార్పు కనిపిస్తోంది. ముందు {frm}, ఇప్పుడు {to}. {to} సరేనా? (అవును/కాదు)")
        elif field == "state":
            parts.append(f"మీ రాష్ట్రం విషయంలో మార్పు కనిపిస్తోంది. ముందు {frm}, ఇప్పుడు {to}. మీ అసలు రాష్ట్రం {to}నా? (అవును/కాదు)")
        else:
            parts.append(f"{field} విషయంలో మార్పు కనిపిస్తోంది. ముందు {frm}, ఇప్పుడు {to}. {to} సరేనా? (అవును/కాదు)")
    return " ".join([p for p in parts if p]) or "కొన్ని వివరాల్లో మార్పు కనిపిస్తోంది. దయచేసి నిర్ధారించండి."


def _identify_scheme_from_text(user_text: str, user_state: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Use LLM to intelligently identify which scheme the user is asking about"""
    if not user_text or len(user_text.strip()) < 3:
        return None, None
    
    # Build scheme list for LLM context
    scheme_list = []
    states_to_check = [user_state] if user_state in ["AP", "TS"] else ["AP", "TS"]
    
    for state in states_to_check:
        for scheme in _SCHEMES_MASTER.get(state, []):
            scheme_id = scheme.get("scheme_id", "")
            scheme_name = scheme.get("scheme_name_te", "")
            if scheme_id and scheme_name:
                scheme_list.append(f"{scheme_id}|{scheme_name}")
    
    if not scheme_list:
        return None, None
    
    prompt = f"""User is asking about a government scheme in Telugu. Identify which scheme they are referring to.

Available schemes (format: ID|Name):
{chr(10).join(scheme_list[:120])}

User text: "{user_text}"

IMPORTANT:
- User may have typos or ASR errors (e.g., "అమ్మఒడి" means "అమ్మ ఒడి")
- Match based on phonetic similarity and meaning, not exact spelling
- If user mentions a scheme name (even partially), return that scheme ID
- If no scheme is mentioned, return "NONE"

Return ONLY the scheme ID (e.g., AP_AMMA_VODI) or NONE."""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You identify scheme names from user queries. Return only the scheme ID or NONE."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=50
        )
        
        raw_result = (response.choices[0].message.content or "").strip()
        result = raw_result.upper().replace(" ", "_")

        # If the model replies with an explanation (common failure mode), treat it as NONE.
        # We only accept short ID-like outputs.
        if len(raw_result) > 40 and "_" not in raw_result and "NONE" not in result:
            print(f"[SCHEME_IDENTIFICATION] LLM returned non-ID explanation for: {user_text[:50]}")
            return None, None

        # Clean up common LLM output issues
        if "NONE" in result or not result or result == "N/A":
            print(f"[SCHEME_IDENTIFICATION] LLM returned NONE for: {user_text[:50]}")
            return None, None
        
        # Extract just the scheme ID if LLM added extra text
        for sid in _SCHEME_NAME_TO_ID.values():
            if sid in result:
                result = sid
                break
        
        print(f"[SCHEME_IDENTIFICATION] LLM raw: '{raw_result}' -> cleaned: '{result}'")
        
        # Find the scheme name for this ID
        for nm, sid in _SCHEME_NAME_TO_ID.items():
            if sid == result:
                print(f"[SCHEME_IDENTIFICATION] Matched by ID: {sid} / {nm}")
                return sid, nm

        # If LLM returned a scheme NAME (common), map name -> id.
        # Also handle ASR space variants like "అమ్మఒడి" vs "అమ్మ ఒడి" by comparing compacted strings.
        raw_compact = "".join(raw_result.split())
        for nm, sid in _SCHEME_NAME_TO_ID.items():
            if not nm:
                continue
            nm_compact = "".join(nm.split())
            if nm in raw_result or (nm_compact and nm_compact in raw_compact):
                print(f"[SCHEME_IDENTIFICATION] Matched by NAME: {sid} / {nm}")
                return sid, nm
        
        print(f"[SCHEME_IDENTIFICATION] No match found for result: {result}")
        return None, None
        
    except Exception as e:
        print(f"[SCHEME_IDENTIFICATION] LLM error: {e}")
        return None, None


def _match_scheme_from_text_deterministic(
    user_text: str,
    user_state: Optional[str],
    restrict_scheme_ids: Optional[List[str]] = None,
) -> tuple[Optional[str], Optional[str]]:
    if not user_text:
        return None, None
    if user_state not in ["AP", "TS"]:
        return None, None

    text = user_text.strip()
    if not text:
        return None, None

    compact = "".join(text.split())
    restrict_set = set(restrict_scheme_ids or []) if restrict_scheme_ids else None

    for scheme in _SCHEMES_MASTER.get(user_state, []) or []:
        sid = (scheme.get("scheme_id") or "").strip()
        name_te = (scheme.get("scheme_name_te") or "").strip()
        if not sid or not name_te:
            continue
        if restrict_set is not None and sid not in restrict_set:
            continue

        name_compact = "".join(name_te.split())
        if name_te in text or (name_compact and name_compact in compact):
            return sid, name_te

    return None, None


def _regex_fallback_extract(user_text: str) -> Dict[str, Any]:
    """Enhanced regex extraction with better Telugu support"""
    text_lower = user_text.lower()
    slots: Dict[str, Any] = {}
    
    # CRITICAL: Age extraction with validation
    age_patterns = [
        r"వయసు\s*(\d+)",
        r"age\s*(\d+)",
        r"(\d+)\s*సంవత్సరాలు",
        r"(\d+)\s*years",
        r"(\d+)\s*ఏళ్ళు",
        r"(\d+)\s*సంవత్సర",
        r"(\d+)\s*ఏళ్ల"
    ]
    for pattern in age_patterns:
        match = re.search(pattern, user_text)
        if match:
            age_val = int(match.group(1))
            # FIXED: Validate age range (5 years is clearly wrong for pension!)
            if 10 <= age_val <= 120:  # Reasonable age range
                slots["age"] = age_val
                break
    
    # Enhanced income extraction
    income_patterns = [
        (r"(\d+)\s*లక్ష", lambda x: int(x) * 100000),
        (r"(\d+)\s*lakh", lambda x: int(x) * 100000),
        (r"ఆదాయం\s*(\d+)", lambda x: int(x)),
        (r"income\s*(\d+)", lambda x: int(x)),
        (r"(\d+)\s*రూపాయలు", lambda x: int(x)),
    ]
    for pattern, converter in income_patterns:
        match = re.search(pattern, user_text)
        if match:
            slots["income"] = converter(match.group(1))
            break
    
    # Enhanced state extraction with space variants
    if any(x in user_text for x in ["తెలంగాణ", "తెలంగాణా", "తెలగాణ"]) or "telangana" in text_lower:
        slots["state"] = "TS"
    elif any(x in user_text for x in ["ఆంధ్రప్రదేశ్", "ఆంధ్రప్రదేశ", "ఆంధ్ర", "ఆంధ్రా", "ఆంధ్ర ప్రదేశ్"]) or "andhra" in text_lower:
        slots["state"] = "AP"
    
    # Enhanced occupation extraction
    occupation_map = {
        "రైతు": "farmer",
        "farmer": "farmer",
        "కూలీ": "laborer",
        "laborer": "laborer",
        "లేబరర్": "laborer",
        "ఉద్యోగి": "employee",
        "employee": "employee",
        "వేవర్": "weaver",
        "weaver": "weaver",
        "నేత": "weaver",
        "నేతకారుడు": "weaver",
        "డ్రైవర్": "driver",
        "driver": "driver",
        "మత్స్యకారుడు": "fisherman",
        "fisherman": "fisherman",
        "ఇస్త్రీ": "iron_worker",
        "ఇస్త్రీవాడు": "iron_worker",
    }
    for token, occ in occupation_map.items():
        if token in user_text or token in text_lower:
            slots["occupation"] = occ
            break
    
    # Gender extraction
    if any(word in user_text for word in ["స్త్రీ", "ఆడ", "మహిళ", "female"]):
        slots["gender"] = "female"
    elif any(word in user_text for word in ["పురుషుడు", "మగ", "పురుష", "male"]):
        slots["gender"] = "male"
    
    return slots


def intent_detection_node(state: AgentState) -> AgentState:
    user_text = state["user_text"]

    pending_followup = state.get("pending_followup")
    short_yes = _is_affirmative_followup(user_text)
    is_number_choice = bool(re.search(r"\b(\d{1,2})\b", user_text or ""))

    # Follow-up flows are interruptible: only force follow-up routing when the user
    # gives a short follow-up/selection. Otherwise, treat it as a new query.
    if pending_followup in {"choose_scheme_from_eligibility", "scheme_details"}:
        if short_yes or is_number_choice:
            state["intent"] = "eligibility_check"
            return state
        state["pending_followup"] = None

    # Sticky follow-up: if we were collecting missing fields for eligibility, keep routing to eligibility
    if state.get("pending_followup") == "eligibility_clarification":
        state["intent"] = "eligibility_check"
        return state
    
    # Deterministic greeting override
    short = user_text.strip()
    if short in ["నమస్కారం", "హలో", "హాయ్", "hello", "hi", "హాయ్!", "హలో!"]:
        state["intent"] = "greeting"
        return state
    
    # Deterministic pension eligibility override
    if "పెన్షన్" in user_text and any(x in user_text for x in ["వస్తుందా", "వస్తుందా?", "అర్హ", "అర్హత", "eligible", "వస్తుందా రాదా", "నాకు పెన్షన్", "రాదా"]):
        state["intent"] = "eligibility_check"
        return state
    
    # Deterministic scheme eligibility override
    scheme_elig_words = [
        "వస్తుందా",
        "వస్తుందో",
        "వస్తుందో లేదో",
        "వస్తుందా లేదో",
        "రాదా",
        "అర్హ",
        "అర్హుడ",
        "అర్హత",
        "eligible",
        "eligibility",
        "ఎలిజిబిలిటీ",
    ]
    if any(w in user_text for w in scheme_elig_words):
        for scheme_name in _SCHEME_NAME_TO_ID.keys():
            if scheme_name and scheme_name in user_text:
                state["intent"] = "eligibility_check"
                return state
    
    prompt = f"""Classify the user's Telugu/English message into exactly one intent.

Allowed intents:
- greeting: short greeting only ("నమస్కారం")
- time_query: asking current time ("టైమ్ ఎంత", "ఇప్పుడు సమయం ఎంత")
- name_query: asking their saved profile name ("నా పేరు ఏమిటి")
- scheme_list: asking list of govt schemes for a state ("ఆంధ్రప్రదేశ్ లో ఏమేమి పథకాలు ఉన్నాయి")
- scheme_info: asking details about a specific scheme ("అమ్మ ఒడి గురించి చెప్పండి")
- scheme_criteria: asking eligibility criteria/requirements of a scheme ("అమ్మ ఒడి రావాలి అంటే పిల్లలకు ఎంత వయసు")
- scheme_search: wants schemes based on their profile but not explicitly asking eligible/not-eligible
- eligibility_check: explicitly wants eligible/not eligible ("నాకు వస్తుందా", "నేను అర్హుడానా")
- apply: wants to apply or asks application steps
- unknown: unclear

User text: {user_text}

Return ONLY one of:
greeting, time_query, name_query, scheme_list, scheme_info, scheme_criteria, scheme_search, eligibility_check, apply, unknown"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are an intent classifier. Return only the intent name."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        intent = response.choices[0].message.content.strip().lower()
        
        if intent not in FINAL_INTENTS:
            intent = "unknown"
            
    except Exception as e:
        print(f"Intent detection error: {e}")
        intent = "unknown"
    
    state["intent"] = intent
    return state


def _sanitize_user_text(text: str) -> str:
    if not text:
        return ""
    t = str(text)
    t = re.sub(r"\([^)]*\d{1,3}%[^)]*\)", " ", t)
    t = t.replace("🎤", " ").replace("🔊", " ").replace("⏹️", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def input_node(state: AgentState) -> AgentState:
    history = state.get("history", [])
    user_text = _sanitize_user_text(state.get("user_text", ""))
    state["user_text"] = user_text
    
    state["response"] = ""
    state["next_action"] = ""
    state["_extracted_slots"] = {}
    
    history.append({"role": "user", "content": user_text})
    state["history"] = history[-20:]
    state["iteration_count"] = state.get("iteration_count", 0) + 1
    return state


def slot_extraction_node(state: AgentState) -> AgentState:
    user_text = _sanitize_user_text(state.get("user_text", ""))
    state["user_text"] = user_text
    current_slots = (state.get("slots") or {}).copy()

    llm_slots: Dict[str, Any] = {}
    try:
        prompt = f"""Extract user profile information from Telugu/English text.

Return ONLY a single JSON object (no markdown, no explanation).

Fields you may extract if mentioned:
state, age, gender, occupation, income, family_size, land_owner, disability, caste, religion, has_children, pregnant, location.

Normalization rules:
- state: తెలంగాణ/తెలంగాణా -> TS, ఆంధ్రప్రదేశ్/ఆంధ్ర/ఆంధ్రప్రదేశ/ఆంధ్ర ప్రదేశ్ -> AP
- occupation: రైతు->farmer, కూలీ->laborer, ఉద్యోగి->employee, వేవర్/నేత->weaver, డ్రైవర్->driver, మత్స్యకారుడు->fisherman
- age: integer only (must be between 10-120)
- income: integer rupees ("లక్ష" => 100000)

Current stored profile: {current_slots}
User text: {user_text}
"""

        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You extract structured data and output ONLY valid JSON. Follow normalization rules strictly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=256,
        )
        raw = resp.choices[0].message.content or ""
        llm_slots = _parse_json_lenient(raw)
    except Exception as e:
        print(f"Slot extraction LLM error: {e}")

    regex_slots = _regex_fallback_extract(user_text)

    new_slots: Dict[str, Any] = {}
    if isinstance(llm_slots, dict):
        for k, v in llm_slots.items():
            new_slots[k] = v

    # Regex overrides LLM for critical fields
    for k, v in (regex_slots or {}).items():
        if k in ["state", "age", "occupation", "income"]:
            new_slots[k] = v
        elif k not in new_slots or new_slots.get(k) in [None, "", 0, False]:
            new_slots[k] = v

    normalized: Dict[str, Any] = {}
    for k, v in new_slots.items():
        normalized[k] = _normalize_value(k, v)

    # Validate age
    if "age" in normalized:
        age_val = normalized.get("age")
        if isinstance(age_val, int) and not (10 <= age_val <= 120):
            normalized.pop("age", None)

    state["_extracted_slots"] = normalized

    critical_keys = ["state", "age", "income", "occupation", "gender"]
    conflicts: Dict[str, Any] = {}
    pending_updates: Dict[str, Any] = {}
    for k in critical_keys:
        if k in normalized and normalized.get(k) not in [None, ""]:
            prev = current_slots.get(k)
            newv = normalized.get(k)
            if prev not in [None, ""] and prev != newv:
                conflicts[k] = {"from": prev, "to": newv}
                pending_updates[k] = newv
            else:
                current_slots[k] = newv

    if conflicts:
        state["pending_conflicts"] = conflicts
        state["needs_confirmation"] = True
        state["pending_updates"] = pending_updates
        state["eligible_schemes"] = []
        state["last_presented_eligible_scheme_ids"] = []
        state["last_presented_eligible_scheme_names"] = []
        state["last_referenced_scheme_id"] = None
        state["last_referenced_scheme_name"] = None

        state["response"] = _conflict_prompt_te(conflicts)
        state["next_action"] = "end"

        if "state" in conflicts:
            # State change invalidates any scheme-specific follow-ups, but if we were
            # in the middle of collecting eligibility slots, keep that flow running.
            if state.get("pending_followup") in {"choose_scheme_from_eligibility", "scheme_details"}:
                state["pending_followup"] = None
            if state.get("last_question_slot") == "state":
                state["last_question_slot"] = None
    else:
        state["pending_conflicts"] = {}
        state["needs_confirmation"] = False
        state["pending_updates"] = {}

    for k, v in normalized.items():
        if k in critical_keys:
            continue
        if v is not None:
            current_slots[k] = v

    last_slot = state.get("last_question_slot")
    extracted_this_turn = state.get("_extracted_slots") or {}
    if last_slot and isinstance(extracted_this_turn, dict):
        if extracted_this_turn.get(last_slot) not in [None, ""]:
            state["last_question_slot"] = None
    state["slots"] = current_slots
    return state


def intent_slot_extraction_node(state: AgentState) -> AgentState:
    # If we are waiting on contradiction confirmation and user confirms, apply the pending updates.
    if state.get("needs_confirmation") and _is_confirmation_response(state.get("user_text", "")):
        pending_updates = state.get("pending_updates") or {}
        slots = (state.get("slots") or {}).copy()
        if isinstance(pending_updates, dict):
            for k, v in pending_updates.items():
                if v not in [None, ""]:
                    slots[k] = v
        state["slots"] = slots
        state["pending_updates"] = {}
        state["pending_conflicts"] = {}
        state["needs_confirmation"] = False
        state["response"] = "సరే, మీ సమాచారాన్ని అప్డేట్ చేశాను."
        state["next_action"] = "end"
        return state

    state = intent_detection_node(state)
    state = slot_extraction_node(state)
    return state


def planner_node(state: AgentState) -> AgentState:
    intent = state.get("intent", "unknown")
    slots = state.get("slots", {})
    user_text = state.get("user_text", "")

    # Follow-up flows should never go to knowledge node.
    if state.get("pending_followup") in {"choose_scheme_from_eligibility", "scheme_details"}:
        state["next_action"] = "eligibility"
        return state
    
    if state.get("response"):
        state["next_action"] = "end"
        return state
    
    if intent == "greeting":
        state["response"] = "నమస్కారం! నేను ప్రభుత్వ పథకాల సహాయకుడిని. మీకు ఏ విధంగా సహాయం చేయాలి? (ఉదా: పథకాల వివరాలు / అర్హత చెక్)"
        state["next_action"] = "end"
        return state
    
    if intent in {"time_query", "name_query", "scheme_criteria"}:
        state["next_action"] = "eligibility"
        return state
    
    # Direct profile questions should be answered in response_generation_node.
    if any(k in user_text for k in ["నా వయసు", "నా వయస్సు", "my age", "నా ఆదాయం", "my income", "annual income"]):
        state["next_action"] = "eligibility"
        return state
    
    if intent == "scheme_list":
        state["next_action"] = "knowledge"
        return state
    
    # FIXED: Don't route scheme_info to knowledge if it's actually eligibility
    if intent == "scheme_info" and not any(k in state.get("user_text", "") for k in ["పెన్షన్", "అర్హత", "వస్తుందా"]):
        state["next_action"] = "knowledge"
        return state
    
    if intent == "unknown":
        state["next_action"] = "knowledge"
        return state
    
    if intent == "scheme_search" and not slots:
        state["next_action"] = "knowledge"
        return state
    
    if intent in ["eligibility_check", "apply"] and not slots:
        state["next_action"] = "clarification"
        return state
    
    if intent in ["scheme_search", "eligibility_check", "apply"]:
        state["next_action"] = "eligibility"
        return state
    
    state["next_action"] = "knowledge"
    return state


def clarification_node(state: AgentState) -> AgentState:
    slots = state.get("slots", {})
    missing = [s for s in REQUIRED_SLOTS if slots.get(s) in [None, ""]]
    next_slot = missing[0] if missing else None
    state["last_question_slot"] = next_slot
    state["pending_followup"] = "eligibility_clarification"
    q = _next_question_for_missing(missing) if missing else "మీ అర్హత చెక్ చేయడానికి మీ వయసు లేదా వృత్తి లేదా ఆదాయం వివరాలు చెప్పగలరా?"
    state["response"] = q
    return state


def eligibility_check_node(state: AgentState) -> AgentState:
    slots = state.get("slots", {})

    profile: Dict[str, Any] = {}
    if "age" in slots and slots["age"] is not None:
        try:
            profile["age"] = int(slots["age"])
        except Exception:
            pass

    if "income" in slots and slots["income"] is not None:
        try:
            profile["income"] = int(slots["income"])
        except Exception:
            pass

    for key in [
        "gender",
        "occupation",
        "state",
        "disability",
        "caste",
        "religion",
        "has_children",
        "pregnant",
        "location",
        "land_owner",
    ]:
        if key in slots and slots[key] is not None:
            profile[key] = slots[key]

    print(f"[ELIGIBILITY_CHECK] Profile: {profile}")
    eligible = check_eligibility(profile)
    state["eligible_schemes"] = eligible
    print(f"[ELIGIBILITY_CHECK] Eligible schemes: {eligible}")
    return state


def correction_handler_node(state: AgentState) -> AgentState:
    user_text = state.get("user_text", "")
    slots = state.get("slots", {})
    last_slot = state.get("last_question_slot")
    
    if not last_slot:
        return state
    
    correction_words = ["కాదు", "తప్పు", "నో", "not", "wrong"]
    if any(w in user_text.lower() for w in correction_words) or any(w in user_text for w in ["కాదు", "తప్పు"]):
        extracted_this_turn = state.get("_extracted_slots", {})
        # If this turn actually provided ANY corrected slot value (common: state correction like
        # "AP కాదు తెలంగాణ"), do not wipe the previously asked slot.
        if isinstance(extracted_this_turn, dict):
            for _k, _v in extracted_this_turn.items():
                if _v not in [None, ""]:
                    return state
        
        if last_slot in slots:
            slots[last_slot] = None
            state["slots"] = slots
            state["response"] = "సరే, మీరు చెప్పినది సరిచేస్తాను. " + _next_question_for_missing([last_slot])
            state["next_action"] = "end"
            return state
    return state


def knowledge_answer_node(state: AgentState) -> AgentState:
    slots = state.get("slots", {})
    user_text = state.get("user_text", "")

    if state.get("intent") == "scheme_list":
        user_state = slots.get("state")
        if user_state not in ["AP", "TS"]:
            state["last_question_slot"] = "state"
            state["pending_followup"] = "eligibility_clarification"
            state["response"] = "మీరు ఏ రాష్ట్రానికి చెందినవారు? తెలంగాణా లేదా ఆంధ్రప్రదేశ్?"
            return state

        schemes = _SCHEMES_MASTER.get(user_state, [])
        scheme_names = [s.get("scheme_name_te") for s in schemes[:12]]
        scheme_names = [n for n in scheme_names if n]

        response_lines = [f"{user_state} రాష్ట్రంలో అందుబాటులో ఉన్న కొన్ని ముఖ్యమైన పథకాలు:"]
        for i, name in enumerate(scheme_names[:10], start=1):
            response_lines.append(f"{i}. {name}")
        response_lines.append("\nమీకు ఏ పథకం గురించి వివరంగా తెలుసుకోవాలి?")
        state["response"] = "\n".join(response_lines)
        return state

    pending_followup = state.get("pending_followup")
    last_scheme_id = state.get("last_referenced_scheme_id")
    last_scheme_name = state.get("last_referenced_scheme_name")
    short_yes = _is_affirmative_followup(user_text)

    asked_scheme_id, asked_scheme_name = _match_scheme_from_text_deterministic(user_text, slots.get("state"))
    if not asked_scheme_id:
        asked_scheme_id, asked_scheme_name = _identify_scheme_from_text(user_text, slots.get("state"))
    print(f"[KNOWLEDGE_NODE] Identified scheme: {asked_scheme_id} / {asked_scheme_name}")

    if asked_scheme_id:
        state["pending_followup"] = None
        details = get_scheme_details(asked_scheme_id)
        benefits = details.get("benefits", [])
        eligibility_text = details.get("eligibility") or ""
        docs = details.get("documents_required", [])
        offline = details.get("application_process", {}).get("offline", [])
        response_lines: List[str] = []
        response_lines.append(f"'{details.get('scheme_name', asked_scheme_name)}' పథకం వివరాలు:")
        if eligibility_text:
            response_lines.append(f"అర్హత: {eligibility_text}")
        if benefits:
            response_lines.append("లాభాలు:")
            for b in benefits[:5]:
                response_lines.append(f"- {b}")
        if docs:
            response_lines.append("కావాల్సిన పత్రాలు:")
            for d in docs[:6]:
                response_lines.append(f"- {d}")
        if offline:
            response_lines.append("దరఖాస్తు విధానం (ఆఫ్‌లైన్):")
            for step in offline[:5]:
                response_lines.append(f"- {step}")
        state["response"] = "\n".join(response_lines)
        state["last_referenced_scheme_id"] = asked_scheme_id
        state["last_referenced_scheme_name"] = details.get("scheme_name", asked_scheme_name)
        state["pending_followup"] = "scheme_details"
        return state

    if pending_followup == "scheme_details" and short_yes and last_scheme_id:
        details = get_scheme_details(last_scheme_id)
        docs = details.get("documents_required", [])
        offline = details.get("application_process", {}).get("offline", [])
        response_lines = [f"'{last_scheme_name or details.get('scheme_name', '')}' కోసం కావాల్సిన పత్రాలు:"]
        for d in docs[:8]:
            response_lines.append(f"- {d}")
        if offline:
            response_lines.append("")
            response_lines.append("దరఖాస్తు విధానం (ఆఫ్‌లైన్):")
            for step in offline[:6]:
                response_lines.append(f"- {step}")
        state["response"] = "\n".join([x for x in response_lines if x is not None and x != ""]) or "దయచేసి మీ ప్రశ్నను మళ్లీ చెప్పండి."
        state["pending_followup"] = None
        return state

    user_state = slots.get("state")
    if user_state in [None, ""]:
        state["last_question_slot"] = "state"
        state["pending_followup"] = "eligibility_clarification"
        state["response"] = "మీరు ఏ రాష్ట్రానికి చెందినవారు? తెలంగాణా లేదా ఆంధ్రప్రదేశ్?"
        return state

    if any(k in user_text for k in ["పథకాలు", "schemes", "లిస్ట్", "జాబితా", "ఏవి"]):
        if user_state in ["AP", "TS"]:
            schemes = _SCHEMES_MASTER.get(user_state, [])
            scheme_names = [s.get("scheme_name_te") for s in schemes[:10]]
            scheme_names = [n for n in scheme_names if n]
            response_lines = [f"{user_state} రాష్ట్రంలో అందుబాటులో ఉన్న కొన్ని ముఖ్యమైన పథకాలు:"]
            for i, name in enumerate(scheme_names[:8], start=1):
                response_lines.append(f"{i}. {name}")
            response_lines.append("\nమీకు ఏ పథకం గురించి వివరంగా తెలుసుకోవాలి?")
            state["response"] = "\n".join(response_lines)
            return state

    state["response"] = "దయచేసి మీ ప్రశ్నను మరొక విధంగా చెప్పండి (ఉదా: పథకం పేరు/అర్హత చెక్/దరఖాస్తు విధానం)."
    return state


def response_generation_node(state: AgentState) -> AgentState:
    intent = state.get("intent", "unknown")
    slots = state.get("slots", {})
    eligible_schemes = state.get("eligible_schemes", [])
    user_text = state.get("user_text", "")

    pending_followup = state.get("pending_followup")
    last_scheme_id = state.get("last_referenced_scheme_id")
    last_scheme_name = state.get("last_referenced_scheme_name")
    short_yes = _is_affirmative_followup(user_text)

    user_state = slots.get("state")

    if intent == "time_query":
        now = datetime.now().strftime("%H:%M")
        state["response"] = f"ఇప్పుడు సమయం {now}."
        return state

    if intent == "name_query":
        name_val = (slots.get("name") or "").strip() if isinstance(slots.get("name"), str) else None
        if not name_val:
            state["response"] = "మీ పేరు నాకు ఇప్పటివరకు తెలియదు. దయచేసి మీ పేరు చెప్పండి."
            return state
        state["response"] = f"మీ పేరు {name_val}."
        return state

    # Direct profile question: age (avoid hijacking children-age questions)
    if any(k in user_text for k in ["నా వయసు", "నా వయస్సు", "my age"]) or (
        any(k in user_text for k in ["వయసు ఎంత", "వయస్సు ఎంత"]) and "పిల్ల" not in user_text and "పిల్లల" not in user_text and "నా" in user_text
    ):
        age_val = slots.get("age")
        if age_val in [None, ""]:
            state["last_question_slot"] = "age"
            state["pending_followup"] = "eligibility_clarification"
            state["response"] = "మీ వయసు ఎంత?"
            return state
        state["response"] = f"మీ వయసు {age_val} సంవత్సరాలు."
        return state

    # Direct profile question: state
    if any(k in user_text for k in ["నా రాష్ట్రం", "నా స్టేట్", "my state", "state what", "which state"]) and any(
        k in user_text for k in ["ఏమిటి", "ఏది", "what", "which"]
    ):
        st_val = slots.get("state")
        if st_val in [None, ""]:
            state["last_question_slot"] = "state"
            state["pending_followup"] = "eligibility_clarification"
            state["response"] = "మీరు ఏ రాష్ట్రానికి చెందినవారు? తెలంగాణా లేదా ఆంధ్రప్రదేశ్?"
            return state
        if st_val == "TS":
            state["response"] = "మీ రాష్ట్రం తెలంగాణ."
            return state
        if st_val == "AP":
            state["response"] = "మీ రాష్ట్రం ఆంధ్రప్రదేశ్."
            return state
        state["response"] = f"మీ రాష్ట్రం {st_val}."
        return state

    # If user asks scheme criteria (requirements) like child-age, answer from scheme details.
    # LLM-driven intent: scheme_criteria
    criteria_markers = ["ఎంత వయసు", "వయసు ఎంత", "పిల్ల", "పిల్లల", "ఎంత ఉండాలి", "అర్హత ఏంటి", "క్రైటీరియా"]
    if intent == "scheme_criteria" or any(m in user_text for m in criteria_markers):
        crit_scheme_id, crit_scheme_name = _match_scheme_from_text_deterministic(user_text, user_state)
        if not crit_scheme_id:
            crit_scheme_id, crit_scheme_name = _identify_scheme_from_text(user_text, user_state)
        if crit_scheme_id:
            details = get_scheme_details(crit_scheme_id)
            eligibility_text = (details.get("eligibility") or "").strip()
            if eligibility_text:
                state["response"] = f"'{details.get('scheme_name', crit_scheme_name)}' పథకం అర్హత: {eligibility_text}"
            else:
                state["response"] = f"'{details.get('scheme_name', crit_scheme_name)}' పథకం అర్హత వివరాలు ప్రస్తుతం అందుబాటులో లేవు."
            state["last_referenced_scheme_id"] = crit_scheme_id
            state["last_referenced_scheme_name"] = details.get("scheme_name", crit_scheme_name)
            state["pending_followup"] = "scheme_details"
            return state

        state["response"] = "మీరు ఏ పథకం అర్హత గురించి అడుగుతున్నారు? (ఉదా: అమ్మ ఒడి / పెన్షన్ కానుక)"
        return state

    # If we just asked the user to choose one scheme from the eligible list, handle that here.
    if state.get("pending_followup") == "choose_scheme_from_eligibility":
        presented_ids = state.get("last_presented_eligible_scheme_ids") or []
        presented_names = state.get("last_presented_eligible_scheme_names") or []
        # If the user only says "తెలుసుకోవాలి/కావాలి" again, prompt them to pick a specific scheme.
        if short_yes:
            if presented_names:
                lines = ["దయచేసి ఏ పథకం గురించి వివరాలు కావాలో చెప్పండి (పేరు లేదా నంబర్)."]
                for i, nm in enumerate(presented_names[:8], start=1):
                    lines.append(f"{i}. {nm}")
                state["response"] = "\n".join(lines)
                return state
            state["pending_followup"] = None

        # Numeric selection: "1" / "2" etc.
        m = re.search(r"\b(\d{1,2})\b", user_text)
        if m and presented_ids:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(presented_ids):
                chosen_id = presented_ids[idx]
                chosen_name = presented_names[idx] if idx < len(presented_names) else None
                details = get_scheme_details(chosen_id)
                response_lines: List[str] = []
                response_lines.append(f"'{details.get('scheme_name', chosen_name)}' పథకం వివరాలు:")
                eligibility_text = details.get("eligibility") or ""
                if eligibility_text:
                    response_lines.append(f"అర్హత: {eligibility_text}")
                benefits = details.get("benefits", [])
                if benefits:
                    response_lines.append("లాభాలు:")
                    for b in benefits[:5]:
                        response_lines.append(f"- {b}")
                state["response"] = "\n".join(response_lines)
                state["last_referenced_scheme_id"] = chosen_id
                state["last_referenced_scheme_name"] = details.get("scheme_name", chosen_name)
                state["pending_followup"] = "scheme_details"
                return state

        # Name selection (deterministic, restricted to presented list)
        chosen_id, chosen_name = _match_scheme_from_text_deterministic(
            user_text,
            user_state,
            restrict_scheme_ids=presented_ids,
        )
        if chosen_id:
            details = get_scheme_details(chosen_id)
            response_lines = [f"'{details.get('scheme_name', chosen_name)}' పథకం వివరాలు:"]
            eligibility_text = details.get("eligibility") or ""
            if eligibility_text:
                response_lines.append(f"అర్హత: {eligibility_text}")
            benefits = details.get("benefits", [])
            if benefits:
                response_lines.append("లాభాలు:")
                for b in benefits[:5]:
                    response_lines.append(f"- {b}")
            state["response"] = "\n".join(response_lines)
            state["last_referenced_scheme_id"] = chosen_id
            state["last_referenced_scheme_name"] = details.get("scheme_name", chosen_name)
            state["pending_followup"] = "scheme_details"
            return state

        # If we couldn't resolve the choice, ask again.
        if presented_names:
            lines = ["దయచేసి ఏ పథకం గురించి వివరాలు కావాలో చెప్పండి (పేరు లేదా నంబర్)."]
            for i, nm in enumerate(presented_names[:8], start=1):
                lines.append(f"{i}. {nm}")
            state["response"] = "\n".join(lines)
            return state

    # Direct profile question: income
    if any(k in user_text for k in ["నా ఆదాయం", "my income", "ఆదాయం ఎంత", "income ఎంత", "annual income"]):
        inc_val = slots.get("income")
        if inc_val in [None, ""]:
            state["last_question_slot"] = "income"
            state["pending_followup"] = "eligibility_clarification"
            state["response"] = "మీ వార్షిక ఆదాయం సుమారు ఎంత?"
            return state
        state["response"] = f"మీ వార్షిక ఆదాయం సుమారు {inc_val} రూపాయలు."
        return state

    # ============================================================
    # 🔥 CRITICAL FIX 1:
    # NEW scheme question must OVERRIDE previous eligibility list
    # ============================================================
    # First try deterministic match (works well for short utterances like "రైతు భరోసా")
    # Do NOT restrict to eligible schemes here; user may ask about any scheme.
    asked_scheme_id, asked_scheme_name = _match_scheme_from_text_deterministic(user_text, user_state)
    if not asked_scheme_id:
        asked_scheme_id, asked_scheme_name = _identify_scheme_from_text(user_text, user_state)

    if asked_scheme_id:
        # User explicitly asking eligibility for THIS scheme
        if intent == "eligibility_check":
            if asked_scheme_id in eligible_schemes:
                state["response"] = f"అవును 👍 మీరు '{asked_scheme_name}' పథకానికి అర్హులు."
            else:
                state["response"] = f"క్షమించాలి ❌ మీరు '{asked_scheme_name}' పథకానికి అర్హులు కారు."

            state["last_referenced_scheme_id"] = asked_scheme_id
            state["last_referenced_scheme_name"] = asked_scheme_name
            state["pending_followup"] = "scheme_details"
            return state

        # Otherwise user wants scheme info
        details = get_scheme_details(asked_scheme_id)
        response_lines: List[str] = []
        response_lines.append(f"'{details.get('scheme_name', asked_scheme_name)}' పథకం వివరాలు:")
        eligibility_text = details.get("eligibility") or ""
        if eligibility_text:
            response_lines.append(f"అర్హత: {eligibility_text}")
        benefits = details.get("benefits", [])
        if benefits:
            response_lines.append("లాభాలు:")
            for b in benefits[:5]:
                response_lines.append(f"- {b}")
        state["response"] = "\n".join(response_lines)
        state["last_referenced_scheme_id"] = asked_scheme_id
        state["last_referenced_scheme_name"] = details.get("scheme_name", asked_scheme_name)
        state["pending_followup"] = "scheme_details"
        return state

    # ============================================================
    # 🔁 Follow-up like "తెలుసుకోవాలి / కావాలి"
    # ============================================================
    if pending_followup == "scheme_details" and short_yes and last_scheme_id:
        details = get_scheme_details(last_scheme_id)
        docs = details.get("documents_required", [])
        offline = details.get("application_process", {}).get("offline", [])

        response_lines = [f"'{last_scheme_name or details.get('scheme_name', '')}' కోసం కావాల్సిన పత్రాలు:"]
        for d in docs[:8]:
            response_lines.append(f"- {d}")

        if offline:
            response_lines.append("\nదరఖాస్తు విధానం (ఆఫ్‌లైన్):")
            for step in offline[:6]:
                response_lines.append(f"- {step}")

        state["response"] = "\n".join([x for x in response_lines if x is not None and x != ""]) or "దయచేసి మీ ప్రశ్నను మళ్లీ చెప్పండి."
        state["pending_followup"] = None
        return state

    # ============================================================
    # 🧩 Missing slot clarification (state/age/etc.)
    # ============================================================
    if user_state in [None, ""]:
        state["last_question_slot"] = "state"
        state["pending_followup"] = "eligibility_clarification"
        state["response"] = "మీరు ఏ రాష్ట్రానికి చెందినవారు? తెలంగాణా లేదా ఆంధ్రప్రదేశ్?"
        return state

    if intent in ["eligibility_check", "scheme_search", "apply"]:
        missing = [s for s in REQUIRED_SLOTS if slots.get(s) in [None, ""]]
        if missing:
            state["last_question_slot"] = missing[0]
            state["pending_followup"] = "eligibility_clarification"
            state["response"] = _next_question_for_missing(missing)
            return state

    # ============================================================
    # ✅ FINAL FALLBACK:
    # Show eligible schemes ONLY if no scheme was asked
    # ============================================================
    scheme_names = []
    with open("data/schemes_master.json", encoding="utf-8") as f:
        schemes_data = json.load(f)

    if user_state in ["AP", "TS"]:
        for scheme in schemes_data.get(user_state, []):
            if scheme.get("scheme_id") in eligible_schemes:
                scheme_names.append(scheme.get("scheme_name_te"))

    scheme_names = [n for n in scheme_names if n]

    # If we have exactly one eligible scheme and user says a short affirmative follow-up,
    # treat it as asking details for that single scheme.
    if scheme_names and len(scheme_names) == 1 and short_yes and eligible_schemes:
        only_id = eligible_schemes[0]
        details = get_scheme_details(only_id)
        response_lines: List[str] = []
        response_lines.append(f"'{details.get('scheme_name', scheme_names[0])}' పథకం వివరాలు:")
        eligibility_text = details.get("eligibility") or ""
        if eligibility_text:
            response_lines.append(f"అర్హత: {eligibility_text}")
        benefits = details.get("benefits", [])
        if benefits:
            response_lines.append("లాభాలు:")
            for b in benefits[:5]:
                response_lines.append(f"- {b}")
        state["response"] = "\n".join(response_lines)
        state["last_referenced_scheme_id"] = only_id
        state["last_referenced_scheme_name"] = details.get("scheme_name", scheme_names[0])
        state["pending_followup"] = "scheme_details"
        return state

    if intent in ["eligibility_check", "scheme_search"] and scheme_names:
        response_lines = ["మీకు ఈ పథకాలు అర్హత ఉన్నాయి:"]
        for i, name in enumerate(scheme_names[:8], start=1):
            response_lines.append(f"{i}. {name}")
        response_lines.append("మీకు ఏ పథకం గురించి వివరంగా తెలుసుకోవాలి?")

        # Store presented ordering so the user can answer with a number or name.
        state["last_presented_eligible_scheme_ids"] = list(eligible_schemes or [])
        state["last_presented_eligible_scheme_names"] = list(scheme_names or [])

        # If exactly one scheme is eligible, store it so the next "తెలుసుకోవాలి" can work.
        if len(scheme_names) == 1 and eligible_schemes:
            state["last_referenced_scheme_id"] = eligible_schemes[0]
            state["last_referenced_scheme_name"] = scheme_names[0]
            state["pending_followup"] = "scheme_details"
        else:
            state["pending_followup"] = "choose_scheme_from_eligibility"
        state["response"] = "\n".join(response_lines)
        return state

    state["response"] = "మీకు ఏ విధంగా సహాయం చేయాలి? (ఉదా: పథక వివరాలు / అర్హత చెక్)"
    return state
