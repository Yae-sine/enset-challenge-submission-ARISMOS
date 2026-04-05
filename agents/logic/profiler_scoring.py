"""Scoring utilities for the Profileur agent."""


def _calculate_domain_scores_fallback(
    serie_bac: str,
    notes: dict[str, float],
    interets: list[str]
) -> dict[str, float]:
    """
    Fallback calculation if LLM fails to return valid JSON.
    Implements the weighted scoring formula from the spec.
    """
    # Normalize notes to 0-1 scale
    normalized = {k: min(1.0, v / 20.0) for k, v in notes.items()}

    # Calculate base scores by serie
    if serie_bac == "Sciences":
        sciences = (
            normalized.get("maths", 0.5) * 0.3
            + normalized.get("physique", 0.5) * 0.25
            + normalized.get("svt", 0.5) * 0.2
            + normalized.get("francais", 0.5) * 0.125
            + normalized.get("arabe", 0.5) * 0.125
        )
        tech = sciences * 0.9
        lettres = (
            normalized.get("francais", 0.5) * 0.4
            + normalized.get("arabe", 0.5) * 0.3
            + normalized.get("histoire_geo", 0.5) * 0.3
        )
        economie = (
            normalized.get("maths", 0.5) * 0.5
            + normalized.get("francais", 0.5) * 0.25
            + lettres * 0.25
        )
    elif serie_bac == "Lettres":
        lettres = (
            normalized.get("arabe", 0.5) * 0.3
            + normalized.get("francais", 0.5) * 0.25
            + normalized.get("histoire_geo", 0.5) * 0.25
            + normalized.get("philo", 0.5) * 0.2
        )
        sciences = lettres * 0.4
        tech = sciences * 0.5
        economie = lettres * 0.6
    elif serie_bac == "Economie":
        economie = (
            normalized.get("maths", 0.5) * 0.25
            + normalized.get("economie", 0.5) * 0.3
            + normalized.get("compta", 0.5) * 0.25
            + normalized.get("francais", 0.5) * 0.2
        )
        sciences = economie * 0.5
        tech = economie * 0.4
        lettres = economie * 0.6
    elif serie_bac == "Technique":
        tech = (
            normalized.get("maths", 0.5) * 0.25
            + normalized.get("physique", 0.5) * 0.2
            + normalized.get("techno", 0.5) * 0.35
            + normalized.get("francais", 0.5) * 0.2
        )
        sciences = tech * 0.8
        lettres = tech * 0.3
        economie = tech * 0.5
    else:
        # Default balanced scores
        avg = sum(normalized.values()) / max(len(normalized), 1)
        sciences = tech = lettres = economie = avg

    # Adjust for interests
    interest_mapping = {
        "informatique": "tech",
        "robotique": "tech",
        "programmation": "tech",
        "ia": "tech",
        "maths": "sciences",
        "physique": "sciences",
        "chimie": "sciences",
        "biologie": "sciences",
        "littérature": "lettres",
        "langues": "lettres",
        "histoire": "lettres",
        "philosophie": "lettres",
        "droit": "lettres",
        "commerce": "economie",
        "gestion": "economie",
        "finance": "economie",
        "marketing": "economie",
        "entrepreneuriat": "economie",
    }

    adjustments = {"sciences": 0, "tech": 0, "lettres": 0, "economie": 0}

    for interet in interets:
        interet_lower = interet.lower()
        for key, domain in interest_mapping.items():
            if key in interet_lower:
                adjustments[domain] = min(adjustments[domain] + 0.1, 0.3)
                break

    # Apply adjustments and clamp to 0-1
    return {
        "sciences": min(1.0, max(0.0, sciences + adjustments["sciences"])),
        "tech": min(1.0, max(0.0, tech + adjustments["tech"])),
        "lettres": min(1.0, max(0.0, lettres + adjustments["lettres"])),
        "economie": min(1.0, max(0.0, economie + adjustments["economie"])),
    }


def _determine_learning_style(interets: list[str], serie_bac: str) -> str:
    """Determine learning style from interests and serie."""
    practical_keywords = ["robotique", "programmation", "projet", "stage", "pratique"]
    theoretical_keywords = ["recherche", "théorie", "maths", "philosophie"]

    interets_lower = " ".join(interets).lower()

    practical_count = sum(1 for kw in practical_keywords if kw in interets_lower)
    theoretical_count = sum(1 for kw in theoretical_keywords if kw in interets_lower)

    if practical_count > theoretical_count + 1:
        return "pratique"
    elif theoretical_count > practical_count + 1:
        return "theorique"
    return "mixte"
