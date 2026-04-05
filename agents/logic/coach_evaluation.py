"""Interview evaluation utilities for the Coach Entretien agent."""


def compute_interview_score(evaluations: list[dict]) -> dict:
    """
    Compute the final interview score from individual question evaluations.

    Each evaluation has: clarte (0-10), motivation (0-10), connaissance (0-10)
    Final score is /100, with strengths and improvement axes identified.

    Args:
        evaluations: List of evaluation dicts from evaluate_answer

    Returns:
        Dict with score, points_forts, axes_amelioration, and details
    """
    if not evaluations:
        return {
            "score": 0,
            "points_forts": ["Aucune évaluation disponible"],
            "axes_amelioration": ["Complétez l'entretien pour recevoir un feedback"],
        }

    # Calculate averages per axis
    avg_clarte = sum(e.get("clarte", 5) for e in evaluations) / len(evaluations)
    avg_motivation = (
        sum(e.get("motivation", 5) for e in evaluations) / len(evaluations)
    )
    avg_connaissance = (
        sum(e.get("connaissance", 5) for e in evaluations) / len(evaluations)
    )

    # Final score: average of three axes, scaled to /100
    final_score = int((avg_clarte + avg_motivation + avg_connaissance) / 3 * 10)
    final_score = min(100, max(0, final_score))

    # Determine strengths and weaknesses
    axis_scores = [
        ("Clarté et expression", avg_clarte),
        ("Motivation et projet professionnel", avg_motivation),
        ("Connaissance de la filière", avg_connaissance),
    ]

    # Sort to find best and worst
    sorted_axes = sorted(axis_scores, key=lambda x: x[1], reverse=True)

    points_forts = []
    axes_amelioration = []

    # Best axes (score >= 6)
    for name, score in sorted_axes:
        if score >= 7:
            points_forts.append(f"{name} : excellent ({score:.1f}/10)")
        elif score >= 5:
            if len(points_forts) < 2:
                points_forts.append(f"{name} : satisfaisant ({score:.1f}/10)")

    # Axes to improve (score < 6)
    for name, score in reversed(sorted_axes):
        if score < 6:
            axes_amelioration.append(f"{name} : à renforcer ({score:.1f}/10)")
        elif score < 7 and len(axes_amelioration) < 2:
            axes_amelioration.append(f"{name} : peut progresser ({score:.1f}/10)")

    # Ensure we have at least some feedback
    if not points_forts:
        points_forts = ["Participation à l'entretien", "Effort de réponse"]
    if not axes_amelioration:
        axes_amelioration = ["Continuer à se préparer aux entretiens"]

    # Add specific advice based on scores
    if avg_clarte < 5:
        axes_amelioration.append(
            "Conseil : Structure tes réponses en introduction-développement-conclusion"
        )
    if avg_motivation < 5:
        axes_amelioration.append(
            "Conseil : Prépare des exemples concrets qui illustrent ta motivation"
        )
    if avg_connaissance < 5:
        axes_amelioration.append(
            "Conseil : Recherche davantage sur les débouchés et le contenu de la formation"
        )

    return {
        "score": final_score,
        "points_forts": points_forts[:3],
        "axes_amelioration": axes_amelioration[:3],
        "details": {
            "clarte_moyenne": round(avg_clarte, 1),
            "motivation_moyenne": round(avg_motivation, 1),
            "connaissance_moyenne": round(avg_connaissance, 1),
        },
    }
