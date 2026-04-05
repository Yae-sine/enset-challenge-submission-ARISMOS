"""Utility functions for the Explorateur agent."""

from graph.state import StudentProfile


def build_rag_query(state: StudentProfile) -> str:
    """
    Build a semantic query for RAG retrieval based on student profile.
    """
    domain_scores = state.get("domain_scores", {})

    if not domain_scores:
        # Fallback if no scores yet
        return f"Formation {state.get('serie_bac', 'Sciences')} {state.get('ville', 'Maroc')} emploi"

    # Get top 2 domains
    sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
    top_domains = [d[0] for d in sorted_domains[:2]]

    query_parts = [
        f"Formation {' '.join(top_domains)}",
        f"Maroc {state.get('ville', '')}",
        f"série {state.get('serie_bac', 'Sciences')}",
        "débouchés emploi",
    ]

    return " ".join(query_parts)


def format_filieres_context(filieres: list[dict]) -> str:
    """Format retrieved filières as context for the LLM."""
    if not filieres:
        return "Aucune filière trouvée dans la base de données."

    lines = []
    for i, filiere in enumerate(filieres, 1):
        lines.append(
            f"""
{i}. **{filiere.get('nom', 'N/A')}** (ID: {filiere.get('id', 'N/A')})
   - Type: {filiere.get('type', 'N/A')} | Ville: {filiere.get('ville', 'N/A')} | Domaine: {filiere.get('domaine', 'N/A')}
   - Taux emploi: {filiere.get('taux_emploi', 'N/A')}% | Salaire moyen: {filiere.get('salaire_moyen_premier_emploi_mad', 'N/A')} MAD
   - Conditions: {filiere.get('conditions_acces', 'N/A')}
   - Série Bac: {filiere.get('serie_bac_requise', 'N/A')}
   - Débouchés: {filiere.get('debouches', 'N/A')}
"""
        )
    return "\n".join(lines)
