import json
import os

def get_scheme_details(scheme_id: str, language: str = "te") -> dict:
    """
    Tool to get detailed information about a specific scheme
    
    Args:
        scheme_id: Scheme identifier (e.g., TS_RYTHU_BANDHU)
        language: Language code (te for Telugu, en for English)
    
    Returns:
        Dictionary with scheme details including:
        - scheme_name
        - description
        - benefits
        - documents_required
        - application_process
        - eligibility_criteria
    """
    
    with open("data/schemes_master.json", encoding="utf-8") as f:
        schemes_master = json.load(f)
    
    scheme_name = None
    state = None
    
    for st, schemes in schemes_master.items():
        for scheme in schemes:
            if scheme["scheme_id"] == scheme_id:
                scheme_name = scheme["scheme_name_te"]
                state = st
                break
    
    if not scheme_name:
        return {"error": "Scheme not found"}
    
    details = {
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
        "state": state,
        "description": f"{scheme_name} పథకం {state} రాష్ట్ర ప్రభుత్వం అందిస్తున్న సంక్షేమ పథకం",
        "benefits": get_scheme_benefits(scheme_id),
        "documents_required": get_required_documents(scheme_id),
        "application_process": get_application_process(scheme_id),
        "eligibility": get_eligibility_text(scheme_id)
    }
    
    return details


def get_scheme_benefits(scheme_id: str) -> list:
    """Get benefits for a specific scheme"""
    
    benefits_map = {
        "TS_RYTHU_BANDHU": [
            "ఎకరానికి రూ. 5000 ఆర్థిక సహాయం",
            "సంవత్సరానికి రెండు సార్లు చెల్లింపు",
            "నేరుగా బ్యాంకు ఖాతాలో జమ"
        ],
        "TS_RYTHU_BHEEMA": [
            "రైతు మరణించినప్పుడు రూ. 5 లక్షల బీమా",
            "కుటుంబానికి ఆర్థిక భద్రత",
            "ప్రీమియం ప్రభుత్వం చెల్లిస్తుంది"
        ],
        "AP_RYTHU_BHAROSA": [
            "ఎకరానికి రూ. 7500 ఆర్థిక సహాయం",
            "సంవత్సరానికి ఒకసారి చెల్లింపు",
            "నేరుగా బ్యాంకు ఖాతాలో జమ"
        ],
        "AP_AMMA_VODI": [
            "పిల్లల చదువుకు సంవత్సరానికి రూ. 15000",
            "తల్లుల ఖాతాలో నేరుగా జమ",
            "విద్యా ఖర్చులకు మద్దతు"
        ]
    }
    
    return benefits_map.get(scheme_id, ["పథకం వివరాలు త్వరలో అందుబాటులో ఉంటాయి"])


def get_required_documents(scheme_id: str) -> list:
    """Get required documents for a specific scheme"""
    
    common_docs = [
        "ఆధార్ కార్డు",
        "రేషన్ కార్డు",
        "బ్యాంకు పాస్‌బుక్",
        "ఫోటో"
    ]
    
    scheme_specific = {
        "TS_RYTHU_BANDHU": ["పట్టా పత్రాలు", "భూ రికార్డులు"],
        "TS_RYTHU_BHEEMA": ["పట్టా పత్రాలు", "భూ రికార్డులు"],
        "AP_RYTHU_BHAROSA": ["పట్టా పత్రాలు", "భూ రికార్డులు"],
        "AP_AMMA_VODI": ["పిల్లల పాఠశాల సర్టిఫికెట్", "తల్లి ఆధార్"],
        "TS_KALYANA_LAKSHMI": ["వివాహ ఆహ్వాన పత్రిక", "వయస్సు ధృవీకరణ పత్రం"],
        "TS_AASARA": ["వయస్సు ధృవీకరణ పత్రం", "ఆదాయ ధృవీకరణ పత్రం"]
    }
    
    specific = scheme_specific.get(scheme_id, [])
    return common_docs + specific


