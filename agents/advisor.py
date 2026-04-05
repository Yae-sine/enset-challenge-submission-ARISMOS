"""
OrientAgent - Agent 3: Conseiller

Ranks filières and generates personalized recommendations with action plans.
"""

import json
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import StudentProfile


SYSTEM_PROMPT = """Tu es un conseiller d'orientation expert du contexte éducatif marocain.

Tu dois analyser les filières candidates et générer un top 3 personnalisé pour l'étudiant.

**Top filières candidates (pré-scorées) :**
{top_filieres_with_scores}

**Profil de l'étudiant :**
- Nom : {nom}
- Série Bac : {serie_bac}
- Ville : {ville}
- Budget : {budget}
- Langue préférée : {langue}
- Style d'apprentissage : {learning_style}
- Domain scores : {domain_scores}
- Centres d'intérêt : {interets}

**Ta mission :**
Pour le TOP 3, génère pour chaque filière :
1. Une **justification narrative personnalisée** (3-4 phrases, parle directement à l'étudiant en utilisant "tu/toi")
2. Un **plan d'action concret sur 30 jours** avec 5 étapes spécifiques
3. Les **établissements recommandés** dans ou près de sa ville
4. Les **prochaines étapes immédiates**

Réponds en JSON avec cette structure exacte :
{{
    "top_3": [
        {{
            "rang": 1,
            "filiere_id": "<id>",
            "filiere_nom": "<nom complet>",
            "type": "<type>",
            "ville": "<ville>",
            "score_final": <float 0-1>,
            "justification": "<3-4 phrases personnalisées>",
            "plan_action_30j": [
                "<étape 1 avec deadline>",
                "<étape 2 avec deadline>",
                "<étape 3 avec deadline>",
                "<étape 4 avec deadline>",
                "<étape 5 avec deadline>"
            ],
            "etablissements_recommandes": ["<établissement 1>", "<établissement 2>"],
            "prochaine_etape": "<action immédiate à faire cette semaine>"
        }}
    ]
}}

Sois encourageant et réaliste. Mentionne des éléments concrets du profil de l'étudiant."""


def score_filiere(filiere: dict, profile: StudentProfile) -> float:
    """
    Calculate the final recommendation score for a filière.
    
    Scoring formula:
    - Profil alignment: 40%
    - Employment rate: 25%
    - Accessibility (ville + budget): 20%
    - Language match: 15%
    
    Args:
        filiere: Filière dict with metadata
        profile: Student profile state
    
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
    # Ville match
    filiere_ville = filiere.get("ville", "")
    profile_ville = constraints.get("ville", profile.get("ville", ""))
    ville_match = 1.0 if filiere_ville.lower() == profile_ville.lower() else 0.5
    
    # Budget match
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
    else:  # prive_premium
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
    for i, f in enumerate(filieres[:8], 1):
        score = score_filiere(f, profile)
        lines.append(f"""
{i}. **{f.get('nom', 'N/A')}** (Score: {score:.0%})
   - Type: {f.get('type', 'N/A')} | Ville: {f.get('ville', 'N/A')}
   - Domaine: {f.get('domaine', 'N/A')}
   - Taux emploi: {f.get('taux_emploi', 'N/A')}% | Salaire: {f.get('salaire_moyen', 'N/A')} MAD
   - Conditions: {f.get('conditions_acces', 'N/A')}
   - Débouchés: {', '.join(f.get('debouches', [])[:3])}
""")
    return "\n".join(lines)


class ConseillerAgent:
    """
    Agent 3: Generates personalized recommendations with action plans.
    
    Scores all retrieved filières using the weighted formula and
    generates narrative justifications and concrete action plans
    for the top 3 recommendations.
    """
    
    def __init__(self, llm: BaseChatModel):
        """
        Initialize the Conseiller agent.
        
        Args:
            llm: A LangChain chat model
        """
        self.llm = llm
    
    def score_filiere(self, filiere: dict, profile: StudentProfile) -> float:
        """Public wrapper for scoring function."""
        return score_filiere(filiere, profile)
    
    async def run(self, state: StudentProfile) -> dict[str, Any]:
        """
        Generate top 3 recommendations with justifications and action plans.
        
        Args:
            state: Current StudentProfile state with filieres_retrieved populated
        
        Returns:
            Partial state update with top_3 list
        """
        filieres = state.get("filieres_retrieved", [])
        
        if not filieres:
            return {
                "top_3": [],
                "current_step": "coach_entretien",
                "error": "No filières available for recommendation"
            }
        
        # Score and sort filières
        scored_filieres = []
        for f in filieres:
            f_copy = dict(f)
            f_copy["score_calculated"] = self.score_filiere(f, state)
            scored_filieres.append(f_copy)
        
        scored_filieres.sort(key=lambda x: x["score_calculated"], reverse=True)
        
        # Format for LLM
        filieres_context = format_filieres_for_prompt(scored_filieres[:8], state)
        
        system_content = SYSTEM_PROMPT.format(
            top_filieres_with_scores=filieres_context,
            nom=state.get("nom", "Étudiant"),
            serie_bac=state.get("serie_bac", "Sciences"),
            ville=state.get("ville", "Non spécifiée"),
            budget=state.get("budget", "public"),
            langue=state.get("langue", "fr"),
            learning_style=state.get("learning_style", "mixte"),
            domain_scores=json.dumps(state.get("domain_scores", {})),
            interets=", ".join(state.get("interets", [])),
        )
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content="Génère le top 3 des filières recommandées avec justifications et plans d'action."),
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            response_text = response.content
            
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                top_3 = result.get("top_3", [])
            else:
                raise ValueError("No JSON found in response")
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Fallback: generate basic recommendations
            print(f"ConseillerAgent: LLM parsing failed ({e}), using fallback")
            
            top_3 = []
            for i, f in enumerate(scored_filieres[:3], 1):
                top_3.append({
                    "rang": i,
                    "filiere_id": f.get("id", ""),
                    "filiere_nom": f.get("nom", ""),
                    "type": f.get("type", ""),
                    "ville": f.get("ville", ""),
                    "score_final": f.get("score_calculated", 0.5),
                    "justification": (
                        f"Cette filière correspond bien à ton profil {state.get('serie_bac', '')} "
                        f"avec un taux d'emploi de {f.get('taux_emploi', 'N/A')}%. "
                        f"Elle est accessible depuis {state.get('ville', 'ta ville')} et "
                        f"offre des débouchés intéressants dans le domaine {f.get('domaine', '')}."
                    ),
                    "plan_action_30j": [
                        "Semaine 1: Recherche approfondie sur la filière et ses conditions d'accès",
                        "Semaine 2: Préparation du dossier de candidature (notes, lettres)",
                        "Semaine 3: Contact avec l'établissement et anciens étudiants",
                        "Semaine 4: Soumission de la candidature et préparation de l'entretien",
                        "Fin du mois: Suivi de la candidature et plan B si nécessaire"
                    ],
                    "etablissements_recommandes": [f.get("nom", "")],
                    "prochaine_etape": "Visite le site officiel de l'établissement pour vérifier les dates d'inscription"
                })
        
        return {
            "top_3": top_3,
            "current_step": "coach_entretien",
        }
