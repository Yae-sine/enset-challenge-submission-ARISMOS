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
from agents.static.advisor_prompt import SYSTEM_PROMPT
from agents.static.advisor_scoring import (
    score_filiere as _score_filiere,
    format_filieres_for_prompt,
)


def score_filiere(filiere: dict, profile: StudentProfile) -> float:
    """Compatibility wrapper re-exported for tests and external imports."""
    return _score_filiere(filiere, profile)


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