def get_application_process(scheme_id: str) -> dict:
    """Get application process steps"""
    
    return {
        "online": [
            "అధికారిక వెబ్‌సైట్‌కు వెళ్లండి",
            "లాగిన్ చేయండి లేదా రిజిస్టర్ చేయండి",
            "పథకం ఎంచుకోండి",
            "వివరాలు నింపండి",
            "పత్రాలు అప్‌లోడ్ చేయండి",
            "సబ్మిట్ చేయండి"
        ],
        "offline": [
            "సమీప గ్రామ సచివాలయం/మీసేవ కేంద్రానికి వెళ్లండి",
            "దరఖాస్తు ఫారం తీసుకోండి",
            "వివరాలు నింపండి",
            "అవసరమైన పత్రాలు జతచేయండి",
            "సబ్మిట్ చేయండి"
        ],
        "helpline": "1800-XXX-XXXX"
    }


def get_eligibility_text(scheme_id: str) -> str:
    """Get human-readable eligibility criteria"""
    
    with open("data/eligibility_rules.json", encoding="utf-8") as f:
        rules = json.load(f)
    
    for rule in rules:
        if rule["scheme_id"] == scheme_id:
            criteria = rule["rules"]
            
            if not criteria:
                return "అందరికీ అర్హత ఉంది"
            
            text_parts = []
            
            if "age_min" in criteria:
                text_parts.append(f"వయస్సు {criteria['age_min']} సంవత్సరాలు పైబడి ఉండాలి")
            
            if "age_range" in criteria:
                text_parts.append(f"వయస్సు {criteria['age_range'][0]} నుండి {criteria['age_range'][1]} మధ్య ఉండాలి")
            
            if "gender" in criteria:
                gender_te = "మహిళ" if criteria["gender"] == "female" else "పురుషుడు"
                text_parts.append(f"{gender_te} అయి ఉండాలి")
            
            if "occupation" in criteria:
                occ_map = {
                    "farmer": "రైతు",
                    "weaver": "నేత కార్మికుడు",
                    "fisherman": "మత్స్యకారుడు",
                    "driver": "డ్రైవర్"
                }
                text_parts.append(f"{occ_map.get(criteria['occupation'], criteria['occupation'])} అయి ఉండాలి")
            
            if "income_below" in criteria:
                text_parts.append(f"వార్షిక ఆదాయం రూ. {criteria['income_below']} కంటే తక్కువ ఉండాలి")
            
            return ", ".join(text_parts)
    
    return "అర్హత వివరాలు అందుబాటులో లేవు"


def get_schemes_by_category(category: str, state: str = None) -> list:
    """
    Get schemes by category
    
    Categories: farmer, pension, women, student, housing, health, employment
    """
    
    category_map = {
        "farmer": ["RYTHU", "BHAROSA", "BANDHU", "BHEEMA"],
        "pension": ["PENSION", "AASARA", "OLD_AGE", "DISABLED"],
        "women": ["AMMA", "KALYANA", "LAKSHMI", "SHAADI", "CHEYYUTHA"],
        "student": ["SCHOLARSHIP", "FEE", "STUDENT"],
        "housing": ["HOUSING", "2BHK"],
        "health": ["AROGYASRI", "HEALTH", "KCR_KIT"],
        "employment": ["UNEMPLOYMENT", "SKILL", "SELF_EMPLOYMENT"]
    }
    
    keywords = category_map.get(category.lower(), [])
    
    with open("data/schemes_master.json", encoding="utf-8") as f:
        schemes_master = json.load(f)
    
    results = []
    
    states_to_search = [state] if state else ["TS", "AP"]
    
    for st in states_to_search:
        if st in schemes_master:
            for scheme in schemes_master[st]:
                scheme_id = scheme["scheme_id"]
                if any(keyword in scheme_id for keyword in keywords):
                    results.append({
                        "scheme_id": scheme_id,
                        "scheme_name": scheme["scheme_name_te"],
                        "state": st
                    })
    
    return results
