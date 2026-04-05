"""
Scoring utilities for the Conseiller agent.
"""

from graph.state import StudentProfile


def score_filiere(filiere: dict, profile: StudentProfile) -> float:
    """
    Calculate the final recommendation score for a filière.

    Scoring formula:
    - Profil alignment: 40%
    - Employment rate: 25%
    - Accessibility (ville + budget): 20%
    - Language match: 15%

    Returns:
        Score between 0 and 1
    """
    domain_scores = profile.get("domain_scores", {})
    constraints = profile.get("constraints", {})

    # 1. Profile alignment (40%)
    domaine = filiere.get("domaine", "tech")
    profil_score = domain_scores.get(domaine, 0.5) * 0.40

    # 2. Employment rate (25%)
    taux_emploi = filiere.get("taux_emploi", 70)
    if isinstance(taux_emploi, str):
        try:
            taux_emploi = int(taux_emploi)
        except ValueError:
            taux_emploi = 70
    emploi_score = (taux_emploi / 100) * 0.25

    # 3. Accessibility (20%)
    filiere_ville = filiere.get("ville", "")
    profile_ville = constraints.get("ville", profile.get("ville", ""))
    ville_match = 1.0 if filiere_ville.lower() == profile_ville.lower() else 0.5

    frais = filiere.get("frais_annuels_mad", 0)
    if isinstance(frais, str):
        try:
            frais = int(frais)
        except ValueError:
            frais = 0

    budget = constraints.get("budget", profile.get("budget", "public"))
    if budget == "public":
        budget_match = 1.0 if frais == 0 else 0.3
    elif budget == "prive_abordable":
        budget_match = 1.0 if frais <= 50000 else 0.5
    else:
        budget_match = 1.0

    acces_score = ((ville_match + budget_match) / 2) * 0.20

    # 4. Language match (15%)
    filiere_langue = filiere.get("langue_enseignement", "fr")
    profile_langue = constraints.get("langue", profile.get("langue", "fr"))
    langue_match = 1.0 if filiere_langue == profile_langue else 0.6
    langue_score = langue_match * 0.15

    total = profil_score + emploi_score + acces_score + langue_score
    return round(min(1.0, max(0.0, total)), 3)


def format_filieres_for_prompt(filieres: list[dict], profile: StudentProfile) -> str:
    """Format scored filières for the LLM prompt."""
    if not filieres:
        return "Aucune filière disponible."

    lines = []
    for i, filiere in enumerate(filieres[:8], 1):
        score = score_filiere(filiere, profile)
        lines.append(
            f"""
{i}. **{filiere.get('nom', 'N/A')}** (Score: {score:.0%})
   - Type: {filiere.get('type', 'N/A')} | Ville: {filiere.get('ville', 'N/A')}
   - Domaine: {filiere.get('domaine', 'N/A')}
   - Taux emploi: {filiere.get('taux_emploi', 'N/A')}% | Salaire: {filiere.get('salaire_moyen', 'N/A')} MAD
   - Conditions: {filiere.get('conditions_acces', 'N/A')}
   - Débouchés: {', '.join(filiere.get('debouches', [])[:3])}
"""
        )
    return "\n".join(lines)
