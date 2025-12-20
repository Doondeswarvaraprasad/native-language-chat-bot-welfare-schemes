# Telugu Government Voice Agent - LangGraph Multi-Agent System

## Overview

This is a *conversational AI system* built with *LangGraph* that helps Telugu-speaking citizens discover and apply for government welfare schemes through voice interaction.

## Key Features

### 1. Voice-First Native Language Interaction
- Users speak naturally in Telugu
- System responds only in Telugu
- No text dependency required

### 2. Eligibility Discovery
- Users don't need to know scheme names
- Agent asks intelligent questions
- Reasons about eligibility based on profile

### 3. Personalized Scheme Recommendation
- Based on: Age, Income, Gender, Occupation, State
- No generic answers
- Tailored to individual circumstances

### 4. Step-by-Step Application Guidance
- Documents required
- Where to apply
- Online/offline steps

### 5. Error & Contradiction Handling
- Missing info → asks again
- Conflicting info → clarifies
- Real-world robustness

### 6. Conversation Memory
- Remembers previous answers
- User doesn't repeat everything
- Maintains context across turns

## Architecture

### LangGraph Multi-Agent System

User Input
    ↓
[Input Node]
    ↓
[Intent + Slot Extraction Node]
    ↓
[Correction Handler Node]
    ↓
[Planner Node]
    ├─ [Knowledge Answer Node] → END
    ├─ [Clarification Node] → END
    └─ [Eligibility Check Node] → [Response Generation Node] → END
    ↓
Telugu Response

### State Management

python
class AgentState(TypedDict):
    user_text: str                    # Latest user input
    intent: str                       # greeting | scheme_info | scheme_search | scheme_list | scheme_criteria | eligibility_check | apply | time_query | name_query | unknown
    slots: Dict[str, Optional[str]]   # age, income, occupation, state
    missing_slots: List[str]          # What info is needed
    eligible_schemes: List[str]       # Matching schemes
    response: str                     # Telugu response
    history: List[Dict[str, str]]     # Conversation memory
    needs_confirmation: bool
    pending_conflicts: Dict
    next_action: str
    pending_followup: Optional[str]

## Conversation Flows

### Flow 1: Complete Information → Success

User: "నేను రైతును, తెలంగాణ నుండి, నా వయసు 35, ఆదాయం 2 లక్షలు"

Agent:
  1. Intent: scheme_search
  2. Slots: {occupation: farmer, state: TS, age: 35, income: 200000}
  3. Missing: None
  4. Eligible: [TS_RYTHU_BANDHU, TS_RYTHU_BHEEMA]
  5. Response: "మీకు ఈ పథకాలు అర్హత ఉన్నాయి:
                1. రైతు బంధు
                2. రైతు బీమా"

### Flow 2: Missing Information → Intelligent Questioning

User: "నాకు ప్రభుత్వ పథకం కావాలి"

Agent:
  1. Intent: scheme_search
  2. Slots: {}
  3. Missing: [age, income, occupation, state]
  4. Response: "మీ వయసు ఎంత?"

User: "35 సంవత్సరాలు"

Agent:
  1. Slots: {age: 35}
  2. Missing: [income, occupation, state]
  3. Response: "మీ వృత్తి ఏమిటి?"

### Flow 3: Contradiction Handling → Clarification

User: "నా ఆదాయం 1.5 లక్షలు"
Agent: [Stores income: 150000]

User: "నా ఆదాయం 5 లక్షలు"
Agent: [Detects conflict]
Response: "మీరు చెప్పిన వివరాల్లో తేడా ఉంది:
          ఆదాయం: ముందు 150000 అన్నారు, ఇప్పుడు 500000 చెప్పారు
          ఏది సరైనది? దయచేసి నిర్ధారించండి."

User: "5 లక్షలు సరైనది"
Agent: [Updates to 500000]
Response: "సరే, వివరాలు నవీకరించబడ్డాయి."

## File Structure

telugu_govt_voice_agent/
├── app.py                      # Flask app entrypoint (LangGraph)
├── graph/
│   ├── __init__.py
│   ├── state.py                 # AgentState TypedDict
│   ├── nodes.py                 # All graph nodes
│   └── workflow.py              # Workflow graph + run_agent()
├── tools/
│   └── eligibility_engine.py  # Tool for checking eligibility
└── data/
    ├── schemes_master.json    # All schemes
    └── eligibility_rules.json # Eligibility criteria

## Installation

