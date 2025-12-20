import json

with open("data/eligibility_rules.json", encoding="utf-8") as f:
    RULES = json.load(f)

def check_eligibility(profile):
    eligible = []

    for rule in RULES:
        ok = True
        for k, v in rule["rules"].items():
            if k == "age_min":
                if profile.get("age") is None:
                    ok = False
                elif profile.get("age") < v:
                    ok = False
            elif k == "age_range":
                if profile.get("age") is None:
                    ok = False
                else:
                    a = profile.get("age")
                    if not (v[0] <= a <= v[1]):
                        ok = False
            elif k == "income_below":
                if profile.get("income") is None:
                    ok = False
                else:
                    income = profile.get("income")
                    if income > v:
                        ok = False
            else:
                # Strict matching: if a scheme rule requires a field, we must have it to confirm eligibility.
                if profile.get(k) is None:
                    ok = False
                elif profile.get(k) != v:
                    ok = False
        
        # If no rules specified (empty rules), scheme is universally eligible
        if not rule["rules"]:
            ok = True
            
        if ok:
            eligible.append(rule["scheme_id"])

    return eligible
