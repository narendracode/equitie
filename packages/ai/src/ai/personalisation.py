def compute_mode(investor_profile: dict) -> str:
    """
    Scoring per system design:
      +2  tech_savviness == High
      +1  tech_savviness == Medium
      +1  deal_count >= 5
      +1  age < 50  (individuals only)
      -1  age >= 65 (individuals only)

    Thresholds:
      score >= 3  → expert
      score == 2  → standard
      score <= 1  → simplified
    """
    score = 0

    savviness = investor_profile.get("tech_savviness", "Low")
    if savviness == "High":
        score += 2
    elif savviness == "Medium":
        score += 1

    if investor_profile.get("deal_count", 0) >= 5:
        score += 1

    age = investor_profile.get("age")
    if age is not None:
        if age < 50:
            score += 1
        elif age >= 65:
            score -= 1

    if score >= 3:
        return "expert"
    if score == 2:
        return "standard"
    return "simplified"