bash
cd telugu_govt_voice_agent
pip install -r requirements.txt

## Configuration

Create .env file:

GROQ_API_KEY=your_groq_api_key_here

## Running the Application

bash
python app.py

Access at: http://localhost:5000

## API Endpoints

### POST /agent
Send user text, get Telugu response
json
Request:
{
  "text": "నేను రైతును తెలంగాణ నుండి"
}

Response:
{
  "response": "మీ వయసు ఎంత?",
  "intent": "scheme_search",
  "slots": {"occupation": "farmer", "state": "TS"},
  "missing_slots": ["age", "income"],
  "eligible_schemes": [],
  "needs_confirmation": false
}

### GET /reset
Reset conversation state

### GET /history
Get conversation history

## Agent Nodes Explained

### 1. Intent + Slot Extraction Node
- Classifies user intent using Groq
- Extracts/updates structured profile fields from Telugu text

### 2. Planner Node
- Chooses what to do next (knowledge_answer, clarification, or eligibility_check)

### 3. Knowledge Answer Node
- Answers scheme details / scheme list questions
- Uses deterministic scheme matching first, then LLM scheme identification if needed

### 4. Eligibility Check Node
- Calls tools/eligibility_engine.py to compute eligible schemes

### 5. Response Generation Node
- Generates Telugu responses
- Handles follow-ups (scheme selection, scheme documents, etc.)

## Routing Logic

python
input
    ↓
intent_slot_extraction
    ↓
correction_handler
    ↓
planner
    ├─ knowledge_answer → END
    ├─ clarification → END
    └─ eligibility_check → response_generation → END

## Tool Integration

### Eligibility Engine Tool
python
def check_eligibility(profile: dict) -> List[str]:
    """
    Checks user profile against eligibility rules
    Returns list of eligible scheme IDs
    """

## Memory Management

- *Short-term memory*: Current conversation state
- *Persistent memory*: Saved to session_memory.json
- *History*: Last 20 conversation turns
- *Slots*: Accumulated user profile data

## Supported Fields

- *state*: TS (Telangana), AP (Andhra Pradesh)
- *age*: Numeric value
- *gender*: male, female
- *occupation*: farmer, laborer, employee, weaver, driver, fisherman
- *income*: Annual income in rupees
- *location*: rural, urban
- *disability*: true/false
- *caste*: sc, st, obc, kapu
- *religion*: hindu, muslim, christian, minority
- *has_children*: true/false
- *pregnant*: true/false
- *land_owner*: true/false

## Example Schemes

### Telangana (TS)
- రైతు బంధు (Rythu Bandhu)
- రైతు బీమా (Rythu Bheema)
- ఆసరా పెన్షన్ (Aasara Pension)
- కళ్యాణ లక్ష్మి (Kalyana Lakshmi)

### Andhra Pradesh (AP)
- రైతు భరోసా (Rythu Bharosa)
- అమ్మ ఒడి (Amma Vodi)
- పెన్షన్ కానుక (Pension Kanuka)
- ఆసరా (Asara)

## Testing

Test the system with these scenarios:

1. *Complete information*:
   - "నేను రైతును తెలంగాణ నుండి నా వయసు 35 ఆదాయం 2 లక్షలు"

2. *Incomplete information*:
   - "నాకు పథకం కావాలి"

3. *Contradictory information*:
   - First: "నా వయసు 30"
   - Later: "నా వయసు 40"

4. *Confirmation*:
   - After conflict: "అవును సరైనది"

## Advantages of LangGraph Implementation

- *Stateful*: Maintains conversation context
- *Modular*: Each node has single responsibility
- *Debuggable*: Clear flow visualization
- *Extensible*: Easy to add new nodes
- *Robust*: Handles errors and edge cases
- *Tool-enabled*: Integrates with external tools
- *Memory-aware*: Persistent state management

## Future Enhancements

- [ ] Add document requirement node
- [ ] Add application submission node
- [ ] Add multi-language support (Tamil, Hindi)
- [ ] Add voice input/output integration
- [ ] Add scheme comparison node
- [ ] Add feedback collection node
- [ ] Add analytics dashboard

## Troubleshooting

*Issue*: Agent not responding in Telugu
- Check GROQ_API_KEY in .env
- Verify model availability

*Issue*: Schemes not matching
- Check eligibility_rules.json
- Verify slot values are correctly extracted

*Issue*: State not persisting
- Check session_memory.json file permissions
- Verify file is being written